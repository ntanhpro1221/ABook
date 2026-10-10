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
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .. import importers
from . import bookfile, covers, packages, store
from .fingerprints import Fingerprints

COVER_VERSION = 1  # bìa của file sách không đổi theo mốc ghi file như bìa của dự án (covers.cover_meta)
SOURCE_FILE = "source.json"  # nằm cạnh book.json trong thư mục cuốn: mã băm file nguồn đã thêm cuốn này (xem `source_digest`)


def _title(raw: Any, fallback: str) -> str:
    return store.clean_title(str(raw or "")) or fallback


def book_json(book: importers.ImportedBook, texts: dict[str, bytes], cover: dict[str, Any] | None) -> dict[str, Any]:
    """`book.json` (chưa có mục `package`) của sách chỉ-chữ. `texts` = {tên mục: byte chữ} theo thứ tự chương."""
    chapters = []
    for number, (name, data) in enumerate(texts.items(), start=1):
        chapter = book.chapters[number - 1]
        title = _title(chapter.name or chapter.title, f"Chương {number}")
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


def texts_of(book: importers.ImportedBook) -> dict[str, bytes]:
    """{tên mục: byte chữ} của các chương, đúng như `build` ghi vào gói."""
    return {f"texts/{number}.txt": book.chapter_source(chapter).encode("utf-8") for number, chapter in enumerate(book.chapters, start=1)}


def find_existing(book: importers.ImportedBook, library_root: Path) -> Path | None:
    """Cuốn trong thư viện có đúng bộ chữ này (sẽ là "existing" khi thêm) - để hỏi người dùng ngay ở bước xem trước, với các chương
    MẶC ĐỊNH (`importers.default_picks`). Cuốn nhận ra theo bộ chữ của các chương đã chọn (`packages.same_book`): chọn khác đi hay
    thêm bản chưa chọn là cuốn khác; đổi tên chương thì không (tên không nằm trong chữ)."""
    picks = importers.default_picks(book)
    if not picks:
        return None
    book = importers.select_chapters(book, picks)
    prints = {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in texts_of(book).items()}
    return packages.find_imported(prints, library_root)


def source_digest(source: Path) -> str:
    """Mã băm của thứ người dùng chọn để thêm sách: nội dung file, hay (thư mục TXT) tên + nội dung từng file theo thứ tự tên. Cùng file thì cùng mã
    bất kể sau đó chọn chương nào, tách chương hay không, đặt tên gì."""
    digest = hashlib.sha256()
    files = sorted(source.iterdir()) if source.is_dir() else [source]
    for path in files:
        if path.is_file():
            digest.update(path.name.encode("utf-8") if source.is_dir() else b"")
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(block)
    return digest.hexdigest()


def remember_source(folder: Path, digest: str) -> None:
    """Ghi lại cuốn này do file nguồn nào thêm vào (bước xem trước lần sau nhận ra cùng một file)."""
    (Path(folder) / SOURCE_FILE).write_bytes(json.dumps({"sha256": digest}).encode("utf-8"))


def find_same_source(digest: str, library_root: Path) -> Path | None:
    """Cuốn trong thư viện được thêm từ CHÍNH file này (xem `remember_source`), chọn chương nào cũng vậy; không có thì None."""
    for folder in packages.folders(library_root):
        try:
            if json.loads((folder / SOURCE_FILE).read_text(encoding="utf-8")).get("sha256") == digest:
                return folder
        except (OSError, ValueError, AttributeError):
            continue
    return None


def build(book: importers.ImportedBook, out: Path, *, producer: str = "ABook") -> Path:
    """Gói một cuốn vừa đọc từ file sách thành file `.abook` chỉ-chữ ở `out` (cùng `bookfile.seal` với mọi file sách)."""
    texts = texts_of(book)
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
    số ký tự. `notes` là gợi ý - hiện ra, không tự áp. Mỗi hàng có `included` (mặc định có vào sách không: mục rất ngắn - bìa, trang
    bản quyền - hiện ra CHƯA tích, kèm `short`; phần không phải truyện - kèm `matter`, lý do như "Trang bản quyền"); người dùng tích / bỏ tích rồi gửi lại danh sách khi thêm (`picks_from_json`).
    `suggestions[].chapter` và `index` đều là số thứ tự trong danh sách này, không phải mã chương trong sách."""
    rows = []
    for number, chapter in enumerate(book.chapters, start=1):
        source = book.chapter_source(chapter)
        rows.append({
            "index": number,
            "title": _title(chapter.name or chapter.title, f"Chương {number}"),
            "firstLine": next((line.strip() for line in source.splitlines() if line.strip()), "")[:200],
            "words": len(source.split()),
            "chars": sum(not ch.isspace() for ch in source),
            "included": not chapter.short and not chapter.matter,
            **({"short": True} if chapter.short else {}),
            **({"matter": chapter.matter} if chapter.matter else {}),
        })
    kept = [row for row in rows if row["included"]]
    return {
        "title": _title(book.title, "Sách"), "author": book.author, "language": book.language,
        "hasCover": bool(book.cover_bytes), "chapters": rows, "notes": list(book.notes),
        # File TXT cả truyện: số chương nếu tách theo các dòng "Chương N" - giao diện đề xuất (ô KHÔNG tích sẵn). Không có gì để tách thì không có khoá.
        # `splitHeadings`: số dòng "Chương N"; nhãn nói thêm phần "Mở đầu" khi chữ trước tiêu đề đầu thành một chương riêng.
        **({"splitOffer": book.split_offer, "splitHeadings": book.split_headings} if book.split_offer else {}),
        # Gợi ý chọn được: dòng ghi công người nghe có thể bỏ khỏi phần đọc (mặc định KHÔNG bỏ). `chapter` = mã chương trong sách.
        "suggestions": [{"chapter": number, "line": line} for number, line in book.credits],
        "totals": {"chapters": len(kept), "words": sum(row["words"] for row in kept)},
    }


def picks_from_json(raw: Any) -> list[tuple[int, str]] | None:
    """`chapters` của lời gọi thêm sách: [{"index": số chương trong bước xem trước, "title": tên mới (tuỳ chọn)}, ...] -> lựa chọn cho
    `importers.select_chapters`. Không có (None) = các chương mặc định. Dạng sai: `ImportFailed`."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise importers.ImportFailed("Danh sách chương đã chọn không hợp lệ")
    picks = []
    for item in raw:
        index, title = (item.get("index"), item.get("title", "")) if isinstance(item, dict) else (None, None)
        if not isinstance(index, int) or isinstance(index, bool) or not isinstance(title, str):
            raise importers.ImportFailed("Danh sách chương đã chọn không hợp lệ")
        picks.append((index, title))
    return picks


def add_to_library(source: Path, title: str | None, library_root: Path, projects: Iterable[Path],
                   fingerprints: Fingerprints, *, separate: bool = False,
                   split_chapters: bool = False, picks: list[tuple[int, str]] | None = None) -> tuple[Path, str, importers.ImportedBook]:
    """Đọc `source` (thư mục TXT / .epub / .docx / .pdf / .txt) và đưa vào thư viện thành sách chỉ-chữ. Trả (thư mục cuốn, cách -
    "new" / "existing" / "updated" như `packages.import_opened`, cuốn đã đọc). `title` (nếu có) thay tên sách của file.
    `separate`: "Thêm bản riêng" - cuốn mới dù thư viện đã có đúng bộ chữ này. `split_chapters`: file .txt cả truyện tách theo "Chương N".
    `picks`: các chương người dùng tích ở bước xem trước (+ tên mới, `picks_from_json`); không có thì các chương mặc định.
    `importers.ImportFailed` / `bookfile.BookFileError` khi không nhập được."""
    book = importers.import_text(source, split_chapters=split_chapters, keep_short=picks is not None)
    if picks is not None:
        book = importers.select_chapters(book, picks)
    if title and store.clean_title(title):
        book.title = title
    with tempfile.TemporaryDirectory(prefix="abook-text-") as scratch:
        packed = build(book, Path(scratch) / bookfile.default_name(book.title))
        folder, how = packages.import_file(packed, library_root, projects, fingerprints, separate=separate)
    if how == "new":
        remember_source(folder, source_digest(source))
    return folder, how, book
