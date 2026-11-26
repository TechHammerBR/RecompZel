"""Save backups outside the game folder (host/save_backup.c): players lost their saves by uninstalling to update, building into
a new folder, or deleting the old one. Builds host/save_backup.c as it is (on Windows with the real file functions, on Linux
over host/posix/win32_posix.c's) and checks, in a temporary folder:

- a backup copies user/save into its own time-named folder with from.txt, and none is made when nothing is newer;
- a newer save makes another; the oldest past 20 go;
- a start whose save folder is empty takes the newest backup; one that has saves is never touched;
- HOS_SAVE_BACKUP=0, HOS_SAVE_RESTORE=0 and HOS_HEADLESS (scripted runs) turn them off;
- and the game calls it: the start restores before it backs up, and a save mount's nn::fs::Commit backs up.

python -I -B tests/test_save_backup.py [--cc gcc]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block  # noqa: E402

RUN_ALL_ARGS = ["--cc", "gcc"]
RUN_ALL_SKIP = {"windows": "the runner gives no C compiler on Windows: run it with --cc <llvm-mingw clang>"}
ROOT = Path(__file__).resolve().parents[1]

MAIN = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); return 1; } } while (0)
static char base[1024];
static void put(const char *rel, const char *text) {
    char p[1100], d[1100];
    snprintf(p, sizeof p, "%s/%s", base, rel);
    snprintf(d, sizeof d, "%s", p);
    for (char *s = d + strlen(base) + 1; *s; s++) if (*s == '/') { *s = 0; CreateDirectoryA(d, NULL); *s = '/'; }
    FILE *f = fopen(p, "wb"); fputs(text, f); fclose(f);
}
static int same(const char *rel, const char *text) {
    char p[1100], b[256] = {0};
    snprintf(p, sizeof p, "%s/%s", base, rel);
    FILE *f = fopen(p, "rb"); if (!f) return 0;
    size_t n = fread(b, 1, sizeof b - 1, f); fclose(f); b[n] = 0;
    return !strcmp(b, text);
}
static int backups(void) {
    List l; char root[1100];
    snprintf(root, sizeof root, "%s/backups", base);
    list_backups(root, &l);
    return l.n;
}
static void set(const char *k, const char *v) {
#ifdef _WIN32
    _putenv_s(k, v ? v : "");
#else
    if (v) setenv(k, v, 1); else unsetenv(k);
#endif
}
static void age(const char *rel, int seconds) {   /* (a file's time moved: newer than a backup made this second) */
    char p[1100]; struct stat st; struct utimbuf t;
    snprintf(p, sizeof p, "%s/%s", base, rel);
    stat(p, &st); t.actime = t.modtime = st.st_mtime + seconds; utime(p, &t);
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    snprintf(base, sizeof base, "%s", argv[1]);
    char root[1100], user1[1100], user2[1100], user3[1100];
    snprintf(root, sizeof root, "%s/backups", base);
    snprintf(user1, sizeof user1, "%s/game1/user", base);
    snprintf(user2, sizeof user2, "%s/game2/user", base);
    snprintf(user3, sizeof user3, "%s/game3/user", base);
    set("HOS_SAVE_BACKUPS", root); set("HOS_HEADLESS", NULL); set("HOS_SAVE_BACKUP", NULL); set("HOS_SAVE_RESTORE", NULL);
    put("game1/user/save/acct/slot_00/progress.sav", "first");
    put("game1/user/save/acct/option.sav", "options");
    CHECK(hos_save_backup(user1, "test") == 1 && backups() == 1);
    CHECK(hos_save_backup(user1, "test") == 0 && backups() == 1);   /* (nothing newer: none) */
    put("game1/user/save/acct/slot_00/progress.sav", "second");
    age("game1/user/save/acct/slot_00/progress.sav", 5);
    CHECK(hos_save_backup(user1, "test") == 1 && backups() == 2);
    /* (a new game folder with no saves takes the newest backup, the "second" one) */
    CHECK(hos_save_restore_if_empty(user2) == 1);
    CHECK(same("game2/user/save/acct/slot_00/progress.sav", "second") && same("game2/user/save/acct/option.sav", "options"));
    /* (a folder that has saves is never touched) */
    put("game1/user/save/acct/slot_00/progress.sav", "mine");
    CHECK(hos_save_restore_if_empty(user1) == 0 && same("game1/user/save/acct/slot_00/progress.sav", "mine"));
    /* (the switches, and scripted runs) */
    set("HOS_SAVE_RESTORE", "0");
    CHECK(hos_save_restore_if_empty(user3) == 0);
    set("HOS_SAVE_RESTORE", NULL); set("HOS_HEADLESS", "1");
    CHECK(hos_save_restore_if_empty(user3) == 0);
    age("game1/user/save/acct/slot_00/progress.sav", 10);
    CHECK(hos_save_backup(user1, "test") == 0 && backups() == 2);
    set("HOS_HEADLESS", NULL); set("HOS_SAVE_BACKUP", "off");
    CHECK(hos_save_backup(user1, "test") == 0 && backups() == 2);
    set("HOS_SAVE_BACKUP", NULL);
    /* (the oldest past 20 go: 20 older ones made by hand, then one more) */
    for (int i = 0; i < 20; i++) {
        char rel[200];
        snprintf(rel, sizeof rel, "backups/201001%02d-120000/save/acct/option.sav", i + 1);
        put(rel, "old");
    }
    CHECK(backups() == 22);
    age("game1/user/save/acct/slot_00/progress.sav", 20);
    CHECK(hos_save_backup(user1, "test") == 1 && backups() == 20);
    char oldest[1100];
    snprintf(oldest, sizeof oldest, "%s/20100101-120000", root);
    CHECK(GetFileAttributesA(oldest) == INVALID_FILE_ATTRIBUTES);
    printf("PASS: saves backed up outside the game folder, an empty one restored from the newest, the oldest past 20 gone\n");
    return 0;
}
'''


def check_source():
    fs = (ROOT / "host/nn_fs.c").read_text(encoding="utf-8")
    commit = block(fs, "HLE(_ZN2nn2fs6CommitEPKc) {")
    if "hos_save_backup_on_commit(hos_user_dir)" not in commit or '"\\\\save\\\\"' not in commit:
        raise SystemExit("nn::fs::Commit does not back the saves up after a save mount's commit")
    main = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    made = main.index('if (!hos_user_dir) hos_user_dir = "user";')
    restore, backup = main.find("hos_save_restore_if_empty(hos_user_dir);", made), main.find('hos_save_backup(hos_user_dir, "at start");', made)
    if not 0 < restore < backup or backup - made > 800:
        raise SystemExit("the start does not restore an empty save folder before backing up, right after the user folder is set")
    seqg = Path("G:/hs-tools/seqg.ps1")   # (the owner's scripted runs; not in the repository)
    if seqg.exists() and "HOS_SAVE_BACKUP" not in seqg.read_text(encoding="utf-8", errors="replace"):
        print("note: G:\\hs-tools\\seqg.ps1 does not turn the save backups off for its runs")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default=shutil.which("gcc") or shutil.which("clang") or "cc")
    a = p.parse_args()
    check_source()
    backup_c = (ROOT / "host/save_backup.c").resolve().as_posix()
    if os.name == "nt":
        prelude = "#include <windows.h>\n#include <stdio.h>\n#include <sys/stat.h>\n#include <sys/utime.h>\nvoid hos_log(const char *f, ...) { (void)f; }\n"
        flags = []
    else:
        posix = (ROOT / "host/posix/win32_posix.c").read_text(encoding="utf-8")
        pieces = [
            block(posix, "static DWORD error_of(int e) {"),
            "static BOOL fail_errno(void) { last_error = error_of(errno); return FALSE; }",
            "enum { H_THREAD = 0x48540001, H_EVENT, H_SEMA, H_TIMER, H_FILE, H_FIND };",
            "typedef struct { int type; } HObj;",
            "static int is(HANDLE h, int type) { return h && h != INVALID_HANDLE_VALUE && (uintptr_t)h > 0x10000 && ((HObj *)h)->type == type; }",
            block(posix, "static void slashes(char *dst, size_t cap, const char *src) {"),
            block(posix, "DWORD GetFileAttributesA(LPCSTR name) {"),
            block(posix, "BOOL CreateDirectoryA(LPCSTR name, void *attr) {"),
            block(posix, "BOOL RemoveDirectoryA(LPCSTR name) {"),
            block(posix, "BOOL DeleteFileA(LPCSTR name) {"),
            block(posix, "BOOL MoveFileExA(LPCSTR from, LPCSTR to, DWORD flags) {"),
            "BOOL MoveFileA(LPCSTR from, LPCSTR to) { return MoveFileExA(from, to, 0); }",
            "typedef struct { HObj h; DIR *d; char dir[PATH_MAX], pat[256]; } HFind;",
            block(posix, "static BOOL find_next(HFind *f, WIN32_FIND_DATAA *fd) {"),
            block(posix, "HANDLE FindFirstFileA(LPCSTR pattern, WIN32_FIND_DATAA *fd) {"),
            block(posix, "BOOL FindNextFileA(HANDLE h, WIN32_FIND_DATAA *fd) {"),
            block(posix, "BOOL FindClose(HANDLE h) {"),
        ]
        prelude = ("#define _GNU_SOURCE\n#include <windows.h>\n#include <dirent.h>\n#include <errno.h>\n#include <fnmatch.h>\n"
                   "#include <limits.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
                   "#include <sys/stat.h>\n#include <unistd.h>\n#include <utime.h>\nstatic DWORD last_error;\n"
                   "void hos_log(const char *f, ...) { (void)f; }\n" + "\n".join(pieces) + "\n")
        flags = ["-I", str(ROOT / "host/posix"), "-Wno-unused-function"]
    with tempfile.TemporaryDirectory(prefix="save-backup-") as tmp:
        tmp = Path(tmp)
        src = tmp / "fixture.c"
        src.write_text(prelude + '#include "%s"\n' % backup_c + MAIN, encoding="utf-8")
        exe = tmp / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([a.cc, "-std=gnu11", "-Wall", *flags, str(src), "-o", str(exe)], check=True)
        work = tmp / "work"
        work.mkdir()
        r = subprocess.run([str(exe), str(work).replace("\\", "/")], capture_output=True, text=True, timeout=60)
        print(r.stdout + r.stderr, end="")
        if r.returncode:
            raise SystemExit("save backup checks failed")


if __name__ == "__main__":
    main()
