// tests/test_staging_burst.py puts vk_texture.cpp's staging() and texture_frame's give-back loop where ACTUAL is and
// runs the cases below: frames that stage, then present, on a clock the fixture moves.
#include <vulkan/vulkan.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace fixture {
void require(bool ok, const char* why) {
    if (!ok) {
        fprintf(stderr, "FAIL: %s\n", why);
        std::exit(1);
    }
}
int64_t now_ns = 1'000'000'000;
struct Clock {   // (std::chrono::steady_clock in the code cut out)
    using duration = std::chrono::nanoseconds;
    using rep = duration::rep;
    using period = duration::period;
    using time_point = std::chrono::time_point<Clock, duration>;
    static constexpr bool is_steady = true;
    static time_point now() { return time_point(duration(now_ns)); }
};
struct VmaAllocation_T {};
using VmaAllocation = VmaAllocation_T*;
unsigned makes = 0, destroys = 0;
uint8_t mapped_stand_in;   // (never written: the cases only count arenas)
uint64_t rec_value = 1, completed_value = 0;
struct { VkPhysicalDeviceProperties props{}; } dev;
bool create_buffer(uint64_t, VkBufferUsageFlags, bool, VkBuffer& b, VmaAllocation& a, void** map) {
    a = new VmaAllocation_T;
    b = reinterpret_cast<VkBuffer>(a);
    *map = &mapped_stand_in;
    makes++;
    return true;
}
void destroy_buffer(VkBuffer b, VmaAllocation a) {
    require(a && b == reinterpret_cast<VkBuffer>(a), "an arena is destroyed with its own allocation");
    delete a;
    destroys++;
}
void logf(const char*, ...) {}
enum LogLevel : int { log_error, log_warn, log_info, log_debug, log_trace };
void logf_at(LogLevel, const char*, ...) {}
// (texture_frame's: Linux memory pressure is on, and it has just begun; VRAM is near what the driver allows. The cases
// set them)
bool linux_pressed = false, linux_entered_pressure = false, pool_pressed = false;
uint8_t pool_pressure = 0;   // (vk_texture.cpp: 0 normal, 1 pressed, 2 critical)
// (staging()'s count of every arena it makes, and their time: the log's "staging ... made so far")
std::atomic<uint64_t> st_arena_makes{0};
std::atomic<int64_t> st_arena_make_ns{0};

/* ACTUAL */

constexpr uint64_t MB = 1ull << 20;
// (the cases in arenas of the source's own size, kArena: 16 MB since the 8 GB cards' staging was kept smaller, 64 MB before. What a
// card keeps between loads is one arena here: the case the burst rule is for, where the idle one of two arenas taking turns went at
// every second present. A card of 6.5 GB or less keeps 64 MB, which with 16 MB arenas holds both of them)
constexpr uint64_t A = kArena;
constexpr uint64_t kBurst = 256 * MB;                   // (what the arenas a load just used may keep: texture_frame's rule)
constexpr uint64_t big_piece = A / 16 * 15;             // (two of them do not fit one arena)
constexpr unsigned past_cap = (unsigned)(kBurst / A) + 2;   // (big pieces enough that their arenas pass kBurst)
uint64_t keep = A;
// One frame: a submission that stages the pieces, then the present. The GPU finishes a frame's submission between that
// frame's present and the next one (one frame in flight)
void frame(const std::vector<uint64_t>& pieces, int64_t ms = 33) {
    rec_value++;
    for (uint64_t n : pieces) require(staging(n).buffer != VK_NULL_HANDLE, "a piece is staged");
    completed_value = rec_value - 1;
    give_back(completed_value, keep);
    now_ns += ms * 1'000'000;
}
uint64_t held() {
    uint64_t n = 0;
    for (const Arena& a : arenas) n += a.size;
    return n;
}
std::vector<uint64_t> big_pieces(unsigned n) { return std::vector<uint64_t>(n, big_piece); }

int run(int argc, char** argv) {
    require(argc == 2, "a case");
    static_assert(A > 2 * MB && kBurst % A == 0, "the cases' sizes need an arena of a few MB that divides 256 MB");
    const std::string test = argv[1];
    const bool off = getenv("RX_VK_STAGING_BURST_S") && atoll(getenv("RX_VK_STAGING_BURST_S")) == 0;
    dev.props.limits.nonCoherentAtomSize = 64;
    if (test == "consecutive") {
        // an arena's worth staged in each of 20 frames in a row: the frame before's arena is not the GPU's to give yet, and has
        // no room left after what it holds, so two take turns. Kept to one arena, the idle one of the two went at every second
        // present and was made again a frame later. (A little a frame shares one arena: staging() adds after what an arena
        // still in flight holds while it has room)
        for (int i = 0; i < 20; i++) frame({big_piece});
        if (off) require(makes >= 8, "RX_VK_STAGING_BURST_S=0: an arena made every second frame, as before");
        else require(makes == 2 && destroys == 0, "two arenas made for 20 frames in a row, none given back between");
        require(st_arena_makes.load() == makes, "every arena made is counted, for the log's line");
    } else if (test == "settles") {
        for (int i = 0; i < 20; i++) frame({1 * MB});
        for (int i = 0; i < 70; i++) frame({});   // (2.3 s with nothing staged)
        require(arenas.size() == 1 && held() == keep, "the load over, what is kept between loads is left");
        // (an arena nothing staged into for 30 s goes, but two warm ones always stay, against the 70-108 ms allocation stalls
        // a load would take making them again: kept four arenas here, so the idle rule has something to give back)
        keep = 4 * A;
        frame(big_pieces(4));
        for (int i = 0; i < 70; i++) frame({});
        require(arenas.size() == 4 && held() == keep, "four arenas kept between loads");
        for (int i = 0; i < 31; i++) frame({}, 1000);
        require(arenas.size() == 2 && held() == 2 * A, "nothing staged for 30 s: all but the two warm arenas go");
    } else if (test == "cap") {
        frame(big_pieces(past_cap));
        require(arenas.size() == past_cap, "an arena for each big piece");
        frame({});
        if (off) require(held() == keep, "RX_VK_STAGING_BURST_S=0: what the card keeps, as before");
        else require(held() == kBurst, "at most 256 MB of the arenas just used are kept");
    } else if (test == "big") {
        frame({A / 16 * 25});
        require(arenas.size() == 1 && arenas[0].size == A / 16 * 25, "a piece over an arena's size has an arena of its size");
        frame({});
        require(arenas.empty(), "an arena over the arenas' size goes once the GPU is done with it, used a moment ago or not");
    } else if (test == "keep256") {
        keep = kBurst;   // (a card over 6.5 GB: the rule adds nothing to what it keeps)
        for (int i = 0; i < 20; i++) frame({big_piece});
        require(makes == 2 && destroys == 0, "256 MB kept between loads: two arenas for 20 frames, as before");
        frame(big_pieces(past_cap));
        frame({});
        require(held() == kBurst, "256 MB kept between loads: no more than that after a load");
    } else if (test == "pressure") {
        // Linux memory pressure: an idle arena goes after 5 s, not 30, and when the pressure begins the idle ones go at
        // once, the ones a load used a moment ago too
        keep = 4 * A;   // (four kept between loads: the idle rule's 5 s has something to give back beyond the two warm arenas)
        frame(big_pieces(4));
        for (int i = 0; i < 70; i++) frame({});
        require(arenas.size() == 4, "the load over: four arenas kept");
        linux_pressed = true;
        for (int i = 0; i < 6; i++) frame({}, 1000);
        require(arenas.size() == 2, "under memory pressure, nothing staged for 5 s: all but the two warm arenas go");
        linux_pressed = false;
        for (int i = 0; i < 20; i++) frame({big_piece});
        require(arenas.size() == 2, "two arenas taking turns again");
        linux_entered_pressure = true;
        frame({});
        require(arenas.empty(), "the pressure begins: the idle arenas go at once");
    } else if (test == "short") {
        // VRAM near what the driver allows (over 90% of it, or Linux memory pressure on an integrated GPU): the rule is off,
        // and what stays is what the card keeps between loads, as before the rule. On a card of 6.5 GB or less the arenas are
        // VRAM behind the BAR: a burst's more would come off what a load's textures need
        pool_pressure = 1;
        frame(big_pieces(past_cap));
        require(arenas.size() == past_cap, "an arena for each big piece");
        frame({});
        require(held() == keep, "VRAM short: what the card keeps, not a burst's 256 MB");
        for (int i = 0; i < 20; i++) frame({big_piece});
        require(makes >= past_cap + 8, "VRAM short: an arena made every second frame, as before the rule");
        pool_pressure = 0;   // (room again: the rule is back)
        const unsigned before = makes;
        for (int i = 0; i < 20; i++) frame({big_piece});
        require(makes <= before + 1, "room again: two arenas take turns, none made every second frame");
        frame(big_pieces(past_cap));
        frame({});
        require(held() == kBurst, "room again: at most 256 MB of the arenas just used are kept");
    } else {
        require(false, "a known case");
    }
    return 0;
}
} // namespace fixture
int main(int argc, char** argv) { return fixture::run(argc, argv); }
