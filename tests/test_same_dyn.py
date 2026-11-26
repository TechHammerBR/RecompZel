"""A draw does not rebuild dynamic state that matches the draw before it.

python -I -B tests/test_same_dyn.py [--cxx g++] [--headers <Vulkan headers>]
"""
import argparse
import re
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
    for fn in ("bool dyn_same(",):
        if fn in source or fn not in key:
            raise SystemExit("draw_key.h is not the one place that defines " + fn)
    pack = block(source, "int dyn_pack(")
    for needle in ("s.viewport", "s.scissor", "s.chmask", "s.blend", "s.ds", "wm_sig", "s.poly"):
        if needle not in pack:
            raise SystemExit(f"dynamic state is remembered without {needle}")
    reads = lambda text: set(re.findall(r"info\.(\w+)", text))
    mask, sig = block(source, "uint32_t target_write_mask("), block(source, "uint64_t program_wm_sig(")
    if reads(mask) != reads(sig):
        raise SystemExit(f"target_write_mask reads {sorted(reads(mask))} but the program's write mask word is made from {sorted(reads(sig))}")
    body = block(source, "void dynamic_state(")
    # (the program in the key is what its write masks are made from: a draw of another program with the same masks is the same
    # state. The word is dyn_pack's argument, which dynamic_state gives it from the draw's program)
    if ("std::memcpy(raw + atb, &wm_sig, 8);" not in pack or
            "dyn_pack(s, at, topo, mesh, program_wm_sig(p), df, du, db)" not in body):
        raise SystemExit("dynamic state is remembered by program, not by what the program makes of the write masks")
    if body.index("dyn_same(") > body.index("std::memset(&d, 0"):
        raise SystemExit("dynamic state is built before checking the draw before it")
    guard = body[:body.index("dyn_same(")]
    if "cb.dyn_valid" not in guard:
        raise SystemExit("a clear's dynamic state is left unset")
    fixture = f'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
#include "draw_key.h"
using namespace mkwvk;
int main() {{
    float fp[2]{{1.f, 2.f}}, cfp[2]{{1.f, 2.f}};
    uint32_t up[2]{{3, 4}}, cup[2]{{3, 4}};
    uint8_t raw[2]{{5, 6}}, craw[2]{{5, 6}};
    CHECK(dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    cfp[1] = 9.f;
    CHECK(!dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    cfp[1] = 2.f;
    cup[0] = 8;
    CHECK(!dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    cup[0] = 3;
    cup[1] = 4 | 1u << 31;   // (the last word, in its last byte: the words are compared whole)
    CHECK(!dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    cup[1] = 4;
    craw[1] = 7;
    CHECK(!dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    craw[1] = 6;
    cfp[0] = -0.f, fp[0] = 0.f;   // (the floats by value, as before: -0 is 0)
    CHECK(dyn_same(fp, 2, up, 2, raw, 2, cfp, cup, craw));
    CHECK(!dyn_same(fp, 0, up, 2, raw, 2, cfp, cup, craw));
    std::printf("PASS: the same dynamic state is not built again\\n");
}}
'''
    with tempfile.TemporaryDirectory(prefix="same-dyn-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                        *(["-I", str(a.headers)] if a.headers else []), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
