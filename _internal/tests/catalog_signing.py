"""Ký danh mục nhạc nền cho test, và sinh bộ fixture dùng chung với test Kotlin (tests/fixtures/catalog_signing/, xem README ở đó).

Khoá ở đây CHỈ DÙNG CHO TEST - cặp khoá riêng sinh cho bài kiểm này, không liên quan khoá ký thật của ABook (khoá thật nằm ở kho riêng
tư, không bao giờ vào repo). Hạt (seed) công khai ngay trong file này nên ai cũng ký lại được - đó là chủ ý: test dựng danh mục tại chỗ
rồi ký bằng khoá test, `MusicCatalog(..., public_key=TEST_PUBLIC_KEY)` kiểm bằng khoá test.

    python -m tests.catalog_signing     # sinh lại tests/fixtures/catalog_signing/ (Ed25519 tất định: chạy lại ra đúng byte cũ)
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from abook.webui.music_catalog import cell_of, shard_of

TEST_SEED = bytes.fromhex("eecd965d055fce740ce5e700b816f675e8e4c2457ca72f7b764fbde8f441329d")
_KEY = Ed25519PrivateKey.from_private_bytes(TEST_SEED)
TEST_PUBLIC_KEY = _KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
ISSUED = "2026-10-04T00:00:00Z"
FIXTURE = Path(__file__).parent / "fixtures" / "catalog_signing"


def sign(raw: bytes) -> bytes:
    """Nội dung file `.sig`: chữ ký Ed25519 trên đúng các byte `raw`, base64, một dòng."""
    return base64.b64encode(_KEY.sign(raw)) + b"\n"


def write_signed_manifest(root: Path, manifest: dict[str, Any], *, parts_root: Path | None = None, unlisted: tuple[str, ...] = ()) -> None:
    """Điền `files` (sha256 của mọi tracks/*.json và cells/*.json trong `parts_root`, mặc định `root`; trừ `unlisted`), ghi manifest.json
    + manifest.json.sig vào `root`."""
    source = parts_root or root
    files = {f"{folder}/{path.name}": hashlib.sha256(path.read_bytes()).hexdigest()
             for folder in ("tracks", "cells") for path in sorted((source / folder).glob("*.json"))
             if f"{folder}/{path.name}" not in unlisted}
    raw = json.dumps({**manifest, "files": files}, ensure_ascii=False, indent=1).encode("utf-8")
    (root / "manifest.json").write_bytes(raw)
    (root / "manifest.json.sig").write_bytes(sign(raw))


def write_catalog(root: Path, tracks: dict[str, dict], *, revision: str = "r1", issued: str = ISSUED, **extra: Any) -> Path:
    """Dựng một danh mục có chữ ký trong `root`: mảnh `tracks/<xx>.json`, `cells/<v>_<a>.json`, manifest.json + .sig."""
    for folder in ("tracks", "cells"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    shards: dict[str, dict] = {}
    cells: dict[str, list] = {}
    for link, track in tracks.items():
        shards.setdefault(shard_of(link), {})[link] = track
        v, a = cell_of(track["valence"], track["arousal"])
        cells.setdefault(f"{v}_{a}", []).append({"link": link, **track})
    for shard, data in shards.items():
        (root / "tracks" / f"{shard}.json").write_bytes(json.dumps(data).encode("utf-8"))
    for cell, items in cells.items():
        (root / "cells" / f"{cell}.json").write_bytes(json.dumps(items).encode("utf-8"))
    write_signed_manifest(root, {
        "format": "abook-music-catalog", "version": 1, "revision": revision, "issued": issued, "grid": 5,
        "shards": sorted(shards), "cells": {cell: len(items) for cell, items in cells.items()}, **extra})
    return root


def build_fixture(target: Path = FIXTURE) -> None:
    """`good/` là danh mục đầy đủ; các thư mục còn lại chỉ mang file KHÁC `good/` (test chép `good/` rồi phủ thư mục ca lên trên)."""
    from tests.test_music_catalog_and_select import TRACKS

    for child in target.iterdir() if target.exists() else ():
        if child.is_dir():
            shutil.rmtree(child)
    good = write_catalog(target / "good", TRACKS)
    raw, signature = (good / "manifest.json").read_bytes(), (good / "manifest.json.sig").read_bytes()
    unsigned = {key: value for key, value in json.loads(raw).items() if key != "files"}

    def put(name: str, relative: str, content: bytes) -> None:
        path = target / name / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    # Mục lục ký hợp lệ nhưng khác `good/`: bản mới hơn, bản cũ hơn, bản quên liệt kê một mảnh.
    calm_shard = f"tracks/{shard_of('https://x/calm.mp3')}.json"
    for name, changes, unlisted in (("newer", {"revision": "r2", "issued": "2026-10-05T00:00:00Z"}, ()),
                                    ("older", {"revision": "r0", "issued": "2026-10-01T00:00:00Z"}, ()),
                                    ("unlisted_part", {"revision": "r3"}, (calm_shard,))):
        (target / name).mkdir()
        write_signed_manifest(target / name, {**unsigned, **changes}, parts_root=good, unlisted=unlisted)
    # Kẻ tấn công: chữ ký lật một bit, mục lục sửa một byte (chữ ký cũ), mảnh bị tráo link (mục lục nguyên vẹn).
    flipped = bytearray(base64.b64decode(signature.strip()))
    flipped[10] ^= 0x01
    put("bad_signature", "manifest.json", raw)
    put("bad_signature", "manifest.json.sig", base64.b64encode(bytes(flipped)) + b"\n")
    changed = bytearray(raw)
    changed[raw.index(b'"r1"') + 2] = ord("9")  # revision "r1" -> "r9"
    put("tampered_manifest", "manifest.json", bytes(changed))
    put("tampered_manifest", "manifest.json.sig", signature)
    shard_data = (good / calm_shard).read_bytes()
    assert b'"https://x/calm.mp3"' in shard_data
    put("tampered_part", calm_shard, shard_data.replace(b'"https://x/calm.mp3"', b'"https://y/calm.mp3"'))
    (target / "public_key.hex").write_bytes(TEST_PUBLIC_KEY.hex().encode("ascii") + b"\n")
    (target / "test_private_seed.hex").write_bytes(TEST_SEED.hex().encode("ascii") + b"\n")
    (target / "cases.json").write_bytes(json.dumps({
        "good": {"revision": "r1", "issued": ISSUED},
        "newer": {"revision": "r2", "issued": "2026-10-05T00:00:00Z"},
        "older": {"revision": "r0", "issued": "2026-10-01T00:00:00Z"},
        "tampered_part": {"file": calm_shard, "lostLinks": sorted(json.loads(shard_data))},
        "unlisted_part": {"revision": "r3", "unlisted": calm_shard, "lostLinks": sorted(json.loads(shard_data))},
    }, indent=1).encode("utf-8") + b"\n")


if __name__ == "__main__":
    build_fixture()
    print(f"generated {FIXTURE}")
