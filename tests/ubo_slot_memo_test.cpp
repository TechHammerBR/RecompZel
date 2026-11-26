// The user-uniform slot memo (gpu/vk/ubo_memo.h) against a made-up world: a lookup that is a pure function of (addr, n, stamp, epoch,
// limit, segment) and a world whose stamp, update list and segment move at random, some of them while a lookup is under way. The
// memo may skip the lookup only where the lookup would have given the same answer.
#include <cstdint>
#include <cstdio>
#include <random>

#include "../gpu/vk/ubo_memo.h"

using namespace mkwvk::ubomemo;

namespace {
struct World {
    uint64_t stamp = 1, epoch = 1, limit = 1, seg = 0;
};
// The answer the full lookup gives: any function of the key; `direct` says whether it was the pool's buffer itself (an entry is made only then)
uint64_t answer_a(const Key& k) { return k.addr * 0x9E3779B97F4A7C15ull ^ k.stamp * 31 ^ k.epoch * 131 ^ k.limit * 7 ^ k.seg; }
uint64_t answer_b(const Key& k) { return (k.addr >> 4) + k.n + k.limit; }
bool direct_of(const Key& k) { return ((k.addr >> 8) ^ k.epoch) % 5 != 0; }   // (a fifth of the ranges overlap an update: a copy, never kept)
}  // namespace

int main() {
    std::mt19937_64 rng(0xB0A7);
    constexpr int kSlots = 24;
    Entry slots[kSlots];
    World w;
    uint64_t hits = 0, misses = 0, stores = 0, dropped_moved = 0, bad = 0;
    const int kSteps = 6000000;
    for (int step = 0; step < kSteps; step++) {
        // the world moves: rarely the stamp (a new submission), the list (updates), the segment; every step one of a few ranges is looked up
        const uint64_t r = rng();
        if (r % 211 == 0) w.stamp++;
        if (r % 53 == 0) w.epoch++, w.limit++;
        if (r % 997 == 0) w.limit++;   // (a worker passing an update in its own segment)
        if (r % 1499 == 0) w.seg = (w.seg + 1) % 6;
        const int slot = (int)((r >> 20) % kSlots);
        // each slot is bound to one of a few ranges, which change now and then (a draw binds another block)
        const uint64_t pick = (r >> 32) % 7 == 0 ? (r >> 40) % 40 : (uint64_t)slot;
        const uint64_t addr = 0x1000 + pick * 0x100, n = 256 + (pick % 3) * 64;
        const Key k{addr, n, w.stamp, w.epoch, w.limit, w.seg};

        uint64_t a = 0, b = 0;
        Entry& e = slots[slot];
        const bool hit = e.hit(k, &a, &b);
        // the full lookup, always: the reference
        const uint64_t ra = answer_a(k), rb = answer_b(k);
        const bool direct = direct_of(k);
        if (hit) {
            hits++;
            if (a != ra || b != rb || !direct) bad++;   // a hit must be the full lookup's answer, and only direct answers were ever kept
            continue;
        }
        misses++;
        // another thread appends an update during the lookup, now and then
        const uint64_t epoch_after = (rng() % 41 == 0) ? w.epoch + 1 : w.epoch;
        if (direct && storable(k.epoch, epoch_after)) {
            e.store(k, ra, rb);
            stores++;
        } else {
            e.drop();
            if (direct) dropped_moved++;
        }
        if (epoch_after != w.epoch) w.epoch = epoch_after;
    }
    std::printf("ubo slot memo: %d steps, %llu hits, %llu misses, %llu stored, %llu not kept (the list moved meanwhile), %llu mismatches\n", kSteps,
                (unsigned long long)hits, (unsigned long long)misses, (unsigned long long)stores, (unsigned long long)dropped_moved,
                (unsigned long long)bad);
    if (bad || !hits || !misses || !dropped_moved) return 1;
    return 0;
}
