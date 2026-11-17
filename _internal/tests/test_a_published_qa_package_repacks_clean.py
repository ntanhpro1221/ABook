"""A package the app itself shipped before `seal` refused QA marks (Hello, Hello and Hello: six chapters subtitled
"Cần nghe lại", `qualityPassed`/`failedLines` on every chapter) is never treated as a good package. Lead ruling 18-11:

- writing new data: the packer refuses internal marks (no silent strip of a package's QA fields);
- re-packing from the project: the pipeline sees the old file is not clean and packs again from the project, which is clean;
- a listener's reader shows the same book whether or not a package carries QA fields (behaviour, not a source grep).

`fixtures/book_files/hello_published_book.json` is the real book.json of the shipped Hello package (segments trimmed).
"""
from __future__ import annotations

import copy
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from abook.webui import bookfile, packages
from tests.test_the_book_file_is_the_production_output import _finished_project, _output, _Pipeline

HELLO = json.loads((Path(__file__).parent / "fixtures" / "book_files" / "hello_published_book.json").read_text(encoding="utf-8"))["book"]
QA_KEYS = ("subtitle", "qualityPassed", "qualityWarning", "failedLines")


def _rewrite_manifest(path: Path, change) -> None:
    """Rewrite book.json inside a sealed package (what an older packer wrote), every other entry byte for byte."""
    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    temp = path.with_suffix(".tmp")
    with zipfile.ZipFile(temp, "w") as archive:
        for info, data in entries:
            if info.filename == bookfile.MANIFEST:
                book = json.loads(data)
                change(book)
                data = json.dumps(book, ensure_ascii=False).encode("utf-8")
            archive.writestr(info, data)
    temp.replace(path)


def _graft_hello(book: dict, keys: tuple[str, ...] = QA_KEYS) -> None:
    """Give each chapter the QA state of the matching shipped Hello chapter (second Hello chapter onward: the first is clean)."""
    chapters = [chapter for volume in book.get("volumes") or [] for chapter in volume.get("chapters") or []] or book["chapters"]
    for chapter, shipped in zip(chapters, HELLO["chapters"][1:]):
        chapter.update({key: copy.deepcopy(shipped[key]) for key in keys})


def test_the_shipped_hello_book_carries_marks_the_packer_refuses(tmp_path: Path) -> None:
    leaked, internal = bookfile.listener_package_problems(HELLO, [], lambda name: b"")
    assert [problem.split(":")[0] for problem in leaked] == [f"chapters[{n}].subtitle" for n in (2, 3, 5, 6, 7, 9)]
    assert {problem.rsplit(".", 1)[1] for problem in internal} == {"qualityPassed", "qualityWarning", "failedLines"}
    with pytest.raises(bookfile.BookFileError, match="dấu nội bộ"):
        bookfile.seal(copy.deepcopy(HELLO), {"chapters/00002_001.mp3": b"audio"}, tmp_path / "x.abook", producer="test", version=1)
    assert not (tmp_path / "x.abook").exists()


def test_the_pipeline_repacks_a_shipped_hello_package_clean_from_the_project(tmp_path: Path) -> None:
    project = _finished_project(tmp_path)
    with sqlite3.connect(project / "project.sqlite3") as connection:  # the project itself still has a chapter in review
        connection.execute("UPDATE chapters SET last_error='Cần nghe lại: c00001_s0001' WHERE id=1")
    pipeline = _Pipeline(project, "completed")
    pipeline._export_book_file()
    target = _output(project)
    _rewrite_manifest(target, _graft_hello)
    with bookfile.BookFile(target) as shipped:
        shipped.verify()  # an intact file: only its listener text and QA fields are wrong
        assert bookfile.listener_package_problems(shipped.book, shipped.content, shipped.read) != ([], [])

    pipeline._export_book_file(only_if_missing=True)

    with bookfile.BookFile(target) as repacked:
        repacked.verify()
        assert bookfile.listener_package_problems(repacked.book, repacked.content, repacked.read) == ([], [])
    stamp = target.stat().st_mtime_ns
    pipeline._export_book_file(only_if_missing=True)
    assert target.stat().st_mtime_ns == stamp, "a clean package is current: no repack on every resume"


def test_repacking_an_imported_hello_copy_refuses_instead_of_stripping(tmp_path: Path) -> None:
    project = _finished_project(tmp_path)
    clean = bookfile.pack(project, tmp_path / "clean.abook")
    with bookfile.BookFile(clean) as opened:
        folder = opened.extract(tmp_path / "library")
    manifest = folder / bookfile.MANIFEST
    book = json.loads(manifest.read_text(encoding="utf-8"))
    _graft_hello(book, ("qualityPassed", "qualityWarning", "failedLines"))  # QA fields only: no visible mark to catch
    manifest.write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(bookfile.BookFileError, match="QA / nội bộ"):
        bookfile.repack(folder, tmp_path / "again.abook")
    assert not (tmp_path / "again.abook").exists()


def test_a_reader_shows_the_same_book_whether_or_not_a_package_carries_qa_fields(tmp_path: Path) -> None:
    """Replaces a grep for field names: the listening view of an imported package ignores every QA field."""
    project = _finished_project(tmp_path)
    clean = bookfile.pack(project, tmp_path / "clean.abook")
    with bookfile.BookFile(clean) as opened:
        folder = opened.extract(tmp_path / "library")
    before = packages.listen(folder, "b", {})

    def qa_only(book: dict) -> None:
        for chapter in [c for v in book.get("volumes") or [] for c in v.get("chapters") or []] or book["chapters"]:
            shipped = HELLO["chapters"][1]
            chapter.update({key: copy.deepcopy(shipped[key]) for key in ("qualityPassed", "qualityWarning", "failedLines")})
        book["levelQa"] = {"verdict": "warning", "chapters": []}

    manifest = folder / bookfile.MANIFEST
    book = json.loads(manifest.read_text(encoding="utf-8"))
    qa_only(book)
    manifest.write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
    after = packages.listen(folder, "b", {})

    for view in (before, after):
        view.pop("updatedAt"), view.pop("addedAt")
    assert after == before
    assert "Cần nghe lại" not in json.dumps(after, ensure_ascii=False)
