"""Mesa's submit thread on by default with an AMD card: the process start (host/hos_main.c main(), after hookshot_env.txt and
before any thread) sets MESA_VK_ENABLE_SUBMIT_THREAD=1 for the whole process when /sys/class/drm has an amdgpu card, the user
has not set it, and there are 12 or more hardware threads or RX_VK_RADV_SUBMIT_THREAD=1 (=0: left alone). Compiles
host/hos_submit_thread.h's test (the decision table, the amdgpu probe on fake sysfs trees) and reads the source; no game or GPU.

    python -I -B tests/test_radv_submit_thread.py [--cxx g++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fails = []


def need(ok, what):
    if not ok:
        fails.append(what)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def body(src, head):
    """The function starting at `head`, to its closing brace at the start of a line"""
    i = src.find(head)
    if i < 0:
        fails.append("no " + head)
        return ""
    return src[i:src.find("\n}\n", i) + 3]


def check_source():
    host = read("host/hos_main.c")
    need('#include "hos_submit_thread.h"' in host, "hos_main.c includes hos_submit_thread.h")
    start = body(host, "static void submit_thread_at_start(void) {")
    need("hos_submit_thread_decide(hos_drm_has_amdgpu(\"/sys/class/drm\")" in start
         and 'getenv("RX_VK_RADV_SUBMIT_THREAD")' in start and "sysconf(_SC_NPROCESSORS_ONLN)" in start,
         "submit_thread_at_start: the amdgpu probe, the switch and the thread count decide")
    need('setenv("MESA_VK_ENABLE_SUBMIT_THREAD", "1", 1)' in start and "setenv(HOS_SUBMIT_THREAD_MARK" in start,
         "submit_thread_at_start: the variable and its mark set")
    # (the only setenv/unsetenv of Mesa's variable: in submit_thread_at_start, none anywhere else)
    rest = host.replace(start, "")
    need('"MESA_VK_ENABLE_SUBMIT_THREAD"' not in rest, "hos_main.c: Mesa's variable set nowhere but submit_thread_at_start")
    s = host.find("#ifdef __linux__\n#include \"hos_submit_thread.h\"")
    need(0 <= s < host.find("static void submit_thread_at_start") < host.find("#endif", s + 1),
         "hos_main.c: submit_thread_at_start is Linux only")
    # Linux main(): hookshot_env.txt read, then the decision, then SDL (the first thread) and the game's thread
    # (the last main in the file: the one SDL and the game's thread start in; the crash window's helper comes first in it)
    linux_main = body(host[host.rfind("int main(int argc, char **argv) {"):], "int main(int argc, char **argv) {")
    env = linux_main.find("load_hookshot_env();")
    decide = linux_main.find("submit_thread_at_start();")
    display = linux_main.find("hos_display_init()")
    discord = linux_main.find("hos_discord_start();")
    thread = linux_main.find("CreateThread(")
    need(min(env, decide, display, discord, thread) >= 0, "Linux main: load_hookshot_env, submit_thread_at_start, SDL, the game's thread")
    need(env < decide < display < discord < thread,
         "Linux main: the decision after hookshot_env.txt and before any thread (SDL, Discord, the game's)")
    game = body(host, "static int game_main(int argc, char **argv) {")
    need("hos_log(\"env: Mesa's submit thread %s\", submit_thread_note)" in game
         and game.find("hos_log(\"hookshot %s\"") < game.find("submit_thread_note"),
         "game_main: the decision logged after the log's first line")
    need("const char *hos_posix_submit_thread_note(void)" in host, "hos_main.c: the note exported (hos_posix_*) to the back end")

    main = read("gpu/vk/vk_main.cpp")
    need("radv_submit_thread" not in main, "vk_main.cpp: no radv_submit_thread.h any more")
    need("setenv(" not in main and "unsetenv(" not in main, "vk_main.cpp: no setenv/unsetenv (a thread-safety hazard there)")
    dev = body(main, "bool create_device() {")
    note = dev.find('dlsym(RTLD_DEFAULT, "hos_posix_submit_thread_note")')
    create = dev.find("vkCreateDevice(dev.physical, &ci, nullptr, &dev.device)")
    need(0 <= note < create, "create_device: the start's decision logged before vkCreateDevice")
    need("VK_DRIVER_ID_MESA_RADV" in dev[note:create], "create_device: says whether the picked device is RADV")
    need(dev.rfind("#ifndef _WIN32", 0, note) > dev.rfind("#endif", 0, note), "create_device: not on Windows")
    need(dev.count("vkCreateDevice(") == 1, "create_device: one vkCreateDevice")
    need(not (ROOT / "gpu/vk/radv_submit_thread.h").exists(), "gpu/vk/radv_submit_thread.h gone (the decision is the host's)")

    # (the menu's restart: the environment the process started with, which setenv does not change)
    relaunch = read("host/hos_relaunch.c")
    need('hos_relaunch_command("/proc/self/cmdline", "/proc/self/environ", &r)' in relaunch,
         "hos_relaunch.c: a restart takes /proc/self/environ (the start's environment, without the variable Hookshot set)")

    docs = read("docs/development.md")
    row = docs[docs.find("`RX_VK_RADV_SUBMIT_THREAD"):]
    row = row[:row.find("\n")]
    need(row != "", "docs/development.md: RX_VK_RADV_SUBMIT_THREAD in the table")
    for words in ("12", "`=1`", "`=0`", "amdgpu", "/sys/class/drm", "HOS_INPUT_SCRIPT=8:A,10:A,12:A,14:A"):
        need(words in row, "docs/development.md's row says: " + words)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    if sys.platform == "win32":
        print("radv_submit_thread: Linux only (the source checked, the test not compiled)")
        return 1 if fails else 0
    with tempfile.TemporaryDirectory(prefix="radv-submit-thread-") as tmp:
        exe = Path(tmp) / "radv-submit-thread"
        subprocess.run([args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "tests/test_radv_submit_thread.cpp"), "-o", str(exe)], check=True)
        tree = Path(tmp) / "sys"
        tree.mkdir()
        run = subprocess.run([str(exe), str(tree)], text=True, capture_output=True)
        need(run.returncode == 0, "hos_submit_thread.h: " + (run.stderr.strip() or f"exit {run.returncode}"))
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("test_radv_submit_thread: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
