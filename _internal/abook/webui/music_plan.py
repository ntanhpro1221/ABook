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
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from ..config import DEFAULT_SETTINGS
from ..io_utils import atomic_write_json, atomic_write_text, ffmpeg_available, ffmpeg_executable, run_hidden
from . import music_moods, music_scene_student, music_scenes, music_select, store

PLAN_FILE = "music_plan.json"
OVERRIDES_FILE = "music_overrides.json"
PLAN_VERSION = 1
# `levelDb` = nhạc nền thấp hơn GIỌNG bao nhiêu LU (Pha 4, docs/MUSIC_RESEARCH.md: -20 + bù theo bài -> 94% cặp ESTOI >= 0,9).
DEFAULT_LEVEL_DB = -20.0
VOICE_LUFS = float(DEFAULT_SETTINGS["audio"]["loudness_lufs"])  # giọng mọi chương được chuẩn hoá về mức này
# Chương giọng đọc là file MỘT kênh, chuẩn hoá về VOICE_LUFS đo một kênh; phát ra hai loa / tai nghe thì BS.1770 cộng hai
# kênh giống nhau -> to hơn 3,01 dB. Nhạc đo đúng như lúc phát (hai kênh, `stereo_lufs`), nên mốc giọng cũng tính như lúc phát.
VOICE_PLAYED_LUFS = VOICE_LUFS + 10 * math.log10(2)
LUFS_SIDECAR = ".lufs2"  # 2: đo hai kênh như lúc phát; số cũ (`.lufs`, trộn xuống một kênh) thấp 0,5-3 dB với bài stereo rộng
DEFAULT_TRACK_LUFS = -16.6  # trung vị danh mục: bài chưa có `lufs` (plan / danh mục cũ) và chưa có file để đo
MASKING_CENTER = 0.30  # trung vị `speechBand` của danh mục: bài lấn dải tiếng nói hơn mức này thì hạ thêm
MASKING_SLOPE_DB = 8.0
MASKING_LIMIT_DB = 6.0
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
          available: Callable[[str], bool] | None = None) -> dict[str, Any]:
    """Dựng lại music_plan.json: chia đoạn cả cuốn, chọn bài theo lựa chọn của người dùng, gắn thông tin bài.
    `scenes`: các đoạn đã có (từ plan cũ, qua `scenes_of`) - chọn lại bài trên đúng các đoạn ấy, không chia lại sách;
    người dùng sửa một đoạn thì các đoạn khác không đổi theo (chỉ "Chọn lại nhạc" mới chia lại).
    `keep`: {khoá đoạn: bài cũ} (từ `kept_tracks`) - đoạn nào có trong đó giữ nguyên bài, trừ khi bài đã bị bỏ hoặc không
    còn trong danh mục (không dùng được nữa) thì chọn lại như thường. `kept_siblings` (từ `kept_siblings`): bài anh em cũ của
    các đoạn ấy - đoạn không bị sửa lan thì nối đúng các bài cũ (music_select.choose).
    `available(link)`: bài dùng được trên máy này không (music_select.choose) - bài không lấy được thì đoạn chọn bài kế."""
    project_root = Path(project_root)
    overrides = read_overrides(project_root)
    if scenes is None:
        # Có kết quả LLM đọc cả đoạn (music_moods.py) thì valence / tension của đoạn lấy từ đó; không có thì đường nhãn câu. Có học
        # sinh đoán hình không khí trong chương (music_scene_student.py) thì nó chỉnh tiếp V / E / T quanh mức chương.
        moods = music_moods.load(project_root)
        student = music_scene_student.load(project_root)
        scenes = music_scenes.book_scenes(book_scripts(project_root), moods["scenes"] if moods else None,
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
    atomic_write_json(project_root / PLAN_FILE, plan)
    return plan


# Thông tin bài ghi vào plan["tracks"] (ghi công, độ to) - bài thay thế tạm lúc phát cũng mang đúng bộ này.
TRACK_INFO_KEYS = ("title", "creator", "license", "licenseUrl", "attribution", "duration", "source", "landing", "lufs",
                   "speechBand")
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


def chapter_cues(plan: dict[str, Any], chapter_id: int) -> list[dict[str, Any]]:
    """Nhạc của một chương cho trình phát: [{start, end, link, key}] theo thời gian trong MP3 chương (đoạn im lặng thì
    không có). Hai đoạn liền nhau cùng bài gộp làm một - bài chơi liền, không bắt đầu lại.
    Bài anh em nối trong cảnh (`siblings` của đoạn, music_select.choose) tách mốc đúng ở điểm kết bài: mốc mới mang
    `sibling: True` (trình phát mờ chéo dài hơn, không nghe như đổi cảnh). Bước âm lượng của các mảnh nối tiếp (`stepDb`) thành
    `steps: [{at, db}]` của mốc - mức (dB, cộng vào `gainDb`) từ giây `at` của chương; mốc bắt đầu ở mức khác 0 thì có bước
    ngay ở `start`."""
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
            if end - start < 1e-6:
                continue  # nền tắt ngay từ đầu mảnh (truyện mở cảnh bằng tiếng nhạc thật): không có mốc
            if cues and not rested and cues[-1]["link"] == link and abs(cues[-1]["end"] - start) < 5:
                cue = cues[-1]
                cue["end"] = end
            else:
                cue = {"start": start, "end": end, "link": link, "key": scene["key"]}
                if sibling:
                    cue["sibling"] = True
                cues.append(cue)
            if level != (cue["steps"][-1]["db"] if cue.get("steps") else 0.0):
                cue.setdefault("steps", []).append({"at": round(start, 3), "db": level})
            rested = False
        rested = scene.get("stopAt") is not None
    return cues


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


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


def measured_lufs(path: Path, *, measure: bool = True) -> float | None:
    """Độ to (`stereo_lufs`) của file bài nhạc, đo một lần rồi ghi cạnh file (`<tên>.lufs2`) cho lần sau. `measure=False`:
    chỉ đọc số đã ghi, không giải mã (đường nóng của trình phát). Không đo được -> None."""
    sidecar = Path(path).with_suffix(LUFS_SIDECAR)
    try:
        cached = _number(float(sidecar.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        cached = None
    if cached is not None or not measure or not ffmpeg_available():  # chưa có ffmpeg (mô-đun "Phân tích nhạc"): chưa đo, dùng mức mặc định
        return cached
    wav = Path(path).with_suffix(f".{os.getpid()}.measure.wav")
    try:
        command = [ffmpeg_executable(), "-hide_banner", "-nostats", "-loglevel", "error", "-nostdin", "-y", "-i",
                   str(path), "-map", "0:a:0", "-ar", "48000", "-codec:a", "pcm_f32le", str(wav)]
        if run_hidden(command, timeout=300, check=False).returncode != 0:
            return None
        import soundfile

        audio, rate = soundfile.read(wav, dtype="float32", always_2d=True)
        value = stereo_lufs(audio, int(rate))
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError, ImportError):
        return None
    finally:
        with contextlib.suppress(OSError):
            wav.unlink(missing_ok=True)
    if value is None:
        return None
    value = round(value, 2)  # đúng số ghi cạnh file: lần đo đầu và các lần đọc lại cho cùng gainDb
    with contextlib.suppress(OSError):
        atomic_write_text(sidecar, f"{value:.2f}\n")
    return value


def track_lufs(info: dict[str, Any] | None, path: Path | None, *, measure: bool = True) -> float | None:
    """Độ to của một bài: số đo từ chính file trên máy (chính xác nhất - danh mục có bài chỉ ước lượng từ vài đoạn), không thì
    `lufs` của danh mục, không thì None. Có số danh mục thì không bắt giải mã khi `measure=False`."""
    known = _number((info or {}).get("lufs"))
    if path is not None:
        measured = measured_lufs(path, measure=measure or known is None)
        if measured is not None:
            return measured
    return known


def cue_gain_db(level_db: float, lufs: float | None, speech_band: float | None) -> float:
    """Độ khuếch đại (dB, <= 0) cho một bài để nó nằm `level_db` LU dưới giọng: VOICE_PLAYED_LUFS + level_db - lufs - bù, với bù
    = 8 x (speechBand - 0,30) kẹp +-6 (bài lấn dải tiếng nói nhiều thì thấp thêm, ít thì cao hơn). MỘT chỗ tính duy nhất:
    hai trình phát (musicBed.ts, MusicBed.kt) chỉ áp con số này. Thiếu `lufs` -> trung vị danh mục; thiếu `speechBand`
    -> không bù."""
    loudness = DEFAULT_TRACK_LUFS if lufs is None else lufs
    band = MASKING_CENTER if speech_band is None else speech_band
    masking = max(-MASKING_LIMIT_DB, min(MASKING_LIMIT_DB, MASKING_SLOPE_DB * (band - MASKING_CENTER)))
    return round(min(0.0, VOICE_PLAYED_LUFS + level_db - loudness - masking), 2)  # volume HTML / ExoPlayer tối đa 1


def apply_gain(cues: list[dict[str, Any]], level_db: float, tracks: dict[str, Any],
               track_path: Callable[[str], Path | None] | None = None) -> None:
    """Gắn `gainDb` cho từng mốc chưa có (mốc của gói sách xuất bởi bản mới đã mang sẵn). `tracks`: {link: thông tin bài};
    `track_path(link)` -> file bài ĐÃ có trên máy (không tải): số đo của nó thắng `lufs` danh mục; chỉ giải mã khi danh mục
    thiếu `lufs` (còn lại dùng số đã đo sẵn, `server` đo nền lúc tải bài)."""
    for cue in cues:
        if _number(cue.get("gainDb")) is not None:
            continue
        info = tracks.get(cue["link"])
        info = info if isinstance(info, dict) else {}
        path = track_path(cue["link"]) if track_path is not None else None
        cue["gainDb"] = cue_gain_db(level_db, track_lufs(info, path, measure=False), _number(info.get("speechBand")))


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


def package(project_root: Path, chapter_ids: Iterable[int],
            track_file: Callable[[str], Path | None]) -> tuple[dict[str, Any], dict[str, Path]] | None:
    """Nhạc nền đi theo cuốn sách khi xuất (chủ sách 01-10: sách xuất ra mang nhạc người sản xuất đã gắn): mục `music`
    của book.json + các file bài. Bài nào không lấy được file (mất mạng, nguồn gỡ) thì dùng bài thay thế đầu tiên lấy được
    (`TrackSource.alternatives`); không có bài nào thì các mốc của nó bỏ đi - chỗ đó im lặng, sách vẫn xuất được. Rãnh
    nhạc tắt / chưa dựng -> None (sách không nhạc, định dạng cũ)."""
    plan = read_plan(project_root)
    if plan is None or not plan.get("enabled"):
        return None
    level_db = plan.get("levelDb", DEFAULT_LEVEL_DB)
    files: dict[str, Path] = {}
    tracks: dict[str, dict[str, Any]] = {}
    chapters: dict[str, list[dict[str, Any]]] = {}
    alternatives = getattr(track_file, "alternatives", None)
    names: dict[str, str] = {}  # link -> tên file trong gói, của các bài đã có file
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

    for chapter_id in chapter_ids:
        kept = []
        for cue in chapter_cues(plan, chapter_id):
            found = resolve(cue)
            if found is None:
                continue
            link, info, path = found
            name = names.get(link)
            if name is None:
                name = names[link] = track_name(link, path)
                files[name] = path
                tracks[name] = {"file": name, "link": link,
                                **{key: info.get(key) for key in ("title", "creator", "license", "licenseUrl",
                                                                  "attribution", "landing") if info.get(key)}}
                # Độ to + độ lấn dải tiếng nói đi theo bài (sách đọc lại / cập nhật mà không cần danh mục); số đo từ
                # chính file đang đóng gói thắng số danh mục.
                lufs = track_lufs(info, path)
                for key, value in (("lufs", lufs), ("speechBand", _number(info.get("speechBand")))):
                    if value is not None:
                        tracks[name][key] = round(value, 2)
            kept.append({"start": round(cue["start"], 3), "end": round(cue["end"], 3), "track": name,
                         "gainDb": cue_gain_db(level_db, _number(tracks[name].get("lufs")),
                                               _number(tracks[name].get("speechBand"))),
                         **_cue_shape(cue)})
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


def _cue_shape(cue: dict[str, Any]) -> dict[str, Any]:
    """Phần hình dạng của một mốc ngoài bài và độ to: `sibling` (nối bài anh em trong cảnh) và `steps` (bước âm lượng
    [{at, db}], `at` tăng dần) - chỉ khoá nào có, bước hỏng bị bỏ. Một chỗ cho gói sách (`package`) lẫn sách đã đóng gói
    (`packaged_cues`)."""
    out: dict[str, Any] = {}
    if cue.get("sibling") is True:
        out["sibling"] = True
    raw = cue.get("steps") if isinstance(cue.get("steps"), list) else []
    steps = [{"at": round(float(step["at"]), 3), "db": round(float(step["db"]), 2)} for step in raw
             if isinstance(step, dict) and _number(step.get("at")) is not None and _number(step.get("db")) is not None]
    if steps:
        out["steps"] = sorted(steps, key=lambda step: step["at"])
    return out
