"""The AMD work ported from a collaborator's fork (RecompZel-main.zip, 2026-11-12) keeps its gates and guards.

AMD FSR 4 frame generation (Redstone, vk_fsr4fg.cpp), the HUD guard against ghosting (fg_hudguard.comp), the FSR 4
fixes (inverted depth, model fallback, render-size descriptions) and the game's delay (echo) effect (nn_audio.c).
None of it may leak outside its gate: an NVIDIA card must see no change unless the FSR 4 engine runs.

  * vk_temporal.cpp hands dlss_prep the inverted-depth bit (16) only when the engine is FSR 4, and keeps the
    linear-colour bit (8) gated on DLSS;
  * the menu's frame-generation method clamps to 0..3 and offers the fourth row only when fsr4fg is available;
  * vk_fsr4fg.cpp loads AMD's library with a safe search path (never the plain working directory) and only from the
    game's own fsr4fg folder;
  * the HUD guard runs after both interpolators (AMD FSR 3.1 and FSR 4);
  * the delay effect clamps its feedback under 1 (no runaway loop) and HOS_AUDIO_NO_DELAY=1 leaves it out.

python -I -B tests/test_fsr4fg_port.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    t = (ROOT / "gpu/vk/vk_temporal.cpp").read_text(encoding="utf-8")
    assert re.search(r"if \(engine\.e == fsr4_engine\(\)\) pc\.flags \|= 16;", t), \
        "vk_temporal.cpp: the inverted-depth bit is not gated on the FSR 4 engine"
    assert "temporal_linear_color() && engine.e == dlss_engine()" in t, \
        "vk_temporal.cpp: the linear-colour bit lost its DLSS gate"

    prep = (ROOT / "gpu/vk/shaders/dlss_prep.comp").read_text(encoding="utf-8")
    assert "pc.flags & 8" in prep and "pc.flags & 16" in prep, "dlss_prep.comp: a flag bit is gone (8 linear, 16 inverted depth)"

    m = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    assert "std::clamp(v, 0, 3)" in m, "vk_menu.cpp: the frame-generation method no longer clamps to 0..3"
    assert re.search(r"v == 3 && fsr4fg::available\(\)", m), "vk_menu.cpp: the FSR 4 method row is not gated on available()"

    fg = (ROOT / "gpu/vk/vk_fsr4fg.cpp").read_text(encoding="utf-8")
    assert "LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR" in fg, "vk_fsr4fg.cpp: AMD's library is not loaded with a safe search path"
    assert not re.search(r"LoadLibraryA\(", fg), "vk_fsr4fg.cpp: a plain LoadLibraryA searches the working directory"
    assert "fsr4fg" in fg, "vk_fsr4fg.cpp: the library no longer comes from the game's fsr4fg folder"

    fgen = (ROOT / "gpu/vk/vk_framegen.cpp").read_text(encoding="utf-8")
    assert fgen.count("fg.hudguard, {{fg.frames[cur ^ 1].view") >= 2, \
        "vk_framegen.cpp: the HUD guard does not run after both interpolators"

    a = (ROOT / "host/nn_audio.c").read_text(encoding="utf-8")
    assert re.search(r"fminf\(fmaxf\(dl->feedback, 0\.0f\), 0\.9[0-9]f\)", a), "nn_audio.c: the delay's feedback is not clamped under 1"
    assert 'getenv("HOS_AUDIO_NO_DELAY")' in a, "nn_audio.c: no HOS_AUDIO_NO_DELAY switch"

    docs = (ROOT / "docs/development.md").read_text(encoding="utf-8")
    assert "HOS_AUDIO_NO_DELAY" in docs, "docs/development.md: no HOS_AUDIO_NO_DELAY row"
    print("AMD port: the gates, the safe library load, the HUD guard and the delay clamps hold")


if __name__ == "__main__":
    main()
