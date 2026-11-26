"""The setup takes files the player downloaded with a browser (builder/setup/setup.c browser_file), for players whose setup
could not reach git.notrexed.dev while a browser could (2026-11-15: "not able to connect, even with WARP or a VPN"). Checked by
source here (an end-to-end run, the list's and a part's links unreachable, installed v2.3.1 from the saved files on
2026-11-15):

- the list: hookshot-setup.txt from the player's Downloads or beside the setup, read when the server did not answer, the
  server then asked once instead of eight times;
- a part: its link's own file name there, copied in only when its SHA-256 is the list's;
- of the two places the newest copy (an old list left in Downloads is not taken over a fresh one);
- both connection failures name the manual page that lists the links.

python -I -B tests/test_setup_browser_files.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    src = (ROOT / "builder/setup/setup.c").read_text(encoding="utf-8")
    find = block(src, "static int browser_file(const char *name, wchar_t *out) {")
    for need in ("SHGetKnownFolderPath(&downloads_id", "GetModuleFileNameW(NULL, dirs[n], MAX_PATH)",
                 "CompareFileTime(&d.ftLastWriteTime, &best) > 0", 'L"%ls\\\\%ls"'):
        assert need in find, "browser_file: " + need
    assert '#define MANUAL_PAGE L"https://hookshot.notrexed.dev/manual"' in src
    assert 'int have_saved = browser_file("hookshot-setup.txt", saved_list);' in src and '7ull * 24 * 3600 * 10000000ull) have_saved = 0;' in src
    assert "attempt < (have_saved ? 1 : TRIES)" in src
    assert "if (!ok && have_saved) {" in src and "ok = read_whole(saved_list, &man);" in src
    part = src[src.index("/* (a part the player saved with a browser"):]
    part = part[:part.index("wchar_t part[MAX_PATH];")]
    assert "browser_file(link_name(p->url), saved) && file_sha256(saved, saved_sha) && !strcmp(saved_sha, p->sha)" in part
    assert src.count("L\" with your browser into your Downloads folder") == 3 and src.count("\" MANUAL_PAGE L\"") == 3
    # (and a failure with no answer at all says why, in Windows' words and number: net_why; IPv4 tried at once when IPv6 hangs)
    assert src.count("net_why(g_http_error), g_http_error);") == 2
    assert "WinHttpSetOption(s, WINHTTP_OPTION_IPV6_FAST_FALLBACK, &fast, sizeof fast);" in src
    print("PASS: the setup takes a list and parts the player saved with a browser, the newest copy, parts checked by SHA-256")


if __name__ == "__main__":
    main()
