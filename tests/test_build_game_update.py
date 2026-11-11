"""build-game.ps1 brings a git clone up to date before building, and never discards anything of the user's.

The build of 2026-11-11 said "on the latest version" but compiled d3e58ab: C:\\DEV\\RecompZel is a clone and nothing updated it, so
the engine fix on GitHub was not in the exe. Update-Clone (recompzel/build-game.ps1) fetches and fast-forwards. PowerShell is not run
here (only the launcher workflow compiles it), so this reads the script's text for the rules that must hold:

  * only a fast-forward merge: no reset, clean, checkout, stash, pull or force anywhere in the script;
  * it stops without touching the clone when it has local commits, changes or another branch (and says how to align it);
  * the merge's exit code is read before another git command rewrites it;
  * the update runs before the script's Set-Location $Repo and the build;
  * the file stays ASCII (Windows PowerShell 5.1 reads it without a BOM in the system's code page).

python -I -B tests/test_build_game_update.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    raw = (ROOT / "recompzel/build-game.ps1").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "build-game.ps1 must have no BOM"
    assert all(b < 128 for b in raw), "build-game.ps1 must stay ASCII"
    text = raw.decode("ascii")
    start = text.index("function Update-Clone {")
    end = text.index("\nUpdate-Clone\n", start)
    body = text[start:end]

    assert "git merge --ff-only origin/main" in body, "Update-Clone: the merge is not --ff-only"
    for word in ("reset", "clean", "checkout", "stash", "pull", "--force", " -f ", "rebase", "branch -D"):
        assert not re.search(r"& git [^\n]*" + re.escape(word), text), f"build-game.ps1 runs git with {word!r}"
    assert body.count("& git merge") == 1, "Update-Clone: more than one merge"

    # a clone with the user's own work is left alone
    guard = body.index("if ($ramo -ne 'main' -or $a_frente -gt 0 -or $sujo.Count -gt 0)")
    merge = body.index("& git merge")
    assert guard < merge and "return" in body[guard:merge], "Update-Clone: the guard does not stop before the merge"
    assert "Sincronizar GitHub.bat" in body[guard:merge], "Update-Clone: the warning does not say how to align the clone"

    # only a clone with a .git; no git or no network does not stop the build
    assert "Join-Path $Repo '.git'" in body, "Update-Clone: it must skip a copy without .git"
    assert "Get-Command git" in body, "Update-Clone: no check for git"
    assert body.index("git fetch") < body.index("rev-list"), "Update-Clone: it counts commits before fetching"
    fetch_fail = body[body.index("git fetch"):body.index("$atras =")]
    assert "return" in fetch_fail, "Update-Clone: a failed fetch must not stop the build with an error"

    # the merge's exit code is read before the next git command
    assert body.index("$mesclou = ($LASTEXITCODE -eq 0)") < body.index("$depois = (& git rev-parse"), \
        "Update-Clone: $LASTEXITCODE is read after another git command"

    # it runs before the build uses the code
    assert text.index("\nUpdate-Clone\n") < text.index("Set-Location $Repo"), "Update-Clone runs after Set-Location $Repo"
    assert text.index("\nUpdate-Clone\n") < text.index("& $Py -I (Join-Path $Repo 'nx2\\make_game.py')"), "Update-Clone runs after the build starts"
    print("build-game.ps1 update: all rules hold")


if __name__ == "__main__":
    main()
