"""Check that a save which still holds the first adult night's time lock is repaired outside Hyrule Field.

The game holds the clock at 20:00 while `HrlField_isFirstNightTime_Adult` (MurmurHash3 0x8592aa82) is 1 and quest
0x4dbca27f is not Ready (f_8347c020, called from f_803edf70). The flag is only meaningful in Hyrule Field's first adult
night; a save in the Market, the castle or anywhere else with the flag still 1 can never leave night (Hookshot #1064).
`oot_inventory_refresh` runs twice a second and already reads the map and Link's age, so the repair lives there: outside
Hyrule Field, clear the flag with the game's own setter and log it once.

This cuts the real `oot_inventory_refresh` (and `oot_first_night_fix` when the source has it) out of host/hos_main.c and
runs it against made-up save state, with no game and no romfs. On main the flag stays 1 and the first case fails for the
report's reason; with the repair it is cleared. Run it with:

    python -I tests/test_oot_first_night.py --cc gcc
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from compiler_command import compiler_command, parse_compiler  # noqa: E402

RUN_ALL_ARGS = ["--cc", "{cc}"]
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t x[32]; } Ctx;

static int flag = 1;                 /* HrlField_isFirstNightTime_Adult */
static int child = 1;                /* Sequence_IsChildhood: 1 child, 0 adult */
static int switch_on = 1;            /* HOS_OOT_FIRST_NIGHT_FIX */
static int event_playing;            /* the game's event manager has an active event */
static const char *map_name = "Market_Child";
static int cleared;

__attribute__((unused)) static int env_on_or(const char *name, int def) {
    if (!strcmp(name, "HOS_OOT_FIRST_NIGHT_FIX")) return switch_on;
    return def;
}
static void hos_log(const char *fmt, ...) { (void)fmt; }
static void rx_option_set(int id, int value) { (void)id; (void)value; }
static int oot_item_count(Ctx *c, const char *name) { (void)c; (void)name; return 0; }
static int oot_pouch_count(Ctx *c, const char *name) { (void)c; (void)name; return -1; }
static int oot_gamedata_bool(Ctx *c, uint32_t hash, int *value) {
    (void)c;
    if (hash == 0xcea220d3u) { *value = child; return 1; }
    if (hash == 0x8592aa82u) { *value = flag; return 1; }
    return 0;
}
__attribute__((unused)) static int oot_gamedata_set_bool(Ctx *c, uint32_t hash, int value) {
    (void)c;
    if (hash != 0x8592aa82u) return 0;
    if (flag != value) cleared++;
    flag = value;
    return 1;
}
static int oot_gamedata_string(Ctx *c, uint32_t hash, char *buf, size_t size) {
    (void)c;
    if (hash != 0x1d6189dau) return 0;
    snprintf(buf, size, "%s", map_name);
    return 1;
}
__attribute__((unused)) static int oot_event_playing(Ctx *c) { (void)c; return event_playing; }
/* (the refresh's rupee count, as this fork's oot_inventory_refresh reads it: none here) */
#define OOT_RUPEES_HASH 0xa77921d7u
#define OOT_CHEAT_RUPEES_ID 201
static uint64_t oot_gamedata_int_at(Ctx *c, uint32_t hash) { (void)c; (void)hash; return 0; }
static uint32_t recomp_load32(Ctx *c, uint64_t at) { (void)c; (void)at; return 0; }

#define OOT_CHEAT_ITEM_BASE 100
#define OOT_CHEAT_AGE_ID 200
#define OOT_ITEM_COUNT 2
#define OOT_CHEAT_ITEM_PROBES "Item_DekuSeed"
static const char *const oot_item_names[OOT_ITEM_COUNT] = {"Item_A", "Item_B"};

// FIX

// REFRESH

static void check(const char *what, int want_flag, int want_cleared) {
    if (flag != want_flag || cleared != want_cleared) {
        fprintf(stderr, "FAIL: %s: flag %d (want %d), clears %d (want %d)\n", what, flag, want_flag, cleared, want_cleared);
        exit(1);
    }
}

int main(void) {
    Ctx c = {0};
    int64_t now = 0;

#ifdef SWITCH_OFF
    /* HOS_OOT_FIRST_NIGHT_FIX=0: the repair is off for the whole run. */
    flag = 1, map_name = "Market_Child", switch_on = 0, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("the switch off leaves the flag", 1, 0);
    puts("PASS: HOS_OOT_FIRST_NIGHT_FIX=0 leaves the flag alone");
    return 0;
#else
    /* The report's state: the adult first-night flag left set in a save that is in the Market. */
    flag = 1, map_name = "Market_Child", switch_on = 1, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("the flag is cleared outside Hyrule Field", 0, 1);

    /* Hyrule Field is where the first night belongs: the repair must not touch it. */
    now += 500000000LL;
    flag = 1, map_name = "HyruleField", cleared = 0;
    oot_inventory_refresh(&c, now);
    check("the flag is left alone in Hyrule Field", 1, 0);

    /* A save that is already clear is not written again. */
    now += 500000000LL;
    flag = 0, map_name = "Market_Child", switch_on = 1, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("a clear flag is left clear", 0, 0);

    /* No map name this refresh: nothing to decide on. */
    now += 500000000LL;
    flag = 1, map_name = "", switch_on = 1, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("an empty map leaves the flag", 1, 0);

    /* An event running (the escape's cutscene, say) leaves the flag for a later refresh. */
    now += 500000000LL;
    flag = 1, map_name = "Market_Child", switch_on = 1, event_playing = 1, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("an event running leaves the flag", 1, 0);

    /* The event over, the next refresh clears it. */
    now += 500000000LL;
    event_playing = 0, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("after the event it clears", 0, 1);

    /* A map change after the Field: the next refresh clears it. */
    now += 500000000LL;
    flag = 1, map_name = "Market_Child", switch_on = 1, cleared = 0;
    oot_inventory_refresh(&c, now);
    check("a later map clears it", 0, 1);

    puts("PASS: the first adult night's time lock is cleared outside Hyrule Field, and only there");
    return 0;
#endif
}
'''


def cut(source, pattern, what):
    match = re.search(pattern, source, re.M | re.S)
    if not match:
        raise SystemExit("could not find %s in host/hos_main.c" % what)
    return match.group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default=None)
    args = parser.parse_args()
    cc = parse_compiler(args.cc) if args.cc else compiler_command("CC", "gcc", "clang")
    host = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    refresh = cut(host, r"^static void oot_inventory_refresh\(Ctx \*c, int64_t now\) \{.*?^\}", "oot_inventory_refresh")
    fix = re.search(r"^static int oot_first_night_fix\(Ctx \*c, const char \*map\) \{.*?^\}", host, re.M | re.S)
    body = FIXTURE.replace("// FIX", fix.group() if fix else "").replace("// REFRESH", refresh)
    with tempfile.TemporaryDirectory(prefix="oot-first-night-") as tmp:
        source = Path(tmp) / "test.c"
        source.write_text(body, encoding="utf-8")
        for name, flags in (("on", []), ("off", ["-DSWITCH_OFF"])):
            binary = Path(tmp) / ("test-%s.exe" % name)
            subprocess.run(cc + ["-std=c11", "-Wall", "-Wextra", "-Werror"] + flags + [str(source), "-o", str(binary)],
                           check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
