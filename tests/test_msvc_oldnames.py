"""Windows link defaults: oldnames.lib is no longer a default library (issue 439).

Run with: python -I tests/test_msvc_oldnames.py
"""
import importlib.util
import os
from pathlib import Path
import re
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / "third_party" / "a64-kit" / "tools" / "toolchain.py"
spec = importlib.util.spec_from_file_location("toolchain_under_test", TOOLCHAIN)
toolchain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolchain)

# The legacy names the prebuilt static FFmpeg libraries still reference (avutil's log.o/file.o,
# avcodec's and avutil's file_open.o).
ALIASES = ("close", "fdopen", "isatty", "tempnam")
# Legacy names of the C runtime that only oldnames.lib gave the MSVC target (its own are the same with an underscore). The
# host's code may call them only where the Windows build doesn't compile it. Names a file is likely to give a function of
# its own (open, read, write, close) are left out: this is a net for the usual slips, not the whole list.
LEGACY = ("strdup", "wcsdup", "stricmp", "strnicmp", "strcmpi", "memicmp", "strlwr", "strupr", "itoa", "ltoa", "ultoa",
          "fdopen", "fileno", "isatty", "tempnam", "getcwd", "chdir", "rmdir", "unlink", "putenv", "getpid", "dup2", "lseek")
OTHER_SYSTEMS = ("__linux__", "__APPLE__", "__EMSCRIPTEN__", "__unix__", "__ANDROID__")


def code_only(text):
    """The source with its comments and string literals blanked, line numbers kept."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', blank, text, flags=re.S)


def windows_calls(text, names):
    """(line, name) of each call of one of names that the Windows build compiles: not under #ifndef _WIN32, the #else of
    an #ifdef _WIN32 chain, or a section for another system. A name the file #defines for itself is its own."""
    own = set(re.findall(r"^[ \t]*#[ \t]*define[ \t]+(\w+)", text, re.M))
    call = re.compile(r"(?<![\w.>])(%s)\s*\(" % "|".join(n for n in names if n not in own))
    stack, found = [], []   # (each open #if: [this branch is not Windows', a branch of the chain was Windows'])
    for number, line in enumerate(code_only(text).split("\n"), 1):
        m = re.match(r"\s*#\s*(ifdef|ifndef|if|elif|else|endif)\b(.*)", line)
        if m:
            word, rest = m.group(1), m.group(2)
            win = "_WIN32" in rest or "_MSC_VER" in rest
            negated = word == "ifndef" or bool(re.search(r"!\s*defined\s*\(?\s*_(WIN32|MSC_VER)", rest))
            other = any(o in rest for o in OTHER_SYSTEMS) and "!" not in rest and "||" not in rest
            if word in ("ifdef", "ifndef", "if"):
                stack.append([(win and negated) or (other and word != "ifndef"), win and not negated])
            elif word == "elif" and stack:
                was_win = stack[-1][1]
                stack[-1] = [(win and negated) or other or (was_win and not win), was_win or (win and not negated)]
            elif word == "else" and stack:
                not_win, was_win = stack[-1]
                stack[-1] = [was_win and not not_win, was_win or not_win]
            elif word == "endif" and stack:
                stack.pop()
            continue
        if any(frame[0] for frame in stack):
            continue
        for hit in call.finditer(line):
            found.append((number, hit.group(1)))
    return found


class MsvcLinkTests(unittest.TestCase):
    def test_msvc_link_does_not_ask_for_oldnames(self):
        fake_os = types.SimpleNamespace(name="nt", path=os.path, environ=os.environ)
        with mock.patch.object(toolchain, "os", fake_os), \
                mock.patch.dict(os.environ, {"HOOKSHOT_MINGW": ""}), \
                mock.patch.object(toolchain, "lld_link", return_value=r"C:\emSDK\lld-link.exe"):
            link = toolchain.native_link()
        self.assertEqual(link[0], "-fuse-ld=lld")
        self.assertIn("-Wl,/nodefaultlib:oldnames", link)

    def test_mingw_link_keeps_suppressing_msvc_default_libraries(self):
        with mock.patch.object(toolchain, "mingw", return_value=r"C:\llvm-mingw"):
            link = toolchain.native_link()
        for name in ("libcmt", "oldnames", "libvcruntime", "msvcrt"):
            self.assertIn("-Wl,-Xlink=/nodefaultlib:" + name, link)

    def test_the_aliases_ffmpeg_asks_for_are_defined(self):
        source = (ROOT / "host" / "msvc_oldnames.c").read_text(encoding="utf-8")
        for name in ALIASES:
            self.assertIn('"/alternatename:%s=_%s"' % (name, name), source,
                          "host/msvc_oldnames.c no longer aliases " + name)

    def test_the_scan_tells_the_windows_build_from_the_others(self):
        text = ('#include <string.h>\n#ifdef _WIN32\nchar *a(const char *s) { return strdup(s); }\n#else\n'
                'char *a(const char *s) { return strdup(s); }\n#endif\n#ifndef _WIN32\nint b(void) { return getpid(); }\n#else\n'
                'int b(void) { return getpid(); }\n#endif\n/* strdup(x) */ const char *c = "unlink(x)"; char *d(char *s) { return _strdup(s); }\n'
                '#if defined(A)\nint e;\n#elif defined(_WIN32)\nint f(int x) { return isatty(x); }\n#else\nint f(int x) { return isatty(x); }\n#endif\n'
                '#ifdef __linux__\nint g(char *p) { return unlink(p); }\n#endif\nint h(char *p) { return my.unlink(p) + q->unlink(p) + do_unlink (p); }\n'
                'int i(char *p) { return unlink (p); }\n')
        self.assertEqual(windows_calls(text, LEGACY), [(3, "strdup"), (10, "getpid"), (16, "isatty"), (24, "unlink")])
        self.assertEqual(windows_calls("#define strdup _strdup\nchar *a(char *s) { return strdup(s); }\n", LEGACY), [])

    def test_the_host_calls_no_legacy_name_in_the_windows_build(self):
        # (#983's crash window copied log lines with strdup: every MSVC-target build then stopped at the link, at
        # "lld-link: error: undefined symbol: strdup", after the whole game had been translated and compiled)
        found = []
        for path in sorted((ROOT / "host").glob("*.[ch]")):
            if path.name == "msvc_oldnames.c":
                continue
            names = [n for n in LEGACY if n not in ALIASES]
            found += ["host/%s:%d %s" % (path.name, line, name)
                      for line, name in windows_calls(path.read_text(encoding="utf-8", errors="replace"), names)]
        self.assertEqual(found, [], "the Windows build for the MSVC target links without oldnames.lib (issue 439): "
                         "call the C runtime's own name there (_strdup), or keep the call out of the Windows build")


if __name__ == "__main__":
    unittest.main()
