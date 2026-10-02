"""Thư mục dữ liệu của app mang tên app (%LOCALAPPDATA%/ABook); biến ABOOK_PREFERENCES ghi đè."""
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


def test_the_override_still_wins(local_app_data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABOOK_PREFERENCES", str(local_app_data / "thu" / "prefs.json"))
    assert library.preferences_path() == local_app_data / "thu" / "prefs.json"
    assert not (local_app_data / "ABook").exists()
