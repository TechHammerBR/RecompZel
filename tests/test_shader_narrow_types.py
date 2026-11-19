"""16-bit floats and 8/16-bit integers in translated shaders only where the device has them (gpu/vk/vk_shader.cpp).

A GTX 970 (no shaderFloat16) was given modules that declare Float16, invalid there (VUID-VkShaderModuleCreateInfo-pCode-08740),
and showed a full screen of coloured noise (2026-11-17). float16_shaders() now follows the device's shaderFloat16 (RX_VK_NO_F16=1
and RX_VK_F16=1 force it), make_profile takes shaderInt8 / shaderInt16 from the device, and the program cache's stamp gets a word
only on a device without them. The networks' left-out path and the upscale stand-in follow float16_shaders(). float16_shaders is
compiled here with stubs; the rest are source checks. No game or GPU required.

python -I -B tests/test_shader_narrow_types.py [--cxx clang++]
"""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path

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
#include <cstdio>
#include <cstdlib>
#include <cstring>
using VkBool32 = unsigned;
constexpr VkBool32 VK_FALSE = 0;
struct { struct { VkBool32 shaderFloat16; } vk12; } dev;
void logf(const char*, ...) {}
@FN@
int main(int argc, char** argv) {
    dev.vk12.shaderFloat16 = (VkBool32)atoi(argv[1]);
    std::printf("%d\n", float16_shaders() ? 1 : 0);
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default=os.environ.get("CXX", "clang++"))
    a = p.parse_args()
    shader = (ROOT / "gpu/vk/vk_shader.cpp").read_text(encoding="utf-8-sig")
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8-sig")
    prof = block(shader, "Shader::Profile make_profile()")
    for need in ("p.support_int8 = dev.vk12.shaderInt8 != VK_FALSE;", "p.support_int16 = dev.features.shaderInt16 != VK_FALSE;"):
        assert need in prof, "make_profile does not take " + need
    assert "p.support_int8 = p.support_int16" not in prof, "make_profile still says every device has 8/16-bit integers"
    assert "h.support_float16 = float16_shaders();" in shader, "host_info does not follow float16_shaders()"
    stamp = block(shader, "uint64_t disk_stamp()")
    assert "if (!dev.vk12.shaderInt8 || !dev.features.shaderInt16)" in stamp and "if (!dev.vk12.shaderFloat16)" in stamp, \
        "the program cache's stamp does not keep the narrow-type programs apart"
    assert '|| !float16_shaders())\n                    throw NetworkLeftOut();' in shader, "the networks are not left out without f16"
    assert 'getenv("RX_VK_NO_F16")' not in draw, "vk_draw.cpp still reads RX_VK_NO_F16 itself"
    assert "|| !float16_shaders()) && in.d.format == NVN_FORMAT_RGB9E5F" in draw, "the typed RGB9E5 stand-in skips left-out networks"
    assert "(out_area == in_area && !gameplay_network(key))" in draw, "the same-size gameplay pass is still skipped"
    fn = block(shader, "bool float16_shaders()")
    with tempfile.TemporaryDirectory(prefix="f16-") as tmp:
        cpp = Path(tmp) / "f.cpp"
        exe = Path(tmp) / ("f.exe" if os.name == "nt" else "f")
        cpp.write_text(FIXTURE.replace("@FN@", fn), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-D_CRT_SECURE_NO_WARNINGS", str(cpp), "-o", str(exe)], check=True)
        base = {k: v for k, v in os.environ.items() if k not in ("RX_VK_NO_F16", "RX_VK_F16")}
        cases = [("has", "1", {}, "1"), ("lacks", "0", {}, "0"), ("NO_F16 on a device with it", "1", {"RX_VK_NO_F16": "1"}, "0"),
                 ("F16 forced on a device without it", "0", {"RX_VK_F16": "1"}, "1"), ("NO_F16=0 is not set", "0", {"RX_VK_NO_F16": "0"}, "0")]
        for name, has, env, want in cases:
            out = subprocess.run([str(exe), has], env={**base, **env}, check=True, capture_output=True, text=True).stdout.strip()
            assert out == want, "%s: %s, wanted %s" % (name, out, want)
    print("PASS 16-bit floats and 8/16-bit integers follow the device")


if __name__ == "__main__":
    main()
