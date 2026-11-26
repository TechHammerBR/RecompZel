// Decodes the blocks in argv[1] (one per line: name, width, height, 16 block bytes in hex, bw*bh*4 expected bytes in hex: what ARM's
// astcenc 6.0.0 gives) with renderer_cpu_astc_decode() below and compares texel by texel. Two verdicts, so that a cause is not blamed
// for the other's difference: "within one step" (every channel of every texel at most 1 from astcenc's: the multi-partition fault the
// renderer's earlier decoder, suyu's, had breaks it; see test_texdecode_astc_partitions.py) and "exact" (a rounding convention: suyu
// rounded the 16-bit result to 8 bits, astcenc and texdecode take its top 8 bits). Exit 0 when both hold for every block, 1 otherwise,
// 2 for a bad input file.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <span>
#include <sstream>
#include <string>
#include <vector>
#if defined(DECODER_SUYU)
#include "video_core/textures/astc.h"
#else
#include "texdecode/texdecode.h"
#endif

// The renderer's CPU ASTC decode of a level, as vk_texture.cpp calls it (linear mode): here a level of one block, one 16-byte block into
// bw * bh RGBA texels, rows of bw texels. A block astcenc takes as legal must not count as an error block.
static void renderer_cpu_astc_decode(const uint8_t block[16], unsigned bw, unsigned bh, uint8_t* rgba) {
#if defined(DECODER_SUYU)   // (the decoder main used before: tests/test_texdecode_astc_partitions.py --decoder suyu)
    Tegra::Texture::ASTC::DecompressSerial(std::span<const uint8_t>(block, 16), bw, bh, 1, bw, bh, std::span<uint8_t>(rgba, (size_t)bw * bh * 4));
    return;
#else
    const int64_t errors = mkwvk::texdecode::astc_decode(std::span<const uint8_t>(block, 16), bw, bh, 1, bw, bh, false,
                                                         std::span<uint8_t>(rgba, (size_t)bw * bh * 4),
                                                         mkwvk::texdecode::Rgba8{0, 0, 0, 0});   // (vk_texture.cpp's error colour)
    if (errors != 0) {
        fprintf(stderr, "astc_decode returned %lld for a legal block\n", (long long)errors);
        exit(2);
    }
#endif
}

static bool unhex(const std::string& s, std::vector<uint8_t>& out) {
    if (s.size() % 2) return false;
    out.clear();
    for (size_t i = 0; i < s.size(); i += 2) {
        char* end;
        const std::string two = s.substr(i, 2);
        const long v = strtol(two.c_str(), &end, 16);
        if (*end || two[0] == '-' || two[0] == '+') return false;
        out.push_back((uint8_t)v);
    }
    return true;
}

int main(int argc, char** argv) {
    if (argc != 2) { fprintf(stderr, "usage: test blocks.txt\n"); return 2; }
    std::ifstream in(argv[1]);
    if (!in) { perror(argv[1]); return 2; }
    int blocks = 0, not_close = 0, not_exact = 0;
    for (std::string line; std::getline(in, line);) {
        if (line.empty()) continue;
        std::istringstream ls(line);
        std::string name, bhex, ehex;
        unsigned bw, bh;
        std::vector<uint8_t> blk, want;
        if (!(ls >> name >> bw >> bh >> bhex >> ehex) || bw < 4 || bw > 12 || bh < 4 || bh > 12 || !unhex(bhex, blk) || !unhex(ehex, want) ||
            blk.size() != 16 || want.size() != (size_t)bw * bh * 4) {
            fprintf(stderr, "bad line: %s\n", line.c_str());
            return 2;
        }
        std::vector<uint8_t> got((size_t)bw * bh * 4, 0xA5);
        renderer_cpu_astc_decode(blk.data(), bw, bh, got.data());
        blocks++;
        int worst = 0, bad_texels = 0, first = -1;
        for (unsigned t = 0; t < bw * bh; t++) {
            int m = 0;
            for (int c = 0; c < 4; c++) m = std::max(m, abs((int)got[t * 4 + c] - (int)want[t * 4 + c]));
            worst = std::max(worst, m);
            if (m > 1) { bad_texels++; if (first < 0) first = (int)t; }
        }
        const bool exact = got == want;
        if (worst > 1) not_close++;
        if (!exact) not_exact++;
        printf("%-34s %2ux%-2u largest channel difference from astcenc %3d, %2d of %3u texels more than one step off%s\n", name.c_str(), bw, bh, worst,
               bad_texels, bw * bh, exact ? ", exact" : "");
        if (first >= 0) {
            const unsigned t = (unsigned)first;
            printf("    first: texel (%u,%u) is %02x%02x%02x%02x, astcenc says %02x%02x%02x%02x\n", t % bw, t / bw, got[t * 4], got[t * 4 + 1], got[t * 4 + 2],
                   got[t * 4 + 3], want[t * 4], want[t * 4 + 1], want[t * 4 + 2], want[t * 4 + 3]);
        }
    }
    if (!blocks) { fprintf(stderr, "no blocks\n"); return 2; }
    printf("%d blocks: %d more than one step from astcenc, %d not exactly astcenc's\n", blocks, not_close, not_exact);
    return not_close || not_exact;
}
