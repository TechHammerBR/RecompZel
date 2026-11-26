
"""The build cuts a lifted chunk at function starts into parts of about HOOKSHOT_CHUNK_PART_MB when HOOKSHOT_CHUNK_OPT
compiles it at -O2 (nx2/build.py chunk_parts, chunk_opt_o2, chunk_flags).

A chunk is ~25 MB of lifted C. At -O2 its passes cost more than linearly in a function's size (GVN is 46% of the optimizer's
time on one), so compiling it as one translation unit makes the longest compile the build's tail. The build now cuts the
chunks it sends to -O2 into parts of about 6 MB, each with the chunk's declarations, as separate objects: on a Ryzen 9
9950X3D a 25 MB chunk went 133 s -> 87 s of compile CPU in 4 parts (and its longest compile 133 s -> 28 s), and the whole
all-O2 build's compile falls by about a third. The lifted C is not changed; the parts are written beside the build's objects.

This is the game-free check of that cut: the functions, in order, with the chunk's declarations; a small chunk stays whole;
a stamp keeps a build that changed nothing from writing them again; an earlier, longer cut's extra parts go; and
HOOKSHOT_CHUNK_OPT's selection ("all", a code_*.c, or an f_ name's chunk) and its -O2 flags.

python -I -B tests/test_chunk_parts.py
"""
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "nx2"), str(ROOT / "third_party" / "a64-kit" / "tools")]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load("build_chunk_parts", ROOT / "nx2" / "build.py")

PREAMBLE = '#include "a64.h"\nvoid f_90000000(Ctx *A64_NOESC);\n'
HEAD = re.compile(r"^void (f_[0-9a-f]+)\(Ctx \*__restrict A64_NOESC c\) \{", re.M)


def function(addr, size):
    head = "void f_%08x(Ctx *__restrict A64_NOESC c) {\n" % addr
    line = "c->x[1] = c->x[2] + 1;\n"
    return head + line * max(1, (size - len(head) - 2) // len(line)) + "}\n"


def check(what, ok):
    if not ok:
        raise SystemExit("FAIL: " + what)


def read(path):
    with open(path, newline="") as f:
        return f.read()


def test_cut_keeps_the_functions():
    with tempfile.TemporaryDirectory(prefix="hookshot-parts-") as d:
        fns = [function(0x80000000 + 0x1000 * i, 300000) for i in range(8)]
        src = os.path.join(d, "code_001.c")
        Path(src).write_text(PREAMBLE + "".join(fns), newline=chr(10))
        split = os.path.join(d, "split")
        flag = build.chunk_split_flag(1)
        parts = build.chunk_parts(src, 1, split, flag)
        check("a 2.4 MB chunk is cut into parts", parts is not None and len(parts) >= 2)
        texts = [read(p) for p in parts]
        check("every part has the chunk's declarations", all(t.startswith(PREAMBLE) for t in texts))
        check("no part is cut inside a function", all(HEAD.match(t[len(PREAMBLE):]) for t in texts))
        check("the functions are the chunk's, in order",
              [n for t in texts for n in HEAD.findall(t)] == HEAD.findall(PREAMBLE + "".join(fns)))
        check("the bodies are the chunk's", "".join(t[len(PREAMBLE):] for t in texts) == "".join(fns))
        check("the parts are about the part size", all(len(t) <= 2 * (1 << 20) for t in texts))
        mtimes = [os.stat(p).st_mtime_ns for p in parts]
        again = build.chunk_parts(src, 1, split, flag)
        check("a build that changed nothing keeps the parts", again == parts and
              [os.stat(p).st_mtime_ns for p in again] == mtimes)
        check("a small chunk stays whole", build.chunk_parts(src, 64, split, build.chunk_split_flag(64)) is None)


def test_an_earlier_longer_cut_loses_its_extra_parts():
    with tempfile.TemporaryDirectory(prefix="hookshot-parts-") as d:
        fns = [function(0x80000000 + 0x1000 * i, 300000) for i in range(16)]
        src = os.path.join(d, "code_002.c")
        Path(src).write_text(PREAMBLE + "".join(fns), newline=chr(10))
        split = os.path.join(d, "split")
        many = build.chunk_parts(src, 1, split, build.chunk_split_flag(1))
        few = build.chunk_parts(src, 3, split, build.chunk_split_flag(3))
        check("a coarser cut makes fewer parts", few is not None and len(few) < len(many))
        left = sorted(f for f in os.listdir(split) if f.startswith("code_002.p"))
        check("the earlier cut's extra parts are removed", left == sorted(os.path.basename(p) for p in few))


def test_chunk_opt_selects():
    with tempfile.TemporaryDirectory(prefix="hookshot-opt-") as d:
        gen = os.path.join(d, "gen")
        os.makedirs(gen)
        Path(gen, "code_001.c").write_text(PREAMBLE + function(0x80000000, 2000), newline=chr(10))
        Path(gen, "code_002.c").write_text(PREAMBLE + function(0x81000000, 2000), newline=chr(10))
        Path(gen, "code_hot_0.c").write_text(PREAMBLE + function(0x82000000, 2000), newline=chr(10))
        old = os.environ.get("HOOKSHOT_CHUNK_OPT")
        try:
            os.environ["HOOKSHOT_CHUNK_OPT"] = "all"
            check("all selects every chunk", build.chunk_opt_o2(gen) == "*")
            os.environ["HOOKSHOT_CHUNK_OPT"] = ""
            check("unset selects none", build.chunk_opt_o2(gen) is None)
            os.environ["HOOKSHOT_CHUNK_OPT"] = "0"
            check("0 selects none", build.chunk_opt_o2(gen) is None)
            names = os.path.join(d, "names.txt")
            Path(names).write_text("code_001.c\n", newline=chr(10))
            os.environ["HOOKSHOT_CHUNK_OPT"] = names
            check("a code_*.c line selects that chunk", build.chunk_opt_o2(gen) == {"code_001.c"})
            Path(names).write_text("f_81000000\n", newline=chr(10))
            os.environ["HOOKSHOT_CHUNK_OPT"] = names
            check("an f_ name selects the chunk that defines it", build.chunk_opt_o2(gen) == {"code_002.c"})
        finally:
            if old is None:
                os.environ.pop("HOOKSHOT_CHUNK_OPT", None)
            else:
                os.environ["HOOKSHOT_CHUNK_OPT"] = old


def test_chunk_flags_puts_o2():
    old = build.CHUNK_OPT_O2
    try:
        build.CHUNK_OPT_O2 = "*"
        fl = build.chunk_flags("gen/code_001.c", ["-O1", "-march=native", "-DA64_POLLING"])
        check("a selected chunk is -O2", fl == ["-O2", "-march=native", "-DA64_POLLING"])
        build.CHUNK_OPT_O2 = {"code_002.c"}
        check("an unselected chunk is left to source_flags", build.chunk_flags("gen/code_001.c", ["-O1"]) is None)
        check("a selected chunk by name is -O2", build.chunk_flags("gen/code_002.c", ["-O1"]) == ["-O2"])
        old_level = os.environ.get("HOOKSHOT_CHUNK_LEVEL")
        try:
            build.CHUNK_OPT_O2 = "*"
            os.environ["HOOKSHOT_CHUNK_LEVEL"] = "O3"
            check("the level switch reaches the flags", build.chunk_flags("gen/code_001.c", ["-O1"]) == ["-O3"])
            os.environ["HOOKSHOT_CHUNK_LEVEL"] = "nonsense"
            check("an unknown level is O2", build.chunk_flags("gen/code_001.c", ["-O1"]) == ["-O2"])
        finally:
            if old_level is None:
                os.environ.pop("HOOKSHOT_CHUNK_LEVEL", None)
            else:
                os.environ["HOOKSHOT_CHUNK_LEVEL"] = old_level
    finally:
        build.CHUNK_OPT_O2 = old


def test_main_cuts_the_selected_chunks():
    """The wiring, which a functional test of chunk_parts alone would not see: main() cuts the chunks it sends to -O2, and a
    cut build writes no kept list (the kept objects are the whole chunks')"""
    text = (ROOT / "nx2" / "build.py").read_text(encoding="utf-8")
    check("main cuts the chunks it sends to -O2", "chunk_parts(s, part_mb, split_dir, split_flag)" in text)
    check("a cut build writes no kept list", "and not cut" in text)


def main():
    test_cut_keeps_the_functions()
    test_an_earlier_longer_cut_loses_its_extra_parts()
    test_chunk_opt_selects()
    test_chunk_flags_puts_o2()
    test_main_cuts_the_selected_chunks()
    print("ok: chunks cut into parts of about the part size, the functions and declarations kept, and the -O2 selection")


if __name__ == "__main__":
    main()
