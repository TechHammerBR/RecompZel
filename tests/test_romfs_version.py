"""make_game.romfs_problem: which romfs folders the installer takes, and what it says of the others.

    python -I tests/test_romfs_version.py
"""
import os
import sys
import tempfile

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nx2")
sys.path.insert(0, HERE)
import make_game  # noqa: E402

FIRST = "ResourceSizeTable.Product.100.Nin_Ounce_NVN2.rsizetable.zs"   # (the game's first version's table)


def romfs_with(root, table):
    res = os.path.join(root, "System", "Resource")
    os.makedirs(res)
    if table:
        with open(os.path.join(res, table), "wb") as f:
            f.write(b"x")
    return root


def main():
    with tempfile.TemporaryDirectory() as tmp:
        good = romfs_with(os.path.join(tmp, "good"), make_game.ROMFS_TABLE)
        first = romfs_with(os.path.join(tmp, "first"), FIRST)
        none = romfs_with(os.path.join(tmp, "none"), None)
        missing = os.path.join(tmp, "missing")

        assert make_game.romfs_problem(good) is None
        assert make_game.romfs_problem(good, nup="game.nup") is None

        # a folder chosen by hand
        why = make_game.romfs_problem(first)
        assert first in why and FIRST in why and make_game.ROMFS_TABLE in why and "another version" in why, why
        why = make_game.romfs_problem(none)
        assert "not the game's own RomFS" in why and "0 files, 1 folders" in why, why
        assert "not the game's own RomFS" in make_game.romfs_problem(missing)

        # read from a .nup : the message names the file the player chose, not a folder of the builder's
        why = make_game.romfs_problem(first, nup="D:\\dumps\\game.nup")
        assert "D:\\dumps\\game.nup" in why and FIRST in why and make_game.ROMFS_TABLE in why, why
        assert first not in why and "update applied" in why, why
        why = make_game.romfs_problem(none, nup="game.nup")
        assert "not the game's own RomFS" in why and "game.nup" in why and none not in why, why
    print("ok: romfs_problem (6 cases)")


if __name__ == "__main__":
    main()
