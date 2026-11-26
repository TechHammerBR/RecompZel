"""A finished build leaves .hookshot_build.json in the game folder (nx2/make_game.py write_build_record): the version, the
tools and their Python, the work folder, the toolchain's switches and AMD FSR 4, which the launcher's Mods page reads to build
the folder again for a change of the mods' code patches, the same way and with nothing downloaded
(builder/HookshotBuilder/BuildRecord.cs). Game-free.

    python -I -B tests/test_build_record.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import make_game  # noqa: E402


def main():
    with tempfile.TemporaryDirectory(prefix="build-record-") as d:
        out, work = Path(d) / "game", Path(d) / "work"
        out.mkdir()
        env = {"EMSDK": "C:/tools/emsdk", "HOOKSHOT_MINGW": "C:/tools/llvm-mingw", "UNRELATED": "x"}
        with mock.patch.dict(os.environ, env, clear=False):
            make_game.write_build_record(str(out), str(work), "v9.9.9-1-gabcdef0", True)
        rec = json.loads((out / ".hookshot_build.json").read_text(encoding="utf-8"))
        assert rec["version"] == "v9.9.9-1-gabcdef0", rec
        assert Path(rec["tools"]) == ROOT and Path(rec["python"]) == Path(sys.executable), rec
        assert Path(rec["work"]) == work.resolve() or Path(rec["work"]) == Path(os.path.abspath(work)), rec
        assert rec["env"]["EMSDK"] == "C:/tools/emsdk" and rec["env"]["HOOKSHOT_MINGW"] == "C:/tools/llvm-mingw", rec
        assert "UNRELATED" not in rec["env"] and rec["fsr"] is True, rec
        assert not (out / ".hookshot_build.json.new").exists()
    src = (ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8")
    assert "write_build_record(out, work, tag, fsr_wanted(a, out))" in src, "a build no longer writes its record"
    cs = (ROOT / "builder" / "HookshotBuilder" / "BuildRecord.cs").read_text(encoding="utf-8")
    assert ".hookshot_build.json" in cs and '"tools"' in cs and '"python"' in cs and '"work"' in cs, "the launcher reads other fields"
    print("build record: written by the build with its tools, work folder and switches, read by the launcher's Rebuild")


if __name__ == "__main__":
    main()
