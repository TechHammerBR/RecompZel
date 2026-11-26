"""The build's preparation run lets each noted pipeline go once it is in the pipeline cache (gpu/vk/vk_draw.cpp precompile_run, the
start mode's way: GPUs without mesh shaders). Nothing plays in that run; kept, all 32,713 stayed alive to its end, over 12 GB, and a
16 GB PC paged to disk while it built: a player's build sat in "Prepare the shaders" for over an hour. Checked by source, 2026-11-15:

- the worker destroys what it built when HOOKSHOT_PREPARE_ONLY is set, before any entry is published;
- RX_VK_PREPARE_KEEP=1 keeps them, as before, and the game's own starts (no HOOKSHOT_PREPARE_ONLY) still publish each one;
- the warm path (loads at create) still lets each go, as it did.

python -I -B tests/test_prepare_lets_go.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    run = block(draw, "void precompile_run(void (*progress)(size_t done, size_t total)) {")
    flag = 'static const bool let_go = env_on("HOOKSHOT_PREPARE_ONLY") && !env_on("RX_VK_PREPARE_KEEP");'
    assert flag in run, "precompile_run: the preparation run's let-go switch"
    after = run[run.index(flag):]
    let_go = after[after.index("if (let_go) {"):after.index("} else {")]
    assert "vkDestroyPipeline(dev.device, made, nullptr);" in let_go, "the preparation run destroys what it built"
    assert "pipelines.emplace" not in let_go, "the preparation run publishes nothing"
    kept = after[after.index("} else {"):]
    kept = kept[:kept.index("pre->done++;")]
    for need in ("std::lock_guard lk(note_mu);", "pipelines.emplace(n.key, std::move(e));",
                 "e->ready.store(true, std::memory_order_release);"):
        assert need in kept, "a game start still keeps its pipelines ready: " + need
    assert run.index("build_graphics(*p, n.s") < run.index(flag), "built first, then let go"
    warm = block(draw, "void precompile_warm(void (*progress)(size_t done, size_t total)) {")
    assert "if (made) vkDestroyPipeline(dev.device, made, nullptr);" in warm, "the warm path still lets each go"
    print("PASS: the build's preparation run keeps no pipeline alive; a game start keeps them ready")


if __name__ == "__main__":
    main()
