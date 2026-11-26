"""(recompzel) A texture the upload budget held back comes in at the next presents, not 30 s later.

Two parts (2026-11-26, RTX 4080: the Kokiri Forest's cliffs and Hyrule Field's ground sampled as the dummy for 29-32 s after a
load, the log's "in at last 1760 presents" lines):
- vk_draw.cpp texture_view_of keeps no empty answer for a registered slot whose texture has no image yet: kept, every later
  binding got the dummy until some texture was destroyed;
- vk_texture.cpp upload_defer holds one back at most RX_VK_UPLOAD_DEFER_FRAMES presents (2), whatever the budget.
And scripts/texture_problems.py reads both kinds of line from a log.

    python -I -B tests/test_defer_lookup_retry.py
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = []


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def check(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)


def main():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    tex = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    # (the store into the lookup cache comes after an early return for a registered slot with no image)
    store = draw.index("handle_hits()[key] = {view, tex, dgen, level, version")
    guard = draw.rfind("if (!view && known && !tex) {", 0, store)
    check(guard > 0 and store - guard < 400, "texture_view_of keeps the empty answer of a slot whose texture has no image yet")
    body = block(tex, "bool upload_defer(Texture& tex) {")
    check("RX_VK_UPLOAD_DEFER_FRAMES" in body, "upload_defer has no hold limit")
    rule = re.search(r"if \(tex\.defer_frame && frame_no - tex\.defer_frame >= max_hold\) return false;", body)
    check(rule is not None and body.index(rule.group(0)) < body.index("const int64_t spent"),
          "upload_defer's hold limit is not checked before the budget")
    # (the rule itself, compiled: held at present 10, max 2)
    src = r'''#include <cstdint>
#include <cstdio>
struct Texture { uint64_t defer_frame = 0; };
static uint64_t frame_no;
static bool held_out(const Texture& tex, uint64_t max_hold) {
    if (tex.defer_frame && frame_no - tex.defer_frame >= max_hold) return true;
    return false;
}
int main() {
    Texture t; t.defer_frame = 10;
    int bad = 0;
    frame_no = 10; bad += held_out(t, 2);    /* the present it was held at: may still wait */
    frame_no = 11; bad += held_out(t, 2);    /* one later: may still wait */
    frame_no = 12; bad += !held_out(t, 2);   /* two later: uploaded */
    Texture fresh; frame_no = 500; bad += held_out(fresh, 2);   /* never held: the budget decides */
    if (bad) { std::printf("FAIL %d\n", bad); return 1; }
    return 0;
}
'''
    cxx = os.environ.get("CXX", "c++")
    with tempfile.TemporaryDirectory() as d:
        c, exe = Path(d) / "t.cpp", Path(d) / "t.exe"
        c.write_text(src)
        r = subprocess.run([cxx, "-std=c++17", "-Wall", "-Werror", str(c), "-o", str(exe)], capture_output=True, text=True)
        if r.returncode != 0:
            print("skip: no C++ compiler (%s)" % r.stderr.strip()[:200])
        else:
            check(subprocess.run([str(exe)]).returncode == 0, "the hold rule")
        log = Path(d) / "hookshot_log.txt"
        log.write_text(
            "[hos host] vk: texture problem [dummy]: slot 0xb30 (handle 0x18c00b30) sampled as the dummy: no image for it\n"
            "[hos host] vk: deferral: texture #784 768x768 x1 NVN 0x7b, held back at present 5394, in at last 1760 presents "
            "and 29403 ms later\n"
            "[hos host] vk: texture problems: dummy 1, upload-failed 0, astc-illegal 0 (since the start; x)\n", encoding="utf-8")
        out = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/texture_problems.py"), str(log)], capture_output=True,
                             text=True, check=True).stdout
        check("dummy: 1" in out and "late: 1" in out and "768x768 x1 NVN 0x7b: 1760 presents" in out,
              "texture_problems.py does not read the lines:\n" + out)
    print("defer lookup retry: ok")


if __name__ == "__main__":
    main()
