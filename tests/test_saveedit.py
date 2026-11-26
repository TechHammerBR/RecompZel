"""The launcher's save editor backend (nx2/saveedit/server.py), game-free: a made-up save account (progress.sav and caption.sav
in the game's format, with hearts, rupees and a story flag) in a made-up game folder, then requests over the server's
stdin/stdout as the launcher sends them: the account and its slot are listed, the slot opens, hearts and rupees are set (within
their limits, out of them refused), a flag is turned on, nothing is written before "save", and "save" writes both files after
copying the old ones to save-backups.

    python -I -B tests/test_saveedit.py
"""
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2" / "saveedit"))
import nxsave  # noqa: E402

TYPES = nxsave.TYPES


def save_file(entries):
    """A save file: entries (name, type, value) of inline types (Bool, Int, UInt), grouped by type as the game writes them"""
    by_type = {}
    for name, t, v in entries:
        by_type.setdefault(t, []).append((nxsave.murmur3(name.encode()) if isinstance(name, str) else name, v))
    table = b""
    for t, items in by_type.items():
        table += struct.pack("<II", 0, TYPES.index(t))
        for h, v in items:
            table += struct.pack("<Ii", h, int(v)) if t == "Int" else struct.pack("<II", h, int(v))
    data_off = 0x20 + len(table)
    head = struct.pack("<III", 0x01020304, 1, data_off).ljust(0x20, b"\0")
    return head + table + b"\0" * 8


def main():
    with tempfile.TemporaryDirectory(prefix="saveedit-") as d:
        game = Path(d) / "game"
        slot = game / "user" / "save" / "0123456789abcdef0000000000000001" / "slot_00"
        slot.mkdir(parents=True)
        (slot / "progress.sav").write_bytes(save_file([
            ("PlayerStatus.Life", "Int", 12), ("PlayerStatus.MaxLife", "Int", 16),
            ("PlayerStatus.CurrentRupee", "Int", 5), (0xE0010A50, "Int", 200),   # (RupeeLimit: unnamed in the game files)
            ("HavePlayedEvent.Test", "Bool", 0)]))
        (slot / "caption.sav").write_bytes(save_file([
            ("CaptionData.Life", "Int", 12), ("CaptionData.MaxLife", "Int", 16), ("CaptionData.CurrentRupee", "Int", 5)]))
        before = (slot / "progress.sav").read_bytes()
        account = str(slot.parent)
        requests = [
            {"cmd": "accounts"},
            {"cmd": "open", "account": account, "slot": "slot_00"},
            {"cmd": "set_stat", "key": "hearts", "value": "2.75"},
            {"cmd": "set_stat", "key": "hearts", "value": "9"},          # (more than the containers: refused)
            {"cmd": "set_stat", "key": "rupees", "value": "150"},
            {"cmd": "set_stat", "key": "rupees", "value": "201"},        # (more than the wallet holds: refused)
            {"cmd": "entries", "search": "#"},
            {"cmd": "save"},
        ]
        out = subprocess.run([sys.executable, "-I", str(ROOT / "nx2" / "saveedit" / "server.py"), "--game", str(game)],
                             input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
        answers = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
        assert len(answers) == len(requests), (answers, out.stderr)
        acc, opened, hearts, too_many, rupees, too_rich, entries, saved = answers
        assert acc["ok"] and acc["accounts"][0]["slots"][0]["hearts"] == "3 / 4", acc
        assert opened["ok"], opened
        assert hearts["ok"] and hearts["hearts"] == 2.75 and hearts["edited"] == 2, hearts   # (progress.sav and caption.sav)
        assert not too_many["ok"] and "0 to 4" in too_many["error"], too_many
        assert rupees["ok"] and rupees["rupees"] == 150, rupees
        assert not too_rich["ok"] and "0 to 200" in too_rich["error"], too_rich
        assert entries["ok"] and entries["entries"], entries
        assert (slot / "progress.sav").read_bytes() == before or saved["ok"], "written before save"
        assert saved["ok"] and saved["written"] == 2, saved
        backups = list((game / "save-backups").rglob("*.sav"))
        assert sorted(p.name for p in backups) == ["caption.sav", "progress.sav"], backups
        assert backups[0].read_bytes() != b"" and (slot.parent / "slot_00" / "progress.sav").read_bytes() != before
        sf = nxsave.SaveFile(slot / "progress.sav")
        by = {e.hash: e.value for e in sf.entries}
        assert by[nxsave.murmur3(b"PlayerStatus.Life")] == 11 and by[nxsave.murmur3(b"PlayerStatus.CurrentRupee")] == 150, by
        cap = {e.hash: e.value for e in nxsave.SaveFile(slot / "caption.sav").entries}
        assert cap[nxsave.murmur3(b"CaptionData.Life")] == 11 and cap[nxsave.murmur3(b"CaptionData.CurrentRupee")] == 150, cap
    print("save editor: accounts, open, hearts and rupees in and out of range, save with backups")


if __name__ == "__main__":
    main()
