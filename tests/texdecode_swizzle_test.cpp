// gpu/vk/texdecode/block_linear.cpp: swizzle then deswizzle over a table of layouts, the padding left alone, strips (how
// vk_texture.cpp splits a big level over threads), refusals, and offsets worked out by hand from the layout rules.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include "texdecode/texdecode.h"

using namespace mkwvk::texdecode;
using Bytes = std::vector<uint8_t>;
static long problems, layouts, strips;
static uint64_t seed = 88172645463325252ull;
static uint8_t rnd_byte() { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; return (uint8_t)((seed >> 32) % 0xEE); }   // (never the sentinel 0xEE)
#define CHECK(c, ...) do { if (!(c)) { if (problems++ < 30) { printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } } while (0)

// Where a texel's bytes land: swizzle an image of zeros with only that texel's bytes set to 1.. and read the offsets back
static std::vector<uint64_t> where(uint32_t bpb, uint32_t w, uint32_t h, uint32_t d, uint32_t th, uint32_t td, uint32_t x, uint32_t y, uint32_t z) {
    Bytes lin((size_t)w * h * d * bpb, 0), sw(block_linear_size(bpb, w, h, d, th, td), 0);
    for (uint32_t i = 0; i < bpb; i++) lin[(((size_t)z * h + y) * w + x) * bpb + i] = (uint8_t)(i + 1);
    CHECK(swizzle(sw, lin, bpb, w, h, d, th, td), "where: swizzle refused");
    std::vector<uint64_t> at(bpb, ~0ull);
    for (uint64_t o = 0; o < sw.size(); o++) if (sw[o]) at[sw[o] - 1] = o;
    return at;
}

static void hand(const char* why, uint32_t bpb, uint32_t w, uint32_t h, uint32_t d, uint32_t th, uint32_t td, uint32_t x, uint32_t y, uint32_t z, std::vector<uint64_t> want) {
    const auto got = where(bpb, w, h, d, th, td, x, y, z);
    CHECK(got == want, "%s: texel (%u,%u,%u) of %ux%ux%u bpb %u th %u td %u at %llu.. (want %llu..)", why, x, y, z, w, h, d, bpb, th, td,
          (unsigned long long)got[0], (unsigned long long)want[0]);
}

static void hand_offsets() {
    // The rules: a GOB is 64 bytes by 8 rows = 512 bytes. In it, byte column x (0-63) and row y (0-7) are at
    //   x[3:0] -> bits 0-3, y[0] -> 4, y[1] -> 5, x[4] -> 6, y[2] -> 7, x[5] -> 8.
    // A block is 2^th GOBs high (rows 8*2^th) by 2^td deep, its GOBs in y then z order; blocks go in x, then y, then z
    // order, a block row being gobs_x blocks, gobs_x = ceil(row bytes / 64). The Switch 1 layout has bits 5 and 6 the
    // other way round; the vectors below are the Switch 2's.
    // One GOB, 1 byte per texel (64 x 8):
    hand("origin", 1, 64, 8, 1, 0, 0, 0, 0, 0, {0});
    hand("x=1 is next byte", 1, 64, 8, 1, 0, 0, 1, 0, 0, {1});
    hand("x=8", 1, 64, 8, 1, 0, 0, 8, 0, 0, {8});
    hand("y=1 -> bit 4", 1, 64, 8, 1, 0, 0, 0, 1, 0, {16});
    hand("y=2 -> bit 5", 1, 64, 8, 1, 0, 0, 0, 2, 0, {32});
    hand("x=16 -> bit 6 (Switch 1: bit 5)", 1, 64, 8, 1, 0, 0, 16, 0, 0, {64});
    hand("y=4 -> bit 7", 1, 64, 8, 1, 0, 0, 0, 4, 0, {128});
    hand("x=32 -> bit 8", 1, 64, 8, 1, 0, 0, 32, 0, 0, {256});
    hand("x=48 is bits 6 and 8", 1, 64, 8, 1, 0, 0, 48, 0, 0, {64 + 256});
    hand("last byte of the GOB: all nine bits", 1, 64, 8, 1, 0, 0, 63, 7, 0, {511});
    hand("x=21,y=5: 5 + 64 + (y=5: 16 + 128)", 1, 64, 8, 1, 0, 0, 21, 5, 0, {5 + 64 + 16 + 128});
    // Several GOBs. Width 128 bytes = 2 GOB columns, height 16 rows = 2 GOB rows.
    hand("second GOB column: one block on", 1, 128, 16, 1, 0, 0, 64, 0, 0, {512});
    hand("second GOB row, th 0: a whole block row (2 blocks) on", 1, 128, 16, 1, 0, 0, 0, 8, 0, {1024});
    hand("both", 1, 128, 16, 1, 0, 0, 64, 8, 0, {1536});
    hand("th 1: the second GOB row is the block's second GOB", 1, 128, 16, 1, 1, 0, 0, 8, 0, {512});
    hand("th 1: the second GOB column is a block (1024 bytes) on", 1, 128, 16, 1, 1, 0, 64, 0, 0, {1024});
    hand("th 1: both", 1, 128, 16, 1, 1, 0, 64, 8, 0, {1024 + 512});
    hand("th 1, 32 rows: row 16 starts the next block row, 2 blocks * 1024 on", 1, 128, 32, 1, 1, 0, 0, 16, 0, {2048});
    hand("th 2, 40 rows: a block row is 32 rows, so row 33 is the second block row (1 GOB column: it starts at 2048), row 1 of its first GOB (+16)",
         1, 64, 40, 1, 2, 0, 0, 33, 0, {2048 + 16});
    // Depth: 64 x 8 x 4, td 1: a block is 2 slices deep (1024 bytes), a layer of blocks 1024.
    hand("td 1: slice 1 is the block's second GOB", 1, 64, 8, 4, 0, 1, 0, 0, 1, {512});
    hand("td 1: slice 2 starts the next block layer", 1, 64, 8, 4, 0, 1, 0, 0, 2, {1024});
    hand("td 1: slice 3", 1, 64, 8, 4, 0, 1, 5, 0, 3, {1024 + 512 + 5});
    hand("th 1, td 1, 16 rows: block 2 x 2 GOBs = 2048; slice 1 row 8 = GOB (1*2+1) = 3", 1, 64, 16, 2, 1, 1, 0, 8, 1, {3 * 512});
    // Depth with a block height that is not its depth: the GOBs of a block go y first, then z, so GOB index = (slice % 2^td) * 2^th +
    // row / 8 within the block. (With th == td, as above, a mix-up of the two powers cannot show.) 64 bytes wide: one GOB column.
    // th 1, td 1: a block is 2 GOBs high, 2 deep = 4 GOBs; slice 1 row 0 is GOB 1*2 + 0 = 2 -> 1024.
    hand("th 1, td 1, 16 rows: slice 1 row 0 is GOB 2 (the review's example)", 1, 64, 16, 2, 1, 1, 0, 0, 1, {2 * 512});
    // th 2, td 1: 4 GOBs high, 2 deep = 8 GOBs a block, 4096 bytes; 32 rows, 2 slices = one block. Slice 1 row 0 = GOB 1*4 + 0 = 4 -> 2048,
    // slice 1 row 8 = 1*4 + 1 = 5 -> 2560, slice 0 row 24 = 0*4 + 3 = 3 -> 1536 (z-first order would give 1 * 1 + 0 = 1, 512).
    hand("th 2, td 1: slice 1 row 0 is GOB 4", 1, 64, 32, 2, 2, 1, 0, 0, 1, {4 * 512});
    hand("th 2, td 1: slice 1 row 8 is GOB 5", 1, 64, 32, 2, 2, 1, 0, 8, 1, {5 * 512});
    hand("th 2, td 1: slice 0 row 24 is GOB 3", 1, 64, 32, 2, 2, 1, 0, 24, 0, {3 * 512});
    // th 1, td 2: 2 GOBs high, 4 deep = 8 GOBs a block (4096 bytes). Slice 3 row 8 = 3*2 + 1 = 7 -> 3584. Slice 4 starts the next block
    // layer (one GOB column, one block row of 16 rows: a layer is 4096 bytes): slice 4 row 0 = 4096, slice 5 row 8 = 4096 + (1*2 + 1) * 512.
    hand("th 1, td 2: slice 3 row 8 is GOB 7", 1, 64, 16, 5, 1, 2, 0, 8, 3, {7 * 512});
    hand("th 1, td 2: slice 4 is the next layer of blocks", 1, 64, 16, 5, 1, 2, 0, 0, 4, {4096});
    hand("th 1, td 2: slice 5 row 8, second layer", 1, 64, 16, 6, 1, 2, 0, 8, 5, {4096 + 3 * 512});
    // and with a second GOB column and a second block row, th 2, td 1: 128 bytes, 40 rows = 2 block rows of 32 rows; a block row is
    // 2 columns * 4096 = 8192. Texel (x 64 + 3, row 33, slice 1): block row 1 (8192), column 1 (+4096), GOB (1*4 + (33 % 32) / 8 = 4) -> 2048,
    // in-GOB row 1 = +16, x 3 = +3.
    hand("th 2, td 1, two columns, two block rows", 1, 128, 40, 2, 2, 1, 67, 33, 1, {8192 + 4096 + 4 * 512 + 16 + 3});
    // Bytes per texel, and rows that are not a whole GOB wide.
    hand("4 bytes a texel, 5 wide (20 bytes): texel 4 is bytes 16-19 -> bit 6", 4, 5, 8, 1, 0, 0, 4, 0, 0, {64, 65, 66, 67});
    hand("3 bytes a texel: texel 5 is bytes 15,16,17, across the 16-byte step", 3, 6, 8, 1, 0, 0, 5, 0, 0, {15, 64, 65});
    hand("16 bytes a texel: texel 3 is column 48 -> 64 + 256", 16, 8, 8, 1, 0, 0, 3, 0, 0,
         [] { std::vector<uint64_t> v; for (int i = 0; i < 16; i++) v.push_back(320 + i); return v; }());
    hand("16 bytes a texel, 8 wide = 2 GOB columns: texel 4 is the second GOB", 16, 8, 8, 1, 0, 0, 4, 0, 0,
         [] { std::vector<uint64_t> v; for (int i = 0; i < 16; i++) v.push_back(512 + i); return v; }());
    // Sizes
    CHECK(block_linear_size(1, 64, 8, 1, 0, 0) == 512, "size of one GOB");
    CHECK(block_linear_size(1, 65, 9, 1, 0, 0) == 4 * 512, "65 x 9: 2 x 2 GOBs");
    CHECK(block_linear_size(4, 100, 37, 1, 3, 0) == 7 * 512 * 8, "100 x 37 x 4: 7 GOB columns, one block row of 8 GOBs");
    CHECK(block_linear_size(1, 64, 8, 3, 0, 2) == 2048, "3 slices, td 2: one block layer of 4 GOBs");
    CHECK(block_linear_row_bytes(4, 100, 3, 0) == 7 * 512 * 8, "row of blocks");
    CHECK(block_linear_size(0, 1, 1, 1, 0, 0) == 0 && block_linear_size(1, 1, 1, 1, 6, 0) == 0, "bad arguments give no size");
}

static void round_trip(uint32_t bpb, uint32_t w, uint32_t h, uint32_t d, uint32_t th, uint32_t td) {
    layouts++;
    const size_t n = (size_t)w * h * d * bpb;
    const uint64_t total = block_linear_size(bpb, w, h, d, th, td);
    Bytes lin(n), back(n, 0x77), sw(total, 0xEE);
    for (auto& b : lin) b = rnd_byte();
    CHECK(swizzle(sw, lin, bpb, w, h, d, th, td), "swizzle refused %ux%ux%u bpb %u th %u td %u", w, h, d, bpb, th, td);
    size_t touched = 0;
    for (uint8_t b : sw) touched += b != 0xEE;
    CHECK(touched == n, "%ux%ux%u bpb %u th %u td %u: %zu bytes written, %zu texel bytes (padding disturbed or bytes overlap)", w, h, d, bpb, th, td, touched, n);
    CHECK(deswizzle(back, sw, bpb, w, h, d, th, td) && back == lin, "round trip %ux%ux%u bpb %u th %u td %u", w, h, d, bpb, th, td);
    // the storage need not be padded after the last GOB a texel is in: cut it there, still decodes; one byte less is refused
    size_t last = 0;
    for (size_t i = 0; i < sw.size(); i++) if (sw[i] != 0xEE) last = i;
    size_t need = (last / 512 + 1) * 512;   // (the GOB of the last byte written; the last texel's GOB is the last one touched)
    Bytes cut(sw.begin(), sw.begin() + (long)need), back2(n, 0);
    CHECK(deswizzle(back2, cut, bpb, w, h, d, th, td) && back2 == lin, "cut storage %ux%ux%u bpb %u th %u td %u", w, h, d, bpb, th, td);
    Bytes shorter(sw.begin(), sw.begin() + (long)need - 1);
    CHECK(!deswizzle(back2, shorter, bpb, w, h, d, th, td), "storage ending inside the last GOB was accepted");
    // a second swizzle over the first changes nothing; swizzling over a different filler keeps that filler in the padding
    Bytes sw2(total, 0xEF);   // (texel bytes are below 0xEE)
    swizzle(sw2, lin, bpb, w, h, d, th, td);
    size_t same = 0;
    for (size_t i = 0; i < sw.size(); i++) same += (sw[i] == 0xEE) == (sw2[i] == 0xEF) && (sw[i] == 0xEE || sw[i] == sw2[i]);
    CHECK(same == sw.size(), "padding not left as it was");
    CHECK(n == 0 || !deswizzle(std::span<uint8_t>(back).first(n - 1), sw, bpb, w, h, d, th, td), "short linear span accepted");
    // strips: a level of several block rows deswizzled one block row at a time, each from its own offset, as the threads do
    if (d == 1 && h > (8u << th)) {
        const uint32_t rows = 8u << th;
        const uint64_t rb = block_linear_row_bytes(bpb, w, th, td);
        Bytes strip_out(n, 0x33);
        for (uint32_t y0 = 0; y0 < h; y0 += rows) {
            const uint32_t sh = h - y0 < rows ? h - y0 : rows;
            const uint64_t off = (y0 / rows) * rb;
            CHECK(deswizzle(std::span<uint8_t>(strip_out).subspan((size_t)y0 * w * bpb, (size_t)sh * w * bpb),
                            std::span<const uint8_t>(sw).subspan(off), bpb, w, sh, 1, th, 0), "strip %u refused", y0);
        }
        CHECK(strip_out == lin, "strips of %ux%u bpb %u th %u differ from the whole", w, h, bpb, th);
        strips++;
    }
}

// Geometry whose byte counts wrap 64 bits is refused, nothing written, whatever the spans hold (the first call is the review's
// reproduction: row_bytes * h * d = 2^64 wrapped to 0, and the old code then walked 2^16 slices over a 4 KiB buffer).
static void overflow_checks() {
    Bytes a(4096, 0x5A), b(4096, 0x5B);
    const Bytes a0 = a;
    const uint32_t big = 1u << 16;
    CHECK(!deswizzle(a, b, 16, 1u << 28, big, big, 0, 0), "deswizzle accepted 2^28 x 2^16 x 2^16 at 16 bytes");
    CHECK(!swizzle(b, a, 16, 1u << 28, big, big, 0, 0), "swizzle accepted 2^28 x 2^16 x 2^16 at 16 bytes");
    CHECK(!deswizzle(a, b, 16, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 5, 5) && !swizzle(b, a, 16, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 5, 5),
          "the largest u32 geometry was accepted");
    CHECK(!deswizzle(a, b, 1, 0xFFFFFFFFu, 0xFFFFFFFFu, 2, 0, 0) && !deswizzle(a, b, 1, 1, 0xFFFFFFFFu, 0xFFFFFFFFu, 5, 5),
          "u32-sized dimensions with empty-ish spans were accepted");
    CHECK(block_linear_size(16, 1u << 28, big, big, 0, 0) == 0 && block_linear_size(16, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 5, 5) == 0,
          "block_linear_size of an uncountable level is not 0");
    CHECK(a == a0 && b == Bytes(4096, 0x5B), "a refused call wrote");
    // bytes per texel above 16 does not exist in NVN
    CHECK(!deswizzle(a, b, 17, 1, 1, 1, 0, 0) && !swizzle(b, a, 17, 1, 1, 1, 0, 0) && block_linear_size(17, 1, 1, 1, 0, 0) == 0 &&
          block_linear_row_bytes(17, 1, 0, 0) == 0 && block_linear_size(0xFFFFFFFFu, 1, 1, 1, 0, 0) == 0, "bpb above 16 accepted");
    // what the renderer can ask is counted exactly: 32768 x 32768 at 16 bytes (the largest 2D image a GPU makes), and a
    // 16384^3 volume at 16 bytes (the largest 3D one), th and td 5. size = GOB columns * block rows * blocks * depth blocks.
    CHECK(block_linear_size(16, 32768, 32768, 1, 5, 0) == (8192ull * 128) * (512ull << 5), "largest 2D level");
    CHECK(block_linear_size(16, 16384, 16384, 16384, 5, 5) == (4096ull * 64 * (512ull << 10)) * 512, "largest 3D level");
    CHECK(block_linear_row_bytes(16, 0xFFFFFFFFu, 5, 5) == ((0xFFFFFFFFull * 16 + 63) / 64) * (512ull << 10), "row of blocks of the widest u32");
    // just inside 64 bits is judged by the spans: 2^30 x 2^16 x 1 at 16 bytes is 2^50 bytes
    CHECK(block_linear_size(16, 1u << 30, big, 1, 0, 0) == (16ull << 30) / 64 * (big / 8) * 512 && !deswizzle(a, b, 16, 1u << 30, big, 1, 0, 0),
          "a countable level that no span holds");
    CHECK(a == a0, "a refused call wrote (2)");
}

int main() {
    hand_offsets();
    static const uint32_t bpbs[] = {1, 2, 3, 4, 6, 8, 12, 16}, ws[] = {1, 3, 16, 17, 64, 65, 100, 130, 257}, hs[] = {1, 7, 8, 9, 33, 65, 129};
    for (uint32_t bpb : bpbs) for (uint32_t w : ws) for (uint32_t h : hs) for (uint32_t th = 0; th <= 5; th++) round_trip(bpb, w, h, 1, th, 0);
    // 3D, and arrays of slices: the depth block sizes too
    for (uint32_t bpb : {1u, 4u, 12u}) for (uint32_t w : {5u, 64u, 70u}) for (uint32_t h : {3u, 8u, 20u}) for (uint32_t d : {2u, 3u, 5u, 9u})
        for (uint32_t th : {0u, 1u, 3u}) for (uint32_t td : {0u, 1u, 2u, 4u}) round_trip(bpb, w, h, d, th, td);
    // what the game's levels look like: a big RGBA8, a big BC-ish (width/height in blocks, 8 and 16 bytes), a tall narrow one
    round_trip(4, 1024, 512, 1, 4, 0);
    round_trip(4, 1920, 1080, 1, 4, 0);
    round_trip(16, 512, 256, 1, 3, 0);
    round_trip(8, 513, 257, 1, 5, 0);
    round_trip(4, 16, 4096, 1, 5, 0);
    // refusals: nothing written
    Bytes a(4096, 0x5A), b(4096, 0x5B);
    CHECK(!swizzle(a, b, 0, 8, 8, 1, 0, 0) && !swizzle(a, b, 1, 0, 8, 1, 0, 0) && !swizzle(a, b, 1, 8, 0, 1, 0, 0) && !swizzle(a, b, 1, 8, 8, 0, 0, 0) &&
          !swizzle(a, b, 1, 8, 8, 1, 6, 0) && !swizzle(a, b, 1, 8, 8, 1, 0, 6) && !deswizzle(a, b, 1, 64, 64, 2, 0, 0) &&
          !deswizzle(a, std::span<const uint8_t>(b).first(100), 1, 64, 64, 1, 0, 0), "bad arguments");
    CHECK(a == Bytes(4096, 0x5A), "a refused call wrote");
    overflow_checks();
    printf("%ld layouts round-tripped (%ld of them also as strips), hand-computed offsets checked, %ld problems\n", layouts, strips, problems);
    printf(problems ? "FAIL\n" : "PASS\n");
    return problems ? 1 : 0;
}
