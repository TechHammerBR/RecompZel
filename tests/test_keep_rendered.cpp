// keep_rendered::presents (gpu/vk/keep_rendered.h): how long an unused texture the GPU drew is kept. tests/test_keep_rendered.py
#include "../gpu/vk/keep_rendered.h"

#include <cstdio>
#include <cstdlib>

static int failures = 0;
static void expect(bool ok, const char* what) {
    if (!ok) {
        std::printf("FAIL: %s\n", what);
        failures++;
    }
}

int main() {
    const uint64_t MB = 1ull << 20;
    const uint64_t allowed = 7244 * MB;   // (an 8 GB RX 7700S)
    using keep_rendered::presents;
    expect(presents(false, 0, 0) == 3600, "unknown use: a minute");
    expect(presents(true, 3000 * MB, allowed) == 3600, "far from the limit: a minute");
    expect(presents(true, allowed / 100 * 96, allowed) == 3600, "under 97%: a minute");
    expect(presents(true, allowed / 100 * 97, allowed) == 600, "at 97%: 600");
    expect(presents(true, allowed, allowed) == 600, "AMD's report clamped at what it allows: 600");
    expect(presents(true, allowed + 600 * MB, allowed) == 600, "past it: 600");
    if (failures) return EXIT_FAILURE;
    std::printf("keep rendered: all checks passed\n");
    return EXIT_SUCCESS;
}
