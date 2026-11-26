// The game exe's lowest mapped address, which RX_VK_RB_PROF's call sites (vk_replay.cpp RbScope) are offsets from, as the
// crash offsets are (host/posix/win32_posix.c GetModuleHandleExA: dladdr's dli_fbase). Windows: the exe's HMODULE.
// Linux: GetModuleHandleA(NULL) is dlopen(NULL)'s handle there (for GetProcAddress), not an address, so the main program's
// first PT_LOAD segment from dl_iterate_phdr (the main program is the first object it visits). For a PIE exe (lld puts its
// first segment at 0) an offset is the address in hookshot.map. Pure header: tests/test_exe_base.py checks it.
#pragma once

#include <cstdint>
#ifdef _WIN32
#include <windows.h>
#else
#include <link.h>
#endif

namespace mkwvk {

inline uintptr_t exe_base() {
#ifdef _WIN32
    return (uintptr_t)GetModuleHandleA(nullptr);
#else
    uintptr_t base = 0;
    dl_iterate_phdr([](dl_phdr_info* info, size_t, void* out) -> int {
        uintptr_t lo = UINTPTR_MAX;
        for (int i = 0; i < info->dlpi_phnum; i++)
            if (info->dlpi_phdr[i].p_type == PT_LOAD && info->dlpi_phdr[i].p_vaddr < lo) lo = info->dlpi_phdr[i].p_vaddr;
        if (lo != UINTPTR_MAX) *(uintptr_t*)out = info->dlpi_addr + (lo & ~(uintptr_t)0xfff);
        return 1;   // (the main program only)
    }, &base);
    return base;
#endif
}

}  // namespace mkwvk
