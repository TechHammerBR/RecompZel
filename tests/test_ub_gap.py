"""Words outside an inline uniform update do not walk the update list again.

Most descriptor words are not inside an UPDATE_UB. The first miss remembers the gap
around it. python -I -B tests/test_ub_gap.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
    update = block(source, "struct UbUpdate {")
    fn = block(source, "bool ub_gap(")
    read = block(source, "bool ub_read(")
    holds = read.index("ub_gap_holds(")
    scan = read.index("for (size_t i = 0; i < lim; i++)")
    if holds > scan:
        raise SystemExit("ub_read walks the updates before checking the gap")
    if "ub_list_epoch.fetch_add" not in block(source, "void ub_prune("):
        raise SystemExit("dropping an update leaves the gap in place")
    push = source[source.index("ub_updates.push_back(std::move(up));"):source.index("ub_updates.push_back(std::move(up));") + 180]
    if "ub_list_epoch.fetch_add" not in push:
        raise SystemExit("adding an update leaves the gap in place")
    fixture = f'''#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <vector>
#define CHECK(x) do {{ if (!(x)) {{ std::fprintf(stderr, "FAIL:%d %s\\n", __LINE__, #x); std::exit(1); }} }} while (0)
{update};
{fn}
int main() {{
    const std::deque<UbUpdate> updates = {{{{0, 100, std::vector<uint8_t>(10)}}, {{0, 200, std::vector<uint8_t>(10)}}}};
    const auto first = updates.cbegin(), last = updates.cend();
    uint64_t lo = 1, hi = 1;
    CHECK(ub_gap(first, last, 150, 4, &lo, &hi));
    CHECK(lo == 110 && hi == 200);
    CHECK(ub_gap(first, last, 110, 90, &lo, &hi));
    CHECK(lo == 110 && hi == 200);
    CHECK(!ub_gap(first, last, 108, 4, &lo, &hi));
    CHECK(!ub_gap(first, last, 190, 20, &lo, &hi));
    CHECK(ub_gap(first, first, 5, 5, &lo, &hi));
    CHECK(lo == 0 && hi == ~uint64_t{{0}});
    CHECK(ub_gap({{}}, {{}}, 5, 5, &lo, &hi));
    CHECK(lo == 0 && hi == ~uint64_t{{0}});
    CHECK(!ub_gap(first, last, ~uint64_t{{0}} - 2, 8, &lo, &hi));
    CHECK(ub_gap(first + 1, last, 105, 4, &lo, &hi));
    CHECK(lo == 0 && hi == 200);
    CHECK(ub_gap(first, last - 1, 205, 4, &lo, &hi));
    CHECK(lo == 110 && hi == ~uint64_t{{0}});
    std::printf("PASS: a miss remembers the gap until the next update\\n");
}}
'''
    with tempfile.TemporaryDirectory(prefix="ub-gap-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
