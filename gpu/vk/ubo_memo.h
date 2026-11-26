// (Hookshot, HL_UBO_MEMO) The user-uniform slot memo: what a draw's descriptor build answered for one uniform slot (a stage and an
// index) is kept per thread, and answered again while nothing that decided it moved. No Vulkan, no NvnState: the key and the entry
// only, so tests/ubo_slot_memo_test.cpp can drive them with a made-up world.
//
// What decides an answer (vk_draw.cpp `uniform_range`, the user-uniform branch), and so is in the key:
//   addr, n   the bound range, and the size the program reads of it
//   stamp     gpu_bind_stamp(): pools leaving, a mirror made, the next submission (what `gpu_buffer_bind`'s own memo is keyed by)
//   epoch     the stream's uniform-update list's epoch, and limit the thread's place in it (`ub_view`): whether an update overlaps
//             the range is a function of the list as this thread sees it
//   seg       the parallel replay's segment (a mirror's sync stands for the segments after it)
// An entry is made only from an answer that was the pool's buffer itself (no overlay copy, no inline bytes, no stream copy).
#pragma once
#include <cstdint>

namespace mkwvk::ubomemo {

struct Key {
    uint64_t addr = 0, n = 0, stamp = 0, epoch = 0, limit = 0, seg = 0;
    bool operator==(const Key& o) const {
        return addr == o.addr && n == o.n && stamp == o.stamp && epoch == o.epoch && limit == o.limit && seg == o.seg;
    }
};

struct Entry {
    Key key;
    uint64_t a = 0, b = 0;   // the answer: a buffer handle and an offset
    bool on = false;
    bool hit(const Key& k, uint64_t* out_a, uint64_t* out_b) const {
        if (!on || !(key == k)) return false;
        *out_a = a, *out_b = b;
        return true;
    }
    void store(const Key& k, uint64_t va, uint64_t vb) {
        key = k, a = va, b = vb, on = true;
    }
    void drop() { on = false; }
};

/// The key to make an entry with, given the epoch read before the answer was computed and the one read after: a list that changed
/// meanwhile (another thread's append or a prune) means the answer may not stand, so no entry is made
inline bool storable(uint64_t epoch_before, uint64_t epoch_after) {
    return epoch_before == epoch_after;
}

}  // namespace mkwvk::ubomemo
