"""A dump with many damaged game files stops at once with "still has N damaged files with no replacement", and the
stand-ins for a few are found without opening every file of their kind (#1275): python -I -B tests/test_damaged_stand_in_fail_fast.py

A Windows build from a dump with 1896 damaged files sat after "main: ZBIC -> plain NSO" overnight before it said the dump
was incomplete: nup.stand_in_for opened every file of the damaged one's kind in its folder (PreComputedCulling/RuntimeId
holds about 35,000 .bcul.zs) for each damaged file, about 66 million opens. Game-free: small made-up files in a temporary
folder, and nup's open counted."""
import builtins
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(0, str(ROOT / "third_party/a64-kit/tools"))
import nup  # noqa: E402

spec = importlib.util.spec_from_file_location("make_game_damaged_fail_fast", ROOT / "nx2/make_game.py")
make_game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_game)

ZSTD = b"\x28\xb5\x2f\xfd"
MANY = 150     # (a dump damaged far past an incomplete dump's three textures)
WHOLE = 400    # (whole files of the same kind beside them)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


@contextlib.contextmanager
def counted_opens():
    """The files nup opens to read, by path (its writes through shutil are not counted)"""
    opened = []
    def counting(path, mode="r", *args, **kwargs):
        if "r" in mode and "+" not in mode:
            opened.append(os.fspath(path))
        return builtins.open(path, mode, *args, **kwargs)
    nup.open = counting
    try:
        yield opened
    finally:
        del nup.open


def culling_folder(romfs, damaged):
    """A RuntimeId folder as the game's: names of 16 hex digits, every one .bcul.zs; the first `damaged` begin with zeros"""
    folder = os.path.join(romfs, "PreComputedCulling", "RuntimeId")
    bad = []
    for i in range(damaged + WHOLE):
        path = os.path.join(folder, "%016x.bcul.zs" % (i * 7919))
        if i < damaged:
            write(path, bytes(64))
            bad.append(os.path.normpath(path))
        else:
            write(path, ZSTD + b"c" * (32 + i % 50))
    return bad


class ManyDamagedFilesTests(unittest.TestCase):
    def test_no_stand_in_is_looked_for(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-many-damaged-") as romfs:
            bad = culling_folder(romfs, MANY)
            with counted_opens() as opened:
                done = nup.stand_in_damaged(romfs, damaged=bad)
            self.assertEqual(done, [(path, None) for path in bad])
            self.assertEqual(opened, [])   # (main opened all 400 whole files for each of the 150)
            for path in bad:
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), bytes(64))   # (left as they were)

    def test_the_build_stops_with_the_incomplete_dump_message(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-many-damaged-") as out:
            romfs = os.path.join(out, "romfs")
            bad = culling_folder(romfs, MANY)
            stamp = "unpacked by this builder: game.nup 1"
            with open(os.path.join(out, ".hookshot_romfs"), "w", encoding="utf-8") as f:
                f.write(stamp + "\n")
            with open(os.path.join(out, make_game.HEADS), "w", encoding="utf-8", newline="\n") as f:
                f.write(stamp + "\n" + "".join(os.path.relpath(p, romfs).replace(os.sep, "/") + "\n" for p in bad))
            said = io.StringIO()
            with counted_opens() as opened, contextlib.redirect_stdout(said), self.assertRaises(SystemExit) as stopped:
                make_game.stand_in_damaged_files(out, romfs)
            self.assertEqual(stopped.exception.code, 1)
            self.assertEqual([p for p in opened if p.endswith(".bcul.zs")], [])
            self.assertIn("@@error The game dump still has %d damaged files with no replacement" % MANY, said.getvalue())
            self.assertIn("Your game dump is incomplete: %d game files in it are damaged" % MANY, said.getvalue())
            with open(os.path.join(out, make_game.DAMAGED_NOTE), encoding="utf-8") as f:
                note = f.read()
            for path in bad:   # (the whole list is kept for the player, however long)
                self.assertIn(os.path.relpath(path, romfs), note)
            self.assertFalse(os.path.exists(os.path.join(out, ".hookshot_romfs_checked")))


class FewDamagedFilesTests(unittest.TestCase):
    def test_stand_ins_found_without_opening_every_file_of_their_kind(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-few-damaged-") as romfs:
            bad = culling_folder(romfs, 3)
            with counted_opens() as opened:
                done = nup.stand_in_damaged(romfs, damaged=bad)
            self.assertTrue(all(other for _, other in done))
            self.assertLessEqual(len(opened), 2 * len(bad))   # (main: all 400 whole files for each)
            for path, other in done:
                with open(path, "rb") as f, open(other, "rb") as g:
                    self.assertEqual(f.read(), g.read())

    def test_the_same_choice_as_before(self):
        """The longest common start of the name, then the nearest size, never a damaged file, never one that is not whole"""
        with tempfile.TemporaryDirectory(prefix="hookshot-few-damaged-") as romfs:
            tex = os.path.join(romfs, "Tex")
            gate = os.path.join(tex, "Rock_Temple_Gate_M_01_Nrm.bntx.zs")
            write(gate, bytes(400) + b"rest" * 30)
            write(os.path.join(tex, "Rock_Temple_Gate_M_02_Nrm.bntx.zs"), bytes(64))               # damaged too
            write(os.path.join(tex, "Rock_Temple_Gate_M_03_Nrm.bntx.zs"), b"\0\0\0\0" + b"x" * 500)  # not whole, not listed
            write(os.path.join(tex, "Rock_Temple_Gate_P_01_Nrm.bntx.zs"), ZSTD + b"P" * 2000)
            write(os.path.join(tex, "Rock_Temple_Gate_P_02_Nrm.bntx.zs"), ZSTD + b"P" * 500)        # as close, nearer size
            write(os.path.join(tex, "Rock_Temple_Gate_M_01_Alb.bntx.zs"), ZSTD + b"A" * 520)        # another kind
            for i in range(200):
                write(os.path.join(tex, "Other_%03d_Nrm.bntx.zs" % i), ZSTD + b"o" * 520)
            damaged = [os.path.normpath(gate), os.path.normpath(os.path.join(tex, "Rock_Temple_Gate_M_02_Nrm.bntx.zs"))]
            with counted_opens() as opened:
                done = dict(nup.stand_in_damaged(romfs, damaged=damaged))
            self.assertEqual({os.path.basename(p): os.path.basename(o) for p, o in done.items()},
                             {"Rock_Temple_Gate_M_01_Nrm.bntx.zs": "Rock_Temple_Gate_P_02_Nrm.bntx.zs",
                              "Rock_Temple_Gate_M_02_Nrm.bntx.zs": "Rock_Temple_Gate_P_02_Nrm.bntx.zs"})
            self.assertLessEqual(len(opened), 4)   # (M_03 then P_02 for each at most, not the 200 others)


if __name__ == "__main__":
    unittest.main()
