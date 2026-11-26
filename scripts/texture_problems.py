#!/usr/bin/env python3
"""(recompzel) Reads a hookshot_log.txt and says which textures the renderer told it got wrong, and which it made in ways
worth suspecting when the picture shows wrong textures (smeared, flat, wrong colours).

    python -I scripts/texture_problems.py <game folder>\\logs\\hookshot_log.txt [--all]

Told problems (gpu/vk/texture_health.h, and the older lines that say the same):
  dummy          a texture slot sampled as the renderer's dummy (not registered, no image, no view)
  upload-failed  an upload that failed (tried again 30 frames on)
  astc-illegal   ASTC blocks the specification calls illegal, drawn as transparent black
Suspects (made as asked, but where a wrong picture usually comes from):
  bc-uneven      an ASTC texture kept as BC3/BC7 whose size is not a multiple of 4 (its smaller levels are partial blocks)
  bc-array       an ASTC texture array kept as BC3/BC7 (the terrain's material arrays)
  direct-copy    a texture copy the recorder thread could not take and made directly
  late           a texture the upload budget held back that came in over 30 presents later (sampled as the dummy meanwhile)
  slow-upload    an upload over 16 ms
  device         a device loss or a Vulkan error
Reads the log only: no texel, no game file."""
import argparse
import collections
import re
import sys

TOLD = re.compile(r"vk: texture problem \[([a-z-]+)\]: (.*)")
SUM = re.compile(r"vk: texture problems: (.*)")
OLD = (
    ("dummy", re.compile(r"vk: texture slot (0x[0-9a-f]+) .*(not registered|no image for it|no view of it)")),
    ("upload-failed", re.compile(r"vk: (?:BC3 )?texture #\d+ .*its upload failed")),
    ("astc-illegal", re.compile(r"vk: ASTC texture #\d+ .* illegal blocks")),
)
MADE = re.compile(r"vk: texture (0x[0-9a-f]+) (\d+)x(\d+)x(\d+) x(\d+) levels (\d+) NVN (0x[0-9a-f]+) -> vk (\d+) \(ASTC decoded\)")
SLOW = re.compile(r"vk: slow upload ([\d.]+) ms: #\d+ (0x[0-9a-f]+) (\d+)x(\d+)x\d+ x(\d+) levels (\d+) NVN (0x[0-9a-f]+) ASTC \((BC\d)\)")
DIRECT = re.compile(r"RX_VK_RECORDER=thread: (vkCmd\w+) did not fit")
LATE = re.compile(r"vk: deferral: texture #\d+ (\d+)x(\d+) x(\d+) NVN (0x[0-9a-f]+), held back at present \d+, in at last (\d+) presents and (\d+) ms later")
DEVICE = re.compile(r"(VK_ERROR_\w+|device lost|DEVICE_LOST)")
BC_FORMATS = {137: "BC3", 138: "BC3 sRGB", 145: "BC7", 146: "BC7 sRGB"}   # (VkFormat values: BC3_UNORM/SRGB, BC7_UNORM/SRGB)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def scan(lines):
    told = collections.OrderedDict((k, []) for k in ("dummy", "upload-failed", "astc-illegal"))
    sums, suspects = [], collections.OrderedDict((k, []) for k in ("late", "bc-uneven", "bc-array", "direct-copy", "slow-upload", "device"))
    seen_new = False
    for n, line in enumerate(lines, 1):
        m = TOLD.search(line)
        if m:
            seen_new = True
            told.setdefault(m.group(1), []).append((n, m.group(2)))
            continue
        m = SUM.search(line)
        if m:
            sums.append((n, m.group(1)))
            continue
        m = MADE.search(line)
        if m:
            gpu, w, h, _d, layers, levels, nvn, vk = m.groups()
            fmt = BC_FORMATS.get(int(vk))
            if fmt:
                what = "%s %sx%s x%s levels %s NVN %s as %s" % (gpu, w, h, layers, levels, nvn, fmt)
                if int(w) % 4 or int(h) % 4:
                    suspects["bc-uneven"].append((n, what))
                if int(layers) > 1:
                    suspects["bc-array"].append((n, what))
            continue
        m = SLOW.search(line)
        if m and float(m.group(1)) > 16:
            suspects["slow-upload"].append((n, "%s ms: %s %sx%s x%s as %s" % (m.group(1), m.group(2), m.group(3), m.group(4),
                                                                           m.group(5), m.group(8))))
            continue
        m = LATE.search(line)
        if m and int(m.group(5)) > 30:
            suspects["late"].append((n, "%sx%s x%s NVN %s: %s presents, %s ms" % m.groups()))
            continue
        m = DIRECT.search(line)
        if m:
            suspects["direct-copy"].append((n, m.group(1)))
            continue
        if DEVICE.search(line) and "vk:" in line:
            suspects["device"].append((n, line.strip()[:200]))
    if not seen_new:   # (a log from before texture_health.h: the older lines)
        for n, line in enumerate(lines, 1):
            for kind, rx in OLD:
                if rx.search(line):
                    told[kind].append((n, line.split("vk: ", 1)[-1][:200]))
    return told, sums, suspects


def report(told, sums, suspects, show_all):
    out = []
    total = sum(len(v) for v in told.values())
    out.append("texture problems told: %d" % total + ("" if sums else " (no sum line: an older build, or none happened)"))
    if sums:
        out.append("  last sum (line %d): %s" % sums[-1])
    for kind, items in told.items():
        if items:
            out.append("  %s: %d" % (kind, len(items)))
            for n, text in (items if show_all else items[:5]):
                out.append("    line %d: %s" % (n, text))
    out.append("suspects:")
    for kind, items in suspects.items():
        out.append("  %s: %d" % (kind, len(items)))
        for n, text in (items if show_all else items[:5]):
            out.append("    line %d: %s" % (n, text))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("log")
    p.add_argument("--all", action="store_true", help="every line, not the first 5 of each kind")
    a = p.parse_args(argv)
    print(report(*scan(read(a.log)), a.all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
