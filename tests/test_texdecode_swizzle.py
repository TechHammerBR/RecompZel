"""The block-linear swizzle and deswizzle (gpu/vk/texdecode/block_linear.cpp): round trips over a table of layouts, the padding left alone, strips, refusals and offsets worked out by hand from the GOB layout rules.
python -I -B tests/test_texdecode_swizzle.py [--cxx c++]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "c++"))
    args = parser.parse_args()
    cxx = shutil.which(args.cxx)
    if not cxx:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="hookshot-texdecode-") as folder:
        exe = Path(folder) / "t"
        r = subprocess.run([cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                            str(ROOT / "tests" / "texdecode_swizzle_test.cpp"), str(ROOT / "gpu" / "vk" / "texdecode" / "block_linear.cpp"),
                            "-o", str(exe)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise SystemExit("FAIL: texdecode_swizzle_test.cpp does not compile\n" + r.stdout + r.stderr)
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        print(r.stdout, end="")
        if r.returncode:
            raise SystemExit("FAIL: texdecode_swizzle_test failed\n" + r.stderr)


if __name__ == "__main__":
    main()
