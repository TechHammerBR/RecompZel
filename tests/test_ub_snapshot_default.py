"""The uniform snapshot (gpu/vk/vk_draw.cpp ub_snapshot_wanted, RX_VK_UB_SNAPSHOT) is on by default on every Intel GPU,
its discrete Arc cards with VRAM mirrors included, and off elsewhere; uniform_range asks it. The decision compiled alone
against a table; no game or GPU required.

Bound where the game keeps them, a frame's uniforms are read by the GPU after the game has written the next frame's over
them: on an Arc B580 (101.9154, mirrors on) the Kokiri Forest floor and the treehouses went to sky, with white glowing
blocks and pots that came and went, as on the Intel iGPUs the snapshot was first made for.

python -I -B tests/test_ub_snapshot_default.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"


def block(text, marker):
    """From marker to the brace closing its first one"""
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


# RX_VK_UB_SNAPSHOT's value (None: unset), the GPU (vendor, integrated, pools mirrored), and whether the uniforms are
# snapshotted: every Intel GPU; (hookshot) and an integrated one without mirrors (the Steam Deck); off elsewhere
VENDORS = {"intel": 0x8086, "amd": 0x1002, "nvidia": 0x10DE}
GPUS = {"intel": (0x8086, 0, 1), "intel-igpu": (0x8086, 1, 0), "amd": (0x1002, 0, 1), "amd-nomirror": (0x1002, 0, 0),
        "amd-apu": (0x1002, 1, 0), "amd-apu-mirrored": (0x1002, 1, 1), "nvidia": (0x10DE, 0, 1)}
DEFAULTS = {"intel": 1, "intel-igpu": 1, "amd": 0, "amd-nomirror": 0, "amd-apu": 1, "amd-apu-mirrored": 0, "nvidia": 0}
# (unset and an empty value are the PC's default, by device_policy.h's one rule for the switches)
CASES = ([(None, g, w) for g, w in DEFAULTS.items()] + [("", g, w) for g, w in DEFAULTS.items()] +
         [(v, g, 1) for v in ("1", "on", "yes") for g in GPUS] +
         [(v, g, 0) for v in ("0", "off", "false", "no") for g in GPUS])
# The decision is device_policy.h's (ub_snapshot: the rule, then the switch by device_policy_env), which ub_snapshot_wanted
# returns, with Hookshot's integrated GPUs without mirrors while the switch is not set: the fixture makes the policy of the
# GPU with the switch's value in place of the environment, and asks the function cut from vk_draw.cpp
FIXTURE = r"""
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "device_policy.h"
using namespace mkwvk;
static struct { mkwvk::DevicePolicy policy; struct { unsigned vendorID; int deviceType; } props; } dev;
static bool mirrored;
static bool pools_mirrored() { return mirrored; }
static const char* the_value;   // (the switch's value, nullptr: unset; read in place of the environment)
static const char* fake_getenv(const char* name) { return strcmp(name, "RX_VK_UB_SNAPSHOT") ? nullptr : the_value; }
@@DECISION@@
int main(int argc, char** argv) {
    // (argv: value or -unset, the vendor, integrated, mirrored, 1 snapshotted or 0)
    for (int i = 1; i + 4 < argc; i += 5) {
        the_value = strcmp(argv[i], "-unset") ? argv[i] : nullptr;
        mkwvk::DeviceFacts f;
        f.vendor_id = (unsigned)strtoul(argv[i + 1], nullptr, 0);
        f.device_type = atoi(argv[i + 2]) ? VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU : VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
        dev.policy = mkwvk::device_policy(f);
        mkwvk::device_policy_env(dev.policy, f, fake_getenv);
        dev.props.vendorID = f.vendor_id, dev.props.deviceType = (int)f.device_type;
        mirrored = atoi(argv[i + 3]) != 0;
        const bool got = ub_snapshot_wanted();
        if (got != (atoi(argv[i + 4]) != 0)) {
            printf("FAIL: RX_VK_UB_SNAPSHOT=[%s], vendor 0x%04x: %s\n", the_value ? the_value : "(unset)",
                   (unsigned)f.vendor_id, got ? "snapshotted" : "bound in place");
            return 1;
        }
    }
    return 0;
}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--headers", type=Path, default=None)   # (the Vulkan headers device_policy.h needs; else the compiler's own)
    args = p.parse_args()
    src = (VK / "vk_draw.cpp").read_text(encoding="utf-8")

    ranges = block(src, "VkDescriptorBufferInfo uniform_range(const NvnState& s, const Stage& st, uint32_t index) {")
    code = "\n".join(line.split("//")[0] for line in ranges.splitlines())
    if "static const bool snapshot" not in code or "ub_snapshot_wanted()" not in code:
        raise SystemExit("FAIL: uniform_range no longer asks ub_snapshot_wanted whether to snapshot the uniforms")
    if "snapshot && !gpu_written ? BufferRef{} : gpu_buffer_bind(" not in code:
        raise SystemExit("FAIL: uniform_range binds a uniform buffer in place although the snapshot is on (and the GPU did "
                         "not write it earlier in the submission: tests/test_ub_snapshot_gpu_writes.py)")
    print("source: uniform_range copies the uniforms into the stream when ub_snapshot_wanted says so")

    decision = block(src, "bool ub_snapshot_wanted() {")
    with tempfile.TemporaryDirectory(prefix="ub-snapshot-") as tmp:
        tmp = Path(tmp)
        cpp, exe = tmp / "t.cpp", tmp / "t.exe"
        if "return dev.policy.ub_snapshot;" not in decision:
            raise SystemExit("FAIL: ub_snapshot_wanted no longer returns device_policy.h's ub_snapshot (a second rule?)")
        cpp.write_text(FIXTURE.replace("@@DECISION@@", decision), encoding="utf-8")
        # (-isystem: the renderer's headers are not this check's to warn about)
        headers = ["-isystem", str(VK)] + (["-isystem", str(args.headers)] if args.headers else [])
        r = subprocess.run([args.cxx, "-std=c++20", "-include", str(VK / "compat" / "hookshot_env.h"), "-Wall",
                            "-Wextra", "-Werror", *headers, str(cpp), "-o", str(exe)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stdout + r.stderr)
            raise SystemExit("FAIL: ub_snapshot_wanted did not build alone")
        argv = []
        for value, gpu, want in CASES:
            vendor, integrated, mirror = GPUS[gpu]
            argv += ["-unset" if value is None else value, hex(vendor), str(integrated), str(mirror), str(want)]
        r = subprocess.run([str(exe), *argv], capture_output=True, text=True, timeout=30)
        if r.returncode:
            print(r.stdout + r.stderr)
            raise SystemExit("FAIL: the uniform snapshot's default is wrong (on for every Intel GPU, mirrors or not, and "
                             "an integrated GPU without mirrors; off elsewhere; RX_VK_UB_SNAPSHOT by the switches' rule)")
    print("decision: %d cases: unset, on for Intel (discrete Arc included) and integrated GPUs without mirrors, off for the "
          "rest; RX_VK_UB_SNAPSHOT by the switches' rule" % len(CASES))
    print("PASS")


if __name__ == "__main__":
    main()
