// Game-free regression for the Ampere -> Maxwell lowering's register renaming (lower_to_maxwell.h): a renamed high GPR's
// marker must not be a number another field of the same instruction names. OoT's Castle Town flower colour pass had
// FMUL R252, R216, c[..] (native 864 of mesh code e3fc8fcf540f7a48): R252 took R216 as its marker, the prefix mapped
// R216 to both 252 and 216, the product went to R216 and R252 stayed undefined: the flowers' vertices broke and they
// glowed with the sky colour left behind.
//   clang++ -std=c++20 -I gpu/vk/eden -I gpu/vk/compat gpu/vk/tests/regmap_marker_test.cpp -o regmap_marker_test
#include <cstdio>
#include <map>

#include "shader_recompiler/frontend/ampere/lower_to_maxwell.h"

namespace {
using Shader::Ampere::Instruction;

// Numbers mapped to two different targets by the prefixes before one lowered word.
int collisions(const Shader::Ampere::LoweredProgram& lowered) {
    int bad = 0;
    std::map<u32, u32> current;
    for (const u64 w : lowered.instructions) {
        if ((w >> 48) != 0xefe0) {
            current.clear();
            continue;
        }
        const u32 runs = static_cast<u32>((w >> 40) & 3);
        constexpr u32 number_at[2]{0, 20}, target_at[2]{8, 28};
        for (u32 i = 0; i < runs && i < 2; ++i) {
            const u32 number = static_cast<u32>((w >> number_at[i]) & 0xff);
            const u32 target = static_cast<u32>((w >> target_at[i]) & 0xff);
            const u32 length = static_cast<u32>((w >> (36 + 2 * i)) & 3) + 1;
            for (u32 k = 0; k < length; ++k) {
                const auto it = current.find(number + k);
                if (it != current.end() && it->second != target + k) bad++;
                current[number + k] = target + k;
            }
        }
    }
    return bad;
}
// UR36 puts the first reserved register at R206. A load into R204 needs a
// prefix for R206-R207 only when it writes all four destination registers.
bool check_load_width(u32 size, bool uniform_address) {
    using namespace Shader::Ampere;
    const Instruction load = uniform_address
        ? Instruction{{0xffcc7981, 0, 0x081e8100U | (size << 9), 0x000fe200}}  // LDG.E R204, [UR0]
        : Instruction{{0x08cc7381, 0, 0x001e8100U | (size << 9), 0x000fe200}}; // LDG.E R204, [R8]
    const Instruction program[] = {
        {{0x00247ab9, 0x0001e400, 0x00000a00, 0x000fe200}},  // ULDC.64 UR36
        load,
        {{0x0000794d, 0, 0x03800000, 0x000fea00}},  // EXIT
    };
    const auto lowered = LowerToMaxwell(program);
    if (!lowered) return false;
    const u32 first = lowered.source_instruction_offsets[1];
    const u32 end = lowered.source_instruction_offsets[2];
    if (size != 6) return end == first + 1;
    const RegisterRun upper_pair{206, 206, 2};
    return end == first + 2 && lowered.instructions[first] == RegisterMapPrefix(&upper_pair, 1);
}
}  // namespace

int main() {
    const Instruction program[] = {
        {{0x00047ab9, 0x0001e400, 0x00000a00, 0x000fe200}},   // ULDC.64 UR4, c[0x0][0x1e4] (the uniform bank: high GPRs from R216)
        {{0xd8fc7a20, 0x00cc0c00, 0x00410000, 0x000fe200}},   // FMUL R252, R216, c[0x3][0x30]
        {{0x0000794d, 0x00000000, 0x03800000, 0x000fea00}},   // EXIT
    };
    const auto lowered = Shader::Ampere::LowerToMaxwell(std::span<const Instruction>(program, 3));
    int failures = 0;
    if (!lowered) {
        std::fprintf(stderr, "not lowered: %.*s\n", static_cast<int>(lowered.error.size()), lowered.error.data());
        failures++;
    } else if (!lowered.register_map_words) {
        std::fprintf(stderr, "no extended registers: the case is not exercised\n");
        failures++;
    } else if (const int bad = collisions(lowered)) {
        std::fprintf(stderr, "%d register numbers mapped to two registers in one prefix\n", bad);
        failures++;
    }
    for (const bool uniform_address : {false, true}) {
        for (const u32 size : {4U, 5U, 6U}) {
            if (!check_load_width(size, uniform_address)) {
                std::fprintf(stderr, "incorrect register map for %u-bit LDG R204, [%s]\n",
                             32U << (size - 4), uniform_address ? "UR0" : "R8");
                failures++;
            }
        }
    }
    std::printf("%s\n", failures ? "FAILED" : "ok");
    return failures ? 1 : 0;
}
