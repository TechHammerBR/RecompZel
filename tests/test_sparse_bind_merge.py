"""sparse_merge (gpu/vk/vk_texture.cpp) folds a run of per-block sparse image binds into one wider bind wherever the
blocks are contiguous both in image space (same level/layer/row, consecutive x) and in device memory (same handle,
offsets exactly one block apart), and leaves separate binds wherever either kind of contiguity breaks: a gap in x, a
different row/level/layer, a different VkDeviceMemory (a new chunk), or a memory offset that is not the expected step
apart. These checks build synthetic bind lists by hand and run the real function against them, since nothing here
needs a Vulkan device: it is pure bookkeeping over the VkSparseImageMemoryBind array vkQueueBindSparse is given.

python -I -B tests/test_sparse_bind_merge.py --headers <vulkan_headers include dir> [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


FIXTURE = r'''
#include <vulkan/vulkan_core.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"FAIL:%d %s\n",__LINE__,#x); std::exit(1); } } while (0)

''' + "{FUNC}" + r'''

VkSparseImageMemoryBind tile(uint32_t layer, uint32_t level, int32_t x, int32_t y, uint32_t w, uint32_t h,
                             VkDeviceMemory mem, VkDeviceSize off) {
    VkSparseImageMemoryBind b{};
    b.subresource = {VK_IMAGE_ASPECT_COLOR_BIT, level, layer};
    b.offset = {x, y, 0};
    b.extent = {w, h, 1};
    b.memory = mem;
    b.memoryOffset = off;
    return b;
}
uint64_t total_width(const std::vector<VkSparseImageMemoryBind>& v) {
    uint64_t t = 0;
    for (const auto& b : v) t += b.extent.width;
    return t;
}
VkDeviceMemory chunk_a = (VkDeviceMemory)1, chunk_b = (VkDeviceMemory)2;
constexpr VkDeviceSize kAlign = 65536;   // (tex->sparse_align in play; the value itself does not matter here)

int main(int argc, char** argv) {
    // RX_VK_SPARSE_MERGE=0, set in the environment before this process starts (the switch is a static, read once per
    // process, as the production code's own env switches are: setenv() after the first call would not reach it).
    if (argc > 1 && !std::strcmp(argv[1], "off")) {
        std::vector<VkSparseImageMemoryBind> v;
        for (uint32_t i = 0; i < 5; i++) v.push_back(tile(0, 0, (int32_t)(i * 64), 0, 64, 64, chunk_a, i * kAlign));
        CHECK(sparse_merge(v, kAlign) == 5 && v.size() == 5);
        CHECK(v[0].offset.x == 0 && v[4].offset.x == 4 * 64);
        std::puts("PASS: RX_VK_SPARSE_MERGE=0 leaves the list exactly as given");
        return 0;
    }
    // A full row of 8 contiguous blocks, same memory, offsets one align apart: one merged bind, same total width.
    {
        std::vector<VkSparseImageMemoryBind> v;
        for (uint32_t i = 0; i < 8; i++) v.push_back(tile(0, 0, (int32_t)(i * 64), 0, 64, 64, chunk_a, i * kAlign));
        const uint64_t before = total_width(v);
        const size_t n = sparse_merge(v, kAlign);
        CHECK(n == 1 && v.size() == 1);
        CHECK(v[0].offset.x == 0 && v[0].extent.width == 64 * 8 && v[0].extent.height == 64);
        CHECK(total_width(v) == before);
    }
    // A row with its last block narrower (the right edge of the image): still merges, the odd width carried through.
    {
        std::vector<VkSparseImageMemoryBind> v;
        for (uint32_t i = 0; i < 3; i++) v.push_back(tile(0, 0, (int32_t)(i * 64), 0, 64, 64, chunk_a, i * kAlign));
        v.push_back(tile(0, 0, 3 * 64, 0, 37, 64, chunk_a, 3 * kAlign));   // (clamped at the image's right edge)
        const uint64_t before = total_width(v);
        CHECK(sparse_merge(v, kAlign) == 1);
        CHECK(v[0].extent.width == 64 * 3 + 37);
        CHECK(total_width(v) == before);
    }
    // A gap in image space (block 1 never queued): two binds, neither widened past the gap.
    {
        std::vector<VkSparseImageMemoryBind> v;
        v.push_back(tile(0, 0, 0, 0, 64, 64, chunk_a, 0));
        v.push_back(tile(0, 0, 128, 0, 64, 64, chunk_a, kAlign));   // (x=128, not the 64 a contiguous run would be at)
        CHECK(sparse_merge(v, kAlign) == 2);
        CHECK(v[0].extent.width == 64 && v[1].extent.width == 64);
    }
    // Contiguous in image space but not in memory (a chunk boundary fell between them): two binds, not one.
    {
        std::vector<VkSparseImageMemoryBind> v;
        v.push_back(tile(0, 0, 0, 0, 64, 64, chunk_a, 0));
        v.push_back(tile(0, 0, 64, 0, 64, 64, chunk_b, 0));   // (a new chunk: a different memory handle)
        CHECK(sparse_merge(v, kAlign) == 2);
    }
    // Contiguous in image space, same memory, but the offset step is wrong (not exactly one align apart): two binds.
    {
        std::vector<VkSparseImageMemoryBind> v;
        v.push_back(tile(0, 0, 0, 0, 64, 64, chunk_a, 0));
        v.push_back(tile(0, 0, 64, 0, 64, 64, chunk_a, kAlign * 2));   // (a slot skipped: not contiguous)
        CHECK(sparse_merge(v, kAlign) == 2);
    }
    // Two rows (different y) of 4 contiguous blocks each, interleaved out of queue order: merges within each row,
    // never across them, and the sort inside sparse_merge puts the result back in row-major order either way.
    {
        std::vector<VkSparseImageMemoryBind> v;
        for (uint32_t i = 0; i < 4; i++) v.push_back(tile(0, 0, (int32_t)(i * 64), 64, 64, 64, chunk_a, (4 + i) * kAlign));
        for (uint32_t i = 0; i < 4; i++) v.push_back(tile(0, 0, (int32_t)(i * 64), 0, 64, 64, chunk_a, i * kAlign));
        CHECK(sparse_merge(v, kAlign) == 2);
        CHECK(v[0].offset.y == 0 && v[0].extent.width == 256);
        CHECK(v[1].offset.y == 64 && v[1].extent.width == 256);
    }
    // Different layers and different mip levels never merge into each other even at the same (x, y).
    {
        std::vector<VkSparseImageMemoryBind> v;
        v.push_back(tile(0, 0, 0, 0, 64, 64, chunk_a, 0));
        v.push_back(tile(1, 0, 0, 0, 64, 64, chunk_a, kAlign));     // (a different layer)
        v.push_back(tile(0, 1, 0, 0, 64, 64, chunk_a, kAlign * 2)); // (a different mip level)
        CHECK(sparse_merge(v, kAlign) == 3);
    }
    std::puts("PASS: 7 sparse-bind-merge scenarios (contiguous, clamped, gapped, chunk break, offset break, "
              "two rows, layer/level isolation)");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--headers", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "gpu/vk/vk_texture.cpp")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    func = block(source, "size_t sparse_merge(")
    fixture = FIXTURE.replace("{FUNC}", func)
    with tempfile.TemporaryDirectory(prefix="hookshot-sparse-merge-") as directory:
        cpp, exe = Path(directory) / "test.cpp", Path(directory) / "test.exe"
        cpp.write_text(fixture, encoding="utf-8")
        flags = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"] if args.sanitize else []
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Werror",
                        "-Wno-missing-field-initializers", *flags,
                        "-I" + str(args.headers), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=10)
        subprocess.run([str(exe), "off"], check=True, timeout=10, env={**os.environ, "RX_VK_SPARSE_MERGE": "0"})


if __name__ == "__main__":
    main()
