// (Hookshot, HL_UBO_WRITER) The native writer of the driver's constant banks of a graphics stage: the per-draw uniform data
// the replay builds itself (c2: the texture, image and sampler handles; c0: the storage buffer table and the vertex stage's
// fixed word), written as the words' final bytes in one pass instead of word by word.
//
// driver_bank_fill (vk_bank.cpp) puts every word through a bounds-checked 4-byte copy, after clearing the whole bank:
// ~300 puts for a c2. The banks' layout is dense: every 8-byte slot of c2 and every 16-byte entry of c0's table holds a
// bound value's low words and zeros, so each region is the source array masked to its low words, which is a copy the
// compiler vectorizes. The same bytes, checked word for word against driver_bank_fill (HL_UBO_WRITER_CHECK, tests/).
//
// No Vulkan, no NvnState: plain arrays in, bytes out, so it is tested alone (tests/bank_write_test.cpp).
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>

namespace mkwvk::bankw {

constexpr uint32_t kC2Tex0 = 0x20, kC2Img = 0x120, kC2Tex1 = 0x168, kC2Samp = 0x568, kC2End = 0x968;   // (driver_bank_word's c2)
constexpr uint32_t kSsboEntries = 16, kVertexWordAt = 0x610;

namespace detail {
/// d[0..n) (words of 8 bytes, the first `words` of them whole) = src[i] & 0xffffffff
inline void low_words(uint8_t* d, const uint64_t* src, uint32_t words) {
    for (uint32_t i = 0; i < words; i++) {
        const uint64_t v = src[i] & 0xffffffffull;
        std::memcpy(d + 8 * (size_t)i, &v, 8);
    }
}
/// A bank is written into d (n bytes) at a place `at`, `len` bytes long, only as far as n reaches, whole dwords only (driver_bank_fill's
/// put: a word that does not fit in n is not written); `tmp` holds the region's bytes
inline void put_clipped(uint8_t* d, uint32_t n, uint32_t at, const uint8_t* tmp, uint32_t len) {
    if (at >= n) return;
    const uint32_t room = std::min<uint32_t>(len, n - at), k = room & ~3u;
    std::memcpy(d + at, tmp, k);
    std::memset(d + at + k, 0, room - k);   // (a dword that does not fit whole stays zero)
}
}  // namespace detail

/// c2 of a graphics stage: handles' low words, 8 bytes a slot (tex 32 from 0x20, img 9 from 0x120, tex 128 from 0x168, samp 128 from
/// 0x568), zeros elsewhere. The first n bytes. tex and samp: 128 values, img: 9 at least
inline void write_c2(const uint64_t* tex, const uint64_t* samp, const uint64_t* img, uint8_t* d, uint32_t n) {
    if (n <= kC2Tex0) {
        std::memset(d, 0, n);
        return;
    }
    std::memset(d, 0, kC2Tex0);
    struct Seg { uint32_t at; const uint64_t* src; uint32_t count; };
    const Seg segs[4] = {{kC2Tex0, tex, 32}, {kC2Img, img, 9}, {kC2Tex1, tex, 128}, {kC2Samp, samp, 128}};
    for (const Seg& s : segs) {
        if (s.at >= n) break;
        const uint32_t whole = std::min<uint32_t>(s.count, (n - s.at) / 8);
        detail::low_words(d + s.at, s.src, whole);
        if (whole < s.count) {   // the slot n cuts: its low word if it fits whole
            uint64_t v = s.src[whole] & 0xffffffffull;
            uint8_t b[8];
            std::memcpy(b, &v, 8);
            detail::put_clipped(d, n, s.at + 8 * whole, b, 8);
            break;
        }
    }
    if (n > kC2End) std::memset(d + kC2End, 0, n - kC2End);
}

/// c0 of a graphics stage whose storage buffer table is at `base` (0x110, 0x510, 0x410, 0x210, 0x310): 16 entries of 16 bytes, an
/// address (8 bytes) and the size's low word and a zero; zeros elsewhere. Stage 0 (the vertex stage: `vertex`) has the float
/// 2047.9375 at 0x610. E: any type with .addr and .size
template <class E>
inline void write_c0(const E* ssbo, uint32_t base, bool vertex, uint8_t* d, uint32_t n) {
    std::memset(d, 0, n);
    if (base < n) {
        const uint32_t whole = std::min<uint32_t>(kSsboEntries, (n - base) / 16);
        for (uint32_t i = 0; i < whole; i++) {
            const uint64_t a = ssbo[i].addr, s = (uint64_t)ssbo[i].size & 0xffffffffull;
            std::memcpy(d + base + 16 * (size_t)i, &a, 8);
            std::memcpy(d + base + 16 * (size_t)i + 8, &s, 8);
        }
        if (whole < kSsboEntries) {   // the entry n cuts: the words that fit whole
            const uint64_t a = ssbo[whole].addr, s = (uint64_t)ssbo[whole].size & 0xffffffffull;
            uint8_t b[16];
            std::memcpy(b, &a, 8);
            std::memcpy(b + 8, &s, 8);
            detail::put_clipped(d, n, base + 16 * whole, b, 16);
        }
    }
    if (vertex && kVertexWordAt + 4 <= n) {
        const float f = 2047.9375f;
        std::memcpy(d + kVertexWordAt, &f, 4);
    }
}

}  // namespace mkwvk::bankw
