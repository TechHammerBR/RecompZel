"""A mesh stage over RX_VK_MESH_NOINLINE_ABOVE IR instructions keeps its global-memory helpers out of line (default off).

The decision (gpu/vk/eden/shader_recompiler/backend/spirv/global_helper_policy.h) is compiled and run on its own against a
table: the switch's text, off by default, mesh stages only, over the limit only. The source is checked to use it where the
helpers are made: the load helpers' inline flag and the hoisted ranges both stand down for such a stage, the program's IR
instructions are counted before the helpers are made, and the switch keeps a name the program cache's stamp covers.

python -I -B tests/test_global_helper_policy.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPIRV = ROOT / "gpu/vk/eden/shader_recompiler/backend/spirv"
RECOMPILER = ROOT / "gpu/vk/eden"


def check_source():
    ctx = (SPIRV / "spirv_emit_context.cpp").read_text(encoding="utf-8")
    header = (SPIRV / "spirv_emit_context.h").read_text(encoding="utf-8")
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    for needle in ('getenv("RX_VK_MESH_NOINLINE_ABOVE")',
                   "LeaveHelpersOutOfLine(stage == Stage::Mesh, ir_instruction_count, noinline_above)",
                   "g3_hoist && !big_mesh",
                   "const bool noinline_here{big_mesh ||",
                   "ir_instruction_count += static_cast<u32>(block->size());"):
        if needle not in ctx:
            raise SystemExit("spirv_emit_context.cpp no longer has: " + needle)
    if ctx.index("ir_instruction_count += ") > ctx.index("DefineGlobalMemoryFunctions(program.info);"):
        raise SystemExit("the IR is counted after the helpers are made")
    if "u32 ir_instruction_count" not in header:
        raise SystemExit("spirv_emit_context.h lost ir_instruction_count")
    if '"RX_VK_MESH"' not in shader:
        raise SystemExit("the program cache's stamp no longer covers the RX_VK_MESH names")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="global-helper-policy-") as tmp:
        exe = Path(tmp) / "policy"
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(RECOMPILER / "shader_recompiler" / ".."),
                        "-I", str(RECOMPILER), str(ROOT / "tests/test_global_helper_policy.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
