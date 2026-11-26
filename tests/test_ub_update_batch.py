"""A recording's uniform updates reach guest memory in stream order as few copies: one barrier and one copy for a batch.

flush_ub_updates (gpu/vk/vk_replay.cpp) writes the stream's UPDATE_UB bytes into guest memory at the end of their
recording. Each update had a full barrier and a vkCmdUpdateBuffer of its own (80 a frame, 0.33 ms of GPU time). Now their
bytes go into the recording's stream and the updates of one import that write different bytes are one vkCmdCopyBuffer of
many regions behind one barrier. What that must keep, and what is checked here:

- two updates of the same bytes land in stream order: a batch ends where an update writes a byte an earlier region of it
  wrote, and the next starts behind a barrier of its own (Vulkan: a copy's regions may not overlap in the destination, and
  with no barrier between two writes of the same bytes their order is not defined);
- updates to different buffers go in different copies, a barrier between them (two imports may hold the same memory), and a
  copy reads one stream buffer (the recording's stream moves to a bigger one when it is full);
- one barrier before each copy and one after the last: a batch of N updates costs 2 barriers, not N + 2;
- with no room in the stream an update is written as before (gpu_put: its own barrier, an update or nothing), after the
  batch before it; bytes no import holds are written on the CPU.

flush_ub_updates, UbBatch, ub_batch_add, ub_batch_emit, gpu_piece_bind, gpu_put and full_barrier are cut from the source and
run against a recorded-command stand-in that applies each command to memory, counts a region overlapping another of its
copy, and counts a write of bytes written since the last barrier. Memory is compared with the updates applied in stream
order. Negative controls: the overlap rule, the buffers rule and the batch's barrier taken out must each fail.

No GPU or game. python -I -B tests/test_ub_update_batch.py --headers <Vulkan headers> [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import between, block

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]
ROOT = Path(__file__).resolve().parents[1]

PREFIX = r'''
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan_core.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <iterator>
#include <utility>
#include <vector>
namespace mkwvk {
@@BUFFERREF@@;
const VkCommandBuffer cb = (VkCommandBuffer)(uintptr_t)7;
// ---- guest memory: two pools, each one import (a buffer), a gap between them that no import holds ----
constexpr uint64_t kPool = 0x40000, kBase[2] = {0x100000, 0x200000};
std::vector<uint8_t> memory[2] = {std::vector<uint8_t>(kPool), std::vector<uint8_t>(kPool)};
std::vector<uint8_t> want[2] = {std::vector<uint8_t>(kPool), std::vector<uint8_t>(kPool)};   // (the updates in stream order)
VkBuffer pool_buffer(int i) { return (VkBuffer)(uintptr_t)(0x100 + i); }
int pool_of(VkBuffer b) { return b == pool_buffer(0) ? 0 : b == pool_buffer(1) ? 1 : -1; }
BufferRef gpu_buffer_bind(uint64_t gpu, uint64_t n, bool write) {
    if (!write) std::puts("FAIL: a write's binding asked for as a read"), exit(1);
    for (int i = 0; i < 2; i++)
        if (gpu >= kBase[i] && gpu - kBase[i] < kPool && n <= kPool - (gpu - kBase[i])) return {pool_buffer(i), gpu - kBase[i], n, 0};
    return {};
}
uint64_t gpu_pool_piece(uint64_t gpu, uint64_t n, bool& in_pool) {
    in_pool = false;
    for (int i = 0; i < 2; i++)
        if (gpu >= kBase[i] && gpu - kBase[i] < kPool) return in_pool = true, std::min<uint64_t>(n, kPool - (gpu - kBase[i]));
    return n;
}
// ---- the recording's stream: two buffers, the second taken when the first is full (stream_move_at), then none ----
constexpr uint64_t kStream = 1 << 20;
std::vector<uint8_t> stream_bytes[2] = {std::vector<uint8_t>(kStream), std::vector<uint8_t>(kStream)};
VkBuffer stream_buffer(int i) { return (VkBuffer)(uintptr_t)(0x900 + i); }
int stream_now;
uint64_t stream_used, stream_move_at;
bool stream_full;
BufferRef stream_copy(const void* src, uint64_t n) {
    if (stream_full || !n) return {};
    uint64_t at = (stream_used + 255) & ~255ull;
    if (stream_move_at && !stream_now && at + n > stream_move_at) stream_now = 1, at = 0;
    if (at + n > kStream) return {};
    std::memcpy(stream_bytes[stream_now].data() + at, src, n);
    stream_used = at + n;
    return {stream_buffer(stream_now), at, n, 0};
}
unsigned cpu_writes;
int guest_cpu_write(uint64_t, const void*, uint64_t) { return ++cpu_writes, 1; }
// ---- the commands, applied as they are recorded ----
struct Range { int pool; uint64_t lo, hi; };
std::vector<Range> pending;   // (written since the last full barrier)
std::vector<unsigned> copy_regions;   // (each copy's region count, in order)
unsigned barriers, updates, hazards, region_overlaps, bad;
void wrote(int pool, uint64_t lo, uint64_t hi) {
    for (const Range& r : pending) if (r.pool == pool && lo < r.hi && r.lo < hi) ++hazards;
    pending.push_back({pool, lo, hi});
}
namespace rec {
void rx_vkCmdPipelineBarrier2(VkCommandBuffer cmd, const VkDependencyInfo* d) {
    if (cmd != cb || d->memoryBarrierCount != 1) { ++bad; return; }
    const auto& b = *d->pMemoryBarriers;
    if ((b.srcStageMask & VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT) && (b.dstStageMask & VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT) &&
        (b.srcAccessMask & VK_ACCESS_2_MEMORY_WRITE_BIT) && (b.dstAccessMask & VK_ACCESS_2_MEMORY_WRITE_BIT)) pending.clear();
    ++barriers;
}
void rx_vkCmdUpdateBuffer(VkCommandBuffer cmd, VkBuffer target, VkDeviceSize offset, VkDeviceSize n, const void* data) {
    const int pool = pool_of(target);
    if (cmd != cb || pool < 0 || !n || n > 65536 || (offset & 3) || (n & 3) || offset + n > kPool) { ++bad; return; }
    wrote(pool, offset, offset + n), ++updates;
    std::memcpy(memory[pool].data() + offset, data, n);
}
void rx_vkCmdCopyBuffer(VkCommandBuffer cmd, VkBuffer src, VkBuffer target, uint32_t count, const VkBufferCopy* r) {
    const int pool = pool_of(target), from = src == stream_buffer(0) ? 0 : src == stream_buffer(1) ? 1 : -1;
    if (cmd != cb || pool < 0 || from < 0 || !count) { ++bad; return; }
    copy_regions.push_back(count);
    // (Vulkan: the union of a copy's destination regions must not overlap itself; which of two such regions lands last is
    // not defined. Applied here LAST REGION FIRST, so a later update of the same bytes in one copy loses, and shows)
    for (uint32_t i = 0; i < count; i++)
        for (uint32_t j = 0; j < i; j++)
            if (r[i].dstOffset < r[j].dstOffset + r[j].size && r[j].dstOffset < r[i].dstOffset + r[i].size) ++region_overlaps;
    for (uint32_t i = count; i-- > 0;) {
        if (!r[i].size || r[i].srcOffset + r[i].size > kStream || r[i].dstOffset + r[i].size > kPool) { ++bad; continue; }
        wrote(pool, r[i].dstOffset, r[i].dstOffset + r[i].size);
        std::memcpy(memory[pool].data() + r[i].dstOffset, stream_bytes[from].data() + r[i].srcOffset, r[i].size);
    }
}
}
// ---- what flush_ub_updates and full_barrier use ----
std::atomic<uint64_t> work_epoch{0};
std::atomic<bool> par_active{false};
std::atomic<int64_t> st_barriers_left_out{0}, st_barriers_made{0};
VkCommandBuffer last_barrier_cmd{};
uint64_t last_barrier_epoch = 0;
bool env_on(const char*) { return false; }
// (the rest of full_barrier's state, as vk_texture.cpp keeps it: note_work's count, the parallel replay's dedupe
// (RX_VK_BARRIER_DEDUPE_PAR, off here: par_active is false) and the trust points' counts, which this test does not read)
std::atomic<uint64_t> foreign_work{0}, other_work_by_cmd[64], xfer_work_by_cmd[64], all_work_by_cmd[64];
void logf(const char*, ...) {}
bool barrier_dedupe_par_on() { return false; }
std::atomic<int64_t> st_barriers_left_out_par{0};
uint64_t last_barrier_cmd_work = 0, last_barrier_foreign = 0, last_barrier_other = 0, last_barrier_xfer = 0;
void note_trust_point(VkCommandBuffer) {}
struct GprofSpan { int items = 0; uint64_t bytes = 0; GprofSpan(VkCommandBuffer, const char*) {} };
constexpr uint32_t kRbWriterUb = 0x10000;
void memory_writer_note(uint32_t, uint64_t) {}
@@UBUPDATE@@
std::deque<UbUpdate> ub_updates;
size_t ub_first_of_recording = 0;
'''

SUFFIX = r'''
uint8_t seed;
void reset() {
    pending.clear(), copy_regions.clear(), ub_updates.clear();
    barriers = updates = hazards = region_overlaps = bad = cpu_writes = 0;
    stream_now = 0, stream_used = 0, stream_move_at = 0, stream_full = false;
    ub_first_of_recording = 0, last_barrier_cmd = VK_NULL_HANDLE, seed = 0;
    for (int i = 0; i < 2; i++) std::fill(memory[i].begin(), memory[i].end(), 0), std::fill(want[i].begin(), want[i].end(), 0);
}
/// An update of n bytes at off of a pool (or, pool 2, of the gap no import holds), its bytes unlike every other's
void update(int pool, uint64_t off, uint64_t n) {
    std::vector<uint8_t> b(n);
    ++seed;
    for (uint64_t i = 0; i < n; i++) b[i] = (uint8_t)(seed * 37 + i * 3 + 1);
    if (pool < 2) std::memcpy(want[pool].data() + off, b.data(), std::min(n, kPool - off));   // (past the pool: no import)
    ub_updates.push_back({1, pool < 2 ? kBase[pool] + off : 0x180000 + off, std::move(b)});
}
int fails;
void expect(bool ok, const char* what, const char* name) {
    if (!ok) std::printf("FAIL: %s: %s\n", name, what), ++fails;
}
/// The flush run, and what every case must show: memory as the updates in stream order left it, no write of bytes written
/// since the last barrier, no copy whose regions overlap, and one barrier before each copy and each update, one after
void flush(const char* name, std::vector<unsigned> regions, unsigned want_updates = 0, unsigned want_cpu = 0) {
    flush_ub_updates(cb);
    expect(!bad, "a command Vulkan does not allow", name);
    expect(!region_overlaps, "a copy's regions overlap in the destination", name);
    expect(!hazards, "overlapping uniform updates are unordered: no barrier between two writes of the same bytes", name);
    expect(memory[0] == want[0] && memory[1] == want[1], "memory is not what the updates in stream order leave", name);
    expect(copy_regions == regions, "the updates were not batched as expected (copies and their regions)", name);
    expect(updates == want_updates && cpu_writes == want_cpu, "the fallback writes are not as expected", name);
    expect(barriers == regions.size() + want_updates + 1, "not one barrier before each copy and one after the last", name);
}
int check() {
    // (a frame's shape: 80 updates of different bytes of one import, aligned or not: ONE copy, between two barriers)
    reset();
    for (int i = 0; i < 80; i++) update(0, 0x1000 + i * 0x140 + (i % 5 == 0), 0x100 + (i % 3));
    flush("80 updates of different bytes", {80});
    // (the window: only the updates from ub_first_of_recording on)
    reset();
    update(0, 0x40, 16), update(0, 0x80, 16);
    ub_first_of_recording = 1;
    std::fill(want[0].begin() + 0x40, want[0].begin() + 0x50, 0);
    flush("the recording's window", {1});
    // (the same bytes twice: the second starts a new copy behind its own barrier, and wins. Touching ranges do not overlap)
    reset();
    update(0, 0x40, 16), update(0, 0x80, 16), update(0, 0x50, 16), update(0, 0x48, 64), update(0, 0x200, 8), update(0, 0x40, 16);
    flush("overlapping updates", {3, 2, 1});
    reset();
    for (int i = 0; i < 4; i++) update(0, 0x100, 64);
    flush("one range written four times", {1, 1, 1, 1});
    reset();
    update(0, 0x100, 64), update(0, 0xfd, 4), update(0, 0x13f, 5), update(0, 0x90, 0x200);   // (a byte at either end, the second clear of the first; then all of them)
    flush("partial overlaps", {1, 2, 1});
    // (two imports: a copy writes one buffer, and a change of buffer is a new copy behind a barrier)
    reset();
    update(0, 0x40, 16), update(0, 0x80, 16), update(1, 0x40, 16), update(1, 0x80, 16), update(0, 0x100, 16);
    flush("two buffers", {2, 2, 1});
    // (more than vkCmdUpdateBuffer's 64 KB, and across the first pool's end into memory no import holds: in pieces)
    reset();
    update(0, 0x1000, 0x10000 + 0x30);
    flush("more than 64 KB", {2});
    reset();
    update(0, kPool - 8, 16), update(2, 0x100, 16);
    flush("no import", {1}, 0, 2);
    // (the recording's stream moves to a bigger buffer: a copy reads one source)
    reset();
    stream_move_at = 0x300;
    for (int i = 0; i < 6; i++) update(0, 0x1000 + i * 0x100, 0x80);
    flush("the stream moves", {3, 3});
    // (no room in the stream: written as before, in stream order with the batch before it)
    reset();
    update(0, 0x40, 16), update(0, 0x80, 16);
    flush_ub_updates(cb);
    ub_first_of_recording = 2, stream_full = true;
    update(0, 0x48, 16), update(0, 0x40, 16);
    flush("a full stream", {2}, 2);   // (the first flush's copy and its two barriers, then two updates and the last barrier)
    return fails;
}
}
int main() {
    if (mkwvk::check()) return 1;
    std::puts("PASS: uniform updates are batched into one copy behind one barrier, and split in stream order where they overlap");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--headers", required=True, type=Path)
    args = parser.parse_args()
    vk = ROOT / "gpu/vk"
    replay = (vk / "vk_replay.cpp").read_text(encoding="utf-8")
    flush = block(replay, "void flush_ub_updates(VkCommandBuffer cmd) {")
    add = block(replay, "bool ub_batch_add(UbBatch& b, VkBuffer src, VkBuffer dst, uint64_t from, uint64_t at, uint64_t k) {")
    emit = block(replay, "void ub_batch_emit(VkCommandBuffer cmd, UbBatch& b) {")
    # (the flush goes through the batch only, and through gpu_put for what the stream has no room for: no write of its own)
    code = "\n".join(line.split("//")[0] for line in flush.splitlines())
    if "vkCmd" in code or "gpu_write(" in code:
        raise SystemExit("FAIL: flush_ub_updates records writes of its own: each update a barrier and a write again?")
    if code.count("ub_batch_emit(cmd, batch);") != 3 or code.count("full_barrier(cmd);") != 1:
        raise SystemExit("FAIL: flush_ub_updates no longer ends a batch where one does not take an update, before a "
                         "write outside it and at the end, with one barrier after the last")
    parts = [block(replay, "BufferRef gpu_piece_bind(uint64_t gpu, uint64_t& n) {"),
             block(replay, "bool gpu_put(VkCommandBuffer cmd, const BufferRef& b, const uint8_t* d, uint64_t k) {"),
             block(replay, "struct UbBatch {") + ";", add, emit, flush]
    barrier = block((vk / "vk_texture.cpp").read_text(encoding="utf-8"), "void full_barrier(VkCommandBuffer cmd, const char* why) {")
    texture_h = (vk / "vk_texture.h").read_text(encoding="utf-8")
    declaration = between(texture_h, "void full_barrier(", "\n")
    work = (vk / "vk_work.h").read_text(encoding="utf-8")
    note = block(work, "inline void note_work() {")
    # (full_barrier reads a command buffer's counts through vk_work.h's own slot helpers)
    note = "".join(block(work, m) for m in ("inline std::atomic<uint64_t>& other_work_slot(",
                                            "inline std::atomic<uint64_t>& all_work_slot(")) + note
    wrappers = [between(work, "#define " + name + "(", "\n")
                for name in ("vkCmdPipelineBarrier2", "vkCmdUpdateBuffer", "vkCmdCopyBuffer")]
    prefix = PREFIX.replace("@@BUFFERREF@@", block((vk / "vk_internal.h").read_text(encoding="utf-8"), "struct BufferRef {")) \
                   .replace("@@UBUPDATE@@", block(replay, "struct UbUpdate {") + ";")
    source = (prefix + note + "\n}\n" + "\n".join(wrappers) + "\nnamespace mkwvk {\n" + declaration + "\n" + barrier + "\n" +
              "\n".join(parts) + SUFFIX)
    overlap = ("    if (next != b.held.end() && next->first < at + k) return false;\n"
               "    if (next != b.held.begin() && std::prev(next)->second > at) return false;\n")
    buffers = "    if (!b.regions.empty() && (b.src != src || b.dst != dst)) return false;\n"
    barrier_line = "    full_barrier(cmd);   // overlapping inline writes must reach memory in stream order\n"
    for name, text, cut in (("the overlap rule", add, overlap), ("the buffers rule", add, buffers),
                            ("the batch's barrier", emit, barrier_line)):
        if text.count(cut) != 1:
            raise SystemExit("FAIL: negative-control source moved: " + name)
    variants = [("current", source, None),
                ("no_overlap_rule", source.replace(overlap, ""), "a copy's regions overlap in the destination"),
                ("no_buffers_rule", source.replace(buffers, ""), "memory is not what the updates in stream order leave"),
                ("no_batch_barrier", source.replace(emit, emit.replace(barrier_line, "")),
                 "overlapping uniform updates are unordered")]
    with tempfile.TemporaryDirectory(prefix="ub-batch-") as tmp:
        for name, text, message in variants:
            if message and text == source:
                raise SystemExit("FAIL: negative-control source moved: " + name)
            cpp, exe = Path(tmp) / (name + ".cpp"), Path(tmp) / (name + (".exe" if os.name == "nt" else ""))
            cpp.write_text(text, encoding="utf-8")
            cmd = [args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
                   "-Wno-unused-parameter", "-I" + str(args.headers), str(cpp), "-o", str(exe)]
            if os.name == "nt":
                cmd.append("-static")
            build = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if build.returncode:
                raise SystemExit("FAIL: " + name + " did not build\n" + build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            if message is None and result.returncode:
                raise SystemExit(result.stdout + result.stderr + "FAIL: the uniform updates' batching")
            if message is not None and (not result.returncode or message not in result.stdout):
                raise SystemExit("FAIL: with " + name.replace("_", " ") + " the check still passes, or fails for another "
                                 "reason:\n" + result.stdout + result.stderr)
            print(name + ": " + (result.stdout.strip().splitlines() or ["(no output)"])[0])
    print("PASS")


if __name__ == "__main__":
    main()
