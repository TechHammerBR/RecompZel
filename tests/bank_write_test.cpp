// (Hookshot, HL_UBO_WRITER) bank_write.h against the word-by-word fill it replaces (a copy of driver_bank_fill's graphics-stage
// branches, made of puts), on random bound state, for every bank size from 0 to 0xA00 and each stage's table.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>

#include "../gpu/vk/bank_write.h"

struct Buf { int32_t stage, index; uint64_t addr, size; };   // (nvn_p_bind_buf's shape)
static const uint32_t kTable[8] = {0x110, 0x510, 0x410, 0x210, 0x310, 0, 0x670, 0x770};

static void ref_c2(const uint64_t* tex, const uint64_t* samp, const uint64_t* img, uint8_t* d, uint32_t n) {
    std::memset(d, 0, n);
    auto put = [&](uint32_t off, uint32_t v) { if (off + 4 <= n) std::memcpy(d + off, &v, 4); };
    for (uint32_t i = 0; i < 32 && 0x20 + 8 * i < n; i++) put(0x20 + 8 * i, (uint32_t)tex[i]);
    for (uint32_t i = 0; i < 9 && 0x120 + 8 * i < n; i++) put(0x120 + 8 * i, (uint32_t)img[i]);
    for (uint32_t i = 0; i < 128 && 0x168 + 8 * i < n; i++) put(0x168 + 8 * i, (uint32_t)tex[i]);
    for (uint32_t i = 0; i < 128 && 0x568 + 8 * i < n; i++) put(0x568 + 8 * i, (uint32_t)samp[i]);
}
static void ref_c0(const Buf* ssbo, int stage, uint8_t* d, uint32_t n) {
    std::memset(d, 0, n);
    auto put = [&](uint32_t off, uint32_t v) { if (off + 4 <= n) std::memcpy(d + off, &v, 4); };
    auto entry = [&](uint32_t off, const Buf& e) {
        put(off, (uint32_t)e.addr), put(off + 4, (uint32_t)(e.addr >> 32)), put(off + 8, (uint32_t)e.size);
    };
    if (const uint32_t base = kTable[stage])
        for (uint32_t i = 0; i < 16 && base + 16 * i < n; i++) entry(base + 16 * i, ssbo[i]);
    if (stage == 0) {
        float f = 2047.9375f;
        uint32_t w;
        std::memcpy(&w, &f, 4);
        put(0x610, w);
    }
}

int main() {
    std::mt19937_64 rng(12345);
    uint64_t compared = 0, bad = 0;
    for (int round = 0; round < 40; round++) {
        uint64_t tex[128], samp[128], img[32];
        Buf ssbo[16];
        for (auto& v : tex) v = rng() | (round % 3 == 0 ? 0 : 0xffffffff00000000ull);   // (high words set: they must not leak)
        for (auto& v : samp) v = rng();
        for (auto& v : img) v = rng();
        for (int i = 0; i < 16; i++) ssbo[i] = {i, i, rng(), rng()};
        for (uint32_t n = 0; n <= 0xA00; n += (n < 0x40 || round < 4 ? 1 : 3)) {
            // (a guard after the bank: nothing past n is written)
            std::vector<uint8_t> a(n + 16, 0xA5), b(n + 16, 0xA5), c(n + 16, 0xA5);
            ref_c2(tex, samp, img, a.data(), n);
            mkwvk::bankw::write_c2(tex, samp, img, b.data(), n);
            compared++;
            if (std::memcmp(a.data(), b.data(), n) || std::memcmp(b.data() + n, c.data() + n, 16)) {
                if (bad++ < 5) std::printf("c2 n=%u differs\n", n);
            }
            for (int stage : {0, 1, 2, 3, 4}) {
                ref_c0(ssbo, stage, a.data(), n);
                mkwvk::bankw::write_c0(ssbo, kTable[stage], stage == 0, b.data(), n);
                compared++;
                if (std::memcmp(a.data(), b.data(), n) || std::memcmp(b.data() + n, c.data() + n, 16)) {
                    if (bad++ < 5) std::printf("c0 stage %d n=%u differs\n", stage, n);
                }
            }
        }
    }
    std::printf("bank_write: %llu banks compared, %llu mismatches\n", (unsigned long long)compared, (unsigned long long)bad);
    return bad ? 1 : 0;
}
