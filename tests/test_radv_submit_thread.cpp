// host/hos_submit_thread.h: whether the process start sets MESA_VK_ENABLE_SUBMIT_THREAD=1 (an amdgpu card, the variable unset,
// RX_VK_RADV_SUBMIT_THREAD not off, 12 or more hardware threads or the switch =1) or leaves Mesa's variable alone, and the
// amdgpu probe against fake /sys/class/drm trees. With --real, this machine's /sys/class/drm (a check by hand).
#include "../host/hos_submit_thread.h"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

namespace fs = std::filesystem;

// <drm>/<card>/device/driver a link to <target> (a dangling one, as the probe only reads the link)
static void card(const fs::path& drm, const char* name, const char* target) {
    fs::create_directories(drm / name / "device");
    fs::create_symlink(target, drm / name / "device" / "driver");
}

static int decisions() {
    // an amdgpu card, nothing set: on from 12 hardware threads, off below
    CHECK("8 threads", hos_submit_thread_decide(1, nullptr, nullptr, 8) == HOS_SUBMIT_THREAD_FEW_THREADS);
    CHECK("11 threads", hos_submit_thread_decide(1, nullptr, nullptr, 11) == HOS_SUBMIT_THREAD_FEW_THREADS);
    CHECK("12 threads", hos_submit_thread_decide(1, nullptr, nullptr, 12) == HOS_SUBMIT_THREAD_ON);
    CHECK("16 threads", hos_submit_thread_decide(1, nullptr, nullptr, 16) == HOS_SUBMIT_THREAD_ON);
    CHECK("junk switch: the thread rule", hos_submit_thread_decide(1, nullptr, "2", 8) == HOS_SUBMIT_THREAD_FEW_THREADS &&
                                          hos_submit_thread_decide(1, nullptr, "2", 12) == HOS_SUBMIT_THREAD_ON);

    // the switch =1 forces it on whatever the thread count; =0 leaves it alone whatever the thread count
    CHECK("forced, 8", hos_submit_thread_decide(1, nullptr, "1", 8) == HOS_SUBMIT_THREAD_FORCED);
    CHECK("forced, 11", hos_submit_thread_decide(1, nullptr, "Yes", 11) == HOS_SUBMIT_THREAD_FORCED);
    CHECK("forced, 16", hos_submit_thread_decide(1, nullptr, "on", 16) == HOS_SUBMIT_THREAD_FORCED);
    CHECK("switch 0, 16", hos_submit_thread_decide(1, nullptr, "0", 16) == HOS_SUBMIT_THREAD_SWITCH_OFF);
    CHECK("switch OFF, 12", hos_submit_thread_decide(1, nullptr, "OFF", 12) == HOS_SUBMIT_THREAD_SWITCH_OFF);
    CHECK("switch empty, 12", hos_submit_thread_decide(1, nullptr, "", 12) == HOS_SUBMIT_THREAD_SWITCH_OFF);
    CHECK("switch 0, 8", hos_submit_thread_decide(1, nullptr, "false", 8) == HOS_SUBMIT_THREAD_SWITCH_OFF);

    // the user's own value, whatever it is, is kept, over the switch and the thread count
    CHECK("user 1, 8", hos_submit_thread_decide(1, "1", nullptr, 8) == HOS_SUBMIT_THREAD_USER_SET);
    CHECK("user 0, 16", hos_submit_thread_decide(1, "0", nullptr, 16) == HOS_SUBMIT_THREAD_USER_SET);
    CHECK("user empty", hos_submit_thread_decide(1, "", nullptr, 16) == HOS_SUBMIT_THREAD_USER_SET);
    CHECK("user 0, switch 1", hos_submit_thread_decide(1, "0", "1", 16) == HOS_SUBMIT_THREAD_USER_SET);
    CHECK("user 1, switch 0", hos_submit_thread_decide(1, "1", "0", 16) == HOS_SUBMIT_THREAD_USER_SET);

    // no amdgpu card: never touched, not even with the switch =1
    CHECK("no amdgpu", hos_submit_thread_decide(0, nullptr, nullptr, 16) == HOS_SUBMIT_THREAD_NO_AMDGPU);
    CHECK("no amdgpu, forced", hos_submit_thread_decide(0, nullptr, "1", 16) == HOS_SUBMIT_THREAD_NO_AMDGPU);
    CHECK("no amdgpu, user set", hos_submit_thread_decide(0, "1", nullptr, 16) == HOS_SUBMIT_THREAD_NO_AMDGPU);

    // a 1 a Hookshot set (its mark inherited with it) is not the user's; anything else is
    CHECK("ours", hos_submit_thread_user_value("1", "1") == nullptr);
    CHECK("user's, no mark", !std::strcmp(hos_submit_thread_user_value("1", nullptr), "1"));
    CHECK("user's 0 with a mark", !std::strcmp(hos_submit_thread_user_value("0", "1"), "0"));
    CHECK("unset", hos_submit_thread_user_value(nullptr, "1") == nullptr);

    CHECK("switch words", hos_submit_thread_switch(nullptr) == -1 && hos_submit_thread_switch("0") == 0 &&
                              hos_submit_thread_switch("") == 0 && hos_submit_thread_switch("No") == 0 &&
                              hos_submit_thread_switch("1") == 1 && hos_submit_thread_switch("TRUE") == 1 &&
                              hos_submit_thread_switch("00") == -1 && hos_submit_thread_switch("offf") == -1 &&
                              hos_submit_thread_switch("o") == -1);
    return 0;
}

static int probe(const fs::path& root) {
    CHECK("no folder", !hos_drm_has_amdgpu((root / "missing").c_str()));
    {
        const fs::path drm = root / "empty";
        fs::create_directories(drm);
        CHECK("no cards", !hos_drm_has_amdgpu(drm.c_str()));
    }
    {   // the kernel's layout (this machine's): class/drm/card1 a link into devices/, its device a link to the PCI device,
        // that one's driver a link to bus/pci/drivers/amdgpu; card1-DP-1 and renderD128 beside it
        const fs::path sys = root / "kernel";
        const fs::path pci = sys / "devices/pci0000:00/0000:0b:00.0";
        fs::create_directories(pci / "drm/card1/card1-DP-1");
        fs::create_directories(sys / "bus/pci/drivers/amdgpu");
        fs::create_directory_symlink("../../../bus/pci/drivers/amdgpu", pci / "driver");
        fs::create_directory_symlink("../../../0000:0b:00.0", pci / "drm/card1/device");
        fs::create_directories(sys / "class/drm");
        fs::create_directory_symlink("../../devices/pci0000:00/0000:0b:00.0/drm/card1", sys / "class/drm/card1");
        fs::create_directory_symlink("../../devices/pci0000:00/0000:0b:00.0/drm/card1/card1-DP-1", sys / "class/drm/card1-DP-1");
        fs::create_directory_symlink("../../devices/pci0000:00/0000:0b:00.0/drm/renderD128", sys / "class/drm/renderD128");
        CHECK("amdgpu, kernel layout", hos_drm_has_amdgpu((sys / "class/drm").c_str()));
    }
    {   // another card first (Intel, then the AMD card): found
        const fs::path drm = root / "two";
        card(drm, "card0", "../../../bus/pci/drivers/i915");
        card(drm, "card1", "../../../bus/pci/drivers/amdgpu");
        CHECK("i915 and amdgpu", hos_drm_has_amdgpu(drm.c_str()));
    }
    {   // NVIDIA and Intel only; a driver named like amdgpu but not it
        const fs::path drm = root / "other";
        card(drm, "card0", "../../../bus/pci/drivers/nvidia");
        card(drm, "card1", "../../../bus/pci/drivers/i915");
        card(drm, "card2", "../../../bus/pci/drivers/amdgpu_x");
        CHECK("no amdgpu among others", !hos_drm_has_amdgpu(drm.c_str()));
    }
    {   // only card<N>: a connector, a render node, "card" and "cardX" with an amdgpu driver are passed over
        const fs::path drm = root / "names";
        card(drm, "card1-DP-1", "../drivers/amdgpu");
        card(drm, "renderD128", "../drivers/amdgpu");
        card(drm, "card", "../drivers/amdgpu");
        card(drm, "cardX", "../drivers/amdgpu");
        card(drm, "card1a", "../drivers/amdgpu");
        CHECK("connectors and other names", !hos_drm_has_amdgpu(drm.c_str()));
        card(drm, "card12", "amdgpu");   // (a bare name, no folder)
        CHECK("card12 found", hos_drm_has_amdgpu(drm.c_str()));
    }
    {   // a driver that is a file and not a link, a card with no device, a card that is a plain file
        const fs::path drm = root / "odd";
        fs::create_directories(drm / "card0/device");
        std::ofstream(drm / "card0/device/driver") << "amdgpu\n";
        fs::create_directories(drm / "card1");
        std::ofstream(drm / "card2") << "x\n";
        CHECK("no link", !hos_drm_has_amdgpu(drm.c_str()));
    }
    return 0;
}

int main(int argc, char** argv) {
    if (argc >= 2 && !std::strcmp(argv[1], "--real")) {
        std::printf("amdgpu in /sys/class/drm: %s\n", hos_drm_has_amdgpu("/sys/class/drm") ? "yes" : "no");
        return 0;
    }
    if (argc < 2) return 2;
    if (const int r = decisions()) return r;
    return probe(argv[1]);
}
