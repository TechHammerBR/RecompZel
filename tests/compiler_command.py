"""Compiler command parsing shared by the suite and its C fixtures."""
import os
import shlex
import shutil
import sys


def windows_arguments(line):
    """Split compiler arguments using Windows backslash and double-quote rules."""
    out, cur, quoted, have, i = [], [], False, False, 0
    while i < len(line):
        if line[i] == "\\":
            start = i
            while i < len(line) and line[i] == "\\":
                i += 1
            n = i - start
            if i < len(line) and line[i] == '"':
                cur.append("\\" * (n // 2))
                if n % 2:
                    cur.append('"')
                    i += 1
            else:
                cur.append("\\" * n)
            have = True
        elif line[i] == '"':
            if quoted and i + 1 < len(line) and line[i + 1] == '"':
                cur.append('"')
                i += 2
            else:
                quoted, i = not quoted, i + 1
            have = True
        elif line[i] in " \t" and not quoted:
            if have:
                out.append("".join(cur))
            cur, have, i = [], False, i + 1
        else:
            cur.append(line[i])
            have, i = True, i + 1
    if have:
        out.append("".join(cur))
    return out


def parse_compiler(configured):
    """Accept a bare executable path or a compiler command with flags."""
    if configured:
        if os.path.isfile(configured) or shutil.which(configured):
            return [configured]
        return windows_arguments(configured) if sys.platform == "win32" else shlex.split(configured)
    return []


def compiler_command(variable, *fallbacks):
    configured = os.environ.get(variable)
    if configured:
        return parse_compiler(configured)
    return [next((path for name in fallbacks if (path := shutil.which(name))), None)]
