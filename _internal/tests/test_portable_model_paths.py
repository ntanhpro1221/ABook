"""Một cuốn sách vẫn là cuốn ấy khi runtime của Studio dời chỗ (runtime_contract.relocated_model_path).

Cài đặt khoá theo sách ghi đường dẫn tuyệt đối tới model của runtime đã tạo ra nó. Thư mục dự án đổi tên (`Ebook Reader`
-> `ABook`, 28-09) hay dự án mở từ `.abookproj` ở máy cài Studio chỗ khác thì đường dẫn ấy không còn: trước đây SHA của
checkpoint trong mã băm chính sách thành "MISSING" và sách không làm tiếp được nữa.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ebook_reader.config import build_settings
from ebook_reader.quality_policy import build_quality_policy, quality_policy_hash
from ebook_reader.runtime_contract import relocated_model_path

CHECKPOINT = "fold0_s42_best_model.pth"


def _runtime(root: Path) -> Path:
    (root / "models" / "utmosv2").mkdir(parents=True)
    (root / "models" / "utmosv2" / CHECKPOINT).write_bytes(b"checkpoint bytes")
    (root / "models" / "whisper").mkdir(parents=True)
    (root / "models" / "whisper" / "large-v3-turbo.pt").write_bytes(b"whisper bytes")
    return root


def test_a_path_that_still_exists_is_used_as_stored(tmp_path: Path) -> None:
    old = _runtime(tmp_path / "Ebook Reader" / "runtime")
    new = _runtime(tmp_path / "ABook" / "runtime")
    stored = old / "models" / "utmosv2" / CHECKPOINT
    assert relocated_model_path(str(stored), new) == stored


def test_a_moved_runtime_is_found_under_the_current_one(tmp_path: Path) -> None:
    new = _runtime(tmp_path / "ABook" / "runtime")
    stored = r"D:\Novels\Ebook Reader\_internal\runtime\models\utmosv2" + "\\" + CHECKPOINT
    assert relocated_model_path(stored, new) == new / "models" / "utmosv2" / CHECKPOINT
    assert relocated_model_path(r"D:\Novels\Ebook Reader\_internal\runtime\models\whisper", new) == new / "models" / "whisper"


@pytest.mark.parametrize("stored", [r"D:\khong\co\gi\model.pth", r"D:\Novels\old\runtime\models\utmosv2\khac.pth"])
def test_nothing_found_keeps_the_stored_path_so_callers_fail_closed(tmp_path: Path, stored: str) -> None:
    new = _runtime(tmp_path / "runtime")
    assert str(relocated_model_path(stored, new)) == str(Path(stored))


def test_the_policy_hash_of_a_book_survives_its_runtime_moving(tmp_path: Path, monkeypatch) -> None:
    old = _runtime(tmp_path / "Ebook Reader" / "runtime")
    monkeypatch.setenv("EBOOK_READER_RUNTIME", str(old))
    settings = build_settings(overrides={
        "perceptual_qa": {"checkpoint_path": str(old / "models" / "utmosv2" / CHECKPOINT)},
        "asr": {"download_root": str(old / "models" / "whisper")},
    })
    before = build_quality_policy(settings)
    assert before["settings"]["perceptual_qa"]["checkpoint_sha256"] != "MISSING"

    moved = tmp_path / "ABook" / "runtime"
    moved.parent.mkdir(parents=True)
    shutil.move(str(old), str(moved))
    monkeypatch.setenv("EBOOK_READER_RUNTIME", str(moved))
    after = build_quality_policy(settings)

    assert after["settings"]["perceptual_qa"]["checkpoint_path"] == before["settings"]["perceptual_qa"]["checkpoint_path"]
    assert quality_policy_hash(after) == quality_policy_hash(before)
