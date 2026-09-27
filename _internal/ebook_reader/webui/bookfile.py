"""Một cuốn sách nói đã làm xong trong MỘT file: đầu ra của máy sản xuất, mở bằng app trên Windows và Android.

Chủ sách, 27-09: *"loại file mà sẽ dành riêng cho app của tôi, chứa mọi thứ về sách sau khi đã xử lý, từ bìa, text với
các tag, âm thanh các thứ... giống như photoshop có file psb"*.

Hình dạng - một gói ZIP:

    mimetype                 MIMETYPE, mục ĐẦU TIÊN, không nén: nhận ra loại file mà không phải mở gói (như EPUB)
    book.json                gói sách của app: đúng `book.json` điện thoại tải qua Wi-Fi (`sync.manifest`), cộng mục
                             `package` (mã sách cố định, phiên bản định dạng, ai làm ra, cỡ + mã băm từng file)
    manifest.json            cùng cuốn sách theo chuẩn mở Readium Audiobook: app sách nói khác (Thorium...) đọc được
                             phần audio, nếu sau này cần đưa sách ra ngoài
    cover.jpg                bìa thật, nếu có
    cast.json                dàn nhân vật
    chapters/<tên>.mp3       audio chương, KHÔNG nén: phát và tua thẳng trong gói, không phải giải nén
    scripts/<chương>.json    từng câu: chữ, loại (kể/thoại/nội tâm/tiêu đề), người nói, cảm xúc, cường độ, nhịp, âm
                             lượng, mốc thời gian trong MP3 - cho đọc theo và chế độ đọc
    samples/<câu>.wav        câu mẫu giọng của từng nhân vật

Đường dẫn giữ y như gói điện thoại đang tải, nên nhập một file chỉ là giải nén vào chỗ sách tải về.

KHÔNG chứa dữ liệu cá nhân: chỗ đang nghe, dấu trang, lịch sử đi theo app và đồng bộ, gắn vào mã sách.

Mở một file là mở dữ liệu của người khác: mọi tên mục phải thuộc đúng danh sách trên (không đường dẫn tuyệt đối, không
`..`), số mục và cỡ có trần, mọi file phải có cỡ và mã băm khớp `book.json`, định dạng mới hơn app thì từ chối kèm lời
nhắc cập nhật. Trong gói không có gì được "chạy".

    python -m ebook_reader.webui.bookfile pack <thư mục sách> [-o file]
    python -m ebook_reader.webui.bookfile inspect <file>
    python -m ebook_reader.webui.bookfile verify <file>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from . import covers, store, sync
from .library import book_id

# Đuôi file (27-09, chờ chủ sách chốt): `.audiobook` là của chuẩn Readium (Thorium mở được), `.ab` là file sao lưu
# `adb backup` của Android, `.vbook` trùng app đọc truyện vBook, `.aubook` trùng app AuBook - không cái nào độc quyền
# được. `.abook` chưa thấy ai dùng. Đổi được tới trước bản phát hành đầu tiên; sau đó file đã nằm trên máy người khác.
EXTENSION = ".abook"
MIMETYPE = "application/vnd.ebookreader.audiobook+zip"
FORMAT = "ebook-reader-book"
FORMAT_VERSION = 1
MANIFEST = "book.json"
READIUM_MANIFEST = "manifest.json"
MAX_ENTRIES = 20_000
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024**3
IDENTITY = re.compile(r"bk-[0-9a-f]{24}")
_CONTENT = re.compile(r"cast\.json|cover\.jpg|chapters/[0-9A-Za-z_.\-]+\.mp3|scripts/\d+\.json|samples/\d+\.wav")
_STORED = (".mp3", ".jpg", ".wav")  # đã nén sẵn hay cần đọc thẳng: nén thêm chỉ tốn công khi phát
_CHUNK = 1024 * 1024


class BookFileError(Exception):
    """File không mở được như một cuốn sách của app. Câu chữ để người dùng đọc."""


class _NoListening:
    """Gói không mang chỗ đang nghe của ai: `listen_view` nhận trạng thái rỗng."""

    def get(self, _book: str) -> dict[str, Any]:
        return {}


def book_identity(project_root: Path) -> str:
    """Mã sách đi theo file sang mọi máy. Mã của webui (`library.book_id`) là đường dẫn thư mục, không mang đi được.

    Băm từ nguồn (mã băm các file TXT) và lúc tạo project: cùng một lần sản xuất thì cùng mã (xuất lại không thành sách
    mới), hai lần sản xuất cùng nguồn là hai cuốn (chương, mốc thời gian khác nhau - chỗ đang nghe không dùng chung được).
    """
    with closing(store.connect(project_root)) as connection:
        row = connection.execute("SELECT * FROM book WHERE id = 1").fetchone()
    if row is None:
        raise BookFileError("Thư mục này không phải một cuốn sách của app.")
    # sqlite3.Row: `in` hỏi GIÁ TRỊ, không hỏi tên cột.
    source = row["input_manifest_hash"] if "input_manifest_hash" in set(row.keys()) else row["title"]
    return "bk-" + hashlib.sha256(f"{source}:{row['created_at']!r}".encode()).hexdigest()[:24]


def default_name(title: str) -> str:
    """Tên file từ tên sách, giữ tiếng Việt, bỏ ký tự Windows cấm."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(title)).strip(" .") or "Sách nói"
    return " ".join(name.split())[:150] + EXTENSION


def pack(project_root: Path, out: Path | None = None, *, producer: str = "Ebook Reader") -> Path:
    """Gói một cuốn thành một file; ghi file tạm cạnh đích rồi thay nguyên tử. Trả đường dẫn file."""
    project_root = Path(project_root)
    identity = book_identity(project_root)
    book = sync.manifest(project_root, book_id(project_root), _NoListening())
    files: dict[str, Path | bytes] = {"cast.json": _json_bytes(store.cast(project_root))}
    cover = covers.cover_file(project_root)
    if cover is not None:
        files[covers.COVER_FILE] = cover
    for chapter in book["chapters"]:
        audio = store.chapter_audio_path(project_root, chapter["id"]) if chapter.get("file") else None
        if audio is not None:
            files[chapter["file"]] = audio
        script = store.chapter_script(project_root, chapter["id"])
        if script is not None:
            files[chapter["script"]] = _json_bytes(script)
    samples = []
    for name in book["samples"]:
        path = store.sample_audio_path(project_root, int(name.split("/")[1].split(".")[0]))
        if path is not None:
            files[name] = path
            samples.append(name)
    book["samples"] = samples
    book["id"] = identity
    book["package"] = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "id": identity,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "producer": producer,
        "files": {name: _describe(source) for name, source in sorted(files.items())},
    }
    unknown = [name for name in files if not _CONTENT.fullmatch(name)]
    if unknown:
        raise BookFileError(f"Không gói được các file có tên ngoài định dạng: {unknown[:3]}")
    out = Path(out) if out is not None else project_root / "output" / default_name(book["title"])
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            archive.writestr(_entry("mimetype", stored=True), MIMETYPE)
            archive.writestr(_entry(MANIFEST), _json_bytes(book))
            archive.writestr(_entry(READIUM_MANIFEST), _json_bytes(_readium(book)))
            for name in sorted(files, key=_order):
                source = files[name]
                stored = name.endswith(_STORED)
                if isinstance(source, Path):
                    archive.write(source, name, compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
                else:
                    archive.writestr(_entry(name, stored=stored), source)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, out)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return out


class BookFile:
    """Một file sách đã mở và đã kiểm hình dạng (chưa kiểm mã băm - `verify()`; `extract()` tự kiểm)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            self._zip = zipfile.ZipFile(self.path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise BookFileError("Đây không phải file sách của app (không mở được gói).") from exc
        try:
            self.book = self._validate()
        except BaseException:
            self._zip.close()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._zip.close()

    @property
    def identity(self) -> str:
        return str(self.book["package"]["id"])

    @property
    def content(self) -> list[str]:
        return sorted(self.book["package"]["files"])

    def read(self, name: str) -> bytes:
        if name not in self.book["package"]["files"] and name not in (MANIFEST, READIUM_MANIFEST):
            raise KeyError(name)
        return self._zip.read(name)

    def verify(self) -> None:
        """Mọi file đúng cỡ và mã băm ghi trong `book.json` - file tải dở hay bị sửa thì không được vào thư viện."""
        for name, expected in self.book["package"]["files"].items():
            digest = hashlib.sha256()
            size = 0
            with self._zip.open(name) as handle:
                while chunk := handle.read(_CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
            if size != expected["size"] or digest.hexdigest() != expected["sha256"]:
                raise BookFileError(f"File sách bị hỏng hoặc bị sửa ({name}). Hãy chép lại file từ nguồn.")

    def extract(self, library: Path) -> Path:
        """Kiểm rồi giải nén vào `library/<mã sách>/`: thư mục tạm rồi đổi tên, không bao giờ để lại nửa cuốn.
        Cuốn cùng mã đã có thì được thay (xuất lại từ cùng lần sản xuất = bản mới của cùng cuốn)."""
        self.verify()
        library = Path(library)
        library.mkdir(parents=True, exist_ok=True)
        target = library / self.identity
        staging = library / f".{self.identity}.{secrets.token_hex(4)}.part"
        try:
            for name in [MANIFEST, READIUM_MANIFEST, *self.content]:
                destination = staging.joinpath(*name.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                with self._zip.open(name) as source, destination.open("wb") as sink:
                    shutil.copyfileobj(source, sink, _CHUNK)
            if target.exists():
                retired = library / f".{self.identity}.{secrets.token_hex(4)}.old"
                os.replace(target, retired)
                os.replace(staging, target)
                shutil.rmtree(retired, ignore_errors=True)
            else:
                os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target

    def _validate(self) -> dict[str, Any]:
        infos = self._zip.infolist()
        if not infos or infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            raise BookFileError("Đây không phải file sách của app.")
        if self._zip.read("mimetype").decode("ascii", "replace").strip() != MIMETYPE:
            raise BookFileError("Đây không phải file sách của app.")
        if len(infos) > MAX_ENTRIES:
            raise BookFileError("File sách có quá nhiều mục.")
        names: set[str] = set()
        total = 0
        for info in infos:
            name = info.filename
            if name in names or info.is_dir():
                raise BookFileError(f"Gói có mục trùng hay thư mục lạ: {name!r}.")
            if name not in ("mimetype", MANIFEST, READIUM_MANIFEST) and not _CONTENT.fullmatch(name):
                raise BookFileError(f"Gói có mục lạ: {name!r}.")
            names.add(name)
            total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise BookFileError("File sách quá lớn.")
        if MANIFEST not in names:
            raise BookFileError("File sách thiếu phần mô tả (book.json).")
        book = self._json(MANIFEST)
        package = book.get("package") if isinstance(book, dict) else None
        if not isinstance(package, dict) or package.get("format") != FORMAT:
            raise BookFileError("Đây không phải file sách của app.")
        version = package.get("version")
        if not isinstance(version, int) or version < 1:
            raise BookFileError("File sách có phiên bản định dạng không hợp lệ.")
        if version > FORMAT_VERSION:
            raise BookFileError("Sách này được làm bằng bản app mới hơn. Hãy cập nhật app để mở.")
        if not isinstance(package.get("id"), str) or not IDENTITY.fullmatch(package["id"]):
            raise BookFileError("File sách có mã sách không hợp lệ.")
        files = package.get("files")
        content = names - {"mimetype", MANIFEST, READIUM_MANIFEST}
        if not isinstance(files, dict) or set(files) != content:
            raise BookFileError("Danh sách file trong sách không khớp nội dung gói.")
        for name, meta in files.items():
            if (not isinstance(meta, dict) or self._zip.getinfo(name).file_size != meta.get("size")
                    or not isinstance(meta.get("sha256"), str)):
                raise BookFileError(f"Mô tả file {name!r} không khớp gói.")
        for chapter in book.get("chapters") or []:
            for key in ("file", "script"):
                reference = chapter.get(key) if isinstance(chapter, dict) else None
                if reference and key == "file" and reference not in content:
                    raise BookFileError("File sách thiếu audio của một chương.")
        return book

    def _json(self, name: str) -> Any:
        if self._zip.getinfo(name).file_size > MAX_JSON_BYTES:
            raise BookFileError(f"{name} quá lớn.")
        try:
            return json.loads(self._zip.read(name).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise BookFileError(f"{name} hỏng.") from exc


def _readium(book: dict[str, Any]) -> dict[str, Any]:
    """Cùng cuốn sách theo Readium Web Publication Manifest, hồ sơ Audiobook
    (https://readium.org/webpub-manifest/profiles/audiobook.html): chỉ phần audio có thật trong gói."""
    order = [
        {"href": chapter["file"], "type": "audio/mpeg", "title": chapter.get("fullTitle") or chapter.get("title") or "",
         **({"duration": chapter["duration"]} if chapter.get("duration") else {})}
        for chapter in book["chapters"] if chapter.get("file")
    ]
    manifest: dict[str, Any] = {
        "@context": "https://readium.org/webpub-manifest/context.jsonld",
        "metadata": {
            "@type": "http://schema.org/Audiobook",
            "conformsTo": "https://readium.org/webpub-manifest/profiles/audiobook",
            "identifier": f"urn:ebook-reader:{book['package']['id']}",
            "title": book["title"],
            "language": "vi",
            "readBy": book.get("narrator") or "",
            "duration": round(sum(float(item.get("duration") or 0) for item in order), 3),
            "modified": book["package"]["createdAt"],
        },
        "readingOrder": order,
        "toc": [{"href": item["href"], "title": item["title"]} for item in order],
    }
    if book.get("cover"):
        manifest["resources"] = [{"href": covers.COVER_FILE, "type": "image/jpeg", "rel": "cover"}]
    return manifest


def _order(name: str) -> tuple[int, str]:
    """Phần nhỏ trước, audio sau cùng: đọc mô tả, bìa, chữ mà không phải lướt qua hàng trăm MB audio."""
    rank = ("cover.jpg", "cast.json", "scripts/", "samples/", "chapters/")
    return next(index for index, prefix in enumerate(rank) if name.startswith(prefix)), name


def _entry(name: str, *, stored: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])  # ZIP ghi giờ địa phương
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    return info


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8")


def _describe(source: Path | bytes) -> dict[str, Any]:
    digest = hashlib.sha256()
    if isinstance(source, Path):
        size = 0
        with source.open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
                size += len(chunk)
        return {"size": size, "sha256": digest.hexdigest()}
    digest.update(source)
    return {"size": len(source), "sha256": digest.hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_command = commands.add_parser("pack", help="gói một cuốn sách thành một file")
    pack_command.add_argument("project", type=Path)
    pack_command.add_argument("-o", "--out", type=Path, default=None)
    for name in ("inspect", "verify"):
        commands.add_parser(name).add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            print(pack(args.project, args.out))
            return 0
        with BookFile(args.file) as book:
            if args.command == "verify":
                book.verify()
            chapters = book.book.get("chapters") or []
            print(f"{book.book['title']} · {book.identity} · {sum(1 for c in chapters if c.get('file'))}/{len(chapters)}"
                  f" chương có audio · {len(book.content)} file{' · mã băm khớp' if args.command == 'verify' else ''}")
        return 0
    except BookFileError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
