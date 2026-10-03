"""“Dựng xưởng”: biến một cuốn sách đang chờ xưởng (file `.abookproj` có `workshop: "pending"`) thành một dự án Studio mới.

Điện thoại, hay máy Windows chưa cài Studio, lưu sách thành `.abookproj` mà không có xưởng nào (projectfile.repack): chỉ có
phần nghe + lớp sửa của người nghe. Máy có Studio mở file ấy được một cuốn sách nghe được, và mời “Dựng xưởng”: tạo một dự án
mới rồi gieo vào đó những gì file biết (docs/EDITING.md):

- chữ các chương: `sources/` của file nếu file mang theo (nguyên văn), không thì dựng lại từ `scripts/<chương>.json` (mỗi đoạn
  văn một đoạn, tiêu đề chương là đoạn đầu) - gần nguyên văn, mất chỗ ngắt dòng chưa phải đoạn. Sách CHỈ-CHỮ (textbook.py) thì
  chép nguyên văn `texts/<n>.txt` - chính là file nguồn Studio sẽ đọc, nên "Làm sách nói từ cuốn này" không mất gì;
- giọng từng nhân vật và người kể: khoá `voice.key` trong `cast.json` thành hồ sơ giọng + ghim giọng của dự án (cùng hàm
  `voice_profile_spec` mà bộ cấp giọng dùng, nên giọng ra đúng như cũ) - bộ cấp giọng không đổi giọng người đã ghim;
- tên hiển thị người nghe đã đặt (“Đổi tên”) và tên sách, bìa;
- ý muốn người nghe ghi cho Studio (cách đọc tên, giọng/giới tính, gộp người) thành yêu cầu của dự án qua `book_wishes.fold`;
  ý muốn gắn với một câu cụ thể (đổi người nói, đổi cách đọc câu, thu lại) không còn nghĩa khi chữ được phân tích lại, nên bị
  bỏ qua và đếm.

MẤT (không có trong file): nguồn chương gốc (khi file không mang), lịch sử phân tích, từng câu đã thu, hạt giống, ứng viên,
phán quyết chấp nhận. TOÀN BỘ audio sẽ được làm lại khi chạy - giọng người nghe quen có thể khác chút ở chỗ cách đọc phụ thuộc
phân tích. Cuốn sách nghe được vẫn giữ nguyên, dự án mới là một cuốn riêng.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from .. import names as renames
from . import book_edits, book_wishes, covers, packages
from .library import book_id

SOURCE_FOLDER = "Nguồn dựng xưởng"
BUILT_FILE = "workshop_built.json"
_VOICE_KEY = re.compile(r"preset_.+_f(?P<formant>\d{3})_p(?P<pitch>[+-]\d+)")


class WorkshopError(ValueError):
    """Không dựng được xưởng. Câu chữ để người dùng đọc."""


def built(folder: Path) -> str | None:
    """Mã dự án đã dựng từ cuốn này (`build`), hay None."""
    try:
        value = json.loads((Path(folder) / BUILT_FILE).read_text(encoding="utf-8")).get("id")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value else None


def chapter_text(script: dict[str, Any]) -> str:
    """Chữ một chương dựng lại từ `scripts/<chương>.json`: các đoạn cùng `paragraph` nối bằng dấu cách, đoạn cách nhau một dòng trống."""
    paragraphs: dict[int, list[str]] = {}
    for position, segment in enumerate(script.get("segments") or []):
        text = str(segment.get("text") or "").strip()
        if text:
            number = segment.get("paragraph")
            paragraphs.setdefault(number if isinstance(number, int) else 10_000_000 + position, []).append(text)
    return "\n\n".join(" ".join(parts) for _, parts in sorted(paragraphs.items())) + "\n"


def buildable(folder: Path) -> bool:
    """Cuốn này có thể thành dự án Studio: chờ xưởng (file `.abookproj` không xưởng), hay sách chỉ-chữ (chưa có audio nào)."""
    return packages.workshop_state(folder) == "pending" or packages.text_book(packages.manifest(folder))


def _sources(folder: Path, library_root: Path, title: str) -> tuple[list[str], int]:
    """Viết chữ các chương ra `library_root/Nguồn dựng xưởng/<tên sách>/` (dự án giữ đường dẫn tới chúng). Trả (đường dẫn các file,
    số chương không có chữ). Sách chỉ-chữ: chép `texts/<n>.txt`. Có `sources/` trong thư mục cuốn thì dùng nguyên văn; không thì
    dựng từ kịch bản."""
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", title).strip(" .") or "Sách"
    target = Path(library_root) / SOURCE_FOLDER / f"{' '.join(clean.split())[:80]}"
    n = 2
    while target.exists():
        target = target.with_name(f"{target.name} ({n})")
        n += 1
    target.mkdir(parents=True)
    book = packages.manifest(folder)
    if packages.text_book(book):
        paths = []
        for chapter in sorted(book["chapters"], key=lambda item: (item.get("index") or 0, item.get("id") or 0)):
            text = packages.chapter_text(folder, chapter["id"])
            if text is None:
                continue
            copy = target / f"{int(chapter.get('index') or chapter['id']):05d}.txt"
            copy.write_bytes(text.encode("utf-8"))
            paths.append(str(copy))
        return paths, len(book["chapters"]) - len(paths)
    kept = sorted((folder / "sources").glob("*")) if (folder / "sources").is_dir() else []
    if kept:
        paths = []
        for source in kept:
            copy = target / source.name
            copy.write_bytes(source.read_bytes())
            paths.append(str(copy))
        return paths, 0
    paths, without = [], 0
    for chapter in sorted(book.get("chapters") or [], key=lambda item: (item.get("index") or 0, item.get("id") or 0)):
        script = packages.script(folder, chapter.get("id")) if isinstance(chapter.get("id"), int) else None
        if not isinstance(script, dict) or not script.get("segments"):
            without += 1
            continue
        copy = target / f"{int(chapter.get('index') or chapter['id']):05d}.txt"
        copy.write_bytes(chapter_text(script).encode("utf-8"))
        paths.append(str(copy))
    return paths, without


def _seed_voices(project: Path, cast: dict[str, Any]) -> int:
    """Hồ sơ giọng + ghim giọng của từng nhân vật có `voice.key`. Khoá không dựng lại được đúng từ preset (preset đã đổi tên, khoá lạ)
    thì bỏ qua người ấy - bộ cấp giọng chọn lại, không ai bị ghim vào giọng sai. Trả số nhân vật đã ghim."""
    from ..character_registry import voice_profile_spec
    from ..database import ProjectDB
    from ..voice_catalog import base_pitch_for_preset, preset_by_name
    from . import store

    database = ProjectDB(project / store.DB_NAME)
    seeded = 0
    for person in [*(cast.get("characters") or []), *(cast.get("extras") or [])]:
        voice = person.get("voice") if isinstance(person, dict) else None
        key = str((voice or {}).get("key") or "")
        match = _VOICE_KEY.fullmatch(key)
        name = str(person.get("name") or "").strip() if isinstance(person, dict) else ""
        if not match or not name:
            continue
        try:
            preset = str(voice.get("preset") or "")
            spec = voice_profile_spec(preset_by_name(preset), int(match["formant"]) / 100,
                                      age_pitch=int(match["pitch"]) - base_pitch_for_preset(preset))
        except ValueError:
            continue
        if spec["voice_key"] != key:
            continue
        database.upsert_voice_profile(spec)
        database.set_locked_character_voice(name, key)
        seeded += 1
    return seeded


def build(folder: Path, library_root: Path, create: Callable[[list[str], str, str], Path]) -> dict[str, Any]:
    """Dựng dự án mới từ cuốn đang chờ xưởng ở `folder`. `create(đường dẫn chữ các chương, tên sách, giọng người kể)` là cách tạo
    dự án của app (server.App._create_book - đúng thiết lập mặc định của trình tạo sách). Không chạy gì: dự án vừa tạo, chưa bắt đầu.
    Trả {"project": thư mục, "chapters", "chaptersWithoutText", "voices", "names", "requests", "skipped"}."""
    folder = Path(folder)
    if not buildable(folder):
        raise WorkshopError("Cuốn này không chờ dựng xưởng.")
    if built(folder):
        raise WorkshopError("Xưởng của cuốn này đã dựng rồi.")
    book = packages.edited_manifest(folder)
    title = str(book.get("title") or folder.name)
    cast = packages.cast(folder)
    paths, without = _sources(folder, library_root, title)
    if not paths:
        raise WorkshopError("Cuốn này không có chữ của chương nào để dựng lại - file không mang kịch bản hay nguồn chương.")
    narrator = str((cast.get("narrator") or {}).get("voice") or book.get("narrator") or "")
    project = Path(create(paths, title, narrator))
    voices = _seed_voices(project, cast)
    named = 0
    for person in cast.get("characters") or []:
        shown, original = str(person.get("displayName") or ""), str(person.get("originalName") or "")
        if shown and original and shown != original:
            named += renames.set_name(project, str(person["name"]), shown, original)
    cover = book_edits.cover_file(folder)  # bìa người nghe thấy (bìa họ chọn thắng bìa của người làm sách)
    if cover is not None:
        covers.save_cover_bytes(project, cover.read_bytes())
    folded = book_wishes.fold(project, book_edits.load(folder).get("wishes") or {}, now=time.time())
    (folder / BUILT_FILE).write_text(json.dumps({"id": book_id(project)}), encoding="utf-8")
    return {"project": project, "chapters": len(paths), "chaptersWithoutText": without, "voices": voices, "names": named,
            "requests": folded["requests"], "skipped": folded["skipped"]}
