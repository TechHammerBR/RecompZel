/* (hookshot, 2026-11-15) Save backups outside the game folder.

   On Windows the saves live in the game folder (user\save). Players lost them by updating the wrong way: uninstalling the game
   to install it again, building into a new folder, or deleting the old one first. Linux keeps them in ~/.local/share/hookshot,
   but a deleted or broken save is gone there too.

   So the game keeps copies itself, in a place no build, update or uninstall touches: %LOCALAPPDATA%\Hookshot\save-backups on
   Windows, $XDG_DATA_HOME/hookshot/save-backups on Linux. A backup is a folder named by its time (YYYYmmdd-HHMMSS) holding a
   copy of user/save and from.txt (the folder it came from, and when). One is made at each start and after the game commits its
   save data (at most every 20 s), and only when something in user/save is newer than the last one; the 20 newest are kept.

   A start whose user/save holds no file at all (a new game folder, one built again from nothing, a reinstall) and that finds a
   backup copies the newest one in before the game reads its saves, and says so in the log. A folder that has saves is never
   touched: a backup is only ever read into an empty one.

   HOS_SAVE_BACKUP=0: no backups; HOS_SAVE_RESTORE=0: no restore; HOS_SAVE_BACKUPS=<folder>: another place. Scripted test runs
   (G:\hs-tools\seqg.ps1, HOS_HEADLESS) turn both off, so that a test's saves never become the newest backup. */
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include "save_backup.h"
#ifndef HOOKSHOT_ENV_H   /* (env_on: the switches' one rule) */
#include "../gpu/vk/compat/hookshot_env.h"
#endif

#ifdef _WIN32
#define SEP_S "\\"
#else
#define SEP_S "/"
#endif
#define PATH_CAP 1024

void hos_log(const char *fmt, ...);

enum { KEEP = 20 };
#define COMMIT_GAP_MS 20000ull

/* whether name is a switch set to off ("0", "off", ...); unset: on */
static int switched_off(const char *name) {
    const char *v = getenv(name);
    return v && env_value_off(v);
}
static int test_run(void) { return env_on("HOS_HEADLESS"); }

static int is_dir(const char *p) {
    const DWORD a = GetFileAttributesA(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

/* every folder of path made (its parents first) */
static void make_dirs(const char *path) {
    char p[PATH_CAP];
    snprintf(p, sizeof p, "%s", path);
    for (char *s = p + 1; *s; s++) {
        if (*s != '\\' && *s != '/') continue;
        const char c = *s;
        *s = 0;
        if (s[-1] != ':') CreateDirectoryA(p, NULL);
        *s = c;
    }
    CreateDirectoryA(p, NULL);
}

typedef void (*EachFn)(const char *path, int dir, void *user);
/* fn for each entry of dir (not . and ..) */
static void each(const char *dir, EachFn fn, void *user) {
    char pattern[PATH_CAP];
    snprintf(pattern, sizeof pattern, "%s" SEP_S "*", dir);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        char p[PATH_CAP];
        snprintf(p, sizeof p, "%s" SEP_S "%s", dir, fd.cFileName);
        fn(p, (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0, user);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

/* the files under a folder, and the newest one's time */
typedef struct { unsigned files; time_t newest; } Stats;
static void stats_one(const char *path, int dir, void *user) {
    Stats *s = (Stats *)user;
    if (dir) {
        each(path, stats_one, user);
        return;
    }
    struct stat st;
    s->files++;
    if (stat(path, &st) == 0 && st.st_mtime > s->newest) s->newest = st.st_mtime;
}
static Stats tree_stats(const char *dir) {
    Stats s = {0, 0};
    if (is_dir(dir)) each(dir, stats_one, &s);
    return s;
}

static int copy_file(const char *from, const char *to) {
    FILE *in = fopen(from, "rb"), *out = in ? fopen(to, "wb") : NULL;
    int ok = in && out;
    char buf[1 << 16];
    for (size_t n; ok && (n = fread(buf, 1, sizeof buf, in)) > 0;) ok = fwrite(buf, 1, n, out) == n;
    ok = ok && in && !ferror(in);
    if (in) fclose(in);
    if (out && fclose(out)) ok = 0;
    return ok;
}
typedef struct { const char *to; int ok; unsigned files; } Copy;
static void copy_one(const char *path, int dir, void *user) {
    Copy *c = (Copy *)user;
    const char *name = strrchr(path, SEP_S[0]);
    char dst[PATH_CAP];
    snprintf(dst, sizeof dst, "%s" SEP_S "%s", c->to, name ? name + 1 : path);
    if (dir) {
        CreateDirectoryA(dst, NULL);
        Copy sub = {dst, 1, 0};
        each(path, copy_one, &sub);
        c->ok &= sub.ok, c->files += sub.files;
    } else {
        c->ok &= copy_file(path, dst);
        c->files++;
    }
}
/* from's contents into to (made if missing); the files copied, -1 on a failure */
static int copy_tree(const char *from, const char *to) {
    make_dirs(to);
    Copy c = {to, 1, 0};
    each(from, copy_one, &c);
    return c.ok ? (int)c.files : -1;
}

static void delete_one(const char *path, int dir, void *user) {
    (void)user;
    if (dir) {
        each(path, delete_one, NULL);
        RemoveDirectoryA(path);
    } else {
#ifdef _WIN32
        SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);   /* (a read-only file is not deleted otherwise) */
#endif
        DeleteFileA(path);
    }
}
static void delete_tree(const char *dir) {
    each(dir, delete_one, NULL);
    RemoveDirectoryA(dir);
}

/* a backup's folder name: YYYYmmdd-HHMMSS, maybe -<n> after it; its time, 0: not one */
static time_t backup_time(const char *name) {
    int Y, M, D, h, m, s;
    if (strlen(name) < 15 || sscanf(name, "%4d%2d%2d-%2d%2d%2d", &Y, &M, &D, &h, &m, &s) != 6) return 0;
    struct tm t = {0};
    t.tm_year = Y - 1900, t.tm_mon = M - 1, t.tm_mday = D, t.tm_hour = h, t.tm_min = m, t.tm_sec = s, t.tm_isdst = -1;
    return mktime(&t);
}

/* the backups in root, oldest first (their names sort by time) */
typedef struct { char names[64][32]; int n; } List;
static void list_one(const char *path, int dir, void *user) {
    List *l = (List *)user;
    const char *name = strrchr(path, SEP_S[0]);
    name = name ? name + 1 : path;
    if (!dir || !backup_time(name) || strstr(name, ".part") || l->n >= 64) return;
    snprintf(l->names[l->n++], sizeof l->names[0], "%s", name);
}
static int by_name(const void *a, const void *b) { return strcmp((const char *)a, (const char *)b); }
static void list_backups(const char *root, List *l) {
    l->n = 0;
    each(root, list_one, l);
    qsort(l->names, (size_t)l->n, sizeof l->names[0], by_name);
}

int hos_save_backups_dir(char *out, size_t cap) {
    const char *own = getenv("HOS_SAVE_BACKUPS");
    if (own && *own) return snprintf(out, cap, "%s", own) < (int)cap;
#ifdef _WIN32
    const char *base = getenv("LOCALAPPDATA");
    if (!base || !*base) return 0;
    return snprintf(out, cap, "%s\\Hookshot\\save-backups", base) < (int)cap;
#else
    const char *data = getenv("XDG_DATA_HOME"), *home = getenv("HOME");
    if (data && *data) return snprintf(out, cap, "%s/hookshot/save-backups", data) < (int)cap;
    if (!home || !*home) return 0;
    return snprintf(out, cap, "%s/.local/share/hookshot/save-backups", home) < (int)cap;
#endif
}

int hos_save_backup(const char *user_dir, const char *why) {
    char save[PATH_CAP], root[PATH_CAP];
    if (!user_dir || switched_off("HOS_SAVE_BACKUP") || test_run() || !hos_save_backups_dir(root, sizeof root)) return 0;
    snprintf(save, sizeof save, "%s" SEP_S "save", user_dir);
    const Stats now = tree_stats(save);
    if (!now.files) return 0;
    make_dirs(root);
    List *l = (List *)calloc(1, sizeof *l);
    if (!l) return 0;
    list_backups(root, l);
    /* (nothing written since the newest backup was made: no new one) */
    if (l->n && now.newest <= backup_time(l->names[l->n - 1])) {
        free(l);
        return 0;
    }
    char name[48], part[PATH_CAP], dst[PATH_CAP], copy_to[PATH_CAP];
    const time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    strftime(name, sizeof name, "%Y%m%d-%H%M%S", &tm);
    snprintf(dst, sizeof dst, "%s" SEP_S "%s", root, name);
    for (int k = 2; is_dir(dst) && k < 100; k++) snprintf(dst, sizeof dst, "%s" SEP_S "%s-%d", root, name, k);
    snprintf(part, sizeof part, "%s.part", dst);
    delete_tree(part);
    snprintf(copy_to, sizeof copy_to, "%s" SEP_S "save", part);
    const int files = copy_tree(save, copy_to);
    char from[PATH_CAP];
    snprintf(from, sizeof from, "%s" SEP_S "from.txt", part);
    FILE *f = fopen(from, "w");
    if (f) {
        char when[32];
        strftime(when, sizeof when, "%Y-%m-%d %H:%M:%S", &tm);
        fprintf(f, "from=%s\nwhen=%s\nwhy=%s\n", save, when, why ? why : "");
        fclose(f);
    }
    if (files <= 0 || !MoveFileA(part, dst)) {
        delete_tree(part);
        hos_log("saves: the backup to %s could not be made (%s)", dst, files <= 0 ? "copying failed" : "renaming failed");
        free(l);
        return 0;
    }
    /* (the oldest past KEEP go: the list read before this one, so it counts once more) */
    for (int i = 0; i + KEEP <= l->n; i++) {
        char old[PATH_CAP];
        snprintf(old, sizeof old, "%s" SEP_S "%s", root, l->names[i]);
        delete_tree(old);
    }
    hos_log("saves: backed up %d files to %s (%s)", files, dst, why ? why : "");
    free(l);
    return 1;
}

void hos_save_backup_on_commit(const char *user_dir) {
    static uint64_t last = 0;
    const uint64_t now = GetTickCount64();
    if (last && now - last < COMMIT_GAP_MS) return;
    last = now;
    hos_save_backup(user_dir, "the game saved");
}

int hos_save_restore_if_empty(const char *user_dir) {
    char save[PATH_CAP], root[PATH_CAP];
    if (!user_dir || switched_off("HOS_SAVE_RESTORE") || test_run() || !hos_save_backups_dir(root, sizeof root)) return 0;
    snprintf(save, sizeof save, "%s" SEP_S "save", user_dir);
    if (tree_stats(save).files) return 0;   /* (saves here: never touched) */
    List *l = (List *)calloc(1, sizeof *l);
    if (!l) return 0;
    list_backups(root, l);
    int restored = 0;
    for (int i = l->n - 1; i >= 0 && !restored; i--) {   /* (the newest whose copy has files) */
        char from[PATH_CAP];
        snprintf(from, sizeof from, "%s" SEP_S "%s" SEP_S "save", root, l->names[i]);
        if (!tree_stats(from).files) continue;
        const int files = copy_tree(from, save);
        if (files > 0) {
            hos_log("saves: none in %s: the newest backup (%s" SEP_S "%s, %d files) copied in", save, root, l->names[i], files);
            restored = 1;
        } else {
            hos_log("saves: none in %s, and the backup %s could not be copied in", save, l->names[i]);
            break;
        }
    }
    free(l);
    return restored;
}
