"""Một cuốn sách nói đã làm xong trong MỘT file: đầu ra của máy sản xuất, mở bằng app trên Windows và Android.

Chủ sách, 27-09: *"loại file mà sẽ dành riêng cho app của tôi, chứa mọi thứ về sách sau khi đã xử lý, từ bìa, text với
các tag, âm thanh các thứ... giống như photoshop có file psb"*.

Hình dạng - một gói ZIP:

    mimetype                 MIMETYPE, mục ĐẦU TIÊN, không nén: nhận ra loại file mà không phải mở gói (như EPUB)
    book.json                gói sách của app: đúng `book.json` điện thoại tải qua Wi-Fi (`sync.manifest`), cộng mục
                             `package` (phiên bản định dạng, ai làm ra, cỡ + mã băm từng file)
    manifest.json            cùng cuốn sách theo chuẩn mở Readium Audiobook: app sách nói khác (Thorium...) đọc được
                             phần audio, nếu sau này cần đưa sách ra ngoài
    cover.jpg                bìa thật, nếu có
    cast.json                dàn nhân vật
    chapters/<tên>.mp3       audio chương, KHÔNG nén: phát và tua thẳng trong gói, không phải giải nén
    scripts/<chương>.json    từng câu: chữ, loại (kể/thoại/nội tâm/tiêu đề), người nói, cảm xúc, cường độ, nhịp, âm
                             lượng, mốc thời gian trong MP3 - cho đọc theo và chế độ đọc
    samples/<câu>.wav        câu mẫu giọng của từng nhân vật
    texts/<chương>.txt       phiên bản 5 (03-10): chữ của chương - sách CHỈ CÓ CHỮ (nhập từ EPUB / DOCX / PDF / TXT, chưa có audio) hay chương
                             chưa có audio; `chapters[i].state` = "text", `chapters[i].text` = tên mục (docs/LISTEN_ANYTHING.md mục 1)
    music/<sha1>.<đuôi>      nhạc nền người sản xuất đã gắn (02-10; mốc từng chương ở mục `music` của book.json,
                             music_plan.package) - chỉ khi cuốn có rãnh nhạc; KHÔNG nén như audio chương
    edits.json               phiên bản 4 (03-10): LỚP SỬA của người nghe - tên sách, bìa, tên nhân vật, tên chương, nhạc nền
    edits/cover.jpg          (book_edits.py, docs/EDITING.md); chỉ có khi người nghe đã sửa gì. Lớp sách ở trên không bao giờ
                             bị sửa tại chỗ - bìa mới nằm ở edits/cover.jpg chứ không đè cover.jpg (mã băm của nó giữ nguyên)

Phiên bản 4 chỉ ghi khi file mang lớp sửa (`repack`); `.abook` không bao giờ chứa `project/`, `sources/`, `views/` (của
`.abookproj`). Phiên bản 3 (02-10, `pack_series`): CẢ BỘ nhiều phần trong một file. Audio nằm ở `chapters/<phần>/<tên>.mp3` (hai phần
có thể trùng tên file), mã chương = phần x 100000 + mã chương trong phần (nên `scripts/<mã>.json` và mốc nhạc dùng mã
chung của cả bộ), một `cast.json` gộp theo tên nhân vật, câu mẫu đánh số lại 1..K, một bìa (của phần đầu), mục `parts`
trong book.json. Chi tiết: docs/ABOOK_FILE_FORMAT.md.

Đường dẫn giữ y như gói điện thoại đang tải, nên nhập một file chỉ là giải nén vào chỗ sách tải về.

KHÔNG chứa dữ liệu nghe (chỗ đang nghe, dấu trang, lịch sử) và KHÔNG mang mã sách nào (chủ sách 27-09: sách và dữ
liệu nghe độc lập, không biết đến mã; app giữ liên kết giữa chúng) - kể cả mục `series` của gói điện thoại, vì nó mang mã
của máy làm ra file. Muốn biết hai file có phải cùng một lần sản xuất, app so mã băm audio từng chương
(`fingerprints.py`) - chính mã băm dùng để kiểm file hỏng, không phải thêm gì.

Mở một file là mở dữ liệu của người khác: mọi tên mục phải thuộc đúng danh sách trên (không đường dẫn tuyệt đối, không
`..`), số mục và cỡ có trần, mọi file phải có cỡ và mã băm khớp `book.json`, định dạng mới hơn app thì từ chối kèm lời
nhắc cập nhật. Trong gói không có gì được "chạy".

    python -m abook.webui.bookfile pack <thư mục sách> [-o file]
    python -m abook.webui.bookfile repack <thư mục sách đã nhập> -o file
    python -m abook.webui.bookfile inspect <file>
    python -m abook.webui.bookfile verify <file>
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Self, Sequence

from .. import continuation
from . import book_edits, covers, music_plan, store, sync, word_timing
from .fingerprints import content_key, identity_prints
from .library import book_id

# Đuôi file - chủ sách chốt `.abook` 27-09. `.audiobook` là của chuẩn Readium (Thorium mở được), `.ab` là file sao lưu
# `adb backup` của Android, `.vbook` trùng app đọc truyện vBook, `.aubook` trùng app AuBook - không cái nào độc quyền
# được; `.abook` chưa thấy ai dùng. Sau bản phát hành đầu tiên thì không đổi được nữa: file đã nằm trên máy người khác.
EXTENSION = ".abook"
MIMETYPE = "application/vnd.ngdtuanh.abook+zip"
FORMAT = "abook"
# 1 = sách không nhạc nền; 2 = có mục `music` + music/*.mp3 (02-10); 3 = cả bộ nhiều phần (`pack_series`); 4 = có lớp sửa của
# người nghe (edits.json + edits/cover.jpg, `repack`); 5 = có chương chỉ-chữ (texts/<n>.txt, không audio). Gói ghi phiên bản THẤP
# NHẤT đủ chứa nội dung: sách một phần không nhạc vẫn là 1, có nhạc là 2 - app cũ mở được; app cũ gặp file mới hơn thì từ chối kèm
# lời nhắc cập nhật thay vì báo "mục lạ".
FORMAT_VERSION = 5
MANIFEST = "book.json"
READIUM_MANIFEST = "manifest.json"
TEXT_STATE = sync.TEXT_STATE  # `chapters[i].state` của chương chỉ có chữ (các giai đoạn khác: docs/LISTEN_ANYTHING.md mục 1)
MAX_ENTRIES = 20_000
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024**3
PART_SPAN = 100_000  # mã chương trong bộ = số phần x PART_SPAN + mã chương trong phần
_COMMON = r"cast\.json|cover\.jpg|scripts/\d+\.json|samples/\d+\.wav|" + music_plan.TRACK_FILE.pattern
_CONTENT = re.compile(_COMMON + r"|chapters/[0-9A-Za-z_.\-]+\.mp3")
# Phiên bản 3 thêm thư mục phần: chapters/<phần>/<tên>.mp3 (phiên bản 1-2 không có - gặp thì là mục lạ).
_CONTENT_V3 = re.compile(_COMMON + r"|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3")
# Phiên bản 4 thêm lớp sửa của người nghe (book_edits.py).
_CONTENT_V4 = re.compile(_COMMON + r"|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3|edits\.json|edits/cover\.jpg")
# Phần nghe của một file dự án `.abookproj` (projectfile.py) có đúng các tên mục của một file sách mới nhất (kể cả lớp sửa);
# chép hai lần cùng một audio thì không - mục nào trùng byte với mục khác của gói chỉ là bí danh (projectfile.py).
# Phiên bản 5 thêm chữ của chương: texts/<mã chương>.txt (mã chương cả bộ có thể tới 9 chữ số).
TEXT_ENTRY = re.compile(r"texts/\d{1,9}\.txt")
_CONTENT_V5 = re.compile(_CONTENT_V4.pattern + "|" + TEXT_ENTRY.pattern)
LISTENING_ENTRY = _CONTENT_V5
# Chỗ trống dư ngoài cỡ giải nén (thư mục tạm, book.json): không cần sát từng byte, chỉ cần không để ổ đĩa đầy giữa chừng.
_ROOM_MARGIN = 64 * 1024 * 1024
_STORED = (".mp3", ".jpg", ".wav", ".m4a", ".ogg", ".opus", ".flac")  # đã nén sẵn hay cần đọc thẳng: nén thêm chỉ tốn công khi phát
_CHUNK = 1024 * 1024


class BookFileError(Exception):
    """File không mở được như một cuốn sách của app. Câu chữ để người dùng đọc."""


class _NoListening:
    """Gói không mang chỗ đang nghe của ai: `listen_view` nhận trạng thái rỗng."""

    def get(self, _book: str) -> dict[str, Any]:
        return {}


def default_name(title: str) -> str:
    """Tên file từ tên sách, giữ tiếng Việt, bỏ ký tự Windows cấm."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(title)).strip(" .") or "Sách nói"
    return " ".join(name.split())[:150] + EXTENSION


def _packaged_book(project_root: Path) -> dict[str, Any]:
    """`book.json` của một dự án như điện thoại tải (`sync.manifest`), bỏ những gì là của máy này: mã (đường dẫn thư
    mục), mục `series` (nó mang mã của phần đầu) và `wordsVersion` (dấu bộ nhớ đệm mốc chữ của máy này).

    Mốc từng chữ (`words` trong từng câu, word_timing.py) được căn ở đây - lúc đóng gói, ngoài dây chuyền khoá, TRƯỚC khi hỏi manifest để
    `version` của gói đã tính cả chúng - và nhớ theo dự án, nên đóng gói lại không căn lại; `store.chapter_script` đọc chúng. Không căn được
    (máy chưa có Studio...) thì sách vẫn đóng gói, chỉ không có `words`."""
    word_timing.prepare(project_root)
    book = sync.manifest(project_root, book_id(project_root), _NoListening())
    for key in ("id", "series", "wordsVersion"):
        book.pop(key, None)
    return book


def _add_chapters(project_root: Path, book: dict[str, Any], files: dict[str, Path | bytes], *,
                  part: int | None = None) -> None:
    """Audio + chữ đọc theo của từng chương vào `files`. `part` (cả bộ): chương `book["chapters"]` được sửa tại chỗ sang
    mã chung của bộ, đường dẫn nằm trong thư mục phần, và mang số phần."""
    for chapter in book["chapters"]:
        local = chapter["id"]
        audio = store.chapter_audio_path(project_root, local) if chapter.get("file") else None
        script = store.chapter_script(project_root, local)
        if part is not None:
            if not 0 < local < PART_SPAN:
                raise BookFileError(f"Mã chương {local} vượt cỡ một phần của bộ.")
            chapter["id"] = part * PART_SPAN + local
            chapter["part"] = part
            if chapter.get("file"):
                chapter["file"] = f"chapters/{part}/{chapter['file'].split('/', 1)[1]}"
            chapter["script"] = f"scripts/{chapter['id']}.json"
            if script is not None:
                script = {**script, "chapterId": chapter["id"]}
        if audio is not None:
            files[chapter["file"]] = audio
        if script is not None:
            files[chapter["script"]] = json_bytes(script)


def _add_texts(project_root: Path, book: dict[str, Any], files: dict[str, Path | bytes]) -> None:
    """Cuốn chưa có chương nào xong audio: chương nào còn đọc được chữ nguồn thì thành chương CHỈ-CHỮ (`sync.text_layer`) - sách vẫn
    đóng gói, mở, đọc được. Chương không còn file nguồn thì để nguyên (không chữ, không audio)."""
    files.update(sync.text_layer(project_root, book["chapters"]))
    for chapter in book["chapters"]:
        # Chương chỉ-chữ không mang khoá `script` (JSON null thì `optString` của Android đọc ra chữ "null") trừ khi chữ đọc theo đã vào gói.
        if chapter.get("text") and chapter.get("script") not in files:
            chapter.pop("script", None)


def listening_layer(project_root: Path, music_track: Callable[[str], Path | None] | None = None
                    ) -> tuple[dict[str, Any], dict[str, Path | bytes]]:
    """Phần NGHE của một cuốn: `book.json` (chưa có mục `package`) + các file đi cùng (`cast.json`, bìa, `chapters/`,
    `scripts/`, `samples/`, nhạc nền) - dùng chung cho file `.abook` (`pack`) và phần nghe nằm trong file dự án
    (projectfile.pack; audio chương và câu mẫu là file của dự án, nên trong gói chúng là bí danh chứ không chép hai lần).
    `music_track(link)` -> file của một bài nhạc nền (bộ đệm của máy, tải khi cần); có thì kèm rãnh nhạc."""
    book = _packaged_book(project_root)
    files: dict[str, Path | bytes] = {"cast.json": json_bytes(store.cast(project_root))}
    cover = covers.cover_file(project_root)
    if cover is not None:
        files[covers.COVER_FILE] = cover
    _add_chapters(project_root, book, files)
    if not any(chapter.get("file") for chapter in book["chapters"]):
        _add_texts(project_root, book, files)
    samples = []
    for name in book["samples"]:
        path = store.sample_audio_path(project_root, int(name.split("/")[1].split(".")[0]))
        if path is not None:
            files[name] = path
            samples.append(name)
    book["samples"] = samples
    music = None
    if music_track is not None:
        music = music_plan.package(project_root, [c["id"] for c in book["chapters"] if c.get("file")], music_track)
    if music is not None:
        book["music"], tracks = music
        files.update(tracks)
    return book, files


def pack(project_root: Path, out: Path | None = None, *, producer: str = "ABook",
         music_track: Callable[[str], Path | None] | None = None) -> Path:
    """Gói một cuốn thành một file; ghi file tạm cạnh đích rồi thay nguyên tử. Trả đường dẫn file.

    `music_track(link)` -> file của một bài nhạc nền (bộ đệm của máy, tải khi cần); có thì gói kèm rãnh nhạc."""
    project_root = Path(project_root)
    book, files = listening_layer(project_root, music_track)
    out = Path(out) if out is not None else project_root / "output" / default_name(book["title"])
    return seal(book, files, out, producer=producer, version=package_version(book))


def book_layer(folder: Path) -> tuple[dict[str, Any], dict[str, Path | bytes], dict[str, dict[str, Any]], dict[str, Any]]:
    """Lớp sách của một cuốn ĐÃ NHẬP (thư mục trong thư viện, giải nén từ file `.abook` hay phần nghe của `.abookproj`) cộng lớp
    sửa của người nghe: (`book.json` bỏ mục `package`, {tên mục: file hay byte}, {tên mục: cỡ + mã băm đã biết}, lớp sửa). Dùng
    chung cho `repack` (file `.abook`) và `projectfile.repack` (file `.abookproj`) - hai nơi chỉ khác phần còn lại của gói."""
    folder = Path(folder)
    try:
        book = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BookFileError("Không đọc được thư mục sách này.") from exc
    package = book.get("package") if isinstance(book, dict) else None
    if not isinstance(package, dict) or not isinstance(package.get("files"), dict):
        raise BookFileError("Đây không phải một cuốn đã nhập từ file sách.")
    files: dict[str, Path | bytes] = {}
    known: dict[str, dict[str, Any]] = {}
    for name, meta in package["files"].items():
        if name in (book_edits.EDITS_FILE, book_edits.EDITS_COVER):
            continue  # lớp sửa suy lại từ phần sửa hiện có, không từ danh sách cũ
        source = folder.joinpath(*name.split("/"))
        if not source.is_file():
            raise BookFileError(f"Thư mục sách thiếu file {name}.")
        files[name], known[name] = source, meta
    book.pop("package", None)
    edits = book_edits.load(folder)
    try:
        layer = book_edits.layer_files(folder, edits)
    except book_edits.EditsError as exc:
        raise BookFileError(str(exc)) from exc
    for name, item in layer.items():  # bài nhạc của người nghe đã ghim đi theo file như bài của người làm sách (đã có thì giữ)
        files.setdefault(name, item)
    return book, files, known, edits


def repack(folder: Path, out: Path, *, producer: str = "ABook") -> Path:
    """Đóng lại một cuốn ĐÃ NHẬP (thư mục trong thư viện, giải nén từ file `.abook`) thành một file: lớp sách y nguyên (file,
    mã băm đã biết không băm lại), cộng lớp sửa của người nghe nếu có - khi ấy phiên bản 4 (`edits.json`, `edits/cover.jpg`).
    Không có lớp sửa thì ra file như người làm sách đã đóng, ở phiên bản thấp nhất đủ chứa nó. Thư mục dự án (Studio) thì
    dùng `pack`, không phải hàm này. Cuốn nhập từ `.abookproj` cũng ra `.abook` (phần xưởng - `project/`, `sources/`,
    `views/` - không nằm trong `package.files` nên không đi theo)."""
    book, files, known, edits = book_layer(folder)
    return seal(book, files, Path(out), producer=producer, version=layer_version(book, files, edits), known=known, edits=edits)


def layer_version(book: dict[str, Any], files: dict[str, Path | bytes], edits: dict[str, Any]) -> int:
    """Phiên bản THẤP NHẤT đủ chứa một lớp sách đã nhập: có chữ chương là 5, có lớp sửa là 4, có thư mục phần là 3, còn lại theo
    `package_version`."""
    if any(TEXT_ENTRY.fullmatch(name) for name in files):
        return 5
    if not book_edits.is_empty(edits):
        return 4
    if any(re.fullmatch(r"chapters/\d+/.+", name) for name in files):
        return 3
    return package_version(book)


def package_version(book: dict[str, Any]) -> int:
    """Phiên bản THẤP NHẤT đủ chứa sách một phần: có chương chỉ-chữ là 5, có nhạc nền là 2, không thì 1 (cả bộ: 3, `pack_series`)."""
    if any(isinstance(chapter, dict) and chapter.get("text") for chapter in book.get("chapters") or []):
        return 5
    return 2 if "music" in book else 1


def pack_series(parts: Sequence[tuple[int, Path] | Path], out: Path, *, producer: str = "ABook",
                music_track: Callable[[str], Path | None] | None = None) -> Path:
    """Cả bộ nhiều phần ("Làm tiếp cuốn này") trong MỘT file, phiên bản 3. `parts`: (số phần, thư mục dự án) theo thứ tự
    - hay chỉ thư mục, số phần là vị trí từ 1. Số phần là số của bộ nên phần bị bỏ qua không làm các phần sau đổi mã.
    Phần chưa có chương nào nghe được không vào file (người gọi nói tên chúng với người dùng: export.series_split)."""
    books: list[tuple[int, Path, dict[str, Any]]] = []
    musics: list[tuple[int, dict[str, Any]]] = []
    files: dict[str, Path | bytes] = {}
    for number, root in _numbered(parts):
        book = _packaged_book(root)
        playable = [chapter["id"] for chapter in book["chapters"] if chapter.get("file")]
        if not playable:
            continue
        packed = music_plan.package(root, playable, music_track) if music_track is not None else None
        _add_chapters(root, book, files, part=number)
        books.append((number, root, book))
        if packed is not None:
            musics.append((number, packed[0]))
            files.update(packed[1])
    if not books:
        raise BookFileError("Sách chưa có chương nào nghe được để xuất.")
    first_root, first = books[0][1], books[0][2]
    cover = covers.cover_file(first_root)
    if cover is not None:
        files[covers.COVER_FILE] = cover
    cast, samples = _merge_cast([(number, root) for number, root, _ in books], files)
    files["cast.json"] = json_bytes(cast)
    merged: dict[str, Any] = {
        "format": first["format"],
        "title": continuation.base_title(first["title"]),
        "narrator": first["narrator"],
        "duration": round(sum(float(book["duration"]) for _, _, book in books), 1),
        "chaptersTotal": sum(int(book["chaptersTotal"]) for _, _, book in books),
        "chaptersAvailable": sum(int(book["chaptersAvailable"]) for _, _, book in books),
        "complete": all(book["complete"] for _, _, book in books),
        "version": hashlib.sha256("".join(str(book["version"]) for _, _, book in books).encode()).hexdigest()[:16],
        "chapters": [chapter for _, _, book in books for chapter in book["chapters"]],
        "cast": "cast.json",
        "samples": samples,
        "cover": first.get("cover") if cover is not None else None,
        "parts": [{"part": number, "title": continuation.continued_title(book["title"], number),
                   "chapters": [book["chapters"][0]["id"], book["chapters"][-1]["id"]],
                   "duration": round(float(book["duration"]), 1), "narrator": book["narrator"]}
                  for number, _, book in books],
    }
    music = _merge_music(musics)
    if music is not None:
        merged["music"] = music
    return seal(merged, files, Path(out), producer=producer, version=3)


def _numbered(parts: Sequence[tuple[int, Path] | Path]) -> list[tuple[int, Path]]:
    numbered = [(item if isinstance(item, tuple) else (index, item)) for index, item in enumerate(parts, start=1)]
    numbers = [number for number, _ in numbered]
    if any(not 0 < number < 10_000 for number in numbers) or len(set(numbers)) != len(numbers):
        raise ValueError("Số phần của bộ phải khác nhau và nằm trong 1..9999")
    return [(number, Path(root)) for number, root in numbered]


def _merge_cast(parts: list[tuple[int, Path]], files: dict[str, Path | bytes]) -> tuple[dict[str, Any], list[str]]:
    """Dàn nhân vật của cả bộ: gộp theo tên chuẩn (`name`), cộng số câu, `parts` = phần nào người ấy lên tiếng. Câu mẫu
    đánh số lại 1..K theo thứ tự gặp (mã câu của hai dự án có thể trùng nhau) và `sampleId` trỏ theo số mới; file mẫu vào
    `files`. Người là nhân vật chính ở phần này, vai phụ ở phần kia: tính là nhân vật chính."""
    people: dict[str, dict[str, Any]] = {}
    section: dict[str, str] = {}
    carried: dict[str, dict[str, Any]] = {}
    narrator: dict[str, Any] | None = None
    samples: list[str] = []
    for number, root in parts:
        cast = store.cast(root)
        narrator = narrator or cast["narrator"]
        for kind in ("characters", "extras"):
            for person in cast[kind]:
                name = person["name"]
                entry = people.get(name)
                if entry is None:
                    entry = people[name] = {**person, "lines": 0, "seconds": 0.0, "recorded": 0, "parts": [],
                                            "sampleId": None}
                    section[name] = kind
                elif kind == "characters":
                    section[name] = kind
                entry["lines"] += person["lines"]
                entry["seconds"] = round(entry["seconds"] + person["seconds"], 1)
                entry["recorded"] += person["recorded"]
                entry["parts"].append(number)
                entry["voice"] = entry.get("voice") or person.get("voice")
                if entry["sampleId"] is None and person.get("sampleId"):
                    path = store.sample_audio_path(root, int(person["sampleId"]))
                    if path is not None:
                        samples.append(f"samples/{len(samples) + 1}.wav")
                        files[samples[-1]] = path
                        entry["sampleId"] = len(samples)
        for person in cast.get("carried") or []:
            carried.setdefault(person["name"], {**person, "parts": []})

    def ordered(kind: str) -> list[dict[str, Any]]:
        return sorted((entry for name, entry in people.items() if section[name] == kind),
                      key=lambda entry: (-entry["lines"], entry["displayName"]))

    return ({"narrator": narrator or {}, "characters": ordered("characters"), "extras": ordered("extras"),
             "carried": sorted((entry for name, entry in carried.items() if name not in people),
                               key=lambda entry: entry["displayName"])}, samples)


def _merge_music(parts: list[tuple[int, dict[str, Any]]]) -> dict[str, Any] | None:
    """Mục `music` của cả bộ: bài trùng giữa các phần chỉ một mục (tên file là sha1 của link), mốc theo mã chương chung."""
    if not parts:
        return None
    tracks: dict[str, Any] = {}
    chapters: dict[str, Any] = {}
    for number, music in parts:
        for name, info in music["tracks"].items():
            tracks.setdefault(name, info)
        for local, cues in music["chapters"].items():
            chapters[str(number * PART_SPAN + int(local))] = cues
    return {"levelDb": parts[0][1]["levelDb"], "tracks": tracks, "chapters": chapters}


def seal(book: dict[str, Any], files: dict[str, Path | bytes], out: Path, *, producer: str, version: int,
         known: dict[str, dict[str, Any]] | None = None, edits: dict[str, Any] | None = None) -> Path:
    """Ghi `book.package` (cỡ + mã băm từng file) rồi gói ZIP: file tạm cạnh đích, thay nguyên tử. Sách phải có gì để nghe hay
    để đọc: audio chương, hay (phiên bản 5) chữ chương - sách chỉ-chữ không có audio nào vẫn là sách.
    `known`: cỡ + mã băm đã biết của một số file (sách đã nhập, đã kiểm lúc giải nén) - file đúng cỡ ấy khỏi băm lại.
    `edits`: lớp sửa của người nghe - `manifest.json` (Readium, cho app khác) mang tên sách / tên chương đã sửa."""
    if not any(name.startswith(("chapters/", "texts/")) for name in files):
        raise BookFileError("Sách chưa có chương nào nghe được hay đọc được để xuất.")
    known = known or {}
    book["package"] = {
        "format": FORMAT,
        "version": version,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "producer": producer,
        "files": {name: described(name, source, known) for name, source in sorted(files.items())},
    }
    allowed = content_pattern(version)
    unknown = [name for name in files if not allowed.fullmatch(name)]
    if unknown:
        raise BookFileError(f"Không gói được các file có tên ngoài định dạng: {unknown[:3]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
            archive.writestr(_entry("mimetype", stored=True), MIMETYPE)
            archive.writestr(_entry(MANIFEST), json_bytes(book))
            archive.writestr(_entry(READIUM_MANIFEST), json_bytes(_readium(book_edits.apply_manifest(book, edits or {}))))
            write_entries(archive, files, order=_order)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, out)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return out


def content_pattern(version: int) -> re.Pattern[str]:
    """Tên mục hợp lệ của một file `.abook` phiên bản `version` (thư mục phần từ 3, lớp sửa từ 4, chữ chương từ 5)."""
    return _CONTENT_V5 if version >= 5 else _CONTENT_V4 if version >= 4 else _CONTENT_V3 if version >= 3 else _CONTENT


def described(name: str, source: Path | bytes, known: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Cỡ + mã băm của một mục: lấy từ `known` nếu file còn đúng cỡ ấy (đã kiểm lúc giải nén), không thì băm."""
    meta = known.get(name)
    if isinstance(source, Path) and isinstance(meta, dict) and meta.get("size") == source.stat().st_size and isinstance(meta.get("sha256"), str):
        return {"size": meta["size"], "sha256": meta["sha256"]}
    return describe(source)


def write_entries(archive: zipfile.ZipFile, files: dict[str, Path | bytes], *, order: Callable[[str], Any],
                  stored_suffixes: tuple[str, ...] = _STORED) -> None:
    """Ghi từng mục vào gói theo `order`: audio và ảnh KHÔNG nén (phát thẳng trong gói), còn lại nén."""
    for name in sorted(files, key=order):
        source = files[name]
        stored = name.lower().endswith(stored_suffixes)
        if isinstance(source, Path):
            archive.write(source, name, compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
        else:
            archive.writestr(_entry(name, stored=stored), source)


class BookFile:
    """Một file sách đã mở và đã kiểm hình dạng (chưa kiểm mã băm - `verify()`; `extract()` tự kiểm)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.last_merge: dict[str, Any] | None = None
        self._edits: dict[str, Any] = book_edits.empty()
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
    def chapter_prints(self) -> dict[str, dict[str, Any]]:
        """Cỡ + mã băm audio từng chương - app so với sách đã có để nhận ra cùng một lần sản xuất (fingerprints.py). Cuốn chưa có
        audio nào thì mã băm chữ từng chương."""
        return identity_prints(self.book["package"]["files"])

    @property
    def content_key(self) -> str:
        """Tên thư mục app đặt cho cuốn này khi mở từ file - suy từ nội dung, không phải mã nằm trong sách."""
        return content_key({name: meta["sha256"] for name, meta in self.chapter_prints.items()})

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

    def extract(self, library: Path, folder: str | None = None) -> Path:
        """Giải nén vào `library/<folder>/` (mặc định: tên suy từ nội dung), kiểm cỡ + mã băm TRONG LÚC chép - một lần đọc,
        không đọc cả file hai lượt (cả bộ có thể vài GB). Thư mục tạm rồi đổi tên: hỏng giữa chừng thì không có gì vào
        thư viện, không bao giờ để lại nửa cuốn. Thư mục ấy đã có thì được thay - app chọn `folder` là cuốn cùng lần sản
        xuất đã có. Ổ đĩa không đủ chỗ thì từ chối TRƯỚC khi chép gì. Thư mục ấy đã có phần sửa của người nghe (edits.json) thì
        phần sửa KHÔNG mất: nó được hợp với phần sửa của file (`book_edits.merge`: bên máy này thắng), báo cáo ở `last_merge`."""
        library = Path(library)
        library.mkdir(parents=True, exist_ok=True)
        self.require_room(library)
        name = folder or self.content_key
        target = library / name
        staging = library / f".{name}.{secrets.token_hex(4)}.part"
        files = self.book["package"]["files"]
        try:
            for entry in [MANIFEST, READIUM_MANIFEST, *self.content]:
                destination = staging.joinpath(*entry.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with self._zip.open(entry) as source, destination.open("wb") as sink:
                    while chunk := source.read(_CHUNK):
                        digest.update(chunk)
                        sink.write(chunk)
                        size += len(chunk)
                expected = files.get(entry)  # book.json / manifest.json không nằm trong danh sách mã băm
                if expected is not None and (size != expected["size"] or digest.hexdigest() != expected["sha256"]):
                    raise BookFileError(f"File sách bị hỏng hoặc bị sửa ({entry}). Hãy chép lại file từ nguồn.")
            self.last_merge = self._keep_local_edits(target, staging) if target.exists() else None
            if target.exists():
                retired = library / f".{name}.{secrets.token_hex(4)}.old"
                os.replace(target, retired)
                os.replace(staging, target)
                shutil.rmtree(retired, ignore_errors=True)
            else:
                os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target

    def _keep_local_edits(self, target: Path, staging: Path) -> dict[str, Any] | None:
        """Thư mục cũ có phần sửa của người nghe: hợp nó vào bản vừa giải nén (trước khi bản cũ bị thay)."""
        return keep_local_edits(target, staging, self.edits)

    def require_room(self, library: Path) -> None:
        """Ổ chứa `library` còn đủ chỗ cho cả cuốn khi giải nén? Không thì `BookFileError` nói cần bao nhiêu, còn bao nhiêu."""
        ensure_room(library, sum(info.file_size for info in self._zip.infolist()))

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
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise BookFileError("File sách có phiên bản định dạng không hợp lệ.")
        if version > FORMAT_VERSION:
            raise BookFileError("Sách này được làm bằng bản app mới hơn. Hãy cập nhật app để mở.")
        files = package.get("files")
        content = names - {"mimetype", MANIFEST, READIUM_MANIFEST}
        # thư mục phần chỉ có từ phiên bản 3, lớp sửa (edits.json, edits/cover.jpg) từ phiên bản 4, chữ chương (texts/) từ phiên bản 5
        allowed = content_pattern(version)
        for name in content:
            if not allowed.fullmatch(name):
                raise BookFileError(f"Gói có mục lạ: {name!r}.")
        if not isinstance(files, dict) or set(files) != content:
            raise BookFileError("Danh sách file trong sách không khớp nội dung gói.")
        for name, meta in files.items():
            if (not isinstance(meta, dict) or self._zip.getinfo(name).file_size != meta.get("size")
                    or not isinstance(meta.get("sha256"), str)):
                raise BookFileError(f"Mô tả file {name!r} không khớp gói.")
        music = book.get("music")
        if music is not None:
            tracks = music.get("tracks") if isinstance(music, dict) else None
            if not isinstance(tracks, dict) or not isinstance(music.get("chapters"), dict):
                raise BookFileError("Phần nhạc nền của sách bị hỏng.")
            for name, track in tracks.items():
                if (not music_plan.TRACK_FILE.fullmatch(name) or not isinstance(track, dict)
                        or track.get("file") != name or name not in content):
                    raise BookFileError("Sách thiếu file nhạc nền.")
        for chapter in book.get("chapters") or []:
            reference = chapter.get("file") if isinstance(chapter, dict) else None
            if reference and reference not in content:
                raise BookFileError("File sách thiếu audio của một chương.")
            written = chapter.get("text") if isinstance(chapter, dict) else None
            if written and (not isinstance(written, str) or written not in content):
                raise BookFileError("File sách thiếu chữ của một chương.")
        self._check_edits(content)
        return book

    def _check_edits(self, content: set[str]) -> None:
        """Lớp sửa (phiên bản 4): kiểm bằng `book_edits.read_layer` - cùng cổng với gói điện thoại gửi về."""
        try:
            self._edits, _ = book_edits.read_layer(self._zip, content)
        except book_edits.EditsError as exc:
            raise BookFileError(str(exc)) from exc

    @property
    def edits(self) -> dict[str, Any]:
        """Lớp sửa của người nghe mà file mang theo (đã kiểm); rỗng khi file không có."""
        return self._edits

    def copy_member(self, name: str, target: Path) -> None:
        """Chép một mục của gói ra `target` (nguyên tử): bài nhạc người nghe đã ghim, khi nhập lại vào cuốn đã có (`book_edits.adopt`)."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(f".{target.name}.{secrets.token_hex(4)}.part")
        try:
            with self._zip.open(name) as source, part.open("wb") as sink:
                shutil.copyfileobj(source, sink, _CHUNK)
            os.replace(part, target)
        finally:
            part.unlink(missing_ok=True)

    def edits_cover(self) -> bytes | None:
        """Byte ảnh bìa sửa của file (edits/cover.jpg), hay None."""
        return self._zip.read(book_edits.EDITS_COVER) if book_edits.EDITS_COVER in self.book["package"]["files"] else None

    def _json(self, name: str) -> Any:
        if self._zip.getinfo(name).file_size > MAX_JSON_BYTES:
            raise BookFileError(f"{name} quá lớn.")
        try:
            return json.loads(self._zip.read(name).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise BookFileError(f"{name} hỏng.") from exc


def keep_local_edits(target: Path, staging: Path, incoming: dict[str, Any]) -> dict[str, Any] | None:
    """Thư mục cũ `target` của cuốn có phần sửa của người nghe: hợp nó với phần sửa của file (`incoming`) vào bản vừa giải nén
    `staging` (máy này thắng), kể cả bìa sửa và file bài nhạc đã ghim - trước khi bản cũ bị thay. Báo cáo của `merge`, hay None
    khi thư mục cũ chưa sửa gì. Dùng chung cho `BookFile.extract` và `ProjectFile.extract`."""
    local = book_edits.load(target)
    if book_edits.is_empty(local):
        return None
    merged, report = book_edits.merge(local, incoming)
    book_edits.save(staging, merged)
    if report["cover"] == "local":
        destination = staging / book_edits.EDITS_COVER
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / book_edits.EDITS_COVER, destination)
    for name in book_edits.pinned_files(merged):  # bài người nghe đã ghim ở máy này: file của nó không mất khi nhập lại
        kept, fresh = target.joinpath(*name.split("/")), staging.joinpath(*name.split("/"))
        if kept.is_file() and not fresh.exists():
            fresh.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kept, fresh)
    return report


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


def ensure_room(library: Path, size: int) -> None:
    """Ổ chứa `library` còn đủ chỗ cho `size` byte giải nén (cộng chút dư)? Không thì `BookFileError` nói cần bao nhiêu, còn bao nhiêu.
    Dùng chung cho `BookFile` và `ProjectFile` (nhập `.abookproj` thành sách)."""
    need = size + _ROOM_MARGIN
    free = shutil.disk_usage(library).free
    if free < need:
        raise BookFileError(f"Ổ đĩa không đủ chỗ để mở sách này: cần khoảng {_gigabytes(need)}, còn {_gigabytes(free)}. "
                            "Hãy dọn bớt ổ đĩa rồi mở lại file.")


def _gigabytes(size: int) -> str:
    return f"{size / 1024**3:.1f} GB".replace(".", ",")


def _order(name: str) -> tuple[int, str]:
    """Phần nhỏ trước, audio sau cùng: đọc mô tả, bìa, chữ mà không phải lướt qua hàng trăm MB audio."""
    rank = ("edits", "cover.jpg", "cast.json", "scripts/", "texts/", "samples/", "chapters/", "music/")
    return next(index for index, prefix in enumerate(rank) if name.startswith(prefix)), name


def _entry(name: str, *, stored: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=time.localtime()[:6])  # ZIP ghi giờ địa phương
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    return info


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8")


def describe(source: Path | bytes) -> dict[str, Any]:
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
    # Tên sách tiếng Việt: console Windows mặc định cp1252 thì print vỡ (UnicodeEncodeError) - in UTF-8, thay ký tự lạ.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pack_command = commands.add_parser("pack", help="gói một cuốn sách thành một file")
    pack_command.add_argument("project", type=Path)
    pack_command.add_argument("-o", "--out", type=Path, default=None)
    repack_command = commands.add_parser("repack", help="đóng lại một cuốn đã nhập (kèm phần sửa của người nghe)")
    repack_command.add_argument("folder", type=Path)
    repack_command.add_argument("-o", "--out", type=Path, required=True)
    for name in ("inspect", "verify"):
        commands.add_parser(name).add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            print(pack(args.project, args.out))
            return 0
        if args.command == "repack":
            print(repack(args.folder, args.out))
            return 0
        with BookFile(args.file) as book:
            if args.command == "verify":
                book.verify()
            chapters = book.book.get("chapters") or []
            print(f"{book.book['title']} · {book.content_key} · {sum(1 for c in chapters if c.get('file'))}/{len(chapters)}"
                  f" chương có audio · {len(book.content)} file{' · mã băm khớp' if args.command == 'verify' else ''}")
        return 0
    except BookFileError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
