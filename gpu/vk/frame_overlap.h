// (hookshot) Frame overlap: what a frame's recordings do to the game's memory, and where the GPU's time goes between them
// (vk_replay.cpp; docs/development/frame-pipeline.md has the frame's whole sequence and
// what was measured). Kept apart so the rules are checked without the renderer (tests/test_frame_overlap.py).
//
// The game waits once a frame, with no timeout, for the fence of the frame before's present, and only then says that its next
// frame's data is written (the CPU signal the frame's work waits for). So the render thread gets a frame only once the GPU has
// finished the one before, and the GPU has nothing to do until the new frame's first part is recorded: 2.4 ms of a 14.8 ms
// frame on an RTX 3090 in Kokiri Forest.
//
// What each recording did is counted always (the `vk: frame overlap` log line):
//  - it reads the game's memory at the GPU's time: a dispatch or a draw whose program follows pointers (the page table: a pool
//    never bound has no mirror), or a binding or copy served from guest memory in place;
//  - it writes the game's memory at the GPU's time: its part's end copies mirrors back (results, the stream's uniform updates,
//    event words).
// Measured: after a frame's last recording of either kind comes its present's own recording and 0.00 ms of GPU time. An answer
// to the game's wait at that recording (tried as RX_VK_FRAME_WAIT_EARLY, removed) had nothing to gain.
#pragma once

#include <cstdint>

namespace mkwvk::frame_overlap {

/// What one recording did, counted from the end of the recording before it to its own
struct RecordingFacts {
    int64_t follows = 0;          // (dispatches, and draws whose program follows pointers into the game's memory)
    int64_t written_back = 0;     // (bytes its part's end copies from mirrors into the game's memory)
    uint64_t in_place_part = 0;   // (the newest part that read or wrote the game's memory where it lies: memory_in_place_part)
    uint64_t part = 0;            // (its own part number; 0: none)
};
/// Whether the recording reads the game's memory at the GPU's time: it could see what the game writes after it is recorded
constexpr bool reads_game(const RecordingFacts& f) { return f.follows > 0 || (f.part && f.in_place_part >= f.part); }
/// Whether it reads or writes it: the game could also see its results
constexpr bool touches_game(const RecordingFacts& f) { return reads_game(f) || f.written_back > 0; }

/// The presents whose frames are recorded whole: each present's value, a recording of its frame (release: the last of a kind,
/// or an older frame's when it has none) and the present's own recording (last). The newest kKept: for the GPU time of what
/// comes after that recording, read when the recordings' slots come round
class Frames {
public:
    static constexpr int kKept = 64;
    void note(uint64_t value, uint64_t release, uint64_t last) {
        Frame& f = frames_[at_++ % kKept];
        f.value = value, f.release = release < last ? release : last, f.last = last;
    }
    /// Whether recording seq comes after its frame's kept recording and up to its present's
    bool after_release(uint64_t seq) const {
        for (const Frame& f : frames_)
            if (f.value && seq > f.release && seq <= f.last) return true;
        return false;
    }

private:
    struct Frame {
        uint64_t value = 0, release = 0, last = 0;
    };
    Frame frames_[kKept];
    unsigned at_ = 0;
};

// ---- The GPU's time between two recordings ----
/// From the end of one recording's command buffer to the start of the next one's (GPU clock ticks), split by the start of
/// the next one's upload command buffer when it had one that ran in between (upload: its first timestamp; 0 or outside the
/// two: none, or an older use's). idle: nothing of ours on the GPU; uploads: its upload command buffer (mirror syncs, texture
/// uploads, the readback pages' refresh, the page table). Both 0 when the end before is not known, the clock went back, or
/// the two are over a_pause_ns apart (a load, the menu: not a frame's gap)
struct Gap {
    int64_t idle_ns = 0, uploads_ns = 0;
};
constexpr Gap gap(uint64_t end_before, uint64_t upload, uint64_t begin, double ns_a_tick, int64_t a_pause_ns = 100000000) {
    if (!end_before || begin < end_before) return {};
    const int64_t all = (int64_t)((double)(begin - end_before) * ns_a_tick);
    if (all > a_pause_ns) return {};
    if (upload < end_before || upload > begin) return {all, 0};
    const int64_t up = (int64_t)((double)(begin - upload) * ns_a_tick);
    return {all - up, up};
}
/// Which of the line's columns a recording's gap goes to, by how many recordings of its frame before it had a draw or a
/// dispatch: 0 up to the frame's first such recording (the lead: over the submits that record none), 1 up to its second, and
/// so on; the last column for every one after the kGapColumns - 1 first
constexpr int kGapColumns = 13;
constexpr int gap_column(int working_before) {
    return working_before < 0 ? 0 : working_before >= kGapColumns ? kGapColumns - 1 : working_before;
}

// ---- Frame ahead: what the signal's job took that came with the signal (counters only; docs/development/frame-pipeline.md) ----
// The frame's submits are in the render thread's hands ~2 ms before the CPU's signal, and its draws are recorded in the
// signal's job. Could a part have been recorded when the last submit came? Not if it took something that came after it.
// Counted per recording with a draw of the signal's job (a part):
//  - signal_pages: pages of the signal's capture (written between the last submit's capture and the signal's) that were
//    copied into a mirror in this part: a pool's dirty pages are copied when a part first binds the pool, so they are counted
//    for the first part that uses the pool, whichever of its pages that part reads, and not again for a later part;
//  - live_pages: dirty pages in no capture, copied from guest memory as it is at the replay.
struct PartInputs {
    int64_t signal_pages = 0, live_pages = 0;
};
/// Whether the part took nothing that came with the signal (of what is counted)
constexpr bool part_final(const PartInputs& p) { return p.signal_pages == 0 && p.live_pages == 0; }
/// The parts of the frames since the last log line
struct AheadTally {
    int64_t frames = 0;              // (frames with at least one part)
    int64_t parts = 0, final_parts = 0;
    int64_t by_signal = 0, by_live = 0;          // (parts not final, by what they took: a part may be in both)
    int64_t signal_pages = 0, live_pages = 0;    // (the pages those parts took)
    int64_t first_final = 0;         // (frames whose first part was final)
    int64_t first_three_final = 0;   // (frames whose first three parts were all final; all of them, where it has fewer)
    int index = 0;                   // (this frame's parts so far)
    bool three = true;               // (and whether its first three were final so far)
    constexpr void part(const PartInputs& p) {
        const bool fin = part_final(p);
        parts++, final_parts += fin;
        by_signal += p.signal_pages > 0, by_live += p.live_pages > 0;
        signal_pages += p.signal_pages, live_pages += p.live_pages;
        if (index == 0) first_final += fin;
        if (index < 3 && !fin) three = false;
        index++;
    }
    constexpr void frame_end() {
        if (index) frames++, first_three_final += three;
        index = 0, three = true;
    }
};
/// The share of the parts that were final, in percent (100 with no part)
constexpr double final_share(const AheadTally& t) { return t.parts ? 100.0 * (double)t.final_parts / (double)t.parts : 100.0; }

}   // namespace mkwvk::frame_overlap
