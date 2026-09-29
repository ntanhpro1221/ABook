"""Tên giọng hiển thị như VieNeu hiện hành (chủ sách 29-09): VieNeu 3.8.3 đổi tên ba giọng; dữ liệu sách và bảng giọng
vẫn dùng tên cũ làm khoá, giao diện thấy tên mới và gửi tên mới về."""
from __future__ import annotations

from pathlib import Path

from ebook_reader.voice_catalog import narrator_presets
from ebook_reader.webui import humanize
from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.library import Preferences
from ebook_reader.webui.server import App


def test_a_renamed_voice_goes_out_under_its_vieneu_name_and_comes_back_as_its_key() -> None:
    assert humanize.VOICE_LABELS == {"Anh Khôi": "Thiện Minh", "Minh Quân Pro": "Hải Đăng", "Mạnh Dũng": "Quốc Tuấn"}
    for key, label in humanize.VOICE_LABELS.items():
        assert humanize.voice_label(key) == label and humanize.voice_key(label) == key
    # VieNeu vẫn gọi đúng những tên này (kể cả "Adam bựa", giọng nó xếp đầu) - giữ nguyên.
    for name in ("Adam bựa", "Đức Trí", "Phạm Tuyên", ""):
        assert humanize.voice_label(name) == name == humanize.voice_key(name)


def test_the_narrator_list_shows_only_the_new_names(tmp_path: Path) -> None:
    app = App(preferences=Preferences(tmp_path / "prefs.json"), runner=FakeRunner(), token="t")
    shown = {voice["name"] for voice in app.voices()}
    renamed = set(humanize.VOICE_LABELS) & {str(preset["name"]) for preset in narrator_presets()}
    assert not shown & renamed, "tên cũ không còn ra giao diện"
    assert {humanize.VOICE_LABELS[name] for name in renamed} <= shown
