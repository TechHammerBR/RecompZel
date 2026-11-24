"""A graphics pipeline's key keeps its value (gpu/vk/draw_key.h pipeline_key and mix, vk_draw.cpp key_inputs; no game/GPU).

The keys are on players' disks: the pipeline state list, the predicted keys and the pipeline notes name pipelines by them,
and a key that comes out one bit different is a pipeline nothing asks for, built again at every player's next start. So the
arithmetic is restated here in Python, from the code as it was before the key moved to draw_key.h, and three things are
held to it:

- draw_key.h's pipeline_key(KeyInputs) and mix, compiled from the header alone (which also shows the header needs nothing
  but Vulkan's headers, NVN's constants and the standard library);
- vk_draw.cpp's key_inputs and pipeline_key(program, state, targets, topology), cut out and run on made-up programs and
  states: what it reads out of them, and with which casts, is half of the key;
- nx2/bake.py's mix and pipeline_key_skeleton, the same chain for the bake.

PINNED holds keys worked out once from that arithmetic: a change made to the header and to the restatement together still
fails on them. A key that has to change is a change every player pays for; say so in the pull request and pin the new ones.
The NVN to Vulkan maps that moved with the key (topology, blend_factor, blend_op, vertex_format, compare_op, stencil_op) are
checked at a few values of each.

python -I -B tests/test_pipeline_key_values.py [--cxx g++] [--headers <Vulkan headers>]
"""
import argparse
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
M64 = (1 << 64) - 1

# Vulkan's numbers, written out: this file restates the key without the header's help
POINT_LIST, LINE_LIST, LINE_STRIP, TRIANGLE_LIST, TRIANGLE_STRIP, TRIANGLE_FAN = 0, 1, 2, 3, 4, 5
LINE_LIST_ADJ, LINE_STRIP_ADJ, TRIANGLE_LIST_ADJ, TRIANGLE_STRIP_ADJ, PATCH_LIST = 6, 7, 8, 9, 10
FORMATS = (0, 9, 37, 43, 44, 50, 64, 97, 109, 122)   # (VkFormat: UNDEFINED, R8_UNORM, R8G8B8A8_UNORM, ..., B10G11R11_UFLOAT_PACK32)
DEPTHS = (0, 124, 126, 129, 130)                      # (UNDEFINED, D16_UNORM, D32_SFLOAT, D24_UNORM_S8_UINT, D32_SFLOAT_S8_UINT)


def mix(h, v):
    h ^= (v + 0x9E3779B97F4A7C15 + (h << 6) + (h >> 2)) & M64
    return (h * 0xFF51AFD7ED558CCD) & M64


def topology_class(t):
    if t == POINT_LIST:
        return 0
    if t in (LINE_LIST, LINE_STRIP, LINE_LIST_ADJ, LINE_STRIP_ADJ):
        return 1
    return 3 if t == PATCH_LIST else 2


def write_mask(c, i):
    """target_write_mask: the state's channel mask, nothing for an output the fragment stage does not store, and of one it
    stores only the components it writes (none recorded: all four)"""
    if not c["fragment"] or i >= 8 or not c["stores"][i]:
        return 0
    written = c["comps"][i]
    return (c["chmask"] >> (4 * i)) & 0xF & (written if written else 0xF)


def pipeline_key(c):
    """vk_draw.cpp's pipeline_key as it was before draw_key.h had it, term for term"""
    if c["n"] < 0 or c["n"] > 8:
        return 0
    key = mix(mix(c["key"], c["variant"]), topology_class(c["topo"]) << 8 | c["samples"])
    if not c["mesh"] and not c["fallback"]:
        for i in range(16):
            if c["loads"] >> i & 1:
                key = mix(key, c["vattr"][i] << 8 | (1 if i < c["nvattr"] else 0))
        for i in range(16):
            key = mix(key, c["divisor"][i])
    for i in range(c["n"]):
        key = mix(key, c["formats"][i])
        if not c["eds3_blend"]:
            key = mix(key, c["blend"][i] if c["blend_en"] >> i & 1 else 0)
    key = mix(key, c["depth"])
    if not c["eds3_blend"]:
        wm = 0
        for i in range(c["n"]):
            wm |= write_mask(c, i) << (4 * i)
        key = mix(key, wm << 8 | c["blend_en"])
    if not c["eds3_polygon"]:
        key = mix(key, c["poly_mode"])
    if not c["eds3_clamp"]:
        key = mix(key, c["depth_clamp"])
    if not c["eds3_a2c"]:
        key = mix(key, c["a2c"])
    return key


def case(**over):
    """An ordinary program's draw into one RGBA8 target with D24S8, on a device with every dynamic state; over: what differs"""
    c = dict(key=0x0123456789ABCDEF, variant=0xFEDCBA9876543210, mesh=False, fallback=False, fragment=True, loads=0x0007,
             stores=[True] + [False] * 7, comps=[0xF] + [0] * 7, vattr=[0x00000125, 0x00018225, 0x0802001D] + [0] * 13, nvattr=3,
             divisor=[0] * 16, blend=[0x0000000C0CC89A08] + [0] * 7, blend_en=1, chmask=0xFFFFFFFF, poly_mode=2,
             depth_clamp=0, a2c=0, n=1, formats=[37] + [0] * 7, depth=129, samples=1, topo=TRIANGLE_LIST,
             eds3_blend=True, eds3_polygon=True, eds3_clamp=True, eds3_a2c=True)
    c.update(over)
    return c


# (keys worked out from the arithmetic above when the key moved to draw_key.h: see the docstring)
PINNED = [
    (case(), 0x37F544B111B166C4),
    (case(eds3_blend=False, eds3_polygon=False, eds3_clamp=False, eds3_a2c=False, depth_clamp=1, a2c=1, chmask=0xFFFFFF7F),
     0x71016158448EB905),
    (case(mesh=True, n=3, formats=[97, 37, 122] + [0] * 5, stores=[True, True, True] + [False] * 5, comps=[0xF, 0x7, 0] + [0] * 5,
          depth=126, samples=4, eds3_blend=False, blend_en=5, blend=[0x11, 0x22, 0x33] + [0] * 5), 0xDF1809A5234809DC),
    (case(n=0, formats=[0] * 8, depth=130, topo=LINE_STRIP, divisor=[0, 1] + [0] * 14), 0x86829E887C91ADE7),
]
MIX_PINNED = [((0, 0), 0x2E72B4654E79D8D1), ((1, 2), 0x02305A38913298DE), ((0x0123456789ABCDEF, 0xFEDCBA9876543210), 0x1DD0346BF10E3683)]


def made_up_cases():
    """Programs, states and targets from a fixed seed: every branch of the key, many times"""
    r = random.Random(1340)
    out = []
    for i in range(160):
        kind = r.choice(("plain", "plain", "mesh", "fallback"))
        n = r.choice((0, 1, 1, 2, 3, 4, 8))
        c = case(key=r.getrandbits(64), variant=r.getrandbits(64), mesh=kind == "mesh", fallback=kind == "fallback",
                 fragment=r.random() > 0.1, loads=r.getrandbits(16), stores=[r.random() > 0.3 for _ in range(8)],
                 comps=[r.choice((0, 0xF, 0x7, 0x1, 0x8, 0x10, 0xF3)) for _ in range(8)],
                 vattr=[r.getrandbits(32) for _ in range(16)], nvattr=r.randrange(0, 17),
                 divisor=[r.choice((0, 0, 1, 2, 0xFFFFFFFF)) for _ in range(16)], blend=[r.getrandbits(37) for _ in range(8)],
                 blend_en=r.getrandbits(8), chmask=r.getrandbits(32), poly_mode=r.randrange(0, 4), depth_clamp=r.randrange(0, 2),
                 a2c=r.choice((0, 1, 1, 0xFF)), n=n, formats=[r.choice(FORMATS) if k < n else 0 for k in range(8)],
                 depth=r.choice(DEPTHS), samples=r.choice((1, 1, 4, 8)), topo=r.randrange(0, 11),
                 eds3_blend=r.random() > 0.5, eds3_polygon=r.random() > 0.5, eds3_clamp=r.random() > 0.5,
                 eds3_a2c=r.random() > 0.5)
        if i < 4:   # (the devices at the two ends, with everything else made up)
            on = i % 2 == 0
            c.update(eds3_blend=on, eds3_polygon=on, eds3_clamp=on, eds3_a2c=on)
        out.append(c)
    return out


def hx(v):
    return "0x%Xull" % v


def array(values):
    """A C++ initializer list: booleans by name, numbers in decimal while an int holds them"""
    return "{" + ", ".join("true" if v is True else "false" if v is False else str(v) if v < 1 << 31 else hx(v)
                           for v in values) + "}"


def inputs_code(c, want):
    """A case as draw_key.h's KeyInputs: what vk_draw.cpp's key_inputs is to read out of the program and the state"""
    plain = not c["mesh"] and not c["fallback"]
    wm = 0
    if not c["eds3_blend"]:
        for i in range(max(0, min(c["n"], 8))):
            wm |= write_mask(c, i) << (4 * i)
    lines = ["    {", "        KeyInputs k;",
             "        k.prog = %s, k.variant = %s;" % (hx(c["key"]), hx(c["variant"])),
             "        k.topo_class = %d, k.samples = %d, k.vertex_input = %s, k.loads = %s;"
             % (topology_class(c["topo"]), c["samples"], "true" if plain else "false", "0x%Xu" % c["loads"]),
             "        const uint64_t vattr[16] = %s, divisor[16] = %s, formats[8] = %s, blend[8] = %s;"
             % (array(c["vattr"]), array(c["divisor"]), array(c["formats"]), array(c["blend"])),
             "        for (int i = 0; i < 16; i++) k.vattr[i] = vattr[i], k.divisor[i] = divisor[i];",
             "        for (int i = 0; i < 8; i++) k.color_format[i] = formats[i], k.blend[i] = blend[i];",
             "        k.nvattr = %d, k.n = %d, k.depth_format = %d, k.blend_en = %d, k.write_masks = %s;"
             % (c["nvattr"], c["n"], c["depth"], c["blend_en"], hx(wm)),
             "        k.poly_mode = %d, k.depth_clamp = %d, k.a2c = %d;" % (c["poly_mode"], c["depth_clamp"], c["a2c"]),
             "        k.eds3_blend = %d, k.eds3_polygon = %d, k.eds3_clamp = %d, k.eds3_a2c = %d;"
             % (c["eds3_blend"], c["eds3_polygon"], c["eds3_clamp"], c["eds3_a2c"]),
             "        CHECK_KEY(pipeline_key(k), %s);" % hx(want), "    }"]
    return "\n".join(lines)


def draw_code(c, want):
    """A case as a program, a state, targets and a device: what a draw hands vk_draw.cpp's pipeline_key"""
    stages = []
    if c["mesh"]:
        stages.append("mesh_stage()")
    if c["fallback"]:
        stages.append("compute_stage()")
    stages.append("vertex_stage(0x%Xu)" % c["loads"])   # (a mesh program has none in the game: the key must not read it)
    if c["fragment"]:
        stages.append("fragment_stage({%s}, {%s})" % (array(c["stores"]), array(c["comps"])))   # (std::array: braces twice)
    lines = ["    {", "        Program p;",
             "        p.key = %s, p.variant = %s, p.mesh = %s, p.fallback = %s;"
             % (hx(c["key"]), hx(c["variant"]), "true" if c["mesh"] else "false", "true" if c["fallback"] else "false"),
             "        p.stages = {%s};" % ", ".join(stages),
             "        NvnState s;",
             "        const uint32_t vattr[16] = %s, divisor[16] = %s;" % (array(c["vattr"]), array(c["divisor"])),
             "        const uint64_t blend[8] = %s;" % array(c["blend"]),
             "        for (int i = 0; i < 16; i++) s.vattr[i] = vattr[i], s.vstream[i].divisor = divisor[i], s.vstream[i].stride = 16;",
             "        std::memcpy(s.blend, blend, sizeof blend);",
             "        s.nvattr = %d, s.color.blend_en = %d, s.chmask.mask = %s, s.poly.mode = %d;"
             % (c["nvattr"], c["blend_en"], "0x%Xu" % c["chmask"], c["poly_mode"]),
             "        s.depth_clamp = %s, s.ms.a2c = %d;" % ("true" if c["depth_clamp"] else "false", c["a2c"]),
             "        Targets at;",
             "        const int formats[8] = %s;" % array(c["formats"]),
             "        for (int i = 0; i < 8; i++) at.color_format[i] = (VkFormat)formats[i];",
             "        at.n = %d, at.depth_format = (VkFormat)%d, at.samples = (VkSampleCountFlagBits)%d;"
             % (c["n"], c["depth"], c["samples"]),
             "        dev.eds3_blend = %d, dev.eds3_polygon = %d, dev.eds3_clamp = %d, dev.eds3_a2c = %d;"
             % (c["eds3_blend"], c["eds3_polygon"], c["eds3_clamp"], c["eds3_a2c"]),
             "        CHECK_KEY(pipeline_key(p, s, at, (VkPrimitiveTopology)%d), %s);" % (c["topo"], hx(want)), "    }"]
    return "\n".join(lines)


CHECKS = r"""
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
static int checked = 0;
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } checked++; } while (0)
#define CHECK_KEY(got, want) do { const uint64_t g = (got), w = (want); if (g != w) { std::fprintf(stderr, \
    "FAIL:%d a pipeline key is %016llx, and was %016llx\n", __LINE__, (unsigned long long)g, (unsigned long long)w); std::exit(1); } \
    checked++; } while (0)
"""

# draw_key.h first, before any other header: it has to compile alone
HEADER_ALONE = r"""#include "draw_key.h"
""" + CHECKS + r"""
using namespace mkwvk;
int main() {
@MIX@
@KEYS@
    // more colour targets than a pipeline has, or fewer than none: no key
    { KeyInputs k; k.n = 9; CHECK_KEY(pipeline_key(k), 0); k.n = -1; CHECK_KEY(pipeline_key(k), 0); }
    // the maps that moved with the key
    VkPrimitiveTopology t = VK_PRIMITIVE_TOPOLOGY_MAX_ENUM;
    CHECK(topology(NVN_DRAW_PRIMITIVE_POINTS, t) && t == VK_PRIMITIVE_TOPOLOGY_POINT_LIST);
    CHECK(topology(NVN_DRAW_PRIMITIVE_TRIANGLES, t) && t == VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST);
    CHECK(topology(NVN_DRAW_PRIMITIVE_TRIANGLE_STRIP, t) && t == VK_PRIMITIVE_TOPOLOGY_TRIANGLE_STRIP);
    CHECK(topology(NVN_DRAW_PRIMITIVE_POLYGON, t) && t == VK_PRIMITIVE_TOPOLOGY_TRIANGLE_FAN);
    CHECK(topology(NVN_DRAW_PRIMITIVE_QUADS, t) && t == VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST);   // (draw() makes the indices)
    CHECK(topology(NVN_DRAW_PRIMITIVE_PATCHES, t) && t == VK_PRIMITIVE_TOPOLOGY_PATCH_LIST);
    CHECK(topology(NVN_DRAW_PRIMITIVE_LINE_STRIP_ADJACENCY, t) && t == VK_PRIMITIVE_TOPOLOGY_LINE_STRIP_WITH_ADJACENCY);
    t = VK_PRIMITIVE_TOPOLOGY_MAX_ENUM;
    CHECK(!topology(NVN_DRAW_PRIMITIVE_LINE_LOOP, t) && !topology(NVN_DRAW_PRIMITIVE_QUAD_STRIP, t));   // (Vulkan has neither)
    CHECK(!topology(-1, t) && !topology(1000, t) && t == VK_PRIMITIVE_TOPOLOGY_MAX_ENUM);   // (none: left as it was)
    CHECK(topology_class(VK_PRIMITIVE_TOPOLOGY_POINT_LIST) == 0 && topology_class(VK_PRIMITIVE_TOPOLOGY_LINE_STRIP) == 1);
    CHECK(topology_class(VK_PRIMITIVE_TOPOLOGY_TRIANGLE_FAN) == 2 && topology_class(VK_PRIMITIVE_TOPOLOGY_PATCH_LIST) == 3);
    CHECK(blend_factor(NVN_BLEND_FUNC_ZERO) == VK_BLEND_FACTOR_ZERO && blend_factor(NVN_BLEND_FUNC_ONE) == VK_BLEND_FACTOR_ONE);
    CHECK(blend_factor(NVN_BLEND_FUNC_SRC_ALPHA) == VK_BLEND_FACTOR_SRC_ALPHA);
    CHECK(blend_factor(NVN_BLEND_FUNC_ONE_MINUS_SRC_ALPHA) == VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA);
    CHECK(blend_factor(NVN_BLEND_FUNC_ONE_MINUS_SRC1_ALPHA) == VK_BLEND_FACTOR_ONE_MINUS_SRC1_ALPHA);
    CHECK(blend_factor(0) == VK_BLEND_FACTOR_ONE && blend_factor(0x7F) == VK_BLEND_FACTOR_ONE);   // (not a function: ONE)
    CHECK(blend_op(NVN_BLEND_EQUATION_SUB) == VK_BLEND_OP_SUBTRACT && blend_op(NVN_BLEND_EQUATION_MAX) == VK_BLEND_OP_MAX);
    CHECK(blend_op(NVN_BLEND_EQUATION_REVERSE_SUB) == VK_BLEND_OP_REVERSE_SUBTRACT && blend_op(NVN_BLEND_EQUATION_MIN) == VK_BLEND_OP_MIN);
    CHECK(blend_op(0) == VK_BLEND_OP_ADD && blend_op(7) == VK_BLEND_OP_ADD);
    CHECK(vertex_format(0x01) == VK_FORMAT_R8_UNORM && vertex_format(0x04) == VK_FORMAT_R8_SINT);
    CHECK(vertex_format(0x05) == VK_FORMAT_R16_SFLOAT && vertex_format(0x0A) == VK_FORMAT_R32_SFLOAT);
    CHECK(vertex_format(0x16) == VK_FORMAT_R32G32_SFLOAT && vertex_format(0x22) == VK_FORMAT_R32G32B32_SFLOAT);
    CHECK(vertex_format(0x25) == VK_FORMAT_R8G8B8A8_UNORM && vertex_format(0x30) == VK_FORMAT_R32G32B32A32_SINT);
    CHECK(vertex_format(0x51) == VK_FORMAT_R8_UINT && vertex_format(0x52) == VK_FORMAT_R8_SINT);   // (scaled: read as integers)
    CHECK(vertex_format(0x67) == VK_FORMAT_R32G32B32A32_UINT && vertex_format(0x68) == VK_FORMAT_R32G32B32A32_SINT);
    CHECK(vertex_format(NVN_FORMAT_RGB10A2) == VK_FORMAT_A2B10G10R10_UNORM_PACK32);
    CHECK(vertex_format(NVN_FORMAT_BGRA8) == VK_FORMAT_B8G8R8A8_UNORM && vertex_format(0) == VK_FORMAT_UNDEFINED);
    CHECK(compare_op(1) == VK_COMPARE_OP_NEVER && compare_op(8) == VK_COMPARE_OP_ALWAYS && compare_op(4) == VK_COMPARE_OP_LESS_OR_EQUAL);
    CHECK(compare_op(0) == VK_COMPARE_OP_ALWAYS && compare_op(9) == VK_COMPARE_OP_ALWAYS);
    CHECK(stencil_op(1) == VK_STENCIL_OP_KEEP && stencil_op(8) == VK_STENCIL_OP_DECREMENT_AND_WRAP);
    CHECK(stencil_op(0) == VK_STENCIL_OP_KEEP && stencil_op(9) == VK_STENCIL_OP_KEEP);
    std::printf("draw_key.h alone: %d checks\n", checked);
    return 0;
}
"""

# vk_draw.cpp's two functions with the least that stands in for the program, the state and the device
FROM_A_DRAW = r"""#include "draw_key.h"
#include <array>
#include <vector>
""" + CHECKS + r"""
@NVN_STATES@
namespace mkwvk {
// (the fields of NvnState the key reads, with rx_nvn.h's own state structs, cut above)
struct NvnState {
    nvn_blend_st blend[8]{};
    nvn_color_st color{};
    nvn_chmask_st chmask{0xffffffffu};
    nvn_ms_st ms{};
    nvn_poly_st poly{};
    uint32_t vattr[16]{};
    int nvattr = 0;
    nvn_vs_st vstream[16]{};
    bool depth_clamp = false;
};
static_assert(sizeof(nvn_blend_st) == 8, "a target's blend state is the 8 bytes the key mixes");
}
namespace Shader {
struct Info {
    struct { uint32_t mask = 0; bool Generic(int i) const { return (mask >> i & 1) != 0; } } loads;
    std::array<bool, 8> stores_frag_color{};
    std::array<uint8_t, 8> frag_color_components{};
};
}
namespace mkwvk {
struct Stage { VkShaderStageFlagBits vk_stage = VK_SHADER_STAGE_VERTEX_BIT; Shader::Info info; };
struct Program { uint64_t key = 0, variant = 0; bool mesh = false, fallback = false; std::vector<Stage> stages; };
struct Texture;
@TARGETS@;
struct { bool eds3_blend = false, eds3_polygon = false, eds3_clamp = false, eds3_a2c = false; } dev;
@TARGET_WRITE_MASK@
@VERTEX_INFO@
@KEY_INPUTS@
@PIPELINE_KEY@
static Stage vertex_stage(uint32_t loads) { Stage s; s.info.loads.mask = loads; return s; }
static Stage mesh_stage() { Stage s; s.vk_stage = VK_SHADER_STAGE_MESH_BIT_EXT; return s; }
static Stage compute_stage() { Stage s; s.vk_stage = VK_SHADER_STAGE_COMPUTE_BIT; return s; }
static Stage fragment_stage(std::array<bool, 8> stores, std::array<uint8_t, 8> comps) {
    Stage s;
    s.vk_stage = VK_SHADER_STAGE_FRAGMENT_BIT, s.info.stores_frag_color = stores, s.info.frag_color_components = comps;
    return s;
}
}
using namespace mkwvk;
int main() {
@KEYS@
    {   // more colour targets than a pipeline has: no key, and nothing read past the eight
        Program p; p.stages = {vertex_stage(1)}; NvnState s; Targets at; at.n = 9;
        CHECK_KEY(pipeline_key(p, s, at, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST), 0);
        at.n = -1;
        CHECK_KEY(pipeline_key(p, s, at, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST), 0);
    }
    (void)mesh_stage, (void)compute_stage, (void)fragment_stage;
    std::printf("vk_draw.cpp's key from a draw: %d checks\n", checked);
    return 0;
}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--headers", type=Path, help="the Vulkan headers, where the compiler does not find them itself")
    a = p.parse_args()
    draw = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    key_h = (ROOT / "gpu" / "vk" / "draw_key.h").read_text(encoding="utf-8")
    nvn = (ROOT / "gpu" / "render" / "rx_nvn.h").read_text(encoding="utf-8")

    # 1. the restatement against the pinned keys, and against the bake's
    for (h, v), want in MIX_PINNED:
        if mix(h, v) != want:
            raise SystemExit("mix(%#x, %#x) is restated here as %#018x, and was %#018x" % (h, v, mix(h, v), want))
    for i, (c, want) in enumerate(PINNED):
        if pipeline_key(c) != want:
            raise SystemExit("pinned key %d is restated here as %#018x, and was %#018x" % (i, pipeline_key(c), want))
    sys.path.insert(0, str(ROOT / "nx2"))
    import bake   # noqa: E402  (nx2/bake.py: standard library only)
    cases = [c for c, _ in PINNED] + made_up_cases()
    for c in cases:
        if bake.mix(c["key"], c["variant"]) != mix(c["key"], c["variant"]):
            raise SystemExit("nx2/bake.py's mix is not the renderer's")
        # (the bake's chain is the key of a program without vertex input on a device with every dynamic state)
        b = dict(c, mesh=True, eds3_blend=True, eds3_polygon=True, eds3_clamp=True, eds3_a2c=True)
        skeleton = bake.pipeline_key_skeleton(b["key"], b["variant"], topology_class(b["topo"]), b["samples"],
                                              b["formats"][:b["n"]], b["depth"])
        if skeleton != pipeline_key(b):
            raise SystemExit("nx2/bake.py's pipeline_key_skeleton is not the renderer's key")

    # 2. the sources: one definition of the arithmetic, and vk_draw.cpp's key goes through it
    if '#include "draw_key.h"' not in draw:
        raise SystemExit("vk_draw.cpp does not include draw_key.h")
    for fn in ("uint64_t mix(uint64_t h, uint64_t v) {", "uint64_t pipeline_key(const KeyInputs& k) {"):
        if fn in draw or key_h.count(fn) != 1:
            raise SystemExit("draw_key.h is not the one place that defines " + fn)
    wrapper = block(draw, "uint64_t pipeline_key(const Program& p, const NvnState& s, const Targets& at, VkPrimitiveTopology topo) {")
    # (the key from a seed, so that the shader ledger can seed it with a program's fingerprint (pipeline_key_from): the
    # wrapper's seed is the one draw_key.h's pipeline_key takes, mix(prog, variant), and key_inputs copies both from the program)
    seeded = block(draw, "static uint64_t pipeline_key_from(uint64_t seed, const Program& p, const NvnState& s, const Targets& at, "
                         "VkPrimitiveTopology topo) {")
    inputs = block(draw, "KeyInputs key_inputs(")
    if "return pipeline_key_from(mix(p.key, p.variant), p, s, at, topo);" not in wrapper or \
            "return pipeline_key_seeded(key_inputs(p, s, at, topo), seed);" not in seeded or "mix(" in seeded or \
            "k.prog = p.key, k.variant = p.variant;" not in inputs or \
            "inline uint64_t pipeline_key(const KeyInputs& k) { return pipeline_key_seeded(k, mix(k.prog, k.variant)); }" not in key_h:
        raise SystemExit("vk_draw.cpp's pipeline_key does not make its key with draw_key.h's")
    reads = block(draw, "KeyInputs key_inputs(")
    if "mix(" in reads:
        raise SystemExit("vk_draw.cpp's key_inputs mixes: the arithmetic is draw_key.h's alone")

    # 3. the header alone, and the key as a draw asks for it
    states = "\n".join(re.search(r"(?m)^typedef struct \{[^\n]*\} %s;" % name, nvn).group(0)
                       for name in ("nvn_color_st", "nvn_chmask_st", "nvn_blend_st", "nvn_ms_st", "nvn_poly_st", "nvn_vs_st"))
    mixes = "\n".join("    CHECK_KEY(mix(%s, %s), %s);" % (hx(h), hx(v), hx(want)) for (h, v), want in MIX_PINNED)
    alone = (HEADER_ALONE.replace("@MIX@", mixes)
             .replace("@KEYS@", "\n".join(inputs_code(c, pipeline_key(c)) for c in cases)))
    from_a_draw = (FROM_A_DRAW.replace("@NVN_STATES@", states)
                   .replace("@TARGETS@", block(draw, "struct Targets {"))
                   .replace("@TARGET_WRITE_MASK@", block(draw, "uint32_t target_write_mask(const Program& p, const NvnState& s, int i) {"))
                   .replace("@VERTEX_INFO@", block(draw, "const Shader::Info* vertex_info(const Program& p) {"))
                   .replace("@KEY_INPUTS@", reads).replace("@PIPELINE_KEY@", seeded + "\n" + wrapper)
                   .replace("@KEYS@", "\n".join(draw_code(c, pipeline_key(c)) for c in cases)))
    with tempfile.TemporaryDirectory(prefix="pipeline-key-") as tmp:
        for name, text in (("alone", alone), ("draw", from_a_draw)):
            cpp, exe = Path(tmp) / (name + ".cpp"), Path(tmp) / name
            cpp.write_text(text, encoding="utf-8")
            subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"),
                            *(["-I", str(a.headers)] if a.headers else []), str(cpp), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
    print("ok: %d pipeline keys, from the header alone and from a draw, are the ones on players' disks" % len(cases))


if __name__ == "__main__":
    main()
