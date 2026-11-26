"""The Builders say how long the shaders' preparation has left. 2026-11-15: a player's build sat in "Prepare the shaders" for 58
minutes and more while the window said "Usually about 45 minutes" for the whole build, and they took it for stuck; the game's own
log said "about 1998 s left" all along. Each Builder now takes the game's countdown while it is fresh (gpu/vk/vk_draw.cpp
prepare_progress_log), else works it out from the step's bar.

Checked: the Windows Builder's ShaderStep.Left and LeftIn under .NET 8 (when dotnet is there), the Python Builder's (core.py) and
the Linux Builder's functions on the same cases, and each window reading the lines and showing the countdown in the shaders' step.

    python -I -B tests/test_builder_shader_eta.py [--dotnet dotnet]
"""
import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--dotnet", "{dotnet}"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "builder/py"))

LINE = "[hos host] vk: noted pipelines: 18009 of 32713 pipelines in 2447 s, about 1998 s left"
# (said, since, fraction, elapsed) -> seconds left, or -1
CASES = [
    ((1998, 10, 0.5, 2447), 1988),        # the game's countdown, fresh: less the time since
    ((1998, 39, 0.5, 2447), 1959),
    ((30, 35, 0.9, 900), 0),              # never below 0
    ((1998, 45, 0.5, 600), 600),          # stale (40 s and more): the bar's own, 600 / 0.5 * 0.5
    ((-1, -1, 0.25, 100), 300),           # no countdown yet: by the bar
    ((-1, -1, 0.02, 100), -1),            # the bar too little to go by
    ((-1, -1, 0.5, 10), -1),              # too early
    ((-1, -1, 1.0, 100), -1),             # done: nothing to tell
]


def check_functions(left_in, left, who):
    assert left_in(LINE) == 1998, who + ": the game's countdown line"
    assert left_in("[hos host] vk: compute pipelines: 2312 of 4127 pipelines in 1 s, about 1 s left") == 1, who
    assert left_in("[hos host] vk: noted pipelines: 0 of 32713 pipelines in 0 s (the driver compiles the first ones)") == -1, who
    assert left_in("@@progress 0.500") == -1, who
    for args, want in CASES:
        got = left(*args)
        assert abs(got - want) < 1e-6, "%s: shader_left%s = %s, not %s" % (who, args, got, want)


def linux_functions():
    """pipelines_left_in and shader_left from builder/linux/hookshot_builder.py, without its window (tkinter) or tools"""
    src = (ROOT / "builder/linux/hookshot_builder.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ("pipelines_left_in", "shader_left")) or
            (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "PIPELINES_LEFT" for t in n.targets))]
    assert len(keep) == 3, "the Linux Builder's countdown functions"
    ns = {"re": re}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "hookshot_builder.py", "exec"), ns)
    return ns["pipelines_left_in"], ns["shader_left"]


def check_windows_wiring():
    cs = (ROOT / "builder/HookshotBuilder/MainWindow.xaml.cs").read_text(encoding="utf-8")
    for need in ("if (id == ShaderStep.Id) { shadersBegan = true; shaderClock.Restart(); }",
                 "if (current == ShaderStep.Id) shaderFraction = f;",
                 "ShaderStep.LeftIn(line) is double said && said >= 0) { shaderSaid = said; shaderSaidAt.Restart(); }",
                 "if (current == ShaderStep.Id)", "ShaderStep.Left(shaderSaid,", "Preparing shaders {Clock(shaderClock.Elapsed)}"):
        assert need in cs, "MainWindow.xaml.cs: " + need
    assert "\"Usually about 45 minutes\"" not in cs, "MainWindow.xaml.cs: the fixed 45 minutes is gone"
    qt = (ROOT / "builder/py/hookshot_builder/window.py").read_text(encoding="utf-8")
    for need in ("self.shader0 = time.monotonic()", "self.shader_fraction = f", "core.pipelines_left_in(line) >= 0",
                 "core.shader_left(self.shader_said,", "\"Preparing shaders %s · %s%s\""):
        assert need in qt, "window.py: " + need
    tk = (ROOT / "builder/linux/hookshot_builder.py").read_text(encoding="utf-8")
    for need in ("self.shader_started = time.time() if stage == \"shaders\" else None", "self.shader_fraction = float(",
                 "elif pipelines_left_in(line) >= 0:", "left = shader_left(self.shader_said,", "preparing shaders %d:%02d"):
        assert need in tk, "hookshot_builder.py: " + need


PROGRAM = r'''
using HookshotBuilder;
static void Check(bool ok, string what) { if (!ok) { Console.Error.WriteLine("FAIL: " + what); Environment.Exit(1); } }
Check(ShaderStep.LeftIn("%LINE%") == 1998, "LeftIn");
Check(ShaderStep.LeftIn("@@progress 0.500") == -1, "LeftIn, another line");
%CASES%
Console.WriteLine("PASS: ShaderStep.Left and LeftIn");
'''


def check_dotnet(dotnet):
    cases = "\n".join('Check(Math.Abs(ShaderStep.Left(%s, %s, %s, %s) - (%s)) < 1e-6, "Left%s");' %
                      (a[0], a[1], a[2], a[3], want, str(a).replace('"', "")) for a, want in CASES)
    with tempfile.TemporaryDirectory(prefix="builder-shader-eta-") as folder:
        root = Path(folder)
        (root / "Program.cs").write_text(PROGRAM.replace("%LINE%", LINE).replace("%CASES%", cases), encoding="utf-8")
        shutil.copyfile(ROOT / "builder/HookshotBuilder/ShaderStep.cs", root / "ShaderStep.cs")
        (root / "NuGet.Config").write_text("<configuration><packageSources><clear/></packageSources></configuration>", encoding="utf-8")
        (root / "Fixture.csproj").write_text('''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>
<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings>
<Nullable>enable</Nullable><TreatWarningsAsErrors>true</TreatWarningsAsErrors><NuGetAudit>false</NuGetAudit>
</PropertyGroup></Project>''', encoding="utf-8")
        subprocess.run([dotnet, "run", "--project", str(root / "Fixture.csproj"), "--configuration", "Release"], check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dotnet", default="dotnet")
    a = p.parse_args()
    from hookshot_builder import core
    check_functions(core.pipelines_left_in, core.shader_left, "core.py")
    check_functions(*linux_functions(), "hookshot_builder.py")
    check_windows_wiring()
    dotnet = shutil.which(a.dotnet)
    if dotnet:
        check_dotnet(dotnet)
    else:
        print("(no dotnet: the Windows Builder's ShaderStep was checked by source only)")
    print("PASS: every Builder counts the shaders' time down")


if __name__ == "__main__":
    main()
