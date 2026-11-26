"""The Linux Builder's AMD FSR 4 tick (builder/linux/hookshot_builder.py). The game and make_game.py had FSR 4 on Linux
(--fsr, AMD's amd_fidelityfx_upscaler_vk.so from the game folder), but the Linux Builder offered no tick, so it was only
reachable from the command line (players, 2026-11-15: "the checkbox hasn't appeared on Hookshot"). Checks, without Tk:

- fsr_args: --fsr when ticked; an update whose tick was not changed passes nothing (the folder's mark decides); one unticked
  here passes --no-fsr. folder_has_fsr reads make_game.py's FSR_MARK;
- the window has the tick, remembers it, and both the build and the update pass fsr_args; a changed tick offers Update.

python -I -B tests/test_linux_builder_fsr.py
"""
import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "builder" / "linux" / "hookshot_builder.py"
spec = importlib.util.spec_from_file_location("make_game_fsr", ROOT / "nx2" / "make_game.py")
make_game = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_game)

TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
FUNCS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}
NS = {"os": os, "make_game": make_game}
exec(compile(ast.Module(body=[FUNCS["folder_has_fsr"], FUNCS["fsr_args"]], type_ignores=[]), str(SOURCE), "exec"), NS)
folder_has_fsr, fsr_args = NS["folder_has_fsr"], NS["fsr_args"]
TEXT = SOURCE.read_text(encoding="utf-8")


def method(name):
    builder = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "Builder")
    m = next(n for n in builder.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(TEXT, m)


class FsrTick(unittest.TestCase):
    def test_args(self):
        self.assertEqual(fsr_args(True), ["--fsr"])
        self.assertEqual(fsr_args(False), ["--no-fsr"])
        self.assertEqual(fsr_args(True, toggled=False), [])
        self.assertEqual(fsr_args(False, toggled=False), [])

    def test_folder_mark(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(folder_has_fsr(d))
            Path(d, make_game.FSR_MARK).write_text("")
            self.assertTrue(folder_has_fsr(d))
        self.assertFalse(folder_has_fsr(""))

    def test_the_window_offers_and_passes_it(self):
        self.assertIn('ttk.Checkbutton(options, text="AMD FSR 4", variable=self.fsr, command=self.on_fsr_changed', TEXT)
        self.assertIn('self.fsr = tk.BooleanVar(value=self.cfg.get("fsr", "0") == "1")', TEXT)
        self.assertIn('self.cfg["fsr"] = "1" if self.fsr.get() else "0"', method("on_fsr_changed"))
        self.assertIn("fsr_args(True)", method("build"))
        self.assertIn('fsr_args(bool(self.fsr.get()), getattr(self, "fsr_toggled", False))', method("start_make_update"))
        mode = method("apply_mode")
        self.assertIn("folder_has_fsr(expanded)", mode)
        self.assertIn('if self.mode == "up-to-date" and (dlss_changed or fsr_changed):', mode)
        self.assertIn("amd_fidelityfx_upscaler_vk.so", TEXT)   # (the file the game looks for, gpu/vk/vk_fsr4.cpp kLoader)
        self.assertIn('kLoader = "amd_fidelityfx_upscaler_vk.so"', (ROOT / "gpu/vk/vk_fsr4.cpp").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
