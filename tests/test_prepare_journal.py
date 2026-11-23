"""The preparation's journal (gpu/vk/prepare_journal.h): what a --prepare-shaders run writes before and after each call into
the driver's compiler, and what the Builder's supervisor (nx2/prepare_supervisor.py) reads back when the run died.

Compiles the real header alone and runs it, with no game and no GPU:
- an entry is named as hookshot_driver_faults.txt names one, and the game's own reader (driver_faults::parse) takes it;
- a process that ends without closing anything (_Exit in the middle of a call) leaves its begin in the file: the supervisor's
  parser finds that entry open, and only that one;
- a run started again numbers on from the last entry, an entry past its limit is named by a "t" line, a run that got through
  leaves nothing open;
- a last line cut short and lines that are not the journal's are skipped;
- the supervisor's list of programs to leave out and to build one at a time is read (asked_parse), and the test switch
  (RX_VK_TEST_PREPARE_FAULT) names the same programs in every run.
And the source: the three driver calls of the preparation are journalled in vk_draw.cpp outside the guards, a line is flushed
before the call, the run's exit status for an entry past its limit is the supervisor's, and none of it is in a file of the
shader translator's stamp.

    python -I -B tests/test_prepare_journal.py [--cxx g++]
"""
import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block   # noqa: E402

FIXTURE = r"""
#include "prepare_journal.h"
#include <cstdlib>
#include <cstring>

using namespace prepare_journal;
static int bad;
static void need(bool ok, const char* what) { if (!ok) bad++, std::printf("FAIL: %s\n", what); }

static int unit() {
    const uint32_t amd = 0x1002, drv = 0x800161;
    const uint64_t key = 0x6eaa646d07ea4e43ull;
    need(identity(amd, drv, key) == "1002 00800161 6eaa646d07ea4e43", "an entry's identity");
    need(identity(amd, drv, key) + "\n" == driver_faults::line(amd, drv, key), "the identity is a line of the faults file");
    need(driver_faults::parse(identity(amd, drv, key) + "\n", amd, drv).count(key) == 1, "the game reads it as a faulted program");
    need(driver_faults::parse(identity(amd, drv, key) + "\n", amd, drv + 1).empty(), "another driver version tries it again");
    const Asked a = asked_parse("# a comment\nskip 00000000000000aa\nalone bb\nalone 00000000000000cc\nskip\nskip zz\n"
                                "other 12\nskip 0\nskip dd extra\n\nskip ee");
    need(a.skip.size() == 2 && a.skip.count(0xaa) && a.skip.count(0xee), "the programs left out");
    need(a.alone.size() == 2 && a.alone.count(0xbb) && a.alone.count(0xcc), "the suspects built one at a time");
    need(asked_parse("").skip.empty() && asked_parse("").alone.empty(), "an empty list");
    bool wrong = true;
    TestFault t = test_fault_parse("crash:5", &wrong);
    need(t.mode == 1 && t.every == 5 && !t.key && !wrong, "crash:5");
    need(test_fault_here(t, 5) && test_fault_here(t, 10), "a program whose key is a multiple of 5");
    need(!test_fault_here(t, 4) && !test_fault_here(t, 11), "not the other programs");
    need(!test_fault_here(t, 0), "not a shader of the renderer's own");
    t = test_fault_parse("hang:1", &wrong);
    need(t.mode == 2 && t.every == 1 && !wrong && test_fault_here(t, 7) && !test_fault_here(t, 0), "hang:1: every program");
    t = test_fault_parse("crash:=6eaa646d07ea4e43", &wrong);
    need(t.mode == 1 && t.key == key && !t.every && !wrong, "crash:=<key>");
    need(test_fault_here(t, key) && !test_fault_here(t, key + 1) && !test_fault_here(t, 0), "that program alone");
    t = test_fault_parse("hang:=ff", &wrong);
    need(t.mode == 2 && t.key == 0xff && !wrong, "hang:=<key>");
    for (const char* text : {"crash:0", "boom", "crash:5x", "hang:", "crash", "crash:=", "crash:=0", "hang:=xyz", "crash:-5"}) {
        t = test_fault_parse(text, &wrong);
        need(t.mode == 0 && wrong && !test_fault_here(t, 5), text);
    }
    t = test_fault_parse(nullptr, &wrong);
    need(t.mode == 0 && !wrong, "not set");
    t = test_fault_parse("", &wrong);
    need(t.mode == 0 && !wrong, "set to nothing");
    need(!test_fault_here(t, 5), "nothing fires when it is not set");
    Writer none;   // (no file: a game run, or a journal that could not be opened)
    need(!none.on() && none.begin(kGraphics, 1, 0, 0) == 0 && none.overdue(1, 1000) == 0 && none.open_count() == 0, "no journal");
    none.end(0, 0, 0);
    need(!none.open("", amd, drv, 0), "a file that cannot be opened is no journal");
    need(kExitEntryLimit == 6, "the exit status of a run that named an entry past its limit");
    return bad ? 1 : 0;
}

// write <file> <from> die|limit|ok
static int write(const char* path, uint64_t from, const char* how) {
    Writer w;
    if (!w.open(path, 0x1002, 0x800161, from)) return 2;
    need(w.on(), "the journal is open");
    const uint64_t a = w.begin(kModule, 0x11, 0x40, 1000);
    w.end(a, 0, 1007);
    const uint64_t b = w.begin(kGraphics, 0xaaaa, 0x8, 1010);
    const uint64_t c = w.begin(kCompute, 0xbbbb, 0, 1011);
    w.end(c, -77, 1500);
    const uint64_t own = w.begin(kModule, 0, 0x10, 1600);
    w.end(own, 0, 1601);
    need(a == from + 1 && b == from + 2 && c == from + 3 && own == from + 4, "entries are numbered on from the run before");
    need(w.open_count() == 1, "one entry is open");
    if (bad) return 1;
    if (!strcmp(how, "die")) std::_Exit(9);   // (inside entry b: nothing is closed, no buffer of the C library is written out)
    if (!strcmp(how, "limit")) {
        uint64_t program = 0;
        int64_t ms = 0;
        need(w.overdue(5000, 3000) == 0, "not overdue yet");
        need(w.overdue(0, 99000) == 0, "no limit");
        need(w.overdue(5000, 7010, &program, &ms) == b && program == 0xaaaa && ms == 6000, "the entry past its limit");
        if (bad) return 1;
        std::_Exit(kExitEntryLimit);
    }
    w.end(b, 0, 1700);
    w.end(b, 0, 1800);   // (twice: nothing)
    need(w.open_count() == 0 && w.overdue(1, 99000) == 0, "nothing is open");
    return bad ? 1 : 0;
}

// faults <file>: the keys the game reads from a hookshot_driver_faults.txt, for the fixture's driver
static int faults(const char* path) {
    std::string text;
    if (FILE* f = fopen(path, "rb")) {
        char b[4096];
        size_t n;
        while ((n = fread(b, 1, sizeof b, f)) > 0) text.append(b, n);
        fclose(f);
    }
    for (const uint64_t k : driver_faults::parse(text, 0x1002, 0x800161)) std::printf("%016llx\n", (unsigned long long)k);
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && !strcmp(argv[1], "unit")) return unit();
    if (argc == 5 && !strcmp(argv[1], "write")) return write(argv[2], strtoull(argv[3], nullptr, 10), argv[4]);
    if (argc == 3 && !strcmp(argv[1], "faults")) return faults(argv[2]);
    return 64;
}
"""


def need(ok, what):
    if not ok:
        raise SystemExit("test_prepare_journal: " + what)


def supervisor():
    spec = importlib.util.spec_from_file_location("prepare_supervisor_for_journal", ROOT / "nx2" / "prepare_supervisor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_source(sup):
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    for marker, begin, call in (("VkResult guarded_graphics_held(", "JournalEntry entry(prepare_journal::kGraphics,", "guarded_graphics(cache, ci, pl)"),
                                ("VkResult guarded_compute_held(", "JournalEntry entry(prepare_journal::kCompute,", "guarded_compute(cache, ci, pl)"),
                                ("VkResult extern_guarded_shader_module(", "JournalEntry entry(prepare_journal::kModule,", "entry.end(guarded_shader_module(ci, m))")):
        body = block(draw, marker)
        need(begin in body and call in body and body.index(begin) < body.index(call), marker + " is not journalled before the driver call")
        need("entry.end(" in body and body.index("entry.end(") <= body.index(call) + len(call), marker + " does not journal the call's end")
        need("if (entry.skip) return" in body and body.index("if (entry.skip) return") < body.index(call),
             marker + " hands the driver a program the supervisor named")
    wanted = block(draw, "bool journal_wanted() {")
    need('env_on("HOOKSHOT_PREPARE_ONLY")' in wanted, "a game run could keep a journal")
    entry = block(draw, "struct JournalEntry {")
    need("if (!journal_wanted()) return;" in entry, "a game run pays for the journal")
    need("if (!j.asked.alone.empty()) j.alone_mu.lock()" in entry, "diagnosis does not isolate every driver call")
    need(entry.index("j.writer.begin(") < entry.index("journal_test_fault("), "the test fault comes before its entry is written")
    faulted = block(draw, "bool driver_faulted_program(uint64_t key) {")
    need("journal_module_program" in faulted, "a shader module's entry does not name its program")
    header = (ROOT / "gpu/vk/prepare_journal.h").read_text(encoding="utf-8")
    put = block(header, "void put(const char* line) {")
    need("fwrite(" in put and "fflush(f_)" in put and put.index("fwrite(") < put.index("fflush(f_)"),
         "a journal line is not handed to the system before the driver call")
    need("kPrepareSkip" in block(draw, "VkResult extern_guarded_shader_module(") and
         "kPrepareSkip" in block(draw, "VkResult guarded_graphics_held(") and
         "kPrepareSkip" in block(draw, "VkResult guarded_compute_held("), "a supervisor skip is reported as a driver fault")
    need('fopen(path.c_str(), "ab")' in header, "the journal is not appended to")
    need("constexpr int kExitEntryLimit = %d;" % sup.EXIT_ENTRY_LIMIT in header, "the run's exit status for an entry past its limit is not the supervisor's")
    main = (ROOT / "gpu/vk/vk_main.cpp").read_text(encoding="utf-8")
    watch = block(main, "void prepare_entry_watch() {")
    need("if (prepare_journal_overdue()) prepare_end(prepare_journal::kExitEntryLimit);" in watch, "an entry past its limit does not end the run")
    need("prepare_end(4);" in block(main, "void prepare_watchdog() {"), "the whole run's watchdog no longer ends with 4")
    supervised = block(main, "void prepare_supervised() {")
    need("if (!prepare_only()) return;" in supervised and "prepare_entry_watch();" in supervised and
         "prepare_restart_forgive();" in supervised, "the preparation run does not start its entry watch, or counts the run "
         "before against the steps")
    started = main[main.index("bool started_up() {"):]
    need(0 <= started.find("prepare_supervised();") < started.index("if (prepare_only()) {"),
         "the supervised run is set up after the preparation's parts have read the crash markers")
    args = (ROOT / "host/prepare_args.h").read_text(encoding="utf-8")
    source = (ROOT / "nx2/prepare_supervisor.py").read_text(encoding="utf-8")
    for arg, switch in (("--prepare-journal", "HOOKSHOT_PREPARE_JOURNAL"), ("--prepare-from", "HOOKSHOT_PREPARE_FROM"),
                        ("--prepare-skip", "HOOKSHOT_PREPARE_SKIP"), ("--prepare-entry-limit", "HOOKSHOT_PREPARE_ENTRY_S")):
        need('if (!strcmp(arg, "%s")) return "%s";' % (arg, switch) in args, "the game does not take " + arg)
        need('"%s"' % arg in source, "the supervisor does not give " + arg)
        need('getenv("%s")' % switch in draw, "the renderer does not read " + switch)
    # (the shader translator's stamp: a change to one of its files makes every player translate every program again)
    spec = importlib.util.spec_from_file_location("translator_files_for_journal", ROOT / "nx2" / "translator_files.py")
    stamp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stamp)
    for rel in ("gpu/vk/prepare_journal.h", "gpu/vk/vk_draw.cpp", "gpu/vk/vk_main.cpp", "gpu/vk/vk_internal.h", "gpu/vk/driver_faults.h"):
        need(not stamp.stamped(rel), rel + " is in the shader translator's stamp")
    for name in stamp.FILES:
        text = (ROOT / "gpu/vk" / name).read_text(encoding="utf-8")
        need("prepare_journal" not in text, name + " (stamped) knows of the journal")
    print("PASS: the journal in the source", flush=True)


def check_journal(cxx, sup, tmp):
    source, exe = tmp / "journal.cpp", tmp / ("journal.exe" if sys.platform == "win32" else "journal")
    source.write_text(FIXTURE, encoding="utf-8")
    subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D_CRT_SECURE_NO_WARNINGS", "-pthread",
                    "-I", str(ROOT / "gpu/vk"), str(source), "-o", str(exe)], check=True)
    r = subprocess.run([str(exe), "unit"], capture_output=True, text=True, timeout=60)
    need(r.returncode == 0, "the header's own rules:\n" + r.stdout + r.stderr)
    print("PASS: identities, the asked list, the test switch", flush=True)

    def run(start, how):
        return subprocess.run([str(exe), "write", str(journal), str(start), how], capture_output=True, text=True, timeout=60)

    journal = tmp / "hookshot_prepare_journal.txt"
    r = run(0, "die")
    need(r.returncode == 9, "the fixture did not die inside its entry: %d\n%s" % (r.returncode, r.stdout))
    text = journal.read_text(encoding="utf-8")
    need(text.endswith("\n") and text.splitlines()[0] == "run 1002 00800161 0", "the run's first line: %r" % text)
    j = sup.parse(text)
    need(j.runs == 1 and len(j.entries) == 4 and j.last_seq == 4 and j.driver == "1002 00800161", "the journal of a run that died: %r" % text)
    opened = j.open_entries()
    need(len(opened) == 1 and opened[0].seq == 2 and opened[0].kind == "graphics" and opened[0].key == 0xaaaa,
         "the entry the process died in is not the open one")
    need(opened[0].identity == "1002 00800161 000000000000aaaa" and opened[0].detail == "0000000000000008", "the open entry's identity")
    need(j.timed() is None, "a run that died named no entry as past its limit")
    done = {e.seq: e for e in j.entries}
    need(done[1].result == 0 and done[1].ms == 7 and done[1].kind == "module" and done[1].key == 0x11, "an entry that returned")
    need(done[3].result == -77 and done[3].ms == 489 and sup.entry_state(done[3]) == "faulted", "a fault the guard caught")
    need(done[4].key == 0 and sup.entry_state(done[4]) == "built", "a shader of the renderer's own")
    # (the game reads what the supervisor appends: the real driver_faults::parse on the file's text)
    faults = tmp / "hookshot_driver_faults.txt"
    appended = sup.faults_with("", opened[0].identity)
    need(appended.startswith("#") and appended.endswith("1002 00800161 000000000000aaaa\n"), "the faults file's text: %r" % appended)
    need(sup.faults_with(appended, opened[0].identity) is None, "a program is listed twice")
    more = sup.faults_with("10de 12345678 0000000000000001", "1002 00800161 000000000000cccc")
    need(more == "10de 12345678 0000000000000001\n1002 00800161 000000000000cccc\n", "a last line without its end: %r" % more)
    faults.write_text(sup.faults_with(appended, "1002 00800161 000000000000cccc") + "1002 00800170 000000000000dddd\n", encoding="utf-8")
    keys = subprocess.run([str(exe), "faults", str(faults)], capture_output=True, text=True, timeout=60, check=True).stdout.split()
    need(sorted(keys) == ["000000000000aaaa", "000000000000cccc"], "the game does not read the supervisor's lines: %s" % keys)
    print("PASS: a process that dies inside a call leaves that entry open, and the game reads the line made of it", flush=True)

    r = run(j.last_seq, "limit")
    need(r.returncode == sup.EXIT_ENTRY_LIMIT, "the fixture's limit run: %d\n%s" % (r.returncode, r.stdout))
    text = journal.read_text(encoding="utf-8")
    j = sup.parse(text)
    need(j.runs == 2 and len(j.entries) == 8 and j.last_seq == 8, "the second run numbers on")
    need([e.seq for e in j.open_entries()] == [6], "the second run's open entry (the first run's is not its own)")
    timed = j.timed()
    need(timed is not None and timed.seq == 6 and timed.ms == 6000 and timed.key == 0xaaaa, "the entry past its limit")
    r = run(j.last_seq, "ok")
    need(r.returncode == 0, "the fixture's clean run: %d\n%s" % (r.returncode, r.stdout))
    whole = journal.read_text(encoding="utf-8")
    j = sup.parse(whole)
    need(j.runs == 3 and len(j.entries) == 12 and j.last_seq == 12 and not j.open_entries() and j.timed() is None,
         "a run that got through leaves nothing open")
    print("PASS: numbers go on across runs, a limit names its entry, a clean run leaves nothing open", flush=True)

    # (lines cut short, and lines that are not the journal's)
    for torn in ("b d graphics 1002 0080", "e", "b d graphics 1002 00800161 000000000000eeee 0000000000000000"):
        t = sup.parse(whole + torn)
        need(len(t.entries) == 12 and not t.open_entries() and t.incomplete, "a last line with no end is read: %r" % torn)
    noisy = sup.parse("junk\nb 1 graphics 1002 00800161 0000000000000001 0000000000000000\n" + text.replace("\n", "\r\n", 3) +
                      "e 99 0 1\nt 99 3\nb zz\n\nb 9 graphics 1002 00800161 0000000000000009 0000000000000000 more\n")
    need(noisy.runs == 2 and len(noisy.entries) == 8 and [e.seq for e in noisy.open_entries()] == [6],
         "lines that are not the journal's change what is read")
    need(sup.parse("").runs == 0 and not sup.parse("").open_entries() and sup.parse("run 1002 00800161 0").runs == 0, "an empty journal")
    cut = text[:text.rindex("\nt ") + 1]
    half = sup.parse(cut[:-4])   # (the last whole line cut inside)
    need(half.runs == 2 and all(e.seq != 8 or e.result is None for e in half.entries), "an end cut short counts as an end")
    print("PASS: torn and foreign lines are skipped", flush=True)

    j = sup.parse(whole)
    listed = sup.results_text(j, [(j.entries[1], "crashed")], "prepared")
    need("driver 1002 00800161\n" in listed and "runs 3\n" in listed and "ended prepared\n" in listed and "entries 12\n" in listed,
         "the result list's head:\n" + listed)
    need("crashed graphics 1002 00800161 000000000000aaaa 0000000000000008 0\n" in listed, "the culprit's row:\n" + listed)
    # (built: each run's own shader and its module, and the last run's graphics pipeline; the caught fault three times; the
    # limit run's open entry was only interrupted as far as this list knows)
    need("built 7\n" in listed and "faulted 3\n" in listed and "crashed 1\n" in listed and "interrupted 1\n" in listed,
         "the result list's totals:\n" + listed)
    print("PASS: the result list", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    sup = supervisor()
    check_source(sup)
    with tempfile.TemporaryDirectory(prefix="prepare-journal-") as tmp:
        check_journal(args.cxx, sup, Path(tmp))
    print("PASS: the preparation's journal")


if __name__ == "__main__":
    main()
