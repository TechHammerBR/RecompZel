"""A waited-for job still in the queue runs on the waiting thread at once (gpu/vk/vk_jobs.cpp jobs_wait; no game/GPU).

vk_jobs.cpp is compiled beside stand-ins for vk_internal.h and vk_draw.h (logging, the thread calls, ub_thread_off) and
run with every worker held in a job: the draw's pipeline job, queued behind them, must run on the thread that waits, and
only there (the queue keeps no copy for a worker). Free workers racing two waiters for the same job: it runs once.
python -I -B tests/test_jobs_wait_runs_queued.py
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STUB_INTERNAL = """#pragma once
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <thread>
using HANDLE = void*;
constexpr int THREAD_PRIORITY_BELOW_NORMAL = -1;
inline HANDLE GetCurrentThread() { return nullptr; }
inline int SetThreadPriority(HANDLE, int) { return 1; }
inline long SetThreadDescription(HANDLE, const wchar_t*) { return 0; }
namespace mkwvk {
inline void logf(const char*, ...) {}
// (dev.policy.workers, which start() reads: gpu/vk/device_policy.h makes it of the PC's threads, 2 to 6, and of
// RX_VK_WORKERS, and tests/test_device_policy.py checks both. No device here: 4, or the run's RX_VK_WORKERS)
struct StandInDevice { struct { unsigned workers; } policy; };
inline StandInDevice dev{{std::getenv("RX_VK_WORKERS") ? (unsigned)std::atoi(std::getenv("RX_VK_WORKERS")) : 4u}};
}
"""

STUB_DRAW = """#pragma once
namespace mkwvk {
inline void ub_thread_off() {}
inline void pipeline_cache_between_builds() {}
}
"""


def check_source():
    """The pipeline and translation jobs a draw waits for are pushed with their flags, and jobs_wait still looks for them in the queue"""
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    if "}, false, &e->ready," not in draw:
        raise SystemExit("graphics_pipeline's build job is pushed without its ready flag")
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8")
    if shader.count("&raw->ready,") < 2:
        raise SystemExit("a graphics or mesh translation job is pushed without its ready flag")
    jobs = (ROOT / "gpu/vk/vk_jobs.cpp").read_text(encoding="utf-8")
    wait = jobs[jobs.index("bool jobs_wait("):]
    wait = wait[:wait.index("\n}\n")]
    if "it->flag == &flag" not in wait:
        raise SystemExit("jobs_wait no longer runs a queued job it waits for")
    if "queue.erase(it)" not in wait:
        raise SystemExit("jobs_wait runs a queued job without taking it out of the queue: a worker would run it again")
    block = draw[draw.index("void draw(VkCommandBuffer"):]
    block = block[:block.index("    dlss_trace_draw(s, p, d, at);")]
    pipe = block[block.index("if (!pe->ready.load(std::memory_order_acquire))"):]
    if "wait_for(pe->ready)" not in pipe or "jobs_wait(ready)" not in block[block.index("auto wait_for = "):]:
        raise SystemExit("draw()'s pipeline wait no longer goes through jobs_wait, which runs the queued build there")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="jobs-wait-") as tmp:
        tmp = Path(tmp)
        for name in ("vk_jobs.cpp", "vk_jobs.h"):
            shutil.copy(ROOT / "gpu/vk" / name, tmp / name)
        (tmp / "vk_internal.h").write_text(STUB_INTERNAL, encoding="utf-8")
        (tmp / "vk_draw.h").write_text(STUB_DRAW, encoding="utf-8")
        exe = tmp / "jobs-wait"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-pthread", "-I", str(tmp),
                        "-I", str(ROOT / "gpu/vk/compat"),
                        str(tmp / "vk_jobs.cpp"), str(ROOT / "tests/test_jobs_wait_runs_queued.cpp"), "-o", str(exe)],
                       check=True)
        for mode in ("steal", "race"):
            subprocess.run([str(exe), mode], check=True, timeout=60)
        # (jobs_hurry, quick pipelines' brief wait: one worker, so that the order the queue runs in is the order checked)
        env = dict(os.environ)
        env["RX_VK_WORKERS"] = "1"
        subprocess.run([str(exe), "hurry"], check=True, timeout=60, env=env)


if __name__ == "__main__":
    main()
