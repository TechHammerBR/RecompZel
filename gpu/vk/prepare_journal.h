// (hookshot) The preparation's journal: which driver call a --prepare-shaders run was in when it died.
//
// The in-process guards (vk_draw.cpp guarded_graphics, guarded_compute, guarded_shader_module) catch an access violation on the
// calling thread. They do not catch a driver that ends the process another way (a fault on a thread of its own, abort, a
// fail-fast, a stack overflow) nor one that never returns. Such a run left nothing that said which shader it was in: the
// work fell to the game's own first start, which died in the same place.
//
// So a preparation asked for a journal (hookshot --prepare-shaders --prepare-journal <file>, HOOKSHOT_PREPARE_JOURNAL) appends
// one short line before each driver compile call and one after it. The Builder's supervisor (nx2/prepare_supervisor.py) reads
// the file when the run dies: a begin with no end is where it was. docs/shader-preparation.md has the whole of it.
//
// The lines ('\n' ended, fields separated by one space, numbers in hex except where said):
//   run <vendor> <driver> <from>                        a process opened the journal; its entries are numbered from <from> + 1
//   b <seq> <kind> <vendor> <driver> <program> <detail> before the call. kind: module, graphics or compute.
//                                                       "<vendor> <driver> <program>" is driver_faults::line()'s own text, a
//                                                       line of hookshot_driver_faults.txt as it stands; program 0: a shader
//                                                       of the renderer's own, which no file can leave out
//   e <seq> <result> <ms>                               after it: the VkResult (decimal; -77: a fault the guard caught) and
//                                                       the time (decimal)
//   t <seq> <s>                                         the entry has been open for <s> seconds (decimal), past the limit an
//                                                       entry gets: the run ends itself with exit status 6 right after
//
// Durability, for a process that dies (not for a power loss): the file is opened once, in append mode, and each line is one
// fwrite followed by fflush, under one lock, before the driver is entered. fflush hands the C library's buffer to the
// operating system (write() on Linux, WriteFile through the UCRT's _write on Windows): from then on the bytes are in the
// system's file cache, which belongs to the system and not to the process, so they reach the file however the process ends
// (a signal, TerminateProcess, an unhandled exception, _Exit). No fsync or FlushFileBuffers: those are for a system that
// dies, and would cost a disk write per shader. A .pending marker surrounds each write, so a crash during a write or a write
// failure leaves the supervisor an indication that it cannot attribute the run. A partial last line is also incomplete.
//
// Plain code with no Vulkan calls: tests/test_prepare_journal.py compiles it alone.
#pragma once

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>

#include "driver_faults.h"

namespace prepare_journal {

enum Kind { kModule, kGraphics, kCompute };
inline const char* kind_name(Kind k) {
    static const char* const names[] = {"module", "graphics", "compute"};
    return names[(int)k];
}

/// The exit status of a run that ended itself because one entry passed its time limit (the "t" line names it). 3 (no usable
/// Vulkan) and 4 (nothing moved in the whole run: vk_main.cpp prepare_watchdog) are as they were
constexpr int kExitEntryLimit = 6;
constexpr int kExitJournalError = 7;

/// An entry as hookshot_driver_faults.txt names one: driver_faults::line() without its line end
inline std::string identity(uint32_t vendor, uint32_t driver, uint64_t program) {
    std::string s = driver_faults::line(vendor, driver, program);
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
    return s;
}

/// What the supervisor asks of a run that starts again (--prepare-skip <file>, HOOKSHOT_PREPARE_SKIP), a line each:
///   skip <program>    never handed to the driver: its calls answer as a preparation skip
///   alone <program>   a suspect: serialize all driver calls during diagnosis, including unrelated and renderer calls
/// Other lines, comments (#) and malformed lines are skipped
struct Asked {
    std::unordered_set<uint64_t> skip, alone;
};
inline Asked asked_parse(const std::string& text) {
    Asked a;
    size_t at = 0;
    while (at < text.size()) {
        size_t end = text.find('\n', at);
        if (end == std::string::npos) end = text.size();
        const std::string l = text.substr(at, end - at);
        at = end + 1;
        char word[8] = {0};
        unsigned long long k = 0;
        char extra = 0;
        if (l.empty() || l[0] == '#') continue;
        if (sscanf(l.c_str(), "%7s %llx %c", word, &k, &extra) != 2 || !k) continue;
        if (!strcmp(word, "skip")) a.skip.insert(k);
        else if (!strcmp(word, "alone")) a.alone.insert(k);
    }
    return a;
}

/// The writer: one per process, shared by every compiling thread
class Writer {
public:
    /// The file opened for appending and this run's first line written. from: the last entry number of the runs before (0:
    /// none), so that numbers go on across the starts of one preparation. false: the file could not be opened (no journal)
    bool open(const std::string& path, uint32_t vendor, uint32_t driver, uint64_t from) {
        std::lock_guard lk(mu_);
        if (f_) return true;
        f_ = fopen(path.c_str(), "ab");
        if (!f_) return false;
        pending_ = path + ".pending";
        vendor_ = vendor, driver_ = driver, seq_ = from;
        char b[96];
        snprintf(b, sizeof b, "run %04x %08x %llx\n", vendor, driver, (unsigned long long)from);
        put(b);
        return true;
    }
    bool on() const {
        std::lock_guard lk(mu_);
        return f_ != nullptr;
    }
    /// Before a driver call: its line is in the system's hands when this returns. The entry's number (0: no journal)
    uint64_t begin(Kind kind, uint64_t program, uint64_t detail, int64_t now_ms) {
        std::lock_guard lk(mu_);
        if (!f_) return 0;
        const uint64_t seq = ++seq_;
        char b[160];
        snprintf(b, sizeof b, "b %llx %s %s %016llx\n", (unsigned long long)seq, kind_name(kind),
                 identity(vendor_, driver_, program).c_str(), (unsigned long long)detail);
        put(b);
        open_[seq] = {now_ms, program};
        return seq;
    }
    /// After it returned (or the guard caught a fault in it)
    void end(uint64_t seq, int result, int64_t now_ms) {
        std::lock_guard lk(mu_);
        if (!f_ || !seq) return;
        const auto it = open_.find(seq);
        if (it == open_.end()) return;
        char b[96];
        snprintf(b, sizeof b, "e %llx %d %lld\n", (unsigned long long)seq, result, (long long)(now_ms - it->second.began_ms));
        open_.erase(it);
        put(b);
    }
    /// The entry open the longest, when that is limit_ms or more: its "t" line is written and its number comes back (0: none
    /// is overdue). The caller then ends the run with kExitEntryLimit. program, open_ms: that entry's, for the log
    uint64_t overdue(int64_t limit_ms, int64_t now_ms, uint64_t* program = nullptr, int64_t* open_ms = nullptr) {
        std::lock_guard lk(mu_);
        if (!f_ || limit_ms <= 0) return 0;
        uint64_t oldest = 0;
        int64_t began = 0;
        for (const auto& [seq, o] : open_)
            if (!oldest || o.began_ms < began || (o.began_ms == began && seq < oldest)) oldest = seq, began = o.began_ms;
        if (!oldest || now_ms - began < limit_ms) return 0;
        char b[96];
        snprintf(b, sizeof b, "t %llx %lld\n", (unsigned long long)oldest, (long long)((now_ms - began) / 1000));
        put(b);
        if (program) *program = open_[oldest].program;
        if (open_ms) *open_ms = now_ms - began;
        return oldest;
    }
    /// How many entries are open now
    size_t open_count() const {
        std::lock_guard lk(mu_);
        return open_.size();
    }

private:
    struct Open {
        int64_t began_ms;
        uint64_t program;
    };
    /// A marker exists before a write starts and until it has been flushed. A crash or failed write leaves it in place.
    /// If a marker cannot be made, no journal write is attempted. Stop immediately on any error, before another call can
    /// go unjournalled; the supervisor also treats this exit status as an incomplete journal. Under mu_.
    void put(const char* line) {
        FILE* marker = fopen(pending_.c_str(), "wb");
        if (!marker) std::_Exit(kExitJournalError);
        if (fclose(marker) != 0) std::_Exit(kExitJournalError);
        const size_t n = strlen(line);
        if (fwrite(line, 1, n, f_) != n || fflush(f_) != 0 || ferror(f_)) std::_Exit(kExitJournalError);
        if (remove(pending_.c_str()) != 0) std::_Exit(kExitJournalError);
    }
    mutable std::mutex mu_;
    FILE* f_ = nullptr;   // (never closed: the run ends through _Exit or TerminateProcess, and every line is flushed already)
    std::string pending_;
    uint32_t vendor_ = 0, driver_ = 0;
    uint64_t seq_ = 0;
    std::unordered_map<uint64_t, Open> open_;
};

/// RX_VK_TEST_PREPARE_FAULT (a test of the supervisor): a journalled run dies (crash:) or never returns (hang:) in an entry
/// of chosen programs, as a driver that fails on those shaders would: the same programs in every run, so that a run started
/// again with the suspects one at a time meets the same one, and a run that leaves it out gets through.
///   crash:<n>, hang:<n>           every program whose key is a multiple of n: about one program in n; 1: every program
///   crash:=<key>, hang:=<key>     the program of that key (hex) alone
/// An entry number would not do: with several threads the entries of two runs are not numbered alike.
/// mode 0: not set, or not understood (*bad)
struct TestFault {
    int mode = 0;   // 1 crash, 2 hang
    uint64_t every = 0, key = 0;
};
inline TestFault test_fault_parse(const char* text, bool* bad = nullptr) {
    TestFault t;
    if (bad) *bad = false;
    if (!text || !*text) return t;
    const char* rest = nullptr;
    if (!strncmp(text, "crash:", 6)) t.mode = 1, rest = text + 6;
    else if (!strncmp(text, "hang:", 5)) t.mode = 2, rest = text + 5;
    unsigned long long n = 0;
    char extra = 0;
    if (rest && rest[0] == '=' && sscanf(rest + 1, "%llx%c", &n, &extra) == 1 && n) {
        t.key = n;
    } else if (rest && rest[0] >= '0' && rest[0] <= '9' && sscanf(rest, "%llu%c", &n, &extra) == 1 && n) {
        t.every = n;
    } else {
        t = TestFault{};
        if (bad) *bad = true;
    }
    return t;
}
/// Whether the test fires on an entry of this program (never on a shader of the renderer's own, program 0)
inline bool test_fault_here(const TestFault& t, uint64_t program) {
    if (!t.mode || !program) return false;
    return t.key ? program == t.key : program % t.every == 0;
}

}  // namespace prepare_journal
