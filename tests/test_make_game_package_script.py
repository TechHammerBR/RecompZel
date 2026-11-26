"""nx2/make_game.py reads a game file with nx2/nxar.py when it is a .nx archive (its first bytes, not its name), else with
nx2/nup.py. No game.

Run with: python -I tests/test_make_game_package_script.py
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_game_package_under_test", ROOT / "nx2" / "make_game.py")
make_game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_game)


class PackageScriptTests(unittest.TestCase):
    def script(self, name, content):
        with tempfile.TemporaryDirectory(prefix="hookshot-package-script-") as d:
            path = Path(d) / name
            path.write_bytes(content)
            return make_game.package_script(str(path))

    def test_by_first_bytes(self):
        self.assertEqual(self.script("game.nx", b"NXAR" + bytes(252)), "nx2/nxar.py")
        self.assertEqual(self.script("renamed.nup", b"NXAR" + bytes(252)), "nx2/nxar.py")
        self.assertEqual(self.script("game.nup", b"NUP\x01" + bytes(124)), "nx2/nup.py")
        self.assertEqual(self.script("other.nx", b"junk"), "nx2/nup.py")   # (nup.py says it is not a package)
        self.assertEqual(self.script("empty.nx", b""), "nx2/nup.py")

    def test_missing_file_is_left_to_the_reader(self):
        self.assertEqual(make_game.package_script(str(ROOT / "no-such-game.nx")), "nx2/nup.py")

    def test_both_readers_are_run_through_it(self):
        source = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("PY + [package_script(a.nup), a.nup, \"--extract\""), 2)
        self.assertNotIn('PY + ["nx2/nup.py"', source)


if __name__ == "__main__":
    unittest.main()
