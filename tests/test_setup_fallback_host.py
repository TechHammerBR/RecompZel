"""The setup downloads from the server's own address when git.notrexed.dev gives no answer at all (builder/setup/setup.c
http_get). 2026-11-15: players kept seeing "The download server didn't answer (0)", through WARP and VPNs too: an antivirus's
web filter or a provider blocking notrexed.dev. The VPS serves the release files, the latest links and the API's latest release
on git.13.140.227.35.sslip.io itself, not through Cloudflare. Checked by source:

- every git.notrexed.dev request goes through http_get, which asks the same path on the other host when there was no answer
  (no status), and keeps asking it first for the rest of the run; an answer with an error status does not switch;
- no other code opens a connection itself (http_get_once is only called by http_get).

python -I -B tests/test_setup_fallback_host.py
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def body(text, head):
    start = text.index(head)
    depth, i = 0, text.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1]
        i += 1


def main():
    src = (ROOT / "builder/setup/setup.c").read_text(encoding="utf-8")
    assert 'static const char kMainHost[] = "https://git.notrexed.dev/";' in src
    assert 'static const char kFallbackHost[] = "https://git.13.140.227.35.sslip.io/";' in src
    get = body(src, "static int http_get(const char *url8")
    for need in ("if (strncmp(url8, kMainHost, main_n)) return http_get_once(url8, sink, user, expect, accept);",
                 'snprintf(other, sizeof other, "%s%s", kFallbackHost, url8 + main_n);',
                 "if (ok || g_http_status) return ok;", "g_fallback = !fallback;"):
        assert need in get, "http_get: " + need
    once = body(src, "static int http_get_once(")
    assert "g_http_error = 0, g_http_status = 0;" in once, "a request's status is its own"
    calls = [m.start() for m in re.finditer(r"\bhttp_get_once\(", src)]
    inside = [c for c in calls if src.index(get) <= c < src.index(get) + len(get)]
    assert len(calls) - len(inside) == 1, "http_get_once is only defined, and called from http_get"
    print("PASS: the setup falls back to the server's own address when git.notrexed.dev gives no answer")


if __name__ == "__main__":
    main()
