// (recompzel) NVIDIA Streamline: loading, starting and asking what the GPU can do (vk_streamline.h).
#include "vk_streamline.h"

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>

#include "vk_internal.h"
#include "vk_menu.h"   // (opts: the Insert menu's Frame generation rows)

#ifdef _WIN32
#include <windows.h>

#include <filesystem>
#include <string>

// NVIDIA's public headers (third_party/streamline/include). Only plain structs and function-pointer types cross to the DLLs:
// the one type with a virtual member, sl::FrameToken, is only ever held by pointer.
#include <sl.h>
#include <sl_consts.h>
#include <sl_matrix_helpers.h>
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
bool active() { return false; }
int frames_to_generate() { return 0; }
int max_generated() { return 0; }
void idle_tick() {}
void frame_inputs(const FrameInputs&) {}
void present_begins() {}
void submit_ends() {}
void present_starts() {}
void present_ends() {}
void next_frame() {}
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
    PFun_slDLSSGSetOptions* dlssg_options = nullptr;
    PFun_slGetNewFrameToken* new_token = nullptr;
    PFun_slSetConstants* set_constants = nullptr;
    PFun_slSetTagForFrame* set_tag = nullptr;
    PFun_slPCLSetMarker* pcl_marker = nullptr;
    PFun_slReflexSetOptions* reflex_options = nullptr;
    PFun_slReflexSleep* reflex_sleep = nullptr;
    bool live = false;                  // (everything found: DLSS-G runs)
    std::mutex mu;
    sl::FrameToken* token = nullptr;    // (this frame's)
    bool have_inputs = false;           // (this frame's depth and motion were tagged)
    uint32_t in_w = 0, in_h = 0;        // (their render size)
    uint64_t frames = 0, frames_on = 0, tag_errors = 0;
    bool told_on = false;
    int max_gen = 1;                    // (the most frames DLSS-G makes between two rendered ones here: its state says, 2x on an RTX 40)
    bool was_on = false;                // (DLSS-G was switched on and Reflex handed to Streamline: idle_tick undoes it)
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
        if (e && e[0]) {
            S.wanted = e[0] == '1';   // (=1 asks for it, =0 never)
        } else {
            // By default whenever the Streamline files are beside the game (the launcher puts them there for RTX 40 and 50), so
            // the Frame generation method row offers NVIDIA DLSS without an environment variable
            S.wanted = GetFileAttributesW((exe_dir() / L"streamline" / L"sl.interposer.dll").c_str()) != INVALID_FILE_ATTRIBUTES;
        }
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
        if (gr == sl::Result::eOk && state.numFramesToGenerateMax > 0) S.max_gen = (int)state.numFramesToGenerateMax;
        logf("streamline: DLSS-G state: result %d, status %u, up to %u generated frames between two rendered (0: not reported yet), "
             "about %llu MB of video memory",
             (int)gr, (unsigned)state.status, (unsigned)state.numFramesToGenerateMax,
             (unsigned long long)(state.estimatedVRAMUsageInBytes >> 20));
    }

    // Phase 2: what each frame needs (core functions from the interposer, the features' by their names)
    S.new_token = symbol<PFun_slGetNewFrameToken>("slGetNewFrameToken");
    S.set_constants = symbol<PFun_slSetConstants>("slSetConstants");
    S.set_tag = symbol<PFun_slSetTagForFrame>("slSetTagForFrame");
    void* pf = nullptr;
    if (S.feature_fn(sl::kFeaturePCL, "slPCLSetMarker", pf) == sl::Result::eOk) S.pcl_marker = reinterpret_cast<PFun_slPCLSetMarker*>(pf);
    pf = nullptr;
    if (S.feature_fn(sl::kFeatureReflex, "slReflexSetOptions", pf) == sl::Result::eOk) S.reflex_options = reinterpret_cast<PFun_slReflexSetOptions*>(pf);
    pf = nullptr;
    if (S.feature_fn(sl::kFeatureReflex, "slReflexSleep", pf) == sl::Result::eOk) S.reflex_sleep = reinterpret_cast<PFun_slReflexSleep*>(pf);
    pf = nullptr;
    if (S.feature_fn(sl::kFeatureDLSS_G, "slDLSSGSetOptions", pf) == sl::Result::eOk) S.dlssg_options = reinterpret_cast<PFun_slDLSSGSetOptions*>(pf);
    if (!S.new_token || !S.set_constants || !S.set_tag || !S.pcl_marker || !S.reflex_options || !S.reflex_sleep || !S.dlssg_options ||
        !S.dlssg_state) {
        logf("streamline: some of the functions a frame needs were not found (token %d, constants %d, tags %d, PCL %d, Reflex %d/%d, "
             "DLSS-G options %d, state %d): DLSS-G does not run", S.new_token != nullptr, S.set_constants != nullptr, S.set_tag != nullptr,
             S.pcl_marker != nullptr, S.reflex_options != nullptr, S.reflex_sleep != nullptr, S.dlssg_options != nullptr,
             S.dlssg_state != nullptr);
        return;
    }
    S.live = true;
    logf("streamline: DLSS-G is ready: it runs when the Insert menu's Frame generation method is NVIDIA DLSS Frame Generation and the "
         "Frame generation row is 2x or more; then Streamline's Reflex and markers replace vk_reflex.cpp's");
}

bool available() { return S.available; }
int max_generated() { return S.live ? S.max_gen : 0; }
/// Frames to make between two rendered ones: the Insert menu's Frame generation row (2x and up) with the method DLSS-G, at the
/// most this GPU makes. 0: DLSS-G is not wanted now, and the renderer's own Reflex and frame interpolation are as without it
int frames_to_generate() {
    if (!S.live || opts.fgtype != 1 || opts.framegen < 2) return 0;
    return std::min(opts.framegen - 1, std::max(1, S.max_gen));
}
bool active() { return frames_to_generate() > 0; }

namespace {

/// With S.mu held: this frame's token (made at the first ask)
sl::FrameToken* token_locked() {
    if (!S.token && S.new_token) {
        sl::FrameToken* t = nullptr;
        if (S.new_token(t, nullptr) == sl::Result::eOk) S.token = t;
    }
    return S.token;
}

void marker_locked(sl::PCLMarker m) {
    if (sl::FrameToken* t = token_locked()) S.pcl_marker(m, *t);
}

/// A perspective projection with a depth range of 0 to 1 (not reversed), row major, as Streamline's helpers have them
sl::float4x4 projection(float fov_y, float aspect, float n, float f) {
    const float t = 1.0f / std::tan(fov_y * 0.5f);
    sl::float4x4 m = {sl::float4(t / aspect, 0, 0, 0), sl::float4(0, t, 0, 0), sl::float4(0, 0, f / (f - n), 1),
                      sl::float4(0, 0, -n * f / (f - n), 0)};
    return m;
}

const char* status_text(uint32_t status) {
    if (!status) return "ok";
    static char b[160];
    b[0] = 0;
    const struct { uint32_t bit; const char* name; } names[] = {
        {1u << 0, "resolution too low"}, {1u << 1, "Reflex not detected"}, {1u << 2, "HDR format not supported"},
        {1u << 3, "common constants invalid"}, {1u << 4, "needs a swapchain index call"}};
    for (const auto& n : names)
        if (status & n.bit) snprintf(b + strlen(b), sizeof b - strlen(b), "%s%s", b[0] ? ", " : "", n.name);
    return b[0] ? b : "see the programming guide";
}

}  // namespace

/// Every present while DLSS-G is not wanted (vk_reflex.cpp): once after it was, DLSS-G is switched off and Streamline's Reflex
/// too, so the renderer's own are the only ones. The swapchain is made again by vk_reflex.cpp when Reflex changes hands
void idle_tick() {
    if (!S.live || !S.was_on) return;
    std::lock_guard lk(S.mu);
    S.was_on = false;
    sl::DLSSGOptions o{};
    o.mode = sl::DLSSGMode::eOff;
    o.flags = sl::DLSSGFlags::eRetainResourcesWhenOff;
    const sl::Result r = S.dlssg_options(sl::ViewportHandle(0), o);
    sl::ReflexOptions ro{};
    ro.mode = sl::eOff;
    S.reflex_options(ro);
    logf("streamline: DLSS-G off (the menu): the renderer's own Reflex and frame generation are back (slDLSSGSetOptions result %d)", (int)r);
}

void next_frame() {
    if (!S.live) return;
    std::lock_guard lk(S.mu);
    sl::FrameToken* t = nullptr;
    if (S.new_token(t, nullptr) != sl::Result::eOk) return;
    S.token = t, S.have_inputs = false;
    S.reflex_sleep(*t);
    S.pcl_marker(sl::PCLMarker::eSimulationStart, *t);
}

void present_begins() {
    if (!S.live) return;
    std::lock_guard lk(S.mu);
    if (!S.was_on) {   // (back on after the menu turned it off: Reflex is Streamline's again)
        sl::ReflexOptions ro{};
        ro.mode = sl::eLowLatency;
        const sl::Result rr = S.reflex_options(ro);
        if (rr != sl::Result::eOk) logf("streamline: Reflex did not start (result %d): DLSS-G needs it", (int)rr);
        S.was_on = true;
    }
    marker_locked(sl::PCLMarker::eSimulationEnd);
    marker_locked(sl::PCLMarker::eRenderSubmitStart);
    // DLSS-G's options for this frame, on the present thread: on when the frame's depth and motion were tagged, else off (the
    // menus, a loading screen, a frame the upscale did not take), keeping its resources so turning it on again is quick
    sl::DLSSGOptions o{};
    o.mode = S.have_inputs ? sl::DLSSGMode::eOn : sl::DLSSGMode::eOff;
    o.numFramesToGenerate = (uint32_t)std::max(1, frames_to_generate());
    o.flags = sl::DLSSGFlags::eRetainResourcesWhenOff;
    o.mvecDepthWidth = S.in_w, o.mvecDepthHeight = S.in_h;
    const sl::ViewportHandle viewport(0);
    const sl::Result r = S.dlssg_options(viewport, o);
    static sl::Result last = sl::Result::eOk;
    if (r != last) logf("streamline: slDLSSGSetOptions result %d", (int)r), last = r;
    S.frames++;
    if (S.have_inputs) S.frames_on++;
    if (S.frames % 300 == 0 && S.dlssg_state) {
        sl::DLSSGState state{};
        const sl::Result gr = S.dlssg_state(viewport, state, &o);
        if (gr == sl::Result::eOk && state.numFramesToGenerateMax > 0) S.max_gen = (int)state.numFramesToGenerateMax;
        logf("streamline: DLSS-G over the last 300 frames: on for %llu, status %u (%s), %u frames presented since the last look, "
             "up to %u generated per rendered, about %llu MB",
             (unsigned long long)S.frames_on, (unsigned)state.status, gr == sl::Result::eOk ? status_text((uint32_t)state.status) : "state not read",
             (unsigned)state.numFramesActuallyPresented, (unsigned)state.numFramesToGenerateMax,
             (unsigned long long)(state.estimatedVRAMUsageInBytes >> 20));
        S.frames_on = 0;
    }
}

void submit_ends() {
    if (!S.live) return;
    std::lock_guard lk(S.mu);
    marker_locked(sl::PCLMarker::eRenderSubmitEnd);
}
void present_starts() {
    if (!S.live) return;
    std::lock_guard lk(S.mu);
    marker_locked(sl::PCLMarker::ePresentStart);
}
void present_ends() {
    if (!S.live) return;
    std::lock_guard lk(S.mu);
    marker_locked(sl::PCLMarker::ePresentEnd);
}

void frame_inputs(const FrameInputs& in) {
    if (!S.live || !in.depth || !in.motion || !in.render_w || !in.render_h) return;
    std::lock_guard lk(S.mu);
    sl::FrameToken* t = token_locked();
    if (!t) return;
    const sl::ViewportHandle viewport(0);

    sl::Constants c{};
    const float n = in.near_z > 0.0f ? in.near_z : 0.1f;
    float f = in.far_z > n && in.far_z < 1.0e6f ? in.far_z : 1000.0f;
    const float aspect = (float)in.render_w / (float)in.render_h;
    c.cameraViewToClip = projection(in.fov_y > 0.01f ? in.fov_y : 1.0f, aspect, n, f);
    sl::matrixFullInvert(c.clipToCameraView, c.cameraViewToClip);
    // (the scene's camera motion is already in the motion vectors; the matrices between frames are not known to the renderer, so
    // identity: Streamline then takes the motion from the buffer alone)
    const sl::float4x4 id = {sl::float4(1, 0, 0, 0), sl::float4(0, 1, 0, 0), sl::float4(0, 0, 1, 0), sl::float4(0, 0, 0, 1)};
    c.clipToLensClip = id, c.clipToPrevClip = id, c.prevClipToClip = id;
    c.jitterOffset = sl::float2(in.jitter[0], in.jitter[1]);
    c.mvecScale = sl::float2(1.0f / (float)in.render_w, 1.0f / (float)in.render_h);
    c.cameraPinholeOffset = sl::float2(0, 0);
    c.cameraPos = sl::float3(0, 0, 0), c.cameraUp = sl::float3(0, 1, 0), c.cameraRight = sl::float3(1, 0, 0), c.cameraFwd = sl::float3(0, 0, 1);
    c.cameraNear = n, c.cameraFar = f, c.cameraFOV = in.fov_y > 0.01f ? in.fov_y : 1.0f, c.cameraAspectRatio = aspect;
    c.motionVectorsInvalidValue = sl::INVALID_FLOAT;
    c.depthInverted = sl::Boolean::eFalse;
    c.cameraMotionIncluded = sl::Boolean::eTrue;
    c.motionVectors3D = sl::Boolean::eFalse;
    c.reset = in.reset ? sl::Boolean::eTrue : sl::Boolean::eFalse;
    c.orthographicProjection = sl::Boolean::eFalse;
    c.motionVectorsDilated = sl::Boolean::eFalse;
    c.motionVectorsJittered = sl::Boolean::eFalse;
    const sl::Result cr = S.set_constants(c, *t, viewport);

    sl::Resource depth(sl::ResourceType::eTex2d, (void*)in.depth, nullptr, (void*)in.depth_view, VK_IMAGE_LAYOUT_GENERAL);
    depth.width = in.depth_w, depth.height = in.depth_h, depth.nativeFormat = (uint32_t)in.depth_format;
    depth.mipLevels = 1, depth.arrayLayers = 1, depth.flags = 0, depth.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    sl::Resource motion(sl::ResourceType::eTex2d, (void*)in.motion, nullptr, (void*)in.motion_view, VK_IMAGE_LAYOUT_GENERAL);
    motion.width = in.motion_w, motion.height = in.motion_h, motion.nativeFormat = (uint32_t)in.motion_format;
    motion.mipLevels = 1, motion.arrayLayers = 1, motion.flags = 0, motion.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    sl::Extent ext{};
    ext.top = 0, ext.left = 0, ext.width = in.render_w, ext.height = in.render_h;
    const sl::ResourceTag tags[2] = {
        sl::ResourceTag(&depth, sl::kBufferTypeDepth, sl::ResourceLifecycle::eValidUntilPresent, &ext),
        sl::ResourceTag(&motion, sl::kBufferTypeMotionVectors, sl::ResourceLifecycle::eValidUntilPresent, &ext)};
    const sl::Result tr = S.set_tag(*t, viewport, tags, 2, nullptr);
    if ((cr != sl::Result::eOk || tr != sl::Result::eOk) && S.tag_errors++ < 8)
        logf("streamline: constants result %d, tags result %d", (int)cr, (int)tr);
    S.have_inputs = cr == sl::Result::eOk && tr == sl::Result::eOk;
    S.in_w = in.render_w, S.in_h = in.render_h;
    if (S.have_inputs && !S.told_on) {
        S.told_on = true;
        logf("streamline: DLSS-G is given the scene's depth and motion (%ux%u): on from the frames that have them", in.render_w,
             in.render_h);
    }
}

void shutdown() {
    S.live = false;
    if (S.started && S.shut) S.shut();
    S.started = false;
    S.available = false;
}

#endif  // _WIN32

}  // namespace mkwvk::slfg
