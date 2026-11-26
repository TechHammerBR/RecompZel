"""The host's memcpy, memmove, memset, memcmp, strlen and strcmp (host/nn_libc.c's ENTRY_HOOK_SYMs) are spliced at the entry
of the SDK's own functions (nx2/entry_hooks.py), do what the SDK's do, and mark what they write as the lifted stores do.

The hooks were defined but nothing in the lift called them. Checked here, with no game:

- The splice. A real a64_lift.Lifter over a made-up image (no translator): entry_hooks.add finds each hooked symbol where the
  sdk module defines it, and the emit starts that function's C with the hook's call, the rest of its text unchanged; a
  symbol another module defines, an HLE'd one, one that is no entry and one nobody defines are left out. The table goes to
  the emit's new processes (chunks.EMIT_TABLES), lift.py installs and adds it in the standalone lift, and the lift key
  names the hooks (a new one lifts again).
- What they do, built from host/nn_libc.c as it is (gcc, any OS) over a guest window, against a byte-at-a-time model of
  the SDK's functions as lifted code runs them: each byte stored through the soft write watch's own mark (nx2/rtgen.py's
  A64_MARK for the 64-bit window). Sizes 0 to 300 and across pages up to 12 KB, every alignment of source and destination
  mod 16, every overlap of a copy in both directions, memset's value as an int with high bits; memcmp and strcmp with the
  first difference at each place, bytes above 0x7f (an unsigned compare) and the result zero-extended in x0 as the SDK's
  w0 leaves it. After each call the window and the page marks are byte for byte the model's, and the marks are set after
  the data is in place (host/hos_mem.c's hos_mark_written, cut out as it is). Copies and fills over LIBC_PIECE (kept below
  the size where Windows' memmove stops caching what it writes) go in pieces with an interrupt poll between them, every
  overlap of a piece boundary both ways; memset under 8 bytes and memcmp under 16 are declined (nothing written or
  marked) and the spliced line tests the size before it calls.
- The spliced line in a function shaped like the lifted ones: the host does the call and the function returns; with
  HOS_GUEST_LIBC=1 every hook declines (nothing written, nothing marked) and the function's own code runs. The first call
  logs which of the two it is, once.

python -I -B tests/test_libc_hooks.py [--cc gcc]
"""
import argparse
import ast
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
sys.path.insert(0, str(ROOT / "nx2"))
from srccut import block  # noqa: E402
import kit  # noqa: E402,F401  (a64-kit on the path)
import a64_lift  # noqa: E402
import entry_hooks  # noqa: E402

ENV_ON_H = str(ROOT / "gpu" / "vk" / "compat" / "hookshot_env.h")
HOOKS = {"memcpy": 0, "memmove": 0, "memset": 8, "memcmp": 16, "strlen": 0, "strcmp": 0}   # (with their size gates)
CC = "gcc"

# ---- the splice ------------------------------------------------------------------------------------------------------

BASE = 0x80000000
SDK = BASE + 0x10000
RET = 0xd65f03c0
F_MEMCPY, F_STRCMP, F_MEMSET_MAIN, F_STRLEN, F_PLAIN = SDK + 0x100, SDK + 0x200, BASE + 0x300, SDK + 0x400, SDK + 0x500
NOT_ENTRY = SDK + 0x608   # (inside F_MEMMOVE_BODY: an address the lift has no function at)


def add_x0(n):
    return 0x91000000 | (n << 10)   # add x0, x0, #n


WORDS = {F_MEMCPY: add_x0(1), F_MEMCPY + 4: RET, F_STRCMP: add_x0(2), F_STRCMP + 4: RET,
         F_MEMSET_MAIN: add_x0(3), F_MEMSET_MAIN + 4: RET, F_PLAIN: add_x0(5), F_PLAIN + 4: RET,
         SDK + 0x600: add_x0(6), SDK + 0x604: add_x0(7), NOT_ENTRY: RET}


class Module:
    def __init__(self, name, base):
        self.name, self.base = name, base


class Image:
    """Three modules' worth of symbols: memcpy and strcmp the sdk's functions, memset main's own, strlen HLE'd, memmove
    defined in the middle of other code (no entry), memcmp nowhere"""
    def __init__(self):
        main, sdk = Module("main", BASE), Module("sdk", SDK)
        self.modules = [main, sdk]
        self.exports = {
            "memcpy": (sdk, {"value": F_MEMCPY - SDK, "type": "func"}),
            "strcmp": (sdk, {"value": F_STRCMP - SDK, "type": "func"}),
            "memset": (main, {"value": F_MEMSET_MAIN - BASE, "type": "func"}),
            "strlen": (sdk, {"value": F_STRLEN - SDK, "type": "func"}),
            "memmove": (sdk, {"value": NOT_ENTRY - SDK, "type": "func"}),
        }
        self.entries = {F_MEMCPY, F_STRCMP, F_MEMSET_MAIN, F_PLAIN, SDK + 0x600}
        self.hooks = {F_STRLEN: "imp_strlen"}
        self.names = {}

    def word(self, pc):
        return WORDS[pc]

    def in_code(self, pc):
        return pc in WORDS

    def read(self, pc, n):
        return b"".join(struct.pack("<I", WORDS[pc + 4 * i]) for i in range(n // 4))


def pydef(text, name):
    """The source of a top-level Python function"""
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


def texts():
    return {w: ("    c->x[0] += %d;" % ((w >> 10) & 0xFFF), 0) for w in WORDS.values() if (w >> 24) == 0x91}


class Splice(unittest.TestCase):
    def setUp(self):
        self.lifter = a64_lift.Lifter(Image())
        self.found = entry_hooks.add(self.lifter, self.lifter.img)
        self.lifter.discover()

    def test_the_hooks_host_defines(self):
        self.assertEqual(entry_hooks.hooks(), HOOKS)
        self.assertEqual(entry_hooks.hooked_symbols(), ["memcmp>=16", "memcpy", "memmove", "memset>=8", "strcmp", "strlen"])

    def test_a_gated_line(self):
        """memset under 8 bytes stays in the lifted code: the size is tested in the line, before any call"""
        text = entry_hooks.line("memset", 8)
        self.assertIn("if (c->x[2] >= 8ULL && entry_sym_memset(c)) return;", text)
        self.assertNotIn("c->x[2]", entry_hooks.line("memcpy"))

    def test_pieces_below_the_non_temporal_size(self):
        """Windows' memmove stores past the cache from about 1.75 MB (measured): a copy goes in pieces well below it"""
        src = (ROOT / "host" / "nn_libc.c").read_text(encoding="utf-8")
        m = re.search(r"#define LIBC_PIECE \((\d+)u << (\d+)\)", src)
        self.assertIsNotNone(m, "host/nn_libc.c: no LIBC_PIECE")
        self.assertLessEqual(int(m.group(1)) << int(m.group(2)), 1 << 20)

    def test_found_in_the_sdk_only(self):
        self.assertEqual(self.found, {"memcpy": F_MEMCPY, "strcmp": F_STRCMP})
        self.assertEqual(sorted(self.lifter.entry_hooks), [F_MEMCPY, F_STRCMP])
        self.assertTrue({F_MEMCPY, F_STRCMP} <= self.lifter.no_local)   # (the arguments are read from the context)
        self.assertNotIn(F_MEMSET_MAIN, self.lifter.no_local)

    def test_the_function_starts_with_its_hook(self):
        for e, sym in ((F_MEMCPY, "memcpy"), (F_STRCMP, "strcmp")):
            text = a64_lift.Lifter.emit_function(self.lifter, e, texts())[0]
            plain = BASE_EMIT(self.lifter, e, texts())[0]
            lines = text.splitlines()
            self.assertEqual(lines[0], "void f_%08x(Ctx *__restrict A64_NOESC c) {" % e)
            self.assertEqual(lines[1], entry_hooks.line(sym))
            self.assertIn("if (entry_sym_%s(c)) return;" % sym, lines[1])
            self.assertEqual([lines[0]] + lines[2:], plain.splitlines())   # (the lifted function kept behind it, as it was)
        self.assertEqual(self.lifter.stats["entry_hooks"], 2)

    def test_others_unchanged(self):
        for e in (F_MEMSET_MAIN, F_PLAIN):
            self.assertEqual(a64_lift.Lifter.emit_function(self.lifter, e, texts()), BASE_EMIT(self.lifter, e, texts()))
            self.assertNotIn("entry_sym_", a64_lift.Lifter.emit_function(self.lifter, e, texts())[0])

    def test_sent_to_the_emit_processes(self):
        import chunks
        self.assertIn("entry_hooks", chunks.EMIT_TABLES)

    def test_the_lift_splices_them(self):
        lift = (ROOT / "nx2" / "lift.py").read_text(encoding="utf-8")
        tree = ast.parse(lift)
        top = [ast.unparse(n) for n in tree.body if isinstance(n, ast.Expr)]
        self.assertIn("entry_hooks.install()", top)   # (at module level: the emit's new processes run it too)
        self.assertLess(top.index("lift_fixes.install()"), top.index("entry_hooks.install()"))
        main = pydef(lift, "main")
        self.assertIn("entry_hooks.add(L, img)", main)
        self.assertLess(main.index("L = a64_lift.Lifter(img)"), main.index("entry_hooks.add(L, img)"))
        self.assertLess(main.index("entry_hooks.add(L, img)"), main.index("discover.discover(L,"))   # (the discovery's walks)
        key = pydef((ROOT / "nx2" / "make_game.py").read_text(encoding="utf-8"), "lift_key")
        self.assertIn("entry_hooks.hooked_symbols()", key)


BASE_EMIT = a64_lift.Lifter.emit_function   # (before the wrap: a64-kit's own)
entry_hooks.install()                       # (as nx2/lift.py does at its start)


# ---- what the hooks do -----------------------------------------------------------------------------------------------

def mark_macro():
    """nx2/rtgen.py's A64_MARK for the 64-bit window: what every lifted store marks"""
    tree = ast.parse((ROOT / "nx2" / "rtgen.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "MARK_NATIVE_64" for t in node.targets):
            return node.value.value
    raise SystemExit("FAIL: nx2/rtgen.py has no MARK_NATIVE_64")


HOS_H = r'''
#pragma once
#include <stdint.h>
#include <stddef.h>
#define A64_NOESC
typedef struct { uint64_t x[32]; } Ctx;
#define WINDOW 0x400000ull         /* (a 4 MB guest window) */
extern uint8_t *A64_MEM;
#define A64_PTR(a) (A64_MEM + (uint64_t)(a))
#define A64_DIRTY_PAGES (WINDOW >> 12)
#define HOS_GUEST_SPACE WINDOW
#define HOS_SPACE_END WINDOW
@MARK@
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
#define GP(a) ((void *)A64_PTR(a))
#define ENTRY_HOOK_SYM(sym) int entry_sym_##sym(Ctx *c)
#define ENTRY_HOOK_SYM_FROM(sym, min) int entry_sym_##sym(Ctx *c)
extern long polls;
#define A64_POLL(c) ((void)(c), polls++)
void hos_log(const char *fmt, ...);
typedef struct HleCount { const char *name; long calls; } HleCount;   /* (host/hos.h's, HOS_HLE_STATS) */
static int hos_hle_stats = 1;
static inline void hos_hle_counted(HleCount *h, void (*fn)(Ctx *c), Ctx *c) { h->calls++; fn(c); }
void written(const void *p, size_t n);
#define HOS_WRITTEN(p, n) written((p), (n))
static inline void *hos_guest_range(uint64_t a, uint64_t n) { return a < WINDOW && n <= WINDOW - a ? GP(a) : (void *)0; }
'''

FIXTURE = r'''
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hos.h"
uint8_t *A64_MEM;
uint8_t a64_dirty[A64_DIRTY_PAGES];
long polls;
@MARK_WRITTEN@
#include "nn_libc.c"

static int logs;
static char logged[256];
void hos_log(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(logged, sizeof logged, fmt, ap);
    va_end(ap);
    logs++;
}
/* HOS_WRITTEN: the data must be in place when the marks go up (the GPU mirror's scan may run in between) */
static const uint8_t *want;   /* (the model's window after the call) */
static long writes, early;
void written(const void *p, size_t n) {
    const size_t at = (size_t)((const uint8_t *)p - A64_MEM);
    writes++;
    if (want && memcmp(A64_MEM + at, want + at, n)) early++;
    hos_mark_written(p, n);
}

#define FAIL(...) do { fprintf(stderr, "FAIL: " __VA_ARGS__); fprintf(stderr, "\n"); exit(1); } while (0)

/* ---- the model: the SDK's functions a byte at a time, each store marking its page as a lifted store does */
static void st8(uint64_t a, uint8_t v) { *A64_PTR(a) = v; A64_MARK(a, 1); }
static uint64_t m_copy(uint64_t d, uint64_t s, uint64_t n) {   /* (memcpy is the SDK's memmove-safe copy; memmove) */
    if (d <= s) for (uint64_t i = 0; i < n; i++) st8(d + i, *A64_PTR(s + i));
    else for (uint64_t i = n; i--;) st8(d + i, *A64_PTR(s + i));
    return d;
}
static uint64_t m_set(uint64_t d, uint64_t v, uint64_t n) { for (uint64_t i = 0; i < n; i++) st8(d + i, (uint8_t)v); return d; }
static uint64_t m_cmp(uint64_t a, uint64_t b, uint64_t n) {
    for (uint64_t i = 0; i < n; i++)
        if (*A64_PTR(a + i) != *A64_PTR(b + i)) return (uint32_t)((int)*A64_PTR(a + i) - (int)*A64_PTR(b + i));
    return 0;
}
static uint64_t m_len(uint64_t a) { uint64_t n = 0; while (*A64_PTR(a + n)) n++; return n; }
static uint64_t m_strcmp(uint64_t a, uint64_t b) {
    uint64_t i = 0;
    while (*A64_PTR(a + i) && *A64_PTR(a + i) == *A64_PTR(b + i)) i++;
    return (uint32_t)((int)*A64_PTR(a + i) - (int)*A64_PTR(b + i));
}

enum { MEMCPY, MEMMOVE, MEMSET, MEMCMP, STRLEN, STRCMP };
static const char *const NAME[] = {"memcpy", "memmove", "memset", "memcmp", "strlen", "strcmp"};
static int (*const HOOK[])(Ctx *) = {entry_sym_memcpy, entry_sym_memmove, entry_sym_memset, entry_sym_memcmp, entry_sym_strlen,
                                     entry_sym_strcmp};
static uint8_t *before, *after_model, dirty_model[A64_DIRTY_PAGES];
static long cases;

/* One call: the hook on the window as it is, against the model on a copy of it. The window, its marks and x0 must match.
   (The bytes compared are the destination's with 64 around it; every 512th call, the whole window) */
static int gated(int f, uint64_t n) { return (f == MEMSET && n < @MEMSET_MIN@) || (f == MEMCMP && n < @MEMCMP_MIN@); }
static long gated_calls;
static void one(int f, uint64_t a0, uint64_t a1, uint64_t a2) {
    uint64_t lo = 0, hi = 0;
    if (cases % 8192 == 0) hi = WINDOW;
    else if (f <= MEMSET) lo = a0 < 64 ? 0 : a0 - 64, hi = a0 + a2 + 64 > WINDOW ? WINDOW : a0 + a2 + 64;
    memcpy(before + lo, A64_MEM + lo, hi - lo);
    memset(a64_dirty, 0, sizeof a64_dirty);
    uint64_t r;
    switch (f) {
    case MEMCPY: case MEMMOVE: r = m_copy(a0, a1, a2); break;
    case MEMSET: r = m_set(a0, a1, a2); break;
    case MEMCMP: r = m_cmp(a0, a1, a2); break;
    case STRLEN: r = m_len(a0); break;
    default: r = m_strcmp(a0, a1); break;
    }
    memcpy(after_model + lo, A64_MEM + lo, hi - lo);
    memcpy(dirty_model, a64_dirty, sizeof a64_dirty);
    memcpy(A64_MEM + lo, before + lo, hi - lo);
    memset(a64_dirty, 0, sizeof a64_dirty);
    Ctx c;
    for (int i = 0; i < 32; i++) c.x[i] = 0x5a5a5a5a00000000ull | (uint64_t)i;
    c.x[0] = a0, c.x[1] = a1, c.x[2] = a2;
    if (gated(f, a2)) {   /* (under its size gate: declined, the SDK's own code runs; nothing written or marked) */
        if (HOOK[f](&c) != 0) FAIL("%s(%#llx, %#llx, %#llx): taken under its gate", NAME[f], (unsigned long long)a0, (unsigned long long)a1,
                                   (unsigned long long)a2);
        if (c.x[0] != a0 || c.x[1] != a1 || c.x[2] != a2) FAIL("%s: declined, but changed the arguments", NAME[f]);
        if (memcmp(A64_MEM + lo, before + lo, hi - lo)) FAIL("%s: declined, but wrote", NAME[f]);
        for (uint64_t p = 0; p < A64_DIRTY_PAGES; p++)
            if (a64_dirty[p]) FAIL("%s: declined, but marked", NAME[f]);
        gated_calls++, cases++;
        return;
    }
    want = after_model;
    const long early0 = early, polls0 = polls;
    if (HOOK[f](&c) != 1) FAIL("%s(%#llx, %#llx, %#llx) declined", NAME[f], (unsigned long long)a0, (unsigned long long)a1, (unsigned long long)a2);
    want = 0;
    /* (a copy or a fill over LIBC_PIECE goes in pieces, with the lifted loop's interrupt poll between them) */
    const long want_polls = f <= MEMSET && a2 > LIBC_PIECE ? (long)((a2 + LIBC_PIECE - 1) / LIBC_PIECE) - 1 : 0;
    if (polls - polls0 != want_polls) FAIL("%s(%#llx, %#llx, %#llx): %ld polls, %ld expected", NAME[f], (unsigned long long)a0,
                                           (unsigned long long)a1, (unsigned long long)a2, polls - polls0, want_polls);
    if (c.x[0] != r) FAIL("%s(%#llx, %#llx, %#llx): x0 %#llx, the SDK's %#llx", NAME[f], (unsigned long long)a0, (unsigned long long)a1,
                          (unsigned long long)a2, (unsigned long long)c.x[0], (unsigned long long)r);
    for (int i = 1; i < 32; i++)
        if (c.x[i] != (i <= 2 ? (i == 1 ? a1 : a2) : (0x5a5a5a5a00000000ull | (uint64_t)i))) FAIL("%s: x%d changed", NAME[f], i);
    if (memcmp(A64_MEM + lo, after_model + lo, hi - lo)) {
        size_t i = lo;
        while (A64_MEM[i] == after_model[i]) i++;
        FAIL("%s(%#llx, %#llx, %#llx): guest byte %#zx is %02x, the SDK's %02x", NAME[f], (unsigned long long)a0, (unsigned long long)a1,
             (unsigned long long)a2, i, A64_MEM[i], after_model[i]);
    }
    if (memcmp(a64_dirty, dirty_model, sizeof a64_dirty)) {
        size_t p = 0;
        while (a64_dirty[p] == dirty_model[p]) p++;
        FAIL("%s(%#llx, %#llx, %#llx): page %#zx marked %d, the lifted stores' %d", NAME[f], (unsigned long long)a0,
             (unsigned long long)a1, (unsigned long long)a2, p, a64_dirty[p], dirty_model[p]);
    }
    if (early != early0) FAIL("%s(%#llx, %#llx, %#llx): marked before its data was written", NAME[f], (unsigned long long)a0,
                              (unsigned long long)a1, (unsigned long long)a2);
    cases++;
}

static uint32_t seed = 12345;
static uint8_t rnd(void) { seed = seed * 1103515245u + 12345u; return (uint8_t)(seed >> 16); }
static void fill(void) { for (uint64_t i = 0; i < WINDOW; i++) A64_MEM[i] = rnd(); }

static const uint64_t BIG[] = {511, 512, 513, 1023, 4095, 4096, 4097, 8191, 8193, 12293};

static void copies(void) {
    const uint64_t page = 0x3000;   /* (copies placed across 4 KB page boundaries) */
    for (int f = MEMCPY; f <= MEMMOVE; f++) {
        for (uint64_t n = 0; n <= 300; n++)
            for (uint64_t sa = 0; sa < 16; sa++)
                for (uint64_t da = 0; da < 16; da++)
                    one(f, page - 37 + da + 0x10000, page - 150 + sa, n);
        for (uint64_t n = 0; n <= 300; n += (n < 40 ? 1 : 7))   /* every overlap, both ways, and the copy onto itself */
            for (int64_t d = -(int64_t)n - 2; d <= (int64_t)n + 2; d++)
                one(f, page + 0x2000 + d, page + 0x2000, n);
        for (size_t k = 0; k < sizeof BIG / sizeof BIG[0]; k++)
            for (int64_t d = -(int64_t)BIG[k] - 1; d <= (int64_t)BIG[k] + 1; d += (int64_t)BIG[k] / 3 + 1) {
                one(f, 0x20000 + 3 + d, 0x20000, BIG[k]);
                one(f, 0x8000 + 5, 0x30000 + 11, BIG[k]);
            }
    }
}

/* over LIBC_PIECE: in pieces, every overlap of a piece boundary, both ways */
static void pieces(void) {
    const uint64_t P = LIBC_PIECE, s = 0x100000 + 3;
    const uint64_t sizes[] = {P - 1, P, P + 1, 2 * P + 5, 3 * P - 1};
    for (size_t i = 0; i < sizeof sizes / sizeof sizes[0]; i++) {
        const uint64_t n = sizes[i];
        const int64_t d[] = {0, 1, -1, 8, -8, 4096, -4096, (int64_t)P - 1, -(int64_t)P + 1, (int64_t)P, -(int64_t)P, (int64_t)P + 1,
                             -(int64_t)P - 1, (int64_t)n - 1, -(int64_t)n + 1, (int64_t)n, -(int64_t)n, (int64_t)n + 77};
        for (int f = MEMCPY; f <= MEMMOVE; f++)
            for (size_t k = 0; k < sizeof d / sizeof d[0]; k++) one(f, s + d[k], s, n);
        one(MEMSET, s + 5, 0xa5, n);
        cases = (cases + 8191) / 8192 * 8192;   /* (the next call compares the whole window) */
        one(MEMSET, 0x200001, 0x3c, n);
    }
}

static void sets(void) {
    static const uint64_t value[] = {0, 0x41, 0x80, 0xff, 0x1ab, 0xffffffffffffff00ull, 0x7fffffff};
    for (uint64_t n = 0; n <= 300; n++)
        for (uint64_t da = 0; da < 16; da++)
            for (size_t v = 0; v < sizeof value / sizeof value[0]; v++) one(MEMSET, 0x2000 - 60 + da, value[v], n);
    for (size_t k = 0; k < sizeof BIG / sizeof BIG[0]; k++) one(MEMSET, 0x5000 - 7, 0x33, BIG[k]), one(MEMSET, 0x9000, 0, BIG[k]);
}

static void compares(void) {
    const uint64_t a = 0x4000 - 40, b0 = 0x24000 - 33;
    for (uint64_t al = 0; al < 16; al++) {
        const uint64_t b = b0 + al;
        for (uint64_t n = 0; n <= 300; n += (n < 64 ? 1 : 13)) {
            memcpy(A64_PTR(b), A64_PTR(a), n + 1);
            one(MEMCMP, a, b, n);                                        /* equal */
            for (uint64_t k = 0; k < n; k += (n < 64 ? 1 : 5)) {
                static const uint8_t d[] = {1, 0x7f, 0x80, 0xff};
                for (size_t j = 0; j < sizeof d; j++) {
                    const uint8_t was = *A64_PTR(b + k);
                    *A64_PTR(b + k) = (uint8_t)(was + d[j]);            /* the first difference at k, either sign */
                    one(MEMCMP, a, b, n);
                    one(MEMCMP, b, a, n);
                    one(MEMCMP, a, b, k);                                /* before the difference: equal */
                    *A64_PTR(b + k) = was;
                }
            }
        }
    }
    for (size_t k = 0; k < sizeof BIG / sizeof BIG[0]; k++) {
        memcpy(A64_PTR(b0), A64_PTR(a), BIG[k]);
        one(MEMCMP, a, b0, BIG[k]);
        *A64_PTR(b0 + BIG[k] - 1) ^= 0x80;
        one(MEMCMP, a, b0, BIG[k]);
    }
}

static void strings(void) {
    for (uint64_t al = 0; al < 16; al++)
        for (uint64_t n = 0; n <= 300; n++) {
            const uint64_t s = 0x6000 - 100 + al, t = 0x26000 - 77 + al * 3;
            for (uint64_t i = 0; i < n; i++) *A64_PTR(s + i) = (uint8_t)(1 + rnd() % 255);
            *A64_PTR(s + n) = 0;
            one(STRLEN, s, 0, 0);
            memcpy(A64_PTR(t), A64_PTR(s), n + 1);
            one(STRCMP, s, t, 0);                                         /* equal */
            for (uint64_t k = 0; k <= n; k += (n < 32 ? 1 : 9)) {
                const uint8_t was = *A64_PTR(t + k);
                static const uint8_t to[] = {0, 1, 0x7f, 0x80, 0xff};
                for (size_t j = 0; j < sizeof to; j++) {
                    if (to[j] == was) continue;
                    *A64_PTR(t + k) = to[j];                               /* differs at k, or ends early there */
                    one(STRCMP, s, t, 0);
                    one(STRCMP, t, s, 0);
                }
                *A64_PTR(t + k) = was;
            }
        }
    for (size_t k = 0; k < sizeof BIG / sizeof BIG[0]; k++) {   /* across pages */
        memset(A64_PTR(0x10000 - 5), 'x', BIG[k]);
        *A64_PTR(0x10000 - 5 + BIG[k]) = 0;
        one(STRLEN, 0x10000 - 5, 0, 0);
        memcpy(A64_PTR(0x31000 + 1), A64_PTR(0x10000 - 5), BIG[k] + 1);
        one(STRCMP, 0x10000 - 5, 0x31000 + 1, 0);
    }
}

/* the line nx2/entry_hooks.py splices, in a function shaped as the lifted ones */
@SPLICED@

int main(int argc, char **argv) {
    const int guest = argc > 1 && !strcmp(argv[1], "guest");
    A64_MEM = malloc(WINDOW), before = malloc(WINDOW), after_model = malloc(WINDOW);
    if (!A64_MEM || !before || !after_model) FAIL("no memory");
    fill();
    Ctx c = {{0}};
    c.x[0] = 0x200, c.x[1] = 0x1000, c.x[2] = 64;
    f_memcpy_shaped(&c);
    if (logs != 1) FAIL("the first call logged %d lines", logs);
    if (!strstr(logged, guest ? "HOS_GUEST_LIBC=1: memcpy, memmove, memset, memcmp, strlen and strcmp are the game's own"
                              : "memcpy, memmove, memset, memcmp, strlen and strcmp are the host's")) FAIL("logged: %s", logged);
    if (guest) {
        /* every hook declines: the lifted function runs, and the host wrote and marked nothing */
        if (c.x[0] != 0xdeadbeef) FAIL("HOS_GUEST_LIBC=1: the lifted memcpy did not run");
        memcpy(before, A64_MEM, WINDOW);
        for (int f = MEMCPY; f <= STRCMP; f++) {
            Ctx d = {{0}};
            d.x[0] = 0x100, d.x[1] = f == MEMSET ? 0x41 : 0x8000, d.x[2] = 32;
            if (HOOK[f](&d) != 0) FAIL("HOS_GUEST_LIBC=1: %s took the call", NAME[f]);
            if (d.x[0] != 0x100) FAIL("HOS_GUEST_LIBC=1: %s set x0", NAME[f]);
        }
        if (memcmp(before, A64_MEM, WINDOW) || writes) FAIL("HOS_GUEST_LIBC=1: the host wrote guest memory");
        for (uint64_t p = 0; p < A64_DIRTY_PAGES; p++)
            if (a64_dirty[p]) FAIL("HOS_GUEST_LIBC=1: page %#llx marked", (unsigned long long)p);
        if (logs != 1) FAIL("logged again");
        printf("PASS: HOS_GUEST_LIBC=1: every hook declines, writes and marks nothing; the lifted function runs; logged once\n");
        return 0;
    }
    if (c.x[0] != 0x200 || memcmp(A64_MEM + 0x200, A64_MEM + 0x1000, 64)) FAIL("the spliced memcpy did not copy, or ran its lifted code");
    /* past the guest window: the game's own copy, the host touches nothing */
    memcpy(before, A64_MEM, WINDOW);
    memset(a64_dirty, 0, sizeof a64_dirty);
    const uint64_t out[][3] = {{WINDOW - 8, 0x100, 64}, {0x100, WINDOW - 8, 64}, {~0ull - 4, 0x100, 16}, {0x100, WINDOW, 1}};
    for (size_t i = 0; i < sizeof out / sizeof out[0]; i++)
        for (int f = MEMCPY; f <= MEMSET; f++) {
            Ctx d = {{0}};
            d.x[0] = out[i][0], d.x[1] = f == MEMSET ? 0 : out[i][1], d.x[2] = out[i][2];
            if (f == MEMSET && out[i][0] == 0x100) continue;   /* (memset has no source) */
            if (HOOK[f](&d) != 0) FAIL("%s(%#llx, %#llx, %llu) past the window: taken", NAME[f], (unsigned long long)d.x[0],
                                       (unsigned long long)d.x[1], (unsigned long long)d.x[2]);
        }
    if (memcmp(before, A64_MEM, WINDOW)) FAIL("a call past the window wrote guest memory");
    for (uint64_t p = 0; p < A64_DIRTY_PAGES; p++)
        if (a64_dirty[p]) FAIL("a call past the window marked page %#llx", (unsigned long long)p);
    copies();
    pieces();
    sets();
    compares();
    strings();
    if (logs != 1) FAIL("logged %d times", logs);
    if (polls == 0 || gated_calls == 0) FAIL("no pieces, or no call under a gate");
    /* the gated line: memset under its gate runs the lifted body, from it the host's */
    Ctx g = {{0}};
    g.x[0] = 0x300, g.x[1] = 0x11, g.x[2] = @MEMSET_MIN@ - 1;
    f_memset_shaped(&g);
    if (g.x[0] != 0xdeadbeef) FAIL("the gated memset line called the host under its gate");
    g.x[0] = 0x300, g.x[1] = 0x11, g.x[2] = @MEMSET_MIN@;
    f_memset_shaped(&g);
    if (g.x[0] != 0x300 || A64_MEM[0x300 + @MEMSET_MIN@ - 1] != 0x11) FAIL("the gated memset line did not call the host at its gate");
    printf("PASS: %ld calls (%ld under a size gate, %ld interrupt polls between pieces): the window, x0 and the page marks are the SDK's lifted functions' (marks after the data, %ld marked "
           "writes); past the window the game's own; logged once\n", cases, gated_calls, polls, writes);
    return 0;
}
'''

SPLICED = r'''void f_memcpy_shaped(Ctx *__restrict A64_NOESC c) {
@LINE@
    c->x[0] = 0xdeadbeef;   /* (stands for the lifted body) */
}
void f_memset_shaped(Ctx *__restrict A64_NOESC c) {
@LINE_MEMSET@
    c->x[0] = 0xdeadbeef;
}'''


def run_fixture(cc):
    hos_mem = (ROOT / "host" / "hos_mem.c").read_text(encoding="utf-8")
    mark = block(hos_mem, "void hos_mark_written(const void *p, size_t n) {")
    with tempfile.TemporaryDirectory(prefix="libc-hooks-") as tmp:
        tmp = Path(tmp)
        (tmp / "hos.h").write_text(HOS_H.replace("@MARK@", mark_macro()), encoding="utf-8")
        gates = entry_hooks.hooks()
        spliced = SPLICED.replace("@LINE@", entry_hooks.line("memcpy")).replace("@LINE_MEMSET@", entry_hooks.line("memset", gates["memset"]))
        fixture = FIXTURE.replace("@MARK_WRITTEN@", mark).replace("@SPLICED@", spliced)
        fixture = fixture.replace("@MEMSET_MIN@", str(gates["memset"])).replace("@MEMCMP_MIN@", str(gates["memcmp"]))
        (tmp / "fixture.c").write_text(fixture, encoding="utf-8")
        # (beside the stand-in hos.h: an include in quotes looks in the including file's folder first)
        (tmp / "nn_libc.c").write_text((ROOT / "host" / "nn_libc.c").read_text(encoding="utf-8"), encoding="utf-8")
        exe = tmp / ("fixture.exe" if os.name == "nt" else "fixture")
        subprocess.run([cc, "-std=gnu11", "-O1", "-include", ENV_ON_H, "-Wall", "-Wextra", "-Werror", "-I", str(tmp),
                        str(tmp / "fixture.c"), "-o", str(exe)], check=True)
        env = {k: v for k, v in os.environ.items() if k != "HOS_GUEST_LIBC"}
        subprocess.run([str(exe)], check=True, env=env)
        subprocess.run([str(exe), "guest"], check=True, env=dict(env, HOS_GUEST_LIBC="1"))


class Hooks(unittest.TestCase):
    def test_against_the_sdk(self):
        run_fixture(CC)


def main():
    global CC
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a, rest = p.parse_known_args()
    CC = a.cc
    unittest.main(argv=[sys.argv[0]] + rest, verbosity=1)


if __name__ == "__main__":
    main()
