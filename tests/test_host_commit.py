"""The texture cache is held to half of what the driver allows and to the commit the system can still hand out.

gpu/vk/host_commit.h holds the two rules (Fritchii v5.7's commit-room cap and reserve, and our ceiling by the card's memory); the
header is compiled as it is and run on the cases below, and vk_texture.cpp's texture_frame is checked to apply them in order,
after the preset's clamp and before the squeeze, with RX_VK_VRAM_FORCE as the way out. No GPU or game is involved.

python -I -B tests/test_host_commit.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <cstdint>
#include <cstdio>
#include "host_commit.h"

static int fails;
static void check(const char* what, uint64_t got, uint64_t want_mb) {
    if (got != (want_mb << 20)) std::printf("FAIL %s: %llu MB, expected %llu\n", what, (unsigned long long)(got >> 20),
                                            (unsigned long long)want_mb), fails++;
}

int main() {
    const uint64_t MB = 1ull << 20, GB = 1024 * MB;
    // (a 16 GB card, 15.3 GB allowed: half is 7.6 GB, so a 12 GB budget is held to it)
    check("16 GB card", host_commit::ceiling(15668 * MB), 7834);
    // (an 8 GB card, 7.3 GB allowed: half is 3.6 GB, under the 6 GB floor, so the ceiling is 6 GB and no preset is touched)
    check("8 GB card", host_commit::ceiling(7500 * MB), 6144);
    // (a 24 GB card: half of 23.5 GB)
    check("24 GB card", host_commit::ceiling(24064 * MB), 12032);
    // (64 GB PC, 40 GB of commit free, 4 GB of textures held: 44 GB less the 2 GB reserve)
    check("plenty of commit", host_commit::commit_cap(4 * GB, 40 * GB), 42 * 1024);
    // (16 GB PC with a small page file, 5 GB of commit left, 4 GB held: 9 GB less 2)
    check("tight commit", host_commit::commit_cap(4 * GB, 5 * GB), 7 * 1024);
    // (the commit nearly spent, 1 GB left, 4 GB held: 5 GB less 2 is 3 GB, which is the floor)
    check("at the floor", host_commit::commit_cap(4 * GB, 1 * GB), 3 * 1024);
    // (none left, 2 GB held: under the floor, so the floor: the cache is not emptied)
    check("none left", host_commit::commit_cap(2 * GB, 0), 3 * 1024);
    // (nothing held and nothing left: the floor, no wrap-around)
    check("all zero", host_commit::commit_cap(0, 0), 3 * 1024);
    // (room of less than the reserve: no unsigned underflow)
    check("under the reserve", host_commit::commit_cap(1 * GB, 512 * MB), 3 * 1024);
    if (!fails) std::printf("host commit: all cases pass\n");
    return fails != 0;
}
"""


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
    a = p.parse_args()
    source = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    frame = block(source, "void texture_frame(uint64_t completed)")
    preset = frame.index("budget = std::min(budget, (allowed / 4) * 3);")
    ceiling = frame.index("host_commit::ceiling(allowed)")
    cap = frame.index("host_commit::commit_cap(total_bytes, room)")
    squeeze = frame.index("const bool room_in_blocks")
    assert preset < ceiling < cap < squeeze, "texture_frame: the ceiling and the commit cap are not between the preset clamp and the squeeze"
    assert 'getenv("RX_VK_VRAM_FORCE")' in frame, "texture_frame: no RX_VK_VRAM_FORCE way out"
    assert '#include "host_commit.h"' in source, "vk_texture.cpp does not include host_commit.h"
    assert "K32GetPerformanceInfo" in source, "vk_texture.cpp: no system commit room"
    with tempfile.TemporaryDirectory(prefix="hookshot-host-commit-") as temp:
        src, exe = Path(temp) / "fixture.cpp", Path(temp) / "fixture.exe"
        src.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++17", "-O0", "-Wall", "-Wextra", "-Werror", f"-I{ROOT / 'gpu/vk'}", str(src), "-o", str(exe)],
                       check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
