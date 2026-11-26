"""Regenerate tests/texdecode_astc_vectors.vec, the ASTC decoder's test vectors (gpu/vk/texdecode/astc.cpp).

The file holds random 16-byte blocks for the 14 ASTC footprints, and for each what ARM's astcenc 8-bit decode gives in the linear
and the sRGB mode (a checksum) and whether astcenc calls it an error block (texdecode_astc_gen.cpp). astcenc is not in this
repository: build it yourself (cmake, ASTCENC_DECOMPRESSOR=OFF is fine, any ISA, one static library) and point this at its
Source folder and the library. The blocks are random numbers from a fixed seed, never game data; the same astcenc gives the
same file. The test (tests/test_texdecode_astc.py) needs no astcenc.

After the random blocks come blocks built by hand for cases random bytes almost never reach (a void extent with equal low and
high coordinates, one with wrong reserved bits, the 6x10 and 10x6 weight grids, block modes with 97 to 100 weight bits), from a
seed of their own, so the random part is the same bytes with or without them; the generator stops if astcenc does not answer
for one of them as its kind says. Regenerating with the same astcenc gives the same file byte for byte (about 170 KB).

python -I -B scripts/gen_texdecode_astc_vectors.py --astcenc-src PATH/astc-encoder/Source --astcenc-lib PATH/libastcenc-avx2-static.a [--cxx c++]
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--astcenc-src", required=True, help="astcenc's Source folder (astcenc.h)")
    p.add_argument("--astcenc-lib", required=True, help="the static library built from it")
    p.add_argument("--cxx", default="c++")
    p.add_argument("--out", default=str(ROOT / "tests" / "texdecode_astc_vectors.vec"))
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="texdecode-gen-") as folder:
        exe = Path(folder) / "gen"
        subprocess.run([a.cxx, "-std=c++17", "-O2", "-I", a.astcenc_src, str(ROOT / "scripts" / "texdecode_astc_gen.cpp"),
                        a.astcenc_lib, "-lpthread", "-o", str(exe)], check=True)
        subprocess.run([str(exe), a.out], check=True)


if __name__ == "__main__":
    main()
