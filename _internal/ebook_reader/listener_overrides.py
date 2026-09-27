"""Người nghe sửa trong Studio (hộp "Việc cần anh", docs/STUDIO_REVIEW.md) - cách đọc tên, ai nói câu nào - áp ở ranh
giới an toàn.

Giao diện không ghi SQLite của sách: dây chuyền là người ghi duy nhất. Giao diện ghi ý muốn của người nghe vào
`overrides.json` cạnh `project.sqlite3`, dây chuyền đọc file ấy ở ranh giới an toàn và áp từng yêu cầu bằng
`ProjectDB.apply_listener_pronunciation` / `apply_listener_speaker` (đổi và đặt lại câu đã thu, một transaction).

File là TRẠNG THÁI MONG MUỐN, không phải hàng đợi: áp lại một yêu cầu đã áp là không làm gì. Nhờ vậy dây chuyền không
bao giờ phải ghi ngược vào file, và không bao giờ có hai tiến trình cùng ghi một file.

Vì sao chỉ ở ranh giới: `cli pronounce` gõ giữa lúc chạy đã giết alpha.47 - câu đang thu mang checksum chuỗi nói lấy
TRƯỚC khi đổi, rồi khâu kiểm báo lệch. Giữa hai chương thì không câu nào đang bay.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

OVERRIDES_FILE = "overrides.json"
OVERRIDES_VERSION = 1

# Lý do từ chối: mã ổn định cho máy, câu chữ cho người nằm ở giao diện (đổi câu chữ không được đổi hash chất lượng).
MULTI_WORD = "multi_word"
NOT_VIETNAMESE = "not_vietnamese"
UNKNOWN_LINE = "unknown_line"
SOURCE_CHANGED = "source_changed"
NOT_SPEECH = "not_speech"
NO_VOICE = "no_voice"

# Hai đích đặc biệt của "Ai nói câu này", ngoài khoá tên chuẩn của một nhân vật.
NARRATOR = "NARRATOR"
UNNAMED = "UNNAMED"
SPEECH_KINDS = frozenset({"dialogue", "thought"})


def overrides_path(project_root: Path) -> Path:
    return Path(project_root) / OVERRIDES_FILE


def read_overrides(project_root: Path) -> dict[str, Any]:
    """Không có file, hay file không đọc được, đều là "chưa có yêu cầu nào".

    Giao diện ghi file bằng thay nguyên tử, nên file hỏng chỉ có thể do sửa tay; khi ấy làm tiếp với cái máy đã
    quyết tốt hơn là dừng cả lần chạy vì một mong muốn không đọc được."""
    try:
        data = json.loads(overrides_path(project_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def surface_key(surface: str) -> str:
    """Khoá một từ như `character_registry.normalize_name` - cùng khoá `pronunciations.normalized_surface`."""
    return " ".join(str(surface).strip().casefold().split())


def pronunciation_requests(overrides: dict[str, Any]) -> list[dict[str, str]]:
    """Các yêu cầu cách đọc, theo thứ tự khoá (tất định: cùng file thì cùng thứ tự áp)."""
    entries = overrides.get("pronunciations")
    if not isinstance(entries, dict):
        return []
    requests: list[dict[str, str]] = []
    for key in sorted(entries):
        entry = entries[key]
        if not isinstance(entry, dict):
            continue
        surface, spoken = entry.get("surface"), entry.get("spoken_form")
        if isinstance(surface, str) and isinstance(spoken, str) and surface.strip() and spoken.strip():
            requests.append({"surface": surface.strip(), "spoken_form": " ".join(spoken.split())})
    return requests


def pronunciation_problem(surface: str, spoken_form: str) -> str | None:
    """Mã lý do không áp được một yêu cầu, hoặc None.

    Cùng một hợp đồng với cách đọc máy tự đề xuất: MỘT từ (AGENTS.md - cách đọc lưu theo từng từ, entry nhiều từ từng
    khoá cùng một nhân vật thành hai tên), và cách đọc là các âm tiết tiếng Việt thật (`_valid_vietnamese_spoken_form`,
    đúng phép kiểm chặn "Xă-mon", "Xờ-taiu")."""
    if len(str(surface).split()) != 1:
        return MULTI_WORD
    if surface_key(spoken_form) == surface_key(surface):
        # Đọc đúng như viết: phép kiểm tự động từ chối (máy không được lười phiên âm), người nghe thì được chọn - "Deck"
        # đọc là "Deck" (tests/test_pronounce_command.py).
        return None
    from .analysis import _valid_vietnamese_spoken_form

    if not _valid_vietnamese_spoken_form(surface, spoken_form):
        return NOT_VIETNAMESE
    return None


def speaker_requests(overrides: dict[str, Any]) -> list[dict[str, str]]:
    """Các yêu cầu "ai nói câu này", theo thứ tự mã câu."""
    entries = overrides.get("speakers")
    if not isinstance(entries, dict):
        return []
    requests: list[dict[str, str]] = []
    for stable_id in sorted(entries):
        entry = entries[stable_id]
        if not isinstance(entry, dict):
            continue
        speaker, text_sha256 = entry.get("speaker"), entry.get("text_sha256")
        if isinstance(speaker, str) and isinstance(text_sha256, str) and speaker.strip() and text_sha256.strip():
            requests.append({"stable_id": str(stable_id), "speaker": speaker.strip(), "text_sha256": text_sha256.strip()})
    return requests


def speaker_target(
    conn: sqlite3.Connection,
    *,
    stable_id: str,
    text_sha256: str,
    speaker: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Người nói mà câu sẽ mang nếu áp yêu cầu: (đích, None), hoặc (None, mã lý do).

    Dùng chung cho giao diện (từ chối ngay, SQLite chỉ đọc) và dây chuyền (trong transaction áp), nên hai bên không bao giờ
    bất đồng về một yêu cầu. Đích luôn là một nhân vật ĐÃ CÓ giọng: câu mượn đúng nhãn và giọng mà các câu khác của người
    ấy đang dùng, nên "một người một giọng" (`character_registry.assert_voice_stability`) vẫn đúng mà không phân vai lại.
    Người chưa từng nói câu nào thì chưa có giọng - gán cho họ là việc của phân vai, không phải của một lần bấm.

    UNNAMED là nhóm vô danh CÙNG GIỚI với câu (giới của câu, không có thì của người đang giữ câu), rồi nhóm chưa rõ giới;
    không bao giờ mượn giọng vô danh khác giới.
    """
    line = conn.execute(
        "SELECT id, chapter_id, kind, speaker, gender, text_sha256, status, canonical_character_id, voice_profile_id"
        " FROM segments WHERE stable_id=?",
        (stable_id,),
    ).fetchone()
    if line is None:
        return None, UNKNOWN_LINE
    if str(line["text_sha256"] or "") != text_sha256:
        return None, SOURCE_CHANGED
    if str(line["kind"]) not in SPEECH_KINDS:
        return None, NOT_SPEECH
    label: str | None = None
    if speaker == UNNAMED:
        gender = str(line["gender"] or "")
        if gender not in ("male", "female") and line["canonical_character_id"] is not None:
            holder = conn.execute(
                "SELECT gender FROM characters WHERE id=?", (int(line["canonical_character_id"]),)
            ).fetchone()
            gender = str(holder["gender"] or "") if holder is not None else ""
        keys = ([f"ANONYMOUS_{gender.upper()}"] if gender in ("male", "female") else []) + ["ANONYMOUS_UNKNOWN"]
        label = "UNKNOWN"
    else:
        keys = [" ".join(speaker.strip().casefold().split()).upper()]  # = character_registry.canonical_key
    for key in keys:
        character = conn.execute(
            "SELECT id, gender, age FROM characters WHERE canonical_name=?", (key,)
        ).fetchone()
        if character is None:
            continue
        voice = conn.execute(
            """
            SELECT voice_profile_id, speaker, COUNT(*) AS lines FROM segments
            WHERE canonical_character_id=? AND voice_profile_id IS NOT NULL
            GROUP BY voice_profile_id, speaker ORDER BY lines DESC, speaker LIMIT 1
            """,
            (int(character["id"]),),
        ).fetchone()
        if voice is None:
            continue
        return {
            "line": line,
            "character_id": int(character["id"]),
            "voice_profile_id": int(voice["voice_profile_id"]),
            "speaker": label or str(voice["speaker"]),
            "gender": str(character["gender"] or "unknown"),
            "age": str(character["age"] or "unknown"),
        }, None
    return None, NO_VOICE


def request_pronunciation(project_root: Path, surface: str, spoken_form: str, *, now: float) -> None:
    """Giao diện gọi: ghi (hoặc thay) mong muốn cho một từ."""
    data = read_overrides(project_root)
    entries = data.get("pronunciations")
    entries = dict(entries) if isinstance(entries, dict) else {}
    entries[surface_key(surface)] = {
        "surface": str(surface).strip(),
        "spoken_form": " ".join(str(spoken_form).split()),
        "requested_at": float(now),
    }
    data["pronunciations"] = entries
    _write(project_root, data)


def request_speaker(project_root: Path, stable_id: str, text_sha256: str, speaker: str, *, now: float) -> None:
    """Giao diện gọi: ghi (hoặc thay) mong muốn cho một câu. Băm chữ đi kèm để yêu cầu tự rơi khi câu đổi chữ."""
    data = read_overrides(project_root)
    entries = data.get("speakers")
    entries = dict(entries) if isinstance(entries, dict) else {}
    entries[str(stable_id)] = {
        "speaker": str(speaker).strip(),
        "text_sha256": str(text_sha256).strip(),
        "requested_at": float(now),
    }
    data["speakers"] = entries
    _write(project_root, data)


def _write(project_root: Path, data: dict[str, Any]) -> None:
    """Ghi file tạm rồi thay nguyên tử: dây chuyền đọc file bất cứ lúc nào, không bao giờ thấy nửa chừng."""
    data["version"] = OVERRIDES_VERSION
    target = overrides_path(project_root)
    handle, temporary = tempfile.mkstemp(prefix=".overrides.", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as writer:
            json.dump(data, writer, ensure_ascii=False, indent=1, sort_keys=True)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
