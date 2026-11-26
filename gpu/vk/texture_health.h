// (recompzel) Texture problems, told so a log can be searched for them: every place the renderer knows a texture came out
// wrong (sampled as the dummy, an upload that failed, illegal ASTC blocks) counts it here and
// writes its first lines with one prefix, "vk: texture problem [<kind>]:", and the textures' periodic line adds a sum,
// "vk: texture problems: ...", whenever a count changed. scripts/texture_problems.py reads a log for them (and for the
// older lines that say the same). Counts and addresses only, never texel values.
#pragma once

#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>

namespace mkwvk {

void logf(const char* fmt, ...);

enum class TexProblem : int { Dummy = 0, UploadFailed, AstcIllegal, Count };

inline const char* tex_problem_name(TexProblem k) {
    static const char* const names[] = {"dummy", "upload-failed", "astc-illegal"};
    return names[(int)k];
}

inline std::atomic<uint64_t>* tex_problem_counts() {
    static std::atomic<uint64_t> counts[(int)TexProblem::Count];
    return counts;
}

/// One problem of kind k; its detail line (printf-style) is written for the first 24 of each kind
inline void texture_problem(TexProblem k, const char* fmt, ...) {
    const uint64_t n = tex_problem_counts()[(int)k].fetch_add(1, std::memory_order_relaxed) + 1;
    if (n > 24) return;
    char text[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(text, sizeof text, fmt, ap);
    va_end(ap);
    logf("vk: texture problem [%s]: %s%s", tex_problem_name(k), text, n == 24 ? " (no more lines of this kind; the sum goes on)" : "");
}

/// The sum, from the textures' periodic line: written when a count changed since the last sum
inline void texture_problems_summary() {
    static uint64_t last[(int)TexProblem::Count];
    uint64_t now[(int)TexProblem::Count];
    bool changed = false;
    for (int i = 0; i < (int)TexProblem::Count; i++) {
        now[i] = tex_problem_counts()[i].load(std::memory_order_relaxed);
        changed |= now[i] != last[i];
    }
    if (!changed) return;
    logf("vk: texture problems: dummy %llu, upload-failed %llu, astc-illegal %llu (since the start; "
         "scripts/texture_problems.py reads them)", (unsigned long long)now[0], (unsigned long long)now[1],
         (unsigned long long)now[2]);
    for (int i = 0; i < (int)TexProblem::Count; i++) last[i] = now[i];
}

}  // namespace mkwvk
