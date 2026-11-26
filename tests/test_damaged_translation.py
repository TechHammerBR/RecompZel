"""(issue 1762) A compile that refuses translated files: the game is translated again, and files that come out different were changed
by the PC (the same translation made twice is the same, byte for byte). The build says so and compiles the new translation, once.
A translation that comes out the same stops the build with the compiler's error, as does anything that is not the translation.

Runs make_game.py's own compile step, cut out of main() with ast, and its own run(), with a stand-in for build.py that refuses a
file holding a damaged word, and for the translation: no game, no compiler.

    python -I -B tests/test_damaged_translation.py
"""
import ast
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import make_game  # noqa: E402

GOOD = "#include \"a64.h\"\nvoid f_80001000(Ctx *c) {\n    uint64_t _a=c->x[0];\n}\n"
BAD = GOOD.replace("uint64_t", "uint65_t")   # (one bit: issue 1414's)
SILENT = GOOD.replace("x[0]", "x[1]")   # (one bit, and C all the same)
FAKE = '''import os, sys
gen, host = sys.argv[1], sys.argv[2]
log = os.path.join(gen, "..", "compiles")
open(log, "a").write("x")
print("3 files, 4 jobs, -O2")
failed = []
for d, f in [(gen, f) for f in sorted(os.listdir(gen))] + [(host, f) for f in sorted(os.listdir(host))]:
    if not f.endswith(".c"):
        continue
    p = os.path.join(d, f)
    text = open(p).read()
    at = p[:-2] + ".split.c" if "SPLIT" in os.environ else p
    if "uint65_t" in text:
        failed.append((f, "%s:3:5: error: use of undeclared identifier 'uint65_t'; did you mean 'uint64_t'?" % at))
    elif "CRASH" in text:
        failed.append((f, "clang: error: unable to execute command: Killed\\nclang: error: clang frontend command failed due to signal"))
    else:
        print("  %-16s %4d MB  %6.0fs  (%.0fs)" % (f, 1, 1, 1))
for f, err in failed:
    print("not compiled yet: %s (1 MB, 1s), tried again alone at the end:\\n%s" % (f, err))
for f, err in failed:
    print("FAILED %s (1 MB, 1s, alone too):\\n%s" % (f, err))
print("compiled in 1s, %d failed" % len(failed))
sys.exit(1 if failed else 0)
'''


def compile_step():
    """main()'s statements from the first list build.py's lines fill to the compile's try, the failed build forgotten"""
    tree = ast.parse(Path(make_game.__file__).read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    first = next(n for n, s in enumerate(main.body) if isinstance(s, ast.Assign) and ast.unparse(s.targets[0]) == "linking")
    last = next(n for n, s in enumerate(main.body) if isinstance(s, ast.Try) and "forget_failed_build" in ast.unparse(s.handlers))
    assert first < last
    return compile(ast.Module(main.body[first:last + 1], []), make_game.__file__, "exec")


class DamagedTranslationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hookshot-damaged-")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.gen, self.host = self.work / "sa" / "gen", self.work / "host"
        self.gen.mkdir(parents=True)
        self.host.mkdir()
        self.fake = self.work / "build.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        (self.host / "hos_main.c").write_text("int main;\n")
        self.translations = 0

    def files(self, files):
        for name, text in files.items():
            (self.gen / name).write_text(text, newline="\n")

    def build(self, first, later=(), key=lambda: "key", environment=None):
        """The compile step over the translation `first`; each translation made from then on leaves the next of `later`.
        Returns what it printed and whether the build stopped"""
        self.files({"a64_guest.h": "/* authored */\n", **first})
        (self.gen / make_game.LIFT_KEY).write_text("key\nprint\n")
        todo = list(later)

        def translate():
            self.assertFalse((self.gen / make_game.LIFT_KEY).exists(), "a translation vouched for by its key would be kept")
            self.assertTrue(todo, "translated more often than expected")
            self.translations += 1
            self.files(todo.pop(0))
            (self.gen / make_game.LIFT_KEY).write_text("key\nprint\n")

        space = dict(vars(make_game), PY=[sys.executable, "-I", str(self.fake), str(self.gen), str(self.host)], work=str(self.work),
                     gen_dir=str(self.gen), gen=str(self.gen), exefs="exefs", env=environment or {}, key="key", kept_lift=[],
                     a=type("Arguments", (), {"jobs": 4}), translate=translate, compiled=lambda line: None, run_files={},
                     done={"n": 0.0, "of": 1.0}, lift_key=lambda *a, **k: key())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                exec(compile_step(), space)
                stopped = False
            except SystemExit:
                stopped = True
        self.assertEqual(todo, [], "translated less often than expected: %s" % out.getvalue())
        self.compiles = len((self.gen / ".." / "compiles").read_text())
        (self.gen / ".." / "compiles").unlink()
        return out.getvalue(), stopped

    def errors(self, printed):
        return [line for line in printed.splitlines() if line.startswith("@@error ")]

    def test_a_build_that_works_is_as_before(self):
        printed, stopped = self.build({"code_000.c": GOOD, "code_001.c": GOOD})
        self.assertFalse(stopped)
        self.assertEqual((self.compiles, self.translations), (1, 0))
        self.assertNotIn("memory", printed)

    def test_a_changed_file_is_translated_and_compiled_again(self):
        for split in ({}, {"SPLIT": "1"}):   # (the compiler names the source, or the copy with its giants split)
            with self.subTest(split=split):
                self.translations = 0
                printed, stopped = self.build({"code_000.c": GOOD, "code_001.c": BAD, "code_002.c": GOOD}, [{"code_001.c": GOOD}],
                                              environment=split)
                self.assertFalse(stopped, printed)
                self.assertEqual((self.compiles, self.translations), (2, 1))
                self.assertEqual(self.errors(printed), [], "the launcher ends a build at @@error")
                said = [line for line in printed.splitlines() if "memory" in line]
                self.assertEqual(len(said), 1, printed)
                self.assertIn("1 of 4 files", said[0])
                self.assertIn("code_001.c", said[0])
                self.assertIn("drive", said[0])
                self.assertTrue((self.gen / make_game.LIFT_KEY).exists(), "the good translation is the next build's too")

    def test_a_change_that_compiled_is_found_with_it(self):
        printed, stopped = self.build({"code_000.c": SILENT, "code_001.c": BAD}, [{"code_000.c": GOOD, "code_001.c": GOOD}])
        self.assertFalse(stopped, printed)
        self.assertIn("2 of 3 files", printed)
        self.assertIn("code_000.c, code_001.c", printed)

    def test_a_changed_header_is_found(self):
        printed, stopped = self.build({"a64_guest.h": "/* buthored */\n", "code_000.c": BAD}, [{"a64_guest.h": "/* authored */\n",
                                                                                              "code_000.c": GOOD}])
        self.assertFalse(stopped, printed)
        self.assertIn("a64_guest.h, code_000.c", printed)

    def test_the_same_again_stops_with_the_compilers_error(self):
        printed, stopped = self.build({"code_000.c": GOOD, "code_001.c": BAD}, [{"code_001.c": BAD}])
        self.assertTrue(stopped)
        self.assertEqual((self.compiles, self.translations), (1, 1))
        self.assertEqual(len(self.errors(printed)), 1, printed)
        self.assertIn("undeclared identifier 'uint65_t'", self.errors(printed)[0])
        self.assertNotIn("XMP", printed)
        self.assertFalse((self.gen / make_game.LIFT_KEY).exists(), "a failed build forgets the translation")

    def test_changed_again_stops_with_what_to_check(self):
        printed, stopped = self.build({"code_000.c": GOOD, "code_001.c": BAD}, [{"code_000.c": BAD, "code_001.c": GOOD}])
        self.assertTrue(stopped)
        self.assertEqual((self.compiles, self.translations), (2, 1), "translated once more, not over and over")
        self.assertEqual(len(self.errors(printed)), 1, printed)
        error = self.errors(printed)[0]
        for words in ("2 of 3 files", "code_000.c, code_001.c", "memory", "drive", "XMP", str(self.work)):
            self.assertIn(words, error)
        self.assertFalse((self.gen / make_game.LIFT_KEY).exists())

    def test_then_a_source_of_the_repository_stops_as_itself(self):
        """The new translation compiles and something else fails: that is what the build stops with"""
        fake = FAKE.replace(
            "failed = []\n", "failed = []\nif len(open(log).read()) == 2:\n"
            "    failed.append(('hos_main.c', os.path.join(host, 'hos_main.c') + ':1:1: error: authored'))\n", 1)
        self.fake.write_text(fake, encoding="utf-8")
        printed, stopped = self.build({"code_000.c": BAD}, [{"code_000.c": GOOD}])
        self.assertTrue(stopped)
        self.assertIn("error: authored", self.errors(printed)[0])
        self.assertTrue((self.gen / make_game.LIFT_KEY).exists(), "only a source failed: the translation is kept")

    def test_what_is_not_the_translation_is_not_translated_again(self):
        cases = {"a compiler that ran out of memory": ({"code_000.c": "CRASH\n"}, None),
                 "a source of the repository": ({"code_000.c": GOOD}, "uint65_t x;\n"),
                 "both": ({"code_000.c": BAD}, "uint65_t x;\n")}
        for name, (first, host) in cases.items():
            with self.subTest(name):
                (self.host / "hos_main.c").write_text(host or "int main;\n")
                printed, stopped = self.build(first)
                self.assertTrue(stopped)
                self.assertEqual((self.compiles, self.translations), (1, 0))
                self.assertEqual(len(self.errors(printed)), 1, printed)

    def test_parallel_source_error_that_succeeds_alone_does_not_classify_a_killed_compiler(self):
        fake = FAKE.replace(
            'for f, err in failed:\n    print("FAILED',
            'failed = [(f, err) for f, err in failed if f != "code_000.c"]\n'
            'print("  code_000.c          1 MB       1s  (1s, alone)")\n'
            'for f, err in failed:\n    print("FAILED', 1)
        self.fake.write_text(fake, encoding="utf-8")
        printed, stopped = self.build({"code_000.c": BAD, "code_001.c": "CRASH\n"})
        self.assertTrue(stopped)
        self.assertEqual((self.compiles, self.translations), (1, 0))
        self.assertIn("clang frontend command failed due to signal", self.errors(printed)[0])
        self.assertNotIn("XMP", printed)

    def test_a_killed_compiler_among_final_source_errors_is_not_a_refused_lift(self):
        printed, stopped = self.build({"code_000.c": BAD, "code_001.c": "CRASH\n"})
        self.assertTrue(stopped)
        self.assertEqual((self.compiles, self.translations), (1, 0))
        self.assertIn("clang frontend command failed due to signal", self.errors(printed)[0])
        self.assertNotIn("XMP", printed)

    def test_files_that_were_not_there_did_not_change(self):
        """A player's update links the kept objects with no lifted C there (keep_translation): what it is made to is not a change"""
        printed, stopped = self.build({"hos_image.c": BAD}, [{"code_000.c": GOOD, "code_001.c": GOOD, "hos_image.c": BAD}])
        self.assertTrue(stopped)
        self.assertEqual((self.compiles, self.translations), (1, 1))
        self.assertNotIn("XMP", printed)
        self.assertIn("undeclared identifier", self.errors(printed)[0])

    def test_other_inputs_since_prove_nothing(self):
        """A translator edited while the compile ran makes other C: the PC is not at fault, and the error is the first one's"""
        printed, stopped = self.build({"code_000.c": BAD}, key=lambda: "another key")
        self.assertTrue(stopped)
        self.assertEqual(self.translations, 0)
        self.assertIn("undeclared identifier", self.errors(printed)[0])


if __name__ == "__main__":
    unittest.main()
