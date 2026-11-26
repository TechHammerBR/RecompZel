// (hookshot) A mark per 4 KB page that is set and never taken off, read without a lock: whether anything of a kind ever
// touched a page. invalidate_quick (vk_replay.cpp) reads two of them on the game's thread with its virtual core held: the
// pages a write-back of GPU results ever landed on (vk_memory.cpp wb_pages_note) and the pages of a texture the GPU wrote
// that was ever listed for its texels' write-back (vk_texture.cpp vw_note). A range with neither has nothing in it that
// invalidate waits for. Kept apart so the marks are checked without the renderer (tests/test_invalidate_quick.py).
//
// The order: a writer marks with a release before it lets go of the lock under which it notes what the mark stands for, and
// a reader loads with an acquire. A reader that is ordered after the note by anything (a lock, an event, a wait for the GPU)
// is ordered after the mark too, and sees it: it never finds "never" for a page a note it could have seen covered. A reader
// with no such order is racing the note, and so did invalidate's look under the note's own lock, which can come first too:
// the same answers either way. Never taken off, so a mark seen stays true (no ABA); a page used once and then for something
// else keeps its mark, and its readers take the slow way, as before.
//
// Pages from 0 to Pages - 1 (Pages / ChunkPages chunks of a bit a page, each made when a page of it is first marked
// and never freed); a page past them is never marked and reads as never marked. A writer's chunk is made under make_mu.
#pragma once

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <mutex>

namespace mkwvk {
template <uint64_t Pages, uint64_t ChunkPages>
class PageMarks {
    static_assert(ChunkPages > 0 && Pages % ChunkPages == 0, "whole chunks");
    static constexpr uint64_t kWords = (ChunkPages + 63) / 64, kChunks = Pages / ChunkPages;
    std::atomic<std::atomic<uint64_t>*> chunks[kChunks] = {};
    std::mutex make_mu;
    // (the bits of pages a..b of one word, 0 <= a <= b < 64)
    static constexpr uint64_t bits(uint64_t a, uint64_t b) { return (b == 63 ? ~0ull : (2ull << b) - 1) & ~((1ull << a) - 1); }
    // (from page p, the last page of [p, last] in p's word and chunk: a page's bit is its place in its chunk, 64 a word)
    static constexpr uint64_t run_end(uint64_t p, uint64_t last) {
        const uint64_t in = p % ChunkPages, word_end = p + (63 - in % 64), chunk_end = p - in + ChunkPages - 1;
        return std::min(last, std::min(word_end, chunk_end));
    }
    std::atomic<uint64_t>* chunk_made(uint64_t c) {
        std::atomic<uint64_t>* w = chunks[c].load(std::memory_order_acquire);
        if (w) return w;
        std::lock_guard lk(make_mu);
        w = chunks[c].load(std::memory_order_acquire);
        if (!w) {
            w = new std::atomic<uint64_t>[kWords];
            for (uint64_t i = 0; i < kWords; i++) w[i].store(0, std::memory_order_relaxed);
            chunks[c].store(w, std::memory_order_release);   // (its zeros before it)
        }
        return w;
    }

public:
    PageMarks() = default;
    PageMarks(const PageMarks&) = delete;
    PageMarks& operator=(const PageMarks&) = delete;
    /// marks pages first..last (inclusive; the ones past Pages left out)
    void mark(uint64_t first, uint64_t last) {
        if (last >= Pages) last = Pages - 1;
        for (uint64_t p = first; p <= last && p < Pages;) {
            std::atomic<uint64_t>* w = chunk_made(p / ChunkPages);
            const uint64_t in = p % ChunkPages, end = run_end(p, last), word = in / 64;
            const uint64_t m = bits(in % 64, in % 64 + (end - p));
            if ((w[word].load(std::memory_order_relaxed) & m) != m) w[word].fetch_or(m, std::memory_order_release);
            p = end + 1;
        }
    }
    /// whether any of pages first..last was ever marked (a chunk never made: none of its pages)
    bool any(uint64_t first, uint64_t last) const {
        if (last >= Pages) last = Pages - 1;
        for (uint64_t p = first; p <= last && p < Pages;) {
            const std::atomic<uint64_t>* w = chunks[p / ChunkPages].load(std::memory_order_acquire);
            if (!w) {
                p = (p / ChunkPages + 1) * ChunkPages;
                continue;
            }
            const uint64_t in = p % ChunkPages, end = run_end(p, last);
            if (w[in / 64].load(std::memory_order_acquire) & bits(in % 64, in % 64 + (end - p))) return true;
            p = end + 1;
        }
        return false;
    }
};
}   // namespace mkwvk
