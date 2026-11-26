"""The shader preparation at a build, supervised: one shader that crashes or hangs the GPU driver costs that shader, not the
whole preparation, and is not handed to that driver again by the game.

make_game.py's last step (prepare_shaders) and scripts/devtools/packs.py's prepare start `hookshot --prepare-shaders`. A driver
that dies or never returns inside one compile ended that run, the work fell to the game's first start, and the game died in
the same place. Here the run is started with a journal (gpu/vk/prepare_journal.h: a line before and after each driver
compile call). When it dies, is stopped for silence, or ends itself because one entry passed its time limit (exit status
6), the journal says which entries were inside the driver:

- one program open: that is the culprit. If the run crashed, it is appended to cache/hookshot_driver_faults.txt; a timeout
  is left out only for this preparation. The run is started again past it and without it;
- several open (the preparation compiles on many threads): the run is started again with all calls serialized, so that
  the next death has only one open;
- none open: the run is started once more as it was, and a second such death gives up, as before;
- more than MAX_CULPRITS culprits, or MAX_STARTS starts: give up, as before (a driver that fails on everything must not
loop for hours). Crashed programs found stay in the game's list.

Giving up is what a failed preparation always was: "the shaders were not prepared now", and the game prepares them at its
first start. docs/shader-preparation.md has the whole of it.

The pure parts (parse, Policy, results_text, faults_append's text) take no process and no GPU: tests/test_prepare_supervisor.py
drives them with a child described as a list of outcomes.

    python -I nx2/prepare_supervisor.py <game folder> [--compile-shaders most|all] [--entry-limit <s>]
        the supervised preparation of a game folder that is already built (a development runtime), as a build runs it
"""
import os
import re
import sys

JOURNAL = "hookshot_prepare_journal.txt"
ASKED = "hookshot_prepare_skip.txt"
RESULTS = "hookshot_prepare_results.txt"
FAULTS = "hookshot_driver_faults.txt"

# (the run's exit statuses: host/hos_main.c, gpu/vk/vk_main.cpp prepare_watchdog and prepare_entry_watch)
EXIT_NO_VULKAN = 3      # no usable Vulkan on this PC: nothing to retry
EXIT_STALLED = 4        # nothing moved in the whole run for 300 s: the run left hookshot_prepare_skipped and gave up
EXIT_ENTRY_LIMIT = 6    # one journalled entry passed its limit: its "t" line names it
EXIT_JOURNAL_ERROR = 7  # a journal write, flush or marker operation failed

# (seconds one driver call gets. Below the run's own 300 s with nothing moving, so that a stuck shader is named before the
# whole run is given up; HOOKSHOT_PREPARE_ENTRY_S in the Builder's environment sets another, 0 none)
ENTRY_LIMIT_S = 240
MAX_CULPRITS = 8        # (programs left out in one preparation; one more death then gives up)
MAX_STARTS = 20         # (starts of the game in one preparation, whatever they ended with)
MAX_BLIND = 1           # (starts again after a death with nothing open in the journal)

VK_PIPELINE_COMPILE_REQUIRED = 1000297000   # (an ask that compiles nothing found no cache: not a failure)
DRIVER_FAULT = -77                          # (a fault the in-process guard caught: vk_draw.cpp kDriverFault)

FAULTS_HEAD = ("# Hookshot: programs the graphics driver's compiler faulted on, not asked of it again on that driver\n"
               "# (gpu/vk/driver_faults.h). <vendor> <driver version> <program key>. Delete this file to try them again.\n")

_RUN = re.compile(r"run ([0-9a-f]{4}) ([0-9a-f]{8}) ([0-9a-f]+)")
_BEGIN = re.compile(r"b ([0-9a-f]+) (module|graphics|compute) ([0-9a-f]{4} [0-9a-f]{8} ([0-9a-f]{16})) ([0-9a-f]{16})")
_END = re.compile(r"e ([0-9a-f]+) (-?[0-9]+) (-?[0-9]+)")
_LIMIT = re.compile(r"t ([0-9a-f]+) ([0-9]+)")


class Entry:
    """One driver call of the journal. identity: "<vendor> <driver> <program>" as the journal has it, which is a line of
    hookshot_driver_faults.txt. result: the VkResult, None while the call has not returned. timed: its run named it as past
    its limit. state: set by results (crashed, timed out, interrupted) for an entry that never returned"""
    __slots__ = ("run", "seq", "kind", "identity", "key", "detail", "result", "ms", "timed", "state")

    def __init__(self, run, seq, kind, identity, key, detail):
        self.run, self.seq, self.kind, self.identity, self.key, self.detail = run, seq, kind, identity, key, detail
        self.result, self.ms, self.timed, self.state = None, 0, False, None


class Journal:
    """What a journal file holds. runs: how many processes opened it. entries: every begin, in the file's order. last_seq: the
    highest entry number. driver: "<vendor> <driver>" of the last run"""

    def __init__(self):
        self.runs, self.entries, self.last_seq, self.driver = 0, [], 0, ""
        self.incomplete = False

    def open_entries(self):
        """The entries of the last run that never returned: where that process was when it ended"""
        return [e for e in self.entries if e.run == self.runs and e.result is None]

    def timed(self):
        """The entry the last run named as past its limit, or None"""
        return next((e for e in self.entries if e.run == self.runs and e.timed), None)


def parse(text):
    """A journal's text read. A last line with no line end (a full disk) and lines that are not the journal's are skipped; an
    end or a limit names an open entry of its own run, or is skipped"""
    j = Journal()
    lines = text.split("\n")
    j.incomplete = bool(lines.pop())   # (a line cut short cannot be trusted)
    live = {}     # (the current run's open entries, by number)
    for line in lines:
        line = line.rstrip("\r")
        m = _RUN.fullmatch(line)
        if m:
            j.runs += 1
            j.driver = "%s %s" % (m.group(1), m.group(2))
            j.last_seq = max(j.last_seq, int(m.group(3), 16))
            live = {}
            continue
        if not j.runs:
            continue
        m = _BEGIN.fullmatch(line)
        if m:
            e = Entry(j.runs, int(m.group(1), 16), m.group(2), m.group(3), int(m.group(4), 16), m.group(5))
            j.entries.append(e)
            live[e.seq] = e
            j.last_seq = max(j.last_seq, e.seq)
            continue
        m = _END.fullmatch(line)
        if m:
            e = live.pop(int(m.group(1), 16), None)
            if e is not None:
                e.result, e.ms = int(m.group(2)), int(m.group(3))
            continue
        m = _LIMIT.fullmatch(line)
        if m:
            e = live.get(int(m.group(1), 16))
            if e is not None:
                e.timed, e.ms = True, int(m.group(2)) * 1000
    return j


class Decision:
    """What the supervisor does after a run ended. action: "done" (prepared), "restart" or "stop" (give up: why says it).
    culprit: the entry just named, how: "crashed" or "timed out". reason: a word for the stop (vulkan, stalled, silent,
    died, own, repeated, culprits, starts)"""

    def __init__(self, action, reason=None, why=None, culprit=None, how=None):
        self.action, self.reason, self.why, self.culprit, self.how = action, reason, why, culprit, how


class Policy:
    """The retry policy, with no process: after(code, opened, timed) for each run that ended, in order.

    culprits: [(Entry, how)], the programs left out so far. suspects: the programs the next run builds one at a time.
    starts: runs ended so far. blind: deaths with nothing open since the last culprit"""

    def __init__(self, max_culprits=MAX_CULPRITS, max_starts=MAX_STARTS, max_blind=MAX_BLIND):
        self.max_culprits, self.max_starts, self.max_blind = max_culprits, max_starts, max_blind
        self.culprits, self.suspects, self.starts, self.blind = [], [], 0, 0

    def culprit_keys(self):
        return [e.key for e, _ in self.culprits]

    def after(self, code, opened=(), timed=None):
        """code: the run's exit status (None: it printed nothing for too long and was stopped). opened: the entries its
        journal left open (Journal.open_entries). timed: the entry it named as past its limit (Journal.timed)"""
        self.starts += 1
        if code == 0:
            return Decision("done")
        if code == EXIT_NO_VULKAN:
            return Decision("stop", "vulkan")
        if code == EXIT_STALLED:
            return Decision("stop", "stalled")
        hung = code is None or code == EXIT_ENTRY_LIMIT
        how = "timed out" if hung else "crashed"
        if code == EXIT_ENTRY_LIMIT and timed is not None:
            opened = [timed]   # (the run said which: the others open beside it were only interrupted)
        keys = []
        for e in opened:
            if e.key not in keys:
                keys.append(e.key)
        if not keys or keys == [0]:
            if opened:   # (only shaders of the renderer's own: no list can leave those out)
                return Decision("stop", "own", "the GPU driver %s on one of the renderer's own shaders"
                                % ("did not return" if hung else "failed"))
            if code is None:   # (silent with nothing inside the driver: not the driver's compiler, and 15 minutes a try)
                return Decision("stop", "silent")
            if self.blind >= self.max_blind:
                return Decision("stop", "died")
            self.blind += 1
            return self._restart()
        again = [k for k in keys if k in self.culprit_keys()]
        if again:   # (left out and inside the driver all the same: the run does not follow the list, so no restart helps)
            return Decision("stop", "repeated", "the GPU driver %s again on a shader that was already left out"
                            % ("did not return" if hung else "failed"))
        if len(keys) > 1:   # (all calls, including the renderer's own, must be isolated on the retry)
            self.suspects = [k for k in keys if k]
            return self._restart()
        entry = next(e for e in opened if e.key == keys[0])
        self.culprits.append((entry, how))
        self.suspects, self.blind = [], 0
        if len(self.culprits) > self.max_culprits:   # (named and left out as the others, but no further start)
            d = Decision("stop", "culprits", "the GPU driver failed on more than %d shaders" % self.max_culprits)
        else:
            d = self._restart()
        d.culprit, d.how = entry, how
        return d

    def _restart(self):
        if self.starts >= self.max_starts:
            return Decision("stop", "starts", "the game was started %d times and the GPU driver still fails" % self.starts)
        return Decision("restart")


def asked_text(culprits, suspects):
    """The file a restarted run reads (--prepare-skip): the programs left out and the suspects built one at a time"""
    return "".join("skip %016x\n" % k for k in culprits) + "".join("alone %016x\n" % k for k in suspects)


def faults_with(text, identity):
    """hookshot_driver_faults.txt's text with one more program, or None when it names it already. identity: the journal's
    "<vendor> <driver> <program>", written as it is: the game matches a line by those three numbers (driver_faults::parse)"""
    if identity in [line.strip() for line in text.splitlines()]:
        return None
    if not text.strip():
        text = FAULTS_HEAD
    elif not text.endswith("\n"):
        text += "\n"
    return text + identity + "\n"


def entry_state(e):
    """built, cold (asked without compiling, in no cache), faulted (the guard caught it), failed, or what results gave an
    entry that never returned"""
    if e.result is None:
        return e.state or "interrupted"
    if e.result == 0:
        return "built"
    if e.result == VK_PIPELINE_COMPILE_REQUIRED:
        return "cold"
    return "faulted" if e.result == DRIVER_FAULT else "failed"


STATES = ("built", "cold", "failed", "faulted", "crashed", "timed out", "interrupted")


def results_text(journal, culprits, ended, slowest=20):
    """The result list: the totals, every entry that was not built, and the slowest that were. culprits: Policy.culprits.
    ended: how the preparation ended, in words"""
    # (a culprit is an entry of the journal as it was read when its run ended, and supervise reads the file again after every
    # run: the state goes to this journal's own entry of that run and number, which is the one counted and listed below)
    own = {(e.run, e.seq): e for e in journal.entries}
    left_out = []
    for e, how in culprits:
        e = own.get((e.run, e.seq), e)
        e.state = how
        left_out.append(e)
    named = {id(e) for e in left_out}
    counts = dict.fromkeys(STATES, 0)
    for e in journal.entries + [e for e in left_out if own.get((e.run, e.seq)) is not e]:
        counts[entry_state(e)] += 1
    out = ["# Hookshot: what the last shader preparation at a build did with each call into the GPU driver's compiler",
           "# (nx2/prepare_supervisor.py, docs/shader-preparation.md). Made on this PC for this driver; safe to delete.",
           "driver %s" % (journal.driver or "unknown"),
           "runs %d" % journal.runs,
           "ended %s" % ended,
           "entries %d" % len(journal.entries)]
    out += ["%s %d" % (s.replace(" ", "-"), counts[s]) for s in STATES]
    out.append("# programs left out during preparation (crashes also in %s): <state> <kind> <vendor> <driver> <program> <detail> <ms>" % FAULTS)
    out += [_row(e) for e in left_out]
    out.append("# every other entry that was not built (cold ones aside): <state> <kind> <vendor> <driver> <program> <detail> "
               "<ms> [<VkResult>]")
    out +=[_row(e) for e in journal.entries if id(e) not in named and entry_state(e) not in ("built", "cold")]
    out.append("# the slowest that were built")
    built = sorted((e for e in journal.entries if entry_state(e) == "built"), key=lambda e: -e.ms)[:slowest]
    out += [_row(e) for e in built]
    return "\n".join(out) + "\n"


def _row(e):
    state = entry_state(e)
    row = "%s %s %s %s %d" % (state.replace(" ", "-"), e.kind, e.identity, e.detail, e.ms)
    return row + (" %d" % e.result if state in ("failed", "faulted") else "")


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _write(path, text):
    """True when written. A folder that cannot be written (or is not there: a stand-in game in a check) is not an error here"""
    try:
        with open(path + ".new", "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(path + ".new", path)
        return True
    except OSError:
        return False


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _pending(path):
    try:
        os.stat(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True   # (cannot establish that the journal is safe to attribute)


def faults_append(cache, identity):
    """The program added to the game's own list, unless it is there. True when the list names it afterwards"""
    path = os.path.join(cache, FAULTS)
    text = faults_with(_read(path), identity)
    return text is None or _write(path, text)


def entry_limit(environ=None):
    environ = os.environ if environ is None else environ
    try:
        return max(0, int(environ.get("HOOKSHOT_PREPARE_ENTRY_S", ENTRY_LIMIT_S)))
    except ValueError:
        return ENTRY_LIMIT_S


def describe(e):
    what = {"module": "a shader module", "graphics": "a graphics pipeline", "compute": "a compute pipeline"}[e.kind]
    return "%s of program %016x" % (what, e.key)


def supervise(start, cache, say=None, limit_s=None, policy=None):
    """The preparation run until it is done or given up.

    start(extra): starts the game with these arguments after its own and waits; its exit status, or None when it was
    stopped for printing nothing (make_game.run's silence). An OSError goes to the caller: the game could not start.
    cache: the game folder's cache/ (the journal, the result list and hookshot_driver_faults.txt are there).
    Returns (code, decision): the last run's exit status and the Policy's last Decision ("done" or "stop")."""
    say = say or (lambda text: print(text, flush=True))
    policy = policy or Policy()
    limit_s = entry_limit() if limit_s is None else limit_s
    journal_path, asked_path = os.path.join(cache, JOURNAL), os.path.join(cache, ASKED)
    pending_path = journal_path + ".pending"
    _remove(journal_path)
    _remove(pending_path)
    _remove(asked_path)
    extra = ["--prepare-journal", journal_path] + (["--prepare-entry-limit", str(limit_s)] if limit_s else [])
    more, runs = [], 0
    while True:
        code = start(extra + more)
        journal = parse(_read(journal_path))
        if code == EXIT_JOURNAL_ERROR or _pending(pending_path) or journal.incomplete:
            if code == 0:
                code = EXIT_JOURNAL_ERROR
            decision = Decision("stop", "journal", "the shader preparation journal is incomplete")
            say("shader preparation: the journal is incomplete; no program can be attributed to this run")
            break
        # (a run that never opened the journal (it ended before the renderer started, or the file could not be written) left
        # nothing open: what the file's last run left open is the run before's, and already dealt with)
        wrote = journal.runs > runs
        runs = journal.runs
        decision = policy.after(code, journal.open_entries() if wrote else (), journal.timed() if wrote else None)
        if decision.culprit is not None:
            timed_out = decision.how == "timed out"
            listed = False if timed_out else faults_append(cache, decision.culprit.identity)
            say("shader preparation: the GPU driver %s compiling %s: that program is left out%s"
                % ("did not return from" if timed_out else "ended the game while", describe(decision.culprit),
                   " for this preparation only" if timed_out else " on this driver" if listed else
                   " for this preparation (%s could not be written, so the game will meet it again)" % FAULTS))
        if decision.action != "restart":
            break
        if decision.culprit is None:
            say("shader preparation: the game ended %s; started again%s"
                % ("with %d programs inside the GPU driver" % len(policy.suspects) if policy.suspects
                   else "with nothing inside the GPU driver",
                   " with those built one at a time, to find which it was" if policy.suspects else " once"))
        more = []
        if journal.last_seq:   # (numbers go on, and the run before is not counted against the steps: vk_draw.cpp prepare_restart_forgive)
            more += ["--prepare-from", str(journal.last_seq)]
        if policy.culprits or policy.suspects:
            if _write(asked_path, asked_text(policy.culprit_keys(), policy.suspects)):
                more += ["--prepare-skip", asked_path]
    if journal.runs:   # (a run that kept a journal: its result list beside the caches, and the working files gone)
        ended = "prepared" if decision.action == "done" else "given up (%s)" % (decision.why or decision.reason)
        _write(os.path.join(cache, RESULTS), results_text(journal, policy.culprits, ended))
        if policy.culprits:
            say("shader preparation: %d program%s left out during this preparation (%s)"
                % (len(policy.culprits), "" if len(policy.culprits) == 1 else "s", os.path.join(cache, RESULTS)))
    _remove(journal_path)
    _remove(pending_path)
    _remove(asked_path)
    return code, decision


def main(argv=None):
    import argparse
    import importlib.util
    p = argparse.ArgumentParser(description="The supervised shader preparation of a built game folder, as a build runs it")
    p.add_argument("folder", help="the game folder (a development runtime)")
    p.add_argument("--compile-shaders", choices=("most", "all"), default=None)
    p.add_argument("--entry-limit", type=int, default=None, help="seconds one driver call gets (default %d)" % ENTRY_LIMIT_S)
    a = p.parse_args(argv)
    if a.entry_limit is not None:
        os.environ["HOOKSHOT_PREPARE_ENTRY_S"] = str(a.entry_limit)
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("make_game_for_prepare", os.path.join(here, "make_game.py"))
    mg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mg)
    folder = os.path.abspath(a.folder)
    exe = next((c for c in (os.path.join(folder, mg.BESIDE[0]), os.path.join(folder, "bin", mg.BESIDE[0])) if os.path.isfile(c)), None)
    if not exe:
        sys.exit("%s has no %s" % (folder, mg.BESIDE[0]))
    level = a.compile_shaders or mg.folder_compile_level(folder) or "most"
    code = mg.prepare_shaders([exe, "--prepare-shaders", "--compile-shaders", level], folder)
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
