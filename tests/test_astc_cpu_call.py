"""The renderer's CPU ASTC call (the astc_decode statement in vk_texture.cpp's upload_inner, cut out of the source with tests/srccut.py
and compiled against gpu/vk/texdecode) and its sRGB rule (astc_nvn_srgb):
  - an all-zero block is an illegal one, and the call gives 00000000 for every texel, as main's decoder and the GPU shader do (not
    texdecode's default, opaque magenta), and its count of illegal blocks comes back (what astc_error_blocks_told logs);
  - a legal block is not changed by that colour, and sRGB formats decode in the sRGB mode, the others in the linear mode;
  - astc_nvn_srgb is the rule vk_format() (vk_formats.cpp) has: sRGB for NVN formats from its sRGB bound up to the last ASTC one.
Run with --cxx clang++ or g++."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from srccut import block, between

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

HARNESS = r"""
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <span>
#include <vector>
#include "texdecode/texdecode.h"
namespace texdecode = mkwvk::texdecode;
@SRGB@
struct Level { uint32_t w, d; };
struct Tex { int block_w, block_h, nvn_format; };
// (vk_format's rule, from vk_formats.cpp: the ASTC formats and the first sRGB one)
static bool rule(int nvn) { return nvn >= @FIRST@ && nvn <= @LAST@ && nvn >= @SRGB_FROM@; }
// (one call as upload_inner makes it, on a level of 8 x 8 texels of 4 x 4 blocks)
static int64_t call(const std::vector<uint8_t>& in, int nvn, std::vector<uint8_t>& result) {
    const Level g{8, 1};
    const uint32_t px_h = 8;
    const Tex tex{4, 4, nvn};
    const uint64_t block_bytes = in.size(), out_bytes = result.size();
    uint8_t* const out = result.data();
    const uint8_t* const blocks = in.data();
    @CALL@
    return bad;
}
int main() {
    for (int nvn = 0; nvn < 0x100; nvn++) assert(astc_nvn_srgb(nvn) == rule(nvn));
    std::vector<uint8_t> out(8 * 8 * 4, 0x5A);
    for (int nvn : {0x79, 0x87}) {   // (a linear and an sRGB format)
        const std::vector<uint8_t> zero(4 * 16, 0);
        assert(call(zero, nvn, out) == 4);   // (the four blocks are counted)
        for (uint8_t value : out) assert(value == 0);
    }
    // (a legal block, from tests/test_texdecode_astc_partitions.py's controls, is not changed by the error colour, and the format picks
    // the mode: the linear and the sRGB decodes of it differ, and the call gives each its own)
    static const uint8_t legal_block[16] = {0xbe, 0x87, 0xd5, 0x47, 0x3e, 0xb6, 0x10, 0xa8, 0xd2, 0xc3, 0xf6, 0xea, 0x00, 0xe6, 0x5e, 0x8d};
    std::vector<uint8_t> legal;
    for (int b = 0; b < 4; b++) legal.insert(legal.end(), legal_block, legal_block + 16);
    uint8_t lin[4 * 4 * 4], srgb[4 * 4 * 4];
    assert(texdecode::astc_decode_block(legal_block, 4, 4, false, lin));
    assert(texdecode::astc_decode_block(legal_block, 4, 4, true, srgb));
    assert(memcmp(lin, srgb, sizeof lin));
    assert(call(legal, 0x79, out) == 0);
    for (int y = 0; y < 8; y++) assert(!memcmp(&out[y * 8 * 4], &lin[(y % 4) * 16], 16) && !memcmp(&out[y * 8 * 4 + 16], &lin[(y % 4) * 16], 16));
    assert(call(legal, 0x87, out) == 0);
    for (int y = 0; y < 8; y++) assert(!memcmp(&out[y * 8 * 4], &srgb[(y % 4) * 16], 16) && !memcmp(&out[y * 8 * 4 + 16], &srgb[(y % 4) * 16], 16));
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    source = (ROOT / 'gpu/vk/vk_texture.cpp').read_text()
    srgb = block(source, 'bool astc_nvn_srgb(')
    call = between(source, 'const int64_t bad = texdecode::astc_decode(', '                    if (bad < 0) {')
    call = 'const int64_t bad = texdecode::astc_decode(' + call[len('const int64_t bad = texdecode::astc_decode('):]
    formats = (ROOT / 'gpu/vk/vk_formats.cpp').read_text()
    m = re.search(r'if \(nvn_format >= (0x[0-9a-f]+) && nvn_format <= (0x[0-9a-f]+)\) \{\s*const int i = [^;]*;\s*const bool srgb = nvn_format >= (0x[0-9a-f]+);', formats)
    if not m:
        raise SystemExit("vk_format()'s ASTC range and sRGB rule are not where this check reads them (vk_formats.cpp)")
    text = (HARNESS.replace('@SRGB@', srgb).replace('@CALL@', call).replace('@FIRST@', m.group(1)).replace('@LAST@', m.group(2))
            .replace('@SRGB_FROM@', m.group(3)))
    with tempfile.TemporaryDirectory() as folder:
        cpp = Path(folder) / 'call.cpp'
        exe = Path(folder) / 'call.exe'
        cpp.write_text(text)
        subprocess.run([args.cxx, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-I', ROOT / 'gpu/vk', cpp,
                        ROOT / 'gpu/vk/texdecode/astc.cpp', '-o', exe], check=True)
        subprocess.run([exe], check=True)
    print("PASS")


if __name__ == '__main__':
    main()
