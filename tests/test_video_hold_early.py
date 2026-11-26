"""A movie's picture is not handed out ahead of its clock: the one before is shown again (host/nn_video.c, issue 1964).

The game takes a movie's next picture when its own count of the movie's 60ths says so (hos_movie_frames, host/nn_vi.c).
While a movie plays, Hookshot paces at 240 fps, and the count then follows the frames' time, not the clock: at ~226 fps
on an RTX 3080 the opening's picture ran ahead of its clock, 0.2 s after 6 s and 0.73 s by its end, while its sound kept
the clock, so the sound came late. dec_acquire already skips pictures that are late (tests/test_video_catchup.py); a
picture more than 25 ms early is now held back, and the buffer handed out shows the last picture again. Not the first
picture of a movie, not its last, and not into a pool the game reads from memory (no copy is made there).
HOS_VIDEO_NO_HOLD=1 hands every picture out when asked, as before.

python -I -B tests/test_video_hold_early.py [--cxx clang++] [--source host/nn_video.c]
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_video_catchup as catchup  # noqa: E402  (its harness: the stand-ins dec_acquire needs)

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]

# (two pools, one per buffer, both read through the API as OoT's are; pool 4 is one the game reads from memory)
HOST_OF_OLD = """static void *host_of(uint64_t obj, uint32_t magic) {
    if (magic == DEC_MAGIC) return obj == 1 ? &dec : NULL;
    return magic == POOL_MAGIC && obj == 2 ? &pool : NULL;
}"""
HOST_OF_NEW = """static Pool pool_b, pool_mem;
static void *host_of(uint64_t obj, uint32_t magic) {
    if (magic == DEC_MAGIC) return obj == 1 ? &dec : NULL;
    if (magic != POOL_MAGIC) return NULL;
    return obj == 2 ? &pool : obj == 3 ? &pool_b : obj == 4 ? &pool_mem : NULL;
}"""

MAIN = r"""
static int bad;
static void check(int ok, const char *what) { if (!ok) { printf("FAIL: %s\n", what); bad = 1; } }
static void make_pool(Pool *o, int by_api) {
    memset(o, 0, sizeof *o);
    o->w = o->h = 4, o->count = 1, o->read_by_api = by_api;
    o->nv12 = (uint8_t *)calloc(1, 4 * 4 * 3 / 2);
}
static void queue_picture(int at, int ms, int last, int fill) {
    Picture *p = &dec.queue[at];
    p->w = p->h = 4, p->pts = (int64_t)ms * 1000000, p->last = last;
    p->nv12 = (uint8_t *)calloc(1, 4 * 4 * 3 / 2);
    memset(p->nv12, fill, 4 * 4 * 3 / 2);
}
static uint32_t index_out;
static uint64_t acquire(void);
/* a movie by its clock: at 90 ms the picture at 83 ms (all 0xAA) is handed out into buffer 0 (pool 2) and stays shown;
   then at 100 ms the next, decoded at `next` ms (all 0x55), is asked for; buffer 1 (pool 3, or 4) is the free one */
static void setup(int next_ms, int last, uint64_t free_pool) {
    for (int i = 0; i < MAX_QUEUE; i++) picture_free(&dec.queue[i]);
    memset(&dec, 0, sizeof dec);
    make_pool(&pool, 1), make_pool(&pool_b, 1), make_pool(&pool_mem, 0);
    dec.slots[0] = 2, dec.slots[1] = free_pool;
    dec.clock_set = 1, dec.clock_ns = 0, dec.clock_pts = 0;
    queue_picture(0, 83, 0, 0xAA), queue_picture(1, next_ms, last, 0x55);
    dec.qn = 2, dec.decoded = 7, dec.first_pts = 0, dec.end_pts = 6 * 16666667, dec.recent_ns = 1000000;
    clock_ns = 90000000;
    acquire();
    if (index_out != 0 || dec.last_pts != 83000000 || pool.nv12[0] != 0xAA) printf("FAIL: the setup's first picture\n"), exit(1);
    clock_ns = 100000000;
    sleeps = decode_calls = 0;
}
static uint64_t acquire(void) {
    static uint64_t sync;
    Ctx c;
    memset(&c, 0, sizeof c);
    c.x[0] = (uint64_t)(uintptr_t)&index_out, c.x[1] = (uint64_t)(uintptr_t)&sync, c.x[2] = 1;
    dec_acquire(&c);
    return c.x[0];
}
int main(int argc, char **argv) {
    const int off = argc > 1 && !strcmp(argv[1], "off");   /* (HOS_VIDEO_NO_HOLD=1) */
    uint64_t r;

    setup(200, 0, 3);   /* 100 ms ahead of the clock */
    r = acquire();
    if (off) {
        check(r == 0 && index_out == 1 && dec.slot_pts[1] == 200000000 && dec.qn == 0,
              "HOS_VIDEO_NO_HOLD=1: the early picture is handed out when asked");
    } else {
        check(r == 0 && index_out == 1, "the acquire still hands out a free buffer");
        check(dec.slot_pts[1] == 83000000 && dec.last_pts == 83000000,
              "a picture 100 ms ahead of the movie's clock is held back: the buffer has the last picture's time");
        check(pool_b.nv12[0] == 0xAA && pool_b.nv12[4 * 4 * 3 / 2 - 1] == 0xAA,
              "the buffer handed out shows the last picture again, not what it held before");
        check(dec.qn == 1 && dec.queue[dec.qhead].pts == 200000000, "the early picture waits in the queue for its time");
        dec.busy[0] = 0;
        clock_ns = 130000000;
        acquire();
        dec.busy[1] = 0;
        clock_ns = 160000000;
        acquire();
        /* its time comes: handed out */
        dec.busy[0] = 0;
        clock_ns = 190000000;
        r = acquire();
        check(r == 0 && dec.last_pts == 200000000 && dec.qn == 0, "the held picture is handed out once it is due");
        check(dec.out_ns == 190000000 && dec.gap_worst_ns == 30000000 && dec.gaps[0][1] == 3,
              "held buffers count as deliveries and reset the time between pictures");
    }

    setup(120, 0, 3);   /* 20 ms ahead: within a frame and a half, as the late side's 25 ms */
    r = acquire();
    check(r == 0 && index_out == 1 && dec.slot_pts[1] == 120000000, "a picture under 25 ms ahead is handed out");

    setup(200, 1, 3);   /* the movie's last picture */
    r = acquire();
    check(r == 0 && dec.slot_pts[1] == 200000000 && dec.slot_last[1] == 1, "the last picture is handed out, early or not");

    setup(200, 0, 4);   /* the free buffer's pool is read from memory */
    r = acquire();
    check(r == 0 && index_out == 1 && dec.slot_pts[1] == 200000000, "a pool read from memory gets the picture as before");

    for (int i = 0; i < MAX_QUEUE; i++) picture_free(&dec.queue[i]);   /* a movie's first picture, early by its clock */
    memset(&dec, 0, sizeof dec);
    make_pool(&pool, 1), make_pool(&pool_b, 1);
    dec.slots[0] = 2, dec.slots[1] = 3;
    dec.clock_set = 1, dec.clock_ns = 0, dec.clock_pts = 0;
    queue_picture(0, 200, 0, 0x55);
    dec.qn = 1, dec.decoded = 1;
    clock_ns = 100000000;
    r = acquire();
    check(r == 0 && dec.last_pts == 200000000, "a movie's first picture is handed out at once");

    if (!bad) puts("ok");
    return bad;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--source", type=Path, default=ROOT / "host/nn_video.c")
    args = parser.parse_args()
    src = args.source.read_text(encoding="utf-8")
    harness = catchup.HARNESS[:catchup.HARNESS.index("static int bad;")]
    if HOST_OF_OLD not in harness:
        raise SystemExit("FAIL: tests/test_video_catchup.py's host_of stand-in changed")
    harness = harness.replace(HOST_OF_OLD, HOST_OF_NEW)
    defines = "\n".join(l for l in src.splitlines() if l.startswith(("#define RESULT_NO_OUTPUT", "#define POOL_MAGIC",
                        "#define DEC_MAGIC", "#define MAX_SLOTS", "#define MAX_QUEUE", "#define SYNC_IDLE_TAG",
                        "#define SYNC_IDLE_MASK")))
    types = "\n".join((defines,
                       catchup.through(src, "typedef struct {\n    int w, h, format, count;", "} Pool;"),
                       catchup.through(src, "typedef struct { uint8_t *rgba, *nv12;", "} Picture;"),
                       catchup.through(src, "typedef struct Pending {", "} Pending;"),
                       catchup.through(src, "typedef void (*mf_av1_picture_fn)", "int64_t pts);"),
                       catchup.through(src, "typedef struct {\n    const char *name;", "} Av1Decoder;"),
                       catchup.through(src, "typedef struct {\n    AVCodecContext *ctx;", "} Dec;"),
                       "static volatile LONG64 submissions;"))
    fixture = (harness.replace("@TYPES@", types).replace("@ACQUIRE@", catchup.block(src, "static void dec_acquire(Ctx *c) {"))
               + MAIN)
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="video-hold-") as temporary:
        folder = Path(temporary)
        (folder / "fixture.cpp").write_text(fixture, encoding="utf-8")
        exe = folder / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([compiler, "-std=c++17", "-include", catchup.ENV_ON_H, "-O1", "-w",
                        str(folder / "fixture.cpp"), "-o", str(exe)], check=True, timeout=120)
        failed = False
        for mode, value in (("on", None), ("off", "1")):
            env = os.environ.copy()
            for name in ("HOS_VIDEO_NO_CATCHUP", "HOS_VIDEO_LOG", "HOS_VIDEO_NO_HOLD"):
                env.pop(name, None)
            if value:
                env["HOS_VIDEO_NO_HOLD"] = value
            result = subprocess.run([str(exe)] + ([mode] if mode == "off" else []), capture_output=True, text=True,
                                    timeout=30, env=env)
            print("%s: %s" % ("HOS_VIDEO_NO_HOLD=1" if value else "default", result.stdout.strip()))
            if result.stderr:
                print(result.stderr, end="")
            failed |= bool(result.returncode or "ok" not in result.stdout)
        if failed:
            raise SystemExit("a movie's picture is handed out ahead of its clock, or held where it should not be")


if __name__ == "__main__":
    main()
