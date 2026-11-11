// (recompzel) NVIDIA Streamline, the way to NVIDIA DLSS Frame Generation (DLSS-G). Written from NVIDIA's public programming
// guides (third_party/streamline, MIT headers); nothing of another project's code is in it.
//
// Streamline's DLLs are never linked and never in this repository: sl.interposer.dll and its plugins sit in a `streamline`
// folder beside the game (or in the game folder itself) and are loaded at run time only when asked for, with
// RX_VK_DLSSG=1. Without that the game runs exactly as before; this file is then never touched.
//
// What it does: loads the interposer, starts Streamline with DLSS-G, Reflex and PCL, and routes the Vulkan entry points
// through the interposer's, so the instance, the device and the swapchain are the ones Streamline needs, and says in the log
// whether this GPU and driver run DLSS-G and how many frames it can make between two rendered ones (phase 1).
//
// Phase 2: while DLSS-G runs (active()), Streamline's own Reflex and PCL markers replace vk_reflex.cpp's (those functions
// forward here), each frame has a Streamline frame token, the scene's depth and motion (the chain DLSS's upscaler uses,
// vk_temporal.cpp) are tagged and the camera's constants set, and DLSS-G is switched on for each frame that has them. The
// renderer's own frame interpolation (vk_framegen.cpp) is off then: Streamline inserts the frame at the present.
#pragma once

#include "vk_internal.h"

namespace mkwvk::slfg {

/// RX_VK_DLSSG=1 (read once): Streamline is to be used. Windows only.
[[nodiscard]] bool wanted();

/// Before the instance exists: loads sl.interposer.dll and starts Streamline. True when the interposer's entry points are
/// there to be used, false (and one line in the log saying why) when not, which leaves everything as it was.
[[nodiscard]] bool early();

/// The interposer's vkGetInstanceProcAddr when early() succeeded, else null. Every instance and device function fetched
/// through it is the loader's own except the few Streamline intercepts (vkCreateInstance, vkCreateDevice, the swapchain
/// and present calls), which is how the whole renderer ends up on Streamline's swapchain without another change.
[[nodiscard]] PFN_vkGetInstanceProcAddr instance_proc();

/// After the device exists: asks Streamline whether DLSS-G is loaded and supported on this GPU, and how many frames it can
/// generate; logs the answer.
void device_ready(VkPhysicalDevice physical);

/// Whether DLSS-G is loaded and supported here (after device_ready).
[[nodiscard]] bool available();

/// DLSS-G is to run: Streamline is up, the GPU supports it and its functions were all found (after device_ready). While it is
/// true vk_reflex.cpp leaves Reflex to Streamline and vk_framegen.cpp makes no frames of its own.
[[nodiscard]] bool active();

/// What one frame's upscale was given (vk_temporal.cpp, after the engine's evaluation): the images stay GENERAL until the
/// frame is presented. Depth is R32F in [0, 1], not reversed; motion RG16F in render pixels towards the frame before, the
/// jitter taken off. Tagged for this frame's token, with the camera's constants, and DLSS-G is on for the frame.
struct FrameInputs {
    VkImage depth = VK_NULL_HANDLE, motion = VK_NULL_HANDLE;
    VkImageView depth_view = VK_NULL_HANDLE, motion_view = VK_NULL_HANDLE;
    VkFormat depth_format = VK_FORMAT_UNDEFINED, motion_format = VK_FORMAT_UNDEFINED;
    uint32_t depth_w = 0, depth_h = 0, motion_w = 0, motion_h = 0;   ///< the images' own sizes
    uint32_t render_w = 0, render_h = 0;                              ///< the frame's part, at the top left
    float jitter[2]{};                                                ///< render pixels, x right and y down
    float near_z = 0.1f, far_z = 1000.0f, fov_y = 1.0f;
    bool reset = false;
};
void frame_inputs(const FrameInputs& in);

/// The frame's markers, called where vk_reflex.cpp's were (the game's present): the simulation's end and the submission's
/// start (and DLSS-G's options for the frame), the submission's end, the present's start and end, and, after the present,
/// the next frame's start: a new token, Reflex's sleep and the simulation's start.
void present_begins();
void submit_ends();
void present_starts();
void present_ends();
void next_frame();

/// Before the device is destroyed.
void shutdown();

} // namespace mkwvk::slfg
