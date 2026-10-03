"""Sách CHỈ CÓ CHỮ (giai đoạn 0 của sách nhiều lớp, docs/LISTEN_ANYTHING.md mục 1): một cuốn nhập từ EPUB / DOCX / PDF / thư mục
TXT (`importers.import_text`) vào thư viện của người nghe, chưa có audio nào.

Sách chỉ-chữ là một file `.abook` bình thường, phiên bản 5: `book.json` với `chapters[i].state` = "text" và `chapters[i].text` =
`texts/<n>.txt` (không `file`, không thời lượng), `texts/<n>.txt` (chữ như FILE NGUỒN mà Studio đọc - `ImportedBook.chapter_source`,
nên "Làm sách nói từ cuốn này" chép nguyên văn ra thư mục nguồn), `cover.jpg` nếu file sách có bìa. Nên cùng một đường nhập với
file `.abook` (`packages.import_file`: kiểm cỡ + mã băm, không nhân đôi khi nhập lại), cùng lớp sửa (tên sách, bìa, tên chương),
cùng "Lưu thành .abook". Bản Kotlin: TextBook.kt - cùng `book.json` trên bộ ví dụ dùng chung `tests/fixtures/text_books/`.

Chữ KHÔNG bao giờ bị sửa (chủ sách): `importers.import_text` chỉ đổi định dạng; dòng ghi công chỉ là gợi ý (`notes`) hiện ở bước xem
trước, không có gì tự bỏ.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .. import importers
from . import bookfile, covers, packages, store
from .fingerprints import Fingerprints

COVER_VERSION = 1  # bìa của file sách không đổi theo mốc ghi file như bìa của dự án (covers.cover_meta)


def _title(raw: Any, fallback: str) -> str:
    return store.clean_title(str(raw or "")) or fallback


def book_json(book: importers.ImportedBook, texts: dict[str, bytes], cover: dict[str, Any] | None) -> dict[str, Any]:
    """`book.json` (chưa có mục `package`) của sách chỉ-chữ. `texts` = {tên mục: byte chữ} theo thứ tự chương."""
    chapters = []
    for number, (name, data) in enumerate(texts.items(), start=1):
        title = _title(book.chapters[number - 1].title, f"Chương {number}")
        chapters.append({
            "id": number, "index": number, "title": title, "subtitle": "", "fullTitle": title,
            "duration": 0, "available": False, "size": 0, "state": bookfile.TEXT_STATE, "text": name,
        })
    result: dict[str, Any] = {"format": packages.FORMAT, "title": _title(book.title, "Sách")}
    if book.author:
        result["author"] = book.author
    if book.language:
        result["language"] = book.language
    digest = hashlib.sha256("".join(hashlib.sha256(data).hexdigest() for data in texts.values()).encode()).hexdigest()
    result.update({
        "narrator": "", "duration": 0, "chaptersTotal": len(chapters), "chaptersAvailable": 0, "complete": False,
        "version": digest[:16], "chapters": chapters, "samples": [],
        "cover": {**cover, "version": COVER_VERSION, "file": covers.COVER_FILE} if cover else None,
    })
    return result


def build(book: importers.ImportedBook, out: Path, *, producer: str = "ABook") -> Path:
    """Gói một cuốn vừa đọc từ file sách thành file `.abook` chỉ-chữ ở `out` (cùng `bookfile.seal` với mọi file sách)."""
    texts = {f"texts/{number}.txt": book.chapter_source(chapter).encode("utf-8")
             for number, chapter in enumerate(book.chapters, start=1)}
    files: dict[str, Path | bytes] = dict(texts)
    cover = None
    if book.cover_bytes:
        try:
            jpeg, cover = covers.render_cover(book.cover_bytes)
            files[covers.COVER_FILE] = jpeg
        except covers.CoverError:
            cover = None  # bìa hỏng hay quá nhỏ: sách vẫn nhập được, giao diện tự vẽ bìa từ tên
    manifest = book_json(book, texts, cover)
    return bookfile.seal(manifest, files, Path(out), producer=producer, version=bookfile.package_version(manifest))


def preview(book: importers.ImportedBook) -> dict[str, Any]:
    """Danh sách chương cho bước xem trước (cùng hàng chữ với danh sách chương của trình tạo sách Studio): tên, dòng đầu, số chữ,
    số ký tự. `notes` là gợi ý - hiện ra, không tự áp."""
    rows = []
    for number, chapter in enumerate(book.chapters, start=1):
        source = book.chapter_source(chapter)
        rows.append({
            "index": number,
            "title": _title(chapter.title, f"Chương {number}"),
            "firstLine": next((line.strip() for line in source.splitlines() if line.strip()), "")[:200],
            "words": len(source.split()),
            "chars": sum(not ch.isspace() for ch in source),
        })
    return {
        "title": _title(book.title, "Sách"), "author": book.author, "language": book.language,
        "hasCover": bool(book.cover_bytes), "chapters": rows, "notes": list(book.notes),
        "totals": {"chapters": len(rows), "words": sum(row["words"] for row in rows)},
    }


def add_to_library(source: Path, title: str | None, library_root: Path, projects: Iterable[Path],
                   fingerprints: Fingerprints) -> tuple[Path, str, importers.ImportedBook]:
    """Đọc `source` (thư mục TXT / .epub / .docx / .pdf / .txt) và đưa vào thư viện thành sách chỉ-chữ. Trả (thư mục cuốn, cách -
    "new" / "existing" / "updated" như `packages.import_opened`, cuốn đã đọc). `title` (nếu có) thay tên sách của file.
    `importers.ImportFailed` / `bookfile.BookFileError` khi không nhập được."""
    book = importers.import_text(source)
    if title and store.clean_title(title):
        book.title = title
    with tempfile.TemporaryDirectory(prefix="abook-text-") as scratch:
        packed = build(book, Path(scratch) / bookfile.default_name(book.title))
        folder, how = packages.import_file(packed, library_root, projects, fingerprints)
    return folder, how, book
