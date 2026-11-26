# SPDX-License-Identifier: GPL-3.0-or-later
"""RX_VK_MEMORY_PRIORITY (off by default) gives the renderer's memory a VK_EXT_memory_priority priority: the render
targets' above everything, the sampled textures' below, the rest where the driver puts memory allocated without one.

The rule (gpu/vk/memory_priority.h) is compiled and run alone. The source checks read vk_main.cpp and vk_vma.cpp:
the extension is asked of the device only with the switch on and used only with its feature, and, since VMA gives a
pool's blocks and an allocation with a memory object of its own the priority in their create info once the extension
is on (a zero left there is the lowest there is), every pool and every allocation the renderer makes through VMA sets
one. Memory the renderer allocates itself (vkAllocateMemory: the sparse textures' chunks, two small buffers the CPU
reads, the imports of guest memory) has no priority and keeps the driver's 0.5. No game or GPU is needed.

    python -I -B tests/test_memory_priority.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

RULE = r'''#include "memory_priority.h"
#include <cstdio>
#include <initializer_list>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); return 1; } } while (0)
int main() {
    using memory_priority::image;
    using memory_priority::parse;
    // (off: unset, empty or one of the switches' words for off. Nothing is asked of the driver, and the numbers are its own)
    for (const char* off : {(const char*)nullptr, "", "0", " 0 ", "false", "OFF", "no"}) {
        const auto t = parse(off);
        CHECK(!t.on && t.targets == 0.5f && t.textures == 0.5f && t.rest == 0.5f);
    }
    // (on: the render targets at the top, the textures under the rest, the rest where it was)
    for (const char* on : {"1", "on", "yes", "true"}) {
        const auto t = parse(on);
        CHECK(t.on && t.targets == 1.0f && t.textures == 0.25f && t.rest == 0.5f);
        CHECK(t.textures < t.rest && t.rest < t.targets);
    }
    // (<targets>,<textures>: a test's own two, each from 0 to 1; the rest is never moved)
    CHECK(parse("1,0.5").on && parse("1,0.5").targets == 1.0f && parse("1,0.5").textures == 0.5f);
    CHECK(parse("0.75,0.125").targets == 0.75f && parse("0.75,0.125").textures == 0.125f);
    CHECK(parse("0.5,0").on && parse("0.5,0").targets == 0.5f && parse("0.5,0").textures == 0.0f);
    CHECK(parse("0,0").on && parse("0,0").targets == 0.0f && parse("0,0").textures == 0.0f);
    CHECK(parse(" 1 , 0.5 ").targets == 1.0f && parse(" 1 , 0.5 ").textures == 0.5f);
    for (const char* v : {"1,0.5", "0.75,0.125", "0.5,0", "0,0", " 1 , 0.5 "}) CHECK(!parse(v).unread && parse(v).rest == 0.5f);
    // (anything else with a comma is not guessed at: the usual two, and `unread` for the log. 0,5 is a half written with
    // a decimal comma, which read as two numbers would put the render targets at the bottom and the textures at the top;
    // nan would reach the driver as a priority, and the extension wants 0 to 1)
    for (const char* bad : {"0,5", "2,-1", "nan,0.25", "0.5,nan", "inf,0", "1,", ",0.25", ",", "1,0.5,0.2", "a,b", "1;0.25,", "0.5x,0.25",
                            "1e400,0"}) {
        const auto t = parse(bad);
        CHECK(t.on && t.unread && t.targets == 1.0f && t.textures == 0.25f && t.rest == 0.5f);
    }
    for (const char* word : {"1", "on", "abc", "0.0", "1;0.25"}) CHECK(!parse(word).unread);
    // (an image's: a render target's first, then a texture of the textures' pool, then the rest)
    const auto t = parse("1");
    CHECK(image(t, true, false) == 1.0f && image(t, false, true) == 0.25f && image(t, false, false) == 0.5f);
    CHECK(image(t, true, true) == 1.0f);
    const auto off = parse(nullptr);
    CHECK(image(off, true, false) == 0.5f && image(off, false, true) == 0.5f && image(off, false, false) == 0.5f);
    puts("memory priority: off by default; on, the render targets 1, the textures 0.25, the rest 0.5");
    return 0;
}
'''


def block(text, marker):
    start = text.index(marker)
    depth = 0
    for at in range(text.index("{", start), len(text)):
        depth += text[at] == "{"
        depth -= text[at] == "}"
        if depth == 0:
            return text[start:at + 1]
    raise SystemExit("unterminated: " + marker)


def need(where, text, needles):
    for needle in needles:
        if needle not in text:
            raise SystemExit("FAIL: " + where + " no longer has: " + needle)


def check_source():
    vk = ROOT / "gpu" / "vk"
    main_cpp = (vk / "vk_main.cpp").read_text(encoding="utf-8")
    vma = (vk / "vk_vma.cpp").read_text(encoding="utf-8")
    # (the device: the extension only with the switch on, and counted only with its feature, which goes to vkCreateDevice)
    need("vk_main.cpp", main_cpp,
         ['if (memory_priority::parse(getenv("RX_VK_MEMORY_PRIORITY")).on) '
          "optional(VK_EXT_MEMORY_PRIORITY_EXTENSION_NAME, dev.memory_priority);",
          "if (dev.memory_priority) *tail = &mem_priority, tail = &mem_priority.pNext;",
          "dev.memory_priority = dev.memory_priority && mem_priority.memoryPriority;"])
    if len(re.findall(r"VK_EXT_MEMORY_PRIORITY_EXTENSION_NAME", main_cpp)) != 1:
        raise SystemExit("FAIL: vk_main.cpp asks for VK_EXT_memory_priority somewhere the switch does not guard")
    need("vk_internal.h", (vk / "vk_internal.h").read_text(encoding="utf-8"), ["memory_priority = false,"])
    # (the allocator: told of the extension only when the device has it on, so with the switch off VMA reads no priority)
    need("vk_vma.cpp: memory_tiers()", block(vma, "static const memory_priority::Tiers& memory_tiers() {"),
         ['static const memory_priority::Tiers t = memory_priority::parse(getenv("RX_VK_MEMORY_PRIORITY"));'])
    init = block(vma, "bool vma_init(PFN_vkGetInstanceProcAddr gipa) {")
    need("vk_vma.cpp: vma_init()", init,
         ["if (dev.memory_priority) ci.flags |= VMA_ALLOCATOR_CREATE_EXT_MEMORY_PRIORITY_BIT;", 'logf("vk: memory priority (RX_VK_MEMORY_PRIORITY',
          "if (memory_tiers().unread)"])
    if len(re.findall(r"VMA_ALLOCATOR_CREATE_EXT_MEMORY_PRIORITY_BIT", vma)) != 1:
        raise SystemExit("FAIL: vk_vma.cpp sets the allocator's memory priority bit somewhere dev.memory_priority does not guard")
    # (the pools: a block has its pool's priority)
    need("vk_vma.cpp: target_images_pool()", block(vma, "VmaPool target_images_pool() {"), ["pi.priority = memory_tiers().targets;"])
    need("vk_vma.cpp: images_pool()", block(vma, "VmaPool images_pool() {"), ["pi.priority = memory_tiers().rest;"])
    need("vk_vma.cpp: textures_pool()", block(vma, "VmaPool textures_pool() {"), ["pi.priority = memory_tiers().textures;"])
    # (the allocations: one with a memory object of its own has its own, an image's by what the image is. The dedicated,
    # pooled and block-of-its-own tries are copies of ai, made after its priority is set)
    image = block(vma, "bool create_image(const VkImageCreateInfo& ci")
    need("vk_vma.cpp: create_image()", image,
         ["ai.priority = memory_priority::image(memory_tiers(), target, textures);", "sai.priority = ai.priority;"])
    set_at = image.index("ai.priority = memory_priority::image(")
    for copy in re.finditer(r"VmaAllocationCreateInfo \w+ = ai;", image):
        if copy.start() < set_at:
            raise SystemExit("FAIL: create_image() copies its allocation's create info before the priority is set: " + copy.group(0))
    for marker in ("bool create_buffer(", "bool create_buffer_cached(", "bool create_device_buffer(", "bool alloc_sparse_block("):
        need("vk_vma.cpp: " + marker + ")", block(vma, marker), ["ai.priority = memory_tiers().rest;"])
    # (and none is left out: each create info that reaches an allocation, in the one file that makes them. The ones that
    # only ask VMA which memory type a pool's images take allocate nothing)
    for m in re.finditer(r"\n(\S[^\n;]*\)) \{\n", vma):
        body = block(vma, m.group(1) + " {")
        for kind, name in re.findall(r"\b(VmaAllocationCreateInfo|VmaPoolCreateInfo) (\w+)\{\};", body):
            uses = len(re.findall(r"&" + name + r"\b", body))
            finds = len(re.findall(r"vmaFindMemoryTypeIndexForImageInfo\([^;]*&" + name + r"\b", body))
            if uses and uses == finds:
                continue
            if name + ".priority = " not in body:
                raise SystemExit("FAIL: vk_vma.cpp: " + m.group(1) + ": " + kind + " " + name +
                                 " sets no priority (with VK_EXT_memory_priority on, VMA would give it 0, the lowest)")
    for path in sorted(vk.rglob("*")):
        if path.suffix not in (".cpp", ".h") or path.name == "vk_vma.cpp":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\b(vmaCreatePool|vmaCreateImage|vmaCreateBuffer\w*|vmaAllocateMemory\w*)\(", text):
            raise SystemExit("FAIL: " + path.name + " allocates through VMA outside vk_vma.cpp: its create info needs a priority "
                             "too (tests/test_memory_priority.py reads vk_vma.cpp alone)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="memory-priority-") as tmp:
        src = Path(tmp) / "memory_priority_test.cpp"
        src.write_text(RULE, encoding="utf-8")
        exe = Path(tmp) / "memory-priority"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu" / "vk"), str(src),
                        "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=60)
    print("PASS: RX_VK_MEMORY_PRIORITY is off by default, and every pool and allocation the renderer makes through VMA has a priority")


if __name__ == "__main__":
    main()
