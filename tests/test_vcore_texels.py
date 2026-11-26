"""nvnTextureWriteTexels and nvnTextureReadTexels wait for the replay with the calling thread's virtual core given up.

Both wait before they touch the texture (gpu/vk/vk_replay.cpp write_texels / read_texels: finish(), then replay_mu):
behind the submissions another thread is replaying, and for the GPU. nvnQueueFinish gives the core up for the same
wait; texels() (host/nvn_native.c) kept it. While a save loads on a Steam Deck LCD the thread that writes a texture (a
ModuleSystemWorker, or sead::MainThread) was in WriteTexels for 0.5 to 5.4 s behind the first submissions, holding its
core, and in 4 of 8 sampled launches a thread that runs on that core only waited for all of it (the audio's among
them); over 2 s that is the escape (`vcores: ... ran without a core`).

python -I -B tests/test_vcore_texels.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    src = (ROOT / "host" / "nvn_native.c").read_text(encoding="utf-8")
    body = src[src.index("static void texels(Ctx *c, int write, int strided) {"):]
    body = body[:body.index("\n}\n")]
    order = ["const int away = holds ? 0 : hos_vcore_away();", "rx_nvn_write_texels(t, level, layer0, r, data, row, img)",
             "rx_nvn_read_texels(t, level, layer0, r, data, row, img)", "if (away) hos_vcore_back();"]
    at = []
    for needle in order:
        if body.count(needle) != 1:
            raise SystemExit("texels: %r is there %d times" % (needle, body.count(needle)))
        at.append(body.index(needle))
    if at != sorted(at):
        raise SystemExit("texels: the renderer's write and read are not made with the core given up")
    if 'env_on("HOS_TEXELS_HOLD_CORE")' not in body:
        raise SystemExit("texels: no HOS_TEXELS_HOLD_CORE to keep the core, as before")
    # (the four entry points all go through texels)
    for name, args in (("nvnTextureReadTexels", "c, 0, 0"), ("nvnTextureReadTexelsStrided", "c, 0, 1"),
                       ("nvnTextureWriteTexels", "c, 1, 0"), ("nvnTextureWriteTexelsStrided", "c, 1, 1")):
        if "NV(%s) { texels(%s); }" % (name, args) not in src:
            raise SystemExit("%s does not go through texels(%s)" % (name, args))
    print("texels are written and read with the virtual core given up")


if __name__ == "__main__":
    main()
