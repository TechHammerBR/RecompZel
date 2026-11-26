// invalidate_quick's look (gpu/vk/vk_replay.cpp) and the marks it reads (gpu/vk/page_marks.h), with the production pieces
// cut out of the renderer by tests/test_invalidate_quick.py:
//   marks      the marks themselves: words, chunks never made, the window's end
//   agree-wb   vk_memory.cpp's wb_pages_note, memory_writeback_value and memory_writeback_ever: the lock-free "ever" is the
//              locked one's, range by range, over random write-backs
//   agree-vw   vk_texture.cpp's vw_note, vw_forget, texture_gpu_written_in and texture_gpu_written_ever: wherever the locked
//              list has a texture, the marks say so (they may say so where it no longer has one: never the other way)
//   threads    the order: a reader that is ordered after a note (by a later publication it acquires, or by the note's own
//              lock) sees the note's mark, with chunks made by two writers at once
//   quick[-*]  invalidate_quick: kept (1, the read noted) only with nothing in the range, else 0 and nothing noted; the
//              switches that turn it off (the test sets them in the environment)
#include "gpu/vk/compat/hookshot_env.h"
#include "gpu/vk/page_marks.h"
#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <thread>
#include <unordered_map>
#include <vector>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
using mkwvk::PageMarks;

// ---- vk_memory.cpp: the write-back pages (small: 16 chunks of 64 pages) ----
namespace wbt {
constexpr uint64_t kPageShift = 12, kChunkPages = 64, kPages = 1024;
namespace {
#include "quick_wb.inc"
}   // namespace wbt

// ---- vk_texture.cpp: the list of textures the GPU wrote ----
namespace vwt {
struct Texture {
    uint64_t gpu = 0, guest_size = 0;
    bool vw_listed = false;
};
bool flushable(const Texture&) { return true; }
std::unordered_multimap<uint64_t, Texture*> by_gpu;
#include "quick_vw.inc"
}   // namespace vwt

// ---- vk_replay.cpp: invalidate_quick, with what it asks stood in for ----
namespace qt {
bool pages_there, textures_there, writebacks_there;
uint64_t asked_guest, noted_guest, noted_size;
int asks, notes;
void logf(const char*, ...) {}
bool tex_pages_any(uint64_t, uint64_t) { return pages_there; }
bool texture_gpu_written_ever(uint64_t, uint64_t) { return textures_there; }
bool memory_writeback_ever(uint64_t guest, uint64_t) { asked_guest = guest; asks++; return writebacks_there; }
void memory_note_cpu_read(uint64_t guest, uint64_t size) { noted_guest = guest, noted_size = size, notes++; }
struct Host { uint64_t (*gpu_guest)(uint64_t); };
uint64_t to_guest(uint64_t gpu) { return gpu + 0x1000; }
const Host the_host{to_guest};
const Host* host = &the_host;
#include "quick_decide.inc"
}   // namespace qt

static void marks() {
    PageMarks<256, 64> m;   // (four chunks of one word)
    CHECK(!m.any(0, 255) && !m.any(5, 5) && !m.any(7, 3));
    m.mark(5, 5);
    CHECK(m.any(5, 5) && m.any(0, 255) && m.any(4, 6) && !m.any(0, 4) && !m.any(6, 255));
    m.mark(63, 64);   // (a word's last page and the next chunk's first)
    CHECK(m.any(63, 63) && m.any(64, 64) && !m.any(6, 62) && !m.any(65, 255) && m.any(60, 70));
    m.mark(130, 250);   // (more than a word, in chunk 2 and 3; chunk 1 holds only page 64)
    CHECK(m.any(130, 130) && m.any(250, 250) && m.any(190, 191) && !m.any(129, 129) && !m.any(251, 255) && !m.any(65, 129));
    m.mark(130, 250);   // (again: no change)
    CHECK(!m.any(65, 129) && !m.any(251, 255));
    m.mark(255, 100000);   // (past the window: left out)
    CHECK(m.any(255, 255) && m.any(255, 1u << 30) && !m.any(256, 1u << 30) && !m.any(251, 254));
    PageMarks<256, 64> fresh;
    fresh.mark(300, 400);   // (all past the window)
    CHECK(!fresh.any(0, 1u << 30));
    PageMarks<64, 16> small;   // (chunks of less than a word, as tests/test_readback_part.py's tables have)
    small.mark(14, 17);
    CHECK(small.any(14, 14) && small.any(15, 15) && small.any(16, 16) && small.any(17, 17) && !small.any(0, 13) &&
          !small.any(18, 63) && small.any(10, 40));
    small.mark(40, 40);
    CHECK(small.any(33, 47) && !small.any(18, 39) && !small.any(41, 63));
    std::puts("PASS: marks by page, across words and chunks never made, the window's end");
}

static void agree_wb() {
    std::mt19937_64 r(7);
    const uint64_t span = wbt::kPages << wbt::kPageShift;
    for (int round = 0; round < 4000; round++) {
        if (r() % 3 == 0) {   // (a write-back: [lo, hi), some reaching past the table)
            const uint64_t lo = r() % (span + 0x4000), hi = lo + 1 + r() % 0x6000;
            wbt::wb_pages_note(lo, hi, 1 + r() % 50, r() % 2);
        }
        const uint64_t g = r() % (span + 0x4000), size = r() % 3 ? 1 + r() % 0x3000 : 0;
        bool ever = true;
        wbt::memory_writeback_value(g, size, &ever, nullptr, nullptr);
        CHECK(wbt::memory_writeback_ever(g, size) == ever);
    }
    std::puts("PASS: memory_writeback_ever is memory_writeback_value's ever, range by range");
}

static void agree_vw() {
    std::mt19937_64 r(11);
    std::vector<std::unique_ptr<vwt::Texture>> ts;
    const uint64_t top = 1ull << 39;
    auto addr = [&] { return r() % 4 ? r() % (64ull << 20) : top - (r() % (8ull << 20)); };   // (some at 512 GB's edge)
    for (int round = 0; round < 6000; round++) {
        const unsigned k = (unsigned)(r() % 10);
        if (k < 3) {   // (a texture the GPU wrote, listed)
            auto t = std::make_unique<vwt::Texture>();
            t->gpu = addr() & ~0xffull, t->guest_size = 0x100 + r() % (2ull << 20);
            vwt::by_gpu.emplace(t->gpu, t.get());
            vwt::vw_note(*t);
            ts.push_back(std::move(t));
        } else if (k == 3 && !ts.empty()) {   // (one destroyed: off the list)
            const size_t i = r() % ts.size();
            vwt::vw_forget(*ts[i]);
            auto [a, b] = vwt::by_gpu.equal_range(ts[i]->gpu);
            for (auto it = a; it != b; ++it)
                if (it->second == ts[i].get()) { vwt::by_gpu.erase(it); break; }
            ts.erase(ts.begin() + (long)i);
        } else if (k == 4 && !vwt::vw.empty()) {   // (texels written back: texture_flush_to_guest takes the entry off)
            std::lock_guard lk(vwt::vw_mu);
            vwt::vw.erase(vwt::vw.begin());
        }
        const uint64_t g = addr(), size = r() % 5 ? 1 + r() % 0x20000 : 0;
        // (an empty range: invalidate returns before it asks, and texture_gpu_written_in answers for the point lo)
        if (size && vwt::texture_gpu_written_in(g, size)) CHECK(vwt::texture_gpu_written_ever(g, size));
        CHECK(!vwt::texture_gpu_written_ever(g, 0));
    }
    CHECK(vwt::texture_gpu_written_ever(top - 0x1000, 0x2000) && vwt::texture_gpu_written_ever(top, 0x40) &&
          vwt::texture_gpu_written_ever(0x1000, ~0ull));   // (past 512 GB, or wrapping: not followed)
    std::puts("PASS: texture_gpu_written_ever wherever texture_gpu_written_in, and past 512 GB");
}

static void threads() {
    // Two writers note pages, each under the lock what the mark stands for; each note is published after it (as a fence or an
    // event of the game's would be). A reader that acquires the publication must see the mark; so must one that finds the
    // note under the lock. The pages of a round fall in chunks not made yet, shared by both writers (made under make_mu).
    static PageMarks<1u << 20, 1u << 12> m;   // (256 chunks of 4096 pages)
    constexpr int kRounds = 200, kPer = 64;
    std::mutex note_mu;
    std::vector<uint8_t> noted((size_t)2 * kRounds * kPer);
    std::atomic<int> published[2] = {{0}, {0}};
    std::atomic<bool> stop{false};
    auto page = [](int w, int i) { return (uint64_t)(i / kPer) * 4096 + (uint64_t)(i % kPer) * 16 + (uint64_t)w; };
    auto writer = [&](int w) {
        for (int i = 0; i < kRounds * kPer; i++) {
            {
                std::lock_guard lk(note_mu);
                m.mark(page(w, i), page(w, i));
                noted[(size_t)w * kRounds * kPer + (size_t)i] = 1;
            }
            published[w].store(i + 1, std::memory_order_release);
        }
    };
    int seen = 0;
    auto reader = [&] {
        std::mt19937 r(3);
        while (!stop.load(std::memory_order_acquire)) {
            for (int w = 0; w < 2; w++) {
                const int n = published[w].load(std::memory_order_acquire);
                if (!n) continue;
                const int i = n - 1 - (int)(r() % (unsigned)std::min(n, 300));
                CHECK(m.any(page(w, i), page(w, i)));   // (ordered after its note: marked)
                seen++;
            }
            const int w = (int)(r() % 2), i = (int)(r() % (unsigned)(kRounds * kPer));
            bool is_noted;
            {
                std::lock_guard lk(note_mu);
                is_noted = noted[(size_t)w * kRounds * kPer + (size_t)i] != 0;
            }
            if (is_noted) CHECK(m.any(page(w, i), page(w, i)));   // (the note seen under its lock: the mark too)
        }
    };
    std::thread rd(reader), a(writer, 0), b(writer, 1);
    a.join(), b.join();
    stop.store(true, std::memory_order_release);
    rd.join();
    for (int w = 0; w < 2; w++)
        for (int i = 0; i < kRounds * kPer; i++) CHECK(m.any(page(w, i), page(w, i)));
    CHECK(!m.any(page(0, 0) + 2, page(0, 0) + 15) && !m.any(kRounds * 4096ull, (1u << 20) - 1));   // (and nothing else)
    std::printf("PASS: a reader ordered after a note sees its mark (%d checks while the writers ran)\n", seen);
}

static void quick(const char* mode) {
    // (default: on; the others are run with a switch set, which turns it off for every call)
    const bool on = !std::strcmp(mode, "quick");
    auto ask = [](uint64_t gpu, uint64_t size, bool pages, bool textures, bool writebacks) {
        qt::pages_there = pages, qt::textures_there = textures, qt::writebacks_there = writebacks;
        qt::notes = qt::asks = 0, qt::noted_guest = qt::noted_size = 0;
        return qt::invalidate_quick(gpu, size);
    };
    const uint64_t g = 0x2345000, s = 64;
    CHECK(ask(g, s, false, false, false) == (on ? 1 : 0));
    CHECK(qt::notes == (on ? 1 : 0));
    if (on) CHECK(qt::noted_guest == g + 0x1000 && qt::noted_size == s && qt::asked_guest == g + 0x1000);
    // (anything that may be there: the slow way, nothing noted here, invalidate notes it)
    CHECK(ask(g, s, true, false, false) == 0 && qt::notes == 0);
    CHECK(ask(g, s, false, true, false) == 0 && qt::notes == 0);
    CHECK(ask(g, s, false, false, true) == 0 && qt::notes == 0);
    // (past 512 GB, or reaching past it: not followed)
    CHECK(ask(1ull << 39, s, false, false, false) == 0 && qt::notes == 0);
    CHECK(ask((1ull << 39) - 32, s, false, false, false) == 0 && qt::notes == 0);
    CHECK(ask(16, ~0ull, false, false, false) == 0 && qt::notes == 0);
    // (an empty range: nothing to look at, kept)
    CHECK(ask(g, 0, true, true, true) == (on ? 1 : 0));
    // (counted by 256 a thread: a thread of its own, its counts from 0, adds three batches of its 1000 calls)
    qt::inv_kept = 0, qt::inv_gave = 0;
    std::thread([&] { for (int i = 0; i < 1000; i++) ask(g, s, false, false, i % 4 == 0); }).join();
    CHECK(qt::inv_kept.load() + qt::inv_gave.load() == 768);
    CHECK(on ? qt::inv_gave.load() == 192 && qt::inv_kept.load() == 576 : qt::inv_kept.load() == 0);
    std::printf("PASS: %s: invalidate_quick %s\n", mode, on ? "keeps the core only with nothing there" : "never keeps the core");
}

int main(int argc, char** argv) {
    CHECK(argc == 2);
    const char* c = argv[1];
    if (!std::strcmp(c, "marks")) marks();
    else if (!std::strcmp(c, "agree-wb")) agree_wb();
    else if (!std::strcmp(c, "agree-vw")) agree_vw();
    else if (!std::strcmp(c, "threads")) threads();
    else if (!std::strncmp(c, "quick", 5)) quick(c);
    else CHECK(!"no such case");
}
