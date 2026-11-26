"""The renderer's CPU ASTC decoder (gpu/vk/texdecode/astc.cpp) equals ARM's astcenc on legal multi-partition blocks whose colour
endpoint sequence ends in a partial trit or quint group with nonzero spare bits, and on three controls. Blocks are hand-picked
random numbers (never game data), each with astcenc 6.0.0's 8-bit RGBA answer.

What the decoder this one replaced (suyu's, gpu/third_party/suyu/video_core/textures/astc.cpp, still in the tree but no longer built)
did with these blocks: some texels came out far from astcenc's, up to 117 of 255 in one channel, not just
one step off. Cause, checked against astcenc on every legal LDR block in tests/texdecode_astc_vectors.vec and on 267k more random
legal blocks: the colour endpoints are an integer sequence (the specification's "Integer Sequence Encoding") of N values, in groups
of 5 (trits) or 3 (quints) whose high code bits are missing when the last group is not full; astcenc, like the specification, reads
the missing bits as zero. suyu's DecompressBlock copied every bit up to the weights (the sequence's and the spare bits after it)
into the buffer DecodeColorValues decodes, and DecodeTritBlock / DecodeQuintBlock always read a full group, so the missing code
bits came from the spare bits. Where those are not zero (random blocks; an encoder that zeroes them hides the fault) a partial last
group can unquantise to other values, which moves one partition's endpoints. Only blocks with more than 8 colour values are
affected, so mostly 2 to 4 partitions. (Separately, suyu rounded the 8-bit result where astcenc and this decoder truncate it: one
step off in some texel of nearly every block, which is the second verdict below, "exact".)

python -I -B tests/test_texdecode_astc_partitions.py [--cxx c++] [--decoder texdecode|suyu]

--decoder suyu (not run by run_all.py: RUN_ALL_ARGS has no such option, and it fails by design) shows the fault: it builds suyu's astc.cpp
alone, as the project builds it (NDEBUG, without -Werror) and has renderer_cpu_astc_decode call its DecompressSerial. Expect "FAIL", 8 of
the 11 blocks more than one step from astcenc's (largest difference 117), the 3 controls at most one step off.

renderer_cpu_astc_decode in tests/texdecode_astc_partitions_test.cpp is the one function that names the decoder: the call
vk_texture.cpp makes for a level (astc_decode, linear mode), here for a level of one block.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

# (name, width, height, block bytes, astcenc's 8-bit RGBA, what the block is). tail: "nonzero" = the spare bits after the colour
# sequence are not all zero and the last group is partial (the class), "zero" = partial but spare bits zero, "full" = no partial group.
BLOCKS = [
    ("2part-dual-cem8-8-4x4", 4, 4, "236c79f07b04007ee065b257d28fd6e5",
     "000085ffccad64ff000099ffccccffff00008cffcca640ff00007cff000093ff00008fffcca640ff000070ff00008cff00008fff00007aff000070ff000085ff",
     "4x4, 2 partitions, dual plane, both CEM 8 (RGB), 12 values at 6 levels: last trit group holds 2 of 5, 2 spare bits set", 2, "nonzero"),
    ("4part-cem4-4x4", 4, 4, "de9b0d6849e0b34c6ed2ec2d3db73a13",
     "d1d1d1ecd8d8d8cfddddddbc48484879dfdfdfb6e8e8e88fefefef7659595933ebebeb86f6f6f659585858394242428febebeb86f0f0f0705858583954545449",
     "4x4, 4 partitions, all CEM 4 (luminance + alpha), 16 values at 6 levels: last group holds 1 of 5, 5 spare bits set", 4, "nonzero"),
    ("3part-cem6-5-8-4x4", 4, 4, "cd3328e99b68e39d4cf41f07e60ff691",
     "6e4f87ff935859ff90575dff644c94ff4545baff614c97ff7e5373ffa35c45ff644c94ff644c94ff6b4e8bff7a5278ff4545baff865569ff90575dff644c94ff",
     "4x4, 3 partitions, CEMs 6,5,8 (selector 2, extra CEM bits stored), 14 values at 12 levels: last group 4 of 5, 3 spare bits set", 3, "nonzero"),
    ("2part-cem13-9-5x4", 5, 4, "51aae9cb3c742c0bdf343e18f83ab6bc",
     "8c2633ff8c2633ff45cc896649cb8b668c2633ff8c2633ff40cc866647cb8a6649cb8b668c2633ff8c2633ff37cc826642cc876647cb8a668c2633ff43cc88663acc84663fcc866642cc88668c2633ff",
     "5x4, 2 partitions, CEMs 13,9 (selector 3), 14 values at 6 levels: last group 4 of 5, 2 spare bits set; colour error", 2, "nonzero"),
    ("2part-dual-cem12-12-4x4", 4, 4, "5fadd2271b295244f20a4ecefc1f4c37",
     "db8fa9a9c3859f9f55784b785f6c486c7f6f8989a78ca6a643b758b733db5fdbffe5ffffddcce6e651b357b3918fa9a9c9e5ffffc3cce6e64eb357b350935093",
     "4x4, 2 partitions, dual plane, CEMs 12,12 (selector 3), 16 values at 6 levels: last group 1 of 5, 5 spare bits set", 2, "nonzero"),
    ("3part-cem5-6-4-5x5", 5, 5, "d3f0943e8eab51785268c380938d73f5",
     "cc3399ffcc3299ffcc3298ffcc3399ff4848483bcc3299ffcc3299ffcc3299ff5454542459595919cc3299ffcc3298ff545454244c4c4c337e7e7e4bcc3399ff5b5b5b1662626208777777437d7d7d493a3a3a583a3a3a587b7b7b487f7f7f4c76767642",
     "5x5, 3 partitions, CEMs 5,6,4 (selector 1), 12 values at 6 levels: last group 2 of 5, 2 spare bits set; alpha error", 3, "nonzero"),
    ("2part-dual-cem8-8-6x6", 6, 6, "022d7a07ca41b9ee9d1d7e92909b7688",
     "4c5c26ff4c5c26ff9cff36ff9c9236ff4cca26ff7c7f26ff4c7026ff3d5c23ff8df533ff7f9230ff5ad429ff7e7934ff4c8526ff2f5c20ff7feb30ff62922aff69de2cff817343ff4ca126ff1d5c1cff69de2cff3a9222ff7feb30ff856c57ff4cb526ff0e5c19ff5ad429ff1d921cff8df533ff886665ff4cca26ff005c17ff4cca26ff009217ff9cff36ff8b6074ff",
     "6x6, 2 partitions, dual plane, CEMs 8,8 (selector 2, same mode stored per partition), 12 values at 12 levels: last group 2 of 5, 3 spare bits", 2, "nonzero"),
    ("3part-cem6-9-10-8x8", 8, 8, "ed33478dc485d542e4e7b7bead9aa9fd",
     "88002d1c780028386c00244c5d001f6456001c7056001c70ccb35affccb35aff7f002a2c6c00244c5d001f644a001883400015933e0014973c00149bccb355ff780028386700225456001c704300168f3900139f300010af2b000eb724000cc3780028386e0024486c00244c670022545d001f644a0018833c00149b2d000fb36200205c690023506c00244c6e002448700025446200205c56001c704c0019803c00149b4800188756001c706200205c6e002448700025447a0028347f002a2c600020605d001f6456001c7054001c7454001c74600020606700225473002640990033007a002834600020603e001497370012a34300168f4a00188356001c70",
     "8x8, 3 partitions, CEMs 6,9,10 (selector 2), 16 values at 6 levels: last group 1 of 5, 2 spare bits set; alpha error (51), 61 of 64 texels differ", 3, "nonzero"),
    # Controls: the same decoder should be fine on these (within one step) even before the fix.
    ("control-3part-spare-bits-zero", 4, 4, "4ff748a2f786d1f6b85c1b2bedaf42d2",
     "796879ff726c72ff8f9e8fff80a680ff6e726effa09aa0ffa991a9ffb08ab0ff6c6c6cff9e9a9effa8a0a8ffb0a4b0ffa9b6a9ffa7b5a7ffa6b4a6ffa4b3a4ff",
     "control: 4x4, 3 partitions, CEMs 1,1,1, 6 values at 12 levels: partial last group (1 of 5) but its 1 spare bit is zero", 3, "zero"),
    ("control-2part-no-trit-quint", 4, 4, "df4b71509fa26228861ad458023d4ddd",
     "9f7f9fff896d89ffb5573aff8d5f32ffdd5042ffa15b36ff74642cff496d24ff7c632eff656729ff1f191fff3e323eff4e6c25ff5b485bff5e4b5eff0b090bff",
     "control: 4x4, 2 partitions, CEMs 8,8, 12 values at 8 levels (plain bits, no groups): 3 spare bits set but nothing reads them", 2, "full"),
    ("control-1part-cem12", 4, 4, "be87d5473eb610a8d2c3f6ea00e65e8d",
     "6a6e6a0e7370670a7470670a6b6e6a0e776291337867842678697d2074697b1e775ea0427a638f317c648b2d7b648d2f6a60993b78658a2c80648d2f825da345",
     "control: 4x4, 1 partition, dual plane, CEM 12, 8 values at 12 levels: last group 3 of 5 and 2 spare bits set, but one partition rarely moves", 1, "nonzero"),
]

_ISE = [(1, 0, 0), (0, 1, 0), (2, 0, 0), (0, 0, 1), (1, 1, 0), (3, 0, 0), (1, 0, 1), (2, 1, 0), (4, 0, 0), (2, 0, 1), (3, 1, 0),
        (5, 0, 0), (3, 0, 1), (4, 1, 0), (6, 0, 0), (4, 0, 1), (5, 1, 0), (7, 0, 0), (5, 0, 1), (6, 1, 0), (8, 0, 0)]   # (bits, trit, quint) of 2,3,4,5,6,8,10,12,... levels


def _ise_bits(count, q):
    bits, trit, quint = _ISE[q]
    return count * bits + ((8 * count + 4) // 5 if trit else 0) + ((7 * count + 2) // 3 if quint else 0)


def _field(block, pos, n):
    return sum((block[(pos + i) // 8] >> ((pos + i) % 8) & 1) << i for i in range(n))


def describe(block):
    """(partitions, tail) of a block as the spec lays it out (block mode and colour endpoint mode tables); tail as in BLOCKS."""
    mode = _field(block, 0, 11)
    r, h, d, a = mode >> 4 & 1, mode >> 9 & 1, mode >> 10 & 1, mode >> 5 & 3
    if mode & 3:
        r |= (mode & 3) << 1
        b = mode >> 7 & 3
        k = mode >> 2 & 3
        wx, wy = ((b + 4, a + 2), (b + 8, a + 2), (a + 2, b + 8), ((b & 1) + 2, a + 2) if mode & 0x100 else (a + 2, (b & 1) + 6))[k]
    else:
        r |= (mode >> 2 & 3) << 1
        b = mode >> 9 & 3
        k = mode >> 7 & 3
        wx, wy = ((12, a + 2), (a + 2, 12), (a + 6, b + 6), (6, 10) if a == 0 else (10, 6))[k]
        if k == 2:
            d = h = 0
    q = r - 2 + 6 * h
    wbits = _ise_bits(wx * wy * (d + 1), q)
    np = _field(block, 11, 2) + 1
    if np == 1:
        cems, start, extra = [_field(block, 13, 4)], 17, 0
    else:
        base, start, extra = _field(block, 23, 6), 29, 3 * np - 4
        if base & 3 == 0:
            cems, extra = [base >> 2] * np, 0
        else:
            enc = base | _field(block, 128 - wbits - extra, extra) << 6
            cems = [(((enc >> (2 + i)) & 1) + (base & 3) - 1) << 2 | (enc >> (2 + np + 2 * i)) & 3 for i in range(np)]
    values = sum((c >> 2) * 2 + 2 for c in cems)
    space = 128 - wbits - start - extra - 2 * d
    level = max(i for i in range(21) if _ise_bits(values, i) <= space)
    bits, trit, quint = _ISE[level]
    partial = (trit and values % 5 != 0) or (quint and values % 3 != 0)
    spare = [_field(block, start + _ise_bits(values, level) + i, 1) for i in range(space - _ise_bits(values, level))]
    return np, ("full" if not partial else "nonzero" if any(spare) else "zero")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "c++"))
    parser.add_argument("--decoder", choices=("texdecode", "suyu"), default="texdecode")
    args = parser.parse_args()
    cxx = shutil.which(args.cxx)
    if not cxx:
        raise SystemExit("C++ compiler not found: " + args.cxx)
    lines = []
    for name, w, h, blk, want, what, np, tail in BLOCKS:   # (what the blocks claim, checked: a hand edit that breaks the class is caught)
        if len(blk) != 32 or len(want) != w * h * 8 or describe(bytes.fromhex(blk)) != (np, tail):
            raise SystemExit("FAIL: block %s is not what its entry says (%s): found %s" % (name, what, describe(bytes.fromhex(blk))))
        lines.append("%s %d %d %s %s" % (name, w, h, blk, want))
    gpu = ROOT / "gpu"
    flags = [cxx, "-std=c++2b", "-O2"]
    with tempfile.TemporaryDirectory(prefix="hookshot-texdecode-astc-") as folder:
        folder = Path(folder)
        (folder / "blocks.txt").write_text("\n".join(lines) + "\n")
        exe = folder / "t"
        harness = [str(ROOT / "tests" / "texdecode_astc_partitions_test.cpp"), "-o", str(exe)]
        if args.decoder == "suyu":
            suyu = gpu / "third_party" / "suyu"
            obj = folder / "suyu_astc.o"
            r = subprocess.run(flags + ["-DNDEBUG", "-include", "cstdint", "-I", str(gpu / "compat"), "-isystem", str(suyu), "-c",
                                        str(suyu / "video_core/textures/astc.cpp"), "-o", str(obj)], capture_output=True, text=True, timeout=300)
            if r.returncode:
                raise SystemExit("FAIL: suyu's astc.cpp does not compile\n" + r.stdout + r.stderr)
            cmd = flags + ["-Wall", "-Wextra", "-Werror", "-DDECODER_SUYU", "-isystem", str(suyu)] + harness + [str(obj), "-lpthread"]
        else:
            cmd = flags + ["-Wall", "-Wextra", "-Werror", "-I", str(gpu / "vk")] + harness + [str(gpu / "vk" / "texdecode" / "astc.cpp")]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise SystemExit("FAIL: texdecode_astc_partitions_test.cpp does not compile\n" + r.stdout + r.stderr)
        r = subprocess.run([str(exe), str(folder / "blocks.txt")], capture_output=True, text=True, timeout=300)
        print(r.stdout, end="")
        if r.returncode == 1:
            raise SystemExit("FAIL: the %s decoder is not astcenc's on these blocks (see above: more than one step is the multi-partition fault, "
                             "exact is the rounding)" % args.decoder)
        if r.returncode:
            raise SystemExit("FAIL: texdecode_astc_partitions_test failed to run\n" + r.stderr)
        print("ok: the %s decoder equals astcenc on %d blocks" % (args.decoder, len(BLOCKS)))


if __name__ == "__main__":
    main()
