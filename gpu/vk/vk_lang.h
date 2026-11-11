// (recompzel) The menu's language: the Insert menu, the FPS counter and the start-up screen are written in English in the code,
// and every text goes to the screen through gpu/vk/vk_ui.h (text, para, size_of). This turns an English text into the chosen
// language there, at the last moment, from a dictionary (assets/lang/pt-BR.tsv, built into the game as vk_lang_pt_br.inc by
// nx2/gen_lang.py; a lang/pt-BR.tsv beside the game's files is read instead, to try a change without a build).
//
// The dictionary maps a whole English text to its translation. A text with %d, %s, %.1f ... (a format the code fills in) is a
// pattern: the numbers carry over, and a %s is translated in turn. A text made of several (a list "A and B") is translated by
// the known pieces in it. A text not in the dictionary stays English and is written to hookshot_ui_missing.txt (once each, at
// most kMissMax), so a translation can be completed from what players see.
//
// No platform code, no ImGui: tests can use it alone. The menu says which language (set_mode), where the files are (set_dir)
// and what Windows is set to (set_system).
#pragma once

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_set>
#include <vector>

namespace mkwvk::lang {

enum Mode { kAuto = 0, kEnglish = 1, kPortuguese = 2 };

namespace detail {

constexpr int kMissMax = 800;   // (texts written to the missing list)
constexpr int kRing = 64;       // (translated texts kept for the caller to read: the last kRing)
constexpr int kCache = 512;     // (slots of the memory of texts translated by pattern or by pieces)

struct Pat {
    std::vector<std::string> lit;    // (the literals around the conversions: lit.size() == conv.size() + 1)
    std::vector<char> conv;          // d, u, f, s or c
    std::vector<std::string> tlit;   // (the translation's literals, the same way)
    size_t min_len = 0;
};

struct CacheSlot {
    std::string src, dst;
    bool used = false;
};

struct State {
    std::vector<std::string> en, tr;   // (the texts with nothing to fill in)
    std::vector<char> whole;           // (each one only as a whole text, never as a piece of another: a third column x)
    std::vector<uint32_t> table;       // (their hash table: index + 1, 0 empty)
    std::vector<Pat> pats;
    std::vector<int> pieces[256];      // (the entries usable as pieces, by first byte, the longest first)
    std::string loaded_from;
    bool ready = false;
};

inline uint64_t hash(const char* s, size_t n) {
    uint64_t h = 1469598103934665603ull;
    for (size_t i = 0; i < n; i++) h = (h ^ (unsigned char)s[i]) * 1099511628211ull;
    return h;
}

inline bool is_conv_letter(char c) { return c == 'd' || c == 'i' || c == 'u' || c == 'f' || c == 's' || c == 'c'; }

/// A text split at its conversions: literals (with %% as %) and the letters of the conversions
inline void split(const std::string& t, std::vector<std::string>& lit, std::vector<char>& conv) {
    lit.assign(1, std::string());
    conv.clear();
    for (size_t i = 0; i < t.size(); i++) {
        if (t[i] != '%') {
            lit.back() += t[i];
            continue;
        }
        if (i + 1 < t.size() && t[i + 1] == '%') {
            lit.back() += '%';
            i++;
            continue;
        }
        size_t j = i + 1;
        if (j < t.size() && t[j] == '.') {
            j++;
            while (j < t.size() && t[j] >= '0' && t[j] <= '9') j++;
        }
        while (j < t.size() && (t[j] == 'l' || t[j] == 'z')) j++;
        if (j < t.size() && is_conv_letter(t[j])) {
            conv.push_back(t[j] == 'i' ? 'd' : t[j]);
            lit.emplace_back();
            i = j;
            continue;
        }
        lit.back() += t[i];   // (a lone % : itself)
    }
}

inline std::string unescape(const std::string& s) {
    std::string o;
    for (size_t i = 0; i < s.size(); i++) {
        if (s[i] == '\\' && i + 1 < s.size()) {
            const char n = s[++i];
            o += n == 'n' ? '\n' : n == 't' ? '\t' : n;
        } else
            o += s[i];
    }
    return o;
}

inline bool letter(unsigned char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c >= 0x80; }

inline void add(State& st, const std::string& en, const std::string& tr, bool whole) {
    std::vector<std::string> lit, tlit;
    std::vector<char> conv, tconv;
    split(en, lit, conv);
    split(tr, tlit, tconv);
    if (conv != tconv) return;   // (the translation fills in other things than the original: not used)
    if (conv.empty()) {
        st.en.push_back(lit[0]);
        st.tr.push_back(tlit[0]);
        st.whole.push_back(whole);
        return;
    }
    Pat p;
    p.lit = lit;
    p.conv = conv;
    p.tlit = tlit;
    for (const auto& l : lit) p.min_len += l.size();
    st.pats.push_back(std::move(p));
}

inline void finish(State& st) {
    size_t cap = 64;
    while (cap < st.en.size() * 2 + 2) cap <<= 1;
    st.table.assign(cap, 0);
    for (size_t i = 0; i < st.en.size(); i++) {
        size_t k = hash(st.en[i].data(), st.en[i].size()) & (cap - 1);
        while (st.table[k]) {
            if (st.en[st.table[k] - 1] == st.en[i]) break;   // (a repeated text: the first stays)
            k = (k + 1) & (cap - 1);
        }
        if (!st.table[k]) st.table[k] = (uint32_t)i + 1;
    }
    for (auto& v : st.pieces) v.clear();
    for (size_t i = 0; i < st.en.size(); i++) {
        const std::string& e = st.en[i];
        if (e.size() < 3 || st.tr[i] == e || st.whole[i]) continue;
        bool alpha = false;
        for (char c : e) alpha |= letter((unsigned char)c);
        if (alpha) st.pieces[(unsigned char)e[0]].push_back((int)i);
    }
    for (auto& v : st.pieces)
        std::sort(v.begin(), v.end(), [&](int a, int b) { return st.en[a].size() > st.en[b].size(); });
    st.ready = true;
}

/// Entries from a text: a line "original<TAB>translation", # starts a comment
inline void parse(State& st, const char* data, size_t n) {
    size_t i = 0;
    while (i < n) {
        size_t e = i;
        while (e < n && data[e] != '\n') e++;
        size_t end = e;
        if (end > i && data[end - 1] == '\r') end--;
        if (end > i && data[i] != '#') {
            const char* tab = (const char*)memchr(data + i, '\t', end - i);
            if (tab) {
                const char* tab2 = (const char*)memchr(tab + 1, '\t', data + end - (tab + 1));
                const bool whole = tab2 && tab2 + 1 < data + end && tab2[1] == 'x';
                const std::string en = unescape(std::string(data + i, tab)), tr = unescape(std::string(tab + 1, tab2 ? tab2 : data + end));
                if (!en.empty() && !tr.empty()) add(st, en, tr, whole);
            }
        }
        i = e + 1;
    }
}

inline const std::string* exact(const State& st, const char* s, size_t n) {
    if (st.table.empty()) return nullptr;
    const size_t cap = st.table.size();
    for (size_t k = hash(s, n) & (cap - 1); st.table[k]; k = (k + 1) & (cap - 1)) {
        const std::string& e = st.en[st.table[k] - 1];
        if (e.size() == n && !memcmp(e.data(), s, n)) return &st.tr[st.table[k] - 1];
    }
    return nullptr;
}

inline std::string translate(const State& st, const char* s, size_t n, int depth, bool* known);

/// Does text s[0, n) fit the pattern from piece k at pos; the captures in cap
inline bool match(const Pat& p, const char* s, size_t n, size_t pos, size_t k, std::vector<std::pair<size_t, size_t>>& cap) {
    const std::string& l = p.lit[k];
    if (pos + l.size() > n || memcmp(s + pos, l.data(), l.size())) return false;
    pos += l.size();
    if (k == p.conv.size()) return pos == n;
    const char cv = p.conv[k];
    size_t from = pos, to = pos;
    if (cv == 'd' || cv == 'u') {
        if (to < n && s[to] == '-' && cv == 'd') to++;
        const size_t d0 = to;
        while (to < n && s[to] >= '0' && s[to] <= '9') to++;
        if (to == d0) return false;
        cap.push_back({from, to});
        if (match(p, s, n, to, k + 1, cap)) return true;
        cap.pop_back();
        return false;
    }
    if (cv == 'f') {
        if (to < n && s[to] == '-') to++;
        const size_t d0 = to;
        while (to < n && ((s[to] >= '0' && s[to] <= '9') || s[to] == '.')) to++;
        if (to == d0) return false;
        cap.push_back({from, to});
        if (match(p, s, n, to, k + 1, cap)) return true;
        cap.pop_back();
        return false;
    }
    if (cv == 'c') {
        if (to >= n) return false;
        to++;
        while (to < n && ((unsigned char)s[to] & 0xC0) == 0x80) to++;
        cap.push_back({from, to});
        if (match(p, s, n, to, k + 1, cap)) return true;
        cap.pop_back();
        return false;
    }
    // (%s: the shortest that lets the rest fit)
    for (to = pos; to <= n; to++) {
        cap.push_back({from, to});
        if (match(p, s, n, to, k + 1, cap)) return true;
        cap.pop_back();
    }
    return false;
}

inline bool by_pattern(const State& st, const char* s, size_t n, int depth, std::string* out) {
    std::vector<std::pair<size_t, size_t>> cap;
    for (const Pat& p : st.pats) {
        if (n < p.min_len) continue;
        const std::string& l0 = p.lit[0];
        if (!l0.empty() && (n < l0.size() || memcmp(s, l0.data(), l0.size()))) continue;
        const std::string& ln = p.lit.back();
        if (!ln.empty() && (n < ln.size() || memcmp(s + n - ln.size(), ln.data(), ln.size()))) continue;
        cap.clear();
        if (!match(p, s, n, 0, 0, cap)) continue;
        std::string o;
        for (size_t k = 0; k < p.tlit.size(); k++) {
            o += p.tlit[k];
            if (k < cap.size()) {
                const std::string piece(s + cap[k].first, s + cap[k].second);
                if (p.conv[k] == 's' && depth < 4) o += translate(st, piece.data(), piece.size(), depth + 1, nullptr);
                else o += piece;
            }
        }
        *out = std::move(o);
        return true;
    }
    return false;
}

/// The known pieces in a text, each between non-letters, replaced; false when there is none
inline bool by_pieces(const State& st, const char* s, size_t n, std::string* out) {
    std::string o;
    bool any = false;
    size_t i = 0;
    while (i < n) {
        bool hit = false;
        if (i == 0 || !letter((unsigned char)s[i - 1]) || !letter((unsigned char)s[i])) {
            for (int idx : st.pieces[(unsigned char)s[i]]) {
                const std::string& e = st.en[idx];
                if (i + e.size() > n || memcmp(s + i, e.data(), e.size())) continue;
                if (letter((unsigned char)e.front()) && i > 0 && letter((unsigned char)s[i - 1])) continue;
                if (letter((unsigned char)e.back()) && i + e.size() < n && letter((unsigned char)s[i + e.size()])) continue;
                o += st.tr[idx];
                i += e.size();
                hit = any = true;
                break;
            }
        }
        if (!hit) o += s[i++];
    }
    if (any) *out = std::move(o);
    return any;
}

inline std::string translate(const State& st, const char* s, size_t n, int depth, bool* known) {
    if (known) *known = true;
    if (const std::string* t = exact(st, s, n)) return *t;
    std::string o;
    if (by_pattern(st, s, n, depth, &o)) return o;
    if (by_pieces(st, s, n, &o)) return o;
    if (known) *known = false;
    return std::string(s, n);
}

// ---- the state of the process ----
inline State& state() {
    static State st;   // (loaded once, then read only: the texts handed out stay where they are)
    return st;
}
inline std::atomic<int>& mode_ref() {
    static std::atomic<int> m{kAuto};
    return m;
}
inline std::string& dir_ref() {
    static std::string d;   // (the game's folder, with its separator at the end)
    return d;
}
inline std::string& system_ref() {
    static std::string d;   // (the language Windows is set to: "pt-BR", "en-US" ...)
    return d;
}
/// 0 not worked out, 1 English (nothing to do), 2 Portuguese
inline std::atomic<int>& active_ref() {
    static std::atomic<int> a{0};
    return a;
}
inline int& raw_depth() {
    static thread_local int d = 0;
    return d;
}

#include "vk_lang_pt_br.inc"

inline bool same_ascii(const char* a, const char* b, size_t n) {
    for (size_t i = 0; i < n; i++) {
        char x = a[i], y = b[i];
        if (!x || !y) return false;
        if (x >= 'A' && x <= 'Z') x += 32;
        if (y >= 'A' && y <= 'Z') y += 32;
        if (x != y) return false;
    }
    return true;
}

inline bool load_file(State& st, const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    std::string data;
    char buf[8192];
    size_t got;
    while ((got = fread(buf, 1, sizeof buf, f)) > 0) data.append(buf, got);
    fclose(f);
    if (data.size() >= 3 && (unsigned char)data[0] == 0xEF && (unsigned char)data[1] == 0xBB && (unsigned char)data[2] == 0xBF)
        data.erase(0, 3);
    parse(st, data.data(), data.size());
    return true;
}

inline void load_pt() {
    State& st = state();
    bool file = false;
    const std::string& d = dir_ref();
    if (!d.empty()) {
        for (const char* rel : {"lang/pt-BR.tsv", "../lang/pt-BR.tsv"}) {
            State test;
            if (load_file(test, d + rel) && (!test.en.empty() || !test.pats.empty())) {
                finish(test);
                st = std::move(test);
                st.loaded_from = d + rel;
                file = true;
                break;
            }
        }
    }
    if (!file) {
        parse(st, (const char*)kPtBr, sizeof kPtBr);
        finish(st);
        st.loaded_from = "built in";
    }
}

/// The language in force: 1 English, 2 Portuguese. The environment first (RX_VK_UI_LANG: en or pt-BR), then the menu's choice,
/// then Windows' own
inline int resolve() {
    int m = mode_ref().load();
    if (const char* e = getenv("RX_VK_UI_LANG")) {
        if (same_ascii(e, "en", 2)) m = kEnglish;
        else if (same_ascii(e, "pt", 2)) m = kPortuguese;
    }
    if (m == kAuto) {
        const std::string& s = system_ref();
        m = s.size() >= 2 && same_ascii(s.c_str(), "pt", 2) ? kPortuguese : kEnglish;
    }
    return m == kPortuguese ? 2 : 1;
}

inline void note_miss(const char* s, size_t n) {
    static std::mutex mu;
    static std::unordered_set<uint64_t> seen;
    int letters = 0, run = 0;
    bool wide = false;
    for (size_t i = 0; i < n; i++) {
        const unsigned char c = (unsigned char)s[i];
        wide |= c >= 0x80;
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')) letters = std::max(letters, ++run);
        else run = 0;
    }
    if (wide || letters < 3 || n > 600) return;   // (a text already in Portuguese, a number or a symbol: nothing to learn)
    std::lock_guard<std::mutex> lock(mu);
    if ((int)seen.size() >= kMissMax || !seen.insert(hash(s, n)).second) return;
    const std::string path = dir_ref() + "hookshot_ui_missing.txt";
    if (FILE* f = fopen(path.c_str(), "ab")) {
        fwrite(s, 1, n, f);
        fputc('\n', f);
        fclose(f);
    }
}

}  // namespace detail

/// Which language: kAuto (Windows' own), kEnglish, kPortuguese. The menu's row
inline void set_mode(int m) {
    detail::mode_ref().store(m);
    detail::active_ref().store(0);
}
/// The game's folder (with its separator at the end): a lang folder in it is read first, the missing list is written in it
inline void set_dir(const std::string& d) {
    detail::dir_ref() = d;
    detail::active_ref().store(0);
}
/// What Windows is set to ("pt-BR")
inline void set_system(const char* name) {
    detail::system_ref() = name ? name : "";
    detail::active_ref().store(0);
}
/// True when texts are turned into Portuguese
inline bool active() {
    int a = detail::active_ref().load();
    if (!a) {
        a = detail::resolve();
        if (a == 2) {
            static std::once_flag once;
            std::call_once(once, [] { detail::load_pt(); });
        }
        detail::active_ref().store(a);
    }
    return a == 2;
}

/// While one of these lives, texts are drawn as they are: they have been translated already (a text cut to fit a cell)
struct Raw {
    Raw() { detail::raw_depth()++; }
    ~Raw() { detail::raw_depth()--; }
    Raw(const Raw&) = delete;
    Raw& operator=(const Raw&) = delete;
};

/// A text in the language in force. The pointer holds until some hundred other texts have been asked for; the original's when
/// there is no translation
inline const char* tr(const char* s) {
    if (!s || !*s || detail::active_ref().load() == 1) return s;
    if (!active() || detail::raw_depth() > 0) return s;
    const detail::State& st = detail::state();
    const size_t n = strlen(s);
    if (const std::string* t = detail::exact(st, s, n)) return t->c_str();
    static thread_local detail::CacheSlot cache[detail::kCache];
    detail::CacheSlot& slot = cache[detail::hash(s, n) % detail::kCache];
    if (slot.used && slot.src.size() == n && !memcmp(slot.src.data(), s, n)) return slot.dst == slot.src ? s : slot.dst.c_str();
    bool known = false;
    std::string out = detail::translate(st, s, n, 0, &known);
    if (!known) detail::note_miss(s, n);
    slot.src.assign(s, n);
    slot.dst = std::move(out);
    slot.used = true;
    return slot.dst == slot.src ? s : slot.dst.c_str();
}
inline std::string tr(const std::string& s) { return tr(s.c_str()); }

}  // namespace mkwvk::lang
