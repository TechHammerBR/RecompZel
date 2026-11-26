"""The overlays (Dear ImGui) load their Vulkan functions from vkGetInstanceProcAddr, not vkGetDeviceProcAddr first.

ImGui's Vulkan backend loads instance-level functions too (vkGetPhysicalDeviceMemoryProperties, which it calls for every
buffer it makes, and the surface queries). vkGetDeviceProcAddr returns NULL for those only since Vulkan 1.2.193 and was
undefined before: an older loader or driver may hand back a function that takes the driver's own physical device where
ImGui passes the loader's. The validation layer warned for 8 names (WARNING-vkGetDeviceProcAddr-device).
python -I -B tests/test_ui_function_loader.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = (ROOT / "gpu" / "vk" / "vk_imgui.cpp").read_text(encoding="utf-8")
    start = source.index("PFN_vkVoidFunction load(const char* name, void*) {")
    body = source[start:source.index("\n}\n", start)]
    if "ImGui_ImplVulkan_LoadFunctions(VK_API_VERSION_1_3, load)" not in source:
        raise SystemExit("ImGui's functions are loaded another way now: update this test")
    if "vkGetDeviceProcAddr" in body:
        raise SystemExit("the overlays' loader asks vkGetDeviceProcAddr: undefined for ImGui's instance-level functions")
    if "instance_proc_addr()(dev.instance, name)" not in body:
        raise SystemExit("the overlays' loader does not ask vkGetInstanceProcAddr with the instance")
    print("PASS: the overlays' Vulkan functions come from vkGetInstanceProcAddr")


if __name__ == "__main__":
    main()
