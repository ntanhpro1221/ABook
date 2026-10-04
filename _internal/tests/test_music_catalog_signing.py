"""Danh mục nhạc nền có chữ ký (webui/music_catalog.py): mục lục ký Ed25519, `issued` không lùi, mọi mảnh phải khớp sha256 trong `files`.
Bộ ca dùng chung với test Kotlin: tests/fixtures/catalog_signing/ (khoá TEST, xem README ở đó)."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from abook.webui.ed25519_verify import verify_base64
from abook.webui.music_catalog import CatalogError, MusicCatalog, shard_of
from tests.catalog_signing import FIXTURE, TEST_PUBLIC_KEY

CALM = "https://x/calm.mp3"
BATTLE = "https://x/battle.mp3"
CASES = json.loads((FIXTURE / "cases.json").read_text(encoding="utf-8"))


def _cloud(tmp_path: Path, *cases: str) -> Path:
    """Nguồn danh mục: chép `good/` rồi phủ lần lượt các thư mục ca."""
    cloud = tmp_path / "cloud"
    if not cloud.exists():
        shutil.copytree(FIXTURE / "good", cloud)
    for case in cases:
        shutil.copytree(FIXTURE / case, cloud, dirs_exist_ok=True)
    return cloud


def _catalog(tmp_path: Path, cloud: Path) -> MusicCatalog:
    return MusicCatalog(tmp_path / "cache", str(cloud), public_key=TEST_PUBLIC_KEY)


def test_a_signed_catalog_is_read_and_its_bytes_and_signature_are_kept(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, _cloud(tmp_path))
    assert catalog.manifest()["revision"] == CASES["good"]["revision"]
    assert set(catalog.lookup([CALM, BATTLE])) == {CALM, BATTLE}
    for name in ("manifest.json", "manifest.json.sig"):
        assert (tmp_path / "cache" / name).read_bytes() == (FIXTURE / "good" / name).read_bytes(), "cất nguyên byte gốc + chữ ký"


def test_the_app_key_does_not_accept_a_catalog_signed_with_the_test_key(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="chữ ký"):
        MusicCatalog(tmp_path / "cache", str(_cloud(tmp_path))).manifest()


@pytest.mark.parametrize("case", ["bad_signature", "tampered_manifest"])
def test_a_first_start_refuses_a_manifest_with_a_bad_signature_and_keeps_nothing(tmp_path: Path, case: str) -> None:
    catalog = _catalog(tmp_path, _cloud(tmp_path, case))
    with pytest.raises(CatalogError, match="chữ ký"):
        catalog.manifest()
    assert not (tmp_path / "cache" / "manifest.json").exists()


def test_a_bad_signature_later_keeps_the_catalog_already_downloaded(tmp_path: Path) -> None:
    cloud = _cloud(tmp_path)
    catalog = _catalog(tmp_path, cloud)
    assert catalog.manifest()["revision"] == "r1"
    for case in ("bad_signature", "tampered_manifest"):
        _cloud(tmp_path, case)
        assert catalog.manifest(refresh=True)["revision"] == "r1"
        assert CALM in catalog.lookup([CALM])
        assert (tmp_path / "cache" / "manifest.json").read_bytes() == (FIXTURE / "good" / "manifest.json").read_bytes()
        _cloud(tmp_path, "good")  # lại bản tốt


def test_an_older_signed_manifest_cannot_roll_the_catalog_back(tmp_path: Path) -> None:
    cloud = _cloud(tmp_path)
    catalog = _catalog(tmp_path, cloud)
    assert catalog.manifest()["issued"] == CASES["good"]["issued"]
    _cloud(tmp_path, "older")
    assert catalog.manifest(refresh=True)["revision"] == "r1", "bản cũ hơn có chữ ký đúng vẫn bị bỏ"
    _cloud(tmp_path, "newer")
    assert catalog.manifest(refresh=True)["revision"] == "r2"
    _cloud(tmp_path, "good")
    assert _catalog(tmp_path, cloud).manifest(refresh=True)["revision"] == "r2", "cả sau khi khởi động lại: mốc nằm trong bản đã cất"


def test_the_cached_manifest_is_verified_again_when_read(tmp_path: Path) -> None:
    cloud = _cloud(tmp_path)
    _catalog(tmp_path, cloud).manifest()
    cached = tmp_path / "cache" / "manifest.json"
    raw = bytearray(cached.read_bytes())
    raw[raw.index(b'"r1"') + 2] = ord("9")
    cached.write_bytes(bytes(raw))
    shutil.rmtree(cloud)  # mất mạng
    with pytest.raises(CatalogError):
        _catalog(tmp_path, cloud).manifest()
    assert (tmp_path / "cache" / "manifest.json").read_bytes() == bytes(raw), "không đè lên khi không có bản tốt hơn"


def test_a_part_that_does_not_match_its_sha256_is_not_used(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    catalog = _catalog(tmp_path, _cloud(tmp_path, "tampered_part"))
    with caplog.at_level(logging.WARNING):
        found = catalog.lookup([CALM, BATTLE])
    assert set(found) == {BATTLE}, "link của mảnh bị tráo coi như không có - không bao giờ có link lạ"
    assert "https://y/calm.mp3" not in json.dumps(found)
    assert CASES["tampered_part"]["file"] in caplog.text
    assert not (tmp_path / "cache" / "r1" / CASES["tampered_part"]["file"]).exists(), "mảnh hỏng không được cất"


def test_a_part_missing_from_the_signed_files_is_not_used(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    catalog = _catalog(tmp_path, _cloud(tmp_path, "unlisted_part"))
    with caplog.at_level(logging.WARNING):
        found = catalog.lookup([CALM, BATTLE])
    assert set(found) == {BATTLE}
    assert CASES["unlisted_part"]["unlisted"] in caplog.text


def test_cells_are_checked_like_tracks(tmp_path: Path) -> None:
    cloud = _cloud(tmp_path)
    catalog = _catalog(tmp_path, cloud)
    cell = next((cloud / "cells").glob("*.json"))
    cell.write_bytes(cell.read_bytes().replace(b"https://x/", b"https://y/"))
    v, a = (int(part) for part in cell.stem.split("_"))
    assert catalog.cell(v, a) == [], "ô bị sửa: bỏ"
    assert catalog.cell(*(int(part) for part in next(path for path in (cloud / "cells").glob("*.json") if path != cell).stem.split("_")))


def test_a_cached_part_that_was_changed_on_disk_is_downloaded_again(tmp_path: Path) -> None:
    cloud = _cloud(tmp_path)
    assert CALM in _catalog(tmp_path, cloud).lookup([CALM])
    cached = tmp_path / "cache" / "r1" / "tracks" / f"{shard_of(CALM)}.json"
    cached.write_bytes(cached.read_bytes().replace(CALM.encode(), b"https://y/calm.mp3"))
    found = _catalog(tmp_path, cloud).lookup([CALM])
    assert list(found) == [CALM], "mảnh đã cất bị sửa trên đĩa: tải lại bản đúng"
    assert cached.read_bytes() == (FIXTURE / "good" / "tracks" / cached.name).read_bytes()
    shutil.rmtree(cloud)  # mất mạng, mảnh cất lại hỏng: bỏ chứ không dùng
    cached.write_bytes(b"{}")
    with pytest.raises(CatalogError, match="mạng"):
        _catalog(tmp_path, cloud).lookup([CALM])


def test_verify_base64_rejects_garbage_instead_of_raising() -> None:
    raw, signature = (FIXTURE / "good" / "manifest.json").read_bytes(), (FIXTURE / "good" / "manifest.json.sig").read_bytes()
    assert verify_base64(TEST_PUBLIC_KEY, raw, signature)
    assert not verify_base64(TEST_PUBLIC_KEY, raw, b"khong phai base64!!")
    assert not verify_base64(TEST_PUBLIC_KEY, raw, b"")
    assert not verify_base64(TEST_PUBLIC_KEY, raw + b" ", signature)
