// (recompzel) AMD FSR Frame Generation 4 ("Redstone", FSR SDK 2.4), the Frame generation method row's AMD FSR 4: the frame
// between two of the game's made by AMD's machine-learning interpolation, from the same depth and motion FSR 4 upscales with
// (vk_temporal.cpp hands them over, fsr3_inputs::offer). AMD's library generates the frame alone
// (FFX_FRAMEGENERATION_FLAG_NO_SWAPCHAIN_CONTEXT_NOTIFY): the renderer's own pacing shows it, as it shows FSR 3.1's.
// The library: amd_fidelityfx_loader_vk.dll with amd_fidelityfx_framegeneration_vk.dll beside it, in RX_VK_FSR4FG_DIR or the
// game folder's fsr4fg\ (a folder of its own: FSR 4's own amd_fidelityfx_upscaler_vk.dll is another library). AMD says it
// needs an RX 9000 GPU and Windows 11: a context it will not make is told once, and the renderer's own interpolation runs.
#pragma once

#include <cstdint>

#include "vk_internal.h"

namespace mkwvk {
namespace fsr4fg {

/// AMD's frame generation library is there and loaded (asked once): the menu offers the method
bool available();
/// The Frame generation method row says AMD FSR 4 and nothing has failed: frames go to generate()
bool wanted();

struct Inputs {
    VkImage color_image = VK_NULL_HANDLE;    ///< the game's frame, display size, RGBA8 UNORM (sRGB-encoded), GENERAL
    VkImage output_image = VK_NULL_HANDLE;   ///< the made frame, display size, RGBA8 UNORM, storage, GENERAL
    uint32_t width = 0, height = 0;
    VkImage depth_image = VK_NULL_HANDLE;    ///< R32F, render size, inverted (1 at the near plane), GENERAL
    VkImage motion_image = VK_NULL_HANDLE;   ///< RG16F, render size, render pixels toward the frame before, GENERAL
    uint32_t render_w = 0, render_h = 0;
    float jitter[2]{};
    float near_z = 0.0f, far_z = 0.0f, fov_y = 0.0f;
    float frame_ms = 16.667f;
    bool reset = false;
};
/// The made frame into in.output_image: false when it was not made (the caller's own interpolation then)
bool generate(VkCommandBuffer cmd, const Inputs& in);

}  // namespace fsr4fg
}  // namespace mkwvk
