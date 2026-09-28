"""Người nghe sửa trong Studio (hộp "Việc cần anh", docs/STUDIO_REVIEW.md) - cách đọc tên, ai nói câu nào, giọng và
giới của một nhân vật, loại đoạn, cảm xúc và chữ đem đọc của một câu - áp ở ranh giới an toàn.

Giao diện không ghi SQLite của sách: dây chuyền là người ghi duy nhất. Giao diện ghi ý muốn của người nghe vào
`overrides.json` cạnh `project.sqlite3`, dây chuyền đọc file ấy ở ranh giới an toàn và áp từng yêu cầu bằng
`ProjectDB.apply_listener_pronunciation` / `apply_listener_line` / `apply_listener_speaker` / `apply_listener_voice`
(đổi và đặt lại câu đã thu, một transaction).

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
UNKNOWN_CHARACTER = "unknown_character"
NOT_A_CHARACTER = "not_a_character"
UNKNOWN_PRESET = "unknown_preset"
BAD_GENDER = "bad_gender"
BAD_KIND = "bad_kind"
BAD_EMOTION = "bad_emotion"
BAD_TEXT = "bad_text"
# Chữ đem đọc người nghe sửa cho một câu (lỗi chữ, cách viết lạ - STUDIO_REVIEW mục 7): trần tuyệt đối, và không dài quá
# bốn lần câu gốc - sửa chữ chứ không viết lại đoạn văn.
MAX_SPOKEN_CHARS = 2000
LINE_KINDS = ("narration", "dialogue", "thought")

# Hai đích đặc biệt của "Ai nói câu này", ngoài khoá tên chuẩn của một nhân vật.
NARRATOR = "NARRATOR"
UNNAMED = "UNNAMED"
SPEECH_KINDS = frozenset({"dialogue", "thought"})
# Giới người nghe chọn khi TẠO một nhân vật mới ("Người mới…").
NEW_CHARACTER_GENDERS = frozenset({"male", "female", "unknown"})


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
            new = entry.get("new") if isinstance(entry.get("new"), dict) else {}
            new_gender = str(new.get("gender") or "")
            request = {"stable_id": str(stable_id), "speaker": speaker.strip(), "text_sha256": text_sha256.strip()}
            if new_gender in NEW_CHARACTER_GENDERS:
                request["new_gender"] = new_gender  # chỉ khi người nghe TẠO người này
            requests.append(request)
    return requests


def speaker_target(
    conn: sqlite3.Connection,
    *,
    stable_id: str,
    text_sha256: str,
    speaker: str,
    as_kind: str = "",
    new_gender: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """Người nói mà câu sẽ mang nếu áp yêu cầu: (đích, None), hoặc (None, mã lý do).

    Dùng chung cho giao diện (từ chối ngay, SQLite chỉ đọc) và dây chuyền (trong transaction áp), nên hai bên không bao giờ
    bất đồng về một yêu cầu. Đích luôn là một nhân vật ĐÃ CÓ giọng: câu mượn đúng nhãn và giọng mà các câu khác của người
    ấy đang dùng, nên "một người một giọng" (`character_registry.assert_voice_stability`) vẫn đúng mà không phân vai lại.
    Người chưa từng nói câu nào thì chưa có giọng - trừ khi người nghe TẠO họ (`new_gender`: tên mới + giới, chủ sách
    28-09 - linh thể 『』 của Yamiyo chưa từng được máy gán câu nào nên không chọn được): đích mang `create` và
    `character_id` None; bước áp (database.apply_listener_speaker) tạo nhân vật và cấp giọng như bước phân vai.

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
    # `as_kind`: câu người nghe vừa đổi từ lời kể thành lời thoại trong CÙNG yêu cầu - xét như thể đã là lời thoại.
    if (as_kind or str(line["kind"])) not in SPEECH_KINDS:
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
    if new_gender in NEW_CHARACTER_GENDERS and speaker != UNNAMED:
        display = " ".join(speaker.split()).upper()
        if not display or display in ("NARRATOR", "UNKNOWN") or display.startswith("ANONYMOUS_"):
            return None, NO_VOICE
        existing = conn.execute("SELECT id FROM characters WHERE canonical_name=?", (keys[0],)).fetchone()
        return {
            "line": line,
            "character_id": None,
            "voice_profile_id": None,
            "speaker": display,
            "gender": new_gender,
            "age": "unknown",
            "create": {"canonical": keys[0], "display": display,
                       "existing_id": int(existing["id"]) if existing is not None else None},
        }, None
    return None, NO_VOICE


def voice_requests(overrides: dict[str, Any]) -> list[dict[str, str]]:
    """Các yêu cầu giọng/giới cho một nhân vật, theo thứ tự khoá tên chuẩn.

    `preset` rỗng = để máy chọn (đúng phép chọn của bước phân vai, người khác giữ nguyên); `gender` rỗng = giữ giới đang
    có; `avoid` = khoá giọng phải tránh (hai người đang dùng chung giọng ấy). Cả ba rỗng = người nghe bảo "giữ nguyên"."""
    entries = overrides.get("voices")
    if not isinstance(entries, dict):
        return []
    requests: list[dict[str, str]] = []
    for character in sorted(entries):
        entry = entries[character]
        if not isinstance(entry, dict) or not str(character).strip():
            continue
        requests.append({
            "character": str(character).strip(),
            "preset": str(entry.get("preset") or "").strip(),
            "gender": str(entry.get("gender") or "").strip(),
            "avoid": str(entry.get("avoid") or "").strip(),
        })
    return requests


def voice_target(
    conn: sqlite3.Connection,
    voices: dict[str, Any],
    *,
    character: str,
    preset: str = "",
    gender: str = "",
    avoid: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """Nhân vật sẽ mang giọng và giới nào nếu áp yêu cầu: (đích, None), hoặc (None, mã lý do).

    Dùng chung cho giao diện (từ chối ngay, SQLite chỉ đọc) và dây chuyền (trong transaction áp). `profile` của đích là
    None khi giọng đang có đã đáp ứng yêu cầu - đúng giới, không phải giọng cần tránh, đúng preset đã chọn - nên áp lại
    một yêu cầu đã áp không đổi gì, và máy không đổi giọng một người chỉ vì người khác vừa đổi. Giọng mới luôn là hồ sơ
    bước phân vai sẽ tạo (`character_registry.listener_voice_choice`), nên "một người một giọng" vẫn đúng.
    """
    from .character_registry import listener_voice_choice
    from .voice_catalog import CASTING_REGIONS, EXCLUDED_PRESETS, STYLE_NEWS, VIENEU_PRESETS

    if gender not in ("", "male", "female"):
        return None, BAD_GENDER
    key = " ".join(str(character).strip().casefold().split()).upper()  # = character_registry.canonical_key
    if key == NARRATOR:
        return None, NOT_A_CHARACTER
    row = conn.execute("SELECT id, canonical_name, gender, age, locked FROM characters WHERE canonical_name=?",
                       (key,)).fetchone()
    if row is None:
        return None, UNKNOWN_CHARACTER
    current = conn.execute(
        """
        SELECT v.id, v.voice_key, v.preset_name, COUNT(*) AS lines FROM segments s
        JOIN voice_profiles v ON v.id = s.voice_profile_id
        WHERE s.canonical_character_id=? GROUP BY v.id ORDER BY lines DESC LIMIT 1
        """,
        (int(row["id"]),),
    ).fetchone()
    if current is None:
        return None, NO_VOICE
    castable = {
        str(item["name"]): item for item in VIENEU_PRESETS
        if item["style"] != STYLE_NEWS and item["region"] in CASTING_REGIONS and item["name"] not in EXCLUDED_PRESETS
        and item["name"] not in {str(voices.get("narrator_voice") or ""), *map(str, voices.get("other_narrators", ()))}
    }
    if preset and preset not in castable:
        return None, UNKNOWN_PRESET
    current_gender = str(row["gender"] or "unknown")
    final_gender = gender or current_gender
    current_preset = castable.get(str(current["preset_name"] or ""))
    satisfied = (
        (not preset or preset == str(current["preset_name"]))
        and (not avoid or avoid != str(current["voice_key"]))
        and (not gender or (current_preset is not None and current_preset["gender"] == gender))
    )
    profile = None if satisfied else listener_voice_choice(
        conn, voices, key, gender=final_gender, age=str(row["age"] or "unknown"), preset_name=preset
    )
    if profile is not None and preset:
        final_gender = gender or str(castable[preset]["gender"])
    # Giới chỉ ghim khi người nghe NÓI giới, hay chọn hẳn một giọng (giọng mang giới của nó). "Giữ nguyên" và "tách hai
    # người chung giọng" không nói gì về giới.
    stated = bool(gender) or (profile is not None and bool(preset))
    return {
        "character_id": int(row["id"]),
        "canonical_name": key,
        "gender": final_gender,
        "lock_gender": stated and final_gender in ("male", "female")
                       and (final_gender != current_gender or not row["locked"]),
        "current_voice_key": str(current["voice_key"]),
        "profile": profile,
    }, None


def spoken_problem(original: str, spoken: str) -> str | None:
    """Chữ đem đọc người nghe muốn cho câu có văn bản `original`: None nếu dùng được. Rỗng = trả về đúng chữ của sách."""
    text = spoken.strip()
    if not text:
        return None
    if len(text) > MAX_SPOKEN_CHARS or len(text) > 4 * len(original.strip()) + 40:
        return BAD_TEXT
    if any(ord(character) < 32 for character in text) or not any(character.isalpha() for character in text):
        return BAD_TEXT
    return None


def line_requests(overrides: dict[str, Any]) -> list[dict[str, Any]]:
    """Các yêu cầu sửa cách đọc một câu (loại đoạn, cảm xúc, cường độ, chữ đem đọc), theo thứ tự mã câu. Trường rỗng /
    None = giữ; riêng `spoken`: None = giữ, "" = trả về chữ của sách."""
    entries = overrides.get("lines")
    if not isinstance(entries, dict):
        return []
    requests: list[dict[str, Any]] = []
    for stable_id in sorted(entries):
        entry = entries[stable_id]
        if not isinstance(entry, dict) or not str(entry.get("text_sha256") or "").strip():
            continue
        intensity = entry.get("intensity")
        requests.append({
            "stable_id": str(stable_id),
            "text_sha256": str(entry["text_sha256"]).strip(),
            "kind": str(entry.get("kind") or "").strip(),
            "emotion": str(entry.get("emotion") or "").strip(),
            "intensity": int(intensity) if isinstance(intensity, (int, float)) and not isinstance(intensity, bool) else None,
            "spoken": entry["spoken"] if isinstance(entry.get("spoken"), str) else None,
        })
    return requests


def line_target(
    conn: sqlite3.Connection,
    *,
    stable_id: str,
    text_sha256: str,
    kind: str = "",
    emotion: str = "",
    intensity: int | None = None,
    spoken: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Câu sẽ mang loại đoạn / cảm xúc / cường độ / chữ đem đọc nào nếu áp yêu cầu: (đích, None), hoặc (None, mã lý do).
    Dùng chung cho giao diện (từ chối ngay) và dây chuyền (trong transaction áp).

    Cường độ đi qua ĐÚNG phép hiệu chỉnh của khâu phân tích (`analysis._calibrated_intensity`: cảm xúc êm tối đa 1, lời kể
    và nội tâm tối đa 2, mức 3 chỉ cho cảm xúc mạnh có dấu chấm than) - TTS không đọc được gì ngoài dải ấy. Đổi thành lời
    kể thì câu về người kể và giọng người kể."""
    from .analysis import ALLOWED_EMOTIONS, _calibrated_intensity

    # Sách tạo trước khi có cột chữ đem đọc (giao diện mở DB chưa qua lượt nâng cấp của dây chuyền): coi như chưa sửa.
    has_spoken = any(str(row[1]) == "listener_text" for row in conn.execute("PRAGMA table_info(segments)"))
    line = conn.execute(
        "SELECT id, chapter_id, text, kind, speaker, emotion, intensity, status, text_sha256, voice_profile_id,"
        f" canonical_character_id, {'listener_text' if has_spoken else 'NULL AS listener_text'} FROM segments"
        " WHERE stable_id=?",
        (stable_id,),
    ).fetchone()
    if line is None:
        return None, UNKNOWN_LINE
    if str(line["text_sha256"] or "") != text_sha256:
        return None, SOURCE_CHANGED
    if kind and kind not in LINE_KINDS:
        return None, BAD_KIND
    if emotion and emotion not in ALLOWED_EMOTIONS:
        return None, BAD_EMOTION
    if spoken is not None and spoken_problem(str(line["text"]), spoken) is not None:
        return None, BAD_TEXT
    listener_text = line["listener_text"] if spoken is None else (" ".join(spoken.split()) or None)
    if listener_text == str(line["text"]).strip():
        listener_text = None  # sửa về đúng chữ của sách = không sửa
    new_kind = kind or str(line["kind"] or "narration")
    new_emotion = emotion or str(line["emotion"] or "neutral")
    wanted = intensity if intensity is not None else int(line["intensity"] or 0)
    target: dict[str, Any] = {
        "line": line,
        "kind": new_kind,
        "emotion": new_emotion,
        "intensity": _calibrated_intensity(str(line["text"]), new_kind, new_emotion, wanted),
        "listener_text": listener_text,
    }
    if new_kind == "narration" and str(line["kind"]) != "narration":
        narrator = conn.execute(
            """
            SELECT c.id AS character_id, s.voice_profile_id, COUNT(*) AS lines FROM segments s
            JOIN characters c ON c.id = s.canonical_character_id
            WHERE c.canonical_name='NARRATOR' AND s.voice_profile_id IS NOT NULL
            GROUP BY c.id, s.voice_profile_id ORDER BY lines DESC LIMIT 1
            """
        ).fetchone()
        if narrator is None:
            return None, NO_VOICE
        target["narrator"] = {"character_id": int(narrator["character_id"]),
                              "voice_profile_id": int(narrator["voice_profile_id"])}
    return target, None


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


def request_speaker(project_root: Path, stable_id: str, text_sha256: str, speaker: str, *, now: float,
                    new_gender: str = "") -> None:
    """Giao diện gọi: ghi (hoặc thay) mong muốn cho một câu. Băm chữ đi kèm để yêu cầu tự rơi khi câu đổi chữ."""
    request_speakers(project_root, [(stable_id, text_sha256)], speaker, now=now, new_gender=new_gender)


def request_speakers(project_root: Path, lines: list[tuple[str, str]], speaker: str, *, now: float,
                     new_gender: str = "") -> None:
    """Một người cho cả nhóm câu (mọi câu của một vai phụ không tên), trong MỘT lần ghi file: dây chuyền đọc file giữa
    hai lần ghi thì không bao giờ thấy nhóm câu nửa đã gán nửa chưa."""
    data = read_overrides(project_root)
    entries = data.get("speakers")
    entries = dict(entries) if isinstance(entries, dict) else {}
    for stable_id, text_sha256 in lines:
        entries[str(stable_id)] = {
            "speaker": str(speaker).strip(),
            "text_sha256": str(text_sha256).strip(),
            "requested_at": float(now),
        }
        if new_gender in NEW_CHARACTER_GENDERS:
            # Người nghe tạo người này (chưa có giọng): giới để bước áp chọn giọng như bước phân vai.
            entries[str(stable_id)]["new"] = {"gender": new_gender}
    data["speakers"] = entries
    _write(project_root, data)


def request_line(project_root: Path, stable_id: str, text_sha256: str, *, kind: str = "", emotion: str = "",
                 intensity: int | None = None, speaker: str = "", spoken: str | None = None, now: float) -> None:
    """Giao diện gọi: ghi mong muốn về cách đọc một câu, và - khi câu từ lời kể thành lời thoại - người nói của nó, trong
    MỘT lần ghi file (dây chuyền không bao giờ thấy nửa yêu cầu). Gộp với mong muốn cũ của câu: sửa chữ đem đọc không xoá
    cảm xúc vừa chọn mà dây chuyền chưa kịp áp, và ngược lại."""
    data = read_overrides(project_root)
    lines = data.get("lines")
    lines = dict(lines) if isinstance(lines, dict) else {}
    previous = lines.get(str(stable_id))
    previous = previous if isinstance(previous, dict) and previous.get("text_sha256") == str(text_sha256).strip() else {}
    entry = {
        "text_sha256": str(text_sha256).strip(),
        "kind": str(kind).strip() or str(previous.get("kind") or ""),
        "emotion": str(emotion).strip() or str(previous.get("emotion") or ""),
        "intensity": intensity if intensity is not None else previous.get("intensity"),
        "requested_at": float(now),
    }
    if spoken is not None:
        entry["spoken"] = " ".join(str(spoken).split())
    elif isinstance(previous.get("spoken"), str):
        entry["spoken"] = previous["spoken"]
    lines[str(stable_id)] = entry
    data["lines"] = lines
    if speaker:
        speakers = data.get("speakers")
        speakers = dict(speakers) if isinstance(speakers, dict) else {}
        speakers[str(stable_id)] = {"speaker": str(speaker).strip(), "text_sha256": str(text_sha256).strip(),
                                    "requested_at": float(now)}
        data["speakers"] = speakers
    _write(project_root, data)


def request_voice(project_root: Path, character: str, *, preset: str = "", gender: str = "", avoid: str = "",
                  now: float) -> None:
    """Giao diện gọi: ghi (hoặc thay) mong muốn về giọng/giới của một nhân vật."""
    data = read_overrides(project_root)
    entries = data.get("voices")
    entries = dict(entries) if isinstance(entries, dict) else {}
    entries[" ".join(str(character).strip().casefold().split()).upper()] = {
        "preset": str(preset).strip(),
        "gender": str(gender).strip(),
        "avoid": str(avoid).strip(),
        "requested_at": float(now),
    }
    data["voices"] = entries
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
