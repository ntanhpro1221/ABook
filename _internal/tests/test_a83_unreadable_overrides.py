"""Soát a83 B2 (phần ngoài file khoá): overrides.json CÓ mà tạm không đọc được (diệt virus, đồng bộ...) không được coi là "chưa có yêu cầu nào" -
nút Studio và gói sửa từ điện thoại trả 503, KHÔNG ghi lại file chỉ với một yêu cầu mới."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import listener_overrides as lo
from abook.webui import book_wishes, notices
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import App, Server
from tests import book_edits_fixtures as shared
from tests import test_edits_inbox as T
from tests.test_bookfile_music import _plan
from tests.test_listener_speakers import _book
from tests.test_webui_listen_and_sync import FakeRunner, _request


def _lock_out(monkeypatch, name: str = "overrides.json") -> None:
    """Mọi lần đọc `name` đều PermissionError (sharing violation kéo dài); thử lại không chờ."""
    monkeypatch.setattr(notices, "READ_PAUSE_SECONDS", 0)
    for method in ("read_text", "read_bytes"):
        real = getattr(Path, method)

        def locked(self, *args, _real=real, **kwargs):
            if self.name == name:
                raise PermissionError(32, "The process cannot access the file because it is being used by another process")
            return _real(self, *args, **kwargs)

        monkeypatch.setattr(Path, method, locked)


def test_studio_click_is_refused_not_destructive_while_overrides_are_locked(monkeypatch, tmp_path: Path) -> None:
    paths, _db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    for index in range(5):
        lo.request_pronunciation(paths.root, f"Tên{index}", "Tê-nơ", now=1000.0 + index)
    before = (paths.root / lo.OVERRIDES_FILE).read_bytes()
    prefs = Preferences(tmp_path / "prefs" / "preferences.json")
    prefs.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=prefs, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        _lock_out(monkeypatch)
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/pronunciation", headers={"X-Ebook-Token": "t"},
                                   body={"surface": "Mới", "spokenForm": "Mơ-ới"})
        assert status == 503, data
        assert "thử lại" in json.loads(data)["error"]
    finally:
        server.stop()
    monkeypatch.undo()
    assert (paths.root / lo.OVERRIDES_FILE).read_bytes() == before, "5 yêu cầu cũ phải còn nguyên"


def test_fold_refuses_while_overrides_are_locked(monkeypatch, tmp_path: Path) -> None:
    folder = shared.make_base_project(tmp_path)
    _plan(folder)
    lo.request_pronunciation(folder, "Zorba", "Dờ-oóc-ba", now=1000.0)
    before = (folder / lo.OVERRIDES_FILE).read_bytes()
    _lock_out(monkeypatch)
    with pytest.raises(notices.Unreadable):
        book_wishes.fold(folder, T.ONLY_HAILKES, now=T.HAILKES_AT + 600)
    monkeypatch.undo()
    assert (folder / lo.OVERRIDES_FILE).read_bytes() == before


def test_a_broken_overrides_file_is_kept_aside_before_a_new_one_is_written(tmp_path: Path) -> None:
    folder = shared.make_base_project(tmp_path)
    _plan(folder)
    (folder / lo.OVERRIDES_FILE).write_text("{ không phải json", encoding="utf-8")
    book_wishes.guard_overrides(folder)
    assert not (folder / lo.OVERRIDES_FILE).exists()
    assert list(folder.glob(lo.OVERRIDES_FILE + ".hong-*"))
