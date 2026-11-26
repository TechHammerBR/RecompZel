"""invalidate_quick (gpu/vk/vk_replay.cpp): an invalidate with nothing in its range to wait for is done with the game thread's
virtual core kept (host/rx_backend.c), from lock-free marks (gpu/vk/page_marks.h) that the write-backs (vk_memory.cpp
wb_pages_note) and the list of textures the GPU wrote (vk_texture.cpp vw_note) set. Compiles the production pieces with
tests/invalidate_quick_test.cpp and runs its cases: the marks, their agreement with the locked tables they stand for, the
order between a note and a reader, and the look itself with and without its switches. Then reads the sources for what the
look relies on: every write-back and every listing marks under its lock, and invalidate waits only behind the three tests
the look makes (a new switch or early step in invalidate is a question for invalidate_quick: this check asks it).

python -I -B tests/test_invalidate_quick.py [--cxx clang++]
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block, between   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
# (case, the environment it runs with)
CASES = (("marks", {}), ("agree-wb", {}), ("agree-vw", {}), ("threads", {}), ("quick", {}),
         ("quick-off", {"RX_VK_INVALIDATE_QUICK": "0"}), ("quick-log", {"RX_VK_LOG_INVALIDATE": "1"}),
         ("quick-readback", {"RX_VK_LOG_READBACK": "0"}))
SWITCHES = ("RX_VK_INVALIDATE_QUICK", "RX_VK_LOG_INVALIDATE", "RX_VK_LOG_READBACK")   # (RX_VK_INVALIDATE_WAIT is gone)
# invalidate's switches that change nothing when its range has no write-back and no texture: they act inside the branches
# the look keeps it out of (or, RX_VK_READBACK_OFF_FILE, only skip the texture branch's own early returns)
INSIDE = {"RX_VK_NO_READBACK_WAIT", "RX_VK_READBACK_NO_CATCHUP", "RX_VK_READBACK_EXACT", "RX_VK_READBACK_PART",
          "RX_VK_LOG_READBACK_WAITS", "RX_VK_LOG_READBACK_RANGES", "RX_VK_READBACK_OFF_FILE"}


def checks(memory, texture, replay, backend):
    note = block(memory, "void wb_pages_note(")
    lock, mark, first = note.index("std::lock_guard lk(wb_pages_mu);"), note.index("wb_ever.mark("), note.index("wb_pages.set(")
    assert lock < mark < first, "wb_pages_note must mark wb_ever under wb_pages_mu, before the pages' values"
    assert memory.count("wb_pages.set(") == 1, "a page's write-back value is set outside wb_pages_note: does it mark wb_ever?"
    assert re.findall(r"\bwb_ever\.\w+", memory) == ["wb_ever.mark", "wb_ever.any"], "wb_ever is marked or read elsewhere"
    listing = block(texture, "void vw_note(")
    assert listing.index("std::lock_guard lk(vw_mu);") < listing.index("vw_ever.mark(") < listing.index("vw[t.gpu]"), \
        "vw_note must mark vw_ever under vw_mu as it lists the texture"
    # (vw_note lists a texture; vw_forget lists again the others at that start, which vw_note marked)
    assert texture.count("vw[t.gpu]") == 2 and "vw[t.gpu]" in block(texture, "void vw_forget(const Texture& t) {"), \
        "the GPU-written textures' list takes entries elsewhere: does it mark vw_ever?"
    assert re.findall(r"\bvw_ever\.\w+", texture) == ["vw_ever.mark", "vw_ever.any"], "vw_ever is marked or read elsewhere"
    inv = block(replay, "void invalidate(uint64_t gpu, uint64_t size) {")
    # what the look stands in for: invalidate's buffer branch behind `ever`, its texture branch behind the listed textures
    # and the live storage, and the CPU's read noted first
    assert "(memory_writeback_value(host->gpu_guest(gpu), size, &ever), ever)" in inv, \
        "invalidate's waits for write-backs are no longer behind `ever`: what does invalidate_quick test now?"
    tex = inv[inv.index("if (!texture_gpu_written_in(gpu, size)) {"):]
    assert tex.index("if (!replay_behind()) return;") < tex.index("if (!tex_pages_any(gpu, size)) return;") \
        < tex.index("unforced ? sync_settle() : wait_queue_empty();"), \
        "invalidate's texture branch returns differently: what does invalidate_quick test now?"
    assert inv.count("memory_note_cpu_read(") == 1, "invalidate notes the CPU's read differently from invalidate_quick"
    named = set(re.findall(r'"(RX_VK_[A-Z0-9_]+)"', inv))
    quick = block(replay, "int invalidate_quick(")
    for s in SWITCHES:
        assert '"%s"' % s in quick, "invalidate_quick no longer reads " + s
    unknown = named - INSIDE - set(SWITCHES)
    assert not unknown, "invalidate reads a switch invalidate_quick does not know: %s (inside a branch it skips, or one " \
                        "it must turn itself off for?)" % ", ".join(sorted(unknown))
    for need in ("tex_pages_any(gpu, size)", "texture_gpu_written_ever(gpu, size)",
                 "memory_writeback_ever(host->gpu_guest(gpu), size)", "if (kept) memory_note_cpu_read(host->gpu_guest(gpu), size);"):
        assert need in quick, "invalidate_quick no longer has " + need
    assert "t.nvn_invalidate_quick = invalidate_quick;" in replay, "the back end no longer hands out invalidate_quick"
    wrapper = block(backend, "void rx_nvn_invalidate(")
    assert wrapper.index("vk->nvn_invalidate_quick(gpu, size)") < wrapper.index("hos_vcore_away()"), \
        "rx_nvn_invalidate must look before it gives up the core (tests/test_invalidate_vcore.py runs it)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    read = lambda rel: (args.source / rel).read_text(encoding="utf-8")   # noqa: E731
    memory, texture, replay = read("gpu/vk/vk_memory.cpp"), read("gpu/vk/vk_texture.cpp"), read("gpu/vk/vk_replay.cpp")
    checks(memory, texture, replay, read("host/rx_backend.c"))
    wb = (memory[memory.index("std::mutex wb_pages_mu;"):memory.index("uint64_t memory_writeback_value(")] +
          block(memory, "uint64_t memory_writeback_value("))
    vw = "\n".join([between(texture, "constexpr uint64_t kFlushMax", "bool flushable("), block(texture, "void vw_note("),
                    block(texture, "void vw_forget(const Texture& t) {"), block(texture, "bool texture_gpu_written_in("),
                    block(texture, "bool texture_gpu_written_ever(")])
    decide = (between(replay, "std::atomic<int64_t> inv_kept{0}", "void invalidate(uint64_t gpu, uint64_t size) {") +
              block(replay, "int invalidate_quick("))
    compiler = shutil.which(args.cxx)
    if not compiler:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
    env = dict(os.environ)
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    for s in SWITCHES + ("RX_VK_NO_READBACK_WAIT", "RX_VK_NO_VMAP_FLUSH"):
        env.pop(s, None)
    with tempfile.TemporaryDirectory(prefix="invalidate-quick-") as temporary:
        tmp = Path(temporary)
        for name, text in (("quick_wb.inc", wb), ("quick_vw.inc", vw), ("quick_decide.inc", decide)):
            (tmp / name).write_text(text + "\n", encoding="utf-8")
        exe = tmp / "invalidate_quick.exe"   # (the name llvm-mingw writes on Windows; any name runs on Linux)
        command = [compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-pthread", "-D_CRT_SECURE_NO_WARNINGS",
                   "-I" + str(args.source), "-I" + str(tmp), str(ROOT / "tests/invalidate_quick_test.cpp"), "-o", str(exe)]
        def run(cmd, extra, timeout):   # (the output printed: CREATE_NO_WINDOW leaves a child no console to write to)
            r = subprocess.run(cmd, env={**env, **extra}, creationflags=flags, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
            print((r.stdout + r.stderr).strip())
            if r.returncode:
                raise SystemExit("FAIL: %s exited %d" % (cmd[-1] if cmd[0] == str(exe) else "the compile", r.returncode))

        run(command, {}, 300)
        for case, extra in CASES:
            run([str(exe), case], extra, 60)
    print("PASS: invalidate_quick's sources: marks under the tables' locks, invalidate's waits behind the look's tests")


if __name__ == "__main__":
    main()
