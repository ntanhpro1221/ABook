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

from .. import names as renames
from . import store
from .humanize import voice_label
from .reviews import speaker_label

# Giọng nghe thử là dữ liệu của Studio (studio_setup.ASSET_PATHS): bộ cài chỉ-nghe không mang. Máy chưa cài Studio thì
# giọng vẫn liệt kê được nhưng không có nút nghe thử (giao diện ẩn nút khi `preview` là False).
VOICE_PREVIEW_DIR = Path(__file__).resolve().parents[1] / "assets" / "voice_previews"
GENDER_LABELS = {"male": "Nam", "female": "Nữ"}
STYLE_LABELS = {"tu_nhien": "Tự nhiên", "doc_truyen": "Kể chuyện"}


def preview_file(preset_name: str) -> Path | None:
    """File nghe thử của một giọng; None khi giọng không có bản nghe thử hay máy này chưa có dữ liệu của Studio."""
    from ..voice_catalog import VOICE_PREVIEW_FILENAMES

    filename = VOICE_PREVIEW_FILENAMES.get(preset_name)
    path = VOICE_PREVIEW_DIR / filename if filename else None
    return path if path is not None and path.is_file() else None


def _key(name: str) -> str:
    return " ".join(str(name).strip().casefold().split()).upper()


def voice_choices(project_root: Path, character: str) -> dict[str, Any] | None:
    from ..character_registry import listener_voice_choice
    from ..config import build_settings
    from ..voice_catalog import casting_presets

    stored = store.read_settings(project_root).get("voices")
    voices = {**build_settings()["voices"], **(stored if isinstance(stored, dict) else {})}
    not_for_characters = {str(voices.get("narrator_voice") or ""), *map(str, voices.get("other_narrators", ()))}
    key = _key(character)
    renamed = renames.load(project_root)

    def shown(who: str) -> str:
        """Tên người nghe đã "Đổi tên" (tab Nhân vật) thay tên gốc; khoá `value` giữ nguyên."""
        return renamed.get(renames.name_key(who)) or speaker_label(who)

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
        book_row = connection.execute("SELECT updated_at FROM book WHERE id=1").fetchone()
    pending = _pending_request(project_root, key, suggested,
                               float(book_row["updated_at"] or 0) if book_row is not None else 0.0)
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
                    {"label": shown(who), "chapters": len(chapters.get(who, set()) & mine)}
                    for who in others if chapters.get(who, set()) & mine
                ),
                key=lambda item: (-item["chapters"], item["label"].casefold()),
            )
            entries.append({
                "name": voice_label(name),
                "gender": gender,
                "genderLabel": GENDER_LABELS[gender],
                "region": str(preset["region"]),
                "style": STYLE_LABELS.get(str(preset["style"]), str(preset["style"])),
                "preview": preview_file(name) is not None,
                "current": name == current,
                "pending": pending is not None and pending["preset"] == name,
                "suggested": suggested.get(gender) == name,
                "sharedWith": shared[:4],
                "otherUsers": len(others) - min(len(shared), 4),
            })
    return {
        "character": {
            "value": key,
            # Vai phụ cục bộ mang tên sổ "NPC người gác": người đọc thấy "người gác" (speaker_label của khoá).
            "label": renamed.get(renames.name_key(key))
            or (speaker_label(key) if key.startswith("NPC_LOCAL") or not row["display_name"] else str(row["display_name"])),
            "gender": str(row["gender"] or "unknown"),
            "lines": lines,
            "chapters": len(mine),
        },
        "current": voice_label(current),
        # Lựa chọn chưa vào sách: hộp đánh dấu nó và cho giữ giọng đang dùng (bỏ yêu cầu) - soát UX 30-09: lỡ 8 giây
        # "Hoàn tác" thì không còn đường nào bỏ lựa chọn.
        "pending": None if pending is None else {
            "name": voice_label(pending["preset"]) if pending["preset"] else "",
            "requestedAt": pending["requestedAt"],
        },
        "voices": entries,
    }


def _pending_request(project_root: Path, key: str, suggested: dict[str, str], written_at: float) -> dict[str, Any] | None:
    """Yêu cầu giọng/giới của nhân vật này ghi SAU lần dây chuyền ghi sổ cuối (như store.pending_voices), kèm giọng gốc nó
    sẽ thành: giọng đã chọn, hay giọng máy chọn cho giới đã chọn (thẻ "Nam hay nữ"); "tránh trùng giọng" thì chưa biết."""
    from ..listener_overrides import read_overrides

    entries = read_overrides(project_root).get("voices")
    entry = entries.get(key) if isinstance(entries, dict) else None
    if not isinstance(entry, dict):
        return None
    try:
        requested_at = float(entry.get("requested_at") or 0)
    except (TypeError, ValueError):
        return None
    if requested_at <= store.changes_since(project_root, written_at):
        return None
    preset = str(entry.get("preset") or "")
    gender = str(entry.get("gender") or "")
    if not (preset or gender or entry.get("avoid")):
        return None
    return {"preset": preset or suggested.get(gender, ""), "requestedAt": requested_at}
