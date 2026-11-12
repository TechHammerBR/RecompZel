"""The launcher's update never calls a string method on a release asset's bytes.

GitHub serves release assets as application/octet-stream, so in Windows PowerShell 5.1 Invoke-WebRequest's .Content is
byte[] there, and member enumeration turns .Trim() into a call on each System.Byte: the update button of 2026-11-11
died with "[System.Byte] nao contem um metodo denominado 'Trim'" before checking the hash. The sha256 read decodes
byte[] first; no other .Content of an Invoke-WebRequest takes a string method directly.

python -I -B tests/test_launcher_update_sha.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    text = (ROOT / "recompzel/launcher.ps1").read_text(encoding="ascii")
    bad = re.findall(r"\.Content\)?\.(?:Trim|Split|Replace|ToLower|ToUpper)\(", text)
    assert not bad, f"launcher.ps1 calls a string method on .Content, byte[] for a release asset: {bad}"
    assert "[Text.Encoding]::ASCII.GetString($resp.Content)" in text, "launcher.ps1: the sha256 bytes are not decoded"
    assert re.search(r"\$shaTxt = if \(\$resp\.Content -is \[byte\[\]\]\)", text), \
        "launcher.ps1: no byte[] guard on the sha256 response"
    assert "$want = $shaTxt.Trim().Split(' ')[0]" in text, "launcher.ps1: the hash is not read from the decoded text"
    print("launcher update: the sha256 asset is decoded before any string method")


if __name__ == "__main__":
    main()
