"""A trigger counts as pressed only once it has read let go for a second since its pad was opened, and the log says
which pad's trigger reads held, and how (host/pad_sdl.c, trigger_pull, #2327).

A device whose trigger axes read held for good (a ShanWan USB receiver, 2563:0575) held ZL and ZR from every pad, kept
the Controls page from ever listening for a binding (it waits for every input to be let go) and, once the Insert menu
closed, kept the player's own triggers from the game (host/nn_hid.c: an input down at the close waits to be let go). A
single let-go reading was not enough to tell a real trigger: with that receiver plugged in, the rule "seen let go once"
still let its triggers through. The sticks have the "seen at rest" rule (tests/test_stick_rest.py).

trigger_pull and the poll's lines that turn its readings into HOS_PAD_LTRIGGER and HOS_PAD_RTRIGGER are cut out of
host/pad_sdl.c and compiled over a stand-in pad, polled every 4 ms as the pad thread does, then checked:

- a trigger read as held from the start (16384, 32767) never presses, however long it stays; nor one that reads let go
  for a moment as its pad opens, or now and then (4 ms every 2 s, half a second once), and is held otherwise;
- a trigger at rest when the pad opens presses from its first pull after a second, and lets go below the threshold;
  one counted stays counted through a long hold;
- a pull in the first second, or one held as the pad opens, presses once the trigger has been let go for a second;
- each trigger is judged on its own, and the sticks' rest bits are left alone;
- the threshold is unchanged: 8000 is let go, 8001 pressed;
- the log: a trigger not counting 3 s after its pad opened is said once, with the pad's name and the reading (not
  before 3 s, not again); its counting later is said once; a counted trigger held 30 s without a break is said once;
  a pad at rest and short pulls say nothing; at debug, each trigger's first reading and its changes between let go and
  held, nine at most, with their time since the pad opened.

python -I -B tests/test_trigger_rest.py [--cc clang]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between  # noqa: E402

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
TOUCHPAD = "if (hos_sdl_pad_button(gc, BTN_TOUCHPAD)) b |= 1ULL << HOS_PAD_TOUCHPAD;"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    src = (ROOT / "host/pad_sdl.c").read_text(encoding="utf-8")
    axes = between(src, "enum { AX_LX", ";") + ";"
    # (trigger_pull, its constants first, up to the poll)
    pull = between(src, "#define TRIGGER_REST_NS", "/* one poll: controllers plugged in or gone")
    # (the poll's lines after the touchpad's, up to the sticks': the triggers' bits)
    triggers = between(src, TOUCHPAD, "const int inv_x = rx_option(16, 0);")[len(TOUCHPAD):]
    fixture = r'''#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
''' + axes + r'''
#define HOS_PAD_LTRIGGER 15
#define HOS_PAD_RTRIGGER 16
#define LT (1ULL << HOS_PAD_LTRIGGER)
#define RT (1ULL << HOS_PAD_RTRIGGER)
enum { HOS_LOG_ERROR, HOS_LOG_WARN, HOS_LOG_INFO, HOS_LOG_DEBUG, HOS_LOG_TRACE };
static struct {
    void *gc;
    unsigned rested;
    signed char held[4];
    int64_t opened_ns;
    int64_t trig_held_ns[2];
    int64_t trig_rest_ns[2];
    uint8_t trig_said, trig_changes[2];
} pads[1];
static int16_t axis[AX_RT + 1];
static int16_t hos_sdl_pad_axis(void *gc, int a) { (void)gc; return axis[a]; }
static const char *hos_sdl_pad_name(void *gc) { (void)gc; return "Retro Controller"; }
static char said[16][256], dbg[32][256];   /* (what hos_log, and hos_log_at at debug, were given, in order) */
static int said_n, dbg_n;
static void hos_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    if (said_n < 16) vsnprintf(said[said_n], sizeof said[0], fmt, ap);
    said_n++;
    va_end(ap);
}
static void hos_log_at(int level, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    if (level == HOS_LOG_DEBUG && dbg_n < 32) vsnprintf(dbg[dbg_n], sizeof dbg[0], fmt, ap);
    dbg_n += level == HOS_LOG_DEBUG;
    va_end(ap);
}
''' + pull + r'''
static int64_t clock_ns = 1000000000LL;
/* one poll of pad 0 with its triggers at lt and rt, 4 ms after the last: the trigger bits it gives */
static uint64_t poll(int lt, int rt) {
    const int i = 0;
    void *gc = NULL;
    uint64_t b = 0;
    const int64_t now = clock_ns;
    clock_ns += 4000000;
    axis[AX_LT] = (int16_t)lt, axis[AX_RT] = (int16_t)rt;
''' + triggers + r'''
    (void)i, (void)gc, (void)now;
    return b;
}
/* polls for ms milliseconds at lt and rt: the last poll's bits */
static uint64_t hold(int lt, int rt, int ms) {
    uint64_t b = 0;
    for (int n = 0; n < ms / 4; n++) b = poll(lt, rt);
    return b;
}
/* (pad_sdl.c's open: rested, the trigger times and what was said cleared, opened now) */
static void open_pad(void) {
    memset(pads, 0, sizeof pads);
    pads[0].opened_ns = clock_ns;
    said_n = dbg_n = 0;
}
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); return 1; } } while (0)
#define SAID(k, text) (said_n > (k) && strstr(said[k], text) != NULL)
#define DBG(k, text) (dbg_n > (k) && strstr(dbg[k], text) != NULL)
int main(void) {
    /* a device whose triggers read held from the start never presses them */
    open_pad();
    CHECK(hold(16384, 16384, 10000) == 0);
    open_pad();
    CHECK(hold(32767, 32767, 10000) == 0);
    /* #2327's receiver: let go for a moment as it opens, then held */
    open_pad();
    CHECK(poll(0, 0) == 0);
    CHECK(hold(16384, 16384, 10000) == 0);
    /* the reporter's log (pr-2337-e22bbdb5): 0 for its first 42 ms, then 16447 for the rest of the run */
    open_pad();
    CHECK(hold(0, 0, 40) == 0);
    CHECK(hold(16447, 16447, 60000) == 0);
    /* let go now and then: 4 ms every 2 s, then half a second once */
    open_pad();
    for (int k = 0; k < 10; k++) {
        CHECK(poll(0, 0) == 0);
        CHECK(hold(16384, 16384, 2000) == 0);
    }
    CHECK(hold(0, 0, 500) == 0);
    CHECK(hold(16384, 16384, 2000) == 0);
    /* a real trigger at rest as its pad opens: it counts after a second, presses and lets go */
    open_pad();
    CHECK(hold(0, 0, 1100) == 0);
    CHECK(poll(30000, 0) == LT);
    CHECK(poll(0, 32767) == RT);
    CHECK(poll(32767, 32767) == (LT | RT));
    CHECK(poll(0, 0) == 0);
    /* once it counts, a long hold (Z-targeting) stays pressed */
    CHECK(hold(32767, 0, 60000) == LT);
    /* a pull in the pad's first second waits for a second let go */
    open_pad();
    CHECK(hold(0, 0, 500) == 0);
    CHECK(poll(30000, 0) == 0);
    CHECK(hold(0, 0, 1100) == 0);
    CHECK(poll(30000, 0) == LT);
    /* the threshold: 8000 is let go, 8001 pressed */
    open_pad();
    CHECK(hold(8000, 8000, 1100) == 0);
    CHECK(poll(8000, 8001) == RT);
    CHECK(poll(8001, 8000) == LT);
    /* a trigger held as the pad opens presses once it has been let go for a second */
    open_pad();
    CHECK(hold(32767, 0, 2000) == 0);
    CHECK(hold(0, 0, 1100) == 0);
    CHECK(poll(32767, 0) == LT);
    /* each trigger on its own: a left one held for good leaves the right one free */
    open_pad();
    CHECK(hold(16384, 0, 1100) == 0);
    CHECK(poll(16384, 25000) == RT);
    CHECK(hold(16384, 0, 10000) == 0);
    /* the sticks' rest bits (0 to 3, tests/test_stick_rest.py) are not the triggers' */
    CHECK((pads[0].rested & 0xFu) == 0);
    /* a pad opened again is judged again */
    open_pad();
    CHECK(hold(16384, 16384, 2000) == 0);

    /* the log: both triggers not counting are said once each, at 3 s, with the pad's name and the reading */
    open_pad();
    CHECK(poll(0, 0) == 0);   /* (the receiver: let go for a moment as it opens) */
    CHECK(hold(16384, 16384, 2900) == 0);
    CHECK(said_n == 0);
    CHECK(hold(16384, 16384, 200) == 0);
    CHECK(said_n == 2);
    CHECK(SAID(0, "\"Retro Controller\": its left trigger reads 16384 of 32767 and has not read let go for a second"));
    CHECK(SAID(1, "its right trigger reads 16384 of 32767"));
    CHECK(hold(16384, 16384, 60000) == 0);   /* (not again; not counted, so no 30 s line either) */
    CHECK(said_n == 2);
    /* the left let go for a second later: said once, and it presses from then on */
    CHECK(hold(0, 16384, 996) == 0);
    CHECK(said_n == 2);
    CHECK(hold(0, 16384, 100) == 0);
    CHECK(said_n == 3 && SAID(2, "its left trigger has read let go for a second (0 of 32767): it counts from now"));
    CHECK(poll(30000, 16384) == LT);
    CHECK(hold(0, 16384, 1000) == 0);
    CHECK(said_n == 3);
    /* a pad at rest, and pulls shorter than 30 s, say nothing */
    open_pad();
    CHECK(hold(0, 0, 5000) == 0);
    CHECK(hold(30000, 0, 10000) == LT);
    CHECK(hold(0, 20000, 29000) == RT);
    CHECK(hold(0, 0, 1000) == 0);
    CHECK(said_n == 0);
    /* a counted trigger held 30 s without a break: said once, however often it happens again */
    CHECK(hold(0, 25000, 30100) == RT);
    CHECK(said_n == 1 && SAID(0, "its right trigger has read held (25000 of 32767) for 30 s without a break"));
    CHECK(hold(0, 25000, 60000) == RT);
    CHECK(hold(0, 0, 100) == 0);
    CHECK(hold(0, 25000, 31000) == RT);
    CHECK(said_n == 1);
    /* debug: each trigger's first reading, then its changes between let go and held, nine lines at most */
    open_pad();
    CHECK(poll(0, 0) == 0);
    CHECK(dbg_n == 2);
    CHECK(DBG(0, "\"Retro Controller\": its left trigger reads 0 of 32767 (let go), 0.000 s after it was opened"));
    CHECK(DBG(1, "its right trigger reads 0 of 32767 (let go), 0.000 s"));
    CHECK(poll(16384, 0) == 0);
    CHECK(dbg_n == 3 && DBG(2, "its left trigger reads 16384 of 32767 (held), 0.004 s after it was opened"));
    CHECK(hold(16384, 0, 1000) == 0);
    CHECK(dbg_n == 3);   /* (no change, nothing more) */
    for (int k = 0; k < 20; k++) {
        poll(0, 0);
        poll(16384, 0);
    }
    CHECK(dbg_n == 10);   /* (the left's nine and the right's first) */
    printf("PASS: triggers press once let go for a second; held ones, and ones let go only for a moment, never do; "
           "the log says which, once\n");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="trigger-rest-") as tmp:
        c = Path(tmp) / "fixture.c"
        exe = Path(tmp) / "fixture.exe"
        c.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(c), "-o", str(exe)],
                       check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        print(r.stdout, end="")
        if r.returncode:
            print(r.stderr, end="")
            raise SystemExit("test_trigger_rest: failed")


if __name__ == "__main__":
    main()
