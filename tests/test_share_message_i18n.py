"""The Insert menu's Save my pipeline list message in the menu's language. vk_menu.cpp puts the help box's line together from
pieces (the zip's name, its pipelines, its folder, what the worker did), and ui::para looks the whole line up once, which no
table has: so each piece is looked up as it is put in, from the pieces menu_i18n.h's tables carry (" pipelines) in ",
"your home folder", "The report is in the zip. " ...). Compiles the menu's lookup (vk_menu_i18n.cpp: its tables, tr_text,
tr) and the line's functions (vk_menu.cpp share_folder_name, share_saved_line, share_done_line, share_not_written_line),
builds the lines in each language and compares them with the tables' pieces: English as it was, every other language
translated, and the whole line drawn as it was made. No game.

python -I -B tests/test_share_message_i18n.py [--cxx g++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block  # noqa: E402
from test_menu_i18n import tables  # noqa: E402

NAME, PIPELINES, DIR = "hookshot-pipelines-2026-11-16.zip", 1234, "C:\\Users\\someone\\Downloads\\"
WHERE = ("", "your home folder", "the game folder")   # (share_downloads' words: none for the Downloads folder)
REPORT = ("The report is in the zip. ", "The report is copied. ")
ISSUE = ("Open git.notrexed.dev/Hookshot/Hookshot/issues/14 and attach", "Issue 14 is open in your browser: attach")
TAIL = " the zip to a comment, then paste the report and say where you played."
PIECES = ("Saved ", " pipelines) in ", "The zip could not be written in ", TAIL) + WHERE[1:] + REPORT + ISSUE

FIXTURE = r"""#include <algorithm>
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
#include "menu_i18n.h"
namespace mkwvk::i18n {
int lang = 0;
int lang_now() { return lang; }
std::string tr_text(const std::string& s);
const char* tr(const char* s);
/* LOOKUP */
}  // namespace mkwvk::i18n
namespace mkwvk {
/* LINES */
}  // namespace mkwvk
using namespace mkwvk;
static void put(const char* code, int where, const char* kind, const std::string& line) {
    std::printf("%s\t%d\t%s\t%s\t%s\n", code, where, kind, i18n::tr(line.c_str()) == line ? "same" : "changed", line.c_str());
}
int main() {
    static const char* const where[] = {"", "your home folder", "the game folder"};
    for (int l = 0; l < menu_i18n::kLangCount; l++) {
        i18n::lang = l;
        for (int w = 0; w < 3; w++) {
            const std::string folder = share_folder_name("DIR", where[w]);
            for (int r = 0; r < 4; r++)
                put(menu_i18n::kLangs[l].code, w, ("saved" + std::to_string(r)).c_str(),
                    share_saved_line("NAME", PIPELINES, folder) + share_done_line(r));
            put(menu_i18n::kLangs[l].code, w, "not written", share_not_written_line(folder));
        }
    }
}
"""


def c_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def expected(table, where, kind):
    tr = lambda s: table.get(s, s)  # noqa: E731
    folder = tr(WHERE[where]) if WHERE[where] else "Downloads"
    if kind == "not written":
        return tr("The zip could not be written in ") + folder + "."
    r = int(kind[-1])
    return (tr("Saved ") + NAME + " (" + str(PIPELINES) + tr(" pipelines) in ") + folder + ". " + tr(REPORT[r & 1]) +
            tr(ISSUE[r >> 1 & 1]) + tr(TAIL))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    i18n = (VK / "vk_menu_i18n.cpp").read_text(encoding="utf-8")
    menu = (VK / "vk_menu.cpp").read_text(encoding="utf-8")
    lookup = "\n".join((block(i18n, "namespace {\n\n/// A printf conversion"),
                        block(i18n, "std::string tr_text(const std::string& s) {"),
                        block(i18n, "const char* tr(const char* s) {")))
    lines = "\n".join(block(menu, head) for head in (
        "std::string share_folder_name(", "std::string share_saved_line(", "std::string share_done_line(",
        "std::string share_not_written_line("))
    fixture = (FIXTURE.replace("/* LOOKUP */", lookup).replace("/* LINES */", lines).replace('"DIR"', c_string(DIR))
               .replace('"NAME"', c_string(NAME)).replace("PIPELINES", str(PIPELINES)))
    with tempfile.TemporaryDirectory(prefix="share-message-i18n-") as tmp:
        cpp, exe = Path(tmp) / "share.cpp", Path(tmp) / "share"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(VK), str(cpp), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], check=True, capture_output=True).stdout.decode("utf-8").replace("\r\n", "\n")   # (Windows' text-mode stdout)

    found, langs = tables()
    by_code = {code: dict(found[table]) for code, _, table, _ in langs[1:]}
    by_code["en"] = {}
    failures = []
    for code, table in by_code.items():
        missing = [p for p in PIECES if code != "en" and p not in table]
        if missing:
            failures.append("%s: the table has no %r" % (code, missing))
    seen = 0
    for row in filter(None, out.split("\n")):
        code, where, kind, drawn, line = row.split("\t")
        want = expected(by_code[code], int(where), kind)
        seen += 1
        if line != want or drawn != "same":
            failures.append("%s, %s, %s: %r%s, the tables' pieces make %r" % (
                code, WHERE[int(where)] or "Downloads", kind, line, "" if drawn == "same" else " (drawn changed)", want))
    if seen != len(by_code) * len(WHERE) * 5:
        failures.append("%d lines made, %d expected" % (seen, len(by_code) * len(WHERE) * 5))
    for f in failures[:20]:
        print("FAIL " + f)
    print("%d failed of %d lines" % (len(failures), seen) if failures else "all passed: %d lines in %d languages" % (seen, len(by_code)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
