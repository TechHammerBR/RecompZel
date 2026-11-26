/* (Hookshot native engine) The list of guest code an exeFS mod patches: see hl_patched.h. */
#include "hl_patched.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint64_t lo, hi;
    char mod[96];
} Span;
static Span *spans;
static int nspans, cap_spans;

static void add(uint64_t lo, uint64_t hi, const char *mod) {
    if (nspans == cap_spans) {
        Span *grown = (Span *)realloc(spans, sizeof *spans * (size_t)(cap_spans = cap_spans ? cap_spans * 2 : 64));
        if (!grown) return;
        spans = grown;
    }
    spans[nspans].lo = lo;
    spans[nspans].hi = hi;
    snprintf(spans[nspans].mod, sizeof spans[nspans].mod, "%s", mod);
    nspans++;
}

int hl_patched_parse(const char *text) {
    nspans = 0;
    if (!text) return 0;
    for (const char *line = text; *line;) {
        const char *end = strchr(line, '\n');
        const size_t n = end ? (size_t)(end - line) : strlen(line);
        char buf[512];
        snprintf(buf, sizeof buf, "%.*s", (int)(n < sizeof buf - 1 ? n : sizeof buf - 1), line);
        line += n + (end ? 1 : 0);
        size_t len = strlen(buf);
        while (len && (buf[len - 1] == '\r' || buf[len - 1] == ' ')) buf[--len] = 0;
        unsigned long long lo, hi;
        int at = 0;
        if (sscanf(buf, "function 0x%llx 0x%llx %n", &lo, &hi, &at) >= 2 && at) {
            add(lo, hi, buf + at);
        } else if (sscanf(buf, "range 0x%llx 0x%llx %n", &lo, &hi, &at) >= 2 && at) {
            const char *rest = strchr(buf + at, ' ');   /* (the module's name, then the mod's) */
            add(lo, hi, rest ? rest + 1 : buf + at);
        }
    }
    return nspans;
}

const char *hl_patched_mod(uint64_t guest) {
    for (int i = 0; i < nspans; i++)
        if (guest >= spans[i].lo && guest < spans[i].hi) return spans[i].mod;
    return NULL;
}

int hl_patched_left(uint64_t guest, const char *what, HlPatchedLog log) {
    const char *mod = hl_patched_mod(guest);
    if (!mod) return 0;
    if (log) {
        char line[320];
        snprintf(line, sizeof line, "hl: %s 0x%llx left to the lifted code: an exeFS mod patches it (mods/%s)", what,
                 (unsigned long long)guest, mod);
        log(line);
    }
    return 1;
}
