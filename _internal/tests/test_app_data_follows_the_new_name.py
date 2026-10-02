"""Thư mục dữ liệu của app mang tên mới (%LOCALAPPDATA%/ABook); dữ liệu ở thư mục tên cũ ("Ebook Reader") chuyển
sang một lần, không bao giờ đè bản đã có ở thư mục mới, và không đụng bộ nhớ đệm của trình duyệt nhúng."""
from __future__ import annotations

from pathlib import Path

import pytest

from abook.webui import library


@pytest.fixture()
def local_app_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("ABOOK_PREFERENCES", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def test_the_app_data_folder_carries_the_app_name(local_app_data: Path) -> None:
    assert library.preferences_path() == local_app_data / "ABook" / "preferences.json"


def test_files_under_the_old_name_move_once(local_app_data: Path) -> None:
    legacy = local_app_data / "Ebook Reader"
    (legacy / "cache").mkdir(parents=True)
    (legacy / "preferences.json").write_text('{"theme": "dark"}', encoding="utf-8")
    (legacy / "listening.json").write_text('{"version": 2}', encoding="utf-8")
    (legacy / "devices.json").write_text("{}", encoding="utf-8")

    path = library.preferences_path()

    assert path.read_text(encoding="utf-8") == '{"theme": "dark"}'
    assert (path.parent / "listening.json").is_file() and (path.parent / "devices.json").is_file()
    assert not (legacy / "preferences.json").exists() and (legacy / "cache").is_dir(), "chỉ file của app đi"
    assert library.Preferences().get()["theme"] == "dark"


def test_a_file_already_under_the_new_name_is_never_overwritten(local_app_data: Path) -> None:
    legacy = local_app_data / "Ebook Reader"
    legacy.mkdir()
    (legacy / "preferences.json").write_text('{"theme": "dark"}', encoding="utf-8")
    (legacy / "listening.json").write_text("cu", encoding="utf-8")
    fresh = local_app_data / "ABook"
    fresh.mkdir()
    (fresh / "listening.json").write_text("moi", encoding="utf-8")

    library.preferences_path()

    assert (fresh / "listening.json").read_text(encoding="utf-8") == "moi"
    assert (fresh / "preferences.json").is_file() and (legacy / "listening.json").read_text(encoding="utf-8") == "cu"


def test_the_override_still_wins(local_app_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_PREFERENCES", str(local_app_data / "thu" / "prefs.json"))
    assert library.preferences_path() == local_app_data / "thu" / "prefs.json"
    assert not (local_app_data / "ABook").exists()
