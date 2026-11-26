"""The user-uniform slot memo (HL_UBO_MEMO, gpu/vk/ubo_memo.h): the header against a made-up world, and the wiring in vk_draw.cpp
(what the memo keeps, when it stays off, that the check mode works the full lookup out). python -I -B tests/test_ubo_slot_memo.py [--cxx clang++]"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]


def check_wiring():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    start = draw.index("VkDescriptorBufferInfo uniform_range(")
    body = draw[start:draw.index("struct DescWriter", start)]
    for needle in (
        # (the memo is for the plain pool answer only: inline bytes, the overlay copy and the stream copy never make an entry)
        "!s.ubo_bytes[memo_stage][index - 3]",
        "u.addr < (1ull << 40)",
        "return direct = true, VkDescriptorBufferInfo{b.buffer, b.offset, n};",
        "if (direct && ubomemo::storable(memo_key.epoch, epoch_after) && limit == memo_key.limit)",
        # (the check mode works the full lookup out and compares)
        "if (memo_mode == 1) return memo_hit;",
        "if (memo_hit_found) ubo_memo_compare(memo_hit, r, u.addr, n, memo_stage, index);",
    ):
        if needle not in body:
            raise SystemExit("vk_draw.cpp's uniform_range no longer has: " + needle)
    mode = draw[draw.index("int ubo_memo_mode() {"):draw.index("using UboMemoSlots")]
    for needle in ("ledger_on()", "RX_VK_CAP_ONLY_GPU", "RX_VK_UB_SNAPSHOT", "RX_VK_UB_CUR_ONLY", "HL_UBO_MEMO_CHECK", "HL_UBO_MEMO"):
        if needle not in mode:
            raise SystemExit("ubo_memo_mode no longer reads: " + needle)
    # (a draw's key: the pools' stamp, the update list's view and the segment, read before the lookup)
    for needle in ("gpu_bind_stamp()", "ub_view(&limit)", "texture_segment()"):
        if needle not in body:
            raise SystemExit("uniform_range's memo key no longer has: " + needle)
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    view = replay[replay.index("uint64_t ub_view("):]
    view = view[:view.index("\n}\n")]
    if "*limit = ub_limit;" not in view or "ub_list_epoch.load" not in view:
        raise SystemExit("ub_view no longer returns the epoch and this thread's limit")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="clang++")
    a = p.parse_args()
    check_wiring()
    with tempfile.TemporaryDirectory(prefix="ubo-memo-") as temp:
        exe = Path(temp) / "ubo_slot_memo_test.exe"
        subprocess.run([a.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/ubo_slot_memo_test.cpp"), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], check=True, timeout=120, capture_output=True, text=True).stdout
        assert " 0 mismatches" in out, out
    print("PASS:", out.strip())


if __name__ == "__main__":
    main()
