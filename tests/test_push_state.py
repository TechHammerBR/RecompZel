"""The pushed descriptors are remembered as one vector of words, compared and kept in place.

A program change pushes every write, and the next draws of it push the writes that changed. The old bookkeeping was a vector of
vectors resized to each program's writes, so a program with more writes than the one before it grew new vectors word by word.
python -I -B tests/test_push_state.py [--cxx g++] [--headers <Vulkan headers>]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--headers", "{vulkan_headers}"]   # (draw_key.h includes Vulkan's, for its types)

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--headers", type=Path, help="the Vulkan headers, where the compiler does not find them itself")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    # (the functions run below are draw_key.h's, which vk_draw.cpp includes: they were cut out of vk_draw.cpp by their text)
    key = (ROOT / "gpu" / "vk" / "draw_key.h").read_text(encoding="utf-8")
    if '#include "draw_key.h"' not in source:
        raise SystemExit("vk_draw.cpp does not include draw_key.h: what runs below is not what a draw runs")
    for fn in ("void words_append(", "int words_same_store("):
        if fn in source or fn not in key:
            raise SystemExit("draw_key.h is not the one place that defines " + fn)
    bind = block(source, "bool bind_descriptors(")
    full = bind[: bind.index("static thread_local std::vector<VkWriteDescriptorSet> changed")]
    if "ps.words.clear(), ps.at.clear()" not in full or "ps.n = wr.writes.size()" not in full:
        raise SystemExit("a full push does not remember its words")
    fixture = f'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
#include "draw_key.h"
using namespace mkwvk;
// (Vulkan's own structs, as draw_key.h takes them: a handle is a made-up number, never handed to a driver)
template <class T> T handle(uint64_t v) {{ return (T)v; }}
int main() {{
    VkDescriptorBufferInfo b[2] = {{{{handle<VkBuffer>(1), 2, 3}}, {{handle<VkBuffer>(4), 5, 6}}}};
    VkDescriptorImageInfo i[1] = {{{{handle<VkSampler>(7), handle<VkImageView>(8), (VkImageLayout)1}}}};
    VkBufferView t[1] = {{handle<VkBufferView>(9)}};
    VkWriteDescriptorSet w[3] = {{}};
    // (the types by their numbers, which the words below hold: 6 a uniform buffer, 1 a combined image sampler, 4 a uniform texel buffer)
    w[0].dstBinding = 0, w[0].descriptorCount = 2, w[0].descriptorType = (VkDescriptorType)6, w[0].pBufferInfo = b;
    w[1].dstBinding = 1, w[1].descriptorCount = 1, w[1].descriptorType = (VkDescriptorType)1, w[1].pImageInfo = i;
    w[2].dstBinding = 2, w[2].descriptorCount = 1, w[2].descriptorType = (VkDescriptorType)4, w[2].pTexelBufferView = t;
    std::vector<uint64_t> words;
    std::vector<uint32_t> at;
    for (auto& x : w) at.push_back((uint32_t)words.size()), words_append(x, words);
    // (each write's type and binding, then its descriptors: the words the vector of vectors held)
    const std::vector<uint64_t> want = {{6ull << 32 | 0, 1, 2, 3, 4, 5, 6, 1ull << 32 | 1, 7, 8, 4ull << 32 | 2, 9}};
    CHECK(words == want);
    CHECK(at.size() == 3 && at[1] == 7 && at[2] == 10 && words.size() == 12);
    const uint64_t* e = words.data();
    auto same = [&](int k) {{ return words_same_store(w[k], words.data() + at[k], e + (k < 2 ? at[k + 1] : words.size())); }};
    for (int k = 0; k < 3; k++) CHECK(same(k) == 1);
    b[1].range = 60;                                 // (a buffer range changed: that write only)
    CHECK(same(0) == 0);
    CHECK(same(0) == 1);                             // (and kept: the same again)
    CHECK(same(1) == 1 && same(2) == 1);
    i[0].imageView = handle<VkImageView>(80);
    CHECK(same(1) == 0 && same(1) == 1);
    t[0] = handle<VkBufferView>(90);
    CHECK(same(2) == 0 && same(2) == 1);
    CHECK(words[at[0] + 6] == 60 && words[at[1] + 2] == 80 && words[at[2] + 1] == 90 && words.size() == 12);
    w[0].descriptorCount = 1;                        // (a write that is not the one the words were made for: refused, nothing touched)
    const std::vector<uint64_t> before = words;
    CHECK(same(0) == -1 && words == before);
    std::printf("PASS: pushed descriptors are compared and kept in one vector\\n");
}}
'''
    with tempfile.TemporaryDirectory(prefix="push-state-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                        *(["-I", str(a.headers)] if a.headers else []), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
