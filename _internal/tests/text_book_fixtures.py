"""Bộ ví dụ DÙNG CHUNG cho sách CHỈ-CÓ-CHỮ (abook/webui/textbook.py, docs/LISTEN_ANYTHING.md mục 1): pytest và test JVM của app
Android (TextBookTest.kt) cùng đọc `tests/fixtures/text_books/` - hai bản cài (Python `textbook.build`, Kotlin `TextBook.build`) phải
ra đúng cùng một `book.json` và cùng mã băm từng mục trên cùng một cuốn vừa đọc từ file sách.

    fixtures/text_books/cases.json      mỗi ca: `input` (cuốn đọc từ file sách: tên, tác giả, ngôn ngữ, chương) và `expected`
                                        (book.json không có mục `package`, phiên bản, cỡ + mã băm từng mục, chữ từng mục, tên thư mục
                                        `contentKey`, danh sách chương của bước xem trước `preview`)
    fixtures/text_books/python_text.abook   file do bản Python ghi (Kotlin phải mở được và nhập được)

Chữ lấy từ bộ ví dụ của bộ nhập sách (`fixtures/import/expected/*.json`, toàn chữ tự viết). Bìa không nằm trong ví dụ: chuẩn hoá
ảnh là việc của bộ giải mã ảnh từng máy (Pillow / Bitmap), không phải luật dùng chung.
Sinh lại: runtime/.venv/Scripts/python.exe -m tests.text_book_fixtures (chỉ khi cố ý đổi định dạng).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from abook import importers
from abook.webui import bookfile, textbook
from tests import import_fixtures

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "text_books"
# (tên ca, nguồn trong fixtures/import/expected, tên chương nằm sẵn trong chữ - file TXT)
SOURCES = [("epub3", "epub3", False), ("txt", "txt", True), ("story", "story", False)]


def _book(data: dict[str, Any], text_has_title: bool) -> importers.ImportedBook:
    return importers.ImportedBook(
        title=data["title"], author=data.get("author"), language=data.get("language"), text_has_title=text_has_title,
        chapters=[importers.Chapter(chapter["title"], chapter["text"], short=chapter.get("short", False), name=chapter.get("name", ""))
                  for chapter in data["chapters"]])


def _inputs() -> list[tuple[str, dict[str, Any], bool]]:
    cases: list[tuple[str, dict[str, Any], bool]] = []
    for name, source, has_title in SOURCES:
        data = json.loads((import_fixtures.FIXTURES / "expected" / f"{source}.json").read_text(encoding="utf-8"))
        cases.append((name, {key: data[key] for key in ("title", "author", "language", "chapters")}, has_title))
    # Tên sách lộn xộn (khoảng trắng thừa, ký tự điều khiển) và chương không tên: sách ghi tên sạch, chương thành "Chương N".
    cases.append(("messy", {
        "title": "  Sách   thử\u0007 nghiệm  ", "author": None, "language": None,
        "chapters": [{"title": "Mở đầu", "text": "Đoạn một.\n\nĐoạn hai."}, {"title": "", "text": "Chỉ có một dòng."}],
    }, False))
    # Bước xem trước: mục rất ngắn chưa tích (`short`), chương người dùng đổi tên (`name` - chỉ tên, chữ nguyên).
    cases.append(("preview_choices", {
        "title": "Sách có bìa", "author": None, "language": None,
        "chapters": [{"title": "Bìa", "text": "", "short": True}, {"title": "Chương 1", "text": "Một đoạn.", "name": "  Mở   đầu  mới "},
                     {"title": "Chương 2", "text": "Đoạn hai.", "name": ""}],
    }, False))
    return cases


def build_case(data: dict[str, Any], text_has_title: bool, scratch: Path) -> tuple[Path, dict[str, Any]]:
    """Ghi file `.abook` chỉ-chữ của một ca và trả (đường dẫn, phần `expected`)."""
    imported = _book(data, text_has_title)
    path = textbook.build(imported, scratch / "x.abook")
    with bookfile.BookFile(path) as opened:
        book = json.loads(opened.read("book.json"))
        package = book.pop("package")
        texts = {name: opened.read(name).decode("utf-8") for name in opened.content}
        key = opened.content_key
    return path, {"book": book, "version": package["version"], "files": package["files"], "texts": texts, "contentKey": key,
                  "preview": textbook.preview(imported)}


def cases() -> dict[str, Any]:
    out = []
    with tempfile.TemporaryDirectory(prefix="abook-textbooks-") as scratch:
        for name, data, has_title in _inputs():
            _path, expected = build_case(data, has_title, Path(scratch))
            out.append({"name": name, "input": {**data, "textHasTitle": has_title}, "expected": expected})
    return {"cases": out}


def cases_bytes() -> bytes:
    return (json.dumps(cases(), ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "cases.json").write_bytes(cases_bytes())
    name, data, has_title = _inputs()[0]
    with tempfile.TemporaryDirectory(prefix="abook-textbooks-") as scratch:
        path, _ = build_case(data, has_title, Path(scratch))
        (FIXTURES / "python_text.abook").write_bytes(path.read_bytes())
    print("wrote", FIXTURES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
