// (recompzel) NVIDIA Streamline, the way to NVIDIA DLSS Frame Generation (DLSS-G). Written from NVIDIA's public programming
// guides (third_party/streamline, MIT headers); nothing of another project's code is in it.
//
// Streamline's DLLs are never linked and never in this repository: sl.interposer.dll and its plugins sit in a `streamline`
// folder beside the game (or in the game folder itself) and are loaded at run time only when asked for, with
// RX_VK_DLSSG=1. Without that the game runs exactly as before; this file is then never touched.
//
// What it does today (phase 1): loads the interposer, starts Streamline with DLSS-G, Reflex and PCL, and routes the Vulkan
// entry points through the interposer's, so the instance, the device and the swapchain are the ones Streamline needs, and
// says in the log whether this GPU and driver run DLSS-G and how many frames it can make between two rendered ones. It
// makes no frame yet.
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

/// Before the device is destroyed.
void shutdown();

} // namespace mkwvk::slfg
