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


def test_undo_is_refused_when_the_original_place_is_taken(studio, recycled: list[Path]) -> None:  # noqa: F811
    from abook.webui import trash_pending

    paths, app, server, _runner = studio
    original = paths.root.resolve()
    token = _delete(server, paths)
    original.mkdir()
    (original / "cua_nguoi_khac.txt").write_text("giữ nguyên", encoding="utf-8")
    status, data = _call(server, "POST", f"/api/trash/{token}/undo")
    assert status == 409 and "trùng tên" in data["error"]
    assert (original / "cua_nguoi_khac.txt").read_text(encoding="utf-8") == "giữ nguyên", "không đè lên thư mục đang ở đó"
    [held] = _pending(original.parent)
    assert (held / original.name / "project.sqlite3").is_file(), "cuốn vừa xoá vẫn nằm chờ"

    # Hết hạn mà đường gốc vẫn bị chiếm: không đổi tên đè, không vào Thùng rác từ chỗ chờ - để nguyên, lần sau dọn.
    app.trash.clock = lambda: time.time() + trash_pending.UNDO_SECONDS + 5
    assert app.trash.sweep(original.parent) == 1 and recycled == []
    assert (held / original.name / "project.sqlite3").is_file()


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
