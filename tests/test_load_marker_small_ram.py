"""The load default against hookshot_load_start.txt on a small-RAM PC: gpu/vk/vk_programs.cpp's programs_load_decide, cut out
of the real source and run with stand-ins for the PC's RAM, the marker's folder and the log (no game or GPU).

A session whose loads found over 500 listed pipelines in no cache writes the marker (marker_write_lacked), which a settings
change is enough for. Followed, it takes every later start to start mode: every listed program before the title, 26 GB of
private memory on a 16 GB Arc A750 PC, where the window then stayed on "Starting the game", until the folder was prepared
again. Checked here: that marker is not followed at 20 GB of RAM or less and is followed above it or where the RAM is not
known; the waits' marker (marker_write: loads at create that wait seconds, an RX 580 with 16 GB) is followed on any RAM;
no marker is create; RX_VK_LOAD wins over all of them.

Run: python -I tests/test_load_marker_small_ram.py [--cxx g++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from srccut import block, between

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

# (the stand-ins: what programs_load_decide reads besides load_default.h. ram_total_mb is the PC's RAM)
PRELUDE = r"""
#include "load_default.h"
#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <string>

static std::string g_marker;
static uint32_t g_ram_mb;
static std::string g_log;
std::string load_fallback_path() { return g_marker; }
uint32_t ram_total_mb() { return g_ram_mb; }
bool env_on(const char* name) { const char* v = std::getenv(name); return v && *v && *v != '0'; }
void logf(const char* fmt, ...) {
    char line[512];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(line, sizeof line, fmt, ap);
    va_end(ap);
    std::fprintf(stderr, "%s\n", line);
    g_log += line;
    g_log += '\n';
}
std::atomic<int> load_mode{-1};
std::atomic<bool> struck_last_session{false};
bool precompile_wanted() { return true; }
bool programs_load_at_create() { return true; }
struct { std::atomic<long long> load_pipes_cold{0}, load_computes_cold{0}; } census;
"""

MAIN = r"""
#define CHECK(c, why) do { if (!(c)) { std::fprintf(stderr, "FAIL: %s\n", why); std::exit(1); } } while (0)
static bool start_with(const char* marker, uint32_t ram_mb, const char* env) {
    std::remove(g_marker.c_str());
    if (marker && !std::strcmp(marker, "lacked")) load_default::marker_write_lacked(g_marker, 502);
    if (marker && !std::strcmp(marker, "waits")) load_default::marker_write(g_marker, 1300, 2600);
    g_ram_mb = ram_mb;
    g_log.clear();
    if (env) setenv_portable("RX_VK_LOAD", env); else unsetenv_portable("RX_VK_LOAD");
    programs_load_decide(true);
    return load_mode.load() == 1;   // (create)
}
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    g_marker = std::string(argv[1]) + "/hookshot_load_start.txt";
    unsetenv_portable("RX_VK_PROGRAM_CACHE_ZSTD");
    CHECK(start_with(nullptr, 16279, nullptr), "no marker: not create");
    // the bug: a settings change's marker on a 16 GB PC took every later start to start mode
    CHECK(start_with("lacked", 16279, nullptr),
          "a marker left by loads that found listed pipelines in no cache took a 16 GB PC's start to start mode");
    CHECK(g_log.find("not followed: 16279 MB of RAM") != std::string::npos, "the marker not followed, and not logged");
    CHECK(start_with("lacked", 8192, nullptr), "the same on 8 GB");
    CHECK(start_with("lacked", 20480, nullptr), "the same at the 20 GB line");
    // above the line, or with the RAM not known, it is followed as before
    CHECK(!start_with("lacked", 20481, nullptr), "the lacked marker not followed above 20 GB");
    CHECK(!start_with("lacked", 0, nullptr), "the lacked marker not followed where the RAM is not known");
    // the waits' marker: start on any RAM (the RX 580 that needs it had 16 GB)
    CHECK(!start_with("waits", 16384, nullptr), "the waits' marker not followed on 16 GB");
    CHECK(g_log.find("not followed") == std::string::npos, "the waits' marker followed, but logged as not followed");
    CHECK(!start_with("waits", 65536, nullptr), "the waits' marker not followed on 64 GB");
    // the switch wins over both
    CHECK(!start_with("lacked", 16279, "start"), "RX_VK_LOAD=start lost to the RAM rule");
    CHECK(g_log.find("not followed") == std::string::npos, "RX_VK_LOAD=start, yet the marker logged as not followed");
    CHECK(start_with("waits", 16384, "create"), "RX_VK_LOAD=create lost to the waits' marker");
    // Both writers use the real file: waits must win regardless of their order.
    std::remove(g_marker.c_str());
    census.load_pipes_cold = 501;
    programs_frames_note();
    CHECK(load_default::marker_kind(g_marker) == load_default::Marker::kLacked, "lacked marker not written");
    load_wait_note(3000LL * 1000000LL);
    CHECK(load_default::marker_kind(g_marker) == load_default::Marker::kWaits, "waits did not replace lacked");
    CHECK(load_default::marker_counts(load_default::marker_kind(g_marker), 16384), "waits not followed on 16 GB");
    std::remove(g_marker.c_str());
    wait_marked = false; lacked_marked = false; wait_long_ns = 0; wait_worst_ns = 0;
    load_wait_note(3000LL * 1000000LL);
    programs_frames_note();
    CHECK(load_default::marker_kind(g_marker) == load_default::Marker::kWaits, "lacked replaced waits");
    std::remove(g_marker.c_str());
    std::printf("load marker on small RAM: ok\n");
    return 0;
}
"""

PORTABLE_ENV = r"""
#include <cstring>
#ifdef _WIN32
static void setenv_portable(const char* k, const char* v) { _putenv_s(k, v); }
static void unsetenv_portable(const char* k) { _putenv_s(k, ""); }
#else
static void setenv_portable(const char* k, const char* v) { setenv(k, v, 1); }
static void unsetenv_portable(const char* k) { unsetenv(k); }
#endif
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    progs = (ROOT / "gpu/vk/vk_programs.cpp").read_text(encoding="utf-8")
    decide = block(progs, "void programs_load_decide(bool native_mesh) {")
    state = between(progs, "std::atomic<int64_t> wait_worst_ns", "void load_wait_note(int64_t ns) {")
    wait = block(progs, "void load_wait_note(int64_t ns) {")
    # (the lacked marker's log line says what the next start does on this PC's RAM, not start mode on every PC)
    note = block(progs, "void programs_frames_note() {")
    if "marker_counts(load_default::Marker::kLacked, ram_total_mb())" not in note:
        raise SystemExit("programs_frames_note tells every PC its next start loads every listed program before the title")
    with tempfile.TemporaryDirectory(prefix="load-marker-ram-") as tmp:
        src = Path(tmp) / "decide.cpp"
        src.write_text(PRELUDE + PORTABLE_ENV + decide + "\n" + state + wait + "\n" + note + "\n" + MAIN, encoding="utf-8")
        exe = Path(tmp) / "decide"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-D_CRT_SECURE_NO_WARNINGS", "-I", str(ROOT / "gpu/vk"), str(src), "-o", str(exe)], check=True)
        subprocess.run([str(exe), tmp], check=True, timeout=60)


if __name__ == "__main__":
    main()
