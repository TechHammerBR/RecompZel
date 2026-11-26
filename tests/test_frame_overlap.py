"""Frame overlap: what a frame's recordings do to the game's memory, and where the GPU's time goes between them
(gpu/vk/frame_overlap.h, gpu/vk/vk_replay.cpp; docs/development/frame-pipeline.md).

OoT's main thread waits once a frame, with no timeout, for the fence of the frame before's present, and makes the CPU signal
its next frame's work waits for only after it: the render thread gets a frame once the GPU has finished the one before. The
renderer counts, per recording, whether it reads the game's memory at the GPU's time and whether its part's end writes any
back, and the GPU's time between recordings, idle and in upload command buffers, by where in the frame. That is all it
does: an early answer to the game's wait (RX_VK_FRAME_WAIT_EARLY), short first parts and a look of the render thread
before it sleeps were each built, measured to gain nothing, and removed (the page has the numbers).

The rules are compiled and run (tests/frame_overlap_test.cpp). And the source:
- the game's waits are wait(), parts end by RX_VK_CHUNK alone, and the render thread sleeps on its queue: none of the
  three removed things is back;
- every recording is counted at its end, before its submit; a frame ends at its present's own recording;
- a draw or dispatch is only counted where it pushes its constants: nothing there ends a part;
- the presenter thread (RX_VK_PRESENT_THREAD) has the swapchain to itself: present_image waits for it before it acquires.

python -I -B tests/test_frame_overlap.py [--cxx g++]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (python -I leaves the check's own folder off the path)
from srccut import block  # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def need(cond, why):
    if not cond:
        raise SystemExit("FAIL: " + why)


def check_source():
    vk = ROOT / "gpu" / "vk"
    replay = (vk / "vk_replay.cpp").read_text(encoding="utf-8")
    draw = (vk / "vk_draw.cpp").read_text(encoding="utf-8")
    table = (vk / "switches.def").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    page = (ROOT / "docs" / "development" / "frame-pipeline.md").read_text(encoding="utf-8")
    need('#include "frame_overlap.h"' in replay, "vk_replay.cpp no longer includes frame_overlap.h")

    # (the early wait is gone: measured, nothing to gain)
    need(("t.nvn_wait = wait;" in replay or "t.nvn_wait = Guarded<static_cast<int (*)(uint64_t, uint64_t)>(&wait)>::call;" in replay) and '"RX_VK_FRAME_WAIT_EARLY"' not in replay and "RX_VK_FRAME_WAIT_EARLY" not in table,
         "the game's waits are not wait(), or the removed early wait is back")
    need("development/frame-pipeline.md" in docs and "vk: frame overlap (600 presents)" in page and "RX_VK_FRAME_WAIT_EARLY" in page,
         "docs/development.md does not link the frame pipeline's page, or the page lost the log line or the record of the early wait")

    # (every recording counted at its end; a frame ends at its present's own recording)
    end = block(replay, "void fo_recording_end(const Recording& r) {")
    need("const uint64_t seq = rec_seq + 1;" in end, "a recording is not counted with the number its submit gives it")
    need("frame_overlap::RecordingFacts f{fo.follows - fo.follows0, wb - fo.wb0, memory_in_place_part(), r.part};" in end,
         "a recording's facts are not the readers, the bytes written back and the in-place part since the recording before")
    need("fo_slots[r.slot] = {seq, frame_overlap::gap_column(fo.frame_working)};" in end, "a recording's place in its frame is not kept")
    noted = end[end.index("if (!present || r.value != present) return;"):]
    need("fo.frame_working = 0;" in noted, "a frame's counts do not begin again at its present's own recording")
    need(block(replay, "void gpu_time_end(Recording& r, bool uploads = false) {").lstrip().split("\n")[1].strip().startswith("fo_recording_end(r);"),
         "a recording is not counted at its end, before its submit")
    need(replay.count("fo_present.store(") == 3,
         "the render thread does not name each present before it is made (the job's and the held one's), and only those")
    for site in ("present_value = j.value;", "present_value = held_present.value;"):
        at = replay[replay.index(site):]
        need(at.index("fo_present.store(") < at.index("do_present("),
             "a present's value is not set for the frame's end before the present is made: " + site)
    collect = block(replay, "void fo_collect(const Recording& r, const uint64_t* t) {")
    need("frame_overlap::gap(fo.last_end, up, t[0], period);" in collect and "fo.last_end = 0;" in collect and
         "fo_st.idle_ns[s.column] += g.idle_ns, fo_st.uploads_ns[s.column] += g.uploads_ns;" in collect,
         "the GPU's time between recordings is not split into idle and uploads by place, or counts across a recording with no timestamps")
    begin = block(replay, "void fo_recording_begin(const Recording& r) {")
    need("vkCmdWriteTimestamp2(r.upload, VK_PIPELINE_STAGE_2_TOP_OF_PIPE_BIT, fo_up_pool, (uint32_t)r.slot);" in begin and
         "r.cmd" not in begin, "the uploads' timestamp is not written at the start of the recording's upload command buffer")
    need("fo_log(frames);" in block(replay, "void bh_log() {") and
         '"vk: frame overlap (600 presents): ' in block(replay, "void fo_log(double frames) {") and
         '"vk: frame overlap, by place: ' in block(replay, "void fo_log(double frames) {"),
         "the frame overlap's line is not logged with the render thread's, or changed its name")

    # (each draw and dispatch only counted where it pushes its constants; the removed things stay removed)
    push = block(draw, "void push_constants(VkCommandBuffer cmd, const Program& p, const Targets* at, uint32_t fallback_first = 0) {")
    need(push.index("frame_overlap_op(follows);") < push.index("if (!p.uses_push) return;") and "bool follows = !at;" in push and
         "follows |= st.info.uses_global_memory;" in push, "a draw or dispatch is not counted, or not as reading the game's memory when it does")
    op = block(replay, "void frame_overlap_op(bool follows) {")
    need("fo.follows += follows;" in op and "part_end_wanted" not in op and "split_part(" not in op,
         "counting a draw ends a part: the short first parts are back")
    need("kRenderSpinUs" not in replay and "std::this_thread::yield();" not in block(replay, "void replay_thread_main() {"),
         "the render thread looks for a job before it sleeps again")

    # (frame ahead: counters only. A part of the signal's job is tallied with what the mirror syncs took since the part before)
    memory = (vk / "vk_memory.cpp").read_text(encoding="utf-8")
    need("fa.tally.part({cap - fa.cap0, live - fa.live0});" in end and "if (fa_in_signal.load(" in end and "fa.tally.frame_end();" in noted,
         "a part of the signal's job is not tallied with what it took, or the tally's frame does not end at the present")
    sig = block(replay, "void fa_signal_begin() {")
    need(sig.index("memory_capture_peek(&pages, &pools);") < sig.index("memory_sync_sources(&fa.cap0, &fa.live0);") <
         sig.index("fa_in_signal.store(true"), "the signal's capture is not looked at, or the parts' counts do not start, before the job records")
    job = replay[replay.index("case JOB_EVENT_SIGNAL:"):]
    need(job.index("if (j.id) fa_signal_begin();") < job.index("memory_take_capture(j.queue, completed());") <
         job.index("burst_end();") < job.index("fa_in_signal.store(false"),
         "the signal's capture is looked at after it is taken, or the count runs on past the signal's job")
    peek = block(memory, "void memory_capture_peek(int64_t* pages, int64_t* pools) {")
    need("captures.front()->pages" in peek and "pop_front" not in peek and "std::move" not in peek,
         "looking at the next capture takes it, or changes it")
    need("*capture = st_sync_cap_pages, *live = st_sync_live_pages;" in block(memory, "void memory_sync_sources(int64_t* capture, int64_t* live) {"),
         "the parts' counts are not mirror_sync's own (this submit's capture, guest memory as it is)")
    need('"vk: frame ahead (600 presents): ' in block(replay, "void fo_log(double frames) {") and "vk: frame ahead (600 presents)" in page,
         "the frame ahead line is gone from the log or from the page")
    for word in ("part_end_wanted", "submit_recording(", "vkQueueSubmit", "split_part("):
        need(word not in sig, "the frame ahead counters change what is recorded or submitted: " + word)

    # (the presenter thread: the swapchain is one thread's at a time)
    image = block(replay, "void present_image(")
    need(image.rindex("present_thread_drain();", 0, image.index("vkAcquireNextImageKHR(")) > image.index("frame_index = (slot + 1) % slots;"),
         "present_image acquires the next image while the presenter thread may still present the last")
    copy = block(replay, "bool presenter_wait_copy(VkFence done) {")
    need("step < 40;" in copy and "presenter_wait_idle(lk, 5000)" in block(replay, "void present_thread_drain() {"),
         "the presenter's own wait for the copy is not shorter than a drain's wait for the presenter")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="frame-overlap-") as tmp:
        exe = Path(tmp) / "frame-overlap"
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/frame_overlap_test.cpp"), "-o", str(exe)],
                       check=True)
        subprocess.run([str(exe)], check=True, timeout=60)
    print("PASS: frame overlap counts what recordings do and where the GPU's time goes")


if __name__ == "__main__":
    main()
