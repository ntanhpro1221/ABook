"""Xoá sách / dự án trên máy tính có "Hoàn tác" (webui/trash_pending.py): thư mục nằm chờ ở `<thư viện>/.trash-pending` vài chục
giây trước khi vào Thùng rác của Windows.

Không bài nào chạm Thùng rác thật: `move_to_recycle_bin` và câu hỏi "ổ có Thùng rác không" đều bị thay (autouse)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_desktop_opens_book_files import _app, _produced


@pytest.fixture(autouse=True)
def recycled(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Thùng rác giả: ghi lại đường được chuyển (xoá thật trong thư mục thử), và ổ nào cũng "có Thùng rác"."""
    from abook.webui import actions

    moved: list[Path] = []

    def recycle(path: Path) -> None:
        moved.append(path)
        shutil.rmtree(path)

    monkeypatch.setattr(actions, "move_to_recycle_bin", recycle)
    monkeypatch.setattr(actions, "recycle_bin_available", lambda _path: None)
    monkeypatch.setattr(actions, "recycle_bin_accepts", lambda _path: True)  # cỡ thật so với Thùng rác: bài riêng
    return moved


def _pending(root: Path) -> list[Path]:
    base = root / ".trash-pending"
    return sorted(base.iterdir()) if base.is_dir() else []


def _delete(server, paths) -> str:
    from abook.webui.library import book_id

    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 200 and data["ok"] is True, data
    return data["undo"]


def test_undo_puts_the_project_back_and_the_library_sees_it_again(studio, recycled: list[Path]) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    original = paths.root.resolve()
    token = _delete(server, paths)
    assert not original.exists(), "thư viện thôi hiện ngay"
    assert _call(server, "GET", "/api/library")[1]["books"] == []
    [held] = _pending(original.parent)
    assert held.name == token and (held / original.name / "project.sqlite3").is_file(), "cả thư mục nằm chờ, không mất byte nào"

    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["ok"] is True and data["wasQueued"] is False
    assert original.is_dir() and (original / "project.sqlite3").is_file()
    assert len(_call(server, "GET", "/api/library")[1]["books"]) == 1, "thư viện thấy lại"
    assert _pending(original.parent) == [], "chỗ chờ gọn: không còn mã, không còn thư mục .trash-pending"
    assert recycled == [], "hoàn tác thì không có gì vào Thùng rác"
    status, _data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 404, "mỗi mã dùng một lần"


def test_an_expired_deletion_goes_to_the_recycle_bin_from_its_original_place(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui import trash_pending

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    now = [1000.0]
    app.trash.clock = lambda: now[0]
    token = _delete(server, paths)
    assert app.trash.sweep(original.parent) == 1 and recycled == [], "chưa hết hạn: còn nằm chờ"
    assert len(_pending(original.parent)) == 1

    now[0] += trash_pending.UNDO_SECONDS + 1
    assert app.trash.sweep(original.parent) == 0
    assert recycled == [original], "Thùng rác ghi đường GỐC, để Khôi phục của Windows đưa về đúng chỗ cũ"
    assert _pending(original.parent) == [] and not original.exists()
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 404 and "Thùng rác" in data["error"]


def test_a_timer_cleans_up_after_the_deadline(studio, recycled: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from abook.webui import trash_pending
    from abook.webui.library import book_id

    paths, app, _server, _runner = studio
    original = paths.root.resolve()
    monkeypatch.setattr(trash_pending, "UNDO_SECONDS", 0.05)
    monkeypatch.setattr(app, "_fake_run", lambda: False)  # bản thật có hẹn giờ; bản giọng giả thì không
    assert app.delete(book_id(paths.root), undo=True)["undo"]
    deadline = time.time() + 5
    while not recycled and time.time() < deadline:
        time.sleep(0.05)
    assert recycled == [original]
    app.close()


def test_old_tokens_go_to_the_recycle_bin_when_the_app_starts_and_closes(studio, recycled: list[Path]) -> None:  # noqa: F811
    from types import SimpleNamespace

    from abook.webui.library import book_id

    paths, app, _server, _runner = studio
    original = paths.root.resolve()
    app.delete(book_id(paths.root), undo=True)  # app chết giữa hạn: token còn đó, chưa hết hạn
    assert len(_pending(original.parent)) == 1
    app.runner = SimpleNamespace(running=lambda _path: False)  # không phải giọng giả: lúc mở app thì tự dọn
    app._sweep_trash_at_start()
    deadline = time.time() + 5
    while _pending(original.parent) and time.time() < deadline:
        time.sleep(0.05)
    assert recycled == [original] and _pending(original.parent) == []

    # Lúc đóng app: hết hạn hay chưa cũng vào Thùng rác.
    held = app.trash.hold(original.parent, _make_folder(original.parent / "sach_khac"), "imported")
    assert held and len(_pending(original.parent)) == 1
    app.close()
    assert recycled[-1] == (original.parent / "sach_khac") and _pending(original.parent) == []


def _make_folder(path: Path) -> Path:
    path.mkdir()
    (path / "a.txt").write_text("x", encoding="utf-8")
    return path.resolve()


def test_undo_uses_a_free_sibling_when_the_original_place_is_taken(studio, recycled: list[Path]) -> None:
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    token = _delete(server, paths)
    original.mkdir()
    (original / "new.txt").write_text("keep", encoding="utf-8")
    original.with_name(original.name + " (2)").mkdir()
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["ok"] is True, data
    restored = original.with_name(original.name + " (3)")
    assert (restored / "project.sqlite3").is_file()
    assert (original / "new.txt").read_text(encoding="utf-8") == "keep"
    assert _pending(original.parent) == [] and recycled == []
    assert book_id(restored) in str(_call(server, "GET", "/api/library")[1])
    assert _call(server, "POST", f"/api/trash/{token}/undo")[0] == 404


def test_a_book_restored_under_a_sibling_name_takes_its_listening_data_along(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui import listen_export
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    old = book_id(original)
    app.listening.set_voice(old, "edge:vi-VN-NamMinhNeural")
    app.listening.set_rate(old, 1.5)
    work = listen_export.work_folder(app.export_work_dir, old)
    work.mkdir(parents=True)
    (work / "part.mp3").write_bytes(b"dang xuat")
    token = _delete(server, paths)
    original.mkdir()  # cuốn mới mang đúng tên cũ: cùng mã sách với cuốn vừa xoá
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    restored = original.with_name(original.name + " (2)")
    assert status == 200 and data["renamed"] is True and data["title"] == restored.name, data
    new = book_id(restored)
    assert app.listening.get(new)["voice"] == "edge:vi-VN-NamMinhNeural"
    assert app.listening.get(new)["rate"] == 1.5
    assert old not in app.listening.books(), "cuốn đang chiếm chỗ không nhận chỗ nghe / tốc độ của cuốn đã xoá"
    assert "rate" not in app.listening.get(old)
    assert (listen_export.work_folder(app.export_work_dir, new) / "part.mp3").read_bytes() == b"dang xuat"
    assert not work.exists()


@pytest.mark.parametrize("order", ["oldest first", "newest first"])
def test_undoing_two_deletions_of_one_name_moves_data_only_off_a_newer_book(studio, recycled: list[Path], order: str) -> None:  # noqa: F811
    """Xoá "X", thêm "X" mới đúng chỗ, xoá luôn nó, rồi hoàn tác cả hai: dữ liệu nghe theo mã đường gốc chỉ đi theo cuốn về "X (2)" khi
    cuốn đang ở đường gốc ra đời SAU lần xoá cuốn ấy. Giao diện hoàn tác cũ trước: "X" cũ về chỗ mình và giữ tốc độ của nó."""
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    old = book_id(original)
    (original / "which.txt").write_text("cũ", encoding="utf-8")
    app.listening.set_rate(old, 1.5)
    first = _delete(server, paths)
    time.sleep(0.05)  # ngày tạo thư mục theo nấc đồng hồ của hệ thống file (~16 ms)
    [held] = _pending(original.parent)
    shutil.copytree(held / original.name, original)  # "X" mới: thư mục mới tạo, cùng đường, cùng mã sách
    (original / "which.txt").write_text("mới", encoding="utf-8")
    time.sleep(0.05)
    second = _delete(server, paths)

    results = [_call(server, "POST", f"/api/trash/{token}/undo")
               for token in ([first, second] if order == "oldest first" else [second, first])]
    assert [status for status, _data in results] == [200, 200], results
    sibling = original.with_name(original.name + " (2)")
    new = book_id(sibling)
    later = results[1][1]
    assert later["renamed"] is True and later["title"] == sibling.name
    if order == "oldest first":
        assert (original / "which.txt").read_text(encoding="utf-8") == "cũ", "cuốn cũ về đúng chỗ của nó"
        assert "oldId" not in later, "cuốn cũ đang ở đường gốc có trước lần xoá cuốn mới: không lấy dữ liệu của nó"
        assert app.listening.get(old)["rate"] == 1.5
        assert new not in app.listening.books()
    else:
        assert (sibling / "which.txt").read_text(encoding="utf-8") == "cũ"
        assert later["oldId"] == old and later["newId"] == new, "cuốn mới ra đời sau lần xoá cuốn cũ: dữ liệu theo cuốn cũ sang tên mới"
        assert app.listening.get(new)["rate"] == 1.5
        assert old not in app.listening.books()


def test_listening_data_that_cannot_be_moved_still_finishes_the_undo(studio, recycled: list[Path],  # noqa: F811
                                                                      monkeypatch: pytest.MonkeyPatch,
                                                                      caplog: pytest.LogCaptureFixture) -> None:
    """File nghe đang bị giữ lúc chuyển mã: thư mục đã về, mã hoàn tác đã dùng - vẫn là hoàn tác xong (không phải lỗi rồi bấm lại gặp 404),
    lời báo nói dữ liệu chưa theo được, nhật ký ghi rõ."""
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    old = book_id(original)
    app.listening.set_rate(old, 1.75)
    token = _delete(server, paths)
    time.sleep(0.05)
    original.mkdir()

    def held(_renamed: dict[str, str]) -> None:
        raise PermissionError(13, "file đang bị giữ")

    monkeypatch.setattr(app.listening, "rename_books", held)
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    restored = original.with_name(original.name + " (2)")
    assert status == 200 and data["renamed"] is True and data["dataLeft"] is True and "oldId" not in data, data
    assert (restored / "project.sqlite3").is_file() and _pending(original.parent) == []
    assert "không chuyển được dữ liệu nghe" in caplog.text
    assert app.listening.get(old)["rate"] == 1.75


def test_a_plain_undo_keeps_the_same_book_id(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    old = book_id(paths.root.resolve())
    app.listening.set_rate(old, 1.25)
    token = _delete(server, paths)
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["renamed"] is False
    assert app.listening.get(old)["rate"] == 1.25


@pytest.mark.parametrize("link", ["from", "to"])
def test_a_project_in_a_series_is_not_restored_under_another_name(studio, recycled: list[Path], link: str) -> None:  # noqa: F811
    import json

    from abook import continuation

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    if link == "from":  # cuốn bị xoá là phần 2: nó trỏ về phần 1
        (original / continuation.LINK_FILE).write_text(json.dumps({"previous": "Phan 1", "part": 2}), encoding="utf-8")
    else:  # phần sau trỏ về cuốn bị xoá theo đường gốc
        follower = original.with_name(original.name + " · Phần 2")
        shutil.copytree(original, follower)
        (follower / continuation.LINK_FILE).write_text(json.dumps({"previous": original.name, "part": 2}), encoding="utf-8")
    token = _delete(server, paths)
    original.mkdir()
    (original / "new.txt").write_text("keep", encoding="utf-8")
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 409 and "Trùng tên trong bộ" in data["error"] and "dời cuốn mới" in data["error"] and "Hoàn tác" in data["error"], data
    assert (original / "new.txt").read_text(encoding="utf-8") == "keep"
    assert not original.with_name(original.name + " (2)").exists()
    [held] = _pending(original.parent)
    assert (held / original.name / "project.sqlite3").is_file(), "cuốn vừa xoá vẫn nằm chờ"
    shutil.rmtree(original)  # người dùng bỏ cuốn vừa thêm rồi bấm Hoàn tác lại
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["renamed"] is False and (original / "project.sqlite3").is_file()


def test_the_pending_folder_is_never_a_book(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui import store

    paths, app, server, _runner = studio
    token = _delete(server, paths)
    [held] = _pending(paths.root.parent.resolve())
    assert store.is_project(held / paths.root.name), "bên trong vẫn là một dự án đầy đủ..."
    assert app.library.projects() == [] and app.library.packages() == [] and app.listen_library() == [], "...mà thư viện không thấy"
    assert _call(server, "GET", "/api/library")[1]["books"] == []
    assert token


def test_a_wrong_or_unknown_token_is_not_found(studio) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    assert _call(server, "POST", f"/api/trash/{'0' * 32}/undo")[0] == 404
    assert _call(server, "POST", "/api/trash/..%2F..%2Fx/undo")[0] == 404
    assert _call(server, "POST", f"/api/trash/{'A' * 32}/undo")[0] == 404


def test_a_folder_that_cannot_be_renamed_stays_put_and_says_why(studio, recycled: list[Path],  # noqa: F811
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import trash_pending
    from abook.webui.library import book_id

    paths, app, server, _runner = studio

    def locked(_source, _target) -> None:
        raise PermissionError("[WinError 5] Access is denied")

    monkeypatch.setattr(trash_pending.os, "replace", locked)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 409 and "đang mở" in data["error"]
    assert paths.root.is_dir() and _pending(paths.root.parent) == [], "sách còn nguyên, chỗ chờ không để lại rác"
    assert recycled == []


def test_a_drive_without_a_recycle_bin_is_refused_up_front(studio, recycled: list[Path],  # noqa: F811
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions
    from abook.webui.library import book_id

    paths, _app, server, _runner = studio

    def none(_path: Path) -> None:
        raise OSError("ổ E:\\ không có Thùng rác")

    monkeypatch.setattr(actions, "recycle_bin_available", none)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 409 and "Thùng rác" in data["error"]
    assert paths.root.is_dir() and _pending(paths.root.parent) == [] and recycled == []


def test_a_failed_recycle_puts_the_folder_back_in_the_pending_place(studio, recycled: list[Path],  # noqa: F811
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions, trash_pending

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    _delete(server, paths)
    app.trash.clock = lambda: time.time() + trash_pending.UNDO_SECONDS + 5

    def locked(_path: Path) -> None:
        raise OSError("SHFileOperationW trả 0x20")

    good = actions.move_to_recycle_bin
    monkeypatch.setattr(actions, "move_to_recycle_bin", locked)
    assert app.trash.sweep(original.parent) == 1
    assert not original.exists(), "thư viện không thấy lại cuốn đã xoá"
    [held] = _pending(original.parent)
    assert (held / original.name / "project.sqlite3").is_file(), "không mất gì, lần sau dọn tiếp"

    monkeypatch.setattr(actions, "move_to_recycle_bin", good)
    assert app.trash.sweep(original.parent) == 0 and recycled == [original]


def test_a_folder_on_another_drive_goes_straight_to_the_recycle_bin(studio, recycled: list[Path],  # noqa: F811
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    monkeypatch.setattr(app.trash, "fits", lambda _root, _path: False)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 200 and "undo" not in data
    assert recycled == [paths.root.resolve()] and _pending(paths.root.parent) == []


def test_a_queued_book_is_not_queued_again_by_the_undo(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    identity = book_id(paths.root)
    app.queue.append(identity)
    token = _delete(server, paths)
    assert app.queue == []
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["wasQueued"] is True
    assert app.queue == [], "không tự xếp lại hàng chờ - giao diện nói điều đó"


def test_a_project_opened_from_elsewhere_comes_back_through_recents(studio, tmp_path: Path) -> None:  # noqa: F811
    from abook.webui.library import book_id

    paths, app, server, _runner = studio
    library = tmp_path / "thu_vien_khac"
    library.mkdir()
    app.preferences.update({"libraryRoot": str(library)})
    app.preferences.add_recent(paths.root)
    assert len(app.library.projects()) == 1
    token = _delete(server, paths)
    assert app.library.projects() == [] and _pending(library.resolve()) != [], "chỗ chờ nằm trong thư viện, cùng ổ"
    assert _call(server, "POST", f"/api/trash/{token}/undo")[0] == 200
    assert [book_id(path) for path in app.library.projects()] == [book_id(paths.root)]


def test_an_imported_book_can_be_undone_too(tmp_path: Path, recycled: list[Path]) -> None:
    project, file = _produced(tmp_path)
    elsewhere = tmp_path / "thu_vien_nguoi_nghe"
    elsewhere.mkdir()
    app = _app(tmp_path, elsewhere)
    opened = app.open_book_file(str(file))
    removed = app.remove_imported(opened["id"], undo=True)
    assert removed["ok"] is True and app.listen_library() == []
    assert recycled == [] and len(_pending(elsewhere.resolve())) == 1
    restored = app.undo_trash(removed["undo"])
    assert restored["ok"] is True
    assert [book["id"] for book in app.listen_library()] == [opened["id"]], "cùng đường dẫn nên cùng mã sách"
    assert _pending(elsewhere.resolve()) == [] and file.is_file()

    again = app.remove_imported(opened["id"], undo=True)
    app.trash.clock = lambda: time.time() + 3600
    assert app.trash.sweep(elsewhere.resolve()) == 0
    assert len(recycled) == 1 and recycled[0].parent.name == "Sách đã nhập"
    assert again["undo"]


def test_undo_goes_with_the_delete_permission_of_a_remote_device() -> None:
    from abook.webui.remote_studio import permitted

    assert not permitted("DELETE", "/api/books/abcdef0123456789abcdef01")
    assert not permitted("DELETE", "/api/listen/books/abcdef0123456789abcdef01")
    assert not permitted("POST", f"/api/trash/{'0' * 32}/undo"), "xoá không từ xa được thì hoàn tác cũng không"


def test_internal_replacement_deletes_skip_the_waiting_place(studio, recycled: list[Path]) -> None:  # noqa: F811
    """"Làm lại" thay cuốn cũ: người dùng không thấy gì để hoàn tác, nên vào Thùng rác ngay như trước."""
    from abook.webui.library import book_id

    paths, app, _server, _runner = studio
    result = app.delete(book_id(paths.root))
    assert "undo" not in result and recycled == [paths.root.resolve()] and _pending(paths.root.parent) == []


# ----------------------------------------------------------------------------------------------------------------------
# Lỗi soát: đường gốc bị chiếm, Thùng rác lỗi giữa chừng, người dùng huỷ hộp "xoá hẳn", đổi thư viện giữa hạn.

def _hold(tmp_path: Path, name: str = "Sach", clock=lambda: 0.0):
    from abook.webui.trash_pending import TrashPending

    library = (tmp_path / "lib").resolve()
    library.mkdir(exist_ok=True)
    book = library / name
    book.mkdir()
    (book / "a.mp3").write_bytes(b"x" * 10)
    trash = TrashPending(clock=clock)
    return trash, library, book, trash.hold(library, book, "imported")


def test_reopened_pending_trash_restores_to_a_free_sibling(tmp_path: Path, recycled: list[Path]) -> None:
    from abook.webui.trash_pending import TrashPending

    _trash, library, book, token = _hold(tmp_path)
    book.mkdir()
    (book / "new.mp3").write_bytes(b"new")
    # Mất trạng thái trong RAM như khi app chết rồi mở lại; mã và dữ liệu vẫn ở đĩa.
    reopened = TrashPending(clock=lambda: 1.0)
    meta = reopened.restore(library, token)
    restored = book.with_name("Sach (2)")
    assert Path(meta["original"]) == restored
    assert (restored / "a.mp3").read_bytes() == b"x" * 10
    assert (book / "new.mp3").read_bytes() == b"new"
    assert _pending(library) == [] and recycled == []


def test_a_taken_original_path_still_lets_the_old_copy_reach_the_bin_under_a_free_sibling_name(
        tmp_path: Path, recycled: list[Path]) -> None:
    trash, library, book, _token = _hold(tmp_path)
    book.mkdir()  # mở lại đúng file .abook trong hạn: tên cũ được cấp lại cho cuốn mới
    (book / "b.mp3").write_bytes(b"y")
    assert trash.sweep(library, everything=True) == 0
    assert [path.parent for path in recycled] == [library] and recycled[0].name.startswith("Sach ") and recycled[0] != book
    assert (book / "b.mp3").read_bytes() == b"y", "cuốn mới nguyên vẹn, không bị đè hay đẩy đi"
    assert _pending(library) == []


def test_a_recycle_that_fails_twice_does_not_let_the_deleted_book_come_back(
        tmp_path: Path, recycled: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from abook.webui import actions, trash_pending

    trash, library, book, token = _hold(tmp_path)
    item = library / ".trash-pending" / token / "Sach"
    real_replace = os.replace

    def flaky(source, target):
        if Path(target) == item:  # đổi tên ngược về chỗ chờ sau khi Thùng rác lỗi
            raise PermissionError("in use")
        return real_replace(source, target)

    def failing(_path: Path) -> None:
        raise OSError("sharing violation")

    good = actions.move_to_recycle_bin
    monkeypatch.setattr(actions, "move_to_recycle_bin", failing)
    monkeypatch.setattr(trash_pending.os, "replace", flaky)
    assert trash.sweep(library, everything=True) == 1
    monkeypatch.setattr(trash_pending.os, "replace", real_replace)
    monkeypatch.setattr(actions, "move_to_recycle_bin", good)
    assert trash.sweep(library, everything=True) == 0, "lần dọn sau tiếp tục đưa vào Thùng rác, không bỏ meta"
    assert recycled == [book] and _pending(library) == [] and not book.exists()


def test_a_book_made_new_at_the_same_path_after_a_dead_recycle_is_not_binned(
        tmp_path: Path, recycled: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from abook.webui import actions, trash_pending

    trash, library, book, token = _hold(tmp_path)
    item = library / ".trash-pending" / token / "Sach"
    real_replace = os.replace
    good = actions.move_to_recycle_bin

    def failing(_path: Path) -> None:
        raise OSError("khoá")

    def flaky(source, target):
        if Path(target) == item:
            raise PermissionError("x")
        return real_replace(source, target)

    monkeypatch.setattr(actions, "move_to_recycle_bin", failing)
    monkeypatch.setattr(trash_pending.os, "replace", flaky)
    assert trash.sweep(library, everything=True) == 1
    monkeypatch.setattr(trash_pending.os, "replace", real_replace)
    monkeypatch.setattr(actions, "move_to_recycle_bin", good)
    shutil.rmtree(book)  # người dùng tự xoá cuốn cũ rồi dựng cuốn khác cùng tên
    book.mkdir()
    (book / "moi.txt").write_text("moi", encoding="utf-8")
    trash.sweep(library, everything=True)
    assert (book / "moi.txt").is_file() and recycled == [], "cuốn mới không bị nhầm là cuốn đã xoá"


def test_a_user_who_declines_the_permanent_delete_box_gets_the_book_back(
        tmp_path: Path, recycled: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions

    trash, library, book, _token = _hold(tmp_path)

    def declined(_path: Path) -> None:
        raise actions.RecycleCancelled("người dùng huỷ")

    monkeypatch.setattr(actions, "move_to_recycle_bin", declined)
    assert trash.sweep(library, everything=True) == 0, "coi như không xoá: không còn gì chờ, không hỏi lặp"
    assert (book / "a.mp3").is_file() and _pending(library) == [] and recycled == []


def test_closing_the_app_never_asks_about_a_book_the_bin_would_refuse(
        tmp_path: Path, recycled: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions

    trash, library, book, _token = _hold(tmp_path)
    monkeypatch.setattr(actions, "recycle_bin_accepts", lambda _path: False)
    assert trash.sweep(library, everything=True, ask=False) == 1, "để lần mở sau"
    assert recycled == [] and not book.exists() and len(_pending(library)) == 1
    assert trash.sweep(library, everything=True) == 0 and recycled == [book], "lần mở sau thì dọn (có thể hỏi)"


def test_a_book_too_big_for_the_bin_is_not_held_but_goes_to_ask_at_once(studio, recycled: list[Path],  # noqa: F811
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions
    from abook.webui.library import book_id

    paths, _app, server, _runner = studio
    monkeypatch.setattr(actions, "recycle_bin_accepts", lambda _path: False)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 200 and "undo" not in data
    assert recycled == [paths.root.resolve()] and _pending(paths.root.parent) == [], "hỏi NGAY lúc xoá như trước"


def test_declining_the_permanent_delete_box_at_once_keeps_the_book_and_says_so(studio, recycled: list[Path],  # noqa: F811
                                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import actions
    from abook.webui.library import book_id

    paths, _app, server, _runner = studio

    def declined(_path: Path) -> None:
        raise actions.RecycleCancelled("SHFileOperationW bị huỷ (0x4c7)")

    monkeypatch.setattr(actions, "recycle_bin_accepts", lambda _path: False)
    monkeypatch.setattr(actions, "move_to_recycle_bin", declined)
    status, data = _call(server, "DELETE", f"/api/books/{book_id(paths.root)}")
    assert status == 409 and "thôi xoá" in str(data) and "đang mở" not in str(data), data
    assert paths.root.is_dir()
    status, books = _call(server, "GET", "/api/library")
    assert book_id(paths.root) in str(books), "cuốn vẫn trong thư viện"


def test_the_bin_capacity_rule() -> None:
    from abook.webui import actions

    assert actions.bin_takes(size=10, capacity=100, nuke=False)
    assert not actions.bin_takes(size=95, capacity=100, nuke=False), "gần đầy hạn mức: Windows sẽ hỏi"
    assert not actions.bin_takes(size=1, capacity=100, nuke=True), "ổ đặt xoá hẳn"
    assert actions.bin_takes(size=10, capacity=None, nuke=False, drive_total=2000), "không có hạn mức ghi: tới 1% ổ thì chắc"
    assert not actions.bin_takes(size=100, capacity=None, nuke=False, drive_total=2000)


def test_undo_after_the_library_folder_changed_still_finds_the_deleted_book(studio, recycled: list[Path],  # noqa: F811
                                                                           tmp_path: Path) -> None:
    paths, app, server, _runner = studio
    original = paths.root.resolve()
    token = _delete(server, paths)
    other = tmp_path / "thu_vien_moi"
    other.mkdir()
    app.preferences.update({"libraryRoot": str(other)})
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 200 and data["ok"] is True, data
    assert original.is_dir() and (original / "project.sqlite3").is_file() and _pending(original.parent) == []


def test_closing_after_the_library_folder_changed_still_bins_the_old_one(studio, recycled: list[Path],  # noqa: F811
                                                                        tmp_path: Path) -> None:
    paths, app, server, _runner = studio
    original = paths.root.resolve()
    _delete(server, paths)
    other = tmp_path / "thu_vien_moi"
    other.mkdir()
    app.preferences.update({"libraryRoot": str(other)})
    app.close()
    assert recycled == [original] and _pending(original.parent) == []
