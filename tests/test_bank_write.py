"""bank_write.h (the native driver-bank writer, HL_UBO_WRITER) against the word-by-word fill: every bank size, random state."""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="clang++")
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="bank-write-") as temp:
        exe = Path(temp) / "bank_write_test.exe"
        subprocess.run([a.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/bank_write_test.cpp"), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], check=True, timeout=120, capture_output=True, text=True).stdout
        assert " 0 mismatches" in out, out
    print("PASS:", out.strip())


if __name__ == "__main__":
    main()
