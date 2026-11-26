// (hookshot) F12's picture on the disk: vk_screenshot.h. On Windows the PNG is written by Windows' own encoder (WIC), so the
// file is compressed (a 1920x1080 picture is ~2 to 3 MB, where write_png's stored blocks make 6.2 MB) with no library of
// ours; elsewhere write_png (vk_replay.cpp) writes it uncompressed.
#include "vk_screenshot.h"

#include <cstdio>
#include <ctime>
#include <sys/stat.h>

#include "vk_dump.h"

#ifdef _WIN32
#include <direct.h>
#include <initguid.h>   // (before wincodec.h: its GUIDs are defined here, no import library needed for them)
#include <windows.h>
#include <wincodec.h>
#endif

namespace mkwvk {
void logf(const char* fmt, ...);

std::string screenshot_path(const std::string& folder) {
    if (folder.empty()) return "";
#ifdef _WIN32
    {   // (the game folder's path is UTF-8: the folder made by its wide name)
        wchar_t wf[MAX_PATH * 2];
        if (MultiByteToWideChar(CP_UTF8, 0, folder.c_str(), -1, wf, MAX_PATH * 2)) _wmkdir(wf);
    }
    const char sep = '\\';
#else
    mkdir(folder.c_str(), 0755);
    const char sep = '/';
#endif
    const time_t now = time(nullptr);
    struct tm t {};
#ifdef _WIN32
    localtime_s(&t, &now);
#else
    localtime_r(&now, &t);
#endif
    char stamp[64];
    strftime(stamp, sizeof stamp, "Hookshot %Y-%m-%d %H-%M-%S", &t);
    for (int n = 1; n < 100; n++) {
        char tail[16] = "";
        if (n > 1) snprintf(tail, sizeof tail, " (%d)", n);
        const std::string path = folder + sep + stamp + tail + ".png";
#ifdef _WIN32
        wchar_t wp[MAX_PATH * 2];
        if (!MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wp, MAX_PATH * 2)) return "";
        if (GetFileAttributesW(wp) == INVALID_FILE_ATTRIBUTES) return path;
#else
        struct stat sb;
        if (stat(path.c_str(), &sb) != 0) return path;
#endif
    }
    return "";
}

#ifdef _WIN32
namespace {
template <class T>
void release(T*& p) {
    if (p) p->Release(), p = nullptr;
}
} // namespace

bool screenshot_write(const std::string& path, const uint8_t* rgba, uint32_t w, uint32_t h) {
    if (path.empty() || !w || !h) return false;
    wchar_t wide[MAX_PATH * 2];
    if (!MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wide, MAX_PATH * 2)) return false;
    // (the encoder's 24 bits a pixel, blue first: the alpha the game leaves in its picture is not a transparency)
    const uint32_t stride = w * 3;
    std::vector<uint8_t> bgr((size_t)stride * h);
    for (size_t i = 0, n = (size_t)w * h; i < n; i++) {
        bgr[i * 3 + 0] = rgba[i * 4 + 2];
        bgr[i * 3 + 1] = rgba[i * 4 + 1];
        bgr[i * 3 + 2] = rgba[i * 4 + 0];
    }
    // (ole32's three functions loaded at their first use, as vk_menu.cpp's share_proc loads its own: hookshot_vk.dll imports only
    // kernel32, user32, gdi32, advapi32 and the UCRT, which the DLSS workflow's import check holds it to. Without ole32 the
    // picture is written without compression, as for any failure below)
    using CoInitFn = HRESULT(WINAPI*)(void*, DWORD);
    using CoUninitFn = void(WINAPI*)();
    using CoCreateFn = HRESULT(WINAPI*)(REFCLSID, IUnknown*, DWORD, REFIID, void**);
    static const HMODULE ole32 = LoadLibraryExW(L"ole32.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
    static const auto co_init = ole32 ? (CoInitFn)(void*)GetProcAddress(ole32, "CoInitializeEx") : nullptr;
    static const auto co_uninit = ole32 ? (CoUninitFn)(void*)GetProcAddress(ole32, "CoUninitialize") : nullptr;
    static const auto co_create = ole32 ? (CoCreateFn)(void*)GetProcAddress(ole32, "CoCreateInstance") : nullptr;
    const HRESULT co = co_init && co_uninit ? co_init(nullptr, COINIT_MULTITHREADED) : E_FAIL;   // (this worker thread's own; S_FALSE: already was)
    IWICImagingFactory* factory = nullptr;
    IWICStream* stream = nullptr;
    IWICBitmapEncoder* encoder = nullptr;
    IWICBitmapFrameEncode* frame = nullptr;
    WICPixelFormatGUID format = GUID_WICPixelFormat24bppBGR;
    HRESULT hr = co_create ? co_create(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_IWICImagingFactory, (void**)&factory)
                           : E_FAIL;
    const char* step = "the imaging factory";
    if (SUCCEEDED(hr)) step = "the stream", hr = factory->CreateStream(&stream);
    if (SUCCEEDED(hr)) step = "the file", hr = stream->InitializeFromFilename(wide, GENERIC_WRITE);
    if (SUCCEEDED(hr)) step = "the encoder", hr = factory->CreateEncoder(GUID_ContainerFormatPng, nullptr, &encoder);
    if (SUCCEEDED(hr)) hr = encoder->Initialize(stream, WICBitmapEncoderNoCache);
    if (SUCCEEDED(hr)) step = "the frame", hr = encoder->CreateNewFrame(&frame, nullptr);
    if (SUCCEEDED(hr)) hr = frame->Initialize(nullptr);
    if (SUCCEEDED(hr)) hr = frame->SetSize(w, h);
    if (SUCCEEDED(hr)) hr = frame->SetPixelFormat(&format);
    if (SUCCEEDED(hr) && !IsEqualGUID(format, GUID_WICPixelFormat24bppBGR)) hr = E_FAIL;   // (the encoder chose another layout)
    if (SUCCEEDED(hr)) step = "the pixels", hr = frame->WritePixels(h, stride, (UINT)bgr.size(), bgr.data());
    if (SUCCEEDED(hr)) step = "the end of the file", hr = frame->Commit();
    if (SUCCEEDED(hr)) hr = encoder->Commit();
    release(frame);
    release(encoder);
    release(stream);
    release(factory);
    if (SUCCEEDED(co)) co_uninit();
    if (FAILED(hr)) {
        logf("vk: screenshot: Windows' PNG encoder failed at %s (%#lx): written without compression", step, (unsigned long)hr);
        DeleteFileW(wide);   // (what the encoder left of it)
        write_png(path.c_str(), rgba, w, h);
    }
    struct stat sb;
    return stat(path.c_str(), &sb) == 0 && sb.st_size > 0;
}
#else
bool screenshot_write(const std::string& path, const uint8_t* rgba, uint32_t w, uint32_t h) {
    if (path.empty() || !w || !h) return false;
    write_png(path.c_str(), rgba, w, h);
    struct stat sb;
    return stat(path.c_str(), &sb) == 0 && sb.st_size > 0;
}
#endif
} // namespace mkwvk
