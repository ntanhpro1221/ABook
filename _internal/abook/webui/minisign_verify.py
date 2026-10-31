"""Kiểm chữ ký cập nhật: file .sig minisign của `tauri signer sign` / `tauri bundle`, bằng khoá công khai của bộ cập nhật.

File .sig là base64 của bản chữ ký minisign 4 dòng: chú thích, chữ ký ("ED" = Ed25519 trên BLAKE2b-512 của file - kiểu duy nhất
tauri tạo, và kiểu duy nhất được nhận; 8 byte mã khoá; 64 byte chữ ký), dòng "trusted comment: ...", và chữ ký chung trên (chữ ký + trusted comment).
Khoá công khai cũng là base64 của 2 dòng: chú thích, rồi "Ed" + 8 byte mã khoá + 32 byte khoá. Ed25519 là ed25519_verify.py.

Mọi đầu vào hỏng (base64 sai, thiếu dòng, độ dài sai, mã khoá khác) đều là "không hợp lệ", không bao giờ ném lỗi.
"""
import base64
import binascii
import hashlib
from pathlib import Path

from .ed25519_verify import verify

TRUSTED = "trusted comment: "
_CHUNK = 1 << 20


def _lines(blob: str | bytes) -> list[str] | None:
    try:
        text = blob.decode("ascii") if isinstance(blob, bytes) else blob
        return base64.b64decode(text.strip(), validate=True).decode("utf-8").splitlines()
    except (binascii.Error, UnicodeError, ValueError):
        return None


def public_key(blob: str | bytes) -> tuple[bytes, bytes] | None:
    """(mã khoá 8 byte, khoá 32 byte) của khoá công khai minisign; hỏng thì None."""
    lines = _lines(blob)
    try:
        raw = base64.b64decode(lines[1], validate=True) if lines and len(lines) >= 2 else b""
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 42 or raw[:2] != b"Ed":
        return None
    return raw[2:10], raw[10:]


def _parsed(signature_blob: str | bytes, key_id: bytes) -> tuple[bytes, bytes, bytes] | None:
    """(chữ ký 64 byte, trusted comment, chữ ký chung) hay None."""
    lines = _lines(signature_blob)
    if not lines or len(lines) < 4 or not lines[2].startswith(TRUSTED):
        return None
    try:
        raw = base64.b64decode(lines[1], validate=True)
        global_signature = base64.b64decode(lines[3], validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 74 or raw[2:10] != key_id or raw[:2] != b"ED" or len(global_signature) != 64:
        return None
    return raw[10:], lines[2][len(TRUSTED):].encode("utf-8"), global_signature


def _ok(prehashed: bytes | None, data: bytes | None, signature_blob, key_blob, version: str | None) -> bool:
    key = public_key(key_blob)
    if key is None:
        return False
    parsed = _parsed(signature_blob, key[0])
    if parsed is None:
        return False
    signature, trusted, global_signature = parsed
    message = prehashed if prehashed is not None else hashlib.blake2b(data, digest_size=64).digest()
    if not verify(key[1], message, signature):
        return False
    # Có `version`: trusted comment (phần được ký) phải ghi đúng "version:<version>", để chữ ký của bản này không dùng được cho
    # bộ cài bản khác (tauri bundle ghi như vậy; build_windows_qt.ps1 ký với --app-version).
    if version is not None and f"version:{version}".encode() not in trusted.split(b"\t"):
        return False
    return verify(key[1], signature + trusted, global_signature)


def signature_ok(data: bytes, signature_blob: str | bytes, key_blob: str | bytes, version: str | None = None) -> bool:
    return _ok(None, data, signature_blob, key_blob, version)


def digest_ok(blake2b_512: bytes, signature_blob: str | bytes, key_blob: str | bytes, version: str | None = None) -> bool:
    """Như `signature_ok` khi chỉ có BLAKE2b-512 của file."""
    return len(blake2b_512) == 64 and _ok(blake2b_512, None, signature_blob, key_blob, version)


def file_ok(path: Path, signature_blob: str | bytes, key_blob: str | bytes, version: str | None = None) -> bool:
    """Kiểm file `path` mà không đọc cả file vào bộ nhớ (bộ cài vài chục MB)."""
    digest = hashlib.blake2b(digest_size=64)
    try:
        with Path(path).open("rb") as source:
            while chunk := source.read(_CHUNK):
                digest.update(chunk)
    except OSError:
        return False
    return digest_ok(digest.digest(), signature_blob, key_blob, version)
