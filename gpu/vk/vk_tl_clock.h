// (stream R2, RX_VK_TL / RX_VK_TL_PROBE) The host time domain the timeline's GPU side is calibrated against
// (vk_replay.cpp tl_gpu_dump): the one QueryPerformanceCounter reads. On Windows that is VK_TIME_DOMAIN_QUERY_PERFORMANCE_COUNTER_EXT;
// on Linux the shim's QueryPerformanceCounter is CLOCK_MONOTONIC in ns at a frequency of 1e9 (host/posix/windows.h), which is
// VK_TIME_DOMAIN_CLOCK_MONOTONIC_EXT (the QPC domain is Windows-only: Mesa's
// vkGetCalibratedTimestampsEXT fails the whole call for it, and tl_gpu_dump then wrote no GPU lines). The includer brings the
// Vulkan types (vk_loader.h).
#pragma once

#include <cstdint>

namespace mkwvk {

inline VkTimeDomainEXT tl_host_time_domain() {
#ifdef _WIN32
    return VK_TIME_DOMAIN_QUERY_PERFORMANCE_COUNTER_EXT;
#else
    return VK_TIME_DOMAIN_CLOCK_MONOTONIC_EXT;
#endif
}

/// whether the device's calibrateable domains (vkGetPhysicalDeviceCalibrateableTimeDomainsEXT) hold both the device's own and
/// the host one tl_gpu_dump asks for: a domain not listed may not be passed to vkGetCalibratedTimestampsEXT
inline bool tl_time_domains_usable(const VkTimeDomainEXT* domains, uint32_t n) {
    bool device = false, host = false;
    for (uint32_t i = 0; i < n; i++) {
        device = device || domains[i] == VK_TIME_DOMAIN_DEVICE_EXT;
        host = host || domains[i] == tl_host_time_domain();
    }
    return device && host;
}

inline const char* tl_time_domain_name(VkTimeDomainEXT d) {
    switch (d) {
    case VK_TIME_DOMAIN_DEVICE_EXT: return "DEVICE";
    case VK_TIME_DOMAIN_CLOCK_MONOTONIC_EXT: return "CLOCK_MONOTONIC";
    case VK_TIME_DOMAIN_CLOCK_MONOTONIC_RAW_EXT: return "CLOCK_MONOTONIC_RAW";
    case VK_TIME_DOMAIN_QUERY_PERFORMANCE_COUNTER_EXT: return "QUERY_PERFORMANCE_COUNTER";
    default: return "?";
    }
}

} // namespace mkwvk
