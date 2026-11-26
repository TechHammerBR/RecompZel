// (hookshot, stream P5) Folding an instruction of immediates that has pseudo-operations (flags) attached. Pure: tests/test_pseudo_fold.py.
//
// R2P (frontend/maxwell/translate/impl/move_register_to_predicate.cpp) gives every BitFieldExtract of a constant mask a GetZeroFromOp,
// and the constant propagation pass never folded an instruction that had an associated pseudo-operation: 1.89 M constant-foldable
// operations of the program cache stayed (8.7 k of the 44.9 k instructions of the biggest mesh program), with the IEqual / Select /
// LogicalNot chains that hang on them. The fold here gives the flag pseudo-operations (zero, sign) their value, as the SPIR-V back end
// would have made it from the folded result (emit_spirv_integer.cpp: zero = result == 0, sign = result < 0 as signed), and then the
// instruction folds as any other. RX_VK_FOLD_PSEUDO=1 (default off); a name the program cache's stamp covers (vk_shader.cpp).
#pragma once

#include <cstdint>
#include <cstdlib>

namespace Shader::Optimization {

/// The switch's text: on for a number other than 0; unset, empty or anything else: off
inline bool FoldPseudoEnabled(const char* text) {
    if (!text || !*text) {
        return false;
    }
    char* end{};
    const long value{std::strtol(text, &end, 10)};
    return end != text && *end == '\0' && value != 0;
}

/// The zero flag of a 32-bit result (what the back end's OpIEqual(result, 0) says)
constexpr bool ZeroFlagOf(std::uint32_t result) {
    return result == 0;
}

/// The sign flag of a 32-bit result (what the back end's OpSLessThan(result, 0) says)
constexpr bool SignFlagOf(std::uint32_t result) {
    return static_cast<std::int32_t>(result) < 0;
}

} // namespace Shader::Optimization
