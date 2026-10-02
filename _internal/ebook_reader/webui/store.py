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
import time
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from . import humanize
from .. import names as renames

DB_NAME = "project.sqlite3"
SETTINGS_NAME = "book_settings.json"
FINAL_SEGMENT_STATUSES = ("verified", "warning", "failed")
ACCEPTED_SEGMENT_STATUSES = ("verified", "warning")
# Tỉ trọng thời gian thật của hai pha trên máy này (lô 18, 26-09): phân tích 4,7 giờ, thu âm ~5 giờ.
ANALYSIS_WEIGHT = 0.47
RATE_WINDOW_SECONDS = 30 * 60.0
MIN_RATE_SAMPLES = 12
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
    from ..config import build_settings
    from ..listener_overrides import voice_target

    stored = read_settings(project_root).get("voices")
    voices = {**build_settings()["voices"], **(stored if isinstance(stored, dict) else {})}
    with closing(connect(project_root)) as connection:
        _target, problem = voice_target(connection, voices, character=character, preset=preset, gender=gender,
                                        avoid=avoid)
    return problem


def already_applied(project_root: Path, section: str, entries: dict[str, dict[str, Any]]) -> bool:
    """Dây chuyền đã đưa một trong các yêu cầu này vào sách chưa (ranh giới chương vừa qua): áp lại bây giờ không còn
    đổi gì - hỏi bằng ĐÚNG phép các bước áp dùng để bỏ qua yêu cầu đã áp (database.apply_listener_*), trên SQLite chỉ
    đọc. Chỉ có nghĩa với quyết định ĐỔI: "giữ nguyên" thì áp hay chưa, sách vẫn như cũ."""
    from ..config import build_settings
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
            stored = read_settings(project_root).get("voices")
            voices = {**build_settings()["voices"], **(stored if isinstance(stored, dict) else {})}
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


def segment_audio(project_root: Path, recorded_path: str | None) -> Path | None:
    """WAV của một câu, chỉ khi nó nằm trong thư mục sách. Đường dẫn trong DB là tuyệt đối lúc thu: sách đã chuyển chỗ (thư
    mục dự án đổi tên 28-09, chép sang máy khác) thì tìm lại theo phần ĐUÔI dài nhất của đường dẫn ấy ngay trong thư mục sách
    - như `chapter_mp3` tìm MP3 theo tên (soát UX 29-09: câu mẫu báo "chưa có bản thu" dù file vẫn nằm đó)."""
    if not recorded_path:
        return None
    root = project_root.resolve()
    path = Path(str(recorded_path))
    try:
        resolved = (path if path.is_absolute() else project_root / path).resolve()
        resolved.relative_to(root)
        return resolved if resolved.is_file() else None
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
            found = candidate.resolve()
            found.relative_to(root)
        except (OSError, ValueError):
            return None
        return found
    return None


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


def chapter_names(connection: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    """chapter_id -> {index, name, subtitle, full} theo dòng tiêu đề đầu chương (xem `humanize.chapter_names`)."""
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
        out[int(row["id"])] = {
            "index": int(row["chapter_index"]),
            "name": name,
            "subtitle": subtitle,
            "full": f"{name} · {subtitle}" if subtitle else name,
        }
    return out


RUN_MARKER = "studio_last_run.json"
# Tên người dùng đặt lại trong Studio: máy chủ giao diện chỉ ĐỌC sổ dự án (connect: query_only), nên tên mới nằm ở file
# riêng này thay vì cột `book.title` của dây chuyền. Mọi nơi hiện/xuất tên đi qua `summarize`.
TITLE_FILE = "studio_title.json"
TITLE_MAX = 160


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
    """"Làm tiếp cuốn này" (ebook_reader/continuation.py): các chương kế tiếp trong thư mục truyện, tên phần sau, cài
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
        "narrator": humanize.voice_label(str(voices.get("narrator_voice") or "")),
        "firstPerson": str(voices.get("first_person_identity") or ""),
        # Model đọc hiểu của phần trước (soát UX a6 01-10, B3): phần sau đọc bằng đúng model ấy - đổi model giữa hai phần
        # là đổi cách gán người nói giữa cuốn. Máy chủ bỏ đi nếu Ollama không còn model ấy.
        "analysisModel": str((settings.get("analysis") or {}).get("model") or ""),
        # Phần trước còn đang phân tích thì sổ nhân vật chưa đủ - trình tạo nói ra, không chặn.
        "analyzed": bool(total) and int(segments["analyzed"] or 0) == total,
        "carries": continuation.carried_summary(project_root),
    }


def not_started(project_root: Path) -> bool:
    """Sách đã tạo mà CHƯA chạy bước nào: chưa câu nào được phân tích, sổ ứng viên phân tích trống (AGENTS.md: có ứng viên
    là phân tích đã bắt đầu). Chỉ khi ấy mới được làm lại với thiết lập khác - cài đặt khoá theo sách từ lúc tạo, và chưa
    có gì để mất."""
    with closing(connect(project_root)) as connection:
        book = connection.execute("SELECT status FROM book WHERE id=1").fetchone()
        if book is None or str(book["status"]) != "created":
            return False
        if connection.execute("SELECT 1 FROM segments WHERE status != 'pending' LIMIT 1").fetchone():
            return False
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return not ("analysis_candidates" in tables
                    and connection.execute("SELECT 1 FROM analysis_candidates LIMIT 1").fetchone())


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
        "started": not not_started(project_root),
        "paths": [str(path) for path in continuation._input_paths(project_root)],
        "title": display_title(project_root, str(book["title"]) if book is not None else project_root.name),
        "profile": str(settings.get("quality_profile") or "high_quality"),
        "narrator": humanize.voice_label(str(voices.get("narrator_voice") or "")),
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


def pending_details(project_root: Path, since: float) -> dict[str, Any]:
    """Nút "Áp dụng N thay đổi" mở hộp xem trước (soát UX a6 01-10: bấm là chạy ngay, không nói sẽ thu lại gì, hết bao lâu):
    từng thay đổi nói bằng lời, số câu sẽ thu lại, ở những chương nào, và thời gian ước theo TỐC ĐỘ THẬT của chính cuốn này
    (giây làm một câu = thời gian các chương đã xong / số câu của chúng). Cùng cách chọn như `pending_changes` (yêu cầu ghi
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
    seconds_per_line = 0.0
    if not (Path(project_root) / DB_NAME).is_file():
        return {"items": items, "lines": 0, "chapters": [], "seconds": 0.0}
    titles = {chapter["id"]: chapter["displayTitle"] for chapter in chapters(project_root)}

    def same(left: Any, right: Any) -> bool:
        return " ".join(str(left or "").casefold().split()) == " ".join(str(right or "").casefold().split())

    def quote(text: str) -> str:
        # Câu thoại đã có ngoặc của sách ("“Cái… cái này là gì?”") thì không bọc thêm một lớp nữa.
        text = " ".join(str(text or "").split())
        if text[:1] in QUOTE_OPENERS:
            return f"{text[:70]}…{QUOTE_OPENERS[text[0]]}" if len(text) > 70 else text
        return f"“{text[:70]}…”" if len(text) > 70 else f"“{text}”"

    def handle(section: str, key: str, entry: dict[str, Any]) -> dict[str, Any]:
        # Đủ để bỏ ĐÚNG yêu cầu này khỏi hộp (POST …/pending-changes/withdraw): lần bấm sau đã thay thì không bỏ nhầm.
        return {"section": section, "key": key, "requestedAt": float(entry.get("requested_at") or 0)}

    def who(raw: Any) -> str:
        from .humanize import person_name

        raw = str(raw or "")
        return "người kể" if raw.upper() == "NARRATOR" else renames.shown(project_root, raw) or person_name(raw)

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

        forms = {}
        if "pronunciations" in _table_names(connection):
            forms = {surface_key(str(row[0])): str(row[1] or "")
                     for row in connection.execute("SELECT surface, spoken_form FROM pronunciations")}
        for key, entry in fresh["pronunciations"].items():
            if key in forms and same(entry.get("spoken_form"), forms[key]):
                continue
            surface = str(entry.get("surface") or key)
            pattern = re.compile(rf"(?<![\w]){re.escape(surface)}(?![\w])", re.IGNORECASE)
            ids = [str(row["stable_id"]) for row in recorded if pattern.search(str(row["text"] or ""))]
            items.append({"kind": "pronunciation", "label": f"“{surface}” đọc là “{entry.get('spoken_form', '')}”",
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
                items.append({"kind": "speaker", "label": f"{quote(row['text'])} là lời của {who(entry.get('speaker'))}",
                              "chapter": titles.get(int(row["chapter_id"]), ""), "lines": hit(stable_ids),
                              **handle("speakers", stable_ids[0], entry)})
                continue
            # Một lần bấm cho nhiều câu (nhóm vai phụ, "Gộp vào…", Shift-chọn): một mục, bỏ thì bỏ cả nhóm.
            places = sorted({int(by_id[stable_id]["chapter_id"]) for stable_id in stable_ids})
            items.append({"kind": "speaker", "label": f"{len(stable_ids)} câu là lời của {who(entry.get('speaker'))}",
                          "chapter": titles.get(places[0], "") + (f" và {len(places) - 1} chương khác" if len(places) > 1 else ""),
                          "lines": hit(stable_ids), "section": "speakers", "key": stable_ids[0], "keys": stable_ids,
                          "requestedAt": at})
        for stable_id, entry in fresh["lines"].items():
            row = by_id.get(stable_id)
            if row is None:
                continue
            what = []
            if entry.get("kind"):
                what.append(f"đọc là {LINE_KINDS.get(str(entry['kind']), str(entry['kind']))}")
            if entry.get("emotion"):
                what.append(f"cảm xúc {EMOTIONS.get(str(entry['emotion']), str(entry['emotion'])).lower()}")
            if isinstance(entry.get("spoken"), str):
                what.append(f"chữ đem đọc “{entry['spoken'][:50]}”" if entry["spoken"] else "đọc lại theo chữ sách")
            items.append({"kind": "line", "label": f"{quote(row['text'])}: {', '.join(what) or 'cách đọc mới'}",
                          "chapter": titles.get(int(row["chapter_id"]), ""), "lines": hit([stable_id]),
                          **handle("lines", stable_id, entry)})
        for key, entry in fresh["voices"].items():
            ids = [str(row["stable_id"]) for row in recorded if character_key(str(row["speaker"] or "")) == key]
            # Khoá giọng là tên đã hạ chữ thường - lấy lại cách viết trong sách từ một câu của người ấy.
            name = next((who(row["speaker"]) for row in rows if character_key(str(row["speaker"] or "")) == key), who(key))
            change = entry.get("preset") or {"male": "giọng nam", "female": "giọng nữ"}.get(str(entry.get("gender")), "giọng khác")
            items.append({"kind": "voice", "label": f"Giọng của {name}: {change}", "lines": hit(ids),
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
                items.append({"kind": "retake", "label": f"Thu lại {quote(row['text'])}", "chapter": chapter,
                              "lines": hit(known), **handle("retakes", known[0], fresh["retakes"][known[0]])})
            else:
                # Một lần bấm "Thu lại cả chương": một mục, bỏ thì bỏ cả nhóm (`keys`).
                items.append({"kind": "retake", "label": f"Thu lại cả chương ({len(stable_ids)} câu)", "chapter": chapter,
                              "lines": hit(known), "section": "retakes", "key": stable_ids[0], "keys": stable_ids,
                              "requestedAt": at})
        # Tốc độ thật: các chương đã xong của chính cuốn này (bắt đầu -> xong, chia số câu).
        done = connection.execute(
            "SELECT started_at, completed_at, total_segments FROM chapters "
            "WHERE status='completed' AND started_at IS NOT NULL AND completed_at > started_at AND total_segments > 0"
        ).fetchall()
        spent = sum(float(row["completed_at"]) - float(row["started_at"]) for row in done)
        lines_done = sum(int(row["total_segments"]) for row in done)
        if lines_done:
            seconds_per_line = spent / lines_done
    return {
        "items": items,
        "lines": len(affected),
        "chapters": [titles.get(chapter, str(chapter)) for chapter in sorted(chapters_hit)],
        "seconds": round(len(affected) * seconds_per_line, 1),
    }


def _requested_after(entry: dict[str, Any], since: float) -> bool:
    try:
        return float(entry.get("requested_at") or 0) > since
    except (TypeError, ValueError):
        return False


def _kept_as_is(project_root: Path, fresh: dict[str, dict[str, Any]]) -> set[tuple[str, str]]:
    """Số yêu cầu "giữ nguyên" trong `fresh`: người nói bằng đúng người câu đang có, cách đọc bằng đúng cách đang đọc. Chúng
    không đổi gì trong sách nên không phải "thay đổi chờ áp" - soát UX 29-09: sáu lần bấm "Giữ…"/"Đúng rồi" đẩy số trên nút
    "Áp dụng N thay đổi" từ 38 lên 47 trong khi chỉ một lần đổi thật."""
    from ..listener_overrides import surface_key

    speakers, pronunciations = fresh.get("speakers") or {}, fresh.get("pronunciations") or {}
    if not (speakers or pronunciations) or not (Path(project_root) / DB_NAME).is_file():
        return set()

    def same(left: Any, right: Any) -> bool:
        return " ".join(str(left or "").casefold().split()) == " ".join(str(right or "").casefold().split())

    kept: set[tuple[str, str]] = set()
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
        return set()
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
        "createdAt": float(book["created_at"] or 0) or None,
        "updatedAt": max(float(book["updated_at"] or 0), touched(project_root)) or None,
        "lastError": str(book["last_error"] or ""),
        "pendingChanges": pending_changes(project_root, changes_since(project_root, float(book["updated_at"] or 0)))
        if phase == "done" else 0,
        "settings": {
            "profile": profile,
            "profileLabel": humanize.PROFILE_LABELS.get(profile, profile),
            "narrator": humanize.voice_label(str(voices.get("narrator_voice") or "")),
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
        names = chapter_names(connection)
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
            else humanize.CHAPTER_STATUS_LABELS.get(status, status),
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
        rows = connection.execute(
            "SELECT id, seq, paragraph_index, text, kind, speaker, wav_duration, break_ms, status"
            + "".join(f", {column}" for column in tags)
            + " FROM segments WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        names = {
            str(row["canonical_name"]): str(row["display_name"] or row["canonical_name"])
            for row in connection.execute("SELECT canonical_name, display_name FROM characters")
        }
        chapter_name = chapter_names(connection).get(int(chapter["id"]), {})
    renamed = renames.load(project_root)
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
    segments = []
    for index, row in enumerate(rows):
        speaker = str(row["speaker"] or "")
        start = starts[index] * scale
        end = (starts[index] + float(row["wav_duration"] or 0.0)) * scale
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
            **{column: row[column] for column in tags if row[column] is not None},
        })
    return {
        "chapterId": int(chapter["id"]),
        "title": chapter_name.get("full") or humanize.chapter_title(str(chapter["title"])),
        "timed": bool(timed and mp3),
        "duration": round(real if real else elapsed, 3),
        "segments": segments,
    }


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
        "preset": humanize.voice_label(str(profile["preset_name"])),
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
            pending[speaker_key(str(key))] = {"preset": humanize.voice_label(preset),
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
        chapter_numbers = {chapter_id: item["name"] for chapter_id, item in chapter_names(connection).items()}
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
        "voice": humanize.voice_label(str(voices.get("narrator_voice") or "")),
        "lines": lines.get("NARRATOR", 0),
        "seconds": round(seconds.get("NARRATOR", 0.0), 1),
        "profile": voice_of("NARRATOR"),
    }
    renamed = renames.load(project_root)

    def shown_name(name: str, original: str) -> dict[str, str]:
        """Tên người nghe đặt thay tên gốc (tab Nhân vật, "Đổi tên"); `originalName` chỉ có khi đã đổi."""
        mine = renamed.get(renames.name_key(name))
        return {"displayName": mine, "originalName": original} if mine else {"displayName": original}

    main, extras = [], []
    for speaker, count in lines.items():
        if speaker in ("", "NARRATOR"):
            continue
        record = characters.get(speaker)
        entry = {
            "name": speaker,
            **shown_name(speaker, humanize.person_name(str(record["display_name"] or speaker) if record else speaker)),
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
        }
        (main if record is not None else extras).append(entry)
    main.sort(key=lambda entry: (-entry["lines"], entry["displayName"]))
    extras.sort(key=lambda entry: (-entry["lines"], entry["displayName"]))
    # Phần nối tiếp chưa phân tích (soát UX a6 01-10, B2): dàn mang từ phần trước - giọng đã ghim - chưa ai nói câu nào ở
    # phần này nên danh sách trên trống ("Chưa có dàn") dù cuốn mang theo cả trăm giọng. Liệt kê riêng để Studio cho thấy.
    by_key = {str(row["voice_key"]): row for row in profiles.values() if "voice_key" in row.keys()}
    spoke = {speaker_key(name) for name in lines}
    carried = [
        {
            "name": name,
            **shown_name(name, humanize.person_name(str(record["display_name"] or name))),
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
    ]
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
        names = chapter_names(connection)
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
