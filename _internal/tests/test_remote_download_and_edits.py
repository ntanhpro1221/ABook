"""Sách trên máy tính KHÁC (webui/remote_books.py), hai việc điện thoại đã làm được với máy tính:

- "Tải về máy": tải trọn một cuốn của máy kia về máy này ở nền - đứt giữa chừng (máy kia tắt, bấm dừng) thì giữ phần đã xong, bấm lại
  chỉ lấy phần thiếu; xong thì nghe trọn khi máy kia đã tắt.
- Phần sửa đi về máy giữ sách: máy B sửa một cuốn của máy A (tên, tên chương, cách đọc), phần sửa về tới máy A đúng như từ điện thoại
  (sync.receive_edits -> edits_inbox): sửa "áp ngay" áp liền, ý muốn vào hộp thư chờ chủ máy, xung đột báo như cũ.

Hai máy trong một bài: "máy kia" là cổng đồng bộ thật (SyncServer trên 127.0.0.1) với cuốn thử một chương; "máy này" là App ghép
bằng mã 6 số.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from abook.webui import book_edits, book_wishes, edits_inbox, packages, remote_books, store
from abook.webui.library import Preferences
from abook.webui.listening import Listening
from abook.webui.server import ApiError, App, socket_name
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401 - fixture dùng chung


class CountingSync(SyncApp):
    """Máy kia, ghi lại từng file máy này xin (để biết bấm tải tiếp có lấy lại file đã có không)."""

    asked: list[str]

    def resolve_file(self, project_root: Path, relative: str) -> Any:
        self.asked.append(relative)
        return super().resolve_file(project_root, relative)


def _two_computers(library, tmp_path: Path):  # noqa: F811
    other_library, project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    sync = CountingSync(other_library, other_listening, devices, "Máy kia")
    sync.asked = []
    other = SyncServer(sync, host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    app.edits_send_delay = None  # bài thử gửi bằng tay, không để hẹn giờ nền chen vào
    view = app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
    (computer,) = [item["id"] for item in view["computers"]]
    (book,) = [item for item in app.listen_library() if item.get("remote")]
    return app, other, sync, project, devices, computer, book["id"], app._listenable(book["id"])


def _restart(app: App, sync: SyncApp, computer: str) -> SyncServer:
    """Máy kia bật lại (cổng khác, cùng chứng chỉ của tiến trình): máy này tìm thấy nó ở địa chỉ mới."""
    server = SyncServer(sync, host="127.0.0.1", port=0).start()
    app.computers.note(computer, port=server.port)
    return server


# ---- "Tải về máy" -----------------------------------------------------------------------------------------------------


def test_download_takes_every_file_and_the_book_plays_with_the_other_computer_off(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    app, other, _sync, project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    try:
        before = app.remote_download(value, "status")
        assert before["state"] == "none" and before["filesDone"] < before["files"]
        names = [name for name, _size in remote_books.wanted(packages.manifest(path))]
        assert {"chapters/00001_645.mp3", "scripts/1.json", "cast.json", "samples/3.wav"} <= set(names)
        assert "scripts/2.json" not in names, "chương chưa thu chưa có gì để tải"

        done = app.remote_downloads.start(path, wait=True)
        assert (done["state"], done["filesDone"], done["files"]) == ("done", len(names), len(names)), done
        assert done["bytesDone"] == done["bytes"] > 0
        remote_audio = next((project / "output" / "chapters").glob("*.mp3"))
        assert (path / "chapters" / "00001_645.mp3").read_bytes() == remote_audio.read_bytes()
        assert not list(path.rglob("*.part")), "không để lại file dở"
    finally:
        other.stop()

    def no_fetch(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("đã tải về thì đọc file trên đĩa, không xin máy kia")

    monkeypatch.setattr(remote_books, "_save", no_fetch)
    chapter = app.listen_book(value)["chapters"][0]
    assert chapter["available"] and packages.chapter_file(path, chapter["id"]) is not None
    assert packages.script(path, chapter["id"])["segments"] and set(packages.cast(path)) >= {"characters", "extras"}
    assert packages.sample_file(path, 3) is not None
    assert app.remote_download(value, "status")["state"] == "done", "mở lại vẫn biết đã tải đủ (tính theo đĩa)"


def test_an_interrupted_download_keeps_what_is_done_and_resumes_only_the_rest(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    app, other, sync, _project, _devices, computer, value, path = _two_computers(library, tmp_path)
    real_save = remote_books._save
    saved: list[str] = []

    def save_then_vanish(package: Path, relative: str, book: dict, **kwargs: Any) -> Path:
        result = real_save(package, relative, book, **kwargs)
        saved.append(relative)
        if len(saved) == 2:
            other.stop()  # máy kia tắt ngay sau file thứ hai
        return result

    monkeypatch.setattr(remote_books, "_save", save_then_vanish)
    sync.asked.clear()
    failed = app.remote_downloads.start(path, wait=True)
    assert failed["state"] == "failed" and "Không kết nối được máy kia" in failed["error"]
    assert failed["filesDone"] == 2 and all((path / name).is_file() for name in saved)
    assert not list(path.rglob("*.part"))
    assert app.remote_download(value, "status")["state"] == "failed", "nói rõ lần trước hỏng, phần đã xong vẫn đếm"

    monkeypatch.setattr(remote_books, "_save", real_save)
    again = _restart(app, sync, computer)
    try:
        sync.asked.clear()
        done = app.remote_downloads.start(path, wait=True)
        assert done["state"] == "done", done
        assert not set(saved) & set(sync.asked), "tải tiếp không lấy lại file đã có"

        # Máy kia thu lại một chương (cỡ khác): cuốn hết "đủ", bấm tải lại chỉ lấy đúng chương ấy.
        (path / "chapters" / "00001_645.mp3").write_bytes(b"cu")
        assert app.remote_download(value, "status")["state"] == "none"
        sync.asked.clear()
        assert app.remote_downloads.start(path, wait=True)["state"] == "done"
        assert sync.asked == ["chapters/00001_645.mp3"]
    finally:
        again.stop()


def test_cancel_stops_the_download_and_drops_only_the_half_file(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    app, other, _sync, _project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    real_save = remote_books._save
    calls: list[str] = []

    def cancel_on_second(package: Path, relative: str, book: dict, **kwargs: Any) -> Path:
        calls.append(relative)
        if len(calls) == 2:
            app.remote_download(value, "cancel")  # người dùng bấm dừng giữa lúc file thứ hai đang về
        return real_save(package, relative, book, **kwargs)

    monkeypatch.setattr(remote_books, "_save", cancel_on_second)
    try:
        stopped = app.remote_downloads.start(path, wait=True)
        assert (stopped["state"], stopped["filesDone"]) == ("cancelled", 1)
        assert (path / calls[0]).is_file() and not (path / calls[1]).exists() and not list(path.rglob("*.part"))
        monkeypatch.setattr(remote_books, "_save", real_save)
        assert app.remote_downloads.start(path, wait=True)["state"] == "done"
    finally:
        other.stop()


# ---- phần sửa về máy giữ sách ------------------------------------------------------------------------------------------


def test_edits_made_on_this_computer_reach_the_other_computer_like_a_phones(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, project, devices, _computer, value, path = _two_computers(library, tmp_path)
    try:
        book = app.listen_book(value)
        assert book["capabilities"]["sync"] and not book["capabilities"]["link"], "cuốn của máy tính khác sửa được ở đây"
        assert book["editsSync"] == {"pending": 0, "last": None}

        app.rename(value, "Tên đặt ở máy B")
        book_edits.set_chapter_title(path, 1, "Chương mở đầu")
        book_wishes.request_pronunciation(path, "Lucien", "Lu-xi-en", now=1000.0)
        assert app.listen_book(value)["editsSync"]["pending"] == 3

        state = app.send_remote_edits(value)
        assert state["pending"] == 0 and state["last"]["state"] == "sent"
        assert (state["last"]["applied"], state["last"]["waiting"], state["last"]["conflicts"]) == (2, 1, [])
        assert book_edits.is_empty(book_edits.load(path)), "đã tới máy kia thì gỡ khỏi lớp sửa ở đây"

        # Máy kia: sửa "áp ngay" áp bằng đúng đường của điện thoại; ý muốn nằm trong hộp thư, mang tên máy B, chờ chủ máy.
        assert store.display_title(project, "") == "Tên đặt ở máy B"
        assert store.chapter_title_overrides(project)[1]["title"] == "Chương mở đầu"
        inbox = edits_inbox.view(project)
        (device,) = inbox["devices"]
        (paired,) = devices.list()
        assert (device["id"], device["name"]) == (paired["id"], socket_name())
        assert [item["kind"] for item in device["items"]] == ["pronunciation"]
        # Máy này thấy sách theo bản mới của máy kia (đã mang phần sửa), không còn lớp sửa riêng.
        assert app.listen_book(value)["title"] == "Tên đặt ở máy B"

        # Luật xung đột như với điện thoại: chủ máy kia đổi tên sau lần gửi trước -> vẫn thắng bên đến sau, nhưng báo.
        store.set_display_title(project, "Chủ máy A đặt lại")
        app.rename(value, "Máy B đặt lần hai")
        state = app.send_remote_edits(value)
        (conflict,) = state["last"]["conflicts"]
        assert socket_name() in conflict and store.display_title(project, "") == "Máy B đặt lần hai"
    finally:
        other.stop()

    app.rename(value, "Sửa lúc máy kia tắt")
    with pytest.raises(ApiError, match="Không kết nối được máy kia"):
        app.send_remote_edits(value)
    state = app.listen_book(value)["editsSync"]
    assert state["pending"] == 1 and state["last"]["state"] == "error", "lớp sửa giữ nguyên, lần sau gửi lại"
    assert app.listen_book(value)["title"] == "Sửa lúc máy kia tắt"


def test_a_book_shared_by_a_phone_is_still_not_editable_here(library, tmp_path: Path) -> None:  # noqa: F811
    """Điện thoại chia sẻ thư viện (LibraryServer.kt) không nhận phần sửa: cuốn của nó vẫn là `link`, sửa ở điện thoại."""
    app, other, _sync, _project, _devices, computer, value, path = _two_computers(library, tmp_path)
    other.stop()
    app.computers.note(computer, kind="phone")
    assert app.capabilities(path) == {"toolchain": True, "workshop": False, "link": True, "sync": False}
    with pytest.raises(ApiError, match="sửa ở máy ấy"):
        app.rename(value, "Không được")
    assert "editsSync" not in app.listen_book(value)


def test_subtract_keeps_what_changed_after_the_snapshot(tmp_path: Path) -> None:
    """Gửi xong chỉ gỡ đúng giá trị đã gửi: người dùng sửa tiếp trong lúc gửi thì phần mới ở lại để gửi lần sau."""
    folder = tmp_path / "sach"
    folder.mkdir()
    sent = book_edits.validate({"format": "abook-edits", "version": 1, "title": "A", "characters": {"X": "Ích", "Y": "I"},
                                "chapters": {"1": {"title": "Một", "subtitle": "Phụ"}}, "skip": {"1": ["Dịch: Nhóm"]},
                                "music": {"levelDb": -20.0, "silenced": ["1:0"]}})
    book_edits.save(folder, {**sent, "title": "B", "characters": {"X": "Ích", "Y": "Y mới"},
                             "chapters": {"1": {"title": "Một", "subtitle": "Đổi"}}})
    assert book_edits.subtract(folder, sent, None) == 3
    left = book_edits.load(folder)
    assert (left["title"], left["characters"], left["chapters"]) == ("B", {"Y": "Y mới"}, {"1": {"subtitle": "Đổi"}})
    assert "skip" not in left and "music" not in left
    assert json.loads((folder / book_edits.EDITS_FILE).read_text(encoding="utf-8"))["title"] == "B"
