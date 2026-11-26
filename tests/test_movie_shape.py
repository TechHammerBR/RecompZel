"""The MOVIE patch keeps a centered 16:9 viewport on wide and narrow pictures.

python -I -B tests/test_movie_shape.py [--cc gcc] [--movie-module /path/to/oot_wide.py]
"""

import argparse
import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "{cc}"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct { uint64_t x[32]; } Ctx;
static unsigned char mem[64];
enum { VP = 8 };
volatile float hos_wide_ratio, hos_wide_margin;

static uint32_t recomp_load32(Ctx *c, uint64_t addr) {
    uint32_t bits;
    (void)c;
    assert(addr <= sizeof mem - sizeof bits);
    memcpy(&bits, mem + addr, sizeof bits);
    return bits;
}

static void recomp_store32(Ctx *c, uint64_t addr, uint32_t bits) {
    (void)c;
    assert(addr <= sizeof mem - sizeof bits);
    memcpy(mem + addr, &bits, sizeof bits);
}

static void movie(Ctx *c) {
    @MOVIE@
}

static int check(const char *name, float ratio, float margin, const float expected[4]) {
    static const float original[] = {10.0f, 20.0f, 330.0f, 200.0f};
    static const char *const edge[] = {"left", "top", "right", "bottom"};
    Ctx c = {0};
    c.x[29] = VP + 40;
    memcpy(mem + VP + 8, original, sizeof original);
    hos_wide_ratio = ratio;
    hos_wide_margin = margin;
    movie(&c);
    int failed = 0;
    for (int i = 0; i < 4; ++i) {
        float value;
        memcpy(&value, mem + VP + 8 + i * 4, sizeof value);
        if (!(value > expected[i] - 0.001f && value < expected[i] + 0.001f)) {
            fprintf(stderr, "FAIL: %s %s got %.5f, expected %.5f\n", name, edge[i], value, expected[i]);
            failed = 1;
        }
    }
    if (!failed) printf("ok: %s\n", name);
    return failed;
}

int main(void) {
    int failed = 0;
    failed |= check("32:9", 32.0f/9.0f, 0.25f, (float[]){90, 20, 250, 200});
    failed |= check("21:9", 21.0f/9.0f, 5.0f/42.0f, (float[]){48.09524f, 20, 291.90476f, 200});
    failed |= check("16:9", 0, 0, (float[]){10, 20, 330, 200});
    failed |= check("within 1% of 16:9", (16.0f/9.0f) * 0.995f, 0, (float[]){10, 20, 330, 200});
    failed |= check("16:10", 1.6f, 0, (float[]){10, 29, 330, 191});
    failed |= check("4:3", 4.0f/3.0f, 0, (float[]){10, 42.5f, 330, 177.5f});
    failed |= check("5:4", 1.25f, 0, (float[]){10, 46.71875f, 330, 173.28125f});
    return failed;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--movie-module", type=Path, default=ROOT / "nx2" / "oot_wide.py")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("oot_wide_fixture", args.movie_module)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "movie_shape.c"
        exe = source.with_suffix(".exe" if os.name == "nt" else "")
        source.write_text(FIXTURE.replace("@MOVIE@", module.MOVIE), encoding="utf-8")
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
