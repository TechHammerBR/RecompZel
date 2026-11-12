// (recompzel) What the texture cache may hold, given the card's memory and the host's commit (vk_texture.cpp texture_frame; tests/
// test_host_commit.py runs these rules without a game or a GPU).
//
// Windows charges a card's memory to the system's commit limit (RAM plus the page files) like any other memory, since each
// allocation has a backing store there. Logs of the same game on two PCs show it: the process's working set grew about 0.7 to 1.1 MB
// for each MB of textures held, and the commit about 1.8 MB. On a 16 GB card with a 12 GB texture budget the driver's count went to
// 98% of what it allows, the card's memory spilled into RAM, the median frame rate fell from 96 to 40 fps and the system's RAM use
// to 55 GB. The idea, and the 2 GiB reserve and the 3 GiB floor, are Fritchii v5.7's (host_memory_limit.h, GPL-3.0-or-later,
// a port of zortos293/Lichii#1210): the cache holds no more than the commit the system can still hand out. The ceiling by the card's
// own memory is ours.
#pragma once

#include <algorithm>
#include <cstdint>

namespace host_commit {

/// Commit left to the rest of the process and the system
constexpr uint64_t kReserve = 2ull << 30;

/// The cache is not shrunk below this for the host's commit: a scene needs about this much, and under it the collector only
/// deletes and decodes the same textures again
constexpr uint64_t kFloor = 3ull << 30;

/// The most textures one budget may ask for on a card the driver lets the game `allowed` bytes of: half of it, because the rest holds
/// render targets, buffers and pipelines (3.8 to 6.8 GB in the 4080's log), and never less than 6 GB, the engine's own default
/// cap, so that no smaller card's budget or preset is touched
constexpr uint64_t kCeilingFloor = 6144ull << 20;
inline uint64_t ceiling(uint64_t allowed) { return std::max(allowed / 2, kCeilingFloor); }

/// The textures the cache may hold as the host's commit allows: what it holds now (`held`) and the commit the system can still hand
/// out (`room`), less the reserve, and never less than the floor. Below the reserve the result is under what it holds, and the
/// cache gives the difference back
inline uint64_t commit_cap(uint64_t held, uint64_t room) {
    const uint64_t all = held + room;
    return std::max(all - std::min(all, kReserve), kFloor);
}

}  // namespace host_commit
