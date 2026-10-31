"""Kiểm chữ ký cập nhật (.sig minisign của `tauri signer sign`) của một file, bằng khoá công khai trong tauri.conf.json.

File .sig là base64 của bản chữ ký minisign 4 dòng: chú thích, chữ ký ("ED" = Ed25519 trên BLAKE2b-512 của file, 8 byte mã
khoá, 64 byte chữ ký), dòng "trusted comment", và chữ ký chung trên (chữ ký + trusted comment). Khoá công khai cũng là base64
của 2 dòng: chú thích, rồi "Ed" + 8 byte mã khoá + 32 byte khoá. Ed25519 là abook/webui/ed25519_verify.py (Python thuần).

minisign_verify.py <file> [--sig <file>.sig] [--pubkey <base64>] [--version <ver>]  -> SIG_OK / SIG_FAIL, mã 0 / 1
"""
import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

INTERNAL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(INTERNAL))
from abook.webui.ed25519_verify import verify  # noqa: E402

TAURI_CONF = INTERNAL / "shell" / "src-tauri" / "tauri.conf.json"


def _lines(blob: str) -> list[str]:
    return base64.b64decode(blob.strip()).decode("utf-8").splitlines()


def public_key(blob: str) -> tuple[bytes, bytes]:
    """(mã khoá 8 byte, khoá 32 byte)."""
    raw = base64.b64decode(_lines(blob)[1])
    if len(raw) != 42 or raw[:2] != b"Ed":
        raise ValueError("khoá công khai không phải minisign Ed25519")
    return raw[2:10], raw[10:]


def signature_ok(data: bytes, signature_blob: str, key_blob: str, version: str | None = None) -> bool:
    """Chữ ký đúng; có `version` thì trusted comment (phần được ký) còn phải ghi đúng "version:<version>"."""
    key_id, key = public_key(key_blob)
    lines = _lines(signature_blob)
    if len(lines) < 4 or not lines[2].startswith("trusted comment: "):
        return False
    raw = base64.b64decode(lines[1])
    if len(raw) != 74 or raw[2:10] != key_id:
        return False
    algorithm, signature = raw[:2], raw[10:]
    # "ED": chữ ký trên BLAKE2b-512 của file (mặc định của minisign mới và của tauri signer); "Ed": trên chính file.
    message = hashlib.blake2b(data, digest_size=64).digest() if algorithm == b"ED" else data if algorithm == b"Ed" else None
    if message is None or not verify(key, message, signature):
        return False
    trusted = lines[2][len("trusted comment: "):].encode("utf-8")
    if version is not None and f"version:{version}".encode() not in trusted.split(b"\t"):
        return False
    return verify(key, signature + trusted, base64.b64decode(lines[3]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--sig", type=Path)
    ap.add_argument("--pubkey")
    ap.add_argument("--version", help="đòi trusted comment ghi version:<bản này>")
    args = ap.parse_args()
    key = args.pubkey or json.loads(TAURI_CONF.read_text(encoding="utf-8"))["plugins"]["updater"]["pubkey"]
    sig = (args.sig or args.file.with_name(args.file.name + ".sig")).read_text(encoding="utf-8")
    ok = signature_ok(args.file.read_bytes(), sig, key, args.version)
    print(("SIG_OK " if ok else "SIG_FAIL ") + str(args.file))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
