"""Chữ ký cập nhật minisign (webui/minisign_verify.py): chữ ký đúng qua; chữ ký sai, khoá sai, file sửa một byte, bản khác, định dạng
hỏng đều bị từ chối. Ca thật: .sig của bộ cài 0.4.149 (tauri bundle) với khoá công khai trong shell/src-tauri/tauri.conf.json -
lưu mã BLAKE2b-512 của bộ cài thay vì cả file 20 MB (chữ ký "ED" ký trên chính mã ấy)."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from abook.webui.minisign_verify import digest_ok, file_ok, public_key, signature_ok

INTERNAL = Path(__file__).resolve().parents[1]
UPDATER_KEY = json.loads((INTERNAL / "shell/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["plugins"]["updater"]["pubkey"]

# ABook_0.4.149_x64-setup.exe (phát hành 31-10): BLAKE2b-512 và .sig nguyên văn.
REAL_DIGEST = bytes.fromhex(
    "90636eddb25ce4672687ff5ca1bceeedbe4ac442eec19d299cf3e398a4ead8b1b3414049aaa97321cee5a0658176e1e2398f6d1c1f5779de15d8a39eb195c4a4")
REAL_SIG = (
    "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkKUlVRbGsyK1h1SFdFM2F1ZEtWVXhzQU8wdjRRbHNwK1NjRzZlV2hxUit5U3ZV"
    "NUVTTUlwdkpCNFRXQkErQW9NaUFzM0xaalJvK0hXdGxjOWNyV1AxdE5ZTWVuT2hxT1NEdUFVPQp0cnVzdGVkIGNvbW1lbnQ6IHRpbWVzdGFtcDoxNzkzNDMxNDUzCWZp"
    "bGU6QUJvb2tfMC40LjE0OV94NjQtc2V0dXAuZXhlCXZlcnNpb246MC40LjE0OQpsd0U1NmRpYTdIcHp3RE51cE90YnluZzdLNEpiUlM5RUpsZCtJM1poaWd0bjg0YXlz"
    "MUpvZVVlWWRoMVQxVWFHS2R4ZUV3SnVvWkVPc0dhK3lVQkFDdz09Cg==")

DATA = b"ABook test installer \x00\x01\x02" * 100


def _b64(*lines: str) -> str:
    return base64.b64encode(("\n".join(lines) + "\n").encode()).decode()


def _key(key_id: bytes = b"testkey1") -> tuple[Ed25519PrivateKey, str]:
    secret = Ed25519PrivateKey.generate()
    raw = secret.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return secret, _b64("untrusted comment: minisign public key", base64.b64encode(b"Ed" + key_id + raw).decode())


def _sign(secret: Ed25519PrivateKey, data: bytes, trusted: str = "timestamp:1\tfile:x.exe\tversion:1.2.3",
          key_id: bytes = b"testkey1", algorithm: bytes = b"ED") -> str:
    message = hashlib.blake2b(data, digest_size=64).digest() if algorithm == b"ED" else data
    signature = secret.sign(message)
    return _b64("untrusted comment: signature from tauri secret key",
                base64.b64encode(algorithm + key_id + signature).decode(),
                "trusted comment: " + trusted,
                base64.b64encode(secret.sign(signature + trusted.encode())).decode())


def test_good_signature_passes_with_and_without_version():
    secret, key = _key()
    sig = _sign(secret, DATA)
    assert signature_ok(DATA, sig, key)
    assert signature_ok(DATA, sig, key, version="1.2.3")
    assert digest_ok(hashlib.blake2b(DATA, digest_size=64).digest(), sig, key, version="1.2.3")


def test_signature_on_the_file_itself_is_refused():
    """Kiểu "Ed" của minisign (ký thẳng trên file): tauri không tạo, bộ kiểm không nhận - dù chữ ký đúng."""
    secret, key = _key()
    assert not signature_ok(DATA, _sign(secret, DATA, algorithm=b"Ed"), key)


def test_file_changed_by_one_byte_is_refused():
    secret, key = _key()
    sig = _sign(secret, DATA)
    for at in (0, len(DATA) // 2, len(DATA) - 1):
        changed = bytearray(DATA)
        changed[at] ^= 0x01
        assert not signature_ok(bytes(changed), sig, key)
    assert not signature_ok(DATA + b"\x00", sig, key)


def test_wrong_key_is_refused():
    secret, _key_a = _key()
    _other, key_b = _key()  # cùng mã khoá, khoá khác
    assert not signature_ok(DATA, _sign(secret, DATA), key_b)
    _third, key_c = _key(b"otherkey")  # mã khoá khác
    assert not signature_ok(DATA, _sign(secret, DATA), key_c)


def test_key_id_must_match_even_with_the_right_key():
    secret, key = _key()
    raw = base64.b64decode(base64.b64decode(key).decode().splitlines()[1])
    relabelled = _b64("untrusted comment: minisign public key", base64.b64encode(b"Ed" + b"otherkey" + raw[10:]).decode())
    assert signature_ok(DATA, _sign(secret, DATA), key)
    assert not signature_ok(DATA, _sign(secret, DATA), relabelled)


def test_wrong_signature_is_refused():
    secret, key = _key()
    raw = base64.b64decode(_sign(secret, DATA)).decode().splitlines()
    sig_bytes = bytearray(base64.b64decode(raw[1]))
    sig_bytes[20] ^= 0x80
    assert not signature_ok(DATA, _b64(raw[0], base64.b64encode(bytes(sig_bytes)).decode(), raw[2], raw[3]), key)
    # Chữ ký chung sai: trusted comment bị sửa (đổi phiên bản) mà chữ ký file vẫn đúng.
    assert not signature_ok(DATA, _b64(raw[0], raw[1], raw[2].replace("1.2.3", "9.9.9"), raw[3]), key)


def test_signature_of_another_version_is_refused():
    secret, key = _key()
    assert not signature_ok(DATA, _sign(secret, DATA), key, version="1.2.4")
    assert not signature_ok(DATA, _sign(secret, DATA, trusted="timestamp:1\tfile:x.exe"), key, version="1.2.3")
    assert not signature_ok(DATA, _sign(secret, DATA, trusted="timestamp:1\tversion:1.2.30"), key, version="1.2.3")


@pytest.mark.parametrize("broken", [
    "", "không phải base64 !!", base64.b64encode(b"one line\n").decode(),
    _b64("c", "RUQ=", "trusted comment: x", "AAAA"),  # chữ ký quá ngắn
    _b64("c", base64.b64encode(b"XX" + b"testkey1" + b"\0" * 64).decode(), "trusted comment: x",
         base64.b64encode(b"\0" * 64).decode()),  # thuật toán lạ
    _b64("c", base64.b64encode(b"ED" + b"testkey1" + b"\0" * 64).decode(), "not trusted: x",
         base64.b64encode(b"\0" * 64).decode()),  # thiếu "trusted comment: "
    _b64("c", base64.b64encode(b"ED" + b"testkey1" + b"\0" * 64).decode(), "trusted comment: x", "%%%"),
])
def test_malformed_signature_is_refused_without_raising(broken):
    _secret, key = _key()
    assert not signature_ok(DATA, broken, key)


@pytest.mark.parametrize("broken", ["", "!!", _b64("c"), _b64("c", base64.b64encode(b"Ed" + b"short").decode()),
                                    _b64("c", base64.b64encode(b"XY" + b"testkey1" + b"\0" * 32).decode())])
def test_malformed_public_key_is_refused_without_raising(broken):
    secret, _key_ok = _key()
    assert public_key(broken) is None
    assert not signature_ok(DATA, _sign(secret, DATA), broken)


def test_file_ok_streams_the_file(tmp_path):
    secret, key = _key()
    path = tmp_path / "setup.exe"
    path.write_bytes(DATA)
    sig = _sign(secret, DATA)
    assert file_ok(path, sig, key, version="1.2.3")
    path.write_bytes(DATA[:-1] + b"?")
    assert not file_ok(path, sig, key)
    assert not file_ok(tmp_path / "missing.exe", sig, key)


def test_real_049_installer_signature():
    assert public_key(UPDATER_KEY) is not None
    assert digest_ok(REAL_DIGEST, REAL_SIG, UPDATER_KEY)
    assert digest_ok(REAL_DIGEST, REAL_SIG, UPDATER_KEY, version="0.4.149")
    assert not digest_ok(REAL_DIGEST, REAL_SIG, UPDATER_KEY, version="0.4.148")
    changed = bytearray(REAL_DIGEST)
    changed[0] ^= 0x01
    assert not digest_ok(bytes(changed), REAL_SIG, UPDATER_KEY)
    _secret, other = _key()
    assert not digest_ok(REAL_DIGEST, REAL_SIG, other)
