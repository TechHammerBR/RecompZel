"""Above 60 fps the cap drops to 60 while a game menu is in front (the ocarina's song pick crashed uncapped)."""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    vi = (ROOT / "host/nn_vi.c").read_text(encoding="utf-8")
    menu = (ROOT / "host/oot_menu.c").read_text(encoding="utf-8")
    if "static int fps_max(void) { return fps_effective(hos_now_ns()); }" not in vi:
        raise SystemExit("fps_max (every pacing, limiter and step site) is not the menu-aware rate")
    if "return held ? 60 : fps_cap();" not in block(vi, "static int fps_effective("):
        raise SystemExit("fps_effective does not hold 60 while a menu is in front")
    tick = block(menu, "void hos_oot_menu_tick(")
    if "__atomic_store_n(&hos_menu_shown_ns, now" not in tick or "if (front || pause_runs)" not in tick:
        raise SystemExit("the menu tick does not stamp hos_menu_shown_ns")
    fixture = "#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
    fixture += "#define CHECK(x) do { if (!(x)) { fprintf(stderr,\"FAIL:%d %s\\n\",__LINE__,#x); exit(1); } } while(0)\n"
    fixture += block(vi, "static int menu_hold(")
    fixture += r'''
int main(void) {
    const int64_t ms = 1000000;
    CHECK(menu_hold(1000 * ms, 990 * ms, 1000, 1));    /* menu stamped 10 ms ago, uncapped: held at 60 */
    CHECK(menu_hold(1000 * ms, 900 * ms, 144, 1));     /* 100 ms ago, cap 144: still held */
    CHECK(!menu_hold(1000 * ms, 849 * ms, 1000, 1));   /* over 150 ms: the cap again */
    CHECK(!menu_hold(1000 * ms, 0, 1000, 1));          /* never a menu */
    CHECK(!menu_hold(1000 * ms, 990 * ms, 60, 1));     /* cap 60: nothing to do */
    CHECK(!menu_hold(1000 * ms, 990 * ms, 1000, 0));   /* HOS_MENU_FPS60=0 */
    CHECK(!menu_hold(1000 * ms, 1010 * ms, 1000, 1) || 1); /* a stamp from another thread just after: no crash */
    return 0;
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.c"
        exe = Path(tmp) / "t"
        src.write_text(fixture)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Werror", "-o", str(exe), str(src)], check=True)
        subprocess.run([str(exe)], check=True)
    print("menu fps60: ok")


if __name__ == "__main__":
    main()
