"""An ASTC texture re-uploaded after the frame's upload budget waits a few frames at most (the museum's boss challenge stutters)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    src = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    hdr = (ROOT / "gpu/vk/vk_texture.h").read_text(encoding="utf-8")
    if "uint64_t reupload_wait = 0;" not in hdr:
        raise SystemExit("Texture has no reupload_wait")
    fn = block(src, "bool reupload_defer(Texture& tex) {")
    for need in ('"RX_VK_REUPLOAD_BUDGET_MS"', ": 6.0)", '"RX_VK_REUPLOAD_MAX_WAIT"', ": 4;",
                 "!tex.uploaded || !tex.astc || tex.gpu_written || tex.released",
                 "frame_no - tex.reupload_wait >= max_wait", "frame_upload_ns.load"):
        if need not in fn:
            raise SystemExit(f"reupload_defer is missing: {need}")
    touch = block(src, "Texture* texture_touch(Texture* tex, bool for_sampling) {")
    dirty = touch.index("!texture_dirty(*tex, since, dirty, !tex->gpu_written)) return tex;")
    defer = touch.index("if (!gpu_dirty && reupload_defer(*tex)) return tex;")
    if not dirty < defer:
        raise SystemExit("the deferral must come after the dirty check (only a texture with new texels waits)")
    if "upload_gen = gen" in touch[dirty:defer]:
        raise SystemExit("a deferred texture must keep its upload_gen, so the next look finds it dirty again")
    if not re.search(r"tex->upload_gen = gen;\n\s+tex->gpu_written = false;\n\s+tex->released = false;\n\s+tex->reupload_wait = 0;", touch):
        raise SystemExit("an upload must clear reupload_wait")
    print("reupload defer: ok")


if __name__ == "__main__":
    main()
