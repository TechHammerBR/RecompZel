// (recompzel) NVIDIA Streamline: loading, starting and asking what the GPU can do (vk_streamline.h).
#include "vk_streamline.h"

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "vk_internal.h"

#ifdef _WIN32
#include <windows.h>

#include <filesystem>
#include <string>

// NVIDIA's public headers (third_party/streamline/include). Only plain structs and function-pointer types cross to the DLLs:
// the one type with a virtual member, sl::FrameToken, is only ever held by pointer.
#include <sl.h>
#include <sl_consts.h>
#include <sl_dlss_g.h>
#include <sl_pcl.h>
#include <sl_reflex.h>
#endif

namespace mkwvk::slfg {

#ifndef _WIN32

bool wanted() { return false; }
bool early() { return false; }
PFN_vkGetInstanceProcAddr instance_proc() { return nullptr; }
void device_ready(VkPhysicalDevice) {}
bool available() { return false; }
void shutdown() {}

#else

namespace fs = std::filesystem;

namespace {

struct State {
    HMODULE module = nullptr;
    PFN_vkGetInstanceProcAddr gipa = nullptr;
    PFun_slInit* init = nullptr;
    PFun_slShutdown* shut = nullptr;
    PFun_slIsFeatureLoaded* loaded = nullptr;
    PFun_slIsFeatureSupported* supported = nullptr;
    PFun_slGetFeatureFunction* feature_fn = nullptr;
    PFun_slDLSSGGetState* dlssg_state = nullptr;
    int early_result = -1;   // -1 not tried, 0 failed, 1 up
    int wanted = -1;
    bool available = false;
    bool started = false;
};
State S;

/// The game folder, from GetModuleFileNameW (a folder with characters outside the ANSI code page is still the right one)
fs::path exe_dir() {
    std::wstring exe(32768, L'\0');
    const DWORD n = GetModuleFileNameW(nullptr, exe.data(), (DWORD)exe.size());
    if (!n || n >= exe.size()) return {};
    exe.resize(n);
    return fs::path(exe).parent_path();
}

std::string utf8(const fs::path& p) {
    const std::wstring& w = p.native();
    const int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n > 0 ? n : 0, '\0');
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), s.data(), n, nullptr, nullptr);
    return s;
}

/// Streamline's own messages: warnings and errors reach the game's log, the chatter does not (the first 200 only)
void sl_message(sl::LogType type, const char* msg) {
    if (type == sl::LogType::eInfo) return;
    static int n = 0;
    if (n++ < 200) logf("streamline: %s: %s", type == sl::LogType::eError ? "error" : "warning", msg);
}

template <class T>
T* symbol(const char* name) {
    return reinterpret_cast<T*>(GetProcAddress(S.module, name));
}

}  // namespace

bool wanted() {
    if (S.wanted < 0) {
        const char* e = getenv("RX_VK_DLSSG");
        S.wanted = e && e[0] == '1';
    }
    return S.wanted == 1;
}

bool early() {
    if (!wanted()) return false;
    if (S.early_result >= 0) return S.early_result == 1;
    S.early_result = 0;

    // sl.interposer.dll: a `streamline` folder beside the game first, then the game folder itself
    const fs::path game = exe_dir();
    fs::path dir;
    for (const fs::path& d : {game / L"streamline", game}) {
        if (GetFileAttributesW((d / L"sl.interposer.dll").c_str()) != INVALID_FILE_ATTRIBUTES) {
            dir = d;
            break;
        }
    }
    if (dir.empty()) {
        logf("streamline: sl.interposer.dll is not in %s (or its streamline folder): DLSS Frame Generation off",
             utf8(game).c_str());
        return false;
    }
    // (altered search path: the interposer's own dependencies are looked for in its folder first)
    S.module = LoadLibraryExW((dir / L"sl.interposer.dll").c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!S.module) {
        logf("streamline: sl.interposer.dll did not load (error %lu): DLSS Frame Generation off", GetLastError());
        return false;
    }
    S.init = symbol<PFun_slInit>("slInit");
    S.shut = symbol<PFun_slShutdown>("slShutdown");
    S.loaded = symbol<PFun_slIsFeatureLoaded>("slIsFeatureLoaded");
    S.supported = symbol<PFun_slIsFeatureSupported>("slIsFeatureSupported");
    S.feature_fn = symbol<PFun_slGetFeatureFunction>("slGetFeatureFunction");
    S.gipa = reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(S.module, "vkGetInstanceProcAddr"));
    if (!S.init || !S.shut || !S.loaded || !S.supported || !S.feature_fn || !S.gipa) {
        logf("streamline: sl.interposer.dll lacks entry points this build needs (another Streamline version?): off");
        return false;
    }

    // What Streamline starts with. Manual hooking: this renderer creates its own Vulkan objects (the interposer's
    // vkCreateInstance and vkCreateDevice, reached through its vkGetInstanceProcAddr, add what DLSS-G needs). It keeps its own
    // command buffer state, and tags each frame's resources itself.
    static const sl::Feature features[] = {sl::kFeatureDLSS_G, sl::kFeatureReflex, sl::kFeaturePCL};
    const wchar_t* paths[] = {dir.c_str()};
    sl::Preferences pref{};
    pref.showConsole = false;
    pref.logLevel = sl::LogLevel::eDefault;
    pref.pathsToPlugins = paths;
    pref.numPathsToPlugins = 1;
    pref.pathToLogsAndData = dir.c_str();
    pref.logMessageCallback = sl_message;
    pref.flags = sl::PreferenceFlags::eDisableCLStateTracking | sl::PreferenceFlags::eUseManualHooking |
                 sl::PreferenceFlags::eUseFrameBasedResourceTagging;
    pref.featuresToLoad = features;
    pref.numFeaturesToLoad = 3;
    pref.applicationId = 231313132;   // (NVIDIA's sample id, for a build that has none of its own issued: see the programming guide)
    pref.engine = sl::EngineType::eCustom;
    pref.renderAPI = sl::RenderAPI::eVulkan;
    const sl::Result r = S.init(pref, sl::kSDKVersion);
    if (r != sl::Result::eOk) {
        logf("streamline: slInit failed (result %d; the DLLs must be version %d.%d.%d): off", (int)r, SL_VERSION_MAJOR,
             SL_VERSION_MINOR, SL_VERSION_PATCH);
        return false;
    }
    S.started = true;
    S.early_result = 1;
    logf("streamline: started from %s (%d.%d.%d)", utf8(dir).c_str(), SL_VERSION_MAJOR, SL_VERSION_MINOR, SL_VERSION_PATCH);
    return true;
}

PFN_vkGetInstanceProcAddr instance_proc() { return S.early_result == 1 ? S.gipa : nullptr; }

void device_ready(VkPhysicalDevice physical) {
    if (S.early_result != 1) return;
    bool loaded = false;
    const sl::Result lr = S.loaded(sl::kFeatureDLSS_G, loaded);
    if (lr != sl::Result::eOk || !loaded) {
        logf("streamline: the DLSS-G plugin is not loaded (result %d; is sl.dlss_g.dll beside sl.interposer.dll?)", (int)lr);
        return;
    }
    sl::AdapterInfo adapter{};
    adapter.vkPhysicalDevice = physical;
    const sl::Result sr = S.supported(sl::kFeatureDLSS_G, adapter);
    if (sr != sl::Result::eOk) {
        // (the usual causes: a GPU below the RTX 40 series, an old driver, no hardware-accelerated GPU scheduling on Windows)
        logf("streamline: DLSS-G does not run on this GPU or driver (result %d)", (int)sr);
        return;
    }
    S.available = true;
    logf("streamline: DLSS-G is supported on this GPU");

    // How many frames it can make between two rendered ones, as Streamline says it so far (0: it reports it after the first presents)
    void* fn = nullptr;
    if (S.feature_fn(sl::kFeatureDLSS_G, "slDLSSGGetState", fn) == sl::Result::eOk) S.dlssg_state = reinterpret_cast<PFun_slDLSSGGetState*>(fn);
    if (S.dlssg_state) {
        sl::DLSSGState state{};
        const sl::ViewportHandle viewport(0);
        const sl::Result gr = S.dlssg_state(viewport, state, nullptr);
        logf("streamline: DLSS-G state: result %d, status %u, up to %u generated frames between two rendered (0: not reported yet), "
             "about %llu MB of video memory",
             (int)gr, (unsigned)state.status, (unsigned)state.numFramesToGenerateMax,
             (unsigned long long)(state.estimatedVRAMUsageInBytes >> 20));
    }
}

bool available() { return S.available; }

void shutdown() {
    if (S.started && S.shut) S.shut();
    S.started = false;
    S.available = false;
}

#endif  // _WIN32

}  // namespace mkwvk::slfg
