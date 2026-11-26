"""The renderer's source list (nx2/build.py vk_sources) holds the CPU texture decoders (gpu/vk/texdecode/*.cpp: ported code) and none
of suyu's: its decoders.cpp and astc.cpp are no longer built (gpu/third_party/suyu is not edited, and what is not built there is not
removed). Every C++ file under gpu/vk/texdecode is in the list (one added there and left out would fail to link only when something
calls it), nothing in the list is under gpu/third_party/suyu/video_core/textures, and no two of the list's objects take one name.

    python -I -B tests/test_texdecode_build.py
"""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "nx2"), str(ROOT / "third_party" / "a64-kit" / "tools")]
spec = importlib.util.spec_from_file_location("build_texdecode", ROOT / "nx2" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def main():
    sources = {os.path.relpath(s, ROOT).replace(os.sep, "/") for s in build.vk_sources()}
    problems = []
    for f in sorted((ROOT / "gpu/vk/texdecode").glob("*.cpp")):
        rel = f.relative_to(ROOT).as_posix()
        if rel not in sources:
            problems.append("%s is not in vk_sources()" % rel)
    for rel in ("gpu/vk/texdecode/astc.cpp", "gpu/vk/texdecode/block_linear.cpp"):
        if rel not in sources:
            problems.append("%s is not in vk_sources()" % rel)
    for rel in sorted(sources):
        if rel.startswith("gpu/third_party/suyu/video_core/textures/"):
            problems.append("%s is in vk_sources(): suyu's texture decoders are not built" % rel)
    vk = ROOT / "gpu" / "vk"
    names = {}
    for s in build.vk_sources():
        name = os.path.relpath(s, vk).replace(os.sep, "_")[:-4]   # (the object's name, as build.py makes it)
        if name in names:
            problems.append("%s and %s are one object, vk_%s.o" % (s, names[name], name))
        names[name] = s
    if problems:
        raise SystemExit("FAIL:\n  " + "\n  ".join(problems))
    print("ok: %d renderer sources, texdecode's among them and none of suyu's textures" % len(sources))


if __name__ == "__main__":
    main()
