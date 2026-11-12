// (recompzel) AMD FSR Frame Generation 4 ("Redstone"): vk_fsr4fg.h. The host side follows FSR SDK 2.4's frame generation API
// (Kits/FidelityFX/docs/techniques/frame-interpolation-api.md): a context with a Vulkan backend description, then each frame
// a configure, a prepare (depth, motion, camera) and a dispatch into our own output image, with
// FFX_FRAMEGENERATION_FLAG_NO_SWAPCHAIN_CONTEXT_NOTIFY: AMD's swapchain is never made, the renderer presents.
#include "vk_fsr4fg.h"

#include <atomic>
#include <cfloat>
#include <cstdlib>
#include <string>
#include <vector>

#include "vk_menu.h"   // (opts.fgtype: the Frame generation method row)

#ifdef HOOKSHOT_FSR
#include <chrono>
#include <mutex>

#include "vk_paths.h"

#include "api/include/ffx_api.h"
#include "api/include/ffx_api_types.h"
#include "api/include/vk/ffx_api_vk.h"
#include "framegeneration/include/ffx_framegeneration.h"
#endif
#include "vk_work.h"   // (after the others: the barriers here count as work for full_barrier)

namespace mkwvk {
namespace fsr4fg {

#if defined(HOOKSHOT_FSR) && defined(_WIN32)

namespace {

constexpr const char* kLoader = "amd_fidelityfx_loader_vk.dll";

struct Library {
    std::mutex mu;
    bool tried = false, ok = false;
    HMODULE lib = nullptr;
    PfnFfxCreateContext create = nullptr;
    PfnFfxDestroyContext destroy = nullptr;
    PfnFfxConfigure configure = nullptr;
    PfnFfxDispatch dispatch = nullptr;
    VkDeviceContext device_context{};
};
Library& lib() {   // (never destroyed: vk_fsr4.cpp's note, the process leaves with the device alive)
    static Library& l = *new Library;
    return l;
}

struct State {
    ffxCreateBackendVKDesc backend{};
    ffxCreateContextDescFrameGeneration desc{};
    ffxContext context = nullptr;
    uint32_t width = 0, height = 0, flags = 0;
    uint64_t frame_id = 0;
    std::atomic<bool> failed{false};
    uint64_t made = 0;
    bool told = false;
};
State& st() {
    static State& s = *new State;
    return s;
}

std::vector<std::string> library_dirs() {
    std::vector<std::string> d;
    if (const char* e = getenv("RX_VK_FSR4FG_DIR"); e && *e) d.emplace_back(e);
    char exe[MAX_PATH];
    DWORD n = game_module_path(exe, MAX_PATH);
    if (n && n < MAX_PATH) {
        std::string s(exe, n);
        d.push_back(s.substr(0, s.find_last_of("\\/")) + "\\fsr4fg");
    }
    n = GetModuleFileNameA(nullptr, exe, MAX_PATH);
    if (n && n < MAX_PATH) {
        std::string s(exe, n);
        d.push_back(s.substr(0, s.find_last_of("\\/")) + "\\fsr4fg");
    }
    return d;
}

bool load() {
    Library& l = lib();
    std::lock_guard lk(l.mu);
    if (l.tried) return l.ok;
    l.tried = true;
    std::string where;
    for (const std::string& dir : library_dirs()) {
        const std::string path = dir + "\\" + kLoader;
        where += (where.empty() ? "" : ", ") + dir;
        if (GetFileAttributesA(path.c_str()) == INVALID_FILE_ATTRIBUTES) continue;
        // (the frame generation DLL the loader picks lies beside it: the loader's folder first in the search)
        l.lib = LoadLibraryExA(path.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if (!l.lib) {
            logf("vk: AMD FSR 4 frame generation: %s not loaded (Windows error %lu)", path.c_str(), (unsigned long)GetLastError());
            continue;
        }
        logf("vk: AMD FSR 4 frame generation: %s", path.c_str());
        break;
    }
    if (!l.lib) {
        logf("vk: AMD FSR 4 frame generation: no %s in %s", kLoader, where.c_str());
        return false;
    }
    l.create = (PfnFfxCreateContext)(void*)GetProcAddress(l.lib, "ffxCreateContext");
    l.destroy = (PfnFfxDestroyContext)(void*)GetProcAddress(l.lib, "ffxDestroyContext");
    l.configure = (PfnFfxConfigure)(void*)GetProcAddress(l.lib, "ffxConfigure");
    l.dispatch = (PfnFfxDispatch)(void*)GetProcAddress(l.lib, "ffxDispatch");
    if (!l.create || !l.destroy || !l.configure || !l.dispatch) {
        logf("vk: AMD FSR 4 frame generation: %s lacks the FSR API's entry points", kLoader);
        return false;
    }
    l.device_context = VkDeviceContext{dev.device, dev.physical, vkGetDeviceProcAddr};
    l.ok = true;
    return true;
}

void on_message(uint32_t type, const wchar_t* message) {
    char text[512] = {};
    if (message) WideCharToMultiByte(CP_UTF8, 0, message, -1, text, (int)sizeof text - 1, nullptr, nullptr);
    logf("vk: AMD FSR 4 frame generation: AMD's %s: %s", type == FFX_API_MESSAGE_TYPE_ERROR ? "error" : "warning", text);
}

/// A context for frames of w x h (the render size any up to that), made again when the display size or the depth's far plane
/// changes. False, and failed for the rest of the run, when AMD's library will not make one (not an RX 9000, an old driver)
bool ensure_context(uint32_t w, uint32_t h, bool infinite) {
    State& s = st();
    Library& l = lib();
    const uint32_t flags = FFX_FRAMEGENERATION_ENABLE_DEPTH_INVERTED | (infinite ? FFX_FRAMEGENERATION_ENABLE_DEPTH_INFINITE : 0u);
    if (s.context && s.width == w && s.height == h && s.flags == flags) return true;
    if (s.context) {
        vkDeviceWaitIdle(dev.device);   // (its resources may still be in use by a recorded dispatch: rare, a resize)
        l.destroy(&s.context, nullptr);
        s.context = nullptr;
    }
    s.backend = {};
    s.backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;
    s.backend.deviceContext = l.device_context;
    s.desc = {};
    s.desc.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_FRAMEGENERATION;
    s.desc.header.pNext = &s.backend.header;
    s.desc.flags = flags;
    s.desc.displaySize = {w, h};
    s.desc.maxRenderSize = {w, h};
    s.desc.backBufferFormat = FFX_API_SURFACE_FORMAT_R8G8B8A8_UNORM;
    (void)on_message;
    const ffxReturnCode_t r = l.create(&s.context, &s.desc.header, nullptr);
    if (r != FFX_API_RETURN_OK || !s.context) {
        logf("vk: AMD FSR 4 frame generation: AMD's library made no context (%d) for %ux%u: the renderer's own interpolation "
             "makes the frames (it needs an RX 9000 GPU and a recent driver)", (int)r, w, h);
        s.context = nullptr;
        s.failed = true;
        return false;
    }
    s.width = w, s.height = h, s.flags = flags, s.frame_id = 0;
    logf("vk: AMD FSR 4 frame generation: a context for %ux%u%s", w, h, infinite ? " (infinite far plane)" : "");
    return true;
}

FfxApiResource resource(VkImage image, VkFormat format, uint32_t w, uint32_t h, VkImageUsageFlags usage, uint32_t state) {
    VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    ci.imageType = VK_IMAGE_TYPE_2D, ci.format = format, ci.extent = {w, h, 1};
    ci.mipLevels = 1, ci.arrayLayers = 1, ci.samples = VK_SAMPLE_COUNT_1_BIT, ci.tiling = VK_IMAGE_TILING_OPTIMAL;
    ci.usage = usage, ci.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    return ffxApiGetResourceVK((void*)image, ffxApiGetImageResourceDescriptionVK(image, ci, 0), state);
}

VkImageMemoryBarrier2 barrier(VkImage image, VkImageLayout from, VkImageLayout to) {
    VkImageMemoryBarrier2 b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2};
    b.srcStageMask = b.dstStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;
    b.srcAccessMask = b.dstAccessMask = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;
    b.oldLayout = from, b.newLayout = to;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = image, b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    return b;
}
void barriers(VkCommandBuffer cmd, const VkImageMemoryBarrier2* b, uint32_t n) {
    VkDependencyInfo di{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
    di.imageMemoryBarrierCount = n, di.pImageMemoryBarriers = b;
    vkCmdPipelineBarrier2(cmd, &di);
}

}  // namespace

bool available() {
    static const bool env_off = getenv("RX_VK_FSR4FG") && atoi(getenv("RX_VK_FSR4FG")) == 0;
    return !env_off && load();
}

bool wanted() { return opts.fgtype == 3 && !st().failed.load(std::memory_order_relaxed) && available(); }

bool generate(VkCommandBuffer cmd, const Inputs& in) {
    State& s = st();
    Library& l = lib();
    if (!wanted() || !in.color_image || !in.output_image || !in.depth_image || !in.motion_image || !in.render_w) return false;
    if (!ensure_context(in.width, in.height, in.far_z <= 0.0f || in.far_z >= FLT_MAX * 0.5f)) return false;
    const uint64_t id = ++s.frame_id;
    const uint32_t flags = FFX_FRAMEGENERATION_FLAG_NO_SWAPCHAIN_CONTEXT_NOTIFY;

    ffxConfigureDescFrameGeneration cfg{};
    cfg.header.type = FFX_API_CONFIGURE_DESC_TYPE_FRAMEGENERATION;
    cfg.swapChain = nullptr;
    cfg.frameGenerationEnabled = true;
    cfg.allowAsyncWorkloads = false;
    cfg.flags = flags;
    cfg.generationRect = {0, 0, (int32_t)in.width, (int32_t)in.height};
    cfg.frameID = id;
    if (l.configure(&s.context, &cfg.header) != FFX_API_RETURN_OK) {
        logf("vk: AMD FSR 4 frame generation: its configuration was refused: the renderer's own interpolation from now on");
        s.failed = true;
        return false;
    }

    constexpr VkImageLayout G = VK_IMAGE_LAYOUT_GENERAL, R = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    full_barrier(cmd);
    const VkImageMemoryBarrier2 to[3] = {barrier(in.depth_image, G, R), barrier(in.motion_image, G, R), barrier(in.color_image, G, R)};
    barriers(cmd, to, 3);
    ::mkwvk::rec::boundary(::mkwvk::rec::B_DIRECT);   // (ffxDispatch records into cmd itself)

    ffxDispatchDescFrameGenerationPrepareV2 prep{};
    prep.header.type = FFX_API_DISPATCH_DESC_TYPE_FRAMEGENERATION_PREPARE_V2;
    prep.frameID = id;
    prep.flags = flags;
    prep.commandList = cmd;
    prep.renderSize = {in.render_w, in.render_h};
    prep.jitterOffset = {in.jitter[0], in.jitter[1]};
    prep.motionVectorScale = {1.0f, 1.0f};   // (render pixels already, towards the frame before)
    prep.frameTimeDelta = in.frame_ms;
    prep.reset = in.reset;
    prep.cameraNear = in.near_z;
    prep.cameraFar = in.far_z > 0.0f && in.far_z < FLT_MAX * 0.5f ? in.far_z : 10000.0f;
    prep.cameraFovAngleVertical = in.fov_y > 0.0f ? in.fov_y : 1.0f;
    prep.viewSpaceToMetersFactor = 1.0f;
    prep.depth = resource(in.depth_image, VK_FORMAT_R32_SFLOAT, in.render_w, in.render_h, VK_IMAGE_USAGE_SAMPLED_BIT,
                          FFX_API_RESOURCE_STATE_COMPUTE_READ);
    prep.motionVectors = resource(in.motion_image, VK_FORMAT_R16G16_SFLOAT, in.render_w, in.render_h, VK_IMAGE_USAGE_SAMPLED_BIT,
                                  FFX_API_RESOURCE_STATE_COMPUTE_READ);
    // (the camera's place and axes: not read back from the game; a fixed frame, the camera's own view of itself)
    prep.cameraPosition[0] = prep.cameraPosition[1] = prep.cameraPosition[2] = 0.0f;
    prep.cameraUp[1] = 1.0f, prep.cameraRight[0] = 1.0f, prep.cameraForward[2] = -1.0f;
    ffxReturnCode_t r = l.dispatch(&s.context, &prep.header);

    if (r == FFX_API_RETURN_OK) {
        ffxDispatchDescFrameGeneration d{};
        d.header.type = FFX_API_DISPATCH_DESC_TYPE_FRAMEGENERATION;
        d.commandList = cmd;
        d.presentColor = resource(in.color_image, VK_FORMAT_R8G8B8A8_UNORM, in.width, in.height, VK_IMAGE_USAGE_SAMPLED_BIT,
                                  FFX_API_RESOURCE_STATE_COMPUTE_READ);
        d.outputs[0] = resource(in.output_image, VK_FORMAT_R8G8B8A8_UNORM, in.width, in.height,
                                VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
        d.numGeneratedFrames = 1;
        d.reset = in.reset;
        d.backbufferTransferFunction = FFX_API_BACKBUFFER_TRANSFER_FUNCTION_SRGB;
        d.minMaxLuminance[0] = 0.0f, d.minMaxLuminance[1] = 1.0f;
        d.generationRect = {0, 0, (int32_t)in.width, (int32_t)in.height};
        d.frameID = id;
        r = l.dispatch(&s.context, &d.header);
    }
    note_work();
    const VkImageMemoryBarrier2 back[3] = {barrier(in.depth_image, R, G), barrier(in.motion_image, R, G), barrier(in.color_image, R, G)};
    barriers(cmd, back, 3);
    full_barrier(cmd);
    if (r != FFX_API_RETURN_OK) {
        logf("vk: AMD FSR 4 frame generation: its dispatch failed (%d): the renderer's own interpolation from now on", (int)r);
        s.failed = true;
        return false;
    }
    if (!s.told) {
        s.told = true;
        logf("vk: AMD FSR 4 frame generation: AMD's machine-learning interpolation makes the frame between each two of the game's "
             "(%ux%u, its depth and motion %ux%u)", in.width, in.height, in.render_w, in.render_h);
    }
    if (++s.made % 600 == 0) logf("vk: AMD FSR 4 frame generation: %llu frames made", (unsigned long long)s.made);
    return true;
}

#else   // (a build without AMD's headers, or not Windows: the method is not offered)

bool available() { return false; }
bool wanted() { return false; }
bool generate(VkCommandBuffer, const Inputs&) { return false; }

#endif

}  // namespace fsr4fg
}  // namespace mkwvk
