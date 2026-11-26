"""vk_texture.cpp's two lines about the CPU ASTC decoder: an illegal-block count said once per texture and for the first 16
textures only, with counts and ids and never a texel value (astc_error_blocks_told), and a refusal from texdecode said at most
5 times (texdecode_refused). Both functions are cut out of the source (tests/srccut.py) and compiled against a stand-in log.
Run with --cxx clang++ or g++."""
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
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>
static std::vector<std::string> lines;
static void logf(const char* fmt, ...) {
    char text[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(text, sizeof text, fmt, args);
    va_end(args);
    lines.push_back(text);
}
struct Texture { uint32_t id, width, height; int nvn_format; };
@TOLD@
@REFUSED@
int main() {
    // (one line per texture, however often its upload decodes illegal blocks)
    for (int again = 0; again < 3; again++) astc_error_blocks_told(Texture{7, 256, 128, 0x79}, 12);
    assert(lines.size() == 1);
    assert(lines[0].find("#7 ") != std::string::npos && lines[0].find("12 illegal blocks") != std::string::npos);
    assert(lines[0].find("256x128") != std::string::npos && lines[0].find("0x79") != std::string::npos);
    // (the first 16 textures only, the last line saying so)
    for (uint32_t id = 100; id < 140; id++) astc_error_blocks_told(Texture{id, 4, 4, 0x80}, 1);
    assert(lines.size() == 16);
    assert(lines.back().find("no more such lines") != std::string::npos);
    assert(lines[0].find("no more such lines") == std::string::npos);
    // (a refusal: 5 lines at most, each saying what became of the result)
    lines.clear();
    for (int n = 0; n < 20; n++) texdecode_refused("ASTC decode", "the texels are zero");
    assert(lines.size() == 5);
    assert(lines[0].find("ASTC decode") != std::string::npos && lines[0].find("the texels are zero") != std::string::npos);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    source = (ROOT / 'gpu/vk/vk_texture.cpp').read_text()
    told = block(source, 'void astc_error_blocks_told(')
    refused = block(source, 'void texdecode_refused(')
    with tempfile.TemporaryDirectory() as folder:
        cpp = Path(folder) / 'log.cpp'
        exe = Path(folder) / 'log.exe'
        cpp.write_text(HARNESS.replace('@TOLD@', told).replace('@REFUSED@', refused))
        subprocess.run([args.cxx, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', cpp, '-o', exe], check=True)
        subprocess.run([exe], check=True)
    print("PASS")


if __name__ == '__main__':
    main()
