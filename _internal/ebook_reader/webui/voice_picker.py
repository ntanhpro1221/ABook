"""Màn "Đổi giọng" của một nhân vật trong Studio (tab Nhân vật): mọi giọng dùng được cho nhân vật, kèm những gì người nghe
cần để chọn - giọng đang dùng, giọng máy sẽ chọn cho từng giới, giọng nào đang có người khác dùng và cùng mấy chương, có
nghe thử không.

Chọn xong đi đúng đường của thẻ "Nam hay nữ" (POST /voice -> overrides.json `voices` -> `ProjectDB.apply_listener_voice`
ở ranh giới chương), nên bậc giọng vẫn do bộ cấp giọng của bước phân vai quyết (không trùng bậc với người cùng chương).
SQLite mở chỉ đọc như mọi phần của webui.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from . import store
from .reviews import speaker_label

GENDER_LABELS = {"male": "Nam", "female": "Nữ"}
STYLE_LABELS = {"tu_nhien": "Tự nhiên", "doc_truyen": "Kể chuyện"}


def _key(name: str) -> str:
    return " ".join(str(name).strip().casefold().split()).upper()


def voice_choices(project_root: Path, character: str) -> dict[str, Any] | None:
    from ..character_registry import listener_voice_choice
    from ..config import build_settings
    from ..voice_catalog import VOICE_PREVIEW_FILENAMES, casting_presets

    stored = store.read_settings(project_root).get("voices")
    voices = {**build_settings()["voices"], **(stored if isinstance(stored, dict) else {})}
    not_for_characters = {str(voices.get("narrator_voice") or ""), *map(str, voices.get("other_narrators", ()))}
    key = _key(character)
    with closing(store.connect(project_root)) as connection:
        row = connection.execute(
            "SELECT id, canonical_name, display_name, gender, age FROM characters WHERE canonical_name=?", (key,)
        ).fetchone()
        if row is None or key == "NARRATOR":
            return None
        chapters: dict[str, set[int]] = defaultdict(set)
        presets_of: dict[str, set[str]] = defaultdict(set)
        lines = 0
        current = ""
        for segment in connection.execute(
            """
            SELECT c.canonical_name, s.chapter_id, v.preset_name FROM segments s
            JOIN characters c ON c.id = s.canonical_character_id
            JOIN voice_profiles v ON v.id = s.voice_profile_id
            WHERE c.canonical_name <> 'NARRATOR'
            """
        ):
            who = str(segment["canonical_name"])
            chapters[who].add(int(segment["chapter_id"]))
            presets_of[str(segment["preset_name"] or "")].add(who)
            if who == key:
                lines += 1
                current = str(segment["preset_name"] or "")
        if not lines:
            return None
        age = str(row["age"] or "unknown")
        # Giọng máy sẽ chọn cho từng giới - đúng phép của thẻ "Nam hay nữ", mọi người khác giữ giọng.
        suggested = {
            gender: str(listener_voice_choice(connection, voices, key, gender=gender, age=age)["preset_name"])
            for gender in ("male", "female")
        }
    mine = chapters.get(key, set())
    entries = []
    for gender in ("male", "female"):
        for preset in casting_presets(gender):
            name = str(preset["name"])
            if name in not_for_characters:
                continue
            # Sách dài thì giọng gốc nào cũng nhiều người dùng, ở các bậc âm sắc khác nhau - điều người nghe cần biết chỉ là
            # ai CÙNG CHƯƠNG với nhân vật này (máy sẽ lấy bậc khác họ); những người còn lại gộp thành một con số.
            others = [who for who in presets_of.get(name, set()) if who != key]
            shared = sorted(
                (
                    {"label": speaker_label(who), "chapters": len(chapters.get(who, set()) & mine)}
                    for who in others if chapters.get(who, set()) & mine
                ),
                key=lambda item: (-item["chapters"], item["label"].casefold()),
            )
            entries.append({
                "name": name,
                "gender": gender,
                "genderLabel": GENDER_LABELS[gender],
                "region": str(preset["region"]),
                "style": STYLE_LABELS.get(str(preset["style"]), str(preset["style"])),
                "preview": bool(VOICE_PREVIEW_FILENAMES.get(name)),
                "current": name == current,
                "suggested": suggested.get(gender) == name,
                "sharedWith": shared[:4],
                "otherUsers": len(others) - min(len(shared), 4),
            })
    return {
        "character": {
            "value": key,
            # Vai phụ cục bộ mang tên sổ "NPC người gác": người đọc thấy "người gác" (speaker_label của khoá).
            "label": speaker_label(key) if key.startswith("NPC_LOCAL") or not row["display_name"]
            else str(row["display_name"]),
            "gender": str(row["gender"] or "unknown"),
            "lines": lines,
            "chapters": len(mine),
        },
        "current": current,
        "voices": entries,
    }
