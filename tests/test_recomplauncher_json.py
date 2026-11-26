"""Game-free checks of recomplauncher.json: it parses, and every settings key is a row of the in-game menu.

Run with: python -I tests/test_recomplauncher_json.py
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecompLauncherJsonTests(unittest.TestCase):
    def test_settings_are_menu_rows(self):
        manifest = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["format"], 1)
        menu = (ROOT / "gpu" / "vk" / "vk_menu.cpp").read_text(encoding="utf-8")
        rows = {re.sub(" ", "_", name.lower()) for name in re.findall(r'\{TAB_[A-Z]+, "([^"]+)"', menu)}
        # (vk_menu.cpp ini_key: the rows whose key is not their name, renamed rows keeping the key an options file has:
        # output_res, resolution, upscaling, frame_rate_cap, dlss)
        ini_key = menu.split("const char* ini_key(const Row& r) {", 1)[1].split("\n}", 1)[0]
        rows |= set(re.findall(r'return "([a-z_0-9]+)";', ini_key))
        keys = {key for setting in manifest["settings"] for choice in setting["choices"] for key in choice["set"]}
        self.assertTrue(keys)
        self.assertEqual(keys - rows, set())

    def test_builds_into_the_launchers_game_folder(self):
        # (RecompLauncher issue 215: without --out the build went to ~/Games/Hookshot, not the drive the player
        # installed to. The folder it builds into is the one it plays, and the settings and saves live in it.)
        manifest = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        prepare = manifest["prepare"]["args"]
        out = prepare[prepare.index("--out") + 1]
        self.assertTrue(out.startswith("{install}/"))
        self.assertEqual(manifest["start"]["args"], ["--play", out])
        self.assertEqual(manifest["folders"]["game"][0]["path"], out)
        self.assertEqual(manifest["config"][0]["file"][0]["path"], out + "/hookshot_options.ini")
        self.assertIn(out + "/user/save", manifest["saves"])
        self.assertNotIn("{home}/Games", json.dumps(manifest))

    def test_saves_are_the_save_folders_on_both_systems(self):
        # (RecompLauncher's backups and cloud saves copy what "saves" names. Started by the launcher's Play, the game keeps
        # its saves in <user>/save: <game folder>/user on Windows, $XDG_DATA_HOME/hookshot ({local}/hookshot) on Linux. That
        # Linux folder, and %LOCALAPPDATA%\Hookshot on Windows, also hold the builder, the launcher, NVIDIA's DLSS files, the
        # NFC tags and the save backups, none of which a save copy may carry: so the save folder, never the whole data folder)
        # (save-work beside it holds a save while it is being written: the game moves it into save at Commit, host/nn_fs.c)
        manifest = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        out = manifest["folders"]["game"][0]["path"]
        windows, linux = out + "/user", "{local}/hookshot"
        self.assertEqual(manifest["saves"], [windows + "/save", windows + "/mouse_sens.txt",
                                             linux + "/save", linux + "/mouse_sens.txt"])
        self.assertIn('"%s\\\\save\\\\%016llx%016llx"', (ROOT / "host" / "nn_fs.c").read_text(encoding="utf-8"))
        main = (ROOT / "host" / "hos_main.c").read_text(encoding="utf-8")
        self.assertIn('snprintf(beside_user, MAX_PATH, "%s" SEP_S "user", dir);', main)
        self.assertIn('"/hookshot"', main)
        self.assertIn('"%s/mouse_sens.txt", hos_user_dir', (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8"))

    def test_old_save_copies_go_back_where_they_came_from(self):
        # (RecompLauncher restores a copy made before a move into the new folder at the same place in the list, only when
        # the list keeps its length. The copies made before this list name <user> itself, so a copy of <user>/save/<id>
        # would land in <user>/save/save/<id>. A list of another length restores each copy into the folders it names)
        manifest = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        before = ["{local}/hookshot", "{install}/Hookshot/user"]
        self.assertNotEqual(len(manifest["saves"]), len(before))

    def test_the_saves_button_opens_the_save_folder_there_is(self):
        manifest = json.loads((ROOT / "recomplauncher.json").read_text(encoding="utf-8"))
        out = manifest["folders"]["game"][0]["path"]
        places = manifest["folders"]["saves"]
        self.assertEqual([p.get("if") for p in places[:2]], [p["path"] for p in places[:2]])
        self.assertEqual([p["path"] for p in places], [out + "/user/save", "{local}/hookshot/save", out])

    def test_appimage_carries_it(self):
        self.assertIn('cp recomplauncher.json "$APPDIR/recomplauncher.json"',
                      (ROOT / "scripts" / "linux" / "appimage.sh").read_text(encoding="utf-8"))

    def test_windows_zip_carries_it(self):
        workflow = (ROOT / ".github" / "workflows" / "windows-builder.yml").read_text(encoding="utf-8")
        self.assertIn('z.write("recomplauncher.json", "recomplauncher.json")', workflow)
        self.assertIn("dist/RecompZel-*-Windows-x64.zip", workflow)


if __name__ == "__main__":
    unittest.main()
