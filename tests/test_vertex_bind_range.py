"""A draw whose vertex streams changed binds the bindings that changed, not all 16 (gpu/vk/vk_draw.cpp; no game/GPU).

The driver takes every binding it is handed. A draw whose streams differed from the last ones bound handed it all 16,
the unused ones with the zero buffer again: 1.1 % of the replay thread on a Steam Deck, in the driver. vertex_bind_range
gives the bindings that differ from what this command buffer has, and only those are bound.

Runs vertex_bind_range (gpu/vk/draw_key.h, which vk_draw.cpp includes); checks draw() binds its range and still remembers all 16.

python -I -B tests/test_vertex_bind_range.py [--cxx g++] [--headers <Vulkan headers>]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]   # (draw_key.h includes Vulkan's, for its types)

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--headers", type=Path, help="the Vulkan headers, where the compiler does not find them itself")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    draw = block(source, "void draw(")
    ask = "vertex_bind_range(vbufs, voffs, vsizes, vstrides, cb.vb.b, cb.vb.o, cb.vb.z, cb.vb.s, cb.vb_valid, &vb_first, &vb_count);"
    bind = "vkCmdBindVertexBuffers2(cmd, vb_first, vb_count, vbufs + vb_first, voffs + vb_first, vsizes + vb_first, vstrides + vb_first);"
    for needle in (ask, bind):
        if needle not in draw:
            raise SystemExit("draw() no longer has: " + needle)
    if source.count("vkCmdBindVertexBuffers2(") != 1 or "vkCmdBindVertexBuffers2(cmd, 0, 16," in source:
        raise SystemExit("the vertex streams are bound from somewhere that does not ask for the range")
    if not draw.index(ask) < draw.index(bind) < draw.index("std::memcpy(cb.vb.b, vbufs, sizeof vbufs)"):
        raise SystemExit("draw() binds before it asks for the range, or remembers the streams before it binds them")
    for needle in ("std::memcpy(cb.vb.b, vbufs, sizeof vbufs), std::memcpy(cb.vb.o, voffs, sizeof voffs);",
                   "std::memcpy(cb.vb.z, vsizes, sizeof vsizes), std::memcpy(cb.vb.s, vstrides, sizeof vstrides);"):
        if needle not in draw:
            raise SystemExit("draw() no longer remembers all 16 bindings after a bind: " + needle)
    # (the functions run below are draw_key.h's, which vk_draw.cpp includes: they were cut out of vk_draw.cpp by their text)
    key = (ROOT / "gpu" / "vk" / "draw_key.h").read_text(encoding="utf-8")
    if '#include "draw_key.h"' not in source:
        raise SystemExit("vk_draw.cpp does not include draw_key.h: what runs below is not what a draw runs")
    for fn in ("void vertex_bind_range(",):
        if fn in source or fn not in key:
            raise SystemExit("draw_key.h is not the one place that defines " + fn)
    fixture = f'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
#include "draw_key.h"
using namespace mkwvk;
// (a buffer is a made-up number, never handed to a driver)
static VkBuffer buf(uint64_t v) {{ return (VkBuffer)v; }}
int main() {{
    VkBuffer b[16], lb[16];
    VkDeviceSize o[16], z[16], s[16], lo[16], lz[16], ls[16];
    for (int i = 0; i < 16; i++) b[i] = lb[i] = buf(100 + i), o[i] = lo[i] = 8 * i, z[i] = lz[i] = 65536, s[i] = ls[i] = 12;
    uint32_t first = 99, count = 99;
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, false, &first, &count);   // (nothing bound on this command buffer yet)
    CHECK(first == 0 && count == 16);
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);    // (the same 16: nothing to bind)
    CHECK(count == 0);
    b[3] = buf(7);                                                          // (one stream's buffer)
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);
    CHECK(first == 3 && count == 1);
    o[9] = 4096;                                                            // (and another's offset: the range over both)
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);
    CHECK(first == 3 && count == 7);
    b[3] = lb[3], o[9] = lo[9], s[0] = 16;                                  // (a stride alone, the first binding)
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);
    CHECK(first == 0 && count == 1);
    s[0] = ls[0], z[15] = 1;                                                // (a size alone, the last binding)
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);
    CHECK(first == 15 && count == 1);
    b[0] = buf(1);                                                          // (the first and the last: all 16)
    vertex_bind_range(b, o, z, s, lb, lo, lz, ls, true, &first, &count);
    CHECK(first == 0 && count == 16);
    std::puts("vertex bind range: ok");
    return 0;
}}
'''
    with tempfile.TemporaryDirectory(prefix="vertex-bind-range-") as tmp:
        cpp, exe = Path(tmp) / "t.cpp", Path(tmp) / "t"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                        *(["-I", str(a.headers)] if a.headers else []), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
