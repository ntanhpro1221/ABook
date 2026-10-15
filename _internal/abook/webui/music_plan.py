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

import contextlib
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from ..config import DEFAULT_SETTINGS
from ..io_utils import atomic_write_json, ffmpeg_available, ffmpeg_executable, run_hidden
from . import music_bounds, music_mix, music_moods, music_scene_student, music_scenes, music_select, store

PLAN_FILE = "music_plan.json"
OVERRIDES_FILE = "music_overrides.json"
PLAN_VERSION = 1
# Trần đổi bài mỗi giờ của cả cuốn (PLAN_densgate mục 5): ĐỔI BÀI, không phải đoạn - Y có ~31 đoạn/giờ nhưng 21,4 đổi bài/giờ.
# Chỉ đếm và báo (`switches_per_hour`), không đổi hành vi.
SWITCH_CAP_PER_HOUR = 22.0
# `levelDb` = nhạc nền thấp hơn GIỌNG bao nhiêu LU (Pha 4, docs/MUSIC_RESEARCH.md: -20 + bù theo bài -> 94% cặp ESTOI >= 0,9).
DEFAULT_LEVEL_DB = -20.0
VOICE_LUFS = float(DEFAULT_SETTINGS["audio"]["loudness_lufs"])  # giọng mọi chương được chuẩn hoá về mức này
# Chương giọng đọc là file MỘT kênh, chuẩn hoá về VOICE_LUFS đo một kênh; phát ra hai loa / tai nghe thì BS.1770 cộng hai
# kênh giống nhau -> to hơn 3,01 dB. Nhạc đo đúng như lúc phát (hai kênh, `stereo_lufs`), nên mốc giọng cũng tính như lúc phát.
# Số này (= VOICE_LUFS + 10 log10 2) nằm trong music_mix.json, một nguồn cho cả ba bên.
VOICE_PLAYED_LUFS = music_mix.MIX["voicePlayedLufs"]
# Đoạn to nhất của bài (p95 độ to ngắn hạn, `short_term_p95`) vẫn dưới giọng ít nhất chừng này LU (MIX_QA 3.4, Torcoli 2019).
SHORT_TERM_FLOOR_LU = music_mix.MIX["shortTermFloorLu"]
AUDIBLE_THRESHOLD_DBFS = music_mix.MIX["audibleThresholdDbfs"]  # dưới mức này là im: đoạn nghe được của bài (`audible_bounds`)
MEASURE_SIDECAR = ".measure.json"  # số đo của một file bài (`measured_track`), ghi cạnh file
LUFS_SIDECAR = ".lufs2"  # bản cũ chỉ ghi độ to: 2 = đo hai kênh như lúc phát; `.lufs` (trộn xuống một kênh) thấp 0,5-3 dB, bỏ qua
DEFAULT_TRACK_LUFS = -16.6  # trung vị danh mục: bài chưa có `lufs` (plan / danh mục cũ) và chưa có file để đo
MASKING_CENTER = 0.30  # trung vị `speechBand` của danh mục: bài lấn dải tiếng nói hơn mức này thì hạ thêm
MASKING_SLOPE_DB = 8.0
MASKING_LIMIT_DB = 6.0
# Mốc nhạc cuối chương kết muộn nhất chừng này trước khi file giọng hết: mờ 2 s của trình phát + biên đồng bộ 0,5 s.
CHAPTER_END_FADE_SECONDS = music_mix.MIX["chapterEndFadeSeconds"]
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
    newly_banned = {str(link) for link in changes.get("ban") or []}
    banned.update(newly_banned)
    # Bỏ một bài = muốn nó biến khỏi cuốn, kể cả chỗ người dùng từng ghim: ghim trỏ vào bài ấy bị gỡ (đoạn đó chọn lại).
    current["pins"] = {key: link for key, link in current["pins"].items() if link not in newly_banned}
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
          book_key: str | None = None, taxonomy: dict[str, Any] | None = None,
          scenes: list[dict[str, Any]] | None = None,
          keep: dict[str, str | None] | None = None, kept_siblings: dict[str, list[str]] | None = None,
          available: Callable[[str], bool] | None = None, log: Callable[[str], None] | None = None,
          emit: Callable[[str, dict[str, Any]], None] | None = None, persist: bool = True) -> dict[str, Any]:
    """Dựng lại music_plan.json: chia đoạn cả cuốn, chọn bài theo lựa chọn của người dùng, gắn thông tin bài.
    `scenes`: các đoạn đã có (từ plan cũ, qua `scenes_of`) - chọn lại bài trên đúng các đoạn ấy, không chia lại sách;
    người dùng sửa một đoạn thì các đoạn khác không đổi theo (chỉ "Chọn lại nhạc" mới chia lại).
    `keep`: {khoá đoạn: bài cũ} (từ `kept_tracks`) - đoạn nào có trong đó giữ nguyên bài, trừ khi bài đã bị bỏ hoặc không
    còn trong danh mục (không dùng được nữa) thì chọn lại như thường. `kept_siblings` (từ `kept_siblings`): bài anh em cũ của
    các đoạn ấy - đoạn không bị sửa lan thì nối đúng các bài cũ (music_select.choose).
    `available(link)`: bài dùng được trên máy này không (music_select.choose) - bài không lấy được thì đoạn chọn bài kế.
    `log(dòng)` và `emit(loại, nội dung)`: mỗi lần dựng ghi số đổi bài mỗi giờ của cả cuốn; trên `SWITCH_CAP_PER_HOUR` thì phát thêm
    `music_switches_high` {perHour}. Không truyền thì ghi vào nhật ký chạy của dự án (`runtime_events`, như `BookPipeline.log`), dự án
    không có sổ (sách đóng gói) thì vào `logging`. Chỉ đếm, không đổi plan.
    `persist` False: chỉ tính, chưa ghi (người gọi xem plan rồi mới `save_plan`)."""
    project_root = Path(project_root)
    overrides = read_overrides(project_root)
    if scenes is None:
        # Có kết quả LLM đọc cả đoạn (music_moods.py) thì valence / tension của đoạn lấy từ đó; không có thì đường nhãn câu. Có học
        # sinh đoán hình không khí trong chương (music_scene_student.py) thì nó chỉnh tiếp V / E / T quanh mức chương.
        moods = music_moods.load(project_root)
        student = music_scene_student.load(project_root)
        # Ranh giới cảnh do LLM chia (music_bounds.py) nếu có - moods và học sinh dùng cùng ranh, nên khoá đoạn của chúng khớp đoạn ở đây.
        scenes = music_scenes.book_scenes(book_scripts(project_root), moods["scenes"] if moods else None,
                                          boundaries=music_bounds.load(project_root),
                                          student=student["scenes"] if student else None)
    genres = (taxonomy or {}).get("genres") or {}
    genre_styles = (genres.get(overrides["genre"]) or {}).get("styles") if overrides["genre"] else None
    known: dict[str, dict[str, Any]] = {}
    if keep:
        known = lookup(sorted({link for link in keep.values() if link}
                              | {link for links in (kept_siblings or {}).values() for link in links}))
        keep = {key: link for key, link in keep.items() if link is None or link in known}
        kept_siblings = {key: links for key, links in (kept_siblings or {}).items()
                         if key in keep and all(link in known for link in links)}

    def track_info(link: str) -> dict[str, Any] | None:
        return known[link] if link in known else lookup([link]).get(link)

    chosen = music_select.choose(scenes, candidates_near, book_key=book_key or project_root.name,
                                 family=overrides["family"], pins=overrides["pins"], banned=overrides["banned"],
                                 genre_styles=genre_styles, keep=keep, kept_siblings=kept_siblings if keep else None,
                                 available=available,
                                 silenced=overrides["silenced"], track_info=track_info)
    links = sorted({link for scene in chosen for link in [scene.get("link")]
                    + [sibling["link"] for sibling in scene.get("siblings") or []] if link})
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
        "tracks": {link: {key: tracks.get(link, {}).get(key) for key in TRACK_INFO_KEYS} for link in links},
    }
    if persist:
        save_plan(project_root, plan, log, emit)
    return plan


def save_plan(project_root: Path, plan: dict[str, Any], log: Callable[[str], None] | None = None,
              emit: Callable[[str, dict[str, Any]], None] | None = None) -> None:
    """Ghi plan đã tính bằng `build(persist=False)` và báo số đổi bài mỗi giờ."""
    project_root = Path(project_root)
    atomic_write_json(project_root / PLAN_FILE, plan)
    report_switches(plan, log or project_log(project_root), emit or project_emit(project_root))


def record_event(project_root: Path, level: str, code: str, message: str, details: dict[str, Any] | None = None) -> bool:
    """Ghi một dòng vào `runtime_events` của dự án (nhật ký chạy, như `ProjectDB.event`). Dự án không có sổ, sổ khoá hay chưa có bảng
    thì False - người gọi rơi về `logging`. Mở thẳng sqlite, không qua `ProjectDB` (không nâng cấp, không chạm gì khác trong sổ)."""
    path = Path(project_root) / store.DB_NAME
    if not path.is_file():
        return False
    try:
        with contextlib.closing(sqlite3.connect(path, timeout=5.0)) as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_events'").fetchone():
                return False
            with connection:
                connection.execute("INSERT INTO runtime_events(timestamp,level,code,message,details_json) VALUES(?,?,?,?,?)",
                                   (time.time(), level, code, message,
                                    json.dumps(details, ensure_ascii=False) if details else None))
    except sqlite3.Error:
        return False
    return True


def project_log(project_root: Path) -> Callable[[str], None]:
    """`log` của `build` ghi vào nhật ký chạy của dự án (code LOG như `BookPipeline.log`); không ghi được thì `logging`."""
    def log(line: str) -> None:
        if not record_event(project_root, "info", "LOG", line):
            logging.getLogger(__name__).info(line)

    return log


def project_emit(project_root: Path) -> Callable[[str, dict[str, Any]], None]:
    """`emit` của `build` ghi sự kiện vào nhật ký chạy của dự án (code = tên sự kiện); không ghi được thì `logging`."""
    def emit(kind: str, payload: dict[str, Any]) -> None:
        if not record_event(project_root, "warning", kind, f"{kind} {json.dumps(payload, ensure_ascii=False)}", payload):
            logging.getLogger(__name__).warning("%s %s", kind, payload)

    return emit


def switches_per_hour(plan: dict[str, Any]) -> float | None:
    """Đổi bài mỗi giờ của cả cuốn: tổng (số mốc nhạc của chương - 1) / số giờ của các đoạn. Plan tắt hay không có đoạn -> None."""
    if not plan.get("enabled"):
        return None
    chapters: dict[Any, list[dict[str, Any]]] = {}
    for scene in plan.get("scenes") or []:
        chapters.setdefault(scene.get("chapterId"), []).append(scene)
    switches, seconds = 0, 0.0
    for chapter_id, scenes in chapters.items():
        switches += max(0, len(chapter_cues({"enabled": True, "scenes": scenes}, chapter_id)) - 1)
        seconds += max(float(scene["end"]) for scene in scenes) - min(float(scene["start"]) for scene in scenes)
    return switches / (seconds / 3600.0) if seconds > 0 else None


def report_switches(plan: dict[str, Any], log: Callable[[str], None] | None = None,
                    emit: Callable[[str, dict[str, Any]], None] | None = None) -> None:
    """Ghi số đổi bài/giờ của cuốn; trên trần thì phát `music_switches_high`. Chỉ đếm."""
    rate = switches_per_hour(plan)
    if rate is None:
        return
    (log or logging.getLogger(__name__).info)(f"Nhạc nền: {rate:.1f} đổi bài/giờ cả cuốn (trần {SWITCH_CAP_PER_HOUR:.0f})")
    if rate > SWITCH_CAP_PER_HOUR:
        emit = emit or (lambda kind, payload: logging.getLogger(__name__).warning("%s %s", kind, payload))
        emit("music_switches_high", {"perHour": round(rate, 1)})


# Thông tin bài ghi vào plan["tracks"] (ghi công, độ to) - bài thay thế tạm lúc phát cũng mang đúng bộ này.
TRACK_INFO_KEYS = ("title", "creator", "license", "licenseUrl", "attribution", "duration", "source", "landing", "lufs",
                   "speechBand", "s95", "audibleStart", "audibleEnd")
# phần `choose` / `build` gắn thêm cho từng đoạn
CHOICE_FIELDS = ("key", "link", "distance", "pinned", "silenced", "pinUnavailable", "continued", "stepDb", "siblings",
                 "stopAt")


def scenes_of(plan: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Các đoạn của một plan đã dựng, bỏ phần lựa chọn bài (khoá, bài, ghim, im lặng) - để đưa lại cho `build`."""
    scenes = (plan or {}).get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return None
    return [{k: v for k, v in scene.items() if k not in CHOICE_FIELDS} for scene in scenes]


def kept_tracks(plan: dict[str, Any] | None, edited: Iterable[str] = ()) -> dict[str, str | None]:
    """Bài đang chọn của từng đoạn trong plan: {khoá đoạn: link (None = im lặng)}, trừ các đoạn vừa bị sửa (`edited`) - để
    đưa cho `build(keep=...)`: sửa một đoạn / một bài thì các đoạn khác giữ bài cũ. Đoạn người dùng đang để im lặng không
    vào đây (build tự đặt im lặng theo sổ lựa chọn; bỏ im lặng thì đoạn ấy chọn lại)."""
    skip = set(edited)
    return {scene["key"]: scene.get("link") for scene in (plan or {}).get("scenes") or []
            if scene.get("key") and scene["key"] not in skip and not scene.get("silenced")}


def kept_siblings(plan: dict[str, Any] | None, edited: Iterable[str] = ()) -> dict[str, list[str]]:
    """Bài anh em đã nối trong từng đoạn của plan ({khoá đoạn: [link]}), cùng các đoạn với `kept_tracks` - cho
    `build(kept_siblings=...)`."""
    keep = kept_tracks(plan, edited)
    return {scene["key"]: [str(sibling.get("link")) for sibling in scene.get("siblings") or []]
            for scene in (plan or {}).get("scenes") or [] if scene.get("key") in keep}


def read_plan(project_root: Path) -> dict[str, Any] | None:
    try:
        plan = json.loads((Path(project_root) / PLAN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return plan if isinstance(plan, dict) and plan.get("version") == PLAN_VERSION else None


def chapter_cues(plan: dict[str, Any], chapter_id: int, duration: float | None = None) -> list[dict[str, Any]]:
    """Nhạc của một chương cho trình phát: [{start, end, link, key}] theo thời gian trong MP3 chương (đoạn im lặng thì
    không có). Hai đoạn liền nhau cùng bài gộp làm một - bài chơi liền, không bắt đầu lại.
    Bài anh em nối trong cảnh (`siblings` của đoạn, music_select.choose) tách mốc đúng ở điểm kết bài: mốc mới mang
    `sibling: True` (trình phát mờ chéo dài hơn, không nghe như đổi cảnh). Bước âm lượng của các mảnh nối tiếp (`stepDb`) thành
    `steps: [{at, db}]` của mốc - mức (dB, cộng vào `gainDb`) từ giây `at` của chương; mốc bắt đầu ở mức khác 0 thì có bước
    ngay ở `start`.
    Mốc kết đúng ở điểm kết bài đã lập lịch (bài anh em vào ngay sau, hay bài kết sớm ở `stopAt`) mang `tail: True`: trình phát
    thôi lặp ở vòng cuối để bài kết tự nhiên, không quay lại phần dạo đầu. `duration` (giây của chương): mốc kết muộn nhất ở
    `duration - CHAPTER_END_FADE_SECONDS` để nhạc mờ xong trước khi giọng hết; mốc vì thế rỗng thì bỏ."""
    if not plan.get("enabled"):
        return []
    cues: list[dict[str, Any]] = []
    rested = False  # mốc trước kết sớm (`stopAt`): mốc sau dù cùng bài vẫn là bài mở lại sau quãng lặng, không gộp
    for scene in plan.get("scenes") or []:
        if scene.get("chapterId") != chapter_id or not scene.get("link"):
            continue
        level = float(scene.get("stepDb") or 0.0)
        spans = [(float(scene["start"]), scene["link"], False)]
        spans += [(float(sibling["at"]), sibling["link"], True) for sibling in scene.get("siblings") or []]
        for index, (start, link, sibling) in enumerate(spans):
            # `stopAt`: bài kết sớm trước ranh giới (music_select.TAIL_MIN_SECONDS), phần còn lại của mảnh lặng.
            last = float(scene["end"]) if scene.get("stopAt") is None else min(float(scene["end"]), float(scene["stopAt"]))
            end = spans[index + 1][0] if index + 1 < len(spans) else last
            tail = index + 1 < len(spans) or (scene.get("stopAt") is not None and end == float(scene["stopAt"]))
            if (cues and not rested and cues[-1]["link"] == link
                    and abs(cues[-1]["end"] - start) < music_select.CUE_MERGE_GAP_SECONDS):
                cue = cues[-1]
                cue["end"] = end
            else:
                cue = {"start": start, "end": end, "link": link, "key": scene["key"]}
                if sibling:
                    cue["sibling"] = True
                cues.append(cue)
            if tail:
                cue["tail"] = True
            else:
                cue.pop("tail", None)
            if level != (cue["steps"][-1]["db"] if cue.get("steps") else 0.0):
                cue.setdefault("steps", []).append({"at": round(start, 3), "db": level})
            rested = False
        rested = scene.get("stopAt") is not None
    return clamp_to_chapter(cues, duration)


def clamp_to_chapter(cues: list[dict[str, Any]], duration: float | None) -> list[dict[str, Any]]:
    """Mốc kết muộn nhất ở `duration - CHAPTER_END_FADE_SECONDS` (giây của chương); mốc vì thế rỗng thì bỏ. Không có độ dài
    thì để nguyên. Tách khỏi `chapter_cues` để `package` chỉ đọc độ dài cho chương có nhạc."""
    if duration is None:
        return cues
    limit = float(duration) - CHAPTER_END_FADE_SECONDS
    for cue in cues:
        if cue["end"] > limit:
            cue["end"] = limit
            cue.pop("tail", None)  # kết trước điểm kết bài: trình phát mờ ra như mốc thường
    return [cue for cue in cues if cue["end"] > cue["start"]]


def chapter_seconds(project_root: Path, chapter_id: int) -> float | None:
    """Độ dài thật của file audio chương (`store.audio_duration`) - cho `chapter_cues(duration=...)`: nhạc phải mờ xong trước khi
    chính file ấy hết. Chưa có file nghe được hay không đọc được độ dài (thư mục không phải dự án) -> None, mốc không bị kẹp."""
    try:
        path = store.chapter_audio_path(Path(project_root), int(chapter_id))
    except sqlite3.Error:
        return None
    return store.audio_duration(path) if path is not None else None


def chapter_durations(project_root: Path, chapter_ids: Iterable[int]) -> dict[int, float | None]:
    """`chapter_seconds` cho nhiều chương bằng MỘT kết nối, MỘT truy vấn - `package` chạy ở mỗi manifest đồng bộ / xuất
    .abook, sách 3000 chương thì mở kết nối theo từng chương tốn cả chục giây."""
    out: dict[int, float | None] = dict.fromkeys((int(chapter_id) for chapter_id in chapter_ids), None)
    if not out:
        return out
    try:
        paths = store.chapter_audio_paths(Path(project_root))
    except sqlite3.Error:
        return out
    for chapter_id in out:
        if (path := paths.get(chapter_id)) is not None:
            out[chapter_id] = store.audio_duration(path)
    return out


_number = music_mix.number


def stereo_lufs(audio: Any, sample_rate: int) -> float | None:
    """LUFS tích hợp BS.1770 như lúc PHÁT trên hai loa: cộng công suất hai kênh; một kênh -> chép ra hai kênh giống nhau
    (+3,01 dB), nhiều hơn hai -> hai kênh đầu. Trộn xuống một kênh trước khi đo thì thấp hơn tới 3 dB khi hai kênh khác nhau."""
    import numpy as np
    import pyloudnorm

    frames = np.asarray(audio, dtype=np.float64)
    frames = frames[:, None] if frames.ndim == 1 else frames
    frames = np.repeat(frames, 2, axis=1) if frames.shape[1] == 1 else frames[:, :2]
    if sample_rate <= 0 or frames.shape[0] < int(round(sample_rate * 0.4)):
        return None
    try:
        value = float(pyloudnorm.Meter(sample_rate).integrated_loudness(frames))
    except (ValueError, ZeroDivisionError):
        return None
    return value if math.isfinite(value) else None


# Độ to NGẮN HẠN p95 (MIX_QA 3.4, lô 2) - chép nguyên từ LLM_Train/music/mixqa/st_loudness.py, cùng hàm danh mục dùng để đo
# `s95` (build_catalog.py): số trên máy và số danh mục so được với nhau. Chỉ thêm: nhập numpy / scipy trong hàm như `stereo_lufs`.
RATE = 48000
_SHELF = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_HIGHPASS = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def short_term_p95(audio, sample_rate: int = RATE) -> float | None:
    """`audio` (mẫu x kênh, 48 kHz) như lúc phát hai loa (một kênh -> chép ra hai). Không đủ 3 s hay im hẳn -> None."""
    import numpy as np
    from scipy.signal import lfilter

    if sample_rate != RATE:
        return None
    frames = np.asarray(audio, dtype=np.float64)
    frames = frames[:, None] if frames.ndim == 1 else frames
    frames = np.repeat(frames, 2, axis=1) if frames.shape[1] == 1 else frames[:, :2]
    window, hop = 3 * RATE, RATE // 10
    if frames.shape[0] < window:
        return None
    power = np.zeros(frames.shape[0])
    for channel in range(2):
        weighted = lfilter(*_HIGHPASS, lfilter(*_SHELF, frames[:, channel]))
        power += weighted * weighted
    total = np.concatenate(([0.0], np.cumsum(power)))
    starts = np.arange(0, frames.shape[0] - window + 1, hop)
    mean = (total[starts + window] - total[starts]) / window
    with np.errstate(divide="ignore"):
        loud = -0.691 + 10 * np.log10(mean)
    kept = loud[loud > -70]
    if not len(kept):
        return None
    relative = -0.691 + 10 * math.log10(float(np.mean(10 ** ((kept + 0.691) / 10)))) - 20
    kept = kept[kept > relative]
    return round(float(np.percentile(kept, 95)), 2) if len(kept) else None


def audible_bounds(audio: Any, sample_rate: int, threshold_dbfs: float = AUDIBLE_THRESHOLD_DBFS) -> tuple[float, float] | None:
    """Đoạn nghe được của bài (MIX_QA 3.2, 9): (A, E) giây của mẫu đầu và hết mẫu cuối có |x| > 10^(ngưỡng/20) sau khi trộn
    mono - trình phát lặp mờ chéo trong đoạn này, bỏ im lặng đầu / cuối. Im hẳn -> None."""
    import numpy as np

    frames = np.asarray(audio, dtype=np.float64)
    mono = frames.mean(axis=1) if frames.ndim == 2 else frames
    loud = np.flatnonzero(np.abs(mono) > 10 ** (threshold_dbfs / 20))
    if sample_rate <= 0 or not len(loud):
        return None
    return round(int(loud[0]) / sample_rate, 3), round((int(loud[-1]) + 1) / sample_rate, 3)


# Số đo của một file bài (`measured_track`): độ to tích hợp, p95 ngắn hạn, độ dài thật, đoạn nghe được.
MEASURE_KEYS = ("lufs", "s95", "seconds", "audibleStart", "audibleEnd")
# Phần số đo đi theo bài tới gain và trình phát (`track_measure`): file trên máy thắng danh mục, khoá nào cũng vậy.
TRACK_MEASURE_KEYS = ("lufs", "s95", "audibleStart", "audibleEnd")


def measured_track(path: Path, *, measure: bool = True) -> dict[str, float]:
    """Số đo (MEASURE_KEYS) của file bài nhạc, đo một lần rồi ghi cạnh file (`<tên>.measure.json`) cho lần sau. Bộ đệm cũ chỉ có
    `<tên>.lufs2` (độ to) vẫn đọc được: dùng nó tới khi đo lại được đủ. `measure=False`: chỉ đọc số đã ghi, không giải mã
    (đường nóng của trình phát). Khoá nào không đo được thì không có."""
    path = Path(path)
    sidecar = path.with_suffix(MEASURE_SIDECAR)
    try:
        cached = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = None
    if isinstance(cached, dict):
        return {key: value for key in MEASURE_KEYS if (value := _number(cached.get(key))) is not None}
    try:
        old = _number(float(path.with_suffix(LUFS_SIDECAR).read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        old = None
    known = {"lufs": old} if old is not None else {}
    if not measure or not ffmpeg_available():  # chưa có ffmpeg (mô-đun "Phân tích nhạc"): chưa đo, dùng mức mặc định
        return known
    wav = path.with_suffix(f".{os.getpid()}.measure.wav")
    try:
        command = [ffmpeg_executable(), "-hide_banner", "-nostats", "-loglevel", "error", "-nostdin", "-y", "-i",
                   str(path), "-map", "0:a:0", "-ar", str(RATE), "-codec:a", "pcm_f32le", str(wav)]
        if run_hidden(command, timeout=300, check=False).returncode != 0:
            return known
        import soundfile

        audio, rate = soundfile.read(wav, dtype="float32", always_2d=True)
        lufs = stereo_lufs(audio, int(rate))
        if lufs is None:
            return known
        bounds = audible_bounds(audio, int(rate))
        # Làm tròn đúng số ghi cạnh file: lần đo đầu và các lần đọc lại cho cùng gainDb.
        values = {"lufs": round(lufs, 2), "s95": short_term_p95(audio, int(rate)), "seconds": round(len(audio) / rate, 3),
                  "audibleStart": bounds[0] if bounds else None, "audibleEnd": bounds[1] if bounds else None}
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError, ImportError):
        return known
    finally:
        with contextlib.suppress(OSError):
            wav.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        atomic_write_json(sidecar, values)
    return {key: value for key, value in values.items() if value is not None}


def measured_lufs(path: Path, *, measure: bool = True) -> float | None:
    """Độ to (`stereo_lufs`) của file bài nhạc - phần `lufs` của `measured_track`. Không đo được -> None."""
    return measured_track(path, measure=measure).get("lufs")


def track_measure(info: dict[str, Any] | None, path: Path | None, *, measure: bool = True) -> dict[str, float]:
    """Số đo của một bài (TRACK_MEASURE_KEYS): của chính file trên máy (chính xác nhất - danh mục có bài chỉ ước lượng từ vài
    đoạn) thắng số danh mục, khoá nào thiếu thì không có. Có `lufs` danh mục thì không bắt giải mã khi `measure=False`."""
    out = {key: value for key in TRACK_MEASURE_KEYS if (value := _number((info or {}).get(key))) is not None}
    if path is not None:
        measured = measured_track(path, measure=measure or "lufs" not in out)
        out.update((key, value) for key, value in measured.items() if key in TRACK_MEASURE_KEYS)
    return out


def track_lufs(info: dict[str, Any] | None, path: Path | None, *, measure: bool = True) -> float | None:
    """Độ to của một bài - phần `lufs` của `track_measure`; không có -> None."""
    return track_measure(info, path, measure=measure).get("lufs")


def cue_gain_db(level_db: float, lufs: float | None, speech_band: float | None, s95: float | None = None) -> float:
    """Độ khuếch đại (dB, <= 0) cho một bài để nó nằm `level_db` LU dưới giọng: VOICE_PLAYED_LUFS + level_db - lufs - bù, với bù
    = 8 x (speechBand - 0,30) kẹp +-6 (bài lấn dải tiếng nói nhiều thì thấp thêm, ít thì cao hơn). Có `s95` (p95 độ to ngắn hạn)
    thì không quá VOICE_PLAYED_LUFS - SHORT_TERM_FLOOR_LU - s95: đoạn to nhất của bài vẫn dưới giọng ít nhất SHORT_TERM_FLOOR_LU
    (MIX_QA 3.4). MỘT chỗ tính duy nhất: hai trình phát (musicBed.ts, MusicBed.kt) chỉ áp con số này. Thiếu `lufs` -> trung vị
    danh mục; thiếu `speechBand` -> không bù; thiếu `s95` -> không chặn."""
    loudness = DEFAULT_TRACK_LUFS if lufs is None else lufs
    band = MASKING_CENTER if speech_band is None else speech_band
    masking = max(-MASKING_LIMIT_DB, min(MASKING_LIMIT_DB, MASKING_SLOPE_DB * (band - MASKING_CENTER)))
    gain = VOICE_PLAYED_LUFS + level_db - loudness - masking
    if s95 is not None:
        gain = min(gain, VOICE_PLAYED_LUFS - SHORT_TERM_FLOOR_LU - s95)
    return round(min(0.0, gain), 2)  # volume HTML / ExoPlayer tối đa 1


def apply_gain(cues: list[dict[str, Any]], level_db: float, tracks: dict[str, Any],
               track_path: Callable[[str], Path | None] | None = None) -> None:
    """Gắn `gainDb` cho từng mốc chưa có (mốc của gói sách xuất bởi bản mới đã mang sẵn) và đoạn nghe được của bài
    (`audibleStart` / `audibleEnd`, trình phát lặp mờ chéo trong đoạn ấy - music_mix) khi biết. `tracks`: {link: thông tin bài};
    `track_path(link)` -> file bài ĐÃ có trên máy (không tải): số đo của nó thắng số danh mục; chỉ giải mã khi danh mục
    thiếu `lufs` (còn lại dùng số đã đo sẵn, `server` đo nền lúc tải bài)."""
    for cue in cues:
        if all(_number(cue.get(key)) is not None for key in ("gainDb", "audibleStart", "audibleEnd")):
            continue
        info = tracks.get(cue["link"])
        info = info if isinstance(info, dict) else {}
        path = track_path(cue["link"]) if track_path is not None else None
        measured = track_measure(info, path, measure=False)
        if _number(cue.get("gainDb")) is None:
            cue["gainDb"] = cue_gain_db(level_db, measured.get("lufs"), _number(info.get("speechBand")), measured.get("s95"))
        if "audibleStart" in measured and "audibleEnd" in measured and _number(cue.get("audibleEnd")) is None:
            cue["audibleStart"], cue["audibleEnd"] = measured["audibleStart"], measured["audibleEnd"]


# Bài của danh mục luôn là .mp3; bài người dùng tự nhập ("Nhạc của tôi", music_local.py) giữ nguyên định dạng của file.
TRACK_EXTENSIONS = ("mp3", "m4a", "ogg", "opus", "flac", "wav")
TRACK_NAME = r"[0-9a-f]{40}\.(?:" + "|".join(TRACK_EXTENSIONS) + ")"  # tên file bài trong gói, không kể thư mục music/
TRACK_FILE = re.compile("music/" + TRACK_NAME)
TRACK_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".flac": "audio/flac",
               ".wav": "audio/wav"}
LOCAL_PREFIX = "local:"  # link của bài người dùng nhập: `local:<sha1 của file>` - không ai khác tải được


def is_local(link: str) -> bool:
    return link.startswith(LOCAL_PREFIX)


def local_hash(link: str) -> str | None:
    """Mã sha1 (40 hex) của file trong link `local:<sha1>`; link khác dạng -> None."""
    digest = link[len(LOCAL_PREFIX):] if is_local(link) else ""
    return digest if re.fullmatch(r"[0-9a-f]{40}", digest) else None


def track_name(link: str, path: Path | None = None) -> str:
    """Tên file của một bài trong gói sách: `music/<sha1 của link>.mp3` (cùng tên với bộ đệm của máy). Bài người dùng nhập:
    `music/<sha1 của file>.<đuôi thật của file>` (`path`; không có thì .mp3)."""
    digest = local_hash(link)
    if digest is not None:
        suffix = Path(path).suffix.lower() if path is not None else ""
        return f"music/{digest}{suffix if suffix[1:] in TRACK_EXTENSIONS else '.mp3'}"
    return f"music/{hashlib.sha1(link.encode('utf-8')).hexdigest()}.mp3"


class TrackSource:
    """Cách lấy file bài nhạc cho gói sách: gọi như `file(link)`, kèm `alternatives(project_root, khoá đoạn, [link bỏ])` ->
    các bài thay thế (kèm thông tin), tốt nhất trước - để chỗ có bài không lấy được thì dùng bài kế thay vì im lặng."""

    def __init__(self, file: Callable[[str], Path | None],
                 alternatives: Callable[[Path, str, list[str]], list[dict[str, Any]]] | None = None) -> None:
        self.file, self.alternatives = file, alternatives

    def __call__(self, link: str) -> Path | None:
        return self.file(link)


SUBSTITUTE_DROPS = ("tail", "gainDb", "audibleStart", "audibleEnd")


def substituted(cue: dict[str, Any], link: str) -> dict[str, Any]:
    """Mốc `cue` chuyển sang bài thay `link` (bài đã chọn không lấy được): bỏ những gì chỉ đúng cho bài đã lập lịch - cờ `tail`
    (bài kết đúng ở cuối mốc; bài thay dài ngắn khác) và độ khuếch đại / đoạn nghe được (tính lại theo bài thay). Một chỗ cho trình
    phát máy tính (`server._music_playable`) lẫn gói sách (`package`)."""
    return {**{key: value for key, value in cue.items() if key not in SUBSTITUTE_DROPS}, "link": link}


def package(project_root: Path, chapter_ids: Iterable[int],
            track_file: Callable[[str], Path | None], *, include_disabled: bool = False,
            dropped: list[int] | None = None) -> tuple[dict[str, Any], dict[str, Path]] | None:
    """Nhạc nền đi theo cuốn sách khi xuất (chủ sách 01-10: sách xuất ra mang nhạc người sản xuất đã gắn): mục `music`
    của book.json + các file bài. Bài nào không lấy được file (mất mạng, nguồn gỡ) thì dùng bài thay thế đầu tiên lấy được
    (`TrackSource.alternatives`); không có bài nào thì các mốc của nó bỏ đi - chỗ đó im lặng, sách vẫn xuất được. Rãnh
    nhạc tắt / chưa dựng -> None (sách không nhạc, định dạng cũ).
    `include_disabled`: rãnh nhạc đang tắt vẫn gói (bản xuất sách nói người dùng tích "Kèm nhạc nền" - music_export.py). `dropped`:
    nhận mã chương của mỗi mốc bị bỏ vì không lấy được bài nào - để báo "N đoạn thiếu nhạc"."""
    plan = read_plan(project_root)
    if plan is None or not (plan.get("enabled") or include_disabled):
        return None
    plan = {**plan, "enabled": True}
    level_db = plan.get("levelDb", DEFAULT_LEVEL_DB)
    files: dict[str, Path] = {}
    tracks: dict[str, dict[str, Any]] = {}
    chapters: dict[str, list[dict[str, Any]]] = {}
    alternatives = getattr(track_file, "alternatives", None)
    names: dict[str, str] = {}  # link -> tên file trong gói, của các bài đã có file
    audible: dict[str, dict[str, float]] = {}  # tên file trong gói -> đoạn nghe được của bài (`audible_bounds`)
    failed: set[str] = set()  # bài đã thử mà không lấy được: không thử lại ở mốc khác

    def resolve(cue: dict[str, Any]) -> tuple[str, dict[str, Any], Path] | None:
        """(link, thông tin, file) của bài dùng cho mốc này: chính bài đã chọn, không lấy được thì bài thay thế đầu tiên."""
        link = cue["link"]
        info = (plan.get("tracks") or {}).get(link) or {}
        if link in names:
            return link, info, files[names[link]]
        path = None if link in failed else track_file(link)
        if path is not None:
            return link, info, path
        failed.add(link)
        for other in (alternatives(project_root, cue["key"], [link]) if alternatives else []):
            path = files[names[other["link"]]] if other["link"] in names else track_file(other["link"])
            if path is not None:
                return other["link"], other, path
        return None

    # Mốc trước, độ dài sau: chỉ chương có nhạc mới đọc độ dài, và đọc hàng loạt.
    planned = {chapter_id: chapter_cues(plan, chapter_id) for chapter_id in chapter_ids}
    lengths = chapter_durations(project_root, [chapter_id for chapter_id, cues in planned.items() if cues])
    for chapter_id, planned_cues in planned.items():
        kept = []
        for cue in clamp_to_chapter(planned_cues, lengths.get(int(chapter_id))):
            found = resolve(cue)
            if found is None:
                if dropped is not None:
                    dropped.append(int(chapter_id))
                continue
            link, info, path = found
            if link != cue["link"]:
                cue = substituted(cue, link)
            name = names.get(link)
            if name is None:
                name = names[link] = track_name(link, path)
                files[name] = path
                tracks[name] = {"file": name, "link": link,
                                **{key: info.get(key) for key in ("title", "creator", "license", "licenseUrl",
                                                                  "attribution", "landing") if info.get(key)}}
                # Độ to, p95 ngắn hạn + độ lấn dải tiếng nói đi theo bài (sách đọc lại / đổi mức / cập nhật mà không cần
                # danh mục); số đo từ chính file đang đóng gói thắng số danh mục. Đoạn nghe được đi theo từng mốc.
                measured = track_measure(info, path)
                for key, value in (("lufs", measured.get("lufs")), ("speechBand", _number(info.get("speechBand"))),
                                   ("s95", measured.get("s95"))):
                    if value is not None:
                        tracks[name][key] = round(value, 2)
                audible[name] = {key: measured[key] for key in ("audibleStart", "audibleEnd") if key in measured}
            kept.append({"start": round(cue["start"], 3), "end": round(cue["end"], 3), "track": name,
                         "gainDb": cue_gain_db(level_db, _number(tracks[name].get("lufs")),
                                               _number(tracks[name].get("speechBand")), _number(tracks[name].get("s95"))),
                         **_cue_shape({**cue, **audible[name]})})
        if kept:
            chapters[str(chapter_id)] = kept
    if not chapters:
        return None
    music = {"levelDb": level_db, "tracks": tracks, "chapters": chapters}
    return music, files


def substituted_tracks(project_root: Path, track_file: Callable[[str], Path | None]) -> list[str]:
    """Link các bài THAY THẾ mà `package` có thể dùng thay bài của plan mà máy này không lấy được: chỉ đoạn của chính cuốn
    này, qua `TrackSource.alternatives` - để nơi phục vụ file chỉ mở đúng các bài ấy, không phải link tuỳ ý. Không có
    `alternatives` (callable thường) hay plan tắt / chưa dựng -> rỗng."""
    plan = read_plan(project_root)
    alternatives = getattr(track_file, "alternatives", None)
    if plan is None or not plan.get("enabled") or alternatives is None:
        return []
    out: list[str] = []
    for scene in plan.get("scenes") or []:
        link = scene.get("link")
        if not link or track_file(link) is not None:
            continue
        for other in alternatives(project_root, scene["key"], [link]):
            if other["link"] not in out:
                out.append(other["link"])
    return out


def track_file_named(project_root: Path, name: str, track_file: Callable[[str], Path | None]) -> Path | None:
    """File của bài tên `name` (`music/<sha1>.<đuôi>`) trong gói của cuốn này: chỉ bài của chính plan (`plan["tracks"]`) hay bài
    thay thế (`substituted_tracks`) - nơi phục vụ file (đồng bộ điện thoại, trình phát máy tính) không mở link tuỳ ý."""
    plan = read_plan(project_root)
    stem, _, suffix = name.removeprefix("music/").partition(".")

    def matches(link: str) -> bool:
        return (local_hash(link) == stem if is_local(link) else suffix == "mp3" and track_name(link) == name)

    def serve(link: str) -> Path | None:
        path = track_file(link)
        return path if path is not None and track_name(link, path) == name else None

    for link in (plan or {}).get("tracks") or {}:
        if matches(link):
            return serve(link)
    for link in substituted_tracks(project_root, track_file):
        if matches(link):
            return serve(link)
    return None


def packaged_cues(music: dict[str, Any] | None, chapter_id: int) -> list[dict[str, Any]]:
    """Mốc nhạc của một chương từ mục `music` của một cuốn đã đóng gói: [{start, end, link, key, track}]."""
    if not isinstance(music, dict):
        return []
    tracks = music.get("tracks") if isinstance(music.get("tracks"), dict) else {}
    out = []
    for cue in (music.get("chapters") or {}).get(str(chapter_id)) or []:
        track = cue.get("track") if isinstance(cue, dict) else None
        if not isinstance(track, str) or not TRACK_FILE.fullmatch(track) or track not in tracks:
            continue
        try:
            start, end = float(cue["start"]), float(cue["end"])
        except (KeyError, TypeError, ValueError):
            continue
        item = {"start": start, "end": end, "link": tracks[track].get("link") or track, "key": track, "track": track}
        if _number(cue.get("gainDb")) is not None:
            item["gainDb"] = float(cue["gainDb"])
        item.update(_cue_shape(cue))
        out.append(item)
    return out


def packaged_playable(music: dict[str, Any] | None, chapter_id: int) -> tuple[list[dict[str, Any]], float, dict[str, Any]]:
    """(mốc, mức, {link: thông tin bài}) của một chương trong mục `music` của cuốn đã đóng gói - mốc nào chưa có `gainDb` (sách xuất
    bởi bản cũ) thì tính theo mức của gói. Chung cho trình phát máy tính (`server.music_cues`) và bản xuất kèm nhạc (music_export)."""
    cues = packaged_cues(music, chapter_id)
    level = music.get("levelDb") if isinstance(music, dict) else None
    level = level if isinstance(level, (int, float)) else DEFAULT_LEVEL_DB
    tracks = music.get("tracks") if isinstance(music, dict) and isinstance(music.get("tracks"), dict) else {}
    by_link = {cue["link"]: tracks.get(cue["track"]) for cue in cues}
    apply_gain(cues, level, by_link)
    return cues, level, by_link


def _cue_shape(cue: dict[str, Any]) -> dict[str, Any]:
    """Phần hình dạng của một mốc ngoài bài và độ to: `sibling` (nối bài anh em trong cảnh), `tail` (mốc kết đúng ở điểm kết
    bài - `chapter_cues`), `steps` (bước âm lượng [{at, db}], `at` tăng dần) và đoạn nghe được của bài (`audibleStart` /
    `audibleEnd`, giây trong bài - trình phát lặp mờ chéo trong đó; sách cũ không có thì trình phát dùng 0 và độ dài thật) - chỉ
    khoá nào có, bước hỏng bị bỏ. Một chỗ cho gói sách (`package`) lẫn sách đã đóng gói (`packaged_cues`)."""
    out: dict[str, Any] = {}
    for flag in ("sibling", "tail"):
        if cue.get(flag) is True:
            out[flag] = True
    start, end = _number(cue.get("audibleStart")), _number(cue.get("audibleEnd"))
    if start is not None and end is not None and 0 <= start < end:
        out["audibleStart"], out["audibleEnd"] = round(start, 3), round(end, 3)
    raw = cue.get("steps") if isinstance(cue.get("steps"), list) else []
    steps = [{"at": round(float(step["at"]), 3), "db": round(float(step["db"]), 2)} for step in raw
             if isinstance(step, dict) and _number(step.get("at")) is not None and _number(step.get("db")) is not None]
    if steps:
        out["steps"] = sorted(steps, key=lambda step: step["at"])
    return out
