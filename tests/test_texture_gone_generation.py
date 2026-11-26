"""The destroy generation the caches read moves whenever a texture goes.

The recording threads' view, slot and descriptor caches (gpu/vk/vk_draw.cpp), the FSR inputs and the reactive mask compare
texture_destroy_generation() to tell a texture that went from one that stands. It reads the gone ring (destroy_gens,
gpu/vk/gone_ring.h), which only destroy_gen_bump moves. A place that let a texture go and bumped only the old destroy_gen
counter left the generation still: every cache kept serving textures that were gone, and the game read freed memory in
play (texture_touch_quick from a parallel segment's texture_view_of, heap corruption, a lost device).

Checks, by the text of gpu/vk/vk_texture.cpp: texture_destroy_generation reads the ring; every destroy_gen++ also calls
destroy_gen_bump on the same statement; destroy_later bumps it for its texture.

    python -I -B tests/test_texture_gone_generation.py
"""
import re
import sys
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


def main():
    src = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    bad = []
    gen = block(src, "uint64_t texture_destroy_generation() {")
    if "destroy_gens.generation()" not in gen:
        bad.append("texture_destroy_generation does not read the gone ring")
    sites = [m.start() for m in re.finditer(r"\bdestroy_gen\+\+", src)]
    if not sites:
        bad.append("no destroy_gen++ found: this check is out of date")
    for at in sites:
        line_end = src.index("\n", at)
        line = src[src.rindex("\n", 0, at) + 1:line_end]
        if "destroy_gen_bump(" not in line:
            bad.append("line %d bumps destroy_gen without the ring: %s" % (src.count("\n", 0, at) + 1, line.strip()))
    later = block(src, "void destroy_later(Texture& tex) {")
    if "destroy_gen_bump(&tex)" not in later:
        bad.append("destroy_later does not bump the ring for its texture")
    for b in bad:
        print("FAIL:", b)
    print("texture gone generation: %s (%d sites)" % ("FAILED" if bad else "ok", len(sites)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
