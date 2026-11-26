"""gpu/vk/menu_i18n.h as the menu reads it: vk_menu_i18n.cpp table() loads a language's first `count` entries, so each
language's count is its table's length, or the texts past it show in English (pt-BR's last one did, 582 of 583). Compiles
the header and compares each language's count, entries and table as the compiler sees them. No game.

python -I -B tests/test_menu_i18n_count.py [--cxx g++]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

FIXTURE = r"""#include <cstddef>
#include <cstdio>
#include "menu_i18n.h"
using namespace mkwvk::menu_i18n;
template <std::size_t N> constexpr std::size_t length(const Entry (&)[N]) { return N; }
struct Table { const char* name; const Entry* entries; std::size_t length; };
static const Table kTables[] = {
/* TABLES */
};
int main() {
    for (int i = 0; i < kLangCount; i++) {
        const Table* t = nullptr;
        for (const Table& each : kTables)
            if (each.entries == kLangs[i].entries) t = &each;
        std::printf("%s %s %d %zu\n", kLangs[i].code, t ? t->name : "-", kLangs[i].count, t ? t->length : (std::size_t)0);
    }
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    names = re.findall(r'^inline constexpr Entry (k\w+)\[\] = \{$', (VK / "menu_i18n.h").read_text(encoding="utf-8"), re.M)
    if len(names) < 13:
        raise SystemExit("menu_i18n.h: %d tables found, 13 expected (the table's declaration changed?)" % len(names))
    with tempfile.TemporaryDirectory(prefix="menu-i18n-count-") as tmp:
        cpp, exe = Path(tmp) / "count.cpp", Path(tmp) / "count"
        cpp.write_text(FIXTURE.replace("/* TABLES */", "".join('    {"%s", %s, length(%s)},\n' % (n, n, n) for n in names)),
                       encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(VK), str(cpp), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.split("\n")
    failures, used = [], set()
    for line in filter(None, out):
        code, table, count, length = line.split()
        if code == "en":
            ok = table == "-" and count == "0"
        else:
            ok = table != "-" and count == length
            used.add(table)
        print(("ok   " if ok else "FAIL ") + "%s: count %s, table %s of %s entries" % (code, count, table, length))
        if not ok:
            failures.append(code)
    for name in sorted(set(names) - used):
        print("FAIL %s: a table no language reads" % name)
        failures.append(name)
    print("%d failed" % len(failures) if failures else "all passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
