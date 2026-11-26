// The policy of the mesh stages' global-memory helpers (gpu/vk/eden/shader_recompiler/backend/spirv/global_helper_policy.h).
#include <cstdio>
#include <cstdint>
#include <cstdlib>

#include "shader_recompiler/backend/spirv/global_helper_policy.h"

using namespace Shader::Backend::SPIRV;

static int failures = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL line %d: %s\n", __LINE__, #x); ++failures; } } while (0)

int main() {
    // the switch's text
    CHECK(NoInlineAbove(nullptr) == 0);
    CHECK(NoInlineAbove("") == 0);
    CHECK(NoInlineAbove("0") == 0);
    CHECK(NoInlineAbove("-5") == 0);
    CHECK(NoInlineAbove("abc") == 0);
    CHECK(NoInlineAbove("12x") == 0);
    CHECK(NoInlineAbove("30000") == 30000u);
    CHECK(NoInlineAbove("4294967295") == 4294967295u);
    CHECK(NoInlineAbove("4294967296") == 0);   // (past 32 bits: off, not a wrapped small limit)

    // off by default: no limit, no stage is left out of line, whatever its size
    CHECK(!LeaveHelpersOutOfLine(true, 1000000, 0));
    // only mesh stages
    CHECK(!LeaveHelpersOutOfLine(false, 1000000, 100));
    // a mesh stage: over the limit only (the limit itself stays inline)
    CHECK(LeaveHelpersOutOfLine(true, 30001, 30000));
    CHECK(!LeaveHelpersOutOfLine(true, 30000, 30000));
    CHECK(!LeaveHelpersOutOfLine(true, 8000, 30000));
    // G3's programs at a limit between them: the big one out of line (43ec86f35fd937b9, 44.9 k SPIR-V), the others inline
    const std::uint32_t limit = 30000;
    CHECK(LeaveHelpersOutOfLine(true, 44883, limit));
    CHECK(!LeaveHelpersOutOfLine(true, 9365, limit));    // 4f0c0b40ab3a32cd
    CHECK(!LeaveHelpersOutOfLine(true, 12693, limit));   // 3b8c07f2eb4bb7d9
    if (failures) {
        return 1;
    }
    std::printf("global_helper_policy: ok\n");
    return 0;
}
