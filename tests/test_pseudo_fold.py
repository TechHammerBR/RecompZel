"""RX_VK_FOLD_PSEUDO=1 folds the constant extracts and logic ops that carry zero/sign flags, and the flags get the right value (default off).

Builds the real IR (frontend/ir/*.cpp) and runs ConstantPropagationPass over R2P-shaped chains: with the switch on the extract, its
zero/sign flags and what consumes them (LogicalNot, Select, a further XOR) all become immediates, a flag is what the SPIR-V back end
would have made of the result (zero: == 0; sign: < 0 as signed), instructions of registers keep their flags; with it off nothing
that carries a flag folds, as before. The switch keeps a name the program cache's stamp covers (vk_shader.cpp).

python -I -B tests/test_pseudo_fold.py [--cxx g++]   (uses the compat headers of gpu/vk/compat and gpu/compat; no boost or fmt needed)
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDEN = ROOT / "gpu/vk/eden"
SR = EDEN / "shader_recompiler"


def check_source():
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    if '"RX_VK_FOLD"' not in shader:
        raise SystemExit("the program cache's stamp no longer covers the RX_VK_FOLD names")
    cp = (SR / "ir_opt/constant_propagation_pass.cpp").read_text(encoding="utf-8")
    for needle in ('getenv("RX_VK_FOLD_PSEUDO")', "FoldWhenAllImmediatesWithFlags(inst, [](s32 base, u32 shift, u32 count)",
                   "FoldWhenAllImmediatesWithFlags(inst, [](u32 base, u32 shift, u32 count)"):
        if needle not in cp:
            raise SystemExit("constant_propagation_pass.cpp no longer has: " + needle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    sources = [SR / "frontend/ir" / n for n in ("basic_block.cpp", "condition.cpp", "ir_emitter.cpp", "microinstruction.cpp",
                                                 "opcodes.cpp", "patch.cpp", "type.cpp", "value.cpp")]
    sources += [SR / "ir_opt/constant_propagation_pass.cpp"]
    with tempfile.TemporaryDirectory(prefix="pseudo-fold-") as tmp:
        exe = Path(tmp) / "t"
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-w", "-I", str(EDEN), "-I", str(ROOT / "gpu/vk/compat"),
                        "-I", str(ROOT / "gpu/compat"), str(ROOT / "tests/test_pseudo_fold.cpp"),
                        *map(str, sources), "-o", str(exe)], check=True)
        for mode in ("off", "on"):
            subprocess.run([str(exe), mode], check=True)


if __name__ == "__main__":
    main()
