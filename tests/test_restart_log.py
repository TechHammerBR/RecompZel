"""A restart on Linux (host/hos_relaunch.c, the Insert menu's Restart now and the bridge's relaunch) and the game's log.

A game started with no stderr of its own (from its icon, Steam, the launcher: /dev/null or the journal's socket) opens its
hookshot_log.txt as stderr (host/hos_main.c), after moving the run before's to hookshot_log.1.txt. The restart becomes the
game again by execve, which keeps fd 2: the new run found a regular file there, took it for a stderr it was given, and
neither moved the log nor named it for the crash window. Its lines went on after the first run's, and a crash in it showed
the window without the run's log (host/hos_crash_dialog.c looks for "run_id: <run>" in the log's first 8 KB).

This check cuts the Linux restart out of hos_relaunch.c, compiles it with stand-ins for execve and the log, and checks the
stderr the game started again gets: none again (not a regular file) when the game was given none, the one it was given
otherwise, and its own log back when the exec fails (where the restart says so). Also that the Linux main keeps what it was
given before anything opens the log. Linux only (execve, /proc/self).

python -I -B tests/test_restart_log.py [--cxx g++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
RUN_ALL_SKIP = {"windows": "the Linux restart (execve, /proc/self): Windows' is checked by tests/test_menu_restart.py"}

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* (stand-ins for host/posix/win32_posix.c's: stderr's handle, and its kind by the same rule) */
typedef void *HANDLE;
#define INVALID_HANDLE_VALUE ((HANDLE)(long)-1)
#define STD_ERROR_HANDLE ((unsigned)-12)
#define FILE_TYPE_UNKNOWN 0u
#define FILE_TYPE_DISK 1u
#define FILE_TYPE_CHAR 2u
#define FILE_TYPE_PIPE 3u
static int std_err_fd = STDERR_FILENO;
HANDLE GetStdHandle(unsigned which) { return which == STD_ERROR_HANDLE ? (HANDLE)&std_err_fd : INVALID_HANDLE_VALUE; }
unsigned GetFileType(HANDLE h) {
    struct stat st;
    if (fstat(*(int *)h, &st)) return FILE_TYPE_UNKNOWN;
    if (S_ISREG(st.st_mode)) return FILE_TYPE_DISK;
    if (S_ISFIFO(st.st_mode)) return FILE_TYPE_PIPE;
    if (S_ISCHR(st.st_mode)) return isatty(*(int *)h) ? FILE_TYPE_CHAR : FILE_TYPE_UNKNOWN;
    return FILE_TYPE_UNKNOWN;
}

static int out = -1;   /* (the check's own stderr, kept before fd 2 is played with) */
static char last_log[256];
void hos_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(last_log, sizeof last_log, fmt, ap);
    va_end(ap);
}
void hos_log_flush(void) {}

/* (the exec: what fd 2 is at that moment; then a failure, so the restart goes on to its last line) */
static int execs, exec_err_regular;
static ino_t exec_err_ino;
static int fake_execve(const char *path, char *const argv[], char *const envp[]) {
    (void)path, (void)argv, (void)envp;
    struct stat st;
    execs++;
    exec_err_regular = fstat(STDERR_FILENO, &st) == 0 && S_ISREG(st.st_mode);
    exec_err_ino = exec_err_regular ? st.st_ino : 0;
    errno = ENOENT;
    return -1;
}
static int fake_execvp(const char *file, char *const argv[]) {
    (void)file, (void)argv;
    errno = ENOENT;
    return -1;
}
#define execve fake_execve
#define execvp fake_execvp

/* (main's has none: the check then runs as main's game did, with nothing kept) */
void hos_relaunch_keep_env(void) __attribute__((weak));
static void (*volatile keep_env)(void) = hos_relaunch_keep_env;

#include "hos_relaunch.h"
@CUT@

static void fail(const char *why) {
    dprintf(out, "FAIL: %s\n", why);
    exit(1);
}
static void on_fd2(const char *path, int flags) {
    const int fd = open(path, flags, 0644);
    if (fd < 0 || dup2(fd, STDERR_FILENO) < 0) fail("cannot set up fd 2");
    close(fd);
}
static ino_t ino_of(const char *path) {
    struct stat st;
    return stat(path, &st) == 0 ? st.st_ino : 0;
}

int main(int argc, char **argv) {
    (void)argc;
    out = dup(STDERR_FILENO);
    char log[1024], given[1024];
    snprintf(log, sizeof log, "%s/hookshot_log.txt", argv[1]);
    snprintf(given, sizeof given, "%s/run.log", argv[1]);

    /* 1. started with no stderr (/dev/null, as from its icon or Steam): the game's log becomes its stderr (hos_main.c) */
    on_fd2("/dev/null", O_WRONLY);
    if (keep_env) keep_env();
    on_fd2(log, O_WRONLY | O_CREAT | O_TRUNC);
    execs = 0, last_log[0] = 0;
    relaunch();
    if (execs != 1) fail("the restart did not exec the game");
    if (exec_err_regular)
        fail("a game given no stderr starts again with its own hookshot_log.txt as stderr: the new run takes it for a stderr it "
             "was given, appends to it unrotated, and the crash window does not find the run's log");
    struct stat st;
    if (fstat(STDERR_FILENO, &st) || st.st_ino != ino_of(log))
        fail("after a failed exec, stderr is not the game's log again: the restart's failure is not in the log");
    if (!strstr(last_log, "could not be started again")) fail("a failed exec is not said");

    /* 2. started with a stderr of its own (a file: 2>run.log, hookshot_ctl.py's log.txt): passed on as it is */
    on_fd2(given, O_WRONLY | O_CREAT | O_TRUNC);
    if (keep_env) keep_env();
    execs = 0;
    relaunch();
    if (execs != 1 || !exec_err_regular || exec_err_ino != ino_of(given)) fail("a game given a stderr does not start again with it");
    dprintf(out, "restart log: all checks passed\n");
    return 0;
}
"""


def sources():
    relaunch = (ROOT / "host" / "hos_relaunch.c").read_text(encoding="utf-8")
    linux = between(relaunch, "#include <dirent.h>", "/* Shared tail after rx_close_asked returned.").rstrip()
    if not linux.endswith("#endif"):
        raise SystemExit("hos_relaunch.c: the Linux restart does not end at its #endif")
    return linux[:-len("#endif")]


def main_keeps():
    hos_main = (ROOT / "host" / "hos_main.c").read_text(encoding="utf-8")
    linux_main = hos_main[hos_main.rindex("int main(int argc, char **argv) {"):]
    if "hos_relaunch_keep_env();" not in linux_main[:linux_main.index("load_hookshot_env();")]:
        raise SystemExit("hos_main.c: the Linux main does not keep what stderr the game was given (hos_relaunch_keep_env) "
                         "before hookshot_env.txt and the log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        print("SKIP: Linux only")
        return
    cut = sources()
    with tempfile.TemporaryDirectory(prefix="restart-log-") as tmp:
        src = Path(tmp) / "restart_log_test.c"
        src.write_text(HARNESS.replace("@CUT@", cut), encoding="utf-8")
        exe = Path(tmp) / "restart-log-test"
        subprocess.run([args.cxx, "-x", "c", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "host"), str(src),
                        "-o", str(exe)], check=True)
        if subprocess.run([str(exe), tmp, "an argument"]).returncode:
            raise SystemExit("FAIL: the Linux restart's stderr (above)")
    main_keeps()
    print("PASS: a restart on Linux gives the game started again the stderr it was given")


if __name__ == "__main__":
    main()
