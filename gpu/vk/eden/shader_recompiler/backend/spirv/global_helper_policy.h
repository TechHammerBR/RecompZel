// (hookshot, stream P4) Whether a mesh program's global-memory helpers stay inline. Pure: tests/test_global_helper_policy.py.
//
// The helpers (spirv_emit_context.cpp, DefineGlobalMemoryFunctions) search every candidate storage buffer at each access that
// was left global, and are inlined in task and mesh stages (issue 994). On OoT's biggest mesh program (43ec86f35fd937b9: 44.9 k
// SPIR-V instructions, 77 helper calls) the inlined copies are what NVIDIA runs from the edge of its instruction cache: left out
// of line it takes 1.34 ms where it took 2.43 (G3, RTX 3050, Kokiri), while the small mesh programs (8-14 k instructions, the same
// 70-77 calls) lose 0.04-0.4 ms out of line and gain 0.4-0.5 ms from RX_VK_MESH_G3's hoisted ranges. So the choice is the
// program's size, not the helper's: RX_VK_MESH_NOINLINE_ABOVE=<n> leaves the helpers out of line, and the ranges unhoisted,
// in a mesh stage whose IR has more than n instructions. Unset or 0: never (the default). A name under RX_VK_MESH, so the program
// cache's stamp has it.
#pragma once

#include <cstdint>
#include <cstdlib>

namespace Shader::Backend::SPIRV {

/// The limit a switch's text names: a decimal number of IR instructions; empty, unset, zero, negative or not a number: 0 (off)
inline std::uint32_t NoInlineAbove(const char* text) {
    if (!text || !*text) {
        return 0;
    }
    char* end{};
    const long long value{std::strtoll(text, &end, 10)};
    if (end == text || *end != '\0' || value <= 0 || value > 0xFFFFFFFFll) {
        return 0;
    }
    return static_cast<std::uint32_t>(value);
}

/// True when the stage's helpers are left out of line: a mesh stage over the limit
inline bool LeaveHelpersOutOfLine(bool mesh_stage, std::uint32_t ir_instructions, std::uint32_t limit) {
    return mesh_stage && limit != 0 && ir_instructions > limit;
}

} // namespace Shader::Backend::SPIRV
