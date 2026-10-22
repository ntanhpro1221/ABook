"""a93 #4: một cuốn hỏng không làm cả /sync/v1/library trả lỗi."""
from __future__ import annotations

import shutil

from abook.webui import export
from abook.webui.library import book_id
from abook.webui.sync import Devices, SyncApp
from tests.test_webui_listen_and_sync import library  # noqa: F401


def test_one_broken_book_is_skipped_and_the_rest_are_listed(library, tmp_path, monkeypatch):
    lib, project, listening = library
    broken = project.parent / "sach_hong"
    shutil.copytree(project, broken)
    app = SyncApp(lib, listening, Devices(tmp_path / "devices.json"), "May nay")
    assert {entry["id"] for entry in app.library_view()} == {book_id(project), book_id(broken)}
    real = export.audio_bytes

    def audio_bytes(paths, *a, **k):
        if broken in list(paths):
            raise PermissionError("file đang bị khoá")
        return real(paths, *a, **k)

    monkeypatch.setattr(export, "audio_bytes", audio_bytes)
    assert [entry["id"] for entry in app.library_view()] == [book_id(project)]
