// Writes tests/texdecode_astc_vectors.vec: random 16-byte ASTC blocks, each with what ARM's astcenc decodes it to (a 64-bit
// FNV-1a of the 8-bit RGBA output, in the linear and in the sRGB mode) and whether astcenc calls it an error block. Run by
// scripts/gen_texdecode_astc_vectors.py, which builds this against an astcenc you have; astcenc is not part of this repository.
// The blocks are random numbers (a fixed seed, so the file regenerates the same), never game data.
//
// File: "ASTCVEC1", u32 count, then per block 36 bytes: u8 bw, u8 bh, u8 flags (bit 0: astcenc reports an error block in the
// linear mode, bit 1: in the sRGB mode), u8 kind (the enum below, as astcenc classes the block), block[16], u64 sum_linear,
// u64 sum_srgb (little endian).
//
// Two parts. The first is the random blocks, kinds RANDOM .. LEGAL, found by trying random bytes and asking astcenc what each
// turned out to be. The second (kinds VOID_EQ .. WBITS_OVER) is built block by block, because random bytes almost never hit
// these cases, from its own fixed seed after the first part so that the first part is the same bytes as before; astcenc still
// gives every expected value, and the generator stops if astcenc does not answer as the kind says (an error block for the
// kinds that must be one, a decode for the others).
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "astcenc.h"

enum Kind { RANDOM, VOID_OK, VOID_BAD, ERR_BLOCK, HDR_EP, DUAL, PART4, PART23, LEGAL, KINDS,   // (the first part: see below)
            // The second part, each a case the first part does not reach:
            VOID_EQ = KINDS,   // void extent whose low and high coordinate are equal in s or in t (not all four 0x1FFF): illegal
            VOID_RESV,         // LDR void extent whose reserved bits (10 and 11) are not 11, coordinates fine: illegal
            VOID_ONES,         // void extent with all four coordinates 0x1FFF (low == high: the spec allows it): a constant block
            GRID_6X10,         // block modes with a 6x10 or a 10x6 weight grid (the footprints they fit in): legal
            WBITS_OVER,        // block modes whose weights take 97 to 100 bits (96 is the most): illegal
            ALL_KINDS };
static uint64_t s = 0x1234ABCD9E3779B9ull;
static uint64_t rnd() { uint64_t z = (s += 0x9E3779B97F4A7C15ull); z = (z ^ z >> 30) * 0xBF58476D1CE4E5B9ull; z = (z ^ z >> 27) * 0x94D049BB133111EBull; return z ^ z >> 31; }
static uint64_t fnv(const uint8_t* p, size_t n) { uint64_t h = 0xCBF29CE484222325ull; for (size_t i = 0; i < n; i++) h = (h ^ p[i]) * 0x100000001B3ull; return h; }

struct Ctx { astcenc_context* c[3]; unsigned bw, bh; };   // (linear, sRGB, and an HDR-profile context only to class blocks)
static bool decode(astcenc_context* c, const uint8_t* blk, unsigned bw, unsigned bh, uint8_t* out) {
    void* slices[1] = {out};
    astcenc_image img{bw, bh, 1, ASTCENC_TYPE_U8, slices};
    const astcenc_swizzle sw{ASTCENC_SWZ_R, ASTCENC_SWZ_G, ASTCENC_SWZ_B, ASTCENC_SWZ_A};
    const astcenc_error e = astcenc_decompress_image(c, blk, 16, &img, &sw, 0);
    astcenc_decompress_reset(c);
    if (e != ASTCENC_SUCCESS && e != ASTCENC_ERR_BAD_BLOCK) { fprintf(stderr, "astcenc: %s\n", astcenc_get_error_string(e)); exit(1); }
    return e == ASTCENC_ERR_BAD_BLOCK;
}

// ---- the second part: blocks built by hand ----
static void put_bits(uint8_t* b, int pos, int n, uint64_t v) { for (int i = 0; i < n; i++) { uint8_t& by = b[(pos + i) / 8]; const int m = (pos + i) % 8; by = (uint8_t)((by & ~(1 << m)) | ((v >> i & 1) << m)); } }
static uint32_t below(uint32_t n) { return (uint32_t)(rnd() % n); }

// A void extent block: block mode 0x1FC | hdr << 9, bits 10-11 `resv`, four 13-bit coordinates, four random UNORM16 colours
static void void_block(uint8_t* b, int hdr, int resv, uint32_t s0, uint32_t s1, uint32_t t0, uint32_t t1) {
    for (int i = 0; i < 16; i += 8) { uint64_t v = rnd(); memcpy(b + i, &v, 8); }
    put_bits(b, 0, 9, 0x1FC); put_bits(b, 9, 1, (uint64_t)hdr); put_bits(b, 10, 2, (uint64_t)resv);
    put_bits(b, 12, 13, s0); put_bits(b, 25, 13, s1); put_bits(b, 38, 13, t0); put_bits(b, 51, 13, t1);
}
// A pair of 13-bit coordinates, low < high, neither pair all ones
static void ascending(uint32_t& lo, uint32_t& hi) { lo = below(0x1FFF); hi = lo + 1 + below(0x1FFF - lo); }

// The weight grid, quantisation and plane count of a block mode for a 2D footprint, from the spec's block mode table (ASTC
// chapter of the Khronos Data Format spec), written out here only to aim at the modes the second part wants; astcenc says what
// they decode to. false for a reserved mode. Returns the bits the weights take (the integer sequence's size).
static int ise_bits(int count, int q) {   // (quant levels 2..256 as bits + trits + quints)
    static const int bits[21] = {1, 0, 2, 0, 1, 3, 1, 2, 4, 2, 3, 5, 3, 4, 6, 4, 5, 7, 5, 6, 8}, trit[21] = {0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0},
        quint[21] = {0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0};
    return count * bits[q] + (trit[q] ? (8 * count + 4) / 5 : 0) + (quint[q] ? (7 * count + 2) / 3 : 0);
}
static bool mode_grid(unsigned m, int& wx, int& wy, int& dual, int& wbits) {
    unsigned r = m >> 4 & 1, h = m >> 9 & 1, d = m >> 10 & 1, a = m >> 5 & 3;
    if (m & 3) {
        r |= (m & 3) << 1;
        unsigned b = m >> 7 & 3;
        switch (m >> 2 & 3) {
        case 0: wx = b + 4; wy = a + 2; break;
        case 1: wx = b + 8; wy = a + 2; break;
        case 2: wx = a + 2; wy = b + 8; break;
        default: b &= 1; if (m & 0x100) { wx = b + 2; wy = a + 2; } else { wx = a + 2; wy = b + 6; } break;
        }
    } else {
        r |= (m >> 2 & 3) << 1;
        if ((m >> 2 & 3) == 0) return false;
        const unsigned b = m >> 9 & 3;
        switch (m >> 7 & 3) {
        case 0: wx = 12; wy = a + 2; break;
        case 1: wx = a + 2; wy = 12; break;
        case 2: wx = a + 6; wy = b + 6; d = h = 0; break;
        default: if (a == 0) { wx = 6; wy = 10; } else if (a == 1) { wx = 10; wy = 6; } else return false; break;
        }
    }
    dual = (int)d;
    const int q = (int)r - 2 + 6 * (int)h;
    if (q < 0 || q > 20) return false;
    wbits = ise_bits(wx * wy * (dual + 1), q);
    return wx * wy * (dual + 1) <= 64;
}
// A block of block mode m, one partition, an LDR colour mode from `cems` (few colour values, so that the colour bits left after
// the weights are enough: the block is not an error block for any reason but the weights'), everything else random
static void mode_block(uint8_t* b, unsigned m, const int* cems, int ncems) {
    for (int i = 0; i < 16; i += 8) { uint64_t v = rnd(); memcpy(b + i, &v, 8); }
    put_bits(b, 0, 11, m); put_bits(b, 11, 2, 0); put_bits(b, 13, 4, (uint64_t)cems[below((uint32_t)ncems)]);
}

int main(int argc, char** argv) {
    if (argc != 2) { fprintf(stderr, "usage: gen out.bin\n"); return 2; }
    static const int fp[][2] = {{4,4},{5,4},{5,5},{6,5},{6,6},{8,5},{8,6},{8,8},{10,5},{10,6},{10,8},{10,10},{12,10},{12,12}};
    const int RANDOM_N = 100, PER_KIND = 12, PER_LEGAL = 100;   // (RANDOM: bytes as they came, mostly illegal; LEGAL: random, legal, plain)
    std::vector<uint8_t> file = {'A','S','T','C','V','E','C','1', 0, 0, 0, 0};
    uint32_t count = 0;
    long made[ALL_KINDS] = {};
    for (auto& f : fp) {
        const unsigned bw = f[0], bh = f[1];
        Ctx x{{}, bw, bh};
        const astcenc_profile prof[3] = {ASTCENC_PRF_LDR, ASTCENC_PRF_LDR_SRGB, ASTCENC_PRF_HDR};
        for (int m = 0; m < 3; m++) {
            astcenc_config cfg;
            if (astcenc_config_init(prof[m], bw, bh, 1, ASTCENC_PRE_FASTEST, ASTCENC_FLG_DECOMPRESS_ONLY | (m < 2 ? ASTCENC_FLG_USE_DECODE_UNORM8 : 0u), &cfg) ||
                astcenc_context_alloc(&cfg, 1, &x.c[m], nullptr)) { fprintf(stderr, "astcenc init failed\n"); return 1; }
        }
        int have[ALL_KINDS] = {};
        for (long tries = 0; tries < 4000000; tries++) {
            uint8_t b[16];
            for (int i = 0; i < 16; i += 8) { uint64_t v = rnd(); memcpy(b + i, &v, 8); }
            const int want = tries < RANDOM_N ? RANDOM : 1 + (int)(rnd() % (KINDS - 1));   // (a kind to aim at)
            switch (want) {   // bits forced to make the kind likely; astcenc says what the block turned out to be
            case VOID_OK: b[0] = 0xFC; b[1] = (b[1] & 0xF0) | 0x0D; if (rnd() & 1) memset(b + 2, 0xFF, 6); break;
            case VOID_BAD: b[0] = 0xFC; b[1] = (b[1] & 0xF0) | (rnd() & 1 ? 0x0F : 0x0D); if (rnd() & 1) b[1] = (b[1] & 0xF0) | 0x03; break;
            case ERR_BLOCK: if (rnd() & 1) b[0] &= 0xF0; else b[1] |= 0x1C; break;   // (a reserved block mode; dual plane with 4 partitions)
            case HDR_EP: { static const int h[6] = {2, 3, 7, 11, 14, 15}; b[1] &= ~0x18; b[1] &= ~0x04; const int c = h[rnd() % 6]; b[1] = (b[1] & ~0xE0) | ((c & 7) << 5); b[2] = (b[2] & ~1) | (c >> 3 & 1); break; }
            case DUAL: b[1] |= 0x04; break;
            case PART4: b[1] |= 0x18; break;
            case PART23: b[1] = (b[1] & ~0x18) | (rnd() & 1 ? 0x08 : 0x10); break;
            default: break;
            }
            uint8_t out[2][576];
            const bool bad0 = decode(x.c[0], b, bw, bh, out[0]), bad1 = decode(x.c[1], b, bw, bh, out[1]);
            astcenc_block_info info;
            if (astcenc_get_block_info(x.c[0], b, &info)) { fprintf(stderr, "block info failed\n"); return 1; }
            astcenc_block_info hinfo;   // (the LDR profile calls a block with an HDR endpoint mode an error block: ask the HDR one)
            if (astcenc_get_block_info(x.c[2], b, &hinfo)) { fprintf(stderr, "block info failed\n"); return 1; }
            int kind;
            if (b[0] == 0xFC && (b[1] & 1)) kind = bad0 ? VOID_BAD : VOID_OK;   // (void extent: block mode bits 0-8 are 0x1FC)
            else if (bad0) kind = !hinfo.is_error_block && hinfo.is_hdr_block && !hinfo.is_constant_block ? HDR_EP : ERR_BLOCK;
            else if (info.is_dual_plane_block) kind = DUAL;
            else if (info.partition_count == 4) kind = PART4;
            else if (info.partition_count > 1) kind = PART23;
            else kind = LEGAL;
            if (tries < RANDOM_N) kind = RANDOM;                         // (the random ones are recorded as they came)
            else if (kind == RANDOM || have[kind] >= (kind == LEGAL ? PER_LEGAL : PER_KIND)) continue;
            have[kind]++;
            made[kind]++;
            file.insert(file.end(), {(uint8_t)bw, (uint8_t)bh, (uint8_t)(bad0 | bad1 << 1), (uint8_t)kind});
            file.insert(file.end(), b, b + 16);
            for (int m = 0; m < 2; m++) { const uint64_t h = fnv(out[m], bw * bh * 4); for (int i = 0; i < 8; i++) file.push_back((uint8_t)(h >> (8 * i))); }
            count++;
            bool done = true;
            for (int k = 1; k < KINDS; k++) done = done && have[k] >= (k == LEGAL ? PER_LEGAL : PER_KIND);
            if (done && tries >= RANDOM_N) break;
        }
        for (int m = 0; m < 3; m++) astcenc_context_free(x.c[m]);
    }
    // ---- the second part (see the top of the file) ----
    s = 0x5EED0F0B10C4ull;   // (a seed of its own: the first part above is unchanged by this part)
    long made2[ALL_KINDS] = {};
    int seen_wbits[101] = {};
    int seen_grid[2] = {};
    for (auto& f : fp) {
        const unsigned bw = f[0], bh = f[1];
        astcenc_context* c[2];
        for (int m = 0; m < 2; m++) {
            astcenc_config cfg;
            if (astcenc_config_init(m ? ASTCENC_PRF_LDR_SRGB : ASTCENC_PRF_LDR, bw, bh, 1, ASTCENC_PRE_FASTEST, ASTCENC_FLG_DECOMPRESS_ONLY | ASTCENC_FLG_USE_DECODE_UNORM8, &cfg) ||
                astcenc_context_alloc(&cfg, 1, &c[m], nullptr)) { fprintf(stderr, "astcenc init failed\n"); return 1; }
        }
        auto add = [&](int kind, const uint8_t* b, bool must_err) {
            uint8_t out[2][576];
            const bool bad0 = decode(c[0], b, bw, bh, out[0]), bad1 = decode(c[1], b, bw, bh, out[1]);
            if (bad0 != must_err || bad1 != must_err) {
                fprintf(stderr, "astcenc %s kind %d (%ux%u) block that must %sbe an error block\n", bad0 ? "reports" : "does not report", kind, bw, bh, must_err ? "" : "not ");
                exit(1);
            }
            file.insert(file.end(), {(uint8_t)bw, (uint8_t)bh, (uint8_t)(bad0 | bad1 << 1), (uint8_t)kind});
            file.insert(file.end(), b, b + 16);
            for (int m = 0; m < 2; m++) { const uint64_t h = fnv(out[m], bw * bh * 4); for (int i = 0; i < 8; i++) file.push_back((uint8_t)(h >> (8 * i))); }
            count++;
            made2[kind]++;
        };
        uint8_t b[16];
        for (int i = 0; i < 12; i++) {   // void extent, low == high: s, t, both, or 0x1FFF in s with t fine (so not all four ones)
            uint32_t s0, s1, t0, t1;
            ascending(s0, s1); ascending(t0, t1);
            const int v = i % 4;
            if (v == 0 || v == 2) s1 = s0;
            if (v == 1 || v == 2) t1 = t0;
            if (v == 3) s0 = s1 = 0x1FFF;
            void_block(b, 0, 3, s0, s1, t0, t1);
            add(VOID_EQ, b, true);
        }
        for (int i = 0; i < 12; i++) {   // void extent, reserved bits 00, 01, 10, coordinates fine
            uint32_t s0, s1, t0, t1;
            ascending(s0, s1); ascending(t0, t1);
            void_block(b, 0, i % 3, s0, s1, t0, t1);
            add(VOID_RESV, b, true);
        }
        for (int i = 0; i < 6; i++) { void_block(b, 0, 3, 0x1FFF, 0x1FFF, 0x1FFF, 0x1FFF); add(VOID_ONES, b, false); }
        {   // 6x10 and 10x6 weight grids: block mode bits 0-1 = 00, bits 2-3 = 01 (r = 2 | bit 4: 2 or 3 -> 1 bit a weight, or trits), bits 7-8 = 11
            // (a = bits 5-6: 0 is 6x10, 1 is 10x6), bit 9 = 0, bit 10 = 0 (one plane): 60 weights, 60 or 96 bits, the only two that are legal
            static const int ldr[2] = {0, 5};   // (colour modes with 2 and 4 values)
            for (unsigned a = 0; a < 2; a++) for (unsigned r0 = 0; r0 < 2; r0++) {
                const unsigned m = 1u << 2 | r0 << 4 | a << 5 | 3u << 7;
                int wx, wy, dual, wbits;
                if (!mode_grid(m, wx, wy, dual, wbits) || wx != (a ? 10 : 6) || wy != (a ? 6 : 10) || wbits < 24 || wbits > 96) { fprintf(stderr, "grid mode %x is not what the table says\n", m); return 1; }
                if (wx > (int)bw || wy > (int)bh) continue;
                for (int i = 0; i < 6; i++) { mode_block(b, m, ldr, 2); add(GRID_6X10, b, false); seen_grid[a]++; }
            }
        }
        {   // every block mode whose weights take 97 to 100 bits and that fits the footprint: illegal, and for no other reason
            static const int ldr[2] = {0, 1};   // (two colour values: the 11 to 14 bits left over are enough)
            for (unsigned m = 0; m < 2048; m++) {
                if ((m & 0x1FF) == 0x1FC) continue;
                int wx, wy, dual, wbits;
                if (!mode_grid(m, wx, wy, dual, wbits) || wbits < 97 || wbits > 100 || wx > (int)bw || wy > (int)bh) continue;
                mode_block(b, m, ldr, 2);
                add(WBITS_OVER, b, true);
                seen_wbits[wbits]++;
            }
        }
        for (int m = 0; m < 2; m++) astcenc_context_free(c[m]);
    }
    for (int w = 97; w <= 100; w++) if (!seen_wbits[w]) { fprintf(stderr, "no block with %d weight bits\n", w); return 1; }
    if (!seen_grid[0] || !seen_grid[1]) { fprintf(stderr, "no 6x10 or no 10x6 block\n"); return 1; }
    for (int k = KINDS; k < ALL_KINDS; k++) made[k] = made2[k];
    memcpy(&file[8], &count, 4);   // (little endian hosts only: the generator runs on one)
    FILE* o = fopen(argv[1], "wb");
    if (!o || fwrite(file.data(), 1, file.size(), o) != file.size() || fclose(o)) { perror(argv[1]); return 1; }
    printf("%u blocks, %zu bytes; by kind: random %ld, void ok %ld, void bad %ld, error %ld, hdr endpoints %ld, dual plane %ld, 4 partitions %ld, 2-3 partitions %ld, legal plain %ld, "
           "void low == high %ld, void reserved bits %ld, void all ones %ld, 6x10 / 10x6 %ld, weights over 96 bits %ld\n",
           count, file.size(), made[0], made[1], made[2], made[3], made[4], made[5], made[6], made[7], made[8], made[9], made[10], made[11], made[12], made[13]);
}
