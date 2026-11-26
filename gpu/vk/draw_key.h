// The draw path's questions that are answered from their arguments alone (vk_draw.cpp): whether a draw's pipeline, dynamic
// state, vertex streams, index buffer and pushed descriptors are the ones before it, whether it writes a target its pass
// sampled, what NVN's values are in Vulkan, and a graphics pipeline's key from the words baked into it. They take scalars,
// arrays and plain structs, call no Vulkan function, write no log and read no global, thread-local, switch or device:
// nothing here needs a device, so the checks in tests/ include this header and run them, where they used to cut each one out
// of vk_draw.cpp by its text. Inline: each is in a draw's hot path. Only Vulkan's headers (for its types), NVN's (for its
// constants) and the standard library.
//
// The keys pipeline_key() makes are kept on players' disks (the pipeline state list, the predicted keys, the notes): a change
// to mix() or to what pipeline_key() mixes, or in which order, makes every one of them a key nothing asks for.
// tests/test_pipeline_key_values.py holds keys worked out apart from this file; nx2/bake.py restates the chain in Python.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

#include <vulkan/vulkan_core.h>

#include "../render/nvn_api.h"   // (NVN's constants: C)

namespace mkwvk {

// ---- NVN state to Vulkan ----
inline VkCompareOp compare_op(uint32_t f) {
    return f >= 1 && f <= 8 ? (VkCompareOp)(f - 1) : VK_COMPARE_OP_ALWAYS;   // (NEVER = 1 .. ALWAYS = 8)
}
inline VkStencilOp stencil_op(uint32_t o) {
    return o >= 1 && o <= 8 ? (VkStencilOp)(o - 1) : VK_STENCIL_OP_KEEP;   // (KEEP = 1 .. DECR_WRAP = 8)
}
inline int topology_class(VkPrimitiveTopology t) {
    switch (t) {
    case VK_PRIMITIVE_TOPOLOGY_POINT_LIST: return 0;
    case VK_PRIMITIVE_TOPOLOGY_LINE_LIST: case VK_PRIMITIVE_TOPOLOGY_LINE_STRIP:
    case VK_PRIMITIVE_TOPOLOGY_LINE_LIST_WITH_ADJACENCY: case VK_PRIMITIVE_TOPOLOGY_LINE_STRIP_WITH_ADJACENCY: return 1;
    case VK_PRIMITIVE_TOPOLOGY_PATCH_LIST: return 3;
    default: return 2;
    }
}
inline VkBlendFactor blend_factor(uint32_t f) {
    switch (f) {
    case NVN_BLEND_FUNC_ZERO: return VK_BLEND_FACTOR_ZERO;
    case NVN_BLEND_FUNC_ONE: return VK_BLEND_FACTOR_ONE;
    case NVN_BLEND_FUNC_SRC_COLOR: return VK_BLEND_FACTOR_SRC_COLOR;
    case NVN_BLEND_FUNC_ONE_MINUS_SRC_COLOR: return VK_BLEND_FACTOR_ONE_MINUS_SRC_COLOR;
    case NVN_BLEND_FUNC_SRC_ALPHA: return VK_BLEND_FACTOR_SRC_ALPHA;
    case NVN_BLEND_FUNC_ONE_MINUS_SRC_ALPHA: return VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA;
    case NVN_BLEND_FUNC_DST_ALPHA: return VK_BLEND_FACTOR_DST_ALPHA;
    case NVN_BLEND_FUNC_ONE_MINUS_DST_ALPHA: return VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA;
    case NVN_BLEND_FUNC_DST_COLOR: return VK_BLEND_FACTOR_DST_COLOR;
    case NVN_BLEND_FUNC_ONE_MINUS_DST_COLOR: return VK_BLEND_FACTOR_ONE_MINUS_DST_COLOR;
    case NVN_BLEND_FUNC_SRC_ALPHA_SATURATE: return VK_BLEND_FACTOR_SRC_ALPHA_SATURATE;
    case NVN_BLEND_FUNC_CONSTANT_COLOR: return VK_BLEND_FACTOR_CONSTANT_COLOR;
    case NVN_BLEND_FUNC_CONSTANT_ALPHA: return VK_BLEND_FACTOR_CONSTANT_ALPHA;
    case NVN_BLEND_FUNC_ONE_MINUS_CONSTANT_COLOR: return VK_BLEND_FACTOR_ONE_MINUS_CONSTANT_COLOR;
    case NVN_BLEND_FUNC_ONE_MINUS_CONSTANT_ALPHA: return VK_BLEND_FACTOR_ONE_MINUS_CONSTANT_ALPHA;
    case NVN_BLEND_FUNC_SRC1_COLOR: return VK_BLEND_FACTOR_SRC1_COLOR;
    case NVN_BLEND_FUNC_SRC1_ALPHA: return VK_BLEND_FACTOR_SRC1_ALPHA;
    case NVN_BLEND_FUNC_ONE_MINUS_SRC1_COLOR: return VK_BLEND_FACTOR_ONE_MINUS_SRC1_COLOR;
    case NVN_BLEND_FUNC_ONE_MINUS_SRC1_ALPHA: return VK_BLEND_FACTOR_ONE_MINUS_SRC1_ALPHA;
    default: return VK_BLEND_FACTOR_ONE;
    }
}
inline VkBlendOp blend_op(uint32_t e) {
    switch (e) {
    case NVN_BLEND_EQUATION_SUB: return VK_BLEND_OP_SUBTRACT;
    case NVN_BLEND_EQUATION_REVERSE_SUB: return VK_BLEND_OP_REVERSE_SUBTRACT;
    case NVN_BLEND_EQUATION_MIN: return VK_BLEND_OP_MIN;
    case NVN_BLEND_EQUATION_MAX: return VK_BLEND_OP_MAX;
    default: return VK_BLEND_OP_ADD;
    }
}
/// Vulkan topology (false: one Vulkan has none of: quads, quad strips, polygons, line loops)
inline bool topology(int prim, VkPrimitiveTopology& t) {
    switch (prim) {
    case NVN_DRAW_PRIMITIVE_POINTS: t = VK_PRIMITIVE_TOPOLOGY_POINT_LIST; return true;
    case NVN_DRAW_PRIMITIVE_LINES: t = VK_PRIMITIVE_TOPOLOGY_LINE_LIST; return true;
    case NVN_DRAW_PRIMITIVE_LINE_STRIP: t = VK_PRIMITIVE_TOPOLOGY_LINE_STRIP; return true;
    case NVN_DRAW_PRIMITIVE_TRIANGLES: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST; return true;
    case NVN_DRAW_PRIMITIVE_TRIANGLE_STRIP: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP; return true;
    case NVN_DRAW_PRIMITIVE_TRIANGLE_FAN: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_FAN; return true;
    case NVN_DRAW_PRIMITIVE_POLYGON: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_FAN; return true;
    case NVN_DRAW_PRIMITIVE_LINES_ADJACENCY: t = VK_PRIMITIVE_TOPOLOGY_LINE_LIST_WITH_ADJACENCY; return true;
    case NVN_DRAW_PRIMITIVE_LINE_STRIP_ADJACENCY: t = VK_PRIMITIVE_TOPOLOGY_LINE_STRIP_WITH_ADJACENCY; return true;
    case NVN_DRAW_PRIMITIVE_TRIANGLES_ADJACENCY: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST_WITH_ADJACENCY; return true;
    case NVN_DRAW_PRIMITIVE_TRIANGLE_STRIP_ADJACENCY: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP_WITH_ADJACENCY; return true;
    case NVN_DRAW_PRIMITIVE_PATCHES: t = VK_PRIMITIVE_TOPOLOGY_PATCH_LIST; return true;   // (draw() says so in the log)
    case NVN_DRAW_PRIMITIVE_QUADS: t = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST; return true;   // (indices made: draw())
    default: return false;
    }
}
/// NVN vertex attribute format -> Vulkan (gpu/render/rx_draw.cpp nvn_attribute's table)
inline VkFormat vertex_format(int f) {
    static const VkFormat r8[] = {VK_FORMAT_R8_UNORM, VK_FORMAT_R8_SNORM, VK_FORMAT_R8_UINT, VK_FORMAT_R8_SINT};
    static const VkFormat r16[] = {VK_FORMAT_R16_SFLOAT, VK_FORMAT_R16_UNORM, VK_FORMAT_R16_SNORM, VK_FORMAT_R16_UINT, VK_FORMAT_R16_SINT};
    static const VkFormat r32[] = {VK_FORMAT_R32_SFLOAT, VK_FORMAT_R32_UINT, VK_FORMAT_R32_SINT};
    static const VkFormat rg8[] = {VK_FORMAT_R8G8_UNORM, VK_FORMAT_R8G8_SNORM, VK_FORMAT_R8G8_UINT, VK_FORMAT_R8G8_SINT};
    static const VkFormat rg16[] = {VK_FORMAT_R16G16_SFLOAT, VK_FORMAT_R16G16_UNORM, VK_FORMAT_R16G16_SNORM, VK_FORMAT_R16G16_UINT, VK_FORMAT_R16G16_SINT};
    static const VkFormat rg32[] = {VK_FORMAT_R32G32_SFLOAT, VK_FORMAT_R32G32_UINT, VK_FORMAT_R32G32_SINT};
    static const VkFormat rgb8[] = {VK_FORMAT_R8G8B8_UNORM, VK_FORMAT_R8G8B8_SNORM, VK_FORMAT_R8G8B8_UINT, VK_FORMAT_R8G8B8_SINT};
    static const VkFormat rgb16[] = {VK_FORMAT_R16G16B16_SFLOAT, VK_FORMAT_R16G16B16_UNORM, VK_FORMAT_R16G16B16_SNORM, VK_FORMAT_R16G16B16_UINT, VK_FORMAT_R16G16B16_SINT};
    static const VkFormat rgb32[] = {VK_FORMAT_R32G32B32_SFLOAT, VK_FORMAT_R32G32B32_UINT, VK_FORMAT_R32G32B32_SINT};
    static const VkFormat rgba8[] = {VK_FORMAT_R8G8B8A8_UNORM, VK_FORMAT_R8G8B8A8_SNORM, VK_FORMAT_R8G8B8A8_UINT, VK_FORMAT_R8G8B8A8_SINT};
    static const VkFormat rgba16[] = {VK_FORMAT_R16G16B16A16_SFLOAT, VK_FORMAT_R16G16B16A16_UNORM, VK_FORMAT_R16G16B16A16_SNORM, VK_FORMAT_R16G16B16A16_UINT, VK_FORMAT_R16G16B16A16_SINT};
    static const VkFormat rgba32[] = {VK_FORMAT_R32G32B32A32_SFLOAT, VK_FORMAT_R32G32B32A32_UINT, VK_FORMAT_R32G32B32A32_SINT};
    static const struct { int lo; const VkFormat* f; } ranges[] = {
        {0x01, r8}, {0x05, r16}, {0x0A, r32}, {0x0D, rg8}, {0x11, rg16}, {0x16, rg32},
        {0x19, rgb8}, {0x1D, rgb16}, {0x22, rgb32}, {0x25, rgba8}, {0x29, rgba16}, {0x2E, rgba32}};
    static const int counts[] = {4, 5, 3, 4, 5, 3, 4, 5, 3, 4, 5, 3};
    for (int i = 0; i < 12; i++)
        if (f >= ranges[i].lo && f < ranges[i].lo + counts[i]) return ranges[i].f[f - ranges[i].lo];
    if (f >= 0x51 && f <= 0x68) {   // (*_UI2F / *_I2F: integers converted to float by the shader (UnsignedScaled /
        // SignedScaled attributes): the 32-bit ones were read as float bits before, and R32 has no scaled format)
        static const VkFormat us[12] = {VK_FORMAT_R8_UINT, VK_FORMAT_R16_UINT, VK_FORMAT_R32_UINT, VK_FORMAT_R8G8_UINT,
                                        VK_FORMAT_R16G16_UINT, VK_FORMAT_R32G32_UINT, VK_FORMAT_R8G8B8_UINT,
                                        VK_FORMAT_R16G16B16_UINT, VK_FORMAT_R32G32B32_UINT, VK_FORMAT_R8G8B8A8_UINT,
                                        VK_FORMAT_R16G16B16A16_UINT, VK_FORMAT_R32G32B32A32_UINT};
        static const VkFormat ss[12] = {VK_FORMAT_R8_SINT, VK_FORMAT_R16_SINT, VK_FORMAT_R32_SINT, VK_FORMAT_R8G8_SINT,
                                        VK_FORMAT_R16G16_SINT, VK_FORMAT_R32G32_SINT, VK_FORMAT_R8G8B8_SINT,
                                        VK_FORMAT_R16G16B16_SINT, VK_FORMAT_R32G32B32_SINT, VK_FORMAT_R8G8B8A8_SINT,
                                        VK_FORMAT_R16G16B16A16_SINT, VK_FORMAT_R32G32B32A32_SINT};
        return (((f - 0x51) & 1) ? ss : us)[(f - 0x51) / 2];
    }
    switch (f) {
    case NVN_FORMAT_RGB10A2: return VK_FORMAT_A2B10G10R10_UNORM_PACK32;
    case NVN_FORMAT_RGB10A2UI: return VK_FORMAT_A2B10G10R10_UINT_PACK32;
    case NVN_FORMAT_RGB10A2SN: return VK_FORMAT_A2B10G10R10_SNORM_PACK32;
    case NVN_FORMAT_RGB10A2I: return VK_FORMAT_A2B10G10R10_SINT_PACK32;
    case NVN_FORMAT_RGB10A2_UI2F: return VK_FORMAT_A2B10G10R10_UINT_PACK32;
    case NVN_FORMAT_RGB10A2_I2F: return VK_FORMAT_A2B10G10R10_SINT_PACK32;
    case NVN_FORMAT_R11G11B10F: return VK_FORMAT_B10G11R11_UFLOAT_PACK32;
    case NVN_FORMAT_BGRA8: case NVN_FORMAT_BGRX8: return VK_FORMAT_B8G8R8A8_UNORM;
    case NVN_FORMAT_RGBX8: return VK_FORMAT_R8G8B8A8_UNORM;
    default: return VK_FORMAT_UNDEFINED;
    }
}

// ---- pipelines ----
inline uint64_t mix(uint64_t h, uint64_t v) {
    h ^= v + 0x9e3779b97f4a7c15ull + (h << 6) + (h >> 2);
    return h * 0xff51afd7ed558ccdull;
}

/// What is baked into a graphics pipeline, as the words its key is made of (vk_draw.cpp key_inputs reads them out of the
/// program, the state, the targets and the device). 64-bit words hold values already cast as the key mixes them
struct KeyInputs {
    uint64_t prog = 0, variant = 0;          // (Program::key and Program::variant)
    uint64_t topo_class = 0, samples = 0;    // (topology_class of the pipeline's topology; the targets' sample count)
    bool vertex_input = false;               // (neither a mesh program nor the mesh fallback's: the four below are in the key)
    uint32_t loads = 0;                      // (bit i: the vertex stage loads generic attribute i)
    uint64_t vattr[16]{};                    // (NvnState::vattr)
    int nvattr = 0;
    uint64_t divisor[16]{};                  // (each vertex stream's)
    int n = 0;                               // (colour targets: 0 to 8)
    uint64_t color_format[8]{}, depth_format = 0;   // (VkFormat)
    uint64_t blend[8]{};                     // (each target's blend state, the 8 bytes of nvn_blend_st)
    uint64_t blend_en = 0;                   // (bit i: target i blends)
    uint64_t write_masks = 0;                // (4 bits a target: target_write_mask)
    uint64_t poly_mode = 0, depth_clamp = 0, a2c = 0;
    // (what the device sets as dynamic state is not in the key)
    bool eds3_blend = false, eds3_polygon = false, eds3_clamp = false, eds3_a2c = false;
};
/// A graphics pipeline's key from a seed of the caller's (hookshot: the ledger's is the program's fingerprint, vk_draw.cpp
/// pipeline_key_from); pipeline_key's seed is the program's key and variant. 0: more colour targets than a pipeline has
inline uint64_t pipeline_key_seeded(const KeyInputs& k, uint64_t seed) {
    if (k.n < 0 || k.n > 8) return 0;   // (hookshot: at most 8 colour targets)
    uint64_t key = mix(seed, k.topo_class << 8 | k.samples);
    if (k.vertex_input) {
        for (int i = 0; i < 16; i++)
            if (k.loads >> i & 1) key = mix(key, k.vattr[i] << 8 | (i < k.nvattr));
        for (int i = 0; i < 16; i++) key = mix(key, k.divisor[i]);
    }
    for (int i = 0; i < k.n; i++) {
        key = mix(key, k.color_format[i]);
        if (!k.eds3_blend) key = mix(key, (k.blend_en >> i & 1) ? k.blend[i] : 0);
    }
    key = mix(key, k.depth_format);
    if (!k.eds3_blend) key = mix(key, k.write_masks << 8 | k.blend_en);
    if (!k.eds3_polygon) key = mix(key, k.poly_mode);
    if (!k.eds3_clamp) key = mix(key, k.depth_clamp);
    if (!k.eds3_a2c) key = mix(key, k.a2c);
    return key;
}
/// A graphics pipeline's key: what is baked into it (the rest is dynamic state). 0: more colour targets than a pipeline has
inline uint64_t pipeline_key(const KeyInputs& k) { return pipeline_key_seeded(k, mix(k.prog, k.variant)); }

/// What a graphics pipeline was built from, so the next draw of the same material does not hash it again
inline bool pipe_same(uint64_t prog, uint64_t variant, int topo, uint32_t samples, int n, uint32_t depth, const uint32_t* formats,
                      int nvattr, const uint32_t* vattr, const uint32_t* div, uint32_t blend_en, const uint64_t* blend,
                      uint32_t chmask, uint32_t poly, uint32_t clamp, uint32_t a2c, uint64_t cprog, uint64_t cvariant, int ctopo,
                      uint32_t csamples, int cn, uint32_t cdepth, const uint32_t* cformats, int cnvattr, const uint32_t* cvattr,
                      const uint32_t* cdiv, uint32_t cblend_en, const uint64_t* cblend, uint32_t cchmask, uint32_t cpoly,
                      uint32_t cclamp, uint32_t ca2c) {
    if (prog != cprog || variant != cvariant || topo != ctopo || samples != csamples || n != cn || depth != cdepth ||
        nvattr != cnvattr || blend_en != cblend_en || chmask != cchmask || poly != cpoly || clamp != cclamp || a2c != ca2c)
        return false;
    for (int i = 0; i < 8; i++)
        if (formats[i] != cformats[i] || blend[i] != cblend[i]) return false;
    for (int i = 0; i < 16; i++)
        if (vattr[i] != cvattr[i] || div[i] != cdiv[i]) return false;
    return true;
}

// ---- descriptors ----
// The table-entry flip log is diagnostic. It stops after 60 lines, and after this many looks: a game that
// never flips was taking a mutex and updating a map for every storage-buffer table entry of every draw.
// unlimited (RX_VK_LOG_TABLE=1) keeps looking until the 60 lines.
inline bool table_track_open(int logged, int seen, int unlimited) {
    constexpr int kTableTrackLooks = 65536;
    return logged < 60 && (unlimited || seen < kTableTrackLooks);
}

/// A program's descriptor counts in one word (Program::desc_counts): buffers, images, texel views, 21 bits each.
/// ~0: not counted, or a count that does not fit (then they are counted at every build, as before)
inline uint64_t desc_counts_pack(size_t nbuf, size_t nimg, size_t nview) {
    constexpr size_t kMost = (1u << 21) - 1;
    if (nbuf > kMost || nimg > kMost || nview > kMost) return ~0ull;
    return (uint64_t)nbuf | (uint64_t)nimg << 21 | (uint64_t)nview << 42;
}
inline void desc_counts_unpack(uint64_t packed, size_t* nbuf, size_t* nimg, size_t* nview) {
    constexpr uint64_t kMask = (1u << 21) - 1;
    *nbuf = (size_t)(packed & kMask), *nimg = (size_t)(packed >> 21 & kMask), *nview = (size_t)(packed >> 42 & kMask);
}

/// A write's words appended to out (the words of the pushed state, a write after another): its type and binding, then its descriptors
inline void words_append(const VkWriteDescriptorSet& w, std::vector<uint64_t>& out) {
    out.push_back((uint64_t)w.descriptorType << 32 | w.dstBinding);
    for (uint32_t k = 0; k < w.descriptorCount; k++) {
        if (w.pBufferInfo) {
            const VkDescriptorBufferInfo& b = w.pBufferInfo[k];
            out.push_back((uint64_t)b.buffer), out.push_back(b.offset), out.push_back(b.range);
        } else if (w.pImageInfo) {
            const VkDescriptorImageInfo& i = w.pImageInfo[k];
            out.push_back((uint64_t)i.sampler), out.push_back((uint64_t)i.imageView);
        } else if (w.pTexelBufferView) {
            out.push_back((uint64_t)w.pTexelBufferView[k]);
        }
    }
}
/// Whether the words in [o, end) are words_append's of w (1), or not (0: they are after the call). -1: w is not the write they were made for
/// (its words do not fill them exactly), and nothing was touched
inline int words_same_store(const VkWriteDescriptorSet& w, uint64_t* o, const uint64_t* end) {
    const size_t per = w.pBufferInfo ? 3 : w.pImageInfo ? 2 : w.pTexelBufferView ? 1 : 0;
    if ((size_t)(end - o) != 1 + (size_t)w.descriptorCount * per) return -1;
    bool same = true;
    auto put = [&](uint64_t v) {
        same &= *o == v;
        *o++ = v;
    };
    put((uint64_t)w.descriptorType << 32 | w.dstBinding);
    for (uint32_t k = 0; k < w.descriptorCount; k++) {
        if (w.pBufferInfo) {
            const VkDescriptorBufferInfo& b = w.pBufferInfo[k];
            put((uint64_t)b.buffer), put(b.offset), put(b.range);
        } else if (w.pImageInfo) {
            const VkDescriptorImageInfo& i = w.pImageInfo[k];
            put((uint64_t)i.sampler), put((uint64_t)i.imageView);
        } else if (w.pTexelBufferView) {
            put((uint64_t)w.pTexelBufferView[k]);
        }
    }
    return same ? 1 : 0;
}

// ---- dynamic state ----
/// The inputs a draw's dynamic state is built from. Most draws repeat the draw before them.
inline bool dyn_same(const float* fp, int nf, const uint32_t* up, int nu, const uint8_t* raw, int nb, const float* cfp,
                     const uint32_t* cup, const uint8_t* craw) {
    if (nf <= 0 || nu <= 0 || nb <= 0) return false;
    for (int i = 0; i < nf; i++)
        if (fp[i] != cfp[i]) return false;
    // (the words and the bytes each at once: a draw that keeps its state, the usual one, compared every one of them in turn)
    return !std::memcmp(up, cup, (size_t)nu * sizeof *up) && !std::memcmp(raw, craw, (size_t)nb);
}

// ---- passes ----
inline bool writes_sampled_target(uint16_t writes, uint16_t sampled_targets) {
    return (writes & sampled_targets) != 0;
}

// ---- vertex streams and the index buffer ----
/// A vertex stream bound earlier this submission, still the same buffer (a mirror made since, or a new submission, is not)
inline bool vertex_bind_reuse(uint64_t addr, uint64_t size, uint64_t stamp, uint64_t cached_addr, uint64_t cached_size,
                              uint64_t cached_stamp, int cached) {
    return cached && addr && size && addr == cached_addr && size == cached_size && stamp == cached_stamp;
}
/// The vertex streams already bound on this command buffer (a new recording, or a mirror made since, is not)
inline bool vertex_set_same(uint64_t stamp, const uint64_t* addr, const uint64_t* size, const uint32_t* stride,
                            uint64_t cached_stamp, const uint64_t* cached_addr, const uint64_t* cached_size,
                            const uint32_t* cached_stride, int on) {
    if (!on || stamp != cached_stamp) return false;
    for (int i = 0; i < 16; i++) {
        const bool used = i != 15 && addr[i];
        if (!used) {
            if (cached_addr[i] || cached_stride[i]) return false;
            continue;
        }
        const uint64_t sz = size[i] ? size[i] : 1;
        if (cached_addr[i] != addr[i] || cached_size[i] != sz || cached_stride[i] != stride[i]) return false;
    }
    return true;
}
/// (hookshot) The vertex bindings that differ from the ones last bound on this command buffer: first..first+count, count 0
/// when none does. Only those are bound again: the driver takes every binding it is handed, and all 16 were handed to it
/// whenever one stream changed, the unused ones with the zero buffer again (1.1 % of the replay thread on a Steam Deck,
/// in the driver). Nothing bound on this command buffer yet (valid false): all 16
inline void vertex_bind_range(const VkBuffer* b, const VkDeviceSize* o, const VkDeviceSize* z, const VkDeviceSize* s, const VkBuffer* lb,
                              const VkDeviceSize* lo, const VkDeviceSize* lz, const VkDeviceSize* ls, bool valid, uint32_t* first,
                              uint32_t* count) {
    if (!valid) {
        *first = 0, *count = 16;
        return;
    }
    uint32_t a = 16, e = 0;
    for (uint32_t i = 0; i < 16; i++)
        if (b[i] != lb[i] || o[i] != lo[i] || z[i] != lz[i] || s[i] != ls[i]) {
            if (a == 16) a = i;
            e = i + 1;
        }
    *first = a == 16 ? 0 : a, *count = a == 16 ? 0 : e - a;
}
/// The index buffer already bound on this command buffer (a new recording is not)
inline bool index_bind_same(uint64_t buffer, uint64_t offset, uint32_t type, uint64_t cached_buffer, uint64_t cached_offset,
                            uint32_t cached_type, int on) {
    return on && buffer && buffer == cached_buffer && offset == cached_offset && type == cached_type;
}

} // namespace mkwvk
