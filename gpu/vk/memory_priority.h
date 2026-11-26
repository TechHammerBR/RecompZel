// SPDX-License-Identifier: GPL-3.0-or-later
// (hookshot) VK_EXT_memory_priority's rule (RX_VK_MEMORY_PRIORITY, off by default), apart from Vulkan so that
// tests/test_memory_priority.py can run it.
//
// When other programs hold VRAM, or the card is too small for what is loaded, the system moves part of the game's device memory
// out of VRAM (Windows: to shared memory, which the GPU reads over PCIe). It chooses what goes. The priority given with each
// vkAllocateMemory, 0 to 1, is the one say the game has: memory with a higher one "may be more likely to stay in device-local
// memory" (the extension's words; a driver may ignore it). Left alone everything has 0.5.
//
// The rule: the render targets' memory, written and read every frame, above everything; the sampled textures', the largest
// part and the one the cache already lets go of first, below everything; the rest (buffers, DLSS's and the frame
// interpolation's images, the scratch ones) where it was. A priority is a memory object's, so a pool's block has its pool's.
//
// Measured on one PC (an RTX 4090 on NVIDIA 621.24, Windows 11; the game standing in Hyrule Field while other processes
// took the VRAM; docs/tested/2026-11-14-memory-priority-*): the textures' lower priority looks like what helps, from one
// run each: 0.5,0.25 did as well as 1,0.25, and 1,0.5 (the render targets raised alone) lost its gain within 90 s and ended
// slower than with the switch unset. No small card has run it yet, which is why it is off.
#pragma once

#include <cmath>
#include <cstdlib>
#include <cstring>

#include "compat/hookshot_env.h"

namespace memory_priority {

struct Tiers {
    bool on = false;
    bool unread = false;   // (a <targets>,<textures> that isn't two numbers from 0 to 1: the usual two, and the log says so)
    float targets = 0.5f, textures = 0.5f, rest = 0.5f;   // (0.5: what the driver gives memory allocated without one)
};

/// One number of <targets>,<textures>, ending at `end` (the comma or the text's end, spaces before either not counted):
/// false unless it is a number from 0 to 1 and nothing else. So 0,5 meant as a half, nan, "1," and 1,0.5,0.2 are refused
inline bool number(const char* at, char end, float& out) {
    char* stop = nullptr;
    const double v = strtod(at, &stop);
    if (stop == at || !std::isfinite(v) || v < 0.0 || v > 1.0) return false;
    while (*stop == ' ' || *stop == '\t' || *stop == '\r' || *stop == '\n') stop++;
    if (*stop != end) return false;
    out = (float)v;
    return true;
}

/// RX_VK_MEMORY_PRIORITY as the environment has it. Unset, empty, 0, false, off or no: off, nothing asked of the driver.
/// 1 (or anything else): the render targets 1, the textures 0.25. <targets>,<textures>: those two instead, each from 0 to 1
/// (a test: 1,0.5 raises the render targets alone); anything else with a comma in it is not guessed at, and is `unread`
inline Tiers parse(const char* env) {
    Tiers t;
    if (!env || env_value_off(env)) return t;
    t.on = true, t.targets = 1.0f, t.textures = 0.25f;
    if (const char* comma = strchr(env, ',')) {
        float targets = 0.0f, textures = 0.0f;
        if (number(env, ',', targets) && number(comma + 1, '\0', textures)) t.targets = targets, t.textures = textures;
        else t.unread = true;
    }
    return t;
}

/// An image's: a render target's, a sampled texture's (the textures' pool's), or the rest's
inline float image(const Tiers& t, bool target, bool textures) { return target ? t.targets : textures ? t.textures : t.rest; }

}   // namespace memory_priority
