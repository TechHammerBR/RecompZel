"""RX_VK_DLSS_LINEAR: NVIDIA DLSS can take linear scene light, as NX2navi feeds it (runtime/vk_dlaa.c, MIT).

The chain feeds the engines the network's perceptual colour (the square root of the scene's tonemapped light) and squares
the output back. Averaging in that space darkens blended edges against a bright sky: the halo on the castle wall and the
dark rim on the moss of the 2026-11-11 report. With RX_VK_DLSS_LINEAR=1, dlss_prep squares the colour on the way in
(pc.flags bit 3), vk_dlss.cpp creates the feature with IsHDR and AutoExposure, and dlss_out passes the engine's linear
output through (pc.linear_in). Only DLSS reads it; FSR 4 and the Upscaler-Off stretch keep the perceptual colour.

The sources carry the switch and the checked-in SPIR-V matches its push-constant layout:
  * dlss_prep.comp squares the colour under pc.flags bit 3; its push constant block stays 84 bytes (flags at 80);
  * dlss_out.comp skips its squaring under pc.linear_in, at offset 8 (the pipeline's 12-byte range);
  * vk_temporal.cpp makes the out pipeline with a 12-byte range, pushes 3 ints at both dispatches, and sets bit 3 only
    when the engine is DLSS; the stretch path pushes 0;
  * vk_dlss.cpp ORs IsHDR and AutoExposure into the create flags under temporal_linear_color().

python -I -B tests/test_dlss_linear.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu/vk"


def pc_offsets(header):
    """The member offsets of each Offset-decorated struct in a SPIR-V --vn header (id -> sorted offsets)."""
    text = header.read_text(encoding="utf-8")
    w = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]{8}", text[text.index("{"):])]
    assert w[0] == 0x07230203, f"{header.name}: not SPIR-V"
    offsets = {}
    i = 5
    while i < len(w):
        n, op = w[i] >> 16, w[i] & 0xFFFF
        assert n > 0, f"{header.name}: bad instruction at word {i}"
        if op == 72 and w[i + 3] == 35:   # OpMemberDecorate ... Offset <byte>
            offsets.setdefault(w[i + 1], []).append(w[i + 4])
        i += n
    return {k: sorted(v) for k, v in offsets.items()}


def main():
    prep = (VK / "shaders/dlss_prep.comp").read_text(encoding="utf-8")
    assert "pc.flags & 8" in prep and "l * l" in prep, "dlss_prep.comp: no linear-colour branch under flags bit 3"
    out = (VK / "shaders/dlss_out.comp").read_text(encoding="utf-8")
    assert "int linear_in;" in out, "dlss_out.comp: no linear_in in the push constant block"
    assert "if (pc.linear_in == 0) c *= c;" in out, "dlss_out.comp: the squaring is not gated on linear_in"

    po = pc_offsets(VK / "shaders/dlss_prep_comp_spv.h")
    assert [0, 64, 72, 80] in po.values(), f"dlss_prep_comp_spv.h: push constant offsets {po} (expected 0, 64, 72, 80)"
    oo = pc_offsets(VK / "shaders/dlss_out_comp_spv.h")
    assert [0, 8] in oo.values(), f"dlss_out_comp_spv.h: push constant offsets {oo} (expected 0, 8: a 12-byte block)"

    t = (VK / "vk_temporal.cpp").read_text(encoding="utf-8")
    assert re.search(r"DLSS_OUT_COMP_SPV, out_types, 2, 12,", t), "vk_temporal.cpp: the out pipeline's range is not 12 bytes"
    assert "const int32_t pc[3] = {(int32_t)ow, (int32_t)oh, 0};" in t, "vk_temporal.cpp: the stretch path must push 0"
    assert re.search(r"opc\[3\] = \{\(int32_t\)ow, \(int32_t\)oh, lin_color \? 1 : 0\}", t), \
        "vk_temporal.cpp: the engine path does not pass linear_in"
    assert "temporal_linear_color() && engine.e == dlss_engine()" in t, "vk_temporal.cpp: linear colour is not gated on DLSS"
    assert re.search(r"lin_color \? 8 : 0", t), "vk_temporal.cpp: dlss_prep does not get flags bit 3"
    assert 'getenv("RX_VK_DLSS_LINEAR")' in t, "vk_temporal.cpp: no RX_VK_DLSS_LINEAR"

    d = (VK / "vk_dlss.cpp").read_text(encoding="utf-8")
    m = re.search(r"if \(temporal_linear_color\(\)\)\s*\n\s*cp\.InFeatureCreateFlags \|= "
                  r"NVSDK_NGX_DLSS_Feature_Flags_IsHDR \| NVSDK_NGX_DLSS_Feature_Flags_AutoExposure;", d)
    assert m, "vk_dlss.cpp: IsHDR and AutoExposure are not set under temporal_linear_color()"

    docs = (ROOT / "docs/development.md").read_text(encoding="utf-8")
    assert "RX_VK_DLSS_LINEAR" in docs, "docs/development.md: no RX_VK_DLSS_LINEAR row"
    print("DLSS linear colour: the switch, the SPIR-V layouts and the gates hold")


if __name__ == "__main__":
    main()
