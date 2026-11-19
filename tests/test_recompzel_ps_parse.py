"""The launcher's PowerShell scripts (recompzel/*.ps1) parse without errors.

The launcher and the build run these scripts on the player's PC; a syntax error there stops the launcher before its window. The
parse is PowerShell's own (System.Management.Automation.Language.Parser), on Windows only: elsewhere the check is skipped.

python -I -B tests/test_recompzel_ps_parse.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    shell = shutil.which("powershell") or shutil.which("pwsh") if os.name == "nt" else None
    if not shell:
        print("skip: PowerShell's parser is checked on Windows only")
        return 0
    bad = 0
    for script in sorted((ROOT / "recompzel").glob("*.ps1")):
        cmd = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('%s', [ref]$null, [ref]$e); "
               "foreach ($x in $e) { Write-Output ('{0}:{1}: {2}' -f $x.Extent.StartLineNumber, $x.Extent.StartColumnNumber, $x.Message) }"
               % str(script).replace("'", "''"))
        out = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=120)
        errors = out.stdout.strip()
        if out.returncode or errors:
            bad += 1
            print("FAIL %s\n%s%s" % (script.name, errors, out.stderr))
    if bad:
        return 1
    print("PASS the launcher's PowerShell scripts parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
