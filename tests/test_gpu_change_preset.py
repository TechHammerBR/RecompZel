"""A different GPU at the start gets the settings for its memory again (vk_menu.cpp menu_first_start_for_gpu).

A GTX 970 started with an options file made on an RTX card (Custom, 7 made frames, the Compute mesh row) and kept all of it:
5.5 GB of VRAM used of 2.9, 3 fps. The options now remember their card (gpu_card=); another card at the start resets the rows a
preset sets and applies the preset for its memory. The same card, or a file from before gpu_card= on a large card, is left alone.

python -I -B tests/test_gpu_change_preset.py [--cxx clang++] [--headers <Vulkan headers>]
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

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
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vulkan/vulkan.h>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL %s:%d %s\n", name, __LINE__, #x); std::exit(1); } } while (0)
struct Options {
    int resolution = 0, upscale = 0, sharpness = 0, handheld = 0, pace = 0, preset = 0, budget = 0, vram_mb = 0, mirror_mb = 0;
    int mesh_mode = 0, framegen = 0;
};
Options opts;
bool first_start;
std::string gpu_card_saved, gpu_card_now;
int saves;
void save() { saves++; }
void restart_init() {}
void logf(const char*, ...) {}
const char* tx_preset(int) { return "p"; }
void sync_preset_budgets(int p) { opts.vram_mb = p == 1 ? 2200 : p == 2 ? 3600 : 0; }
void apply_preset(int p) {
    if (p == 1) opts.resolution = 4, opts.upscale = 2, opts.sharpness = 30, opts.pace = 1, opts.handheld = 1;
    if (p == 2) opts.resolution = 2, opts.upscale = 2, opts.sharpness = 30, opts.pace = 1, opts.handheld = 1;
    opts.budget = p;
}
@FN@
const char* name;
void run(uint32_t device, uint64_t mb, VkPhysicalDeviceType type = VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
    VkPhysicalDeviceProperties p{};
    p.vendorID = 0x10de, p.deviceID = device, p.deviceType = type;
    VkPhysicalDeviceMemoryProperties m{};
    m.memoryHeapCount = 1;
    m.memoryHeaps[0].flags = VK_MEMORY_HEAP_DEVICE_LOCAL_BIT;
    m.memoryHeaps[0].size = mb << 20;
    saves = 0;
    menu_first_start_for_gpu(p, m);
}
Options rtx() {   // (the options of an RTX player: Custom, 7 made frames, the Compute mesh row, full size)
    Options o;
    o.resolution = 1, o.upscale = 1, o.sharpness = 50, o.framegen = 8, o.mesh_mode = 2;
    return o;
}
int main(int argc, char** argv) {
    const int c = std::atoi(argv[1]);
    if (c == 0) {
        name = "first start on a 4 GB card: Minimum";
        first_start = true; run(0x13c2, 4096);
        CHECK(opts.preset == 1 && opts.budget == 1 && opts.resolution == 4 && opts.handheld == 0 && opts.upscale == 0);
        CHECK(gpu_card_saved == "10de:13c2:4096" && saves == 1);
    } else if (c == 1) {
        name = "the same card: left alone";
        opts = rtx(); gpu_card_saved = "10de:2782:12282"; run(0x2782, 12282);
        CHECK(opts.framegen == 8 && opts.mesh_mode == 2 && opts.resolution == 1 && saves == 0);
    } else if (c == 2) {
        name = "an RTX card's options on a GTX 970: Minimum, no made frames, Automatic mesh";
        opts = rtx(); gpu_card_saved = "10de:2782:12282"; run(0x13c2, 4096);
        CHECK(opts.preset == 1 && opts.resolution == 4 && opts.framegen == 0 && opts.mesh_mode == 0 && opts.vram_mb == 2200);
        CHECK(gpu_card_saved == "10de:13c2:4096" && saves == 1);
    } else if (c == 3) {
        name = "a GTX 970's options on an RTX 3080 Ti: the defaults back, made frames kept";
        opts = Options{}; opts.preset = opts.budget = 1; opts.resolution = 4; opts.handheld = 1; opts.mesh_mode = 2; opts.framegen = 2;
        gpu_card_saved = "10de:13c2:4096"; run(0x2208, 12288);
        CHECK(opts.preset == 0 && opts.budget == 0 && opts.resolution == 0 && opts.handheld == 0 && opts.mesh_mode == 0);
        CHECK(opts.framegen == 2 && opts.vram_mb == 0 && gpu_card_saved == "10de:2208:12288" && saves == 1);
    } else if (c == 4) {
        name = "a file from before gpu_card= on a 4 GB card: changed, once";
        opts = rtx(); gpu_card_saved.clear(); run(0x13c2, 4096);
        CHECK(opts.preset == 1 && opts.framegen == 0 && gpu_card_saved == "10de:13c2:4096");
    } else if (c == 5) {
        name = "a file from before gpu_card= on a large card: only the card recorded";
        opts = rtx(); gpu_card_saved.clear(); run(0x2782, 12282);
        CHECK(opts.framegen == 8 && opts.mesh_mode == 2 && opts.resolution == 1 && gpu_card_saved == "10de:2782:12282" && saves == 1);
    } else if (c == 6) {
        name = "RX_VK_AUTO_PRESET_ON_CHANGE=0: a changed card keeps the options";
        opts = rtx(); gpu_card_saved = "10de:2782:12282"; run(0x13c2, 4096);
        CHECK(opts.framegen == 8 && opts.mesh_mode == 2 && gpu_card_saved == "10de:13c2:4096");
    } else if (c == 7) {
        name = "a 6 GB card after a 12 GB one: Low";
        opts = rtx(); gpu_card_saved = "10de:2782:12282"; run(0x2520, 6144);
        CHECK(opts.preset == 2 && opts.resolution == 2 && opts.framegen == 8 && opts.mesh_mode == 0);
    }
    std::printf("PASS %s\n", name);
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    p.add_argument("--headers", default=os.environ.get("HOOKSHOT_VULKAN_HEADERS"))
    a = p.parse_args()
    source = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8-sig")
    fn = block(source, "void menu_first_start_for_gpu(")
    assert 'fprintf(f, "gpu_card=%s\\n"' in source, "save() does not write gpu_card="
    assert '!strcmp(line, "gpu_card")' in source, "menu_init does not read gpu_card="
    with tempfile.TemporaryDirectory(prefix="gpu-change-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / ("fixture.exe" if os.name == "nt" else "fixture")
        cpp.write_text(FIXTURE.replace("@FN@", fn), encoding="utf-8")
        cmd = [a.cxx, "-std=c++20", "-O1", "-D_CRT_SECURE_NO_WARNINGS"]
        if a.headers:
            cmd += ["-I", a.headers]
        subprocess.run(cmd + [str(cpp), "-o", str(exe)], check=True)
        for case in range(8):
            env = {k: v for k, v in os.environ.items() if not k.startswith("RX_VK_")}
            if case == 6:
                env["RX_VK_AUTO_PRESET_ON_CHANGE"] = "0"
            subprocess.run([str(exe), str(case)], env=env, check=True)
    print("PASS 8 GPU-change cases")


if __name__ == "__main__":
    main()
