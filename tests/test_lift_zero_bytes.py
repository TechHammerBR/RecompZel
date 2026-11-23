"""(issue 2296) A translated file with a zero byte in it is found when the translation ends, not in the compile: the game is translated
again in the same build, once; a second time the build stops saying how many files are damaged and what to check. A translation
that is damaged is neither kept for other work folders nor taken from there (HOOKSHOT_LIFT_STORE).

The translation never writes a zero byte into C (tests/test_compile_zero_byte.py): one there was put by a drive or the memory.
Runs make_game.py's own translate(), cut out of main() with ast, with a stand-in for nx2/lift.py: no game, no compiler.

    python -I -B tests/test_lift_zero_bytes.py
"""
import ast
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import make_game  # noqa: E402

WHOLE = b"#include \"a64.h\"\nvoid f_80001000(Ctx *c) {\n    g(c,(_b+_o),x8_);\n}\n"
ZERO = WHOLE.replace(b"(_b", b"\0_b")   # (one byte changed, as in #2150's report: the file's size and end are right)
CUT = WHOLE[:-4]
PARAMETERS = ("work", "gen_dir", "exefs", "out", "env", "key", "kept_lift")


def translate():
    """make_game's translate() and the list it fills, as a function of what main() has then: the key it ends with"""
    tree = ast.parse(Path(make_game.__file__).read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    inner = [n for n in ast.walk(main) if isinstance(n, ast.FunctionDef) and n.name == "translate"]
    assert len(inner) == 1
    outer = ast.parse("def outer(%s):\n    translate()\n    return key\n" % ", ".join(PARAMETERS)).body[0]
    outer.body.insert(0, inner[0])
    space = {}
    exec(compile(ast.fix_missing_locations(ast.Module([outer], [])), make_game.__file__, "exec"), vars(make_game), space)
    return space["outer"]


class LiftZeroByteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hookshot-lift-zero-")
        self.addCleanup(temporary.cleanup)
        self.top = Path(temporary.name)
        self.store = self.top / "lifts"
        self.lifts = []   # (a work folder's name per translation made)

    def build(self, results, name="work", store=False):
        """The translation step of one build: results[n] is what code_001.c and on hold after the n-th translation it makes.
        Returns what it printed and whether it stopped"""
        work = self.top / name
        gen, image = work / "sa" / "gen", work / "sa" / "image"
        (work / "image").mkdir(parents=True, exist_ok=True)
        todo = list(results)

        def run(command, env, on_line=None, allow=()):
            self.assertIn("nx2/lift.py", command)
            self.assertTrue(todo, "translated more often than expected")
            self.lifts.append(name)
            gen.mkdir(parents=True, exist_ok=True)
            image.mkdir(parents=True, exist_ok=True)
            (gen / "code_000.c").write_bytes(WHOLE)
            for n, data in enumerate(todo.pop(0)):
                (gen / ("code_%03d.c" % (n + 1))).write_bytes(data)
            (gen / "a64_table.c").write_text("int t;\n")
            (image / "image.bin").write_bytes(b"\0" * 64)   # (not C: zero bytes are its content)
            return 0

        printed = io.StringIO()
        environment = {"HOOKSHOT_LIFT_STORE": str(self.store) if store else "0"}
        with mock.patch.dict(os.environ, environment), mock.patch.multiple(
                make_game, run=run, lift_progress=lambda work: None, lift_share_key=lambda *a: "share",
                lift_key=lambda *a, **k: "key"), contextlib.redirect_stdout(printed):
            try:
                translate()(str(work), str(gen), str(work / "exefs"), str(self.top / "out"), {}, "key", [])
                stopped = False
            except SystemExit:
                stopped = True
        self.assertEqual(todo, [], "translated less often than expected: %s" % printed.getvalue())
        return printed.getvalue(), stopped

    def accepted(self, name="work"):
        return make_game.lifted_before(str(self.top / name), "key")

    def chunk(self, name="work"):
        return (self.top / name / "sa" / "gen" / "code_001.c").read_bytes()

    def test_a_whole_translation_is_made_once(self):
        printed, stopped = self.build([[WHOLE]])
        self.assertFalse(stopped)
        self.assertNotIn("again", printed)
        self.assertTrue(self.accepted())
        _, stopped = self.build([])   # (the next build keeps it)
        self.assertFalse(stopped)

    def test_a_zero_byte_is_translated_again_in_the_same_build(self):
        printed, stopped = self.build([[ZERO], [WHOLE]])
        self.assertFalse(stopped)
        self.assertIn("code_001.c", printed)
        self.assertIn("zero byte", printed)
        self.assertEqual(self.chunk(), WHOLE)
        self.assertTrue(self.accepted())

    def test_anywhere_in_a_file_of_any_size(self):
        # (first and last byte, and around the places a read in blocks would cut the file at)
        for size in (64, 1 << 16, (1 << 20) + 7, (4 << 20) + 1):
            body = b"x" * size + b"\n}\n"
            for at in {0, 1, size // 2, size - 1, size, (1 << 16) - 1, 1 << 16, (1 << 20) - 1, 1 << 20}:
                if at < size:
                    _, stopped = self.build([[body[:at] + b"\0" + body[at + 1:]], [WHOLE]], "w%d_%d" % (size, at))
                    self.assertFalse(stopped, (size, at))

    def test_twice_stops_with_the_count_and_what_to_check(self):
        printed, stopped = self.build([[ZERO, ZERO, WHOLE], [ZERO, WHOLE, ZERO]])
        self.assertTrue(stopped)
        error = [line for line in printed.splitlines() if line.startswith("@@error ")]
        self.assertEqual(len(error), 1, printed)
        self.assertIn("2 of 4", error[0])
        self.assertIn("code_001.c", error[0])
        self.assertIn("code_003.c", error[0])
        self.assertIn("zero byte", error[0])
        self.assertIn("memory", error[0])
        self.assertIn("drive", error[0])
        self.assertFalse(self.accepted(), "a damaged translation must not be the next build's")

    def test_a_kept_translation_is_not_read_again(self):
        """The build that made it did: reading 1.5 GB at every build that skips the lift would find only what the compile refuses"""
        self.build([[WHOLE]])
        with mock.patch.object(make_game, "lifted_zero_bytes", side_effect=AssertionError("read again"), create=True):
            printed, stopped = self.build([])
        self.assertFalse(stopped)
        self.assertIn("skipped", printed)

    def test_an_old_keyed_translation_is_checked(self):
        self.build([[WHOLE]], "damaged")
        work = self.top / "damaged"
        (work / "sa" / "gen" / "code_001.c").write_bytes(ZERO)
        make_game.write_lift_key(str(work), "key")   # (the two-line key an older builder wrote)
        printed, stopped = self.build([[WHOLE]], "damaged")
        self.assertFalse(stopped)
        self.assertIn("zero byte", printed)
        self.assertEqual(self.chunk("damaged"), WHOLE)

        self.build([[WHOLE]], "whole")
        make_game.write_lift_key(str(self.top / "whole"), "key")
        with mock.patch.object(make_game, "lifted_zero_bytes", wraps=make_game.lifted_zero_bytes) as scan:
            _, stopped = self.build([], "whole")
            self.assertFalse(stopped)
            self.assertEqual(scan.call_count, 1)
            _, stopped = self.build([], "whole")
            self.assertFalse(stopped)
            self.assertEqual(scan.call_count, 1)

    def test_cut_short_still_is(self):
        printed, stopped = self.build([[CUT], [WHOLE]])
        self.assertFalse(stopped)
        self.assertIn("cut short", printed)
        printed, stopped = self.build([[CUT], [CUT]], "twice")
        self.assertTrue(stopped)
        error = next(line for line in printed.splitlines() if line.startswith("@@error "))
        self.assertIn("cut short twice (code_001.c)", error)
        self.assertIn("free space", error)
        self.assertNotIn("zero byte", error)

    def test_a_damaged_translation_is_not_kept_for_other_folders(self):
        _, stopped = self.build([[ZERO], [WHOLE]], "a", store=True)
        self.assertFalse(stopped)
        self.assertEqual((self.store / "share" / "sa" / "gen" / "code_001.c").read_bytes(), WHOLE)
        _, stopped = self.build([], "b", store=True)   # (another folder takes the whole one)
        self.assertFalse(stopped)
        self.assertEqual(self.chunk("b"), WHOLE)


    def test_damaged_twice_leaves_nothing_for_other_folders(self):
        _, stopped = self.build([[ZERO], [ZERO]], "a", store=True)
        self.assertTrue(stopped)
        self.assertFalse((self.store / "share").exists(), "a damaged translation was kept for other work folders")

    def test_a_kept_one_damaged_since_is_let_go(self):
        self.build([[WHOLE]], "a", store=True)
        (self.store / "share" / "sa" / "gen" / "code_001.c").write_bytes(ZERO)
        _, stopped = self.build([[WHOLE]], "b", store=True)
        self.assertFalse(stopped)
        self.assertEqual(self.chunk("b"), WHOLE)
        self.assertEqual((self.store / "share" / "sa" / "gen" / "code_001.c").read_bytes(), WHOLE)   # (b's, in its place)


if __name__ == "__main__":
    unittest.main()
