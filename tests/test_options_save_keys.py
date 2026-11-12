"""The options file does not collect a copy of every key the menu writes outside its rows.

save() (gpu/vk/vk_menu.cpp) keeps the lines of the old file that the menu does not write (pad_, key_, discord_app_id=...) and
writes them again after its own. A key it writes itself but does not count as its own is kept and written a second time at every
save: memory_budget was one, and a hookshot_options.ini had 152 lines of it, two more per session.

Every key the function writes with a literal name must be among those the filter drops ("mine"), apart from the ones kept on purpose
(pad_ and key_, which have their own branch).

python -I -B tests/test_options_save_keys.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    source = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    save = block(source, "void save() {")
    mine = re.search(r"bool mine = ([^;]+);", save)
    assert mine, "save(): no 'mine' filter"
    dropped = set(re.findall(r'key == "([a-z_0-9]+)"', mine.group(1)))

    written = set(re.findall(r'fprintf\(f, "([a-z_0-9]+)=', save))
    written -= {"pad_%s", "key_%s"}   # (format names: the controls have their own branch)
    written = {k for k in written if "%" not in k}
    assert written, "save(): no literal key found: the test is out of date"
    missing = sorted(written - dropped)
    assert not missing, f"save() writes {missing} but keeps the old line too: it is added again at every save"
    for key in ("memory_budget", "microphone_device", "options_version"):
        assert key in written, f"save() no longer writes {key}: update this test"
    print("options save: every key the menu writes is dropped from the old file:", ", ".join(sorted(written)))


if __name__ == "__main__":
    main()
