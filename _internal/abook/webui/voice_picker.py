"""Màn "Đổi giọng" của một nhân vật trong Studio (tab Nhân vật): mọi giọng dùng được cho nhân vật, kèm những gì người nghe
cần để chọn - giọng đang dùng, giọng máy sẽ chọn cho từng giới, giọng nào đang có người khác dùng và cùng mấy chương, có
nghe thử không.

Chọn xong đi đúng đường của thẻ "Nam hay nữ" (POST /voice -> overrides.json `voices` -> `ProjectDB.apply_listener_voice`
ở ranh giới chương), nên bậc giọng vẫn do bộ cấp giọng của bước phân vai quyết (không trùng bậc với người cùng chương).
SQLite mở chỉ đọc như mọi phần của webui.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
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
STYLE_LABELS = {"tu_nhien": "Tự nhiên", "doc_truyen": "Kể chuyện", "tin_tuc": "Tin tức"}


def preview_file(preset_name: str) -> Path | None:
    """File nghe thử của một giọng; None khi giọng không có bản nghe thử hay máy này chưa có dữ liệu của Studio."""
    from ..voice_catalog import VOICE_PREVIEW_FILENAMES

    filename = VOICE_PREVIEW_FILENAMES.get(preset_name)
    path = VOICE_PREVIEW_DIR / filename if filename else None
    return path if path is not None and path.is_file() else None


def engine_module_status(engine: str) -> dict[str, Any]:
    """Mô-đun tải thêm của một máy đọc khác, cùng một hình cho hộp "Đổi giọng": state / done / total / error / bytes còn thiếu.

    ZeroTTS là mô-đun của Studio (zerotts_module). Supertonic dùng lại đúng mô-đun "Giọng Supertonic" của Nghe ngay
    (supertonic_module) - một bản tải cho cả hai nơi; trạng thái của nó có thêm phần lựa chọn, ở đây chỉ lấy cái hộp cần."""
    from . import supertonic_module, zerotts_module

    if engine == "zerotts":
        return zerotts_module.status()
    if engine == "supertonic":
        full = supertonic_module.status()
        state = full["state"] if full["state"] != "unsupported" or not full["reason"] else "unsupported"
        return {"state": state, "done": full["done"], "total": full["total"],
                "error": full["error"] or (full["reason"] if state == "unsupported" else ""),
                "bytes": sum(int(choice["bytes"]) for choice in full["choices"]),
                "cancelled": bool(full["cancelled"]), "cancellable": state == "downloading"}
    raise ValueError(f"Không có máy đọc {engine!r}")


def engine_installed(engine: str) -> bool:
    """Giọng của máy đọc này đã dùng được trên máy (VieNeu: luôn - Studio mang sẵn)."""
    from . import supertonic_module, zerotts_module

    if engine == "zerotts":
        return zerotts_module.installed() is not None
    if engine == "supertonic":
        return supertonic_module.installed() is not None
    return True


def start_engine_module(engine: str) -> dict[str, Any]:
    """Người nghe bấm "Tải giọng" ở hộp "Đổi giọng": tải phần còn thiếu / đã cũ ở luồng nền."""
    from . import supertonic_module, zerotts_module

    if engine == "zerotts":
        zerotts_module.start()
    elif engine == "supertonic":
        supertonic_module.start([supertonic_module.CHOICE])
    else:
        raise ValueError(f"Không có máy đọc {engine!r}")
    return engine_module_status(engine)


def cancel_engine_module(engine: str) -> dict[str, Any]:
    """Người nghe bấm "Huỷ" khi hộp "Đổi giọng" đang tải giọng: dừng giữa chừng, phần đã tải giữ để lần sau làm tiếp."""
    from . import supertonic_module, zerotts_module

    if engine == "zerotts":
        zerotts_module.cancel()
    elif engine == "supertonic":
        supertonic_module.cancel()
    else:
        raise ValueError(f"Không có máy đọc {engine!r}")
    return engine_module_status(engine)


def _key(name: str) -> str:
    return " ".join(str(name).strip().casefold().split()).upper()


def _once(labels: list[str]) -> list[str]:
    """Mỗi tên một lần, không kể hoa thường, giữ thứ tự."""
    seen: set[str] = set()
    return [label for label in labels if not (label.casefold() in seen or seen.add(label.casefold()))]


def _shown_names(connection: Any, project_root: Path) -> Callable[[str], str]:
    """Tên một nhân vật như hàng của nó ở tab Nhân vật (store.cast): tên người nghe đã "Đổi tên", không thì tên sổ viết
    (`display_name`) - không phải khoá chuẩn viết HOA rồi viết hoa từng chữ ("Áo Choàng Đen", soát UX a24)."""
    renamed = renames.load(project_root)
    display = {str(row[0]): str(row[1] or "") for row in connection.execute("SELECT canonical_name, display_name FROM characters")}

    def shown(who: str) -> str:
        return renamed.get(renames.name_key(who)) or speaker_label(display.get(who) or who)

    return shown


def voice_choices(project_root: Path, character: str) -> dict[str, Any] | None:
    from ..character_registry import listener_voice_choice
    from ..listener_overrides import narrated_voices
    from ..voice_catalog import ENGINE_LABELS, ENGINE_VIENEU, castable_engine_voices, casting_presets
    from .reading_preview import PreviewError, character_line, line_text

    key = _key(character)
    if key == "NARRATOR":
        return narrator_choices(project_root)
    renamed = renames.load(project_root)

    with closing(store.connect(project_root)) as connection:
        shown = _shown_names(connection, project_root)  # khoá `value` giữ nguyên
        # Giọng người kể ĐANG đọc (người nghe có thể đã đổi) cũng không dành cho nhân vật.
        voices = narrated_voices(connection, store.book_voices(project_root))
        not_for_characters = {str(voices.get("narrator_voice") or ""), *map(str, voices.get("other_narrators", ()))}
        row = connection.execute(
            "SELECT id, canonical_name, display_name, gender, age FROM characters WHERE canonical_name=?", (key,)
        ).fetchone()
        if row is None:
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
        # Câu "Nghe thử bằng câu của sách" sẽ đọc (reading_preview.character_line); None: chỉ có bản nghe thử chung.
        try:
            line = character_line(connection, key)
            try_line = {"segmentId": int(line["id"]), "text": line_text(line)}
        except PreviewError:
            try_line = None
        # Đổi giọng là thu lại mọi câu ĐÃ THU của người ấy (như hộp "Áp dụng" - store.pending_details), theo tốc độ của cuốn.
        recorded = int(connection.execute(
            "SELECT COUNT(*) FROM segments WHERE canonical_character_id=? AND wav_path IS NOT NULL AND wav_path <> ''",
            (int(row["id"]),)).fetchone()[0])
        each, measured = store.seconds_per_line(connection)
    pending = _pending_request(project_root, key, suggested,
                               float(book_row["updated_at"] or 0) if book_row is not None else 0.0)
    mine = chapters.get(key, set())
    # Ý muốn chưa áp cũng giữ giọng (soát UX a24, A2): người khác đã chọn hẳn giọng này thì cũng là "cùng giọng"; giọng người
    # kể đang chờ đổi sang thì nhân vật không chọn được (POST /voice từ chối đúng như vậy - store.voice_request_problem).
    wished = store.wished_presets(project_root)
    for name, people in wished.items():
        presets_of[name].update(who for who in people if who != "NARRATOR")
    # Máy đọc khác chỉ chọn được khi máy này đã tải giọng của nó (mô-đun tải thêm); chưa tải thì hộp mời tải.
    engines = sorted({str(voice["engine"]) for voice in castable_engine_voices()})
    installed = {ENGINE_VIENEU: True, **{engine: engine_installed(engine) for engine in engines}}
    entries = []
    for gender in ("male", "female"):
        for preset in [*casting_presets(gender), *castable_engine_voices(gender)]:
            name = str(preset["name"])
            if name in not_for_characters:
                continue
            engine = str(preset.get("engine", ENGINE_VIENEU))
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
                "engine": engine,
                "engineLabel": ENGINE_LABELS.get(engine, engine),
                "installed": bool(installed.get(engine)),
                # Giọng máy khác chỉ có một bậc âm sắc: hai người chung giọng ấy nghe như một.
                "oneStep": engine != ENGINE_VIENEU,
                "description": str(preset["description"]) if engine != ENGINE_VIENEU else "",
                "gender": gender,
                "genderLabel": GENDER_LABELS[gender],
                "region": str(preset["region"]),
                "style": STYLE_LABELS.get(str(preset["style"]), str(preset["style"])),
                "preview": preview_file(name) is not None,
                "current": name == current,
                "pending": pending is not None and pending["preset"] == name,
                # Giọng người kể đang chờ đổi sang thì không chọn được - không gắn "Máy gợi ý" lên nó.
                "suggested": suggested.get(gender) == name and "NARRATOR" not in wished.get(name, ()),
                "sharedWith": shared[:4],
                "otherUsers": len(others) - min(len(shared), 4),
                **({"takenBy": ["Người kể"], "takenNote": "Bạn đã chọn giọng này cho người kể (chờ áp dụng) - nhân vật cần"
                    " giọng khác"} if "NARRATOR" in wished.get(name, ()) and name != current else {}),
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
        "tryLine": try_line,
        "rerecord": {"lines": recorded, "seconds": round(recorded * each, 1), "measured": measured},
        # Mô-đun tải thêm của máy đọc khác (engine_module_status): hộp hiện nút tải và tiến độ.
        "modules": {engine: engine_module_status(engine) for engine in engines},
    }


def narrator_choices(project_root: Path) -> dict[str, Any] | None:
    """Hộp "Đổi giọng" của hàng "Người kể" (soát UX a23, B21): mọi giọng kể chuyện của danh mục (như trình tạo sách), cùng hình
    với hộp của nhân vật. Giọng một nhân vật đang giữ thì không chọn được (`takenBy`: của ai) - người kể không bao giờ trùng
    giọng nhân vật (`listener_overrides._narrator_target` từ chối đúng như vậy). Đổi là thu lại mọi câu ĐÃ THU đọc bằng giọng
    người kể (`listener_overrides.narrator_voiced`). None khi sách chưa phân vai (chưa có giọng người kể để đổi)."""
    from ..listener_overrides import NARRATOR, character_presets, narrator_profile, narrator_voiced
    from ..voice_catalog import ENGINE_LABELS, ENGINE_VIENEU, narrator_presets
    from .reading_preview import PreviewError, character_line, line_text

    with closing(store.connect(project_root)) as connection:
        shown = _shown_names(connection, project_root)
        profile = narrator_profile(connection)
        narrator = connection.execute("SELECT id FROM characters WHERE canonical_name=?", (NARRATOR,)).fetchone()
        if profile is None or narrator is None:
            return None
        current = str(profile["preset_name"] or "")
        held = character_presets(connection)
        rows = connection.execute(
            "SELECT chapter_id, kind, speaker, voice_profile_id, canonical_character_id, wav_path FROM segments").fetchall()
        recorded = sum(1 for row in rows if row["wav_path"] and narrator_voiced(row, int(profile["id"])))
        mine = [row for row in rows if row["canonical_character_id"] == int(narrator["id"])]
        try:
            line = character_line(connection, NARRATOR)
            try_line = {"segmentId": int(line["id"]), "text": line_text(line)}
        except PreviewError:
            try_line = None
        book_row = connection.execute("SELECT updated_at FROM book WHERE id=1").fetchone()
        each, measured = store.seconds_per_line(connection)
    pending = _pending_request(project_root, NARRATOR, {}, float(book_row["updated_at"] or 0) if book_row is not None else 0.0)
    # Nhân vật đã chọn hẳn giọng ấy mà chưa áp cũng giữ nó (soát UX a24, A2) - nói rõ là đang chờ.
    waiting = {name: [who for who in people if who != NARRATOR and who not in held.get(name, ())]
               for name, people in store.wished_presets(project_root).items()}

    entries = []
    for preset in narrator_presets():
        name = str(preset["name"])
        gender = str(preset["gender"])
        entries.append({
            "name": voice_label(name), "engine": ENGINE_VIENEU, "engineLabel": ENGINE_LABELS.get(ENGINE_VIENEU, ENGINE_VIENEU),
            "installed": True, "oneStep": False, "description": "",
            "gender": gender, "genderLabel": GENDER_LABELS.get(gender, ""), "region": str(preset["region"]),
            "style": STYLE_LABELS.get(str(preset["style"]), str(preset["style"])),
            "preview": preview_file(name) is not None,
            "current": name == current,
            "pending": pending is not None and pending["preset"] == name,
            "suggested": False, "sharedWith": [], "otherUsers": 0,
            # Hai khoá cùng một tên hiện ("Lính gác 1" ở hai chương, "lính gác 1" của vai phụ một cảnh) chỉ ghi một lần.
            "takenBy": _once(sorted((shown(who) for who in held.get(name, ())), key=str.casefold)
                             + sorted((f"{shown(who)} (chờ áp dụng)" for who in waiting.get(name, ())), key=str.casefold)),
        })
    return {
        "character": {"value": NARRATOR, "label": "Người kể", "gender": next(
            (str(preset["gender"]) for preset in narrator_presets() if preset["name"] == current), "unknown"),
            "lines": len(mine), "chapters": len({int(row["chapter_id"]) for row in mine})},
        "current": voice_label(current),
        "pending": None if pending is None else {"name": voice_label(pending["preset"]), "requestedAt": pending["requestedAt"]},
        "voices": entries,
        "tryLine": try_line,
        "rerecord": {"lines": recorded, "seconds": round(recorded * each, 1), "measured": measured},
        "modules": {},
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
