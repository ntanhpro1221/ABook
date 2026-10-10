"""Xuất cả bộ (webui/export.export_series + hộp Xuất của Studio): một truyện chia nhiều dự án bằng "Làm tiếp cuốn này".

Fixture: `make_project` (chương 1 đã có MP3) dời vào một thư viện, mỗi phần một thư mục, nối bằng `continues.json`.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from abook import continuation
from abook.webui import bookfile, export
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from tests.test_webui_listen_and_sync import FakeRunner, _request, make_project


def _part(tmp_path: Path, library: Path, name: str, title: str, previous: Path | None = None, *,
          finished: bool = True) -> Path:
    shutil.move(make_project(tmp_path / f"_{name}", title), library / name)
    project = library / name
    if not finished:
        (project / "output" / "chapters" / "00001_645.mp3").unlink()
    if previous is not None:
        (project / continuation.LINK_FILE).write_text(
            json.dumps({"previous": previous.name, "part": continuation.part_number(previous) + 1}), encoding="utf-8")
    return project.resolve()


@pytest.fixture()
def series(tmp_path: Path) -> tuple[Path, list[Path]]:
    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one)
    three = _part(tmp_path, library, "p3", "Truyện X · Phần 3", two)
    return library, [one, two, three]


@pytest.fixture()
def fake_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không có ffmpeg trong test: chép nguyên luồng như `-c:a copy` làm."""
    monkeypatch.setattr(export, "ffmpeg_executable", lambda: "ffmpeg")

    def run(command: list[str], **_: object) -> None:
        shutil.copyfile(Path(command[command.index("-i") + 1]), Path(command[-1]))

    monkeypatch.setattr(export, "run_hidden", run)


def _mp3(project: Path, folder: Path, label: str) -> dict:
    return export.export_book(project, folder, folder_name=label)


def test_series_discovery_walks_back_to_part_one_and_forward_to_the_last(series: tuple[Path, list[Path]],
                                                                         tmp_path: Path) -> None:
    library, parts = series
    stranger = _part(tmp_path, library, "khac", "Cuốn khác")
    candidates = [stranger, *reversed(parts)]
    for here in parts:
        assert continuation.series_parts(here, candidates) == parts, "đứng ở phần nào cũng ra đủ bộ, phần đầu trước"
    assert continuation.series_parts(stranger, candidates) == [stranger], "cuốn lẻ chỉ có chính nó"


def test_mp3_series_goes_into_one_folder_with_a_subfolder_per_part(series: tuple[Path, list[Path]], tmp_path: Path,
                                                                   fake_ffmpeg: None) -> None:
    _library, parts = series
    result = export.export_series(parts, tmp_path / "xuat", _mp3)
    root = tmp_path / "xuat" / "Truyện X"
    assert Path(result["folder"]) == root and result["partsTotal"] == 3 and result["skipped"] == []
    assert sorted(path.name for path in root.iterdir()) == ["Phần 1 - Truyện X", "Phần 2 - Truyện X", "Phần 3 - Truyện X"]
    for number, part in enumerate(result["parts"], start=1):
        folder = root / f"Phần {number} - Truyện X"
        assert part["files"] == 1 and [path.suffix for path in sorted(folder.iterdir())] == [".mp3", ".m3u8"]


def test_a_part_with_nothing_finished_is_skipped_and_named(tmp_path: Path, fake_ffmpeg: None) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one, finished=False)
    three = _part(tmp_path, library, "p3", "Truyện X · Phần 3", two)
    result = export.export_series([one, two, three], tmp_path / "xuat", _mp3)
    assert result["skipped"] == [{"part": 2, "title": "Truyện X · Phần 2"}]
    assert sorted(path.name for path in (tmp_path / "xuat" / "Truyện X").iterdir()) == ["Phần 1 - Truyện X",
                                                                                         "Phần 3 - Truyện X"]
    # Số phần giữ theo vị trí trong bộ, không đếm lại sau khi bỏ qua: "Phần 3" vẫn là phần 3.
    assert [part["part"] for part in result["parts"]] == [1, 3]

    empty = _part(tmp_path, library, "p4", "Truyện Y", finished=False)
    with pytest.raises(ValueError, match="Chưa phần nào"):
        export.export_series([empty], tmp_path / "xuat2", _mp3)
    assert not (tmp_path / "xuat2").exists(), "không để lại thư mục rỗng"


def _studio(tmp_path: Path, library: Path):
    from abook.webui.server import App, Server

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    return app, Server(app, port=0).start()


def _post(server, project: Path, route: str, body: dict) -> tuple[int, dict]:
    status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/{route}",
                               headers={"X-Ebook-Token": "t"}, body=body)
    return status, json.loads(data)


def test_studio_exports_the_whole_series_as_mp3(series: tuple[Path, list[Path]], tmp_path: Path, fake_ffmpeg: None) -> None:
    library, parts = series
    app, server = _studio(tmp_path, library)
    try:
        status, result = _post(server, parts[1], "export", {"target": str(tmp_path / "xuat"), "series": True})
        alone_status, alone = _post(server, parts[1], "export", {"target": str(tmp_path / "xuat2")})
    finally:
        server.stop()
    assert status == 200 and result["files"] == 3 and len(result["parts"]) == 3
    assert (tmp_path / "xuat" / "Truyện X" / "Phần 2 - Truyện X").is_dir()
    assert alone_status == 200 and alone["files"] == 1 and (tmp_path / "xuat2" / "Truyện X · Phần 2").is_dir(), \
        "không có `series` thì xuất riêng phần này như trước"
    assert result["folder"] in app.exports, "nút Mở thư mục mở được thư mục bộ"


def test_studio_exports_the_whole_series_as_one_book_file_per_part(tmp_path: Path) -> None:
    """Không có `single`: bộ thành mỗi phần một file `.abook` (cho thẻ nhớ FAT32 không chứa nổi file trên 4 GiB)."""
    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one, finished=False)
    three = _part(tmp_path, library, "p3", "Truyện X · Phần 3", two)
    lone = _part(tmp_path, library, "p4", "Cuốn lẻ")
    app, server = _studio(tmp_path, library)
    try:
        status, result = _post(server, three, "bookfile", {"target": str(tmp_path / "xuat"), "series": True})
        lone_status, lone_result = _post(server, lone, "bookfile", {"target": str(tmp_path / "xuat"), "series": True})
    finally:
        server.stop()
    folder = tmp_path / "xuat" / "Truyện X"
    assert status == 200 and Path(result["folder"]) == folder
    assert sorted(path.name for path in folder.iterdir()) == [f"Phần 1 - Truyện X{bookfile.EXTENSION}",
                                                              f"Phần 3 - Truyện X{bookfile.EXTENSION}"]
    assert [part["part"] for part in result["parts"]] == [1, 3]
    assert result["skipped"] == [{"part": 2, "title": "Truyện X · Phần 2"}]
    assert result["size"] == sum(path.stat().st_size for path in folder.iterdir())
    for path in folder.iterdir():
        with bookfile.BookFile(path) as book:
            book.verify()
    assert lone_status == 409 and "chưa có phần nào khác" in lone_result["error"]


def test_studio_exports_the_whole_series_as_a_single_book_file(tmp_path: Path) -> None:
    """`single: true` ("Một file" trong hộp Xuất): cả bộ trong MỘT file phiên bản 3; phần chưa có chương nào bị bỏ qua và
    được kể tên, số phần của các phần còn lại giữ nguyên."""
    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one, finished=False)
    three = _part(tmp_path, library, "p3", "Truyện X · Phần 3", two)
    app, server = _studio(tmp_path, library)
    try:
        status, result = _post(server, three, "bookfile", {"target": str(tmp_path / "xuat"), "series": True, "single": True})
    finally:
        server.stop()
    assert status == 200 and Path(result["folder"]) == tmp_path / "xuat"
    assert [path.name for path in (tmp_path / "xuat").iterdir()] == [f"Truyện X{bookfile.EXTENSION}"], "đúng một file, không thư mục con"
    assert result["file"] == str(tmp_path / "xuat" / f"Truyện X{bookfile.EXTENSION}")
    assert result["size"] == Path(result["file"]).stat().st_size
    assert [part["part"] for part in result["parts"]] == [1, 3] and result["partsTotal"] == 3
    assert result["skipped"] == [{"part": 2, "title": "Truyện X · Phần 2"}]
    with bookfile.BookFile(Path(result["file"])) as book:
        book.verify()
        manifest = json.loads(book.read("book.json"))
    assert manifest["package"]["version"] == 3 and [part["part"] for part in manifest["parts"]] == [1, 3]
    assert result["folder"] in app.exports


def test_a_series_in_one_file_with_nothing_to_hear_is_refused_and_leaves_nothing(tmp_path: Path) -> None:
    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X", finished=False)
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one, finished=False)
    app, server = _studio(tmp_path, library)
    try:
        status, result = _post(server, two, "bookfile", {"target": str(tmp_path / "xuat"), "series": True, "single": True})
    finally:
        server.stop()
    assert status == 409 and "Chưa phần nào" in result["error"] and not (tmp_path / "xuat").exists()


def test_the_export_dialog_can_ask_how_big_the_book_file_will_be(series: tuple[Path, list[Path]], tmp_path: Path) -> None:
    """Hộp Xuất báo cỡ ước lượng (audio các chương nghe được) và cảnh báo khi quá 4 GiB - thẻ nhớ FAT32 không chứa nổi."""
    library, parts = series
    app, server = _studio(tmp_path, library)
    each = (parts[0] / "output" / "chapters" / "00001_645.mp3").stat().st_size
    try:
        status, whole = _get(server, parts[1], "export-size?series=1")
        alone_status, alone = _get(server, parts[1], "export-size")
    finally:
        server.stop()
    assert (status, whole) == (200, {"bytes": 3 * each, "parts": 3, "musicPending": 0})
    assert (alone_status, alone) == (200, {"bytes": each, "parts": 1, "musicPending": 0})


def _get(server, project: Path, route: str) -> tuple[int, dict]:
    status, data, _ = _request(server.port, "GET", f"/api/books/{book_id(project)}/{route}", headers={"X-Ebook-Token": "t"})
    return status, json.loads(data)


def test_the_estimated_size_counts_the_background_music_that_travels_with_the_book(series: tuple[Path, list[Path]],
                                                                                  tmp_path: Path) -> None:
    """Soát UX a8: hộp Xuất ghi "khoảng 0 MB" trong khi file thật 24,9 MB - bài nhạc nền đi kèm không được tính. Bài đã
    có trong bộ đệm tính theo cỡ file; bài chưa tải được đếm riêng (lúc xuất mới tải)."""
    import hashlib

    from abook.webui import music_plan

    library, parts = series
    calm, battle = "https://x/calm.mp3", "https://x/battle.mp3"
    scenes = [{"chapterId": 1, "start": 0.0, "end": 30.0, "link": calm, "key": "1:1"},
              {"chapterId": 1, "start": 30.0, "end": 60.0, "link": calm, "key": "1:5"},
              {"chapterId": 1, "start": 60.0, "end": 90.0, "link": battle, "key": "1:9"}]
    (parts[1] / music_plan.PLAN_FILE).write_text(
        json.dumps({"version": music_plan.PLAN_VERSION, "enabled": True, "levelDb": -18.0, "scenes": scenes, "tracks": {}}),
        encoding="utf-8")
    app, server = _studio(tmp_path, library)
    cache = app.music_dir / "files"
    cache.mkdir(parents=True)
    (cache / (hashlib.sha1(calm.encode("utf-8")).hexdigest() + ".mp3")).write_bytes(b"ID3" + b"x" * 997)
    each = (parts[1] / "output" / "chapters" / "00001_645.mp3").stat().st_size
    try:
        status, alone = _get(server, parts[1], "export-size")
    finally:
        server.stop()
    assert (status, alone) == (200, {"bytes": each + 1000, "parts": 1, "musicPending": 1})


def test_exporting_again_into_the_same_place_never_overwrites_the_first_export(tmp_path: Path) -> None:
    """Soát UX a20: xuất lần hai vào cùng thư mục ghi đè im lặng lên bản trước. Giờ thành "tên (2)", "tên (3)"."""
    from abook.webui.export import free_path

    assert free_path(tmp_path / "Sách.m4b") == tmp_path / "Sách.m4b", "chưa có gì thì giữ tên"
    (tmp_path / "Sách.m4b").write_bytes(b"x")
    assert free_path(tmp_path / "Sách.m4b") == tmp_path / "Sách (2).m4b"
    (tmp_path / "Sách (2).m4b").write_bytes(b"x")
    assert free_path(tmp_path / "Sách.m4b") == tmp_path / "Sách (3).m4b"
    (tmp_path / "Bộ truyện").mkdir()
    assert free_path(tmp_path / "Bộ truyện") == tmp_path / "Bộ truyện (2)", "thư mục: thêm sau tên, không cắt chỗ có dấu chấm"
    (tmp_path / "Tập 1. Mở đầu").mkdir()
    assert free_path(tmp_path / "Tập 1. Mở đầu") == tmp_path / "Tập 1. Mở đầu (2)"
