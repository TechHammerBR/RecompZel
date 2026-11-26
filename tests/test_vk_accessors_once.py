"""The Vulkan replay hot paths resolve their thread-local state once.

Run with: python -I -B tests/test_vk_accessors_once.py
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated function: {signature}")


def main() -> None:
    source = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")

    bind = function(source, "bool bind_descriptors(")
    assert bind.count("DescWriter& wr = dw();") == 1
    assert bind.count("dw()") == 1

    for signature in (
        "void begin_pass(",
        "void dynamic_state(",
        "uint16_t draw_hazards(",
        "void end_pass(",
        "void draw(VkCommandBuffer",
    ):
        body = function(source, signature)
        assert body.count("Pass& ps = pass();") == 1, signature
        assert body.count("pass()") == 1, signature

    print("vk_accessors_once: ok")


if __name__ == "__main__":
    main()
