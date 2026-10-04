"""Tên giọng trong app là tên VieNeu hiện hành (chủ sách 29-09): VieNeu 3.8.2 đổi tên ba giọng Turbo; app dùng thẳng tên mới
làm khoá ở mọi nơi (bảng giọng, bảng cân bằng, giao diện), không bí danh, không đổi qua lại."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from abook.voice_catalog import narrator_presets
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences
from abook.webui.server import App

RENAMED = {"Minh Quân Pro": "Hải Đăng", "Anh Khôi": "Thiện Minh", "Mạnh Dũng": "Quốc Tuấn"}


def test_the_catalog_knows_the_voices_only_by_their_vieneu_names() -> None:
    names = {str(preset["name"]) for preset in narrator_presets()}
    assert set(RENAMED.values()) <= names
    assert not names & set(RENAMED), "tên cũ không còn trong bảng giọng"


def test_the_narrator_list_shows_only_the_new_names(tmp_path: Path) -> None:
    app = App(preferences=Preferences(tmp_path / "prefs.json"), runner=FakeRunner(), token="t")
    shown = {voice["name"] for voice in app.voices()}
    assert set(RENAMED.values()) <= shown
    assert not shown & set(RENAMED), "tên cũ không còn ra giao diện"


def test_every_catalog_voice_is_a_voice_vieneu_has() -> None:
    spec = importlib.util.find_spec("vieneu")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("máy này không có gói vieneu")
    listing = Path(next(iter(spec.submodule_search_locations))) / "assets" / "voices_v3_turbo.json"
    if not listing.is_file():
        pytest.skip("gói vieneu không mang danh sách giọng Turbo")
    theirs = set(json.loads(listing.read_text(encoding="utf-8"))["presets"])
    ours = {str(preset["name"]) for preset in narrator_presets()}
    assert ours <= theirs, sorted(ours - theirs)
