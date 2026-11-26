"""The Radeon 860M decodes ASTC on the CPU by default on Windows (gpu/vk/device_policy.h's astc_on_cpu rule; no game or GPU).

PCI 1002:1114 is the 860M in #1040. The same Kokiri Forest arrays lose the device on the GPU decoder. The desktop
iGPUs 1002:164E and 1002:13C0 already default to the CPU. Another AMD id, and the same id on another vendor, stay on the
GPU, and off Windows the default stays the GPU. The rule's one line is cut out of device_policy.h and run against the
facts it reads; the switch over it (RX_VK_ASTC_CPU=0 and =1, device_policy_env) is tests/test_device_policy.py's.

python -I -B tests/test_astc_cpu_860m.py [--cxx g++]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
AMD = 0x1002
NVIDIA = 0x10DE
MARKER = "    p.astc_on_cpu = "


def rule():
    policy = (ROOT / "gpu/vk/device_policy.h").read_text(encoding="utf-8")
    if policy.count(MARKER) != 1:
        raise SystemExit("gpu/vk/device_policy.h: %r appears %d times, not once" % (MARKER.strip(), policy.count(MARKER)))
    at = policy.index(MARKER)
    return policy[at:policy.index(";", at) + 1]


SOURCE = """
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

struct Facts {
    uint32_t vendor_id = 0, device_id = 0;
    bool windows = false;
    bool amd() const { return vendor_id == 0x1002; }
};
struct Policy { bool astc_on_cpu = false; };

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    Facts f;
    f.windows = atoi(argv[1]) != 0;
    f.vendor_id = (uint32_t)strtoul(argv[2], 0, 0);
    f.device_id = (uint32_t)strtoul(argv[3], 0, 0);
    Policy p;
%s
    printf("%%d\\n", p.astc_on_cpu ? 1 : 0);
    return 0;
}
"""

CASES = [
    (1, AMD, 0x1114, 1, "860M (PCI 1002:1114) still decodes ASTC on the GPU by default"),
    (1, AMD, 0x164E, 1, "Ryzen 7000 desktop iGPU"),
    (1, AMD, 0x13C0, 1, "Ryzen 9000 desktop iGPU"),
    (1, AMD, 0x164F, 0, "another AMD id stays on the GPU decoder"),
    (1, NVIDIA, 0x1114, 0, "the 860M's id on another vendor"),
    (0, AMD, 0x1114, 0, "off Windows the default stays the GPU"),
]


def main():
    cxx = "g++"
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--cxx":
        cxx = args[1]
    with tempfile.TemporaryDirectory() as d:
        src, exe = Path(d) / "astc.cpp", Path(d) / "astc"
        src.write_text(SOURCE % rule(), encoding="utf-8")
        r = subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-o", str(exe), str(src)],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(r.stderr or r.stdout)
        for windows, vendor, device, want, why in CASES:
            r = subprocess.run([str(exe), str(windows), hex(vendor), hex(device)], capture_output=True, text=True)
            if r.returncode:
                raise SystemExit(r.stderr or "the probe exited %d" % r.returncode)
            if r.stdout.strip() != str(want):
                raise SystemExit("%s: windows %d vendor %#x device %#x got %s, want %d" % (
                    why, windows, vendor, device, r.stdout.strip(), want))
    print("ok")


if __name__ == "__main__":
    main()
