"""A pass hazard does not walk every texture the pass has sampled.

Earlier draws record the targets they sampled as bits. A later draw that writes one
of those targets is the hazard. python -I -B tests/test_pass_hazard.py [--cxx g++] [--headers <Vulkan headers>]
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
    haz = block(source, "uint16_t draw_hazards(")
    if "for (const Texture* t : ps.sampled)" in haz or "for (const Texture* t : pass().sampled)" in haz:
        raise SystemExit("a pass hazard walks every texture sampled so far")
    if "writes_sampled_target(" not in haz:
        raise SystemExit("a pass hazard ignores the targets earlier draws sampled")
    if haz.index("gfx_sampled") > haz.index("writes_sampled_target("):
        raise SystemExit("a draw's own samples are treated as an earlier draw's")
    begin = block(source, "void begin_pass(")
    clear = begin.index("ps.sampled.clear()")
    if "sampled_targets = 0" not in begin[clear:clear + 80]:
        raise SystemExit("a new pass keeps the targets earlier draws sampled")
    ins = source.index("ps.sampled.push_back(t);")
    wrote = source.index("ps.written |= writes;", ins)
    if "sampled_targets" not in source[ins:wrote]:
        raise SystemExit("a sampled target is invisible to the next draw")
    # (the functions run below are draw_key.h's, which vk_draw.cpp includes: they were cut out of vk_draw.cpp by their text)
    key = (ROOT / "gpu" / "vk" / "draw_key.h").read_text(encoding="utf-8")
    if '#include "draw_key.h"' not in source:
        raise SystemExit("vk_draw.cpp does not include draw_key.h: what runs below is not what a draw runs")
    for fn in ("bool writes_sampled_target(",):
        if fn in source or fn not in key:
            raise SystemExit("draw_key.h is not the one place that defines " + fn)
    fixture = f'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
#include "draw_key.h"
using namespace mkwvk;
int main() {{
    CHECK(writes_sampled_target(1u, 1u));
    CHECK(writes_sampled_target(0x100u, 0x100u));
    CHECK(writes_sampled_target(0x5u, 0x4u));
    CHECK(!writes_sampled_target(1u, 2u));
    CHECK(!writes_sampled_target(0u, 0x1FFu));
    CHECK(!writes_sampled_target(0x1FFu, 0u));
    std::printf("PASS: a draw hazards only the targets earlier draws sampled\\n");
}}
'''
    with tempfile.TemporaryDirectory(prefix="pass-hazard-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                        *(["-I", str(a.headers)] if a.headers else []), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
