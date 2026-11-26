// (hookshot) Each GPU's shader caches kept apart in the game folder's cache/ (vk_progcache.cpp's cache_sets_switch, at the start).
// Apart from Vulkan so that tests/test_gpu_sets.py can run it.
//
// The program cache, the driver's pipeline cache, the prepare record and the module identifiers are good for one translator AND one
// GPU (program_cache_stamp: the GPU's lanes, mesh shaders, storage alignment, vendor fixes). A start on another GPU found them made
// for another stamp and started them over: a laptop's integrated and dedicated GPUs, or a run on the other one, each threw away the
// other's 8 GB and more, and the next start on the first GPU prepared everything again (hours on an integrated GPU, 2026-11-16).
// Now the files of the GPU used before go aside, into cache/gpu_set_<its stamp>/, and a start on a GPU whose set is aside takes it
// back: two renames, no copy. A set made by another build of the translator is no use to anyone and goes; at most kKeep sets are
// kept aside (each can be gigabytes). hookshot_gpu_set.txt says which build and stamp the files in cache/ were made for.
#pragma once

#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

#include "pcache_stamp.h"

namespace gpu_sets {

inline const char* kOwnerFile = "hookshot_gpu_set.txt";
inline const char* kAsidePrefix = "gpu_set_";
constexpr size_t kKeep = 1;   // (sets kept aside: a laptop has two GPUs)

/// Whether name (a file in cache/) belongs to one GPU's set
inline bool is_set_file(const std::string& name) {
    static const char* const exact[] = {"hookshot_programs.bin", "hookshot_programs.idx", "hookshot_programs.zst.bin",
                                        "hookshot_programs.zst.idx", "hookshot_prepared.bin", "hookshot_prepared.bin.warming",
                                        "hookshot_pipelines.bin.built", "hookshot_pipelines.bin.built.warming",
                                        "hookshot_module_ids.bin"};
    for (const char* e : exact)
        if (name == e) return true;
    return name == pcache_stamp::kStampFile || pcache_stamp::is_cache_file(name);
}

struct Owner {
    uint64_t build = 0, stamp = 0;
};
/// The owner record in dir (with its separator); false: none, or not readable
inline bool read_owner(const std::string& dir, Owner* o) {
    FILE* f = fopen((dir + kOwnerFile).c_str(), "rb");
    if (!f) return false;
    unsigned long long b = 0, s = 0;
    const bool ok = fscanf(f, "build %llx stamp %llx", &b, &s) == 2;
    fclose(f);
    if (ok) o->build = b, o->stamp = s;
    return ok;
}
inline bool write_owner(const std::string& dir, const Owner& o, const std::string& gpu) {
    const std::string path = dir + kOwnerFile, tmp = path + ".tmp";
    FILE* f = fopen(tmp.c_str(), "wb");
    if (!f) return false;
    bool ok = fprintf(f, "build %016llx stamp %016llx\ngpu %s\n", (unsigned long long)o.build, (unsigned long long)o.stamp,
                      gpu.c_str()) > 0;
    ok = fclose(f) == 0 && ok;
    std::error_code ec;
    if (ok) std::filesystem::rename(tmp, path, ec);
    return ok && !ec;
}
inline std::string aside_dir(const std::string& dir, uint64_t stamp) {
    char name[48];
    snprintf(name, sizeof name, "%s%016llx", kAsidePrefix, (unsigned long long)stamp);
    return dir + name + "/";
}

/// The set's files in dir (names only)
inline std::vector<std::string> set_files(const std::string& dir) {
    std::vector<std::string> out;
    std::error_code ec;
    for (std::filesystem::directory_iterator it(dir, ec), end; !ec && it != end; it.increment(ec)) {
        std::error_code ec2;
        if (!it->is_regular_file(ec2)) continue;
        std::string name;
        try {
            name = it->path().filename().string();
        } catch (...) {   // (a name the code page cannot hold: never one of ours)
            continue;
        }
        if (is_set_file(name)) out.push_back(name);
    }
    return out;
}
/// The set's files moved from `from` to `to` (both with their separators; a file of the same name in `to` replaced)
inline size_t move_set(const std::string& from, const std::string& to, uint64_t* bytes) {
    size_t n = 0;
    for (const std::string& name : set_files(from)) {
        std::error_code ec;
        const uint64_t size = std::filesystem::file_size(from + name, ec);
        std::filesystem::remove(to + name, ec);   // (rename does not replace on Windows)
        std::error_code ec2;
        std::filesystem::rename(from + name, to + name, ec2);
        if (!ec2) n++, *bytes += size;
    }
    return n;
}

enum class What { kSame, kFirst, kSetAside, kRestored, kNew };
struct Result {
    What what = What::kSame;
    uint64_t from = 0;              // (the stamp of the set that was in cache/ before)
    size_t aside = 0, back = 0;     // (files moved aside, and back)
    uint64_t aside_bytes = 0, back_bytes = 0;
    size_t dropped_sets = 0;        // (sets aside made by another build, or past kKeep)
    uint64_t dropped_bytes = 0;
};

inline uint64_t tree_bytes(const std::string& dir) {
    uint64_t n = 0;
    std::error_code ec;
    for (std::filesystem::recursive_directory_iterator it(dir, ec), end; !ec && it != end; it.increment(ec)) {
        std::error_code ec2;
        if (it->is_regular_file(ec2)) n += it->file_size(ec2);
    }
    return n;
}

/// At the start, before any of the set's files is opened: cache/ (dir, with its separator) made ready for this build and stamp.
/// The set in it made by this build for another stamp goes aside; this stamp's set comes back from aside if it is there. A set in
/// cache/ made by another build is left for the caches' own checks, which start it over, as before
inline Result switch_to(const std::string& dir, uint64_t build, uint64_t stamp, const std::string& gpu) {
    Result r;
    std::error_code ec;
    // (the sets aside: another build's go; this build's, newest first)
    struct Aside { std::string path; uint64_t stamp; std::filesystem::file_time_type when; };
    std::vector<Aside> sets;
    for (std::filesystem::directory_iterator it(dir, ec), end; !ec && it != end; it.increment(ec)) {
        std::error_code ec2;
        if (!it->is_directory(ec2)) continue;
        std::string name;
        try {
            name = it->path().filename().string();
        } catch (...) {
            continue;
        }
        if (name.compare(0, strlen(kAsidePrefix), kAsidePrefix)) continue;
        const std::string path = dir + name + "/";
        Owner o;
        if (!read_owner(path, &o) || o.build != build) {
            r.dropped_bytes += tree_bytes(path);
            if (std::filesystem::remove_all(path, ec2) != static_cast<std::uintmax_t>(-1)) r.dropped_sets++;
            continue;
        }
        sets.push_back({path, o.stamp, std::filesystem::last_write_time(path, ec2)});
    }
    Owner now;
    const bool known = read_owner(dir, &now);
    if (known && now.build == build && now.stamp == stamp) {
        r.what = What::kSame;
    } else {
        r.from = known ? now.stamp : 0;
        r.what = known ? What::kNew : What::kFirst;
        // (this build's set of another stamp: aside, replacing an older copy of it)
        if (known && now.build == build) {
            const std::string to = aside_dir(dir, now.stamp);
            std::error_code ec2;
            std::filesystem::remove_all(to, ec2);
            std::filesystem::create_directories(to, ec2);
            r.aside = move_set(dir, to, &r.aside_bytes);
            write_owner(to, now, "");
            std::filesystem::last_write_time(to, std::filesystem::file_time_type::clock::now(), ec2);
            sets.erase(std::remove_if(sets.begin(), sets.end(), [&](const Aside& a) { return a.stamp == now.stamp; }), sets.end());
            sets.insert(sets.begin(), {to, now.stamp, std::filesystem::file_time_type::clock::now()});
            r.what = What::kSetAside;
        }
        // (this stamp's set aside: back into cache/)
        const auto mine = std::find_if(sets.begin(), sets.end(), [&](const Aside& a) { return a.stamp == stamp; });
        if (mine != sets.end()) {
            for (const std::string& name : set_files(dir)) {   // (another build's files still here: theirs is no use)
                std::error_code ec2;
                std::filesystem::remove(dir + name, ec2);
            }
            r.back = move_set(mine->path, dir, &r.back_bytes);
            std::error_code ec2;
            std::filesystem::remove_all(mine->path, ec2);
            sets.erase(mine);
            r.what = What::kRestored;
        }
        write_owner(dir, {build, stamp}, gpu);
    }
    // (at most kKeep sets aside, the newest)
    std::sort(sets.begin(), sets.end(), [](const Aside& a, const Aside& b) { return a.when > b.when; });
    for (size_t i = kKeep; i < sets.size(); i++) {
        std::error_code ec2;
        r.dropped_bytes += tree_bytes(sets[i].path);
        if (std::filesystem::remove_all(sets[i].path, ec2) != static_cast<std::uintmax_t>(-1)) r.dropped_sets++;
    }
    return r;
}

}   // namespace gpu_sets
