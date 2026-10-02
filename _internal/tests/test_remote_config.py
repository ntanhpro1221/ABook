"""Cấu hình từ xa (webui/remote_config.py): chỉ nhận file có chữ ký đúng, không quay lui về bản cũ, mất mạng vẫn chạy."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from abook.webui.ed25519_verify import verify  # noqa: E402
from abook.webui.remote_config import DEFAULTS, PUBLIC_KEY, RemoteConfig  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _key() -> tuple[Ed25519PrivateKey, bytes]:
    key = Ed25519PrivateKey.generate()
    return key, key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _publish(folder: Path, key: Ed25519PrivateKey, issued: str, catalog: str, **extra) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"format": "abook-remote-config", "version": 1, "issued": issued,
                      "music": {"catalogs": [catalog]}, **extra}).encode("utf-8")
    (folder / "remote-config.json").write_bytes(raw)
    (folder / "remote-config.json.sig").write_bytes(base64.b64encode(key.sign(raw)))
    return str(folder / "remote-config.json")


def test_a_signed_config_moves_the_catalog_without_an_app_update(tmp_path: Path) -> None:
    key, public = _key()
    source = _publish(tmp_path / "github", key, "2026-10-02T01:00:00Z", "https://moi.example/")
    config = RemoteConfig(tmp_path / "cache", sources=(source,), public_key=public)
    assert config.music_catalogs() == ["https://moi.example/"]


def test_a_config_signed_by_someone_else_is_ignored(tmp_path: Path) -> None:
    mine, public = _key()
    stranger, _ = _key()
    source = _publish(tmp_path / "github", stranger, "2026-10-02T01:00:00Z", "https://ke-xau.example/")
    config = RemoteConfig(tmp_path / "cache", sources=(source,), public_key=public)
    assert config.music_catalogs() == DEFAULTS["music"]["catalogs"]


def test_an_older_signed_file_cannot_roll_the_app_back(tmp_path: Path) -> None:
    key, public = _key()
    cache = tmp_path / "cache"
    new = _publish(tmp_path / "new", key, "2026-10-05T00:00:00Z", "https://moi.example/")
    assert RemoteConfig(cache, sources=(new,), public_key=public).music_catalogs() == ["https://moi.example/"]
    old = _publish(tmp_path / "old", key, "2026-10-01T00:00:00Z", "https://cu.example/")
    assert RemoteConfig(cache, sources=(old,), public_key=public).music_catalogs() == ["https://moi.example/"]


def test_offline_uses_the_last_good_config_then_the_built_in_one(tmp_path: Path) -> None:
    key, public = _key()
    cache = tmp_path / "cache"
    source = _publish(tmp_path / "github", key, "2026-10-02T01:00:00Z", "https://moi.example/")
    RemoteConfig(cache, sources=(source,), public_key=public).get()
    gone = str(tmp_path / "khong_co" / "remote-config.json")
    assert RemoteConfig(cache, sources=(gone,), public_key=public).music_catalogs() == ["https://moi.example/"]
    assert RemoteConfig(tmp_path / "trong", sources=(gone,), public_key=public).music_catalogs() == \
        DEFAULTS["music"]["catalogs"]


def test_a_newer_format_is_left_for_a_newer_app(tmp_path: Path) -> None:
    key, public = _key()
    folder = tmp_path / "github"
    folder.mkdir()
    raw = json.dumps({"format": "abook-remote-config", "version": 99, "issued": "2027-01-01T00:00:00Z",
                      "music": {"catalogs": ["https://tuong-lai.example/"]}}).encode()
    (folder / "remote-config.json").write_bytes(raw)
    (folder / "remote-config.json.sig").write_bytes(base64.b64encode(key.sign(raw)))
    config = RemoteConfig(tmp_path / "cache", sources=(str(folder / "remote-config.json"),), public_key=public)
    assert config.music_catalogs() == DEFAULTS["music"]["catalogs"]


def test_the_published_config_is_signed_by_the_app_key() -> None:
    raw = (REPO / "remote-config" / "remote-config.json").read_bytes()
    signature = base64.b64decode((REPO / "remote-config" / "remote-config.json.sig").read_bytes().strip())
    assert verify(PUBLIC_KEY, raw, signature), "sửa remote-config.json mà chưa ký lại (scripts/sign_remote_config.py)"
