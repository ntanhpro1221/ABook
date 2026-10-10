"""Dữ liệu một cuốn sách cho giao diện - CHỈ ĐỌC.

Mọi kết nối mở bằng URI `mode=ro` + `PRAGMA query_only`, không migrate, không ghi, không chạm file điều khiển
(AGENTS.md: nhánh quan sát là read-only; SQLite đang chạy đọc bằng `mode=ro`, không `immutable=1` vì có WAL).
Không dùng `_ReadOnlyProjectDB` của CLI: nó chép nguyên file DB (136 MB cho một lô 40 chương) mỗi lần mở -
đúng cho một lệnh chạy một lần, sai cho một giao diện hỏi trạng thái mỗi giây.

Mọi con số ở đây đo trên bảng thật: `segments.status` (không phải `speaker`, cột có mặc định), `wav_sha256`
cho "đã thu", `chapters.completed_at` cho mốc chương xong. Nhãn tiếng Việt nằm ở `humanize.py`.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import time
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, ClassVar, Iterable

from . import humanize, word_timing
from .. import names as renames

DB_NAME = "project.sqlite3"
SETTINGS_NAME = "book_settings.json"
FINAL_SEGMENT_STATUSES = ("verified", "warning", "failed")
ACCEPTED_SEGMENT_STATUSES = ("verified", "warning")
# Tỉ trọng thời gian thật của hai pha trên máy này (lô 18, 26-09): phân tích 4,7 giờ, thu âm ~5 giờ.
ANALYSIS_WEIGHT = 0.47
RATE_WINDOW_SECONDS = 30 * 60.0
MIN_RATE_SAMPLES = 12
# Giây làm lại một câu đã thu khi cuốn chưa có chương nào xong để đo (thu + nghe kiểm + đôi lần thu lại): cố ý dư tay trên card
# 8 GB - hứa lâu rồi xong sớm hơn là hứa nhanh rồi bắt chờ. Có số đo của chính cuốn thì luôn dùng số đo (`seconds_per_line`).
FALLBACK_SECONDS_PER_LINE = 12.0
LEASE_FRESH_SECONDS = 120.0
STABLE_ID = re.compile(r"^c(\d+)_s(\d+)_")


def is_project(path: Path) -> bool:
    return (path / DB_NAME).is_file() and (path / SETTINGS_NAME).is_file()


def touched(project_root: Path) -> float:
    """Lần ghi cuối: mốc muộn hơn giữa file DB và `-wal` (WAL ghi vào `-wal` trước, file chính đổi khi checkpoint)."""
    database = project_root / DB_NAME
    stamps = []
    for candidate in (database, database.with_name(DB_NAME + "-wal")):
        try:
            stamps.append(candidate.stat().st_mtime)
        except OSError:
            pass
    return max(stamps) if stamps else 0.0


def connect(project_root: Path) -> sqlite3.Connection:
    uri = (project_root / DB_NAME).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def speaker_request_problem(project_root: Path, stable_id: str, text_sha256: str, speaker: str,
                            new_gender: str = "") -> str | None:
    """Mã lý do dây chuyền sẽ từ chối yêu cầu "ai nói câu này", hoặc None - hỏi bằng ĐÚNG phép dây chuyền dùng
    (`listener_overrides.speaker_target`), trên SQLite chỉ đọc, để người nghe biết ngay chứ không phải chờ ranh giới.
    `new_gender`: người nghe TẠO người nói mới (chưa có giọng) - hợp lệ khi tên dùng được."""
    from ..listener_overrides import speaker_target

    with closing(connect(project_root)) as connection:
        _target, problem = speaker_target(connection, stable_id=stable_id, text_sha256=text_sha256, speaker=speaker,
                                          new_gender=new_gender)
    return problem


def line_request_problem(project_root: Path, stable_id: str, text_sha256: str, *, kind: str = "", emotion: str = "",
                         intensity: int | None = None, speaker: str = "", spoken: str | None = None) -> str | None:
    """Mã lý do dây chuyền sẽ từ chối yêu cầu sửa cách đọc một câu (và người nói đi kèm khi câu từ lời kể thành lời thoại),
    hoặc None - hỏi bằng ĐÚNG phép dây chuyền dùng (`line_target`, `speaker_target`), trên SQLite chỉ đọc."""
    from ..listener_overrides import line_target, speaker_target

    with closing(connect(project_root)) as connection:
        target, problem = line_target(connection, stable_id=stable_id, text_sha256=text_sha256, kind=kind,
                                      emotion=emotion, intensity=intensity, spoken=spoken)
        if problem is None and speaker and target is not None:
            _speaker, problem = speaker_target(connection, stable_id=stable_id, text_sha256=text_sha256, speaker=speaker,
                                               as_kind=target["kind"])
    return problem


def voice_request_problem(project_root: Path, character: str, *, preset: str = "", gender: str = "",
                          avoid: str = "") -> str | None:
    """Mã lý do dây chuyền sẽ từ chối yêu cầu giọng/giới của một nhân vật, hoặc None - hỏi bằng ĐÚNG phép dây chuyền dùng
    (`listener_overrides.voice_target`), trên SQLite chỉ đọc."""
    from ..listener_overrides import voice_target

    with closing(connect(project_root)) as connection:
        _target, problem = voice_target(connection, book_voices(project_root), character=character, preset=preset,
                                        gender=gender, avoid=avoid)
    return problem


def book_voices(project_root: Path) -> dict[str, Any]:
    """Phần `voices` của cài đặt cuốn (giọng người kể, người kể khác) chồng lên mặc định - thứ `voice_target` cần."""
    from ..config import build_settings

    stored = read_settings(project_root).get("voices")
    return {**build_settings()["voices"], **(stored if isinstance(stored, dict) else {})}


def seconds_per_line(connection: sqlite3.Connection) -> tuple[float, bool]:
    """(giây làm một câu, có phải số đo không): tốc độ THẬT của chính cuốn này - thời gian các chương đã xong (bắt đầu -> xong)
    chia số câu của chúng; chưa chương nào xong thì FALLBACK_SECONDS_PER_LINE."""
    done = connection.execute(
        "SELECT started_at, completed_at, total_segments FROM chapters "
        "WHERE status='completed' AND started_at IS NOT NULL AND completed_at > started_at AND total_segments > 0"
    ).fetchall()
    spent = sum(float(row["completed_at"]) - float(row["started_at"]) for row in done)
    lines_done = sum(int(row["total_segments"]) for row in done)
    if lines_done and spent > 0:
        return spent / lines_done, True
    return FALLBACK_SECONDS_PER_LINE, False


def already_applied(project_root: Path, section: str, entries: dict[str, dict[str, Any]]) -> bool:
    """Dây chuyền đã đưa một trong các yêu cầu này vào sách chưa (ranh giới chương vừa qua): áp lại bây giờ không còn
    đổi gì - hỏi bằng ĐÚNG phép các bước áp dùng để bỏ qua yêu cầu đã áp (database.apply_listener_*), trên SQLite chỉ
    đọc. Chỉ có nghĩa với quyết định ĐỔI: "giữ nguyên" thì áp hay chưa, sách vẫn như cũ."""
    from ..database import LISTENER_PRONUNCIATION_SOURCE
    from ..listener_overrides import (pronunciation_requests, speaker_requests, speaker_target, surface_key,
                                      voice_requests, voice_target)

    with closing(connect(project_root)) as connection:
        if section == "speakers":
            for wish in speaker_requests({"speakers": entries}):
                target, _problem = speaker_target(connection, stable_id=wish["stable_id"],
                                                  text_sha256=wish["text_sha256"], speaker=wish["speaker"],
                                                  new_gender=wish.get("new_gender", ""))
                if (target is not None and "create" not in target
                        and target["line"]["canonical_character_id"] == target["character_id"]
                        and target["line"]["voice_profile_id"] == target["voice_profile_id"]):
                    return True
        elif section == "pronunciations":
            for wish in pronunciation_requests({"pronunciations": entries}):
                row = connection.execute(
                    "SELECT spoken_form, source, locked FROM pronunciations WHERE normalized_surface=?",
                    (surface_key(wish["surface"]),),
                ).fetchone()
                if (row is not None and int(row["locked"]) and str(row["source"]) == LISTENER_PRONUNCIATION_SOURCE
                        and str(row["spoken_form"]) == wish["spoken_form"]):
                    return True
        elif section == "voices":
            voices = book_voices(project_root)
            for wish in voice_requests({"voices": entries}):
                target, _problem = voice_target(connection, voices, character=wish["character"], preset=wish["preset"],
                                                gender=wish["gender"], avoid=wish["avoid"])
                if target is not None and target["profile"] is None and not target["lock_gender"]:
                    return True
    return False


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def read_settings(project_root: Path) -> dict[str, Any]:
    try:
        return json.loads((project_root / SETTINGS_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def chapter_mp3(project_root: Path, recorded_path: str | None) -> Path | None:
    """File MP3 của chương, tìm theo TÊN trong chính thư mục sách - không tin đường dẫn tuyệt đối trong DB,
    vì sách có thể đã được chuyển chỗ (và server chỉ phát file nằm trong thư mục sách)."""
    if not recorded_path:
        return None
    name = Path(str(recorded_path).replace("\\", "/")).name
    candidate = project_root / "output" / "chapters" / name
    return candidate if candidate.is_file() else None


class AudioLocator:
    """Tìm WAV của câu trong thư mục sách (`segment_audio`) cho CẢ LOẠT câu: thư mục sách và thư mục chứa các file (`chunks/`) chỉ
    phải `resolve` một lần, mỗi file chỉ còn một `lstat`. Hộp việc hỏi ~15.000 câu ví dụ trên cuốn 400 chương - `resolve` từng file
    (hai lần `_getfinalpathname`, thêm lần cho thư mục sách) là phần lớn của 8 giây. File là liên kết (symlink/junction) hay đường dẫn
    có `..` thì vẫn `resolve` đầy đủ như cũ. Một bộ dùng trong MỘT lần gọi: sống lâu thì thư mục bị thay giữa chừng sẽ cho kết quả cũ.
    `many`: hỏi hàng nghìn file chung vài thư mục thì đọc cả thư mục một lần (60.000 file: 0,14 giây) rẻ hơn `lstat` từng file (0,6 giây)."""

    def __init__(self, project_root: Path, many: bool = False) -> None:
        self.project_root = project_root
        self.root = project_root.resolve()
        self._parents: dict[Path, Path] = {}
        self._inside: dict[Path, bool] = {}
        self._listings: dict[Path, dict[str, os.DirEntry[str]]] | None = {} if many else None

    def _lstat(self, path: Path) -> os.stat_result:
        if self._listings is not None:
            listing = self._listings.get(path.parent)
            if listing is None:
                try:
                    listing = {entry.name: entry for entry in os.scandir(path.parent)}
                except OSError:
                    listing = {}
                self._listings[path.parent] = listing
            entry = listing.get(path.name)
            if entry is not None:
                try:
                    return entry.stat(follow_symlinks=False)
                except OSError:
                    pass
        return os.lstat(path)  # không có trong danh sách (khác chữ hoa/thường, mới tạo, chưa có): hỏi thẳng

    def probe(self, path: Path) -> tuple[Path, bool]:
        """(`path.resolve()`, `path.is_file()`) - cho file thường chỉ tốn một `lstat`."""
        if not path.name or ".." in path.parts or "." in path.parts:
            resolved = path.resolve()
            return resolved, resolved.is_file()
        parent = self._parents.get(path.parent)
        if parent is None:
            parent = self._parents[path.parent] = path.parent.resolve()
        try:
            info = self._lstat(path)
        except OSError:
            return parent / path.name, False  # chưa có file: `resolve` cũng chỉ nối phần đuôi vào thư mục đã giải
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            resolved = path.resolve()
            return resolved, resolved.is_file()
        return parent / path.name, stat.S_ISREG(info.st_mode)

    def within_root(self, resolved: Path) -> bool:
        """`resolved` nằm trong thư mục sách - chỉ phụ thuộc thư mục chứa nó, nên nhớ theo thư mục."""
        inside = self._inside.get(resolved.parent)
        if inside is None:
            try:
                resolved.parent.relative_to(self.root)
                inside = True
            except ValueError:
                inside = False
            self._inside[resolved.parent] = inside
        return inside

    def find(self, recorded_path: str | None) -> Path | None:
        if not recorded_path:
            return None
        project_root = self.project_root
        path = Path(str(recorded_path))
        try:
            resolved, is_file = self.probe(path if path.is_absolute() else project_root / path)
            if self.within_root(resolved) or resolved == self.root:
                return resolved if is_file else None
        except (OSError, ValueError):
            pass
        # Ngoài thư mục sách: nối phần đuôi từ thư mục con của dự án ("work", "output") vào thư mục sách hiện tại. Rẻ - chỉ
        # `is_file`, rồi `resolve` đúng một file: hộp việc gọi hàm này cho hàng trăm câu (thử mọi phần đuôi từng làm nó chậm
        # 0,7 -> 5 giây).
        parts = Path(str(recorded_path).replace("\\", "/")).parts
        for index, part in enumerate(parts):
            if part not in ("work", "output") or ".." in parts[index:]:
                continue
            candidate = project_root.joinpath(*parts[index:])
            if not candidate.is_file():
                continue
            try:
                found, _is_file = self.probe(candidate)
            except (OSError, ValueError):
                return None
            return found if self.within_root(found) else None
        return None


def segment_audio(project_root: Path, recorded_path: str | None, locator: AudioLocator | None = None) -> Path | None:
    """WAV của một câu, chỉ khi nó nằm trong thư mục sách. Đường dẫn trong DB là tuyệt đối lúc thu: sách đã chuyển chỗ (thư
    mục dự án đổi tên 28-09, chép sang máy khác) thì tìm lại theo phần ĐUÔI dài nhất của đường dẫn ấy ngay trong thư mục sách
    - như `chapter_mp3` tìm MP3 theo tên (soát UX 29-09: câu mẫu báo "chưa có bản thu" dù file vẫn nằm đó). Hỏi cho nhiều câu
    một lượt thì dựng một `AudioLocator` và truyền vào."""
    if not recorded_path:
        return None
    return (locator or AudioLocator(project_root)).find(recorded_path)


def lease_age(connection: sqlite3.Connection, now: float) -> float | None:
    if "worker_leases" not in _table_names(connection):
        return None
    row = connection.execute("SELECT MAX(heartbeat_at) AS beat FROM worker_leases").fetchone()
    if row is None or row["beat"] is None:
        return None
    try:
        return max(0.0, now - float(row["beat"]))
    except (TypeError, ValueError):
        return None


def _rate(connection: sqlite3.Connection, where: str, now: float) -> float | None:
    """Số câu mỗi giây trong 30 phút gần nhất, hoặc None khi chưa đủ mẫu để nói gì."""
    row = connection.execute(
        f"SELECT COUNT(*) AS n, MIN(updated_at) AS first FROM segments WHERE updated_at >= ? AND ({where})",
        (now - RATE_WINDOW_SECONDS,),
    ).fetchone()
    count = int(row["n"] or 0)
    if count < MIN_RATE_SAMPLES or row["first"] is None:
        return None
    span = max(60.0, now - float(row["first"]))
    return count / span


def _first_line(path: Any) -> str | None:
    """Dòng khác rỗng đầu tiên của một file chương (đọc 8 KB đầu, giải mã như dây chuyền), hoặc None."""
    if not path:
        return None
    from ..io_utils import decode_text_bytes

    try:
        with open(str(path), "rb") as handle:
            data = handle.read(8192)
    except OSError:
        return None
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        data = data[: len(data) // 2 * 2]
    else:
        # Chỉ những dòng trọn vẹn: một ký tự nhiều byte bị cắt ở 8 KB làm bộ giải mã chọn nhầm bảng mã.
        cut = data.rfind(b"\n")
        if 0 < cut < len(data) - 1:
            data = data[:cut]
    text = decode_text_bytes(data)
    return next((line.strip() for line in text.splitlines() if line.strip()), None)


def chapter_names(connection: sqlite3.Connection, project_root: Path | None = None) -> dict[int, dict[str, Any]]:
    """chapter_id -> {index, name, subtitle, full} theo dòng tiêu đề đầu chương (xem `humanize.chapter_names`). Có
    `project_root` thì tên người nghe đặt lại (`CHAPTER_TITLES_FILE`) thay tên suy ra - mọi nơi hiện tên chương như nhau."""
    renamed = chapter_title_overrides(project_root) if project_root is not None else {}
    headings = {
        int(row["chapter_id"]): str(row["text"] or "")
        for row in connection.execute("SELECT chapter_id, text, MIN(seq) FROM segments GROUP BY chapter_id")
    }
    has_path = "input_path" in {row[1] for row in connection.execute("PRAGMA table_info(chapters)")}
    out: dict[int, dict[str, Any]] = {}
    for row in connection.execute(f"SELECT id, chapter_index, title{', input_path' if has_path else ''} FROM chapters"):
        heading = headings.get(int(row["id"]))
        if heading is None and has_path:
            # Chương chưa tách câu (dự án chưa chạy tới): dòng đầu FILE nguồn, như danh sách chương của trình tạo - tên file
            # lệch một so với truyện ("767.txt" mở đầu "Chương 768 - ...") làm ranh giới hai phần trông như lặp chương
            # (soát UX 29-09).
            heading = _first_line(row["input_path"])
        name, subtitle = humanize.chapter_names(str(row["title"]), heading)
        name, subtitle = apply_chapter_title(name, subtitle, renamed.get(int(row["id"])))
        out[int(row["id"])] = {
            "index": int(row["chapter_index"]),
            "name": name,
            "subtitle": subtitle,
            "full": chapter_full_title(name, subtitle),
        }
    return out


def chapter_full_title(name: str, subtitle: str) -> str:
    """Tên đầy đủ của chương: "Chương 12 · Hồi kết", hay chỉ tên khi không có tên phụ."""
    return f"{name} · {subtitle}" if subtitle else name


def apply_chapter_title(name: str, subtitle: str, edit: dict[str, str] | None) -> tuple[str, str]:
    """Tên (`title`) và tên phụ (`subtitle`) của chương sau khi người nghe đặt lại: chỉ phần nào có trong `edit` đổi."""
    if not edit:
        return name, subtitle
    return edit.get("title", name), edit.get("subtitle", subtitle)


RUN_MARKER = "studio_last_run.json"
# Tên người dùng đặt lại trong Studio: máy chủ giao diện chỉ ĐỌC sổ dự án (connect: query_only), nên tên mới nằm ở file
# riêng này thay vì cột `book.title` của dây chuyền. Mọi nơi hiện/xuất tên đi qua `summarize`.
TITLE_FILE = "studio_title.json"
TITLE_MAX = 160


# Tên chương người dùng đặt lại (Studio, trang nghe, điện thoại): file riêng cạnh sổ dự án như `TITLE_FILE` - sổ chỉ đọc,
# tên chương thật của dây chuyền (`chapters.title`) giữ nguyên. {"<mã chương>": {"title"?: ..., "subtitle"?: ...}}.
CHAPTER_TITLES_FILE = "chapter_titles.json"


def chapter_title_overrides(project_root: Path) -> dict[int, dict[str, str]]:
    """{mã chương: {"title"?, "subtitle"?}} người dùng đã đặt lại; file hỏng hay mục lạ thì bỏ mục ấy."""
    try:
        data = json.loads((Path(project_root) / CHAPTER_TITLES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[int, dict[str, str]] = {}
    for key, entry in (data.items() if isinstance(data, dict) else ()):
        if not isinstance(entry, dict) or not str(key).isdigit():
            continue
        kept = {field: entry[field] for field in ("title", "subtitle") if isinstance(entry.get(field), str)}
        if kept.get("title", "x"):
            out[int(key)] = kept
    return out


def set_chapter_title(project_root: Path, chapter_id: int, title: str | None, subtitle: str | None = None) -> None:
    """Đặt lại tên chương `chapter_id`. `title` rỗng/None và `subtitle` None: trở về tên gốc của dây chuyền. `subtitle` ""
    (khác None) là bỏ hẳn tên phụ. Ghi nguyên tử; không còn mục nào thì xoá file."""
    from ..io_utils import atomic_write_json

    entries = {str(key): value for key, value in chapter_title_overrides(project_root).items()}
    entry: dict[str, str] = {}
    if title:
        entry["title"] = title
    if subtitle is not None:
        entry["subtitle"] = subtitle
    if entry:
        entries[str(int(chapter_id))] = entry
    else:
        entries.pop(str(int(chapter_id)), None)
    target = Path(project_root) / CHAPTER_TITLES_FILE
    if entries:
        atomic_write_json(target, entries)
    else:
        target.unlink(missing_ok=True)


def source_digests(project_root: Path) -> set[str]:
    """SHA-256 nội dung các file truyện đã đưa vào dự án (chapters.input_sha256)."""
    with closing(connect(project_root)) as connection:
        return {str(row[0]) for row in connection.execute("SELECT input_sha256 FROM chapters") if row[0]}


def segment_text_sha256(project_root: Path, stable_id: str) -> str | None:
    """Băm chữ của một câu theo mã ổn định (yêu cầu gửi dây chuyền mang băm này - câu đã đổi chữ thì không áp nhầm)."""
    try:
        with closing(connect(project_root)) as connection:
            row = connection.execute("SELECT text_sha256 FROM segments WHERE stable_id=?", (stable_id,)).fetchone()
    except sqlite3.Error:
        return None
    return str(row[0]) if row is not None and row[0] else None


def continuation_plan(project_root: Path) -> dict[str, Any]:
    """"Làm tiếp cuốn này" (abook/continuation.py): các chương kế tiếp trong thư mục truyện, tên phần sau, cài
    đặt giữ nguyên (chất lượng, giọng kể, người xưng "tôi") và những gì sẽ mang theo - cho trình tạo sách điền sẵn."""
    from .. import continuation

    settings = read_settings(project_root)
    voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
    with closing(connect(project_root)) as connection:
        book = connection.execute("SELECT title FROM book WHERE id=1").fetchone()
        segments = connection.execute(
            "SELECT COUNT(*) AS total, SUM(status != 'pending') AS analyzed FROM segments").fetchone()
    title = display_title(project_root, str(book["title"]) if book is not None else project_root.name)
    part = continuation.part_number(project_root) + 1
    total = int(segments["total"] or 0)
    inputs = continuation._input_paths(project_root)
    last_input = inputs[-1] if inputs else None
    return {
        "sourceTitle": continuation.base_title(title),
        "part": part,
        "title": continuation.continued_title(title, part),
        "paths": [str(path) for path in continuation.next_chapters(project_root)],
        # Thư mục truyện của chương cuối đã làm: trình tạo nói RÕ thư mục nào chưa có chương mới (soát UX 29-09).
        "folder": str(last_input.parent) if last_input else "",
        "lastChapter": last_input.name if last_input else "",
        "profile": str(settings.get("quality_profile") or "high_quality"),
        "narrator": str(voices.get("narrator_voice") or ""),
        "firstPerson": str(voices.get("first_person_identity") or ""),
        # Model đọc hiểu của phần trước (soát UX a6 01-10, B3): phần sau đọc bằng đúng model ấy - đổi model giữa hai phần
        # là đổi cách gán người nói giữa cuốn. Máy chủ bỏ đi nếu Ollama không còn model ấy.
        "analysisModel": str((settings.get("analysis") or {}).get("model") or ""),
        # Phần trước còn đang phân tích thì sổ nhân vật chưa đủ - trình tạo nói ra, không chặn.
        "analyzed": bool(total) and int(segments["analyzed"] or 0) == total,
        "carries": continuation.carried_summary(project_root),
    }


def _analysis_begun(connection: sqlite3.Connection) -> bool:
    """Phân tích đã bắt đầu: có câu được phân tích, hay sổ ứng viên phân tích không trống (AGENTS.md: có ứng viên là phân
    tích đã bắt đầu)."""
    if connection.execute("SELECT 1 FROM segments WHERE status != 'pending' LIMIT 1").fetchone():
        return True
    return "analysis_candidates" in _table_names(connection) and bool(
        connection.execute("SELECT 1 FROM analysis_candidates LIMIT 1").fetchone())


def not_started(project_root: Path) -> bool:
    """Sách đã tạo mà CHƯA chạy bước nào: chưa câu nào được phân tích, sổ ứng viên phân tích trống. Chỉ khi ấy mới được làm
    lại với thiết lập khác - cài đặt khoá theo sách từ lúc tạo, và chưa có gì để mất."""
    with closing(connect(project_root)) as connection:
        book = connection.execute("SELECT status FROM book WHERE id=1").fetchone()
        return book is not None and str(book["status"]) == "created" and not _analysis_begun(connection)


def _analysis_cut(connection: sqlite3.Connection) -> bool:
    """Phân tích đã bắt đầu mà chưa xong: còn câu `pending` (AGENTS.md: khác 0 nghĩa là phân tích chưa xong), hay chưa câu nào
    được tách mà đã có ứng viên phân tích."""
    if not _analysis_begun(connection):
        return False
    counted = connection.execute("SELECT COUNT(*) AS total, SUM(status = 'pending') AS pending FROM segments").fetchone()
    return not counted["total"] or bool(counted["pending"])


def analysis_unfinished(project_root: Path) -> bool:
    """Phân tích đã bắt đầu mà chưa xong. Chạy tiếp từ đó ra MỘT CUỐN SÁCH KHÁC với chạy liền mạch (AGENTS.md "Đừng stop
    giữa pha phân tích") - lối sạch là phân tích lại từ đầu bằng một dự án mới."""
    with closing(connect(project_root)) as connection:
        return _analysis_cut(connection)


def can_redo(project_root: Path) -> bool:
    """Làm lại được bằng "Sửa thiết lập" / "Làm lại phân tích": chưa chạy bước nào, hay phân tích dở dang."""
    return not_started(project_root) or analysis_unfinished(project_root)


def redo_plan(project_root: Path) -> dict[str, Any]:
    """"Sửa thiết lập" của sách chưa bắt đầu (soát UX a5 01-10, #4): mọi lựa chọn lúc tạo - chương, tên, chất lượng, giọng
    kể, người xưng "tôi", model đọc hiểu, bỏ dòng ghi công - cho trình tạo sách điền sẵn. Tạo xong cuốn mới thì cuốn này
    vào Thùng rác (`create` với `replaces`)."""
    from .. import continuation

    settings = read_settings(project_root)
    voices = settings.get("voices") if isinstance(settings.get("voices"), dict) else {}
    text = settings.get("text") if isinstance(settings.get("text"), dict) else {}
    with closing(connect(project_root)) as connection:
        book = connection.execute("SELECT title FROM book WHERE id=1").fetchone()
    chapters = voices.get("first_person_chapters")
    return {
        "started": not can_redo(project_root),
        # Phân tích dở dang: làm lại = phân tích lại từ đầu (bản dở vào Thùng rác), không phải sửa thiết lập của sách mới tạo.
        "analysisInterrupted": not not_started(project_root) and analysis_unfinished(project_root),
        "paths": [str(path) for path in continuation._input_paths(project_root)],
        "title": display_title(project_root, str(book["title"]) if book is not None else project_root.name),
        "profile": str(settings.get("quality_profile") or "high_quality"),
        "narrator": str(voices.get("narrator_voice") or ""),
        "firstPerson": str(voices.get("first_person_identity") or ""),
        "firstPersonChapters": {str(key): str(value) for key, value in chapters.items()} if isinstance(chapters, dict) else {},
        "analysisModel": str((settings.get("analysis") or {}).get("model") or ""),
        "dropCreditLines": bool(text.get("drop_credit_lines")),
    }


def display_title(project_root: Path, fallback: str) -> str:
    """Tên sách người dùng đặt lại (TITLE_FILE), hay `fallback` - tên lúc tạo trong sổ."""
    try:
        title = str(json.loads((project_root / TITLE_FILE).read_text(encoding="utf-8")).get("title") or "").strip()
    except (OSError, ValueError, AttributeError):
        title = ""
    return title or fallback


def clean_title(value: str) -> str:
    """Tên hợp lệ: bỏ ký tự điều khiển, gộp khoảng trắng, tối đa TITLE_MAX ký tự; chuỗi rỗng là không hợp lệ."""
    text = "".join(" " if unicodedata.category(char)[0] == "C" else char for char in str(value))
    return " ".join(text.split())[:TITLE_MAX].strip()


def set_display_title(project_root: Path, title: str) -> None:
    temporary = project_root / f".{TITLE_FILE}.tmp"
    temporary.write_text(json.dumps({"title": title}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, project_root / TITLE_FILE)


def mark_run_started(project_root: Path, started_at: float) -> None:
    """Studio đã khởi động một lượt chạy lúc `started_at`: lượt ấy áp MỌI yêu cầu ghi trước đó (Pipeline._recover áp
    overrides trước mọi việc) - kể cả khi chẳng có gì phải thu lại và dây chuyền không ghi gì vào sổ, nên mốc
    `book.updated_at` một mình thì nút "Áp dụng" không bao giờ tắt."""
    try:
        (project_root / RUN_MARKER).write_text(json.dumps({"startedAt": started_at}), encoding="utf-8")
    except OSError:
        pass


def changes_since(project_root: Path, book_updated_at: float) -> float:
    """Mốc mà yêu cầu sửa ghi SAU nó còn chờ áp: lần dây chuyền ghi sổ cuối hay lần Studio khởi động lượt chạy cuối."""
    try:
        started = float(json.loads((project_root / RUN_MARKER).read_text(encoding="utf-8")).get("startedAt") or 0)
    except (OSError, ValueError, AttributeError, TypeError):
        started = 0.0
    return max(book_updated_at, started)


def pending_changes(project_root: Path, since: float) -> int:
    """Số yêu cầu của người nghe (overrides.json: cách đọc tên, người nói, cách đọc câu, giọng, thu lại câu) ghi SAU lần dây chuyền ghi sổ
    cuối `since`. Sách đã xong không tự chạy lại, nên các yêu cầu ấy chờ mãi nếu không có nút "Áp dụng" (soát UX 29-09:
    mọi thẻ báo "chờ lần chạy tới" mà trang dự án "Hoàn tất" không có nút chạy nào). Chạy lại một cuốn xong áp chúng trước
    bước phục hồi (Pipeline._recover) rồi chỉ thu lại câu bị ảnh hưởng."""
    from ..listener_overrides import read_overrides

    data = read_overrides(project_root)
    fresh: dict[str, dict[str, Any]] = {}
    for section in ("pronunciations", "speakers", "lines", "voices", "retakes"):
        entries = data.get(section)
        chosen: dict[str, Any] = {}
        for key, entry in (entries.items() if isinstance(entries, dict) else ()):
            try:
                if float(entry.get("requested_at") or 0) > since:
                    chosen[str(key)] = entry
            except (AttributeError, TypeError, ValueError):
                continue
        fresh[section] = chosen
    kept = _kept_as_is(project_root, fresh)
    # Một lần bấm gán / thu lại nhiều câu (cả nhóm vai phụ, "Gộp vào…", "Thu lại cả chương", Shift-chọn ở Kịch bản) ghi
    # mọi câu cùng một `requested_at`: một thay đổi, không phải trăm.
    total = 0
    for section, entries in fresh.items():
        alive = {key: entry for key, entry in entries.items() if (section, key) not in kept}
        total += len({_click(entry) for entry in alive.values()}) if section in BY_CLICK else len(alive)
    return total


BY_CLICK = ("speakers", "retakes")


def _click(entry: Any) -> float:
    try:
        return float(entry.get("requested_at") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


QUOTE_OPENERS = {"“": "”", '"': '"', "‘": "’", "'": "'", "«": "»", "「": "」", "『": "』"}
EMOTIONS = {"neutral": "Bình thường", "happy": "Vui", "sad": "Buồn", "angry": "Giận", "afraid": "Sợ", "surprised": "Ngạc nhiên",
            "tender": "Dịu dàng", "sarcastic": "Mỉa mai", "excited": "Hào hứng", "tired": "Mệt mỏi", "whispering": "Thì thầm"}
LINE_KINDS = {"narration": "lời kể", "dialogue": "lời thoại", "thought": "nội tâm"}


def quote_line(text: str) -> str:
    """Một câu trích trong hộp thay đổi: cắt ở 70 ký tự. Câu thoại đã có ngoặc của sách ("“Cái… cái này là gì?”") thì không
    bọc thêm một lớp nữa. Dùng chung cho hộp "Áp dụng" của dự án và danh sách ý muốn chờ của sách không có xưởng."""
    text = " ".join(str(text or "").split())
    if text[:1] in QUOTE_OPENERS:
        return f"{text[:70]}…{QUOTE_OPENERS[text[0]]}" if len(text) > 70 else text
    return f"“{text[:70]}…”" if len(text) > 70 else f"“{text}”"


def label_pronunciation(surface: str, spoken_form: Any) -> str:
    return f"“{surface}” đọc là “{spoken_form}”"


def label_speaker(text: str, who: str, count: int) -> str:
    """"“Đi thôi.” là lời của Lucien", hay (cả nhóm câu của một lần bấm) "12 câu là lời của Lucien"."""
    return f"{quote_line(text)} là lời của {who}" if count == 1 else f"{count} câu là lời của {who}"


def label_line(text: str, entry: dict[str, Any]) -> str:
    what = []
    if entry.get("kind"):
        what.append(f"đọc là {LINE_KINDS.get(str(entry['kind']), str(entry['kind']))}")
    if entry.get("emotion"):
        what.append(f"cảm xúc {EMOTIONS.get(str(entry['emotion']), str(entry['emotion'])).lower()}")
    if isinstance(entry.get("spoken"), str):
        what.append(f"chữ đem đọc “{entry['spoken'][:50]}”" if entry["spoken"] else "đọc lại theo chữ sách")
    return f"{quote_line(text)}: {', '.join(what) or 'cách đọc mới'}"


def keeps_voice(entry: Any) -> bool:
    """Mục giọng rỗng - "Giữ nguyên" (thẻ chung giọng), "Để máy quyết" (thẻ giới): không đổi gì trong sách, không phải thay
    đổi chờ áp (soát UX a23: "Áp dụng 8 thay đổi" và "Giọng của Heidi: giọng khác · 7 câu thu lại" cho những mục ấy)."""
    return isinstance(entry, dict) and not any(str(entry.get(field) or "").strip() for field in ("preset", "gender", "avoid"))


def label_voice(name: str, entry: dict[str, Any]) -> str:
    change = entry.get("preset") or {"male": "giọng nam", "female": "giọng nữ"}.get(str(entry.get("gender")), "giọng khác")
    return f"Giọng của {name}: {change}"


def label_retake(text: str, count: int) -> str:
    return f"Thu lại {quote_line(text)}" if count == 1 else f"Thu lại cả chương ({count} câu)"


def person_label(project_root: Path, raw: Any) -> str:
    """Tên người nói như người nghe thấy trong hộp thay đổi: "người kể", tên đã đổi, hay tên gốc đã làm sạch."""
    from .humanize import person_name

    raw = str(raw or "")
    return "người kể" if raw.upper() == "NARRATOR" else renames.shown(project_root, raw) or person_name(raw)


class _WordIndex:
    """Từ -> các câu (vị trí trong danh sách) có từ ấy. Khoá hạ chữ kiểu `casefold` (cộng İ/ı về i, hai chữ mà `re.IGNORECASE` coi là
    một với i) nên mọi câu mà `re.IGNORECASE` khớp trọn từ đều nằm trong tập ứng viên; người gọi vẫn thử lại từng ứng viên bằng regex."""

    _FOLD: ClassVar[dict[int, str]] = {0x130: "i", 0x131: "i"}

    def __init__(self, texts: list[str]) -> None:
        self._at: dict[str, list[int]] = defaultdict(list)
        keys: dict[str, str] = {}
        for position, text in enumerate(texts):
            found = set()
            for word in re.findall(r"\w+", text):
                key = keys.get(word)
                if key is None:
                    key = keys[word] = self.key(word)
                found.add(key)
            for key in found:
                self._at[key].append(position)

    @classmethod
    def key(cls, word: str) -> str:
        return word.translate(cls._FOLD).casefold()

    def positions(self, word: str) -> list[int]:
        return self._at.get(self.key(word), [])


def pending_details(project_root: Path, since: float) -> dict[str, Any]:
    """Nút "Áp dụng N thay đổi" mở hộp xem trước (soát UX a6 01-10: bấm là chạy ngay, không nói sẽ thu lại gì, hết bao lâu):
    từng thay đổi nói bằng lời, số câu sẽ thu lại, ở những chương nào, và thời gian ước theo TỐC ĐỘ THẬT của chính cuốn này
    (`seconds_per_line`; chưa đo được thì số ước dư tay, `measured` False). Cùng cách chọn như `pending_changes` (yêu cầu ghi
    sau `since`, bỏ yêu cầu giữ nguyên) để số mục khớp số trên nút. Câu chưa thu không tốn thêm gì nên không tính."""
    from ..listener_overrides import character_key, read_overrides, surface_key

    data = read_overrides(project_root)
    fresh: dict[str, dict[str, Any]] = {}
    for section in ("pronunciations", "speakers", "lines", "voices", "retakes"):
        entries = data.get(section)
        fresh[section] = {
            str(key): entry for key, entry in (entries.items() if isinstance(entries, dict) else ())
            if isinstance(entry, dict) and _requested_after(entry, since)
        }
    items: list[dict[str, Any]] = []
    affected: set[str] = set()
    chapters_hit: set[int] = set()
    if not (Path(project_root) / DB_NAME).is_file():
        return {"items": items, "lines": 0, "chapters": [], "seconds": 0.0, "measured": False}
    titles = {chapter["id"]: chapter["displayTitle"] for chapter in chapters(project_root)}

    def same(left: Any, right: Any) -> bool:
        return " ".join(str(left or "").casefold().split()) == " ".join(str(right or "").casefold().split())

    quote = quote_line

    def handle(section: str, key: str, entry: dict[str, Any]) -> dict[str, Any]:
        # Đủ để bỏ ĐÚNG yêu cầu này khỏi hộp (POST …/pending-changes/withdraw): lần bấm sau đã thay thì không bỏ nhầm.
        return {"section": section, "key": key, "requestedAt": float(entry.get("requested_at") or 0)}

    def who(raw: Any) -> str:
        return person_label(project_root, raw)

    with closing(connect(project_root)) as connection:
        rows = connection.execute(
            "SELECT stable_id, chapter_id, text, speaker, kind, wav_path FROM segments ORDER BY chapter_id, seq"
        ).fetchall()
        by_id = {str(row["stable_id"]): row for row in rows}
        recorded = [row for row in rows if row["wav_path"]]

        def hit(stable_ids: list[str]) -> int:
            count = 0
            for stable_id in stable_ids:
                row = by_id.get(stable_id)
                if row is not None and row["wav_path"]:
                    affected.add(stable_id)
                    chapters_hit.add(int(row["chapter_id"]))
                    count += 1
            return count

        words: _WordIndex | None = None
        forms = {}
        if "pronunciations" in _table_names(connection):
            forms = {surface_key(str(row[0])): str(row[1] or "")
                     for row in connection.execute("SELECT surface, spoken_form FROM pronunciations")}
        for key, entry in fresh["pronunciations"].items():
            if key in forms and same(entry.get("spoken_form"), forms[key]):
                continue
            surface = str(entry.get("surface") or key)
            pattern = re.compile(rf"(?<![\w]){re.escape(surface)}(?![\w])", re.IGNORECASE)
            if re.fullmatch(r"\w+", surface):
                # Một từ trọn vẹn: chỉ những câu có từ trùng tên (theo chữ hoa/thường) mới đáng thử regex - tách từ cả sách MỘT lần
                # thay vì quét cả sách cho từng cách đọc chờ áp (150 cách x 60.000 câu = 9 triệu lần `search`, 13 giây).
                if words is None:
                    words = _WordIndex([str(row["text"] or "") for row in recorded])
                candidates = (recorded[position] for position in words.positions(surface))
            else:
                candidates = recorded
            ids = [str(row["stable_id"]) for row in candidates if pattern.search(str(row["text"] or ""))]
            items.append({"kind": "pronunciation", "label": label_pronunciation(surface, entry.get("spoken_form", "")),
                          "lines": hit(ids), **handle("pronunciations", key, entry)})
        speaker_clicks: dict[float, list[str]] = {}
        for stable_id, entry in fresh["speakers"].items():
            row = by_id.get(stable_id)
            if row is None or (not entry.get("new") and same(entry.get("speaker"), row["speaker"])):
                continue
            speaker_clicks.setdefault(_click(entry), []).append(stable_id)
        for at, stable_ids in speaker_clicks.items():
            entry = fresh["speakers"][stable_ids[0]]
            row = by_id[stable_ids[0]]
            if len(stable_ids) == 1:
                items.append({"kind": "speaker", "label": label_speaker(row["text"], who(entry.get("speaker")), 1),
                              "chapter": titles.get(int(row["chapter_id"]), ""), "lines": hit(stable_ids),
                              **handle("speakers", stable_ids[0], entry)})
                continue
            # Một lần bấm cho nhiều câu (nhóm vai phụ, "Gộp vào…", Shift-chọn): một mục, bỏ thì bỏ cả nhóm.
            places = sorted({int(by_id[stable_id]["chapter_id"]) for stable_id in stable_ids})
            items.append({"kind": "speaker", "label": label_speaker("", who(entry.get("speaker")), len(stable_ids)),
                          "chapter": titles.get(places[0], "") + (f" và {len(places) - 1} chương khác" if len(places) > 1 else ""),
                          "lines": hit(stable_ids), "section": "speakers", "key": stable_ids[0], "keys": stable_ids,
                          "requestedAt": at})
        for stable_id, entry in fresh["lines"].items():
            row = by_id.get(stable_id)
            if row is None:
                continue
            items.append({"kind": "line", "label": label_line(row["text"], entry),
                          "chapter": titles.get(int(row["chapter_id"]), ""), "lines": hit([stable_id]),
                          **handle("lines", stable_id, entry)})
        by_voice_key: dict[str, list[Any]] | None = None
        for key, entry in fresh["voices"].items():
            if keeps_voice(entry):
                continue
            if by_voice_key is None:
                by_voice_key = defaultdict(list)
                keys_of: dict[str, str] = {}  # cả sách chỉ vài trăm tên người nói
                for row in rows:
                    speaker = str(row["speaker"] or "")
                    if speaker not in keys_of:
                        keys_of[speaker] = character_key(speaker)
                    by_voice_key[keys_of[speaker]].append(row)
            same_person = by_voice_key.get(key, [])
            ids = [str(row["stable_id"]) for row in same_person if row["wav_path"]]
            # Khoá giọng là tên đã hạ chữ thường - lấy lại cách viết trong sách từ một câu của người ấy.
            name = who(same_person[0]["speaker"]) if same_person else who(key)
            # Đủ để "Nghe thử" đúng giọng sẽ áp trên một câu của người ấy (POST …/voice/preview, reading_preview.py).
            wish = {"character": key, **{field: str(entry.get(field) or "") for field in ("preset", "gender", "avoid")}}
            items.append({"kind": "voice", "label": label_voice(name, entry), "lines": hit(ids), "voice": wish,
                          **handle("voices", key, entry)})
        clicks: dict[float, list[str]] = {}
        for stable_id, entry in fresh["retakes"].items():
            clicks.setdefault(_click(entry), []).append(stable_id)
        for at, stable_ids in clicks.items():
            known = [stable_id for stable_id in stable_ids if stable_id in by_id]
            if not known:
                continue
            row = by_id[known[0]]
            chapter = titles.get(int(row["chapter_id"]), "")
            if len(stable_ids) == 1:
                items.append({"kind": "retake", "label": label_retake(row["text"], 1), "chapter": chapter,
                              "lines": hit(known), **handle("retakes", known[0], fresh["retakes"][known[0]])})
            else:
                # Một lần bấm "Thu lại cả chương": một mục, bỏ thì bỏ cả nhóm (`keys`).
                items.append({"kind": "retake", "label": label_retake("", len(stable_ids)), "chapter": chapter,
                              "lines": hit(known), "section": "retakes", "key": stable_ids[0], "keys": stable_ids,
                              "requestedAt": at})
        each, measured = seconds_per_line(connection)
    return {
        "items": items,
        "lines": len(affected),
        "chapters": [titles.get(chapter, str(chapter)) for chapter in sorted(chapters_hit)],
        "seconds": round(len(affected) * each, 1),
        # False: chưa chương nào xong để đo - thời gian là số ước dư tay (FALLBACK_SECONDS_PER_LINE), giao diện nói vậy.
        "measured": measured,
    }


def _requested_after(entry: dict[str, Any], since: float) -> bool:
    try:
        return float(entry.get("requested_at") or 0) > since
    except (TypeError, ValueError):
        return False


def _kept_as_is(project_root: Path, fresh: dict[str, dict[str, Any]]) -> set[tuple[str, str]]:
    """Số yêu cầu "giữ nguyên" trong `fresh`: người nói bằng đúng người câu đang có, cách đọc bằng đúng cách đang đọc, mục
    giọng rỗng (`keeps_voice`). Chúng
    không đổi gì trong sách nên không phải "thay đổi chờ áp" - soát UX 29-09: sáu lần bấm "Giữ…"/"Đúng rồi" đẩy số trên nút
    "Áp dụng N thay đổi" từ 38 lên 47 trong khi chỉ một lần đổi thật."""
    from ..listener_overrides import surface_key

    kept: set[tuple[str, str]] = {("voices", key) for key, entry in (fresh.get("voices") or {}).items() if keeps_voice(entry)}
    speakers, pronunciations = fresh.get("speakers") or {}, fresh.get("pronunciations") or {}
    if not (speakers or pronunciations) or not (Path(project_root) / DB_NAME).is_file():
        return kept

    def same(left: Any, right: Any) -> bool:
        return " ".join(str(left or "").casefold().split()) == " ".join(str(right or "").casefold().split())

    try:
        with closing(connect(project_root)) as connection:
            if speakers:
                ids = list(speakers)
                current: dict[str, str] = {}
                for start in range(0, len(ids), 500):
                    chunk = ids[start:start + 500]
                    current.update(
                        (str(row[0]), str(row[1] or ""))
                        for row in connection.execute(
                            f"SELECT stable_id, speaker FROM segments WHERE stable_id IN ({','.join('?' * len(chunk))})", chunk
                        )
                    )
                kept.update(
                    ("speakers", stable_id) for stable_id, entry in speakers.items()
                    if stable_id in current and isinstance(entry, dict) and not entry.get("new")
                    and same(entry.get("speaker"), current[stable_id])
                )
            if pronunciations and "pronunciations" in _table_names(connection):
                forms = {
                    surface_key(str(row[0])): str(row[1] or "")
                    for row in connection.execute("SELECT surface, spoken_form FROM pronunciations")
                }
                kept.update(
                    ("pronunciations", key) for key, entry in pronunciations.items()
                    if key in forms and isinstance(entry, dict) and same(entry.get("spoken_form"), forms[key])
                )
    except sqlite3.Error:
        return {item for item in kept if item[0] == "voices"}
    return kept


def summarize(project_root: Path, *, running: bool = False, now: float | None = None) -> dict[str, Any]:
    """Tóm tắt một cuốn cho thư viện và phần đầu trang sách."""
    now = time.time() if now is None else now
    settings = read_settings(project_root)
    with closing(connect(project_root)) as connection:
        book = connection.execute("SELECT * FROM book WHERE id=1").fetchone()
        if book is None:
            raise ValueError(f"{project_root} chưa được khởi tạo")
        chapter_rows = connection.execute("SELECT status, COUNT(*) AS n FROM chapters GROUP BY status").fetchall()
        # Chương "xong" trong sổ mà file MP3 không còn (dời/xoá tay, bản sao thiếu audio): Studio từng báo "43/43 chương nghe
        # được" trong khi thư viện chỉ thấy 3 (soát UX 29-09).
        missing_audio = sum(
            1 for row in connection.execute("SELECT output_mp3 FROM chapters WHERE status = 'completed'")
            if chapter_mp3(project_root, row[0]) is None
        )
        segments = connection.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(status != 'pending') AS analyzed,"
            " SUM(wav_sha256 IS NOT NULL AND wav_sha256 != '') AS recorded,"
            f" SUM(status IN {FINAL_SEGMENT_STATUSES}) AS finished,"
            " SUM(status = 'failed') AS failed"
            " FROM segments"
        ).fetchone()
        audio = connection.execute(
            "SELECT COALESCE(SUM(s.wav_duration), 0) + COALESCE(SUM(s.break_ms), 0) / 1000.0 AS seconds"
            " FROM segments s JOIN chapters c ON c.id = s.chapter_id WHERE c.status = 'completed'"
        ).fetchone()
        beat_age = lease_age(connection, now)
        status = str(book["status"])
        stage = str(book["stage"] or "")
        phase = humanize.phase_of(status, stage)
        total = int(segments["total"] or 0)
        analyzed = int(segments["analyzed"] or 0)
        finished = int(segments["finished"] or 0)
        # Phân vai đã khoá: dàn nhân vật, giọng, cách đọc tên đã có - mốc "Duyệt trước khi thu" (precast.py).
        cast_locked = bool(int(book["casting_finalized"] or 0)) if "casting_finalized" in book.keys() else False
        if status == "paused":
            # Tạm dừng (power_source): dây chuyền ghi status/stage "paused" và nhớ pha cũ trong bộ nhớ. Đoán lại pha từ tiến
            # độ - "Đã dừng" là sai khi tiến trình vẫn sống; tiến trình chết lúc đang tạm dừng thì là "Tạm ngưng lúc ...".
            # Phân vai chạy dưới status "analyzing" (humanize.phase_of gọi là phân tích) cho tới khi khoá phân vai.
            finalized = int(book["casting_finalized"] or 0) if "casting_finalized" in book.keys() else 1
            if analyzed < total or not total or not finalized:
                phase = "analysis"
            elif not int(segments["recorded"] or 0) and not any(row["status"] == "completed" for row in chapter_rows):
                phase = "casting"
            else:
                phase = "synthesis"
        # Phân tích dở dang: đã bắt đầu, còn câu chờ, và không có tiến trình nào đang làm (Dừng, hay chết giữa chừng - pha là
        # "stopped" / "error" / "analysis" tuỳ cách ngắt). Chạy tiếp ra cuốn khác với chạy liền mạch.
        analysis_cut = phase != "done" and _analysis_cut(connection)
        eta = None
        if running and phase == "analysis" and total:
            rate = _rate(connection, "status != 'pending'", now)
            if rate:
                eta = {"phase": "analysis", "seconds": round((total - analyzed) / rate)}
        elif running and phase == "synthesis" and total:
            rate = _rate(connection, f"status IN {FINAL_SEGMENT_STATUSES}", now)
            if rate:
                eta = {"phase": "synthesis", "seconds": round((total - finished) / rate)}

    chapters = Counter({str(row["status"]): int(row["n"]) for row in chapter_rows})
    chapter_total = sum(chapters.values())
    analysis_fraction = analyzed / total if total else 0.0
    synthesis_fraction = finished / total if total else 0.0
    if phase == "done":
        overall = 1.0
    else:
        overall = ANALYSIS_WEIGHT * analysis_fraction + (1 - ANALYSIS_WEIGHT) * synthesis_fraction
    active = running or (beat_age is not None and beat_age <= LEASE_FRESH_SECONDS and phase in humanize.WORKING_PHASES)
    voices = settings.get("voices", {}) if isinstance(settings.get("voices"), dict) else {}
    profile = str(settings.get("quality_profile") or "")
    return {
        "path": str(project_root),
        "title": display_title(project_root, str(book["title"])),
        "status": status,
        "stage": stage,
        "phase": phase,
        "statusLabel": humanize.status_label(phase, stage, active=active),
        "running": bool(active),
        "interrupted": phase in humanize.WORKING_PHASES and not active,
        "analysisInterrupted": bool(analysis_cut and not active),
        "createdAt": float(book["created_at"] or 0) or None,
        "updatedAt": max(float(book["updated_at"] or 0), touched(project_root)) or None,
        "lastError": str(book["last_error"] or ""),
        "castLocked": cast_locked,
        "pendingChanges": pending_changes(project_root, changes_since(project_root, float(book["updated_at"] or 0)))
        if phase == "done" else 0,
        "settings": {
            "profile": profile,
            "profileLabel": humanize.PROFILE_LABELS.get(profile, profile),
            "narrator": str(voices.get("narrator_voice") or ""),
            # Model đã phân tích cuốn này (book_settings.json lúc tạo sách) - đổi model mặc định thì biết cuốn nào làm bằng
            # model cũ.
            "analyzer": str((settings.get("analysis") or {}).get("model") or "")
            if isinstance(settings.get("analysis"), dict) else "",
        },
        "chapters": {
            "total": chapter_total,
            "completed": chapters.get("completed", 0),
            "missingAudio": missing_audio,
            "failed": chapters.get("failed", 0),
            "working": chapters.get("synthesizing", 0) + chapters.get("verifying", 0),
        },
        "segments": {
            "total": total,
            "analyzed": analyzed,
            "pending": total - analyzed,
            "recorded": int(segments["recorded"] or 0),
            "finished": finished,
            "failed": int(segments["failed"] or 0),
        },
        "progress": {
            "overall": round(overall, 4),
            "analysis": round(analysis_fraction, 4),
            "synthesis": round(synthesis_fraction, 4),
        },
        "audioSeconds": round(float(audio["seconds"] or 0.0), 1),
        "eta": eta,
    }


def chapters(project_root: Path) -> list[dict[str, Any]]:
    with closing(connect(project_root)) as connection:
        per_chapter = {
            int(row["chapter_id"]): row
            for row in connection.execute(
                "SELECT chapter_id,"
                " COUNT(*) AS total,"
                " SUM(status != 'pending') AS analyzed,"
                " SUM(wav_sha256 IS NOT NULL AND wav_sha256 != '') AS recorded,"
                f" SUM(status IN {FINAL_SEGMENT_STATUSES}) AS finished,"
                " SUM(status = 'failed') AS failed,"
                " SUM(status = 'warning') AS warnings,"
                " COALESCE(SUM(wav_duration), 0) + COALESCE(SUM(break_ms), 0) / 1000.0 AS seconds"
                " FROM segments GROUP BY chapter_id"
            )
        }
        rows = connection.execute(
            "SELECT id, chapter_index, title, status, total_segments, output_mp3, started_at, completed_at, last_error"
            " FROM chapters ORDER BY chapter_index"
        ).fetchall()
        names = chapter_names(connection, project_root)
    out = []
    for row in rows:
        counts = per_chapter.get(int(row["id"]))
        status = str(row["status"])
        mp3 = chapter_mp3(project_root, row["output_mp3"]) if status == "completed" else None
        out.append({
            "id": int(row["id"]),
            "index": int(row["chapter_index"]),
            "title": str(row["title"]),
            "displayTitle": names[int(row["id"])]["name"],
            "subtitle": names[int(row["id"])]["subtitle"],
            "fullTitle": names[int(row["id"])]["full"],
            "status": status,
            "statusLabel": "Mất file audio" if status == "completed" and mp3 is None
            else humanize.chapter_status_label(status),
            "segments": {
                "total": int(counts["total"]) if counts else int(row["total_segments"] or 0),
                "analyzed": int(counts["analyzed"] or 0) if counts else 0,
                "recorded": int(counts["recorded"] or 0) if counts else 0,
                "finished": int(counts["finished"] or 0) if counts else 0,
                "failed": int(counts["failed"] or 0) if counts else 0,
                "warnings": int(counts["warnings"] or 0) if counts else 0,
            },
            "seconds": round(float(counts["seconds"] or 0.0), 1) if counts else 0.0,
            "playable": mp3 is not None,
            "startedAt": float(row["started_at"]) if row["started_at"] else None,
            "completedAt": float(row["completed_at"]) if row["completed_at"] else None,
            "lastError": humanize.error_text(str(row["last_error"] or "")),
        })
    return out


_DURATION_CACHE: dict[tuple[str, float], float] = {}


def audio_duration(path: Path) -> float | None:
    """Độ dài thật của file audio (MP3 đọc bằng libsndfile >= 1.1, ~10 ms). Cache theo mtime."""
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    key = (str(path), stamp)
    if key not in _DURATION_CACHE:
        try:
            import soundfile

            _DURATION_CACHE[key] = float(soundfile.info(str(path)).duration)
        except Exception:  # noqa: BLE001 - không đọc được thì để kịch bản dùng tổng độ dài các câu
            return None
    return _DURATION_CACHE[key]


DELIVERY_TAGS = ("emotion", "intensity", "pace", "volume")


def chapter_source_text(project_root: Path, chapter_id: int) -> str | None:
    """Chữ nguồn của một chương (file TXT người dùng đã đưa vào lúc tạo sách), giải mã như dây chuyền; None khi file nguồn không
    còn đó. Dùng để gói một cuốn chưa có audio thành sách chỉ-chữ (bookfile.listening_layer)."""
    from ..io_utils import decode_text_bytes

    with closing(connect(project_root)) as connection:
        row = connection.execute("SELECT input_path FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
    if row is None or not row["input_path"]:
        return None
    try:
        return decode_text_bytes(Path(str(row["input_path"])).read_bytes())
    except OSError:
        return None


def chapter_script(project_root: Path, chapter_id: int) -> dict[str, Any] | None:
    """Văn bản chương theo từng câu, kèm mốc thời gian trong file MP3 - cho chế độ "đọc theo".

    Chương MP3 là các WAV câu nối nhau, sau mỗi câu (trừ câu cuối) là `break_ms` im lặng
    (`audio_io._source_timeline`). Tổng `wav_duration + break_ms` của chương 645 (lô 16) là 783,6 s, file MP3
    đo được 783,74 s: lệch 0,14 s trên 13 phút. Vẫn co giãn tuyến tính theo độ dài MP3 thật để phần lệch ấy
    không dồn về cuối chương.
    """
    with closing(connect(project_root)) as connection:
        chapter = connection.execute(
            "SELECT id, title, status, output_mp3 FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if chapter is None:
            return None
        # Tag trình bày của từng câu (cảm xúc, cường độ, nhịp, âm lượng) - có ở mọi sách làm bằng dây chuyền hiện nay,
        # sách rất cũ thì không: chỉ lấy cột nào có.
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
        tags = [column for column in DELIVERY_TAGS if column in columns]
        # Mã ổn định + băm chữ: định danh câu qua các lần sản xuất lại - lớp sửa của người nghe (docs/EDITING.md) và yêu
        # cầu "ai nói câu này" trỏ tới câu bằng cặp này, nên sách xuất ra mang chúng theo (cộng thêm, không đổi phiên bản).
        identity = [column for column in ("stable_id", "text_sha256") if column in columns]
        # Câu đứng ngay trước một dòng ngăn cảnh ("***"): nhạc nền đổi cảnh ở câu kế (webui/music_scenes.hard_break).
        scene_break = ["scene_break"] if "scene_break" in columns else []
        rows = connection.execute(
            "SELECT id, seq, paragraph_index, text, kind, speaker, wav_duration, break_ms, status"
            + "".join(f", {column}" for column in (*identity, *scene_break, *tags))
            + " FROM segments WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        names = {
            str(row["canonical_name"]): str(row["display_name"] or row["canonical_name"])
            for row in connection.execute("SELECT canonical_name, display_name FROM characters")
        }
        chapter_name = chapter_names(connection, project_root).get(int(chapter["id"]), {})
    renamed = renames.load(project_root)
    timed, spans, mp3, duration = _sentence_timeline(project_root, chapter, rows)
    segments = []
    for index, row in enumerate(rows):
        speaker = str(row["speaker"] or "")
        start, end = spans[index]
        heading = index == 0 and humanize.is_heading(str(row["text"]))
        segments.append({
            "id": int(row["id"]),
            "paragraph": int(row["paragraph_index"] or 0),
            "text": str(row["text"]),
            "kind": "heading" if heading else str(row["kind"] or "narration"),
            "speaker": "" if speaker in ("", "NARRATOR")
            else renamed.get(renames.name_key(speaker)) or humanize.person_name(names.get(speaker, speaker)),
            "start": round(start, 3) if timed else None,
            "end": round(end, 3) if timed else None,
            "status": str(row["status"]),
            **({"stableId": str(row["stable_id"])} if "stable_id" in identity and row["stable_id"] else {}),
            **({"textSha256": str(row["text_sha256"])} if "text_sha256" in identity and row["text_sha256"] else {}),
            **({"sceneBreak": True} if scene_break and row["scene_break"] else {}),
            **{column: row[column] for column in tags if row[column] is not None},
        })
    if timed and mp3:  # mốc từng chữ đã căn lúc đóng gói (word_timing.py): thêm `words` cho câu nào còn khớp bộ nhớ đệm
        word_timing.attach(project_root, int(chapter["id"]), segments, mp3)
    return {
        "chapterId": int(chapter["id"]),
        "title": chapter_name.get("full") or humanize.chapter_title(str(chapter["title"])),
        "timed": bool(timed and mp3),
        "duration": round(duration, 3),
        "segments": segments,
    }


def _sentence_timeline(project_root: Path, chapter: Any,
                       rows: list[Any]) -> tuple[bool, list[tuple[float, float]], Path | None, float]:
    """(có mốc không, (đầu, cuối) của từng câu trong MP3 chương, file MP3, độ dài chương) - xem `chapter_script`. `chapter`
    cần `status`, `output_mp3`; `rows` (theo `seq`) cần `wav_duration`, `break_ms`."""
    timed = str(chapter["status"]) == "completed" and all(row["wav_duration"] for row in rows)
    starts: list[float] = []
    elapsed = 0.0
    for index, row in enumerate(rows):
        starts.append(elapsed)
        elapsed += float(row["wav_duration"] or 0.0)
        if index + 1 < len(rows):
            elapsed += float(row["break_ms"] or 0) / 1000.0
    mp3 = chapter_mp3(project_root, chapter["output_mp3"]) if timed else None
    real = audio_duration(mp3) if mp3 else None
    scale = (real / elapsed) if (real and elapsed) else 1.0
    spans = [(start * scale, (start + float(row["wav_duration"] or 0.0)) * scale) for start, row in zip(starts, rows)]
    return timed, spans, mp3, real if real else elapsed


def chapter_spans(project_root: Path, chapter_id: int) -> dict[int, tuple[float, float]]:
    """{mã câu: (đầu, cuối) giây trong MP3 chương} - rỗng khi chương chưa xuất hay chưa có mốc. Hàng "Cần nghe lại" dùng để
    nghe một câu ngay trong chương khi WAV riêng của câu đã được dọn."""
    with closing(connect(project_root)) as connection:
        chapter = connection.execute("SELECT status, output_mp3 FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if chapter is None:
            return {}
        rows = connection.execute(
            "SELECT id, wav_duration, break_ms FROM segments WHERE chapter_id = ? ORDER BY seq", (chapter_id,)
        ).fetchall()
    timed, spans, mp3, _duration = _sentence_timeline(project_root, chapter, rows)
    if not (timed and mp3):
        return {}
    return {int(row["id"]): (round(start, 3), round(end, 3)) for row, (start, end) in zip(rows, spans)}


def chapter_audio_path(project_root: Path, chapter_id: int) -> Path | None:
    with closing(connect(project_root)) as connection:
        row = connection.execute(
            "SELECT status, output_mp3 FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
    if row is None or str(row["status"]) != "completed":
        return None
    return chapter_mp3(project_root, row["output_mp3"])


def _voice_view(profile: sqlite3.Row | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    formant = float(profile["formant_ratio"] or 1.0)
    pitch = float(profile["pitch_semitones"] or 0.0)
    return {
        "key": str(profile["voice_key"]),
        "preset": str(profile["preset_name"]),
        "tone": humanize.voice_tone(formant, pitch),
    }


def pending_voices(project_root: Path, since: float) -> dict[str, dict[str, str]]:
    """{khoá tên chuẩn: giọng/giới người nghe đã chọn} cho các yêu cầu ghi SAU lần dây chuyền ghi sổ cuối `since` - dòng
    nhân vật hiện "chờ áp dụng" thay vì vẫn giọng cũ như chưa có gì (soát UX 29-09: đổi giọng Heidi xong, dòng vẫn ghi
    Ngọc Linh, mở lại hộp vẫn "Đang dùng")."""
    from ..listener_overrides import read_overrides

    entries = read_overrides(project_root).get("voices")
    pending: dict[str, dict[str, str]] = {}
    for key, entry in (entries.items() if isinstance(entries, dict) else ()):
        try:
            waiting = float(entry.get("requested_at") or 0) > since
        except (AttributeError, TypeError, ValueError):
            continue
        preset, gender = str(entry.get("preset") or ""), str(entry.get("gender") or "")
        if waiting and (preset or gender):
            pending[speaker_key(str(key))] = {"preset": preset,
                                              "gender": humanize.GENDER_LABELS.get(gender, "")}
    return pending


def speaker_key(name: str) -> str:
    """Khoá tên chuẩn như character_registry.canonical_key - cùng khoá mục `voices` của overrides.json."""
    return " ".join(name.strip().casefold().split()).upper()


def cast(project_root: Path) -> dict[str, Any]:
    """Ai nói trong CUỐN NÀY, bằng giọng nào. Sổ nhân vật của một lô là sổ cộng dồn cả sách (636 người ở lô 16,
    88 người thật sự lên tiếng), nên chỉ lấy những ai có câu trong bảng `segments` của project này."""
    settings = read_settings(project_root)
    voices = settings.get("voices", {}) if isinstance(settings.get("voices"), dict) else {}
    with closing(connect(project_root)) as connection:
        profiles = {int(row["id"]): row for row in connection.execute("SELECT * FROM voice_profiles")}
        characters = {
            str(row["canonical_name"]): row for row in connection.execute("SELECT * FROM characters")
        }
        spoken = connection.execute(
            "SELECT speaker, kind, voice_profile_id, COUNT(*) AS lines,"
            " COALESCE(SUM(wav_duration), 0) AS seconds, MIN(chapter_id) AS first_chapter,"
            " SUM(wav_path IS NOT NULL AND wav_path != '') AS recorded"
            " FROM segments GROUP BY speaker, kind, voice_profile_id"
        ).fetchall()
        samples = {
            str(row["speaker"]): int(row["id"])
            for row in connection.execute(
                "SELECT speaker, id FROM ("
                "  SELECT speaker, id, ROW_NUMBER() OVER ("
                "    PARTITION BY speaker ORDER BY ABS(COALESCE(wav_duration, 0) - 4.0), id) AS rank"
                "  FROM segments WHERE kind = 'dialogue' AND status IN ('verified', 'warning')"
                "   AND wav_path IS NOT NULL AND wav_path != '' AND COALESCE(wav_duration, 0) >= 1.5"
                ") WHERE rank = 1"
            )
        }
        chapter_numbers = {chapter_id: item["name"] for chapter_id, item in chapter_names(connection, project_root).items()}
        book_row = connection.execute("SELECT updated_at FROM book WHERE id=1").fetchone()
    pending = pending_voices(
        project_root, changes_since(project_root, float(book_row["updated_at"] or 0) if book_row is not None else 0.0))
    lines: dict[str, int] = defaultdict(int)
    seconds: dict[str, float] = defaultdict(float)
    recorded: dict[str, int] = defaultdict(int)
    voice_votes: dict[str, Counter[int]] = defaultdict(Counter)
    first_seen: dict[str, int] = {}
    for row in spoken:
        speaker = str(row["speaker"] or "")
        lines[speaker] += int(row["lines"])
        seconds[speaker] += float(row["seconds"] or 0.0)
        recorded[speaker] += int(row["recorded"] or 0)
        if row["voice_profile_id"] is not None:
            voice_votes[speaker][int(row["voice_profile_id"])] += int(row["lines"])
        first = int(row["first_chapter"])
        first_seen[speaker] = min(first, first_seen.get(speaker, first))

    def voice_of(speaker: str) -> dict[str, Any] | None:
        votes = voice_votes.get(speaker)
        if not votes:
            return None
        return _voice_view(profiles.get(votes.most_common(1)[0][0]))

    narrator = {
        "voice": str(voices.get("narrator_voice") or ""),
        "lines": lines.get("NARRATOR", 0),
        "seconds": round(seconds.get("NARRATOR", 0.0), 1),
        "profile": voice_of("NARRATOR"),
    }
    renamed = renames.load(project_root)

    def shown_name(name: str, original: str) -> dict[str, str]:
        """Tên người nghe đặt thay tên gốc (tab Nhân vật, "Đổi tên"); `originalName` chỉ có khi đã đổi."""
        mine = renamed.get(renames.name_key(name))
        return {"displayName": mine, "originalName": original} if mine else {"displayName": original}

    # Nhãn dành riêng của máy ("UNKNOWN") là "Vai phụ không tên" như ở hộp việc và tab Kịch bản - không bao giờ "Unknown" thô
    # (soát UX a23); tên thường thì như humanize.person_name.
    from .. import aliases
    from .reviews import speaker_label

    # "Gộp vào…" chưa áp (aliases.json + câu chờ đổi người nói): người ấy vẫn còn câu dưới tên mình - ghi "chờ gộp vào X" để
    # tab Nhân vật không trông như chưa gộp (soát UX a23).
    merging = aliases.load(project_root)

    def merged_into(speaker: str) -> str | None:
        target = merging.get(aliases.key(speaker))
        if not target or aliases.key(target) == aliases.key(speaker):
            return None
        record = characters.get(target)
        return shown_name(target, speaker_label(str(record["display_name"] or target) if record else target))["displayName"]

    main, extras = [], []
    for speaker, count in lines.items():
        if speaker in ("", "NARRATOR"):
            continue
        record = characters.get(speaker)
        entry = {
            "name": speaker,
            **shown_name(speaker, speaker_label(str(record["display_name"] or speaker) if record else speaker)),
            "gender": humanize.GENDER_LABELS.get(str(record["gender"] if record else ""), ""),
            "age": humanize.AGE_LABELS.get(str(record["age"] if record else ""), ""),
            "lines": count,
            "seconds": round(seconds[speaker], 1),
            # Số câu đã có tiếng - đúng con số "Áp dụng thay đổi" sẽ báo phải thu lại khi đổi giọng người này.
            "recorded": recorded[speaker],
            "voice": voice_of(speaker),
            "sampleId": samples.get(speaker),
            "firstChapter": chapter_numbers.get(first_seen.get(speaker, -1), ""),
            "pendingVoice": pending.get(speaker_key(speaker)),
            "mergedInto": merged_into(speaker),
        }
        (main if record is not None else extras).append(entry)
    main.sort(key=lambda entry: (-entry["lines"], entry["displayName"]))
    extras.sort(key=lambda entry: (-entry["lines"], entry["displayName"]))
    # Phần nối tiếp chưa phân tích (soát UX a6 01-10, B2): dàn mang từ phần trước - giọng đã ghim - chưa ai nói câu nào ở
    # phần này nên danh sách trên trống ("Chưa có dàn") dù cuốn mang theo cả trăm giọng. Liệt kê riêng để Studio cho thấy.
    by_key = {str(row["voice_key"]): row for row in profiles.values() if "voice_key" in row.keys()}
    spoke = {speaker_key(name) for name in lines}
    from .. import continuation

    # Chỉ phần nối tiếp (continues.json, phần 2 trở đi): ở sách lẻ, người có giọng ghim mà không có câu là người đã gộp đi.
    carried = [
        {
            "name": name,
            **shown_name(name, speaker_label(str(record["display_name"] or name))),
            "gender": humanize.GENDER_LABELS.get(str(record["gender"] or ""), ""),
            "age": humanize.AGE_LABELS.get(str(record["age"] or ""), ""),
            "lines": 0,
            "seconds": 0.0,
            "recorded": 0,
            "voice": _voice_view(by_key.get(str(record["locked_voice_key"]))),
            "sampleId": None,
            "firstChapter": "",
            "pendingVoice": pending.get(speaker_key(name)),
        }
        for name, record in characters.items()
        if speaker_key(name) not in spoke and "locked_voice_key" in record.keys() and str(record["locked_voice_key"] or "")
    ] if continuation.part_number(project_root) > 1 else []
    carried.sort(key=lambda entry: entry["displayName"])
    return {"narrator": narrator, "characters": main, "extras": extras, "carried": carried}


def original_name(project_root: Path, character: str) -> str | None:
    """Tên gốc (như sổ nhân vật ghi, chưa qua "Đổi tên") của một người nói trong sách này; None khi sách không có người ấy."""
    with closing(connect(project_root)) as connection:
        record = connection.execute(
            "SELECT display_name FROM characters WHERE canonical_name = ?", (character,)).fetchone()
        spoke = connection.execute("SELECT 1 FROM segments WHERE speaker = ? LIMIT 1", (character,)).fetchone()
    if record is None and spoke is None:
        return None
    return humanize.person_name(str(record["display_name"] or character) if record else character)


def sample_audio_path(project_root: Path, segment_id: int) -> Path | None:
    with closing(connect(project_root)) as connection:
        row = connection.execute("SELECT wav_path FROM segments WHERE id = ?", (segment_id,)).fetchone()
    return segment_audio(project_root, row["wav_path"]) if row else None


def activity(project_root: Path, *, technical: bool = False, limit: int = 200) -> list[dict[str, Any]]:
    """Nhật ký cho người đọc: mốc chương xong, lỗi và cảnh báo có nghĩa với người nghe. `technical=True` trả
    thẳng các dòng sự kiện gần nhất, không dịch."""
    with closing(connect(project_root)) as connection:
        tables = _table_names(connection)
        if technical:
            if "runtime_events" not in tables:
                return []
            rows = connection.execute(
                "SELECT id, timestamp, level, code, message FROM runtime_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {"id": f"e{row['id']}", "at": float(row["timestamp"] or 0), "level": str(row["level"]),
                 "code": str(row["code"]), "text": str(row["message"])}
                for row in rows
            ]
        names = chapter_names(connection, project_root)
        chapter_titles = {item["index"]: item["name"] for item in names.values()}
        items: list[dict[str, Any]] = []
        book = connection.execute("SELECT created_at FROM book WHERE id=1").fetchone()
        if book and book["created_at"]:
            items.append({"id": "created", "at": float(book["created_at"]), "level": "info", "kind": "created",
                          "text": "Đã tạo sách"})
        for row in connection.execute(
            "SELECT id, chapter_index, title, completed_at, status FROM chapters WHERE completed_at IS NOT NULL"
        ):
            items.append({
                "id": f"c{row['id']}", "at": float(row["completed_at"]), "level": "success", "kind": "chapter",
                "text": f"Xong {names.get(int(row['id']), {}).get('full', humanize.chapter_title(str(row['title'])))}",
            })
        if "runtime_events" in tables:
            placeholders = ",".join("?" for _ in humanize.EVENT_TEXT)
            for row in connection.execute(
                f"SELECT id, timestamp, level, code, message FROM runtime_events WHERE code IN ({placeholders})"
                " ORDER BY id DESC LIMIT 400",
                tuple(humanize.EVENT_TEXT),
            ):
                text = humanize.event_text(str(row["code"]), str(row["message"]), chapter_titles)
                if text:
                    items.append({"id": f"e{row['id']}", "at": float(row["timestamp"] or 0),
                                  "level": humanize.event_level(str(row["code"]), str(row["level"])),
                                  "kind": "event", "text": text})
    items.sort(key=lambda item: item["at"], reverse=True)
    return items[:limit]


def input_names(project_root: Path) -> Iterable[str]:
    with closing(connect(project_root)) as connection:
        for row in connection.execute("SELECT input_path FROM chapters ORDER BY chapter_index"):
            yield Path(str(row["input_path"])).name
