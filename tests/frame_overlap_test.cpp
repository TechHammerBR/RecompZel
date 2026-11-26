// The frame overlap's rules (gpu/vk/frame_overlap.h), compiled and run alone: tests/test_frame_overlap.py
#include "../gpu/vk/frame_overlap.h"

#include <cstdio>

using namespace mkwvk::frame_overlap;

static int fails;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

// (the rules hold at compile time too)
static_assert(!reads_game(RecordingFacts{}));
static_assert(reads_game(RecordingFacts{1, 0, 0, 7}));
static_assert(!reads_game(RecordingFacts{0, 4096, 6, 7}) && touches_game(RecordingFacts{0, 4096, 6, 7}));

int main() {
    // ---- what a recording did ----
    {
        RecordingFacts f;   // (draws that read mirrors and captures only, nothing written back)
        f.part = 12, f.in_place_part = 11;   // (an older part read guest memory in place: not this one)
        CHECK(!reads_game(f) && !touches_game(f));
        f.in_place_part = 12;   // (this part did)
        CHECK(reads_game(f) && touches_game(f));
        f.in_place_part = 13;   // (a binding outside a recording's uploads counts for the next part: this one too, never fewer)
        CHECK(reads_game(f));
        f.in_place_part = 11, f.follows = 1;   // (a dispatch, or a draw that follows pointers)
        CHECK(reads_game(f) && touches_game(f));
        f.follows = 0, f.written_back = 64;   // (a uniform update or an event's word copied back: written, not read)
        CHECK(!reads_game(f) && touches_game(f));
        f.written_back = 0, f.part = 0, f.in_place_part = 0;   // (no part number: nothing known to be in place)
        CHECK(!reads_game(f));
    }
    // ---- the frames recorded whole: what comes after a frame's last recording of a kind ----
    {
        Frames frames;
        CHECK(!frames.after_release(41));
        frames.note(7005, 40, 44);   // (present 7005: its recording is 44, its last reading recording 40)
        CHECK(!frames.after_release(40) && frames.after_release(41) && frames.after_release(44) && !frames.after_release(45));
        frames.note(7019, 80, 72);   // (never after the present's own recording)
        CHECK(!frames.after_release(73) && !frames.after_release(72));
        for (uint64_t i = 0; i < Frames::kKept; i++) frames.note(8000 + i, 100 + i, 100 + i);
        CHECK(!frames.after_release(41));   // (the oldest go)
    }
    // ---- the GPU's time between two recordings ----
    {
        Gap g = gap(1000, 0, 3500, 1.0);   // (no upload command buffer)
        CHECK(g.idle_ns == 2500 && g.uploads_ns == 0);
        g = gap(1000, 2000, 3500, 1.0);    // (idle to 2000, then its uploads to 3500)
        CHECK(g.idle_ns == 1000 && g.uploads_ns == 1500);
        g = gap(1000, 400, 3500, 1.0);     // (the slot's query holds an older use's time: no uploads this time)
        CHECK(g.idle_ns == 2500 && g.uploads_ns == 0);
        g = gap(1000, 3600, 3500, 1.0);
        CHECK(g.idle_ns == 2500 && g.uploads_ns == 0);
        g = gap(1000, 1000, 3500, 2.0);    // (uploads from the moment the one before ended; 2 ns a tick)
        CHECK(g.idle_ns == 0 && g.uploads_ns == 5000);
        g = gap(0, 2000, 3500, 1.0);       // (the recording before has no timestamp)
        CHECK(g.idle_ns == 0 && g.uploads_ns == 0);
        g = gap(5000, 0, 3500, 1.0);       // (the clock went back)
        CHECK(g.idle_ns == 0 && g.uploads_ns == 0);
        g = gap(1000, 0, 1000 + 200000000, 1.0);   // (0.2 s: a load or the menu, not a frame's gap)
        CHECK(g.idle_ns == 0 && g.uploads_ns == 0);
        // (a column a recording with a draw for the frame's first twelve, the lead first; the rest together)
        CHECK(gap_column(0) == 0 && gap_column(1) == 1 && gap_column(11) == 11 && gap_column(12) == kGapColumns - 1 &&
              gap_column(40) == kGapColumns - 1 && gap_column(-1) == 0 && kGapColumns == 13);
    }
    // ---- frame ahead: which parts of the signal's job took something that came with the signal ----
    {
        CHECK(part_final(PartInputs{}) && !part_final(PartInputs{3, 0}) && !part_final(PartInputs{0, 1}));
        AheadTally t;
        CHECK(final_share(t) == 100.0);
        t.frame_end();   // (a frame with no part in the signal's job: not a frame of the tally)
        CHECK(t.frames == 0 && t.first_three_final == 0);
        // (frame 1: eleven parts, the first takes 40 pages of the signal's capture, the fifth 2 live ones)
        for (int i = 0; i < 11; i++) t.part(i == 0 ? PartInputs{40, 0} : i == 4 ? PartInputs{0, 2} : PartInputs{});
        t.frame_end();
        CHECK(t.frames == 1 && t.parts == 11 && t.final_parts == 9 && t.by_signal == 1 && t.by_live == 1);
        CHECK(t.signal_pages == 40 && t.live_pages == 2 && t.first_final == 0 && t.first_three_final == 0);
        // (frame 2: all final)
        for (int i = 0; i < 11; i++) t.part(PartInputs{});
        t.frame_end();
        CHECK(t.frames == 2 && t.final_parts == 20 && t.first_final == 1 && t.first_three_final == 1);
        // (frame 3: the third part takes both kinds: the first is final, the first three are not; counted once as a part)
        for (int i = 0; i < 4; i++) t.part(i == 2 ? PartInputs{5, 1} : PartInputs{});
        t.frame_end();
        CHECK(t.frames == 3 && t.parts == 26 && t.final_parts == 23 && t.by_signal == 2 && t.by_live == 2);
        CHECK(t.first_final == 2 && t.first_three_final == 1);
        // (frame 4: two parts only, both final: its first three are all it has; the fourth part of a frame does not count there)
        t.part(PartInputs{}), t.part(PartInputs{});
        t.frame_end();
        for (int i = 0; i < 5; i++) t.part(i == 3 ? PartInputs{1, 0} : PartInputs{});
        t.frame_end();
        CHECK(t.frames == 5 && t.first_final == 4 && t.first_three_final == 3);
        CHECK(final_share(t) > 87.8 && final_share(t) < 87.9);   // (29 of 33)
    }
    if (!fails) std::printf("PASS: the frame overlap's rules\n");
    return fails != 0;
}
