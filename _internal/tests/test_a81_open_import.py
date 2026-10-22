"""Soát a81: mở / nhập file `.abook` và `.abookproj` của người lạ - từ chối rõ ràng hoặc nhận trọn, không bao giờ làm sập thư viện."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from abook.webui import bookfile, packages
from abook.webui.bookfile import BookFile, BookFileError
from abook.webui.fingerprints import Fingerprints
from tests.a81_files import app_in, build, build_golden, golden_cases, simple_book


def _import(tmp_path: Path, file: Path, library: Path | None = None) -> tuple[Path, str]:
    library = library or tmp_path / "lib"
    library.mkdir(exist_ok=True)
    return packages.import_file(file, library, [], Fingerprints(tmp_path / "fp.json"), {})


# ---- 1. kiểu trường của book.json --------------------------------------------------------------------

def _chapter(key: str, value: Any):
    return lambda book: book["chapters"][0].__setitem__(key, value)


def _top(key: str, value: Any):
    return lambda book: book.__setitem__(key, value)


BAD_SHAPES = {
    "duration=[1]": _chapter("duration", [1]),
    "duration='abc'": _chapter("duration", "abc"),
    "skip=5": _chapter("skip", 5),
    "part='a'": _chapter("part", "a"),
    "id=[1]": _chapter("id", [1]),
    "title=5": _chapter("title", 5),
    "available='yes'": _chapter("available", "yes"),
    "chaptersTotal='x'": _top("chaptersTotal", "x"),
    "chaptersTotal=[1]": _top("chaptersTotal", [1]),
    "chaptersAvailable=1.5": _top("chaptersAvailable", 1.5),
    "parts=5": _top("parts", 5),
    "parts duration": _top("parts", [{"part": 1, "chapters": [1, 1], "duration": "x"}]),
    "samples=5": _top("samples", 5),
    "title=[1]": _top("title", [1]),
    "chapters=5": _top("chapters", 5),
    "chapters=[5]": _top("chapters", [5]),
    "duration=inf": _top("duration", float("inf")),
}


@pytest.mark.parametrize("label", list(BAD_SHAPES))
def test_a_book_json_with_the_wrong_kind_of_field_is_refused_on_import(tmp_path: Path, label: str) -> None:
    """Một file bạn bè gửi qua Zalo mà `listen()` ném TypeError thì cả thư viện sập: phải từ chối ngay lúc nhập."""
    book, entries = simple_book(1)
    BAD_SHAPES[label](book)
    file = build(tmp_path / "x.abook", entries, book)

    with pytest.raises(BookFileError) as refused:
        _import(tmp_path, file)

    assert "bạn" in str(refused.value).lower()
    assert not list((tmp_path / "lib").glob("*/*")), "không để lại thư mục nào trong thư viện"


def test_the_app_own_book_json_still_passes_the_shape_check(tmp_path: Path) -> None:
    book, entries = simple_book(2)
    book["parts"] = [{"part": 1, "title": "Phần 1", "chapters": [1, 2], "duration": 2.0, "narrator": "A"}]
    book["chapters"][1]["skip"] = [0, 3]
    book["chapters"][1]["part"] = 1
    book["title"] = None
    with BookFile(build(tmp_path / "ok.abook", entries, book)):
        pass


def test_one_broken_book_does_not_take_the_whole_listen_library_down(tmp_path: Path) -> None:
    """Cuốn trên đĩa có `book.json` hỏng kiểu (đã nhập từ bản app cũ, hay sửa tay) thì cuốn ấy bị bỏ qua - các cuốn khác vẫn hiện."""
    library = tmp_path / "lib"
    library.mkdir()
    app = app_in(tmp_path, library)
    good_book, good_entries = simple_book(1, "Cuốn lành")
    bad_book, bad_entries = simple_book(1, "Cuốn hỏng")
    bad_entries["chapters/001.mp3"] = b"ID3" + b"\x07" * 100
    app.open_book_file(str(build(tmp_path / "good.abook", good_entries, good_book)))
    bad = app.open_book_file(str(build(tmp_path / "bad.abook", bad_entries, bad_book)))
    folder = app.library.resolve_listenable(bad["id"])
    document = json.loads((folder / "book.json").read_text(encoding="utf-8"))
    document["chapters"][0]["duration"] = [1]
    (folder / "book.json").write_bytes(json.dumps(document).encode("utf-8"))

    shelf = app.listen_library()

    assert [book["title"] for book in shelf] == ["Cuốn lành"]


# ---- 2. zip bomb: tỉ lệ nén ---------------------------------------------------------------------------

def test_an_audio_entry_that_compresses_a_thousand_to_one_is_refused(tmp_path: Path) -> None:
    """Âm thanh thật gần như không nén được. 40 MB toàn số 0 trong 40 KB là bom nén: từ chối TRƯỚC khi giải ra đĩa của người nhận."""
    book, entries = simple_book(1)
    entries["chapters/001.mp3"] = bytes(40 * 1024 * 1024)
    file = build(tmp_path / "bomb.abook", entries, book, deflate=("chapters/001.mp3",))
    assert file.stat().st_size < 1024 * 1024

    with pytest.raises(BookFileError) as refused:
        _import(tmp_path, file)

    assert "bạn" in str(refused.value).lower() and "chapters/001.mp3" in str(refused.value)
    assert not list((tmp_path / "lib").glob("*/*")), "chưa ghi gì vào thư viện"


def test_a_text_entry_that_is_a_huge_run_of_spaces_is_refused(tmp_path: Path) -> None:
    book, entries = simple_book(1)
    entries["scripts/1.json"] = b" " * (24 * 1024 * 1024)
    file = build(tmp_path / "bomb.abook", entries, book, deflate=("scripts/1.json",))

    with pytest.raises(BookFileError):
        _import(tmp_path, file)


def test_ordinary_compressed_scripts_and_stored_audio_still_import(tmp_path: Path) -> None:
    book, entries = simple_book(1)
    entries["scripts/1.json"] = json.dumps({"segments": [{"text": "xin chào " * 20, "i": n} for n in range(400)]}).encode()
    entries["chapters/001.mp3"] = b"ID3" + bytes(range(256)) * 8000
    file = build(tmp_path / "ok.abook", entries, book, deflate=("scripts/1.json",))

    assert _import(tmp_path, file)[1] == "new"


def test_a_project_file_with_a_compression_bomb_as_audio_is_refused(tmp_path: Path) -> None:
    from abook.webui import projectfile
    from tests.a81_files import build_pending_project

    book, entries = simple_book(1)
    entries["chapters/001.mp3"] = bytes(40 * 1024 * 1024)
    file = build_pending_project(tmp_path / "bomb.abookproj", entries, book, deflate=("chapters/001.mp3",))

    with pytest.raises(projectfile.ProjectFileError) as refused:
        projectfile.ProjectFile(file)

    assert "bạn" in str(refused.value).lower()


def test_a_project_file_with_a_wrongly_typed_listening_layer_is_refused(tmp_path: Path) -> None:
    from abook.webui import projectfile
    from tests.a81_files import build_pending_project

    book, entries = simple_book(1)
    book["chapters"][0]["duration"] = [1]

    with pytest.raises(projectfile.ProjectFileError) as refused:
        projectfile.ProjectFile(build_pending_project(tmp_path / "x.abookproj", entries, book))

    assert "bạn" in str(refused.value).lower()


# ---- 3, 9. nhập đồng thời / cập nhật khi chương đang mở -------------------------------------------------

def test_the_same_file_opened_from_four_threads_is_one_new_book_and_three_existing(tmp_path: Path) -> None:
    """Bấm đúp hai lần, hay hai bản gửi cùng lúc: mọi lượt đều thành công (new / existing), không lượt nào ăn PermissionError."""
    from concurrent.futures import ThreadPoolExecutor

    library = tmp_path / "lib"
    library.mkdir()
    prints = Fingerprints(tmp_path / "fp.json")
    for round_ in range(6):  # nhiều vòng: lỗi này là chạy đua, một vòng có thể lọt
        book, entries = simple_book(3, f"Sách {round_}")
        entries = {name: data + bytes([round_]) if name.endswith(".mp3") else data for name, data in entries.items()}
        file = build(tmp_path / f"x{round_}.abook", entries, book)
        with ThreadPoolExecutor(4) as pool:
            hows = list(pool.map(lambda _: packages.import_file(file, library, [], prints, {})[1], range(4)))
        assert sorted(hows) == ["existing", "existing", "existing", "new"], hows


def _hold_open(folder: Path):
    """Một chương đang phát: giữ file mở như trình phát (Windows không cho đổi tên thư mục chứa nó)."""
    return next(folder.glob("chapters/*.mp3")).open("rb")


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="chỉ Windows khoá thư mục có file đang mở")
def test_updating_a_book_whose_chapter_is_playing_says_so_and_keeps_the_old_copy(tmp_path: Path) -> None:
    older_book, older = simple_book(1)
    newer_book, newer = simple_book(2)
    library = tmp_path / "lib"
    library.mkdir()
    prints = Fingerprints(tmp_path / "fp.json")
    folder, how = packages.import_file(build(tmp_path / "a.abook", older, older_book), library, [], prints, {})
    assert how == "new"

    with _hold_open(folder):
        with pytest.raises(BookFileError) as refused:
            packages.import_file(build(tmp_path / "b.abook", newer, newer_book), library, [], prints, {})

    assert "đang phát" in str(refused.value) and "bạn" in str(refused.value).lower()
    assert "chỉ đọc" not in str(refused.value)
    assert sorted(p.name for p in folder.glob("chapters/*.mp3")) == ["001.mp3"], "bản cũ còn nguyên"
    assert not [p for p in (library / "Sách đã nhập").iterdir() if p.name.startswith(".")], "không để thư mục tạm"


# ---- 4, 5, 7, 8. ngoại lệ lạ, manifest.json tuỳ chọn, dự án chưa có chương, lược đồ mới hơn --------------------------------

def _damaged_variants(tmp_path: Path) -> dict[str, Path]:
    from tests.a81_files import patch_header

    book, entries = simple_book(2)
    ok = build(tmp_path / "ok.abook", entries, book)
    return {
        "json lồng sâu": build(tmp_path / "deep.abook", entries, raw_book=("[" * 200000 + "]" * 200000).encode()),
        "book.json mã hoá": patch_header(ok, tmp_path / "enc.abook", "book.json", flags=1),
        "chương mã hoá": patch_header(ok, tmp_path / "enc2.abook", "chapters/001.mp3", flags=1),
        "nén kiểu 99": patch_header(ok, tmp_path / "m99.abook", "book.json", method=99),
        "book.json là mảng": build(tmp_path / "arr.abook", entries, raw_book=b"[1,2]"),
        "package.files là mảng": build(tmp_path / "pf.abook", entries, raw_book=json.dumps(
            {"title": "x", "package": {"format": "abook", "version": 1, "files": []}}).encode()),
    }


@pytest.mark.parametrize("label", ["json lồng sâu", "book.json mã hoá", "chương mã hoá", "nén kiểu 99", "book.json là mảng",
                                   "package.files là mảng"])
def test_any_odd_failure_on_a_foreign_file_is_a_vietnamese_book_file_error(tmp_path: Path, label: str) -> None:
    file = _damaged_variants(tmp_path)[label]

    with pytest.raises(BookFileError) as refused:
        packages.import_file(file, tmp_path / "lib", [], Fingerprints(tmp_path / "fp.json"), {})

    assert "bạn" in str(refused.value).lower() or "sách" in str(refused.value).lower()
    assert "Error" not in str(refused.value) and "password" not in str(refused.value)


def test_a_book_without_the_readium_manifest_still_imports(tmp_path: Path) -> None:
    """manifest.json (Readium) chỉ để app khác đọc audio: không bắt buộc, điện thoại nhập được thì máy tính cũng phải nhập được."""
    book, entries = simple_book(2)
    file = build(tmp_path / "x.abook", entries, book, manifest=False)

    folder, how = _import(tmp_path, file)

    assert how == "new" and (folder / "book.json").is_file() and not (folder / "manifest.json").exists()


def test_a_project_file_with_no_finished_chapter_says_so_on_a_machine_without_studio(tmp_path: Path) -> None:
    from abook.webui import projectfile
    from tests.a81_files import build_project, sqlite_bytes

    database = sqlite_bytes(tmp_path / "db.sqlite3")
    file = build_project(tmp_path / "fresh.abookproj", {"project/project.sqlite3": database, "project/book_settings.json": b"{}"})

    with pytest.raises(projectfile.ProjectFileError) as refused:
        _import(tmp_path, file)

    assert "Studio" in str(refused.value) and "bạn" in str(refused.value).lower()
    assert not list((tmp_path / "lib").rglob("*")) or all(p.is_dir() for p in (tmp_path / "lib").rglob("*"))
    assert not list((tmp_path / "lib").glob("*/*")), "không để thư mục thừa"


def test_a_project_made_by_a_newer_app_is_refused_before_anything_is_unpacked(tmp_path: Path, monkeypatch) -> None:
    from abook.database import SCHEMA_VERSION
    from abook.webui import projectfile
    from tests.a81_files import build_project, sqlite_bytes

    database = sqlite_bytes(tmp_path / "db.sqlite3", user_version=SCHEMA_VERSION + 1)
    file = build_project(tmp_path / "new.abookproj", {"project/project.sqlite3": database, "project/book_settings.json": b"{}"})
    unpacked = []
    monkeypatch.setattr(projectfile.ProjectFile, "_copy_checked", lambda *a, **k: unpacked.append(a))
    library = tmp_path / "lib"
    library.mkdir()

    with pytest.raises(projectfile.ProjectFileError) as refused:
        with projectfile.ProjectFile(file) as opened:
            opened.open_into(library)

    assert "mới hơn" in str(refused.value) and "cập nhật" in str(refused.value) and not unpacked
    assert list(library.iterdir()) == []


def test_a_project_with_the_current_schema_is_still_accepted(tmp_path: Path) -> None:
    from abook.webui import projectfile
    from tests.a81_files import build_project, sqlite_bytes

    database = sqlite_bytes(tmp_path / "db.sqlite3")
    file = build_project(tmp_path / "ok.abookproj", {"project/project.sqlite3": database, "project/book_settings.json": b"{}"})

    with projectfile.ProjectFile(file) as opened:
        assert opened.workshop == "present"


# ---- 6, 16. tên mục trùng nhau trên đĩa Windows ------------------------------------------------------------------

def test_two_entries_that_differ_only_by_case_are_refused(tmp_path: Path) -> None:
    """a.mp3 và A.mp3 là MỘT file trên NTFS: chương 2 sẽ phát giọng chương 1 mà không ai báo."""
    book, entries = simple_book(1)
    entries = {"cast.json": entries["cast.json"], "chapters/a.mp3": b"ID3" + b"A" * 50, "chapters/A.mp3": b"ID3" + b"B" * 60}
    book["chapters"] = [{"id": 1, "index": 1, "title": "1", "file": "chapters/a.mp3", "available": True, "duration": 1},
                        {"id": 2, "index": 2, "title": "2", "file": "chapters/A.mp3", "available": True, "duration": 1}]
    book["chaptersTotal"] = book["chaptersAvailable"] = 2

    with pytest.raises(BookFileError) as refused:
        _import(tmp_path, build(tmp_path / "case.abook", entries, book))

    assert "trùng" in str(refused.value) and "bạn" in str(refused.value).lower()
    assert not list((tmp_path / "lib").glob("*/*"))


@pytest.mark.parametrize("second", ["project/Notes.txt", "project/notes.txt.", "project/notes.txt "])
def test_project_entries_that_land_on_the_same_windows_file_are_refused(tmp_path: Path, second: str) -> None:
    from abook.webui import projectfile
    from tests.a81_files import build_project, sqlite_bytes

    entries = {"project/project.sqlite3": sqlite_bytes(tmp_path / "db.sqlite3"), "project/book_settings.json": b"{}",
               "project/notes.txt": b"a", second: b"b"}
    file = build_project(tmp_path / "x.abookproj", entries)

    with pytest.raises(projectfile.ProjectFileError) as refused:
        projectfile.ProjectFile(file)

    assert "trùng" in str(refused.value)


# ---- 15. cùng âm thanh, đổi tiêu đề --------------------------------------------------------------------------------

def test_the_same_audio_under_a_new_title_says_the_title_was_not_taken(tmp_path: Path) -> None:
    library = tmp_path / "lib"
    library.mkdir()
    app = app_in(tmp_path, library)
    book, entries = simple_book(1, "Sách thử")
    app.open_book_file(str(build(tmp_path / "a.abook", entries, book)))
    renamed, _ = simple_book(1, "Tên mới trong file")

    again = app.open_book_file(str(build(tmp_path / "b.abook", entries, renamed)))

    assert again["how"] == "existing" and again["otherTitle"] == "Tên mới trong file"
    same = app.open_book_file(str(tmp_path / "a.abook"))
    assert same["how"] == "existing" and "otherTitle" not in same, "cùng tên thì không có gì để nói"


# ---- 13. một bộ file vàng cho cả hai nền ---------------------------------------------------------------------------------

@pytest.mark.parametrize("case", golden_cases(), ids=lambda case: case["name"])
def test_the_shared_golden_files_get_the_same_verdict_as_on_the_phone(tmp_path: Path, case: dict) -> None:
    """tests/fixtures/book_files/cases.json: BookFileGoldenTest (JVM) đọc đúng những file này. Máy tính nhận mà điện thoại từ chối (hay
    ngược lại) thì file đi từ máy này sang máy kia hỏng im lặng."""
    file = build_golden(tmp_path / "case.abook", case)

    if case["expect"] == "refused":
        with pytest.raises(BookFileError):
            _import(tmp_path, file)
        assert not list((tmp_path / "lib").glob("*/*"))
    else:
        folder, how = _import(tmp_path, file)
        assert how == "new"
        packages.listen(folder, "id", {}, with_chapters=False)


def test_a_book_that_does_not_fit_the_disk_says_how_much_room_the_listener_needs(tmp_path: Path, monkeypatch) -> None:
    import shutil
    from collections import namedtuple

    book, entries = simple_book(1)
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage(10**9, 10**9 - 1000, 1000))

    with pytest.raises(BookFileError) as refused:
        _import(tmp_path, build(tmp_path / "x.abook", entries, book))

    assert "cần khoảng" in str(refused.value) and "còn" in str(refused.value) and "Bạn hãy" in str(refused.value)
