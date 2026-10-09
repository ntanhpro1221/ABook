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
        assert "Máy kia" in conflict and "Chủ máy A đặt lại" in conflict and socket_name() not in conflict, "báo theo góc nhìn máy gửi"
        assert store.display_title(project, "") == "Máy B đặt lần hai"
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
    assert book_edits.subtract(folder, sent, None) == 4
    left = book_edits.load(folder)
    assert (left["title"], left["characters"], left["chapters"]) == ("B", {"Y": "Y mới"}, {"1": {"subtitle": "Đổi"}})
    assert left["skip"] == {"1": ["Dịch: Nhóm"]}, "dòng bỏ khỏi phần đọc ở lại (sách máy kia không mang nó); sent_marks nhớ là đã gửi"
    assert "music" not in left
    assert json.loads((folder / book_edits.EDITS_FILE).read_text(encoding="utf-8"))["title"] == "B"


# ---- thôi ghép không được lặng lẽ xoá sửa chưa gửi (docs/EDITING.md, P2d) -------------------------------------------------


def test_forgetting_a_computer_is_refused_while_edits_are_unsent_and_changes_nothing(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, _project, _devices, computer, value, path = _two_computers(library, tmp_path)
    try:
        assert app.unsent_computer_edits(computer) == {"books": [], "changes": 0, "sendable": True, "cache": {"books": 1, "bytes": 0, "places": 0}}
        app.rename(value, "Tên đặt ở máy B")
        book_edits.set_chapter_title(path, 1, "Chương mở đầu")
        view = app.unsent_computer_edits(computer)
        assert view["changes"] == 2 and view["sendable"] is True
        assert view["reachable"] is True, "máy kia đang bật: hộp mời Gửi trước"
        assert [item["changes"] for item in view["books"]] == [2]
        assert [item["title"] for item in view["books"]] == ["Tên đặt ở máy B"], "hộp gỡ ghép nói tên đã sửa, không phải tên gốc"

        with pytest.raises(ApiError, match="1 cuốn còn 2 thay đổi chưa gửi") as refused:
            app.forget_computer(computer)
        assert refused.value.status == 409
        assert path.exists() and len(app.computers_view()["computers"]) == 1, "từ chối thì không đụng gì"
        assert book_edits.count(book_edits.load(path)) == 2
    finally:
        other.stop()


def test_send_first_delivers_the_edits_and_then_forgets(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, project, _devices, computer, value, path = _two_computers(library, tmp_path)
    try:
        app.rename(value, "Gửi rồi mới gỡ")
        app.forget_computer(computer, "send")
        assert not path.exists() and app.computers_view()["computers"] == []
        assert store.display_title(project, "") == "Gửi rồi mới gỡ", "sửa đã tới máy kia trước khi gỡ"
    finally:
        other.stop()


def test_send_first_that_fails_keeps_the_pairing_and_every_edit(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, _project, _devices, computer, value, path = _two_computers(library, tmp_path)
    other.stop()
    app.rename(value, "Máy kia đã tắt")
    assert app.unsent_computer_edits(computer)["reachable"] is False, "hộp phải biết máy kia đã tắt, không tin trạng thái cũ"
    with pytest.raises(ApiError) as failed:
        app.forget_computer(computer, "send")
    assert failed.value.status == 502
    assert path.exists() and len(app.computers_view()["computers"]) == 1
    assert book_edits.load(path)["title"] == "Máy kia đã tắt"


def test_discarding_drops_the_edits_with_the_folder(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, project, _devices, computer, value, path = _two_computers(library, tmp_path)
    try:
        app.rename(value, "Bỏ đi")
        app.forget_computer(computer, "discard")
        assert not path.exists() and app.computers_view()["computers"] == []
        assert store.display_title(project, "") != "Bỏ đi", "không gửi gì về máy kia"
    finally:
        other.stop()


def test_a_sent_reading_and_playlist_stay_here_but_are_no_longer_pending(library, tmp_path: Path) -> None:  # noqa: F811
    """Cách đọc và nhạc đã chọn tới máy kia rồi thì không còn "chờ gửi" (thôi ghép không hỏi), nhưng vẫn ở lớp sửa - sách máy kia trả về không mang chúng."""
    app, other, _sync, _project, _devices, computer, value, path = _two_computers(library, tmp_path)
    try:
        book_edits.set_reading(path, "Lucien", "Lu-xi-en")
        book_edits.set_music(path, {"playlist": "school_light"})
        assert app.listen_book(value)["editsSync"]["pending"] == 2
        state = app.send_remote_edits(value)
        assert state["pending"] == 0 and "kept" not in (state["last"] or {})
        left = book_edits.load(path)
        assert left["readings"] == {"Lucien": "Lu-xi-en"} and left["music"]["playlist"] == "school_light"
        assert app.unsent_computer_edits(computer)["changes"] == 0

        book_edits.set_reading(path, "Lucien", "Lu-xiên")  # sửa tiếp sau khi đã gửi: chỉ phần mới chờ gửi
        assert app.listen_book(value)["editsSync"]["pending"] == 1
        app.rename(value, "Tên mới")
        assert app.send_remote_edits(value)["pending"] == 0
        app.forget_computer(computer)
        assert not path.exists()
    finally:
        other.stop()


def test_a_phone_cannot_take_edits_so_unsent_is_reported_unsendable(library, tmp_path: Path) -> None:  # noqa: F811
    app, other, _sync, _project, _devices, computer, _value, path = _two_computers(library, tmp_path)
    other.stop()
    app.computers.note(computer, kind="phone")
    book_edits.save(path, {**book_edits.load(path), "title": "Chỉ ở đây"})
    view = app.unsent_computer_edits(computer)
    assert (view["changes"], view["sendable"]) == (1, False)
    with pytest.raises(ApiError, match="chưa gửi"):
        app.forget_computer(computer)


def test_a_skipped_line_is_still_skipped_after_it_was_sent_to_the_other_computer(library, tmp_path: Path) -> None:  # noqa: F811
    """Dòng người nghe bỏ khỏi phần đọc là sở thích của MÁY NÀY: máy kia không phản ánh nó trong sách, nên gửi xong vẫn phải bỏ ở đây."""
    app, other, _sync, _project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    try:
        book_edits.set_skip_line(path, [1], "Dịch: Nhóm Lục Bình", True)
        assert packages.edited_manifest(path)["chapters"][0]["skip"] == ["Dịch: Nhóm Lục Bình"]
        book_edits.set_chapter_title(path, 1, "Chương mở đầu")
        assert app.listen_book(value)["editsSync"]["pending"] == 2
        state = app.send_remote_edits(value)
        assert state["last"]["state"] == "sent" and state["pending"] == 0, "dòng đã gửi không còn là phần chờ gửi"
        assert packages.edited_manifest(path)["chapters"][0]["skip"] == ["Dịch: Nhóm Lục Bình"], "gửi xong vẫn bỏ dòng ấy"
        assert book_edits.load(path)["skip"] == {"1": ["Dịch: Nhóm Lục Bình"]}
        assert app.send_remote_edits(value)["pending"] == 0

        # Bỏ thêm một dòng sau lần gửi: chỉ dòng mới là phần chờ gửi.
        book_edits.set_skip_line(path, [1], "Biên tập: Ai Đó", True)
        assert app.listen_book(value)["editsSync"]["pending"] == 1
        assert app.send_remote_edits(value)["pending"] == 0
        assert packages.edited_manifest(path)["chapters"][0]["skip"] == ["Biên tập: Ai Đó", "Dịch: Nhóm Lục Bình"]

        # Đọc lại dòng ấy thì hết bỏ, như mọi lúc.
        book_edits.set_skip_line(path, [1], "Dịch: Nhóm Lục Bình", False)
        assert packages.edited_manifest(path)["chapters"][0]["skip"] == ["Biên tập: Ai Đó"]
    finally:
        other.stop()


def test_forgetting_says_what_is_downloaded_keeps_the_listening_place_and_pairing_again_brings_it_back(library, tmp_path: Path) -> None:  # noqa: F811
    """Hộp thôi ghép nói số cuốn, dung lượng đã tải và số cuốn có chỗ nghe; thôi ghép rồi ghép lại đúng máy ấy thì mã sách không đổi nên chỗ nghe còn."""
    app, other, _sync, _project, devices, computer, value, _path = _two_computers(library, tmp_path)
    try:
        assert app.remote_downloads.start(app._listenable(value), wait=True)["state"] == "done"
        app.listening.progress(value, 1, 42.0, 300.0)
        cache = app.unsent_computer_edits(computer)["cache"]
        assert cache["books"] == 1 and cache["bytes"] > 0 and cache["places"] == 1, cache
        app.forget_computer(computer)
        assert not app.computers.list()
        view = app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        assert [item["id"] for item in view["computers"]] == [computer], "cùng vân tay chứng chỉ: lấy lại mã cũ"
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        assert book["id"] == value and book["state"]["last"]["seconds"] == 42.0, "chỗ nghe vẫn còn"
    finally:
        other.stop()


class _Reply:
    """Trả lời của máy kia cho một file: `sent` byte đầu của phần được hỏi rồi đóng êm (như tắt máy giữa chừng); `length` là cỡ nó hứa."""

    def __init__(self, body: bytes, *, status: int = 200, content_range: str = "", sent: int | None = None) -> None:
        self.status, self.length, self._content_range = status, len(body), content_range
        self._rest = body if sent is None else body[:sent]

    def getheader(self, name: str) -> str:
        return self._content_range if name == "Content-Range" else ""

    def read(self, amount: int | None = None) -> bytes:
        chunk, self._rest = self._rest[:amount], self._rest[amount:]
        return chunk


def test_a_cut_download_names_the_machine_keeps_the_part_and_resumes_with_a_range(tmp_path: Path, monkeypatch) -> None:
    from contextlib import contextmanager

    data = bytes(range(200)) * 5
    asked: list[dict[str, str] | None] = []
    plan = [lambda: _Reply(data, sent=300), lambda: _Reply(data[300:], status=206, content_range=f"bytes 300-{len(data) - 1}/{len(data)}")]

    class Known:
        def get(self, _computer: str) -> dict[str, Any]:
            return {"id": "c1", "name": "Phòng khách", "token": "t", "host": "x", "port": 1, "fingerprint": "ab"}

    @contextmanager
    def fake_open(_endpoint, _method, _path, _token, *_args, extra=None, **_kwargs):
        asked.append(extra)
        yield plan[len(asked) - 1](), "ab"

    monkeypatch.setattr(remote_books, "_COMPUTERS", Known())
    monkeypatch.setattr(remote_books, "_open", fake_open)
    book = {"package": {"remote": {"computer": "c1", "book": "b" * 24}}, "version": 1}
    with pytest.raises(remote_books.RemoteError, match=r"Máy Phòng khách không trả lời \(tắt hay mất mạng\)"):
        remote_books._save(tmp_path, "chapters/1.mp3", book, size=len(data))
    part = tmp_path / "chapters" / "1.mp3.part"
    assert part.read_bytes() == data[:300] and not (tmp_path / "chapters" / "1.mp3").exists()
    assert remote_books._part_size(tmp_path, "chapters/1.mp3", len(data)) == 300

    remote_books._save(tmp_path, "chapters/1.mp3", book, size=len(data))
    assert asked[1] == {"Range": "bytes=300-"}
    assert (tmp_path / "chapters" / "1.mp3").read_bytes() == data and not part.exists()


def test_an_interrupted_download_resumes_by_itself_when_the_other_computer_answers_again(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    app, other, _sync, _project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    try:
        real_save = remote_books._save

        def cut(package: Path, relative: str, book: dict, **kwargs: Any) -> Path:
            raise remote_books.RemoteError("Máy kia không trả lời (tắt hay mất mạng)")

        monkeypatch.setattr(remote_books, "_save", cut)
        failed = app.remote_downloads.start(path, wait=True)
        assert failed["state"] == "failed" and failed["retry"] is True, failed
        assert app.remote_download(value, "status")["state"] == "failed", "máy kia chưa trả lời lại thì nằm yên"
        monkeypatch.setattr(remote_books, "_save", real_save)
        app.remote_downloads._jobs[str(path.resolve())].pop("probed", None)
        assert app.remote_download(value, "status")["state"] in ("running", "done"), "trả lời lại là tải tiếp"
        for _ in range(100):
            if app.remote_download(value, "status")["state"] == "done":
                break
            import time

            time.sleep(0.05)
        assert app.remote_download(value, "status")["state"] == "done"
    finally:
        other.stop()
