"""The supervisor of the shader preparation at a build (nx2/prepare_supervisor.py), against a stand-in game: no game, no GPU.

The stand-in prepares a list of programs a few at a time, as the game's threads do, and writes the journal the game writes
(gpu/vk/prepare_journal.h). Some of its programs kill it, or never return, when they are handed to the "driver"; it reads
the arguments the supervisor gives a run started again (--prepare-from, --prepare-skip) and follows them, as the game does.

- a program that kills the run costs that program: named, appended to hookshot_driver_faults.txt as the game reads it, the
  run started again past it, the preparation finished;
- one that never returns, the same, as "timed out";
- with several threads inside the driver the neighbours are not blamed: one more start, with the suspects one at a time;
- a run that dies with nothing open is started once more, and a second such death gives up as before;
- a driver that fails on everything stops after the bound, and what was found stays listed;
- exit 3 (no Vulkan), exit 4 (nothing moved) and a silent run with nothing open are not retried;
- a shader of the renderer's own, a run that does not follow the list and a run that never opens the journal each stop;
- make_game.py's prepare_shaders with a stand-in process: the build's lines, the faults file, never a failed build.

    python -I -B tests/test_prepare_supervisor.py
"""
import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sup = load("prepare_supervisor_under_test", ROOT / "nx2" / "prepare_supervisor.py")

DRIVER = "1002 00800161"
FAILS = 0   # (counted by need)


def need(ok, what):
    global FAILS
    if not ok:
        FAILS += 1
        print("FAIL: " + what, flush=True)


class Game:
    """A stand-in for hookshot --prepare-shaders. work: its programs' keys, in order. bad: {key: "crash" or "hang"}.
    threads: how many are inside the driver at once. blind: how many starts die with nothing open. obey: whether it leaves
    out what --prepare-skip names; serial: whether it builds that file's suspects one at a time. own: a shader of the
    renderer's own (key 0) is open when it dies. mute: starts after this many never open the journal"""

    def __init__(self, work, bad=None, threads=1, blind=0, obey=True, serial=True, own=False, mute=None):
        self.work, self.bad, self.threads, self.blind, self.obey, self.own, self.mute = work, bad or {}, threads, blind, obey, own, mute
        self.serial = serial
        self.starts, self.asked = [], []

    def start(self, extra):
        args = dict(zip(extra[::2], extra[1::2]))
        self.starts.append(args)
        if self.mute is not None and len(self.starts) > self.mute:
            self.asked.append(None)
            return -11
        skip, alone = set(), set()
        if "--prepare-skip" in args:
            text = Path(args["--prepare-skip"]).read_text(encoding="utf-8")
            self.asked.append(text)
            for line in text.splitlines():
                word, key = line.split()
                (skip if word == "skip" else alone).add(int(key, 16))
        else:
            self.asked.append(None)
        seq = int(args.get("--prepare-from", 0))
        lines = ["run %s %x" % (DRIVER, seq)]

        def out(code):
            with open(args["--prepare-journal"], "a", encoding="utf-8", newline="\n") as f:
                f.write("".join(l + "\n" for l in lines))
            return code

        if self.blind:
            self.blind -= 1
            return out(1)
        if self.own:
            seq += 1
            lines.append("b %x module %s %016x %016x" % (seq, DRIVER, 0, 64))
            return out(-11)
        todo = [k for k in self.work if not (self.obey and k in skip)]
        while todo:
            batch = []
            while todo and len(batch) < self.threads:
                if self.serial and alone and batch:
                    break   # (all calls are isolated during diagnosis)
                batch.append(todo.pop(0))
            numbered = []
            for k in batch:
                seq += 1
                numbered.append((seq, k))
                lines.append("b %x graphics %s %016x %016x" % (seq, DRIVER, k, 8))
            for n, k in numbered:
                if self.bad.get(k) == "crash":
                    return out(-11)
                if self.bad.get(k) == "hang":
                    lines.append("t %x %d" % (n, int(args.get("--prepare-entry-limit", 0))))
                    return out(sup.EXIT_ENTRY_LIMIT)
            for n, k in numbered:
                lines.append("e %x 0 5" % n)
        return out(0)


def prepare(game, **policy):
    """One supervised preparation of the stand-in in a folder of its own. (code, decision, said, faults' lines, result list)"""
    with tempfile.TemporaryDirectory(prefix="prepare-supervisor-") as tmp:
        cache = Path(tmp) / "cache"
        cache.mkdir()
        said = []
        code, decision = sup.supervise(game.start, str(cache), say=said.append, limit_s=240, policy=sup.Policy(**policy))
        faults = cache / sup.FAULTS
        results = cache / sup.RESULTS
        left = sorted(p.name for p in cache.iterdir())
        return (code, decision, said, [l for l in faults.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
                if faults.exists() else [], results.read_text(encoding="utf-8") if results.exists() else "", left)


def line(key):
    return "%s %016x" % (DRIVER, key)


def check_one_culprit():
    for how, state, verb in (("crash", "crashed", "ended the game"), ("hang", "timed-out", "did not return")):
        game = Game(list(range(1, 41)), {17: how})
        code, d, said, faults, results, left = prepare(game)
        need(code == 0 and d.action == "done", "%s: the preparation does not finish (%r, %s)" % (how, code, d.action))
        need(len(game.starts) == 2, "%s: %d starts, not the one that died and the one that finished" % (how, len(game.starts)))
        need(faults == ([line(17)] if how == "crash" else []), "%s: the faults file is %r" % (how, faults))
        need(game.starts[0].get("--prepare-entry-limit") == "240" and "--prepare-journal" in game.starts[0] and
             "--prepare-from" not in game.starts[0] and "--prepare-skip" not in game.starts[0], "%s: the first start's arguments %r" % (how, game.starts[0]))
        need(game.starts[1].get("--prepare-from") == "17", "%s: started again past entry %r, not 17" % (how, game.starts[1].get("--prepare-from")))
        need(game.asked[1] == "skip %016x\n" % 17, "%s: the second start's list is %r" % (how, game.asked[1]))
        need("%s graphics %s 0000000000000008 " % (state, line(17)) in results, "%s: the result list lacks the culprit:\n%s" % (how, results))
        need("%s 1\n" % state in results and "built 55\n" in results and "ended prepared\n" in results and "runs 2\n" in results,
             "%s: the result list's totals:\n%s" % (how, results))
        # (the culprit is counted and listed once, as what it was: not as an entry that was merely interrupted as well)
        need("interrupted 0\n" in results and "interrupted graphics %s " % line(17) not in results,
             "%s: the result list has the culprit as interrupted too:\n%s" % (how, results))
        need(any(verb in s and "%016x" % 17 in s for s in said) and any("1 program left out" in s for s in said), "%s: said %r" % (how, said))
        need(left == ([sup.FAULTS, sup.RESULTS] if how == "crash" else [sup.RESULTS]), "%s: the working files are left behind: %r" % (how, left))
    print("PASS: a shader that kills the run, or never returns, costs that shader", flush=True)


def check_threads():
    game = Game(list(range(1, 41)), {18: "crash"}, threads=4)
    code, d, said, faults, results, left = prepare(game)
    need(code == 0 and d.action == "done" and len(game.starts) == 3, "four threads: %r, %s, %d starts" % (code, d.action, len(game.starts)))
    need(faults == [line(18)], "four threads: the neighbours are blamed too: %r" % faults)
    need(game.asked[1] == "".join("alone %016x\n" % k for k in (17, 18, 19, 20)), "four threads: the suspects' list is %r" % game.asked[1])
    need(game.asked[2] == "skip %016x\n" % 18, "four threads: the last start's list is %r" % game.asked[2])
    # (the first death's four open entries are only known to have been interrupted; the culprit's is the second death's)
    need("interrupted 4\n" in results and "crashed 1\n" in results, "four threads: the result list's totals:\n" + results)
    # (two culprits in one batch, and a hang beside a crash)
    game = Game(list(range(1, 41)), {5: "crash", 6: "hang", 30: "crash"}, threads=8)
    code, d, said, faults, results, left = prepare(game)
    need(code == 0 and d.action == "done" and sorted(faults) == [line(5), line(30)], "three culprits on eight threads: %r, %r" % (code, faults))
    need("crashed 2\n" in results and "timed-out 1\n" in results, "three culprits: the result list's totals:\n" + results)
    print("PASS: several threads inside the driver: the culprit alone is left out", flush=True)


def check_blind():
    game = Game(list(range(1, 11)), blind=1)
    code, d, said, faults, results, left = prepare(game)
    need(code == 0 and d.action == "done" and len(game.starts) == 2 and not faults, "one death with nothing open: %r, %d starts" % (code, len(game.starts)))
    need("--prepare-skip" not in game.starts[1], "a death with nothing open leaves something out")
    game = Game(list(range(1, 11)), blind=5)
    code, d, said, faults, results, left = prepare(game)
    need(code == 1 and d.action == "stop" and d.reason == "died" and d.why is None and len(game.starts) == 2 and not faults,
         "two deaths with nothing open: %r, %s, %d starts" % (code, d.reason, len(game.starts)))
    need("given up (died)" in results, "the result list does not say it was given up:\n" + results)
    # (one such death, then a culprit: started again each time, the culprit kept)
    game = Game(list(range(1, 11)), {4: "crash"}, blind=1)
    code, d, said, faults, results, left = prepare(game)
    need(code == 0 and len(game.starts) == 3 and faults == [line(4)], "a death with nothing open, then a culprit: %r, %d starts, %r"
         % (code, len(game.starts), faults))
    print("PASS: a death with nothing open is tried once more, and then given up", flush=True)


def check_bound():
    work = list(range(1, 41))
    game = Game(work, {k: "crash" for k in work})
    code, d, said, faults, results, left = prepare(game)
    need(d.action == "stop" and d.reason == "culprits" and "more than %d shaders" % sup.MAX_CULPRITS in (d.why or ""),
         "a driver that fails on everything: %s, %r" % (d.reason, d.why))
    need(len(game.starts) == sup.MAX_CULPRITS + 1, "a driver that fails on everything was started %d times" % len(game.starts))
    need(faults == [line(k) for k in range(1, sup.MAX_CULPRITS + 2)], "what was found does not stay listed: %r" % faults)
    game = Game(work, {k: "hang" for k in work}, threads=4)
    code, d, said, faults, results, left = prepare(game, max_culprits=3)
    need(d.action == "stop" and d.reason == "culprits" and not faults and code == sup.EXIT_ENTRY_LIMIT,
         "a driver that hangs on everything: %s, %r, %r" % (d.reason, code, faults))
    # (every start ends with several open and the game never builds them one at a time: the starts' bound)
    game = Game(work, {k: "crash" for k in work}, threads=4, serial=False)
    code, d, said, faults, results, left = prepare(game, max_starts=6)
    need(d.action == "stop" and d.reason == "starts" and len(game.starts) == 6 and not faults,
         "a game that follows nothing: %s after %d starts, %r" % (d.reason, len(game.starts), faults))
    print("PASS: the bounds", flush=True)


def check_final():
    for code, reason in ((sup.EXIT_NO_VULKAN, "vulkan"), (sup.EXIT_STALLED, "stalled"), (None, "silent")):
        calls = []
        with tempfile.TemporaryDirectory(prefix="prepare-supervisor-") as tmp:
            got, d = sup.supervise(lambda extra: (calls.append(extra), code)[1], tmp, say=lambda s: None)
            need(got == code and d.action == "stop" and d.reason == reason and len(calls) == 1 and d.why is None,
                 "exit %r: %s after %d starts" % (code, d.reason, len(calls)))
            need(not list(Path(tmp).iterdir()), "exit %r: files are written for a run that kept no journal" % (code,))
    # (a folder that is not there: a stand-in game in another check, a game folder that cannot be written)
    got, d = sup.supervise(lambda extra: 0, str(ROOT / "no-such-folder" / "cache"), say=lambda s: need(False, "said " + s))
    need(got == 0 and d.action == "done", "a clean run in a folder that is not there")
    game = Game([1, 2, 3], own=True)
    code, d, said, faults, results, left = prepare(game)
    need(d.action == "stop" and d.reason == "own" and len(game.starts) == 1 and not faults and "renderer's own" in d.why,
         "a shader of the renderer's own: %s, %d starts" % (d.reason, len(game.starts)))
    game = Game([1, 2, 3], {2: "crash"}, obey=False)
    code, d, said, faults, results, left = prepare(game)
    need(d.action == "stop" and d.reason == "repeated" and len(game.starts) == 2 and faults == [line(2)],
         "a game that builds what it was told to leave out: %s, %d starts" % (d.reason, len(game.starts)))
    game = Game([1, 2, 3], {2: "crash"}, mute=1)
    code, d, said, faults, results, left = prepare(game)
    need(d.action == "stop" and d.reason == "died" and len(game.starts) == 3 and faults == [line(2)],
         "a run that never opens the journal is read as the run before: %s, %d starts, %r" % (d.reason, len(game.starts), faults))
    print("PASS: what is not retried", flush=True)


def check_policy():
    def entry(key, seq=1):
        return sup.Entry(1, seq, "graphics", line(key), key, "0" * 16)
    p = sup.Policy()
    need(p.after(0).action == "done", "a clean run")
    p = sup.Policy()
    d = p.after(None, [entry(7)])   # (stopped for silence with one entry inside the driver)
    need(d.action == "restart" and d.culprit.key == 7 and d.how == "timed out", "silence with one entry open")
    p = sup.Policy()
    d = p.after(-11, [entry(1), entry(2), entry(1, 3)])
    need(d.action == "restart" and d.culprit is None and p.suspects == [1, 2], "two programs open")
    d = p.after(-11, [entry(9), entry(2)])   # (the suspect, beside one that was not open before)
    need(d.action == "restart" and d.culprit is None and p.suspects == [9, 2], "an unrelated call beside a suspect is not attributed")
    d = p.after(-11, [entry(0), entry(2)])
    need(d.action == "restart" and d.culprit is None and p.suspects == [2], "a renderer call beside a suspect is not attributed")
    p = sup.Policy()
    p.after(-11, [entry(1), entry(2)])
    d = p.after(-11, [entry(8), entry(9)])   # (another death altogether: these are the suspects now)
    need(d.action == "restart" and d.culprit is None and p.suspects == [8, 9], "a death among other programs")
    p = sup.Policy()
    d = p.after(sup.EXIT_ENTRY_LIMIT, [entry(1), entry(2), entry(3)], entry(2))
    need(d.culprit is not None and d.culprit.key == 2 and d.how == "timed out" and len(p.culprits) == 1, "the run named its entry")
    d = p.after(sup.EXIT_ENTRY_LIMIT, [entry(5)], None)   # (the status with no "t" line: what is open)
    need(d.culprit is not None and d.culprit.key == 5, "exit 6 with no line naming the entry")
    need(sup.asked_text([1, 2], [3]) == "skip %016x\nskip %016x\nalone %016x\n" % (1, 2, 3), "the asked list's text")
    need(sup.entry_limit({}) == sup.ENTRY_LIMIT_S and sup.entry_limit({"HOOKSHOT_PREPARE_ENTRY_S": "30"}) == 30 and
         sup.entry_limit({"HOOKSHOT_PREPARE_ENTRY_S": "x"}) == sup.ENTRY_LIMIT_S and sup.entry_limit({"HOOKSHOT_PREPARE_ENTRY_S": "-4"}) == 0,
         "the entry limit from the environment")
    need(sup.ENTRY_LIMIT_S < 300, "an entry's limit is not below the whole run's 300 s with nothing moving")
    print("PASS: the policy", flush=True)


STUB = r"""
import os, sys
a = sys.argv
journal = a[a.index('--prepare-journal') + 1]
start = int(a[a.index('--prepare-from') + 1]) if '--prepare-from' in a else 0
print('@@stage shaders Preparing shaders', flush=True)
with open(journal, 'a') as f:
    f.write('run 10de 0a0b0c0d %x\n' % start)
    if not start:
        f.write('b 1 compute 10de 0a0b0c0d 00000000000000aa 0000000000000000\n')
        f.flush()
        os._exit(9)
    skipped = open(a[a.index('--prepare-skip') + 1]).read()
    f.write('b %x graphics 10de 0a0b0c0d 00000000000000bb 0000000000000000\ne %x 0 1\n' % (start + 1, start + 1))
print('asked ' + skipped.strip())
print('@@done shaders')
"""


def check_make_game():
    make_game = load("make_game_supervised", ROOT / "nx2" / "make_game.py")
    with tempfile.TemporaryDirectory(prefix="prepare-supervisor-") as tmp:
        (Path(tmp) / "cache").mkdir()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = make_game.prepare_shaders([sys.executable, "-I", "-c", STUB], tmp)
        lines = out.getvalue().splitlines()
        need(code == 0, "make_game.py: the supervised preparation ends with %r:\n%s" % (code, out.getvalue()))
        need(not any(l.startswith(make_game.NOT_PREPARED) for l in lines) and not any(l.startswith("@@done") or l.startswith("@@error") for l in lines),
             "make_game.py: a preparation that finished past a culprit is said to have failed:\n" + out.getvalue())
        need("asked skip 00000000000000aa" in lines and "done shaders" in lines, "make_game.py: the second run's lines:\n" + out.getvalue())
        need(any("compute pipeline of program 00000000000000aa" in l and "left out" in l for l in lines),
             "make_game.py: the culprit is not said:\n" + out.getvalue())
        faults = (Path(tmp) / "cache" / sup.FAULTS).read_text(encoding="utf-8")
        need(faults.endswith("10de 0a0b0c0d 00000000000000aa\n") and faults.count("\n") == 3, "make_game.py: the faults file: %r" % faults)
        need(sorted(p.name for p in (Path(tmp) / "cache").iterdir()) == [sup.FAULTS, sup.RESULTS], "make_game.py: the cache folder's files")
    print("PASS: make_game.py's prepare_shaders, supervised", flush=True)


def check_incomplete():
    for mode in ("pending", "torn", "exit"):
        with tempfile.TemporaryDirectory(prefix="prepare-supervisor-") as tmp:
            def start(extra):
                path = Path(extra[extra.index("--prepare-journal") + 1])
                path.write_text("run %s 0\nb 1 graphics %s %016x %016x\n" % (DRIVER, DRIVER, 17, 8) +
                                ("e 1 0" if mode == "torn" else ""), encoding="utf-8")
                if mode == "pending":
                    Path(str(path) + ".pending").touch()
                return sup.EXIT_JOURNAL_ERROR if mode == "exit" else -11
            code, decision = sup.supervise(start, tmp, say=lambda s: None)
            need(decision.reason == "journal" and not (Path(tmp) / sup.FAULTS).exists(),
                 "%s journal attributed a program" % mode)
            need(not (Path(tmp) / (sup.JOURNAL + ".pending")).exists(), "%s marker left behind" % mode)


def main():
    check_policy()
    check_one_culprit()
    check_threads()
    check_blind()
    check_bound()
    check_final()
    check_incomplete()
    check_make_game()
    if FAILS:
        raise SystemExit("test_prepare_supervisor: %d failed" % FAILS)
    print("PASS: the preparation's supervisor")


if __name__ == "__main__":
    main()
