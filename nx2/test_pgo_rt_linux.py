"""Linux RX_PGO=gen runtime, game-free: ELF sections produce a mergeable raw profile.

    python -I -B nx2/test_pgo_rt_linux.py

The test deliberately links instrumented objects without passing
``-fprofile-instr-generate`` to the final link.  host/pgo_rt.c must provide the
runtime, discover the ELF section bounds, reset the counters and write a raw
profile that llvm-profdata accepts.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent

DRIVER = r'''
#include "windows.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

struct start_args { LPTHREAD_START_ROUTINE fn; void *arg; };

static void *thread_start(void *p) {
    struct start_args *a = p;
    LPTHREAD_START_ROUTINE fn = a->fn;
    void *arg = a->arg;
    free(a);
    return (void *)(uintptr_t)fn(arg);
}

HANDLE CreateThread(void *attr, SIZE_T stack, LPTHREAD_START_ROUTINE fn,
                    void *arg, DWORD flags, DWORD *id) {
    (void)attr; (void)stack; (void)flags; (void)id;
    pthread_t t;
    struct start_args *a = malloc(sizeof(*a));
    if (!a) return NULL;
    a->fn = fn; a->arg = arg;
    if (pthread_create(&t, NULL, thread_start, a)) { free(a); return NULL; }
    pthread_detach(t);
    return (HANDLE)(uintptr_t)1;
}

void Sleep(DWORD ms) { usleep((useconds_t)ms * 1000); }
DWORD GetFileAttributesA(LPCSTR path) {
    struct stat st;
    return stat(path, &st) == 0 ? FILE_ATTRIBUTE_NORMAL : INVALID_FILE_ATTRIBUTES;
}
BOOL DeleteFileA(LPCSTR path) { return unlink(path) == 0; }

__attribute__((noinline)) static int branchy(int x) {
    return (x & 1) ? x + 3 : x - 2;
}

static int marker(const char *base, const char *suffix) {
    char path[MAX_PATH];
    snprintf(path, sizeof(path), "%s%s", base, suffix);
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    fclose(f);
    return 1;
}

int main(void) {
    const char *raw = getenv("HOS_PGO");
    if (!raw || !marker(raw, ".reset")) return 2;
    char reset[MAX_PATH];
    snprintf(reset, sizeof(reset), "%s.reset", raw);
    for (int i = 0; i < 40 && access(reset, F_OK) == 0; i++) usleep(50000);
    if (access(reset, F_OK) == 0) return 3;

    volatile int value = 0;
    for (int i = 0; i < 1000; i++) value += branchy(i);
    if (!marker(raw, ".dump")) return 4;
    char dump[MAX_PATH];
    snprintf(dump, sizeof(dump), "%s.dump", raw);
    for (int i = 0; i < 40 && (access(raw, F_OK) || access(dump, F_OK) == 0); i++) usleep(50000);
    return access(raw, F_OK) == 0 && access(dump, F_OK) != 0 && value != 0 ? 0 : 5;
}
'''


def tool(name):
    override = os.environ.get(name.upper().replace("-", "_"))
    if override:
        return shutil.which(override) or override
    return shutil.which(name)


def main():
    if os.name == "nt":
        print("pgo rt linux: skipped (Windows)")
        return
    cc, profdata = tool("clang"), tool("llvm-profdata")
    if not cc or not profdata:
        print("pgo rt linux: skipped (needs clang and llvm-profdata)")
        return

    build_text = (ROOT / "nx2" / "build.py").read_text(encoding="utf-8")
    start = build_text.index('# (--export-dynamic-symbol:')
    end = build_text.index("undefined =", start)
    if re.search(r'\[\s*["\']-fprofile-instr-generate', build_text[start:end]):
        raise SystemExit("pgo rt linux: final Linux link must not request compiler-rt profile")

    with tempfile.TemporaryDirectory(prefix="hookshot-pgo-rt-") as td:
        tmp = Path(td)
        source = tmp / "driver.c"
        source.write_text(DRIVER, encoding="utf-8")
        common = ["-O0", "-fprofile-instr-generate", "-I" + str(ROOT / "host" / "posix")]
        subprocess.run([cc, *common, "-c", str(source), "-o", str(tmp / "driver.o")], check=True)
        subprocess.run([cc, *common, "-c", str(ROOT / "host" / "pgo_rt.c"), "-o", str(tmp / "pgo_rt.o")], check=True)
        exe, raw, prof = tmp / "fixture", tmp / "fixture.raw", tmp / "fixture.prof"
        # The production Linux link has no -fprofile-instr-generate here.
        subprocess.run([cc, str(tmp / "driver.o"), str(tmp / "pgo_rt.o"), "-pthread", "-o", str(exe)], check=True)
        env = dict(os.environ, HOS_PGO=str(raw))
        subprocess.run([str(exe)], env=env, check=True, timeout=10)
        subprocess.run([profdata, "merge", str(raw), "-o", str(prof)], check=True)
        shown = subprocess.check_output([profdata, "show", "--counts", "--function=branchy", str(prof)], text=True)
        if "branchy" not in shown or "Function count: 1000" not in shown:
            raise SystemExit("pgo rt linux: branch counters were not preserved:\n" + shown)
    print("pgo rt linux: ok")


if __name__ == "__main__":
    main()
