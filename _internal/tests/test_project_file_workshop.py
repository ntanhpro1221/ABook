"""`.abookproj` phiên bản 3 (docs/EDITING.md phase P3): bản chụp `views/`, cuốn nhập từ file dự án giữ xưởng nguyên byte và
lưu lại được, phần sửa của người nghe đi trong file, mở file của dự án đã có trên máy thì không tạo bản trùng, và file "chờ
dựng xưởng" (workshop: pending) thành dự án mới ở máy có Studio.

Python là bản chuẩn của cuộc đối chiếu với app Android: các file trong `fixtures/book_edits/projects/` do đây ghi
(`tests/book_edits_fixtures.py`), BookFileImportTest / BookDocumentWriterTest đọc và ghi lại chúng.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook.webui import book_edits, bookfile, packages, project_views, projectfile, store, workshop
from abook.webui.library import book_id
from abook.webui.projectfile import PENDING, PRESENT, ProjectFile, ProjectFileError
from abook.webui.server import Server
from tests.test_project_file import _app, _project, _with_cover
from tests.test_webui_listen_and_sync import _request, make_project

TOKEN = {"X-Ebook-Token": "t"}


def _stub_views(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sổ dự án tối thiểu của test không có cột cho các màn thật - thay bằng các hàm cho JSON cố định."""
    monkeypatch.setitem(project_views.VIEWS, "work", lambda root, _verdicts=None: {"items": [{"id": "name:Hailkes", "title": "Hailkes"}], "castReady": True})
    monkeypatch.setitem(project_views.VIEWS, "casting", lambda root: {"castReady": True, "chapters": [{"chapterId": 1, "lines": 3}]})
    monkeypatch.setitem(project_views.VIEWS, "names", lambda root: {"items": [{"surface": "Hailkes", "spoken": "Hên-khơ"}]})


def _opened_as_a_book(packed: Path, library: Path) -> Path:
    with ProjectFile(packed) as opened:
        return opened.extract(library)


def _zip_bytes(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


# ---- views/ -----------------------------------------------------------------------------------------------------------


def test_the_views_travel_in_the_file_and_a_failing_view_does_not_block_the_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_views(monkeypatch)

    def broken(_root: Path) -> Any:
        raise sqlite3.OperationalError("no such column: stable_id")

    monkeypatch.setitem(project_views.VIEWS, "names", broken)
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    with ProjectFile(packed) as opened:
        opened.verify()
        assert opened.views == ["work", "casting"]
        assert opened.view("work")["items"][0]["title"] == "Hailkes" and opened.view("names") is None
        assert opened.manifest["files"]["views/work.json"]["size"] > 0


def test_the_work_snapshot_leaves_out_lines_already_judged_like_the_studio_tab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bản chụp "Việc cần duyệt" trong file dự án dùng phán quyết "Cần nghe lại" của máy đóng gói như tab Studio: câu đã chấm
    không còn là việc (soát parity23). Việc đã quyết / chỉ áp khi làm lại phân tích vẫn đi trong bản chụp - màn đọc tự tách."""
    _stub_views(monkeypatch)

    def work(_root: Path, verdicts: dict | None = None) -> dict:
        return {"castReady": True, "items": [{"key": f"audio:{stable_id}", "title": stable_id} for stable_id in ("s2", "s3")
                                             if stable_id not in (verdicts or {})]}

    monkeypatch.setitem(project_views.VIEWS, "work", work)
    project = _project(tmp_path)
    app = _app(tmp_path, project.parent)
    server = Server(app, port=0).start()
    book = book_id(project)
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book}/review", headers=TOKEN,
                                   body={"stableId": "s2", "verdict": "ok", "chapterId": 1})
        assert status == 200, data
        status, data, _ = _request(server.port, "POST", f"/api/books/{book}/projectfile", headers=TOKEN,
                                   body={"target": str(tmp_path / "xuat")})
        assert status == 200, data
    finally:
        server.stop()
        app.close()
    with ProjectFile(Path(json.loads(data)["file"])) as packed:
        assert [item["key"] for item in packed.view("work")["items"]] == ["audio:s3"]


def test_the_real_view_functions_snapshot_a_project(tmp_path: Path) -> None:
    from tests.test_work_items import make_book

    snapshot = project_views.snapshot(make_book(tmp_path))
    assert "views/work.json" in snapshot
    assert json.loads(snapshot["views/work.json"])["items"], "cùng JSON với đường /work của Studio"


def test_a_view_that_is_not_json_or_not_a_known_view_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_views(monkeypatch)
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")

    def broken(name: str, data: bytes) -> bytes:
        return b"{not json" if name == "views/work.json" else data

    with pytest.raises(ProjectFileError, match="hỏng"):
        ProjectFile(_rewrite_keeping_sizes(packed, tmp_path / "x.abookproj", broken))
    with zipfile.ZipFile(packed) as source, zipfile.ZipFile(tmp_path / "la.abookproj", "w") as sink:
        for info in source.infolist():
            sink.writestr(info, source.read(info.filename))
        sink.writestr("views/secrets.json", b"{}")
    with pytest.raises(ProjectFileError, match="mục lạ"):
        ProjectFile(tmp_path / "la.abookproj")


def _rewrite_keeping_sizes(path: Path, target: Path, change: Any) -> Path:
    """Sửa nội dung các mục (không phải mimetype / project.json) và ghi lại cỡ + mã băm của chúng trong project.json, để chỉ còn
    lỗi về NỘI DUNG chứ không phải lỗi mã băm."""
    with zipfile.ZipFile(path) as source:
        manifest = json.loads(source.read(projectfile.MANIFEST))
        entries = []
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename not in ("mimetype", projectfile.MANIFEST):
                data = change(info.filename, data)
                manifest["files"][info.filename] = bookfile.describe(data)
            entries.append((info, data))
    with zipfile.ZipFile(target, "w") as sink:
        for info, data in entries:
            sink.writestr(info, json.dumps(manifest).encode("utf-8") if info.filename == projectfile.MANIFEST else data)
    return target


# ---- cuốn nhập từ file dự án giữ xưởng ---------------------------------------------------------------------------------


def test_a_project_file_opened_as_a_book_keeps_its_workshop_and_saves_it_back_byte_for_byte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_views(monkeypatch)
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    folder = _opened_as_a_book(packed, tmp_path / "dien_thoai")

    assert packages.is_package(folder) and not store.is_project(folder)
    assert packages.workshop_state(folder) == PRESENT
    assert (folder / "chapters" / "00001_645.mp3").is_file() and (folder / "samples" / "3.wav").is_file()
    assert not (folder / "project" / "output").exists(), "bí danh của audio chương không giải ra hai lần"
    assert (folder / "project" / "project.sqlite3").read_bytes() == _zip_bytes(packed, "project/project.sqlite3")
    assert [path.name for path in sorted((folder / "sources").iterdir())] == ["00001_645.txt", "00002_646.txt"]
    assert packages.project_file(folder) == {"workshop": "present", "views": ["work", "casting", "names"]}
    assert packages.view(folder, "work")["castReady"] is True

    again = projectfile.repack(folder, tmp_path / "lai.abookproj")
    with ProjectFile(packed) as before, ProjectFile(again) as after:
        after.verify()
        skipped = {"book.json"}
        assert {n: m for n, m in before.manifest["files"].items() if n not in skipped} == {
            n: m for n, m in after.manifest["files"].items() if n not in skipped}
        assert before.aliases == after.aliases
        assert (before.manifest["projectRoot"], before.manifest["sources"], before.workshop) == (
            after.manifest["projectRoot"], after.manifest["sources"], after.workshop)
        assert before.read("project/work/s3.wav") == after.read("project/work/s3.wav")
        assert after.views == before.views
        target, _ = after.open_into(tmp_path / "may_moi")
    assert store.is_project(target) and (target / "output" / "chapters" / "00001_645.mp3").is_file()


def test_the_listener_edits_ride_in_the_project_file_and_the_book_is_not_rewritten(tmp_path: Path) -> None:
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    folder = _opened_as_a_book(packed, tmp_path / "dien_thoai")
    book_edits.set_title(folder, "Tên mới")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    saved = projectfile.repack(folder, tmp_path / "da_sua.abookproj")

    with ProjectFile(saved) as opened:
        opened.verify()
        assert opened.workshop == PRESENT and opened.edits["title"] == "Tên mới" and book_edits.count(opened.edits) == 2
        assert opened.book["package"]["version"] == 4 and "edits.json" in opened.book["package"]["files"]
        assert opened.manifest["files"]["edits.json"] == opened.book["package"]["files"]["edits.json"]
        assert opened.book["title"] == "Sách thử · Tập 1", "lớp sách không bị sửa tại chỗ"
    with ProjectFile(packed) as before, ProjectFile(saved) as after:
        assert before.read("project/project.sqlite3") == after.read("project/project.sqlite3")
        assert before.read("chapters/00001_645.mp3") == after.read("chapters/00001_645.mp3")
    # cùng cuốn lưu thành .abook: không mang xưởng, vẫn mang phần sửa
    book = bookfile.repack(folder, tmp_path / "sach.abook")
    with bookfile.BookFile(book) as opened_book:
        opened_book.verify()
        assert book_edits.count(opened_book.edits) == 2
        assert not [name for name in opened_book.content if name.startswith(("project/", "sources/", "views/"))]


def test_a_project_file_with_a_cover_edit_and_nothing_else_survives_the_trip(tmp_path: Path) -> None:
    from tests import book_edits_fixtures as shared

    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    folder = _opened_as_a_book(packed, tmp_path / "dien_thoai")
    book_edits.set_cover(folder, shared.tiny_cover(), now=1759400000)
    saved = projectfile.repack(folder, tmp_path / "da_sua.abookproj")
    with ProjectFile(saved) as opened:
        opened.verify()
        assert opened.edits_cover() == (folder / "edits" / "cover.jpg").read_bytes()
        assert opened.edits["cover"]["version"] == 1759400000


# ---- bí danh hỏng ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("damage", ["target_missing", "different_bytes", "alias_stored_too", "workshop_missing"])
def test_a_broken_alias_or_workshop_marker_is_refused(tmp_path: Path, damage: str) -> None:
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")

    def change(name: str, data: bytes) -> bytes:
        if name != projectfile.MANIFEST:
            return data
        manifest = json.loads(data)
        aliases = manifest["aliases"]
        if damage == "target_missing":
            aliases["project/work/s3.wav"] = "samples/9.wav"
        elif damage == "different_bytes":
            manifest["files"]["project/work/s3.wav"] = {"size": 1, "sha256": "0" * 64}
        elif damage == "workshop_missing":
            del manifest["workshop"]
        return json.dumps(manifest).encode("utf-8")

    bad = _rewrite_plain(packed, tmp_path / "hong.abookproj", change)
    if damage == "alias_stored_too":
        with zipfile.ZipFile(bad, "a") as archive:
            archive.writestr("project/work/s3.wav", b"RIFF" + b"\0" * 400)
    with pytest.raises(ProjectFileError):
        ProjectFile(bad)


def _rewrite_plain(path: Path, target: Path, change: Any) -> Path:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            sink.writestr(info, change(info.filename, source.read(info.filename)))
    return target


def test_an_older_format_is_not_read(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")

    def older(name: str, data: bytes) -> bytes:
        if name != projectfile.MANIFEST:
            return data
        manifest = json.loads(data)
        manifest["version"] = 2
        return json.dumps(manifest).encode("utf-8")

    with pytest.raises(ProjectFileError, match="cũ hơn"):
        ProjectFile(_rewrite_plain(packed, tmp_path / "cu.abookproj", older))


# ---- mở file của dự án đã có trên máy ----------------------------------------------------------------------------------


def _phone_edit(packed: Path, tmp_path: Path, name: str = "dien_thoai") -> Path:
    """Điện thoại mở file, sửa tên sách + tên một nhân vật, lưu lại thành .abookproj."""
    folder = _opened_as_a_book(packed, tmp_path / name)
    book_edits.set_title(folder, "Tên mới")
    book_edits.set_character_name(folder, "LUCIEN", "Lu-xi-en")
    return projectfile.repack(folder, tmp_path / f"{name}.abookproj")


def test_opening_the_file_of_a_project_already_here_folds_its_edits_instead_of_making_a_second_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    app = _app(tmp_path, project.parent)
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    edited = _phone_edit(packed, tmp_path)

    plain = app.open_book_file(str(packed))
    assert plain == {"id": book_id(project), "how": "project"}

    opened = app.open_book_file(str(edited))
    assert opened == {"id": book_id(project), "how": "project", "edits": 2}
    assert len(app.library.projects()) == 1
    assert book_edits.count(book_edits.incoming(project)) == 2, "cất chờ người dùng đồng ý, chưa áp gì"
    assert not (project / "studio_title.json").exists()

    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/edits/fold", headers=TOKEN, body={})
    finally:
        server.stop()
    assert status == 200 and json.loads(data)["applied"] == 2
    assert store.summarize(project, running=False)["title"] == "Tên mới"


def test_a_file_with_chapters_the_project_does_not_have_is_a_different_copy_and_opens_as_a_new_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    app = _app(tmp_path, project.parent)
    further = _project(tmp_path / "noi_khac")
    second = further / "output" / "chapters" / "00002_646.mp3"
    second.write_bytes(b"ID3" + bytes(range(255, 0, -1)) * 20)
    with sqlite3.connect(further / store.DB_NAME) as db:
        db.execute("UPDATE chapters SET status = 'completed', output_mp3 = ?, completed_at = 1 WHERE id = 2", (str(second),))
    packed = projectfile.pack(further, tmp_path / "xa_hon.abookproj")

    opened = app.open_book_file(str(packed))

    assert opened["how"] == "studio" and opened["id"] != book_id(project)
    assert len(app.library.projects()) == 2


def test_a_project_file_edited_on_a_phone_opens_on_a_machine_without_the_project_as_a_new_project_with_the_edits_waiting(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    edited = _phone_edit(packed, tmp_path)
    app = _app(tmp_path / "may_khac", tmp_path / "thu_vien_moi")

    opened = app.open_book_file(str(edited))

    [created] = app.library.projects()
    assert opened["how"] == "studio" and opened["edits"] == 2 and opened["id"] == book_id(created)
    assert book_edits.count(book_edits.incoming(created)) == 2


def test_without_studio_a_project_file_opens_as_a_book_that_can_be_saved_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    app = _app(tmp_path / "may_khong_studio", tmp_path / "thu_vien")
    monkeypatch.setattr(app, "capabilities", lambda path=None: {"toolchain": False, "workshop": False, "link": False})

    opened = app.open_book_file(str(packed))
    assert opened["how"] == "new"
    folder = app.library.resolve_listenable(opened["id"])
    assert packages.is_package(folder) and (folder / "project" / "project.sqlite3").is_file()
    view = app.listen_book(opened["id"])
    assert view["projectFile"] == {"workshop": "present", "views": ["names"]}

    server = Server(app, port=0).start()
    try:
        book_edits.set_title(folder, "Tên mới")
        status, data, _ = _request(server.port, "POST", f"/api/books/{opened['id']}/save", headers=TOKEN,
                                   body={"target": str(tmp_path / "xuat")})
    finally:
        server.stop()
    saved = json.loads(data)
    assert status == 200 and Path(saved["file"]).suffix == ".abookproj", "Lưu giữ đúng loại file"
    with ProjectFile(Path(saved["file"])) as again:
        again.verify()
        assert again.workshop == PRESENT and again.edits["title"] == "Tên mới"


def test_open_book_file_says_nothing_new_when_the_file_is_the_same_book_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    app = _app(tmp_path / "may_khong_studio", tmp_path / "thu_vien")
    monkeypatch.setattr(app, "capabilities", lambda path=None: {"toolchain": False, "workshop": False, "link": False})
    first = app.open_book_file(str(packed))
    second = app.open_book_file(str(packed))
    assert second == {"id": first["id"], "how": "existing"}


# ---- views qua máy chủ ------------------------------------------------------------------------------------------------


def test_the_work_casting_and_name_routes_answer_from_the_snapshot_of_a_book_without_a_workshop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_views(monkeypatch)
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    app = _app(tmp_path / "may_khong_studio", tmp_path / "thu_vien")
    monkeypatch.setattr(app, "capabilities", lambda path=None: {"toolchain": False, "workshop": False, "link": False})
    identifier = app.open_book_file(str(packed))["id"]
    server = Server(app, port=0).start()
    try:
        work = _request(server.port, "GET", f"/api/books/{identifier}/work", headers=TOKEN)
        casting = _request(server.port, "GET", f"/api/books/{identifier}/casting", headers=TOKEN)
        names = _request(server.port, "GET", f"/api/books/{identifier}/pronunciations", headers=TOKEN)
        chapter = _request(server.port, "GET", f"/api/books/{identifier}/casting/1", headers=TOKEN)
    finally:
        server.stop()
    assert work[0] == 200 and json.loads(work[1])["items"][0]["title"] == "Hailkes"
    assert casting[0] == 200 and json.loads(casting[1])["chapters"][0]["lines"] == 3
    assert names[0] == 200 and json.loads(names[1])["items"][0]["spoken"] == "Hên-khơ"
    assert chapter[0] == 404


def test_an_imported_book_without_snapshots_answers_404_not_an_error(tmp_path: Path) -> None:
    from tests import book_edits_fixtures as shared

    library = tmp_path / "thu_vien"
    folder = library / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    app = _app(tmp_path, library)
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/api/books/{book_id(folder)}/work", headers=TOKEN)
    finally:
        server.stop()
    assert status == 404 and "bản chụp" in json.loads(data)["error"]


# ---- chờ dựng xưởng ----------------------------------------------------------------------------------------------------


def _pending_file(tmp_path: Path) -> Path:
    """Một file .abook được mở trên "điện thoại" (sửa tên sách), rồi lưu thành .abookproj: không có xưởng."""
    abook = bookfile.pack(_project(tmp_path), tmp_path / "sach.abook")
    phone = _app(tmp_path / "dien_thoai", tmp_path / "thu_vien_dien_thoai")
    folder = phone.library.resolve_listenable(phone.open_book_file(str(abook))["id"])
    book_edits.set_title(folder, "Tên mới")
    return projectfile.repack(folder, tmp_path / "cho_xuong.abookproj")


def test_a_book_saved_as_a_project_has_no_workshop_and_says_so(tmp_path: Path) -> None:
    pending = _pending_file(tmp_path)
    with ProjectFile(pending) as opened:
        opened.verify()
        assert opened.workshop == PENDING and opened.manifest["projectRoot"] == "" and opened.manifest["sources"] == []
        assert not [name for name in opened.manifest["files"] if name.startswith(("project/", "sources/"))]
        assert opened.edits["title"] == "Tên mới" and opened.listenable
        with pytest.raises(ProjectFileError, match="chưa có xưởng"):
            opened.open_into(tmp_path / "thu_vien")
    names = zipfile.ZipFile(pending).namelist()
    assert names[0] == "mimetype" and names[1] == "project.json"
    assert json.loads(_zip_bytes(pending, "project.json"))["workshop"] == "pending"


def test_a_project_file_without_a_workshop_cannot_carry_a_project_folder(tmp_path: Path) -> None:
    pending = _pending_file(tmp_path)
    real = projectfile.pack(_project(tmp_path / "x"), tmp_path / "that.abookproj")

    def sneak(name: str, data: bytes) -> bytes:
        if name != projectfile.MANIFEST:
            return data
        manifest = json.loads(data)
        manifest["workshop"] = "pending"
        return json.dumps(manifest).encode("utf-8")

    with pytest.raises(ProjectFileError, match="chưa có xưởng"):
        ProjectFile(_rewrite_plain(real, tmp_path / "gia.abookproj", sneak))
    assert pending.is_file()


def test_the_studio_offers_to_build_the_workshop_and_seeds_it_from_the_book(tmp_path: Path) -> None:
    pending = _pending_file(tmp_path)
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien_studio")

    opened = studio.open_book_file(str(pending))
    assert opened["how"] == "new"
    view = studio.listen_book(opened["id"])
    assert view["projectFile"] == {"workshop": "pending", "views": [], "built": None}
    assert view["title"] == "Tên mới"

    server = Server(studio, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{opened['id']}/workshop", headers=TOKEN, body={})
        again = _request(server.port, "POST", f"/api/books/{opened['id']}/workshop", headers=TOKEN, body={})
    finally:
        server.stop()
    built = json.loads(data)
    assert status == 201 and built["chapters"] == 2 and built["voices"] == 1 and built["chaptersWithoutText"] == 0
    assert again[0] == 409 and "đã dựng" in json.loads(again[1])["error"], "không dựng hai xưởng cho một cuốn"
    project = studio.library.resolve(built["id"])
    assert project is not None and store.is_project(project)
    assert store.summarize(project, running=False)["title"] == "Tên mới", "tên người nghe đặt"
    with sqlite3.connect(project / store.DB_NAME) as db:
        assert db.execute("SELECT canonical_name, locked_voice_key FROM characters").fetchall() == [
            ("LUCIEN", "preset_thanh_binh_f087_p+00")], "giọng nhân vật được ghim theo khoá trong cast.json"
        assert db.execute("SELECT preset_name FROM voice_profiles WHERE voice_key = 'preset_thanh_binh_f087_p+00'").fetchone() == ("Thanh Bình",)
    source = sorted((studio.library.root / workshop.SOURCE_FOLDER).rglob("*.txt"))
    assert [path.name for path in source] == ["00001.txt", "00002.txt"]
    first = source[0].read_text(encoding="utf-8")
    assert first.startswith("Chương 646 - Trở về (1)\n\nTrời đã sáng. “Đi thôi.”")
    assert studio.listen_book(opened["id"])["projectFile"]["built"] == built["id"], "giao diện mời mở xưởng đã dựng"


def test_building_needs_the_studio_and_a_pending_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.server import ApiError

    studio = _app(tmp_path / "studio", tmp_path / "thu_vien_studio")
    opened = studio.open_book_file(str(_pending_file(tmp_path)))
    monkeypatch.setattr(studio, "capabilities", lambda path=None: {"toolchain": False, "workshop": False, "link": False})
    with pytest.raises(ApiError, match="Cần cài Studio"):
        studio.build_workshop(opened["id"])
    plain = _app(tmp_path / "may_khac", tmp_path / "thu_vien_khac")
    book = plain.open_book_file(str(bookfile.pack(_project(tmp_path / "y"), tmp_path / "y.abook")))
    with pytest.raises(ApiError, match="không chờ dựng xưởng"):
        plain.build_workshop(book["id"])


def test_wishes_that_still_make_sense_become_requests_in_the_new_workshop(tmp_path: Path) -> None:
    from abook.webui import book_wishes

    abook = bookfile.pack(_project(tmp_path), tmp_path / "sach.abook")
    phone = _app(tmp_path / "dien_thoai", tmp_path / "thu_vien_dien_thoai")
    folder = phone.library.resolve_listenable(phone.open_book_file(str(abook))["id"])
    book_wishes.request_pronunciation(folder, "Hailkes", "Hên-khơ", now=1759400001.5)
    saved = projectfile.repack(folder, tmp_path / "cho_xuong.abookproj")
    studio = _app(tmp_path / "studio", tmp_path / "thu_vien_studio")
    opened = studio.open_book_file(str(saved))

    built = studio.build_workshop(opened["id"])

    project = studio.library.resolve(built["id"])
    assert built["requests"] == 1
    overrides = json.loads((project / "overrides.json").read_text(encoding="utf-8"))
    assert overrides["pronunciations"]["hailkes"]["spoken_form"] == "Hên-khơ"


# ---- đối chiếu với app Android (tests/fixtures/book_edits/written/) ---------------------------------------------------


WRITTEN = Path(__file__).parent / "fixtures" / "book_edits" / "written"
EVERYTHING = book_edits.count(book_edits.parse((WRITTEN.parent / "edits" / "everything.json").read_bytes()))


def test_the_project_files_python_wrote_for_the_android_app_are_valid_and_carry_no_local_path() -> None:
    with ProjectFile(WRITTEN / "python_workshop.abookproj") as workshop_file:
        workshop_file.verify()
        assert workshop_file.workshop == PRESENT and workshop_file.views == ["work", "casting", "names"]
        assert set(workshop_file.aliases) == {"project/cover.jpg", "project/output/chapters/00001_645.mp3", "project/work/s3.wav"}
        assert workshop_file.manifest["projectRoot"] == r"D:\Studio\sach_thu"
    with ProjectFile(WRITTEN / "python_pending.abookproj") as pending_file:
        pending_file.verify()
        assert pending_file.workshop == PENDING and book_edits.count(pending_file.edits) == EVERYTHING
    for name in ("python_workshop.abookproj", "python_pending.abookproj", "kotlin_workshop.abookproj", "kotlin_pending.abookproj"):
        with zipfile.ZipFile(WRITTEN / name) as archive:
            for entry in archive.namelist():
                assert b"NGDtuanh" not in archive.read(entry) and b"AppData" not in archive.read(entry), (name, entry)


def test_the_project_files_the_android_app_wrote_open_here_with_the_same_content() -> None:
    with ProjectFile(WRITTEN / "python_workshop.abookproj") as expected, ProjectFile(WRITTEN / "kotlin_workshop.abookproj") as written:
        written.verify()
        assert written.workshop == PRESENT
        assert written.aliases == expected.aliases, "cùng luật bí danh ở hai bên"
        skipped = {"book.json"}
        assert {n: m for n, m in written.manifest["files"].items() if n not in skipped} == {
            n: m for n, m in expected.manifest["files"].items() if n not in skipped}
        assert (written.manifest["projectRoot"], written.manifest["sources"]) == (expected.manifest["projectRoot"], expected.manifest["sources"])
        assert written.view("work") == expected.view("work")
    with ProjectFile(WRITTEN / "kotlin_pending.abookproj") as pending_written:
        pending_written.verify()
        assert pending_written.workshop == PENDING and book_edits.count(pending_written.edits) == EVERYTHING
        assert pending_written.edits_cover() == (WRITTEN.parent / "edits" / "everything.cover.jpg").read_bytes()


def test_a_project_file_the_android_app_wrote_opens_as_a_project_here(tmp_path: Path) -> None:
    with ProjectFile(WRITTEN / "kotlin_workshop.abookproj") as written:
        target, report = written.open_into(tmp_path / "thu_vien")
    assert store.is_project(target) and (target / "output" / "chapters" / "00001_645.mp3").is_file()
    assert (target / "work" / "s3.wav").is_file() and (target / "cover.jpg").is_file()
    assert report["changed"] >= 1
