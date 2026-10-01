"""Rãnh nhạc nền của một cuốn sách - như rãnh phụ đề của video (chủ sách 01-10): danh sách đoạn (chương, câu đầu-cuối, mốc
thời gian), không khí của từng đoạn, bài nhạc cho đoạn ấy (hay im lặng), kèm ghi công từng bài.

Hai file trong thư mục dự án, KHÔNG phải sổ của dây chuyền (sửa nhạc không bao giờ phải đọc lại giọng):
    music_plan.json        máy dựng (`build`) - dựng lại bao nhiêu lần cũng được
    music_overrides.json   lựa chọn của NGƯỜI DÙNG - bật/tắt, phong cách, âm lượng, bài ghim cho từng đoạn, bài đã bỏ;
                           máy dựng lại luôn tôn trọng file này (như sửa cách đọc tên, giọng nhân vật)

Đây là ĐƯỜNG CƠ SỞ (docs/MUSIC_RESEARCH.md): chia đoạn, chọn bài, âm lượng sẽ đổi theo kết quả nghiên cứu - định dạng
hai file giữ ổn định để lựa chọn của người dùng không mất khi thuật toán đổi.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from ..io_utils import atomic_write_json
from . import music_scenes, music_select, store

PLAN_FILE = "music_plan.json"
OVERRIDES_FILE = "music_overrides.json"
PLAN_VERSION = 1
DEFAULT_LEVEL_DB = -20.0  # nền thấp hơn giọng ~20 dB (đường cơ sở - Pha 4 đo lại bằng Whisper)
FAMILIES = ("eastern", "orchestral", "piano", "ambient", "acoustic", "electronic", "other")


def read_overrides(project_root: Path) -> dict[str, Any]:
    try:
        value = json.loads((Path(project_root) / OVERRIDES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    return {
        "enabled": bool(value.get("enabled", True)),  # mặc định BẬT (chủ sách 01-10)
        "family": value.get("family") if value.get("family") in FAMILIES else None,
        # Thế giới của cuốn (bảng thể loại x phong cách trong danh mục nhạc) - lọc phong cách cứng; None = chưa chọn.
        "genre": str(value["genre"])[:40] if isinstance(value.get("genre"), str) and value.get("genre") else None,
        "levelDb": float(value["levelDb"]) if isinstance(value.get("levelDb"), (int, float)) else DEFAULT_LEVEL_DB,
        "pins": {str(k): str(v) for k, v in (value.get("pins") or {}).items() if isinstance(v, str) and v},
        "silenced": sorted({str(k) for k in value.get("silenced") or []}),
        "banned": sorted({str(link) for link in value.get("banned") or []}),
    }


def write_overrides(project_root: Path, changes: dict[str, Any]) -> dict[str, Any]:
    """Gộp thay đổi của người dùng vào music_overrides.json. `pins`: {khoá đoạn: link hay None (bỏ ghim)};
    `silence`: {khoá đoạn: True/False}; `ban` / `unban`: link."""
    current = read_overrides(project_root)
    if "enabled" in changes:
        current["enabled"] = bool(changes["enabled"])
    if "family" in changes:
        current["family"] = changes["family"] if changes["family"] in FAMILIES else None
    if "genre" in changes:
        current["genre"] = str(changes["genre"])[:40] if changes.get("genre") else None
    if "levelDb" in changes:
        current["levelDb"] = max(-40.0, min(-6.0, float(changes["levelDb"])))
    for key, link in (changes.get("pins") or {}).items():
        if link:
            current["pins"][str(key)] = str(link)
        else:
            current["pins"].pop(str(key), None)
    silenced = set(current["silenced"])
    for key, on in (changes.get("silence") or {}).items():
        (silenced.add if on else silenced.discard)(str(key))
    current["silenced"] = sorted(silenced)
    banned = set(current["banned"])
    banned.update(str(link) for link in changes.get("ban") or [])
    banned.difference_update(str(link) for link in changes.get("unban") or [])
    current["banned"] = sorted(banned)
    atomic_write_json(Path(project_root) / OVERRIDES_FILE, current)
    return current


def book_scripts(project_root: Path) -> Iterable[dict[str, Any]]:
    for chapter in store.chapters(project_root):
        script = store.chapter_script(project_root, int(chapter["id"]))
        if script and script.get("segments"):
            yield script


def build(project_root: Path, candidates_near: Callable[[float, float], Iterable[dict[str, Any]]],
          lookup: Callable[[list[str]], dict[str, dict[str, Any]]], *, catalog_revision: str | None = None,
          book_key: str | None = None, taxonomy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dựng lại music_plan.json: chia đoạn cả cuốn, chọn bài theo lựa chọn của người dùng, gắn thông tin bài."""
    project_root = Path(project_root)
    overrides = read_overrides(project_root)
    scenes = music_scenes.book_scenes(book_scripts(project_root))
    genres = (taxonomy or {}).get("genres") or {}
    genre_styles = (genres.get(overrides["genre"]) or {}).get("styles") if overrides["genre"] else None
    chosen = music_select.choose(scenes, candidates_near, book_key=book_key or project_root.name,
                                 family=overrides["family"], pins=overrides["pins"], banned=overrides["banned"],
                                 genre_styles=genre_styles)
    silenced = set(overrides["silenced"])
    for scene in chosen:
        if scene["key"] in silenced:
            scene.update(link=None, silenced=True)
    links = sorted({scene["link"] for scene in chosen if scene.get("link")})
    tracks = lookup(links) if links else {}
    plan = {
        "version": PLAN_VERSION,
        "built": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "catalogRevision": catalog_revision,
        "enabled": overrides["enabled"],
        "levelDb": overrides["levelDb"],
        "family": overrides["family"],
        "genre": overrides["genre"],
        "scenes": chosen,
        "tracks": {link: {key: tracks.get(link, {}).get(key) for key in
                          ("title", "creator", "license", "licenseUrl", "attribution", "duration", "source", "landing")}
                   for link in links},
    }
    atomic_write_json(project_root / PLAN_FILE, plan)
    return plan


def read_plan(project_root: Path) -> dict[str, Any] | None:
    try:
        plan = json.loads((Path(project_root) / PLAN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return plan if isinstance(plan, dict) and plan.get("version") == PLAN_VERSION else None


def chapter_cues(plan: dict[str, Any], chapter_id: int) -> list[dict[str, Any]]:
    """Nhạc của một chương cho trình phát: [{start, end, link, key}] theo thời gian trong MP3 chương (đoạn im lặng thì
    không có). Hai đoạn liền nhau cùng bài gộp làm một - bài chơi liền, không bắt đầu lại."""
    if not plan.get("enabled"):
        return []
    cues: list[dict[str, Any]] = []
    for scene in plan.get("scenes") or []:
        if scene.get("chapterId") != chapter_id or not scene.get("link"):
            continue
        if cues and cues[-1]["link"] == scene["link"] and abs(cues[-1]["end"] - float(scene["start"])) < 5:
            cues[-1]["end"] = float(scene["end"])
            continue
        cues.append({"start": float(scene["start"]), "end": float(scene["end"]), "link": scene["link"],
                     "key": scene["key"]})
    return cues
