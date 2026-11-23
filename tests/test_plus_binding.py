"""Plus is not on the key a pad's A becomes, and a pad's A is the game's B, never its pause (#1992).

A game launched outside Steam keeps Steam Input's Desktop layout over its window: the pad's A arrives as Enter, B and
Menu as Escape and View as Tab, on top of the pad SDL reads. host/nn_hid.c binds the keyboard's Enter to Plus (the
game's pause) until options_version 8, so every A press opened the pause menu. The pad itself maps by position (an Xbox
pad's bottom button is the Switch's B) and its Start is Plus; nothing in host/pad_sdl.c or bound_pad_buttons can make A
Plus.

host/nn_hid.c's binding table, binds_load and bound_down are compiled with fakes for the options file and the key states
(as tests/test_bound_keys.py compiles them), once per file: the reporter's hookshot_options.ini, a file that chose
Enter for Plus, and no file.

python -I -B tests/test_plus_binding.py [--cc gcc]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    while text[end] in ";\n":
        end += 1
        if text[end - 1] == "\n":
            break
    return text[start:end]


def between(text, first, last):
    """from the line that holds first to the end of the block or statement that starts at last"""
    start = text.rindex("\n", 0, text.index(first)) + 1
    return text[start:text.index(last)] + block(text, last)


PRELUDE = r"""
#define _CRT_SECURE_NO_WARNINGS
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "vk_api.h"
#include "../../host/hold_toggle.h"
typedef long LONG;
typedef unsigned long DWORD;
typedef int SRWLOCK;
#define SRWLOCK_INIT 0
static void AcquireSRWLockExclusive(SRWLOCK *p) { (void)p; }
static void ReleaseSRWLockExclusive(SRWLOCK *p) { (void)p; }
static void AcquireSRWLockShared(SRWLOCK *p) { (void)p; }
static void ReleaseSRWLockShared(SRWLOCK *p) { (void)p; }
#define VK_LBUTTON 0x01
#define VK_RBUTTON 0x02
#define VK_MBUTTON 0x04
#define VK_XBUTTON1 0x05
#define VK_XBUTTON2 0x06
#define VK_TAB 0x09
#define VK_RETURN 0x0D
#define VK_SHIFT 0x10
#define VK_CONTROL 0x11
#define VK_MENU 0x12
#define VK_CAPITAL 0x14
#define VK_SPACE 0x20
#define VK_LEFT 0x25
#define VK_UP 0x26
#define VK_RIGHT 0x27
#define VK_DOWN 0x28
static LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG o = *p; *p = v; return o; }
static LONG InterlockedCompareExchange(volatile LONG *p, LONG v, LONG c) { LONG o = *p; if (o == c) *p = v; return o; }
static void Sleep(int ms) { (void)ms; }
static void hos_log(const char *f, ...) { (void)f; }
static const char *ini_dir;
static const char *hos_options_file(void) {   /* (host/options_path.c: here, beside the exe) */
    static char p[600];
    snprintf(p, sizeof p, "%s/hookshot_options.ini", ini_dir);
    return p;
}
static int held[256];
static uint64_t pad_raw_game;
static int key(int vk) { return held[vk & 255]; }
static int kpos(int us) { return key(us); }   /* (nn_hid.c's keys by their place: a US layout here) */
"""

MAIN = r"""
static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static void release(void) { memset(held, 0, sizeof held); }
int main(int argc, char **argv) {
    ini_dir = argv[1];
    const int enter_chosen = argc > 2 && !strcmp(argv[2], "chosen");
    binds_load();
    /* the reporter's pad: the bottom face button is the Switch's B, Start is Plus, nothing else is Plus */
    CHECK(hos_binding(HOS_BIND_PAD, HOS_SW_A, 0) == HOS_PAD_EAST);
    CHECK(hos_binding(HOS_BIND_PAD, HOS_SW_B, 0) == HOS_PAD_SOUTH);
    CHECK(hos_binding(HOS_BIND_PAD, HOS_SW_PLUS, 0) == HOS_PAD_START);
    CHECK(bound_pad_buttons(1ULL << HOS_PAD_SOUTH) == (1ULL << HOS_SW_B));
    CHECK(bound_pad_buttons(1ULL << HOS_PAD_START) == (1ULL << HOS_SW_PLUS));
    CHECK(bound_pad_buttons(1ULL << HOS_PAD_BACK) == (1ULL << HOS_SW_MINUS));
    /* Enter is what Steam Input's Desktop layout sends for the pad's A: it presses Plus only where the player chose it */
    release(), held[VK_RETURN] = 1;
    CHECK(bound_down(HOS_SW_PLUS, 0) == enter_chosen);
    CHECK((hos_binding(HOS_BIND_KEY, HOS_SW_PLUS, 0) == VK_RETURN ||
           hos_binding(HOS_BIND_KEY, HOS_SW_PLUS, 1) == VK_RETURN) == enter_chosen);
    /* Tab, the other key the Desktop layout sends for a pad's View, still presses Plus: the game keeps a pause key */
    release(), held[VK_TAB] = 1;
    CHECK(bound_down(HOS_SW_PLUS, 0));
    /* and Enter is not another control's key either, so nothing else fires from it */
    release(), held[VK_RETURN] = 1;
    for (int i = 0; i < HOS_SW_N; i++)
        if (i != HOS_SW_PLUS) CHECK(!bound_down(i, 0));
    if (!fails) printf("PASS: %s\n", enter_chosen ? "a chosen Enter is kept" : "Plus is not on the pad A's key");
    return fails != 0;
}
"""

# the reporter's file (from #1992), the pad and key lines that matter
REPORTER = "options_version=6\npad_a=1\npad_b=0\npad_x=3\npad_y=2\npad_plus=6\nkey_a=69,0\nkey_b=16,0\nkey_plus=9,13\n"
# a player who put Plus on Enter first in an older build: not the default pair, so it is theirs
CHOSEN = "options_version=6\npad_a=1\npad_b=0\npad_plus=6\nkey_plus=13,9\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    cc = [a.cc]
    if not cc or not cc[0]:
        raise SystemExit("missing C compiler (set CC or install gcc or clang)")
    hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
    code = [block(hid, "static int kmap_down("),
            between(hid, "static const char *const bind_names[HOS_KEY_N]", "void hos_bind(int set, int button, int slot, int code) {"),
            between(hid, "static int mouse_vk_slot(", "static int bound_down("),
            block(hid, "static uint64_t bound_pad_buttons(")]
    source = PRELUDE + "\n".join(code) + MAIN
    with tempfile.TemporaryDirectory(prefix="plus-binding-") as tmp:
        tmp = Path(tmp)
        c = tmp / "fixture.c"
        exe = tmp / "fixture"
        c.write_text(source, encoding="utf-8")
        build = subprocess.run(cc + ["-std=gnu11", "-Wall", "-Wno-unused-function", "-I", str(ROOT / "gpu" / "vk"),
                                "-I", str(ROOT / "gpu"), str(c), "-o", str(exe)], text=True, capture_output=True)
        if build.returncode:
            raise SystemExit("the fixture does not compile:\n" + build.stderr)
        for name, text, case in (("reporter", REPORTER, ""), ("chosen", CHOSEN, "chosen")):
            folder = tmp / name
            folder.mkdir()
            (folder / "hookshot_options.ini").write_text(text, encoding="utf-8")
            subprocess.run([str(exe), str(folder)] + ([case] if case else []), check=True)
        # a fresh install, no file: the defaults must not have Enter on Plus either
        empty = tmp / "fresh"
        empty.mkdir()
        subprocess.run([str(exe), str(empty)], check=True)


if __name__ == "__main__":
    main()
