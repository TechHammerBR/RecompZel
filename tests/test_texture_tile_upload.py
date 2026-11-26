"""Compare the CPU texture upload path to the reference deswizzle (texdecode's: gpu/vk/texdecode, itself checked against offsets
worked out by hand in tests/test_texdecode_swizzle.py), and its refusal to a zeroed level. Run with --cxx clang++ or g++."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from srccut import block

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

HARNESS = r"""
#include "texture_tiles.h"
#include "texdecode/texdecode.h"
#include <cassert>
#include <cstring>
#include <random>
#include <vector>
namespace texture_tiles = mkwvk::texture_tiles;
using texture_tiles::unswizzle;
// (vk_texture.cpp's anonymous namespace sits inside mkwvk: the cut function names texdecode:: without it)
namespace texdecode = mkwvk::texdecode;
// (the deswizzle the upload falls back to when texture_tiles does not take a level, counted)
namespace mkwvk::texdecode {
unsigned fallback_calls;
bool counted_deswizzle(std::span<uint8_t> linear, std::span<const uint8_t> swizzled, uint32_t bpb, uint32_t width, uint32_t height,
                       uint32_t depth, uint32_t tile_h, uint32_t tile_d) {
    ++fallback_calls;
    return deswizzle(linear, swizzled, bpb, width, height, depth, tile_h, tile_d);
}
}
unsigned refusals;
void texdecode_refused(const char*, const char*) { ++refusals; }   // (vk_texture.cpp's: a line in the log)
#define deswizzle counted_deswizzle
@UPLOAD@
#undef deswizzle
int main() {
    std::mt19937 random(817);
    for (unsigned bpb : {1u, 2u, 3u, 4u, 6u, 8u, 12u, 16u})
        for (unsigned width : {8u, 17u, 21u, 32u, 64u, 85u, 128u})
            for (unsigned height : {3u, 8u, 16u, 24u, 72u})
                for (unsigned tile : {0u, 1u, 3u, 5u})
                    for (unsigned depth : {1u, 2u}) {
                        const unsigned tile_d = depth == 2 ? 1 : 0;
                        const size_t pitch = width * bpb;
                        // Allocate both possible padding layouts. Compare their pixel contents safely.
                        const size_t cols = (((width+1u)&~1u)*bpb+63u)/64u;
                        const size_t rows_per_block = 8u << tile;
                        const size_t size = cols * 64 * rows_per_block *
                            ((height+rows_per_block-1)/rows_per_block) * depth;
                        std::vector<uint8_t> input(size+5);
                        for (auto& value : input) value = uint8_t(random());
                        const auto src = std::span(input).subspan(5);
                        std::vector<uint8_t> result(pitch*height*depth+32, 0x7f), ref=result;
                        auto output = std::span(result).subspan(7, pitch*height*depth);
                        assert(texdecode::deswizzle(std::span(ref).subspan(7,output.size()), src,
                                                    bpb,width,height,depth,tile,tile_d));
                        const unsigned before = texdecode::fallback_calls;
                        unswizzle_upload(output,src,bpb,width,height,depth,tile,tile_d);
                        assert(ref == result);
                        const bool complete = pitch % 64 == 0 && height % 8 == 0;
                        assert(texdecode::fallback_calls == before + (depth != 1 || !complete));
                        assert(!refusals);
                        if (depth != 1) continue;
                        assert(unswizzle(output,src,pitch,height,tile) == complete);
                        if (complete) {
                            assert(!unswizzle(output.first(output.size()-1),src,pitch,height,tile));
                            assert(!unswizzle(output,src.first(src.size()-1),pitch,height,tile));
                        }
                    }
    // (a refusal, which no caller makes: a source shorter than the level needs, here after the tiled path declined it. The destination
    // is zero, not what the staging memory held, and it is said once per call)
    {
        std::vector<uint8_t> in(512, 0x55), out(64 * 8 * 2, 0x7f);   // (the level is 64 x 8 x 2 bytes: the destination fits it, only the source is short)
        unswizzle_upload(out, std::span(in).first(100), 1, 64, 8, 2, 0, 1);
        assert(refusals == 1);
        for (uint8_t value : out) assert(value == 0);
    }
    assert(refusals == 1);
    uint8_t a[512]{};
    assert(!unswizzle(a,a,UINT64_MAX-63,8,0));
    assert(!unswizzle(a,a,64,8,32));
    assert(!unswizzle(a,a,0,8,0));
    assert(!unswizzle(a,a,64,0,0));
}
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    gpu = ROOT / 'gpu'
    upload = block((gpu/'vk/vk_texture.cpp').read_text(), 'void unswizzle_upload(')
    with tempfile.TemporaryDirectory() as folder:
        cpp = Path(folder)/'tiles.cpp'
        exe = Path(folder)/'tiles.exe'
        cpp.write_text(HARNESS.replace('@UPLOAD@',upload))
        flags = [args.cxx, '-std=c++20', '-O2', '-I', gpu/'vk']
        subprocess.run([*flags, '-Wall', '-Wextra', '-Werror', cpp, gpu/'vk/texdecode/block_linear.cpp', '-o', exe], check=True)
        subprocess.run([exe],check=True)

if __name__ == '__main__':
    main()
