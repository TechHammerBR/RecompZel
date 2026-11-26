/* (Hookshot, Linux) Mesa's submit thread (MESA_VK_ENABLE_SUBMIT_THREAD=1) on by default with an AMD card and a spare core,
   decided once at process start: host/hos_main.c's main(), after hookshot_env.txt is read and before any thread is made
   (glibc's setenv is not safe against a getenv on another thread), and kept for the whole process. Plain C, so
   tests/test_radv_submit_thread.py compiles it alone.
   Mesa's common Vulkan runtime reads the variable in vk_device_init (src/vulkan/runtime/vk_device.c), in each vkCreateDevice,
   for a device in the "assisted" timeline mode (drm syncobj timelines: RADV, ANV and the other vk_drm_syncobj drivers). Set:
   every queue of the device sends its submissions from a thread of its own (VK_QUEUE_SUBMIT_MODE_THREADED); unset: Mesa starts
   one only for a queue whose submission waits on work not yet sent (THREADED_ON_DEMAND); =0: never. The device is not picked
   yet at start, so the rule is an amdgpu card in /sys/class/drm: on a machine with an AMD card and another Mesa GPU (an Intel
   iGPU's ANV) the variable reaches that driver's queues too.
   Measured on an RX 9070 XT (Mesa 26.2.6, Ryzen 5 5500X3D: 12 hardware threads, Kokiri Forest, frame limit off, 6 interleaved
   rounds): 90.2 -> 100.3 fps (+10.1, se 1.8). The submit ioctl leaves the replay's thread (its "queue submit" 1.16 -> 0.01 ms
   a frame); Mesa's thread takes 21-27% of a core, hence on only from 12 hardware threads.
   RX_VK_RADV_SUBMIT_THREAD=0 (false, off, no, empty): left alone; =1 (true, on, yes): on whatever the thread count. A
   MESA_VK_ENABLE_SUBMIT_THREAD the user set (any value) is kept. */
#pragma once

#include <dirent.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define HOS_SUBMIT_THREAD_MIN_THREADS 12u
/* Set beside MESA_VK_ENABLE_SUBMIT_THREAD=1 when Hookshot set it: a process started from this one (the builder's update,
   which may start the game again) inherits both, and its own start then decides again instead of taking the value as the
   user's. (The menu's restart re-execs with /proc/self/environ, the environment the process started with, which a setenv
   does not change: it has neither.) */
#define HOS_SUBMIT_THREAD_MARK "HOS_MESA_SUBMIT_THREAD_SET"

typedef enum {
    HOS_SUBMIT_THREAD_ON,          /* amdgpu, the variable unset, the switch not off, 12 or more threads: set to 1 */
    HOS_SUBMIT_THREAD_FORCED,      /* amdgpu, the variable unset, RX_VK_RADV_SUBMIT_THREAD=1: set to 1 */
    HOS_SUBMIT_THREAD_FEW_THREADS, /* fewer than 12 threads: left alone */
    HOS_SUBMIT_THREAD_SWITCH_OFF,  /* RX_VK_RADV_SUBMIT_THREAD=0: left alone */
    HOS_SUBMIT_THREAD_USER_SET,    /* the user set MESA_VK_ENABLE_SUBMIT_THREAD (any value, empty too): kept */
    HOS_SUBMIT_THREAD_NO_AMDGPU,   /* no amdgpu card: left alone */
} HosSubmitThread;

/* The words of a switch, any case: 0 for 0/false/off/no/empty, 1 for 1/true/on/yes, -1 unset or anything else */
static inline int hos_submit_thread_switch(const char *v) {
    static const char *const words[] = {"", "0", "false", "off", "no", "1", "true", "on", "yes"};
    if (!v) return -1;
    for (int i = 0; i < 9; i++) {
        const char *a = v, *b = words[i];
        while (*a && *b && (*a >= 'A' && *a <= 'Z' ? *a + 32 : *a) == *b) a++, b++;
        if (!*a && !*b) return i >= 5;
    }
    return -1;
}

/* The user's MESA_VK_ENABLE_SUBMIT_THREAD: NULL when unset, or when it is the 1 a Hookshot this process was started from set
   (its mark inherited with it) */
static inline const char *hos_submit_thread_user_value(const char *mesa_value, const char *mark) {
    return mesa_value && mark && !strcmp(mesa_value, "1") && !strcmp(mark, "1") ? NULL : mesa_value;
}

/* amdgpu: an amdgpu card in /sys/class/drm. mesa_value: the user's MESA_VK_ENABLE_SUBMIT_THREAD (hos_submit_thread_user_value).
   switch_value: getenv("RX_VK_RADV_SUBMIT_THREAD"). threads: the hardware threads online */
static inline HosSubmitThread hos_submit_thread_decide(int amdgpu, const char *mesa_value, const char *switch_value,
                                                       unsigned threads) {
    if (!amdgpu) return HOS_SUBMIT_THREAD_NO_AMDGPU;
    if (mesa_value) return HOS_SUBMIT_THREAD_USER_SET;
    const int sw = hos_submit_thread_switch(switch_value);
    if (sw == 0) return HOS_SUBMIT_THREAD_SWITCH_OFF;
    if (sw == 1) return HOS_SUBMIT_THREAD_FORCED;
    return threads >= HOS_SUBMIT_THREAD_MIN_THREADS ? HOS_SUBMIT_THREAD_ON : HOS_SUBMIT_THREAD_FEW_THREADS;
}

/* Whether some <drm>/card<N>/device/driver (drm: "/sys/class/drm") links to a folder named amdgpu. Only card<N>: the
   connectors (card1-DP-1) and render nodes (renderD128) are passed over; an entry that is not a link, or has no device,
   is too. No root needed */
static inline int hos_drm_has_amdgpu(const char *drm) {
    DIR *d = opendir(drm);
    if (!d) return 0;
    int found = 0;
    for (struct dirent *e; !found && (e = readdir(d));) {
        const char *n = e->d_name;
        if (strncmp(n, "card", 4) || !n[4]) continue;
        const char *p = n + 4;
        while (*p >= '0' && *p <= '9') p++;
        if (*p) continue;
        char path[512], target[512];
        snprintf(path, sizeof path, "%s/%s/device/driver", drm, n);
        const ssize_t len = readlink(path, target, sizeof target - 1);
        if (len <= 0) continue;
        target[len] = 0;
        const char *base = strrchr(target, '/');
        found = !strcmp(base ? base + 1 : target, "amdgpu");
    }
    closedir(d);
    return found;
}

