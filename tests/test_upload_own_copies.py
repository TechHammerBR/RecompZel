"""A texture's first upload and re-upload take only the copies its own submission's capture took (gpu/vk/vk_memory.cpp
memory_as_submitted, after HeyListen 9a697a6c / 9f725aa1).

OoT fills reused texture storage after submitting the draws that sample it and rewrites lightmaps in place, a page more than once;
an upload that read an earlier capture's copy drew one frame in the wrong colours (white and magenta lighting, a banner or the
ground in another material's colours). memory_as_submitted is compiled here with stubs over a two-page shadow: the page the
recorded submission's capture took comes from the copy, the page an earlier capture took from guest memory, and with
RX_VK_FIRST_UPLOAD_OWN=0 / RX_VK_REUPLOAD_OWN=0, or an upload of neither kind, both copies as before. No game or GPU required.

python -I -B tests/test_upload_own_copies.py [--cxx clang++]
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


FIXTURE = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>
void logf(const char*, ...) {}
struct ShadowPage { std::unique_ptr<uint8_t[]> b; uint64_t seq = 0; };
std::unordered_map<uint32_t, ShadowPage> shadow;
std::unordered_map<uint32_t, uint32_t> shadow_regions;
std::atomic<size_t> shadow_n{0};
std::atomic<uint64_t> shadow_seq_own{0};
std::mutex shadow_mu;
std::vector<int> tex_spans;
uint64_t tex_merged_bytes = 0;
bool overlay_off() { return false; }
std::atomic<int64_t> st_overlaid{0}, st_differed{0};
std::atomic<int64_t> st_first_live{0}, st_again_live{0};
@OWN@
@FN@
int main(int argc, char** argv) {
    const int kind = atoi(argv[1]);   // 0: neither, 1: first upload, 2: re-upload
    std::vector<uint8_t> live(8192, 0xAA), scratch;
    for (uint32_t p = 0; p < 2; p++) {
        ShadowPage s;
        s.b.reset(new uint8_t[4096]);
        std::memset(s.b.get(), p == 0 ? 0x11 : 0x22, 4096);
        s.seq = p == 0 ? 7 : 3;   // (page 0: the recorded submission's capture, 7; page 1: an earlier one's, 3)
        shadow[0x100000 + p] = std::move(s);
    }
    shadow_regions[(0x100000ull << 12) >> 21] = 2;
    shadow_n = 2;
    shadow_seq_own = 7;
    const uint8_t* r = memory_as_submitted(0x100000ull << 12, live.data(), 8192, scratch, kind == 1, kind == 2);
    std::printf("%02x %02x\n", r[0], r[4096]);
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    a = p.parse_args()
    mem = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8-sig")
    tex = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8-sig")
    own = "\n".join(block(mem, m) for m in ("static bool own_copies_on(", "bool first_upload_own_on()", "bool reupload_own_on()"))
    fn = block(mem, "const uint8_t* memory_as_submitted(")
    assert "shadow_seq_own.store(shadow_seq, std::memory_order_relaxed);" in mem, "the capture does not record its own seq"
    assert "tl_first_upload = !tex.uploaded, tl_reupload = tex.uploaded;" in tex, "upload() does not say which upload it is"
    assert "memory_as_submitted(gpu, p, n, scratch, tl_first_upload, tl_reupload)" in tex, "guest_bytes does not pass the kind"
    with tempfile.TemporaryDirectory(prefix="own-copies-") as tmp:
        cpp = Path(tmp) / "f.cpp"
        exe = Path(tmp) / ("f.exe" if os.name == "nt" else "f")
        cpp.write_text(FIXTURE.replace("@OWN@", own).replace("@FN@", fn), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", str(cpp), "-o", str(exe)], check=True)
        base = {k: v for k, v in os.environ.items() if k not in ("RX_VK_FIRST_UPLOAD_OWN", "RX_VK_REUPLOAD_OWN")}
        cases = [("neither kind: both copies", "0", {}, "11 22"),
                 ("first upload: own copy, earlier page from guest memory", "1", {}, "11 aa"),
                 ("re-upload: the same", "2", {}, "11 aa"),
                 ("first upload, RX_VK_FIRST_UPLOAD_OWN=0: both copies", "1", {"RX_VK_FIRST_UPLOAD_OWN": "0"}, "11 22"),
                 ("re-upload, RX_VK_REUPLOAD_OWN=0: both copies", "2", {"RX_VK_REUPLOAD_OWN": "0"}, "11 22")]
        for name, kind, env, want in cases:
            out = subprocess.run([str(exe), kind], env={**base, **env}, check=True, capture_output=True, text=True).stdout.strip()
            assert out == want, "%s: %s, wanted %s" % (name, out, want)
    print("PASS an upload takes only its own submission's copies (5 cases)")


if __name__ == "__main__":
    main()
