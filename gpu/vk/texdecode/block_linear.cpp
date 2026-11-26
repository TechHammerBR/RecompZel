// Tegra block-linear <-> linear copies, in the Switch 2 GOB layout.
//
// Ported from ocarina-recomp runtime/tex_deswizzle.c (the address function and the copy loop only), which was itself ported
// from MacNativeGames games/totk/third_party/d2r_gfx/gfx/tex/nvn_deswizzle.c @ b75be8cf (MIT, Copyright (c) 2026 jhaizhou).
// MIT: see LICENSE-MIT in this folder; PROVENANCE.md says what was changed. The texture-descriptor handling of the original
// (nvn_texdesc, levels, layers) is not here: the caller passes the geometry of one level.
//
// Layout (public descriptions: deko3d, Ryujinx BlockLinearLayout):
//   GOB = 64 bytes x 8 rows = 512 bytes; offset of (x byte, y row) within a GOB =
//     (x%64/32)*256 + (y%8/4)*128 + (x%32/16)*64 + (y%4/2)*32 + (y%2)*16 + x%16
//     i.e. x[3:0] -> bits 0-3, y[0] -> 4, y[1] -> 5, x[4] -> 6, y[2] -> 7, x[5] -> 8: the Switch 1 GOB with offset bits 5
//     and 6 swapped (the Switch 2's native tiling; gpu/third_party/suyu's SWIZZLE_X_BITS / SWIZZLE_Y_BITS say the same)
//   block = 1 GOB wide x 2^tile_h GOBs high x 2^tile_d GOBs deep, ordered y first then z inside a block; blocks fill the
//   level in x -> y -> z order (z outermost).
#include "texdecode.h"

#include <cstring>

namespace mkwvk::texdecode {
namespace {

constexpr uint32_t kMaxTile = 5;
// The widest texel (a block of an uncompressed format, or of BC/ASTC) any NVN format has is 16 bytes. Width, height and depth have
// no limit of their own: each is a u32, and every size below is computed in 64 bits with the products checked, so a geometry
// whose storage cannot be counted in 64 bits is refused, and one that can is judged by the spans' lengths.
constexpr uint32_t kMaxBpb = 16;

// a * b into r; false (r untouched) when the product does not fit 64 bits
bool mul(uint64_t a, uint64_t b, uint64_t& r) {
    if (a && b > UINT64_MAX / a) return false;
    r = a * b;
    return true;
}

struct Geo {
    uint64_t row_bytes, gobs_x, block, rows_per_block;   // (bytes of a texel row, GOB columns, bytes of a block, texel rows of one)
    uint64_t blocks_y, layer;                            // (block rows, bytes of one layer of blocks along depth)
    uint64_t total;                                      // (bytes of the whole level in swizzled storage)
    uint32_t th, td;
};

// false for a bad argument, or when the level's size does not fit 64 bits. Past this, no offset below can wrap: every one is
// below `total`.
bool geo(Geo& g, uint32_t bpb, uint32_t w, uint32_t h, uint32_t d, uint32_t th, uint32_t td) {
    if (!bpb || bpb > kMaxBpb || !w || !h || !d || th > kMaxTile || td > kMaxTile) return false;
    g.row_bytes = uint64_t(w) * bpb;                     // (below 2^36)
    g.gobs_x = (g.row_bytes + 63) / 64;
    g.block = 512ull << (th + td);
    g.rows_per_block = 8ull << th;
    g.blocks_y = (uint64_t(h) + g.rows_per_block - 1) / g.rows_per_block;
    uint64_t row_of_blocks;
    if (!mul(g.gobs_x, g.block, row_of_blocks) || !mul(row_of_blocks, g.blocks_y, g.layer)) return false;
    if (!mul(g.layer, (uint64_t(d) + (1ull << td) - 1) >> td, g.total)) return false;
    g.th = th;
    g.td = td;
    return true;
}

// Start of the GOB that holds texel byte column x of row y, slice z
uint64_t gob_start(const Geo& g, uint64_t x, uint64_t y, uint64_t z) {
    const uint64_t bd = 1ull << g.td, bh = 1ull << g.th;
    return (z / bd) * g.layer + (y / g.rows_per_block) * g.gobs_x * g.block + (x / 64) * g.block +
           ((z % bd) * bh + (y % g.rows_per_block) / 8) * 512;
}

// (the offset of a row's first byte in its GOB: the x terms of the formula above are the segments' 0, 64, 256, 320)
uint32_t row_off(uint32_t y) { return (y % 8 / 4) * 128 + (y % 4 / 2) * 32 + (y % 2) * 16; }

// Up to eight rows (y0 a multiple of 8) of one slice, a GOB at a time, so the destination's cache lines are finished before the
// next row's: a 64-byte GOB row is four 16-byte segments, at 0, 64, 256 and 320 inside the GOB (x[4] -> bit 6, x[5] -> bit 8),
// and the row's y bits add the same offset to all four. gob points at the strip's first GOB; lin at its first row.
template <bool TO_LINEAR>
void copy_strip(uint8_t* gob, uint8_t* lin, const Geo& g, uint32_t rows) {
    static constexpr uint32_t seg[4] = {0, 64, 256, 320};
    const uint64_t full = g.row_bytes / 64;
    for (uint64_t c = 0; c < full; c++, gob += g.block)
        for (uint32_t line = 0; line < rows; line++) {
            uint8_t* sw = gob + row_off(line);
            uint8_t* l = lin + line * g.row_bytes + c * 64;
            for (int s = 0; s < 4; s++) {
                if (TO_LINEAR) std::memcpy(l + 16 * s, sw + seg[s], 16);
                else std::memcpy(sw + seg[s], l + 16 * s, 16);
            }
        }
    const uint64_t x = full * 64;
    if (x == g.row_bytes) return;
    for (uint32_t line = 0; line < rows; line++)   // a partial GOB at the end of the rows
        for (int s = 0; x + 16 * s < g.row_bytes; s++) {
            const uint64_t n = g.row_bytes - x - 16 * s < 16 ? g.row_bytes - x - 16 * s : 16;
            uint8_t* sw = gob + row_off(line) + seg[s];
            uint8_t* l = lin + line * g.row_bytes + x + 16 * s;
            if (TO_LINEAR) std::memcpy(l, sw, n);
            else std::memcpy(sw, l, n);
        }
}

template <bool TO_LINEAR>
bool move(uint8_t* sw, uint64_t sw_n, uint8_t* lin, uint64_t lin_n, uint32_t bpb, uint32_t w, uint32_t h, uint32_t d,
          uint32_t th, uint32_t td) {
    Geo g;
    if (!geo(g, bpb, w, h, d, th, td)) return false;
    uint64_t slice_bytes, lin_need;
    if (!mul(g.row_bytes, h, slice_bytes) || !mul(slice_bytes, d, lin_need) || lin_n < lin_need) return false;
    if (sw_n < gob_start(g, g.row_bytes - 1, h - 1, d - 1) + 512) return false;
    for (uint32_t z = 0; z < d; z++)
        for (uint64_t y = 0; y < h; y += 8)   // (64 bits: a u32 y += 8 would wrap for a height within 8 of 2^32)
            copy_strip<TO_LINEAR>(sw + gob_start(g, 0, y, z), lin + (uint64_t(z) * h + y) * g.row_bytes, g, uint32_t(h - y < 8 ? h - y : 8));
    return true;
}

} // namespace

uint64_t block_linear_size(uint32_t bpb, uint32_t w, uint32_t h, uint32_t d, uint32_t th, uint32_t td) {
    Geo g;
    if (!geo(g, bpb, w, h, d, th, td)) return 0;
    return g.total;
}

uint64_t block_linear_row_bytes(uint32_t bpb, uint32_t w, uint32_t th, uint32_t td) {
    Geo g;
    return geo(g, bpb, w, 1, 1, th, td) ? g.gobs_x * g.block : 0;
}

bool deswizzle(std::span<uint8_t> linear, std::span<const uint8_t> swizzled, uint32_t bpb, uint32_t w, uint32_t h, uint32_t d,
               uint32_t th, uint32_t td) {
    // (the copy only reads from the swizzled side; the cast keeps one loop for both directions)
    return move<true>(const_cast<uint8_t*>(swizzled.data()), swizzled.size(), linear.data(), linear.size(), bpb, w, h, d, th, td);
}

bool swizzle(std::span<uint8_t> swizzled, std::span<const uint8_t> linear, uint32_t bpb, uint32_t w, uint32_t h, uint32_t d,
             uint32_t th, uint32_t td) {
    return move<false>(swizzled.data(), swizzled.size(), const_cast<uint8_t*>(linear.data()), linear.size(), bpb, w, h, d, th, td);
}

} // namespace mkwvk::texdecode
