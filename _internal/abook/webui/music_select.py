"""Chọn nhạc nền cho từng đoạn (music_scenes.py) từ danh mục (music_catalog.py) - máy tự làm hết; người dùng chỉ can thiệp
nếu muốn (ghim bài cho một đoạn, đổi không khí, chọn phong cách nhạc của cuốn), như sửa cách đọc tên hay giọng nhân vật.

Đoạn và bài nằm trên cùng mặt phẳng cảm xúc (vui/buồn x êm/dồn dập). Bài "tương đương" = gần nhất trên mặt phẳng ấy, cộng:
- phạt khác PHONG CÁCH của cuốn (nếu đã chọn: cổ phong, giao hưởng, piano...);
- phạt bài ít hợp làm nền (giai điệu nổi), bài quá ngắn để lặp;
- phạt bài vừa dùng ở mấy đoạn trước - không lặp mãi một bài;
- hai đoạn liền nhau chọn trúng cùng bài thì nhạc chơi liền, không bắt đầu lại.
Không bài nào đủ gần (MAX_DISTANCE) thì đoạn ấy IM LẶNG - im lặng tốt hơn nhạc sai không khí. Hoà điểm thì chọn tất định
theo mã sách: làm lại vẫn ra đúng bài cũ.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, Iterable

MAX_DISTANCE = 0.75
TENSION_WEIGHT = 0.6             # trục căng thẳng nhẹ hơn vui/buồn và năng lượng (đường cơ sở - đo lại ở Pha 3)
STYLE_HALF_PENALTY = 0.3         # phong cách chỉ "dùng được" (0,5) với thể loại của cuốn
FAMILY_PENALTY = 0.35
FOREGROUND_PENALTY = 0.25       # x (1 - độ hợp làm nền)
RECENT_PENALTY = 0.3            # bài đã dùng trong RECENT_SCENES đoạn trước
RECENT_SCENES = 3
MIN_TRACK_SECONDS = 60
WEAK_MOOD = 0.2                 # đoạn không có không khí rõ (ít câu có cảm xúc) ...
CALM_TARGET = (0.15, -0.55)     # ... thì nhạc nền nhẹ, êm - nhạc mặc định bật (chủ sách 01-10)


def _tiebreak(book_key: str, link: str) -> float:
    return int(hashlib.sha1(f"{book_key}|{link}".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF * 1e-3


def target_of(scene: dict[str, Any]) -> tuple[float, float]:
    """Điểm cảm xúc cần tìm nhạc: đoạn không có không khí rõ thì kéo về nền êm nhẹ."""
    valence, arousal = float(scene.get("valence") or 0.0), float(scene.get("arousal") or 0.0)
    confidence = float(scene.get("confidence") or 0.0)
    if confidence >= WEAK_MOOD:
        return valence, arousal
    weight = confidence / WEAK_MOOD
    return (weight * valence + (1 - weight) * CALM_TARGET[0], weight * arousal + (1 - weight) * CALM_TARGET[1])


def style_fit(track: dict[str, Any], genre_styles: dict[str, float] | None) -> float:
    """Độ hợp phong cách của bài với thế giới của cuốn (bảng thể loại x phong cách trong danh mục): 1 hợp, 0,5 dùng được,
    0 = LOẠI CỨNG. Chưa chọn thể loại -> không lọc."""
    if not genre_styles:
        return 1.0
    style = track.get("style")
    return float(genre_styles.get(style, 0.0)) if style else 0.5


def score(track: dict[str, Any], target: tuple[float, ...], *, family: str | None, recent: list[str],
          genre_styles: dict[str, float] | None = None) -> float:
    point = (float(track["valence"]), float(track["arousal"]))
    distance = math.dist(point, target[:2])
    if len(target) > 2 and track.get("tension") is not None:
        distance = math.hypot(distance, TENSION_WEIGHT * (float(track["tension"]) - target[2]))
    penalty = 0.0
    if style_fit(track, genre_styles) < 1.0:
        penalty += STYLE_HALF_PENALTY
    if family and track.get("family") != family:
        penalty += FAMILY_PENALTY
    background = track.get("background")
    if background is not None and track.get("source") != "incompetech":
        penalty += FOREGROUND_PENALTY * (1.0 - float(background))
    if track.get("link") in recent:
        penalty += RECENT_PENALTY
    return distance + penalty


def choose(scenes: list[dict[str, Any]], candidates_near: Callable[[float, float], Iterable[dict[str, Any]]], *,
           book_key: str, family: str | None = None, pins: dict[str, str] | None = None,
           banned: Iterable[str] = (), genre_styles: dict[str, float] | None = None,
           keep: dict[str, str | None] | None = None) -> list[dict[str, Any]]:
    """Mỗi đoạn kèm `link` (None = im lặng), `distance`, `pinned`. `pins`: {khoá đoạn: link} người dùng ghim
    (khoá = `scene_key`); `banned`: link người dùng đã bỏ (không chọn lại cho cuốn này).
    `keep`: {khoá đoạn: link đã chọn trước đó (None = đoạn đã im lặng)} - như ghim "mềm": đoạn nào có trong `keep` giữ
    nguyên bài cũ (không tính là ghim), trừ khi bài ấy đã bị bỏ thì chọn lại. Người dùng sửa MỘT đoạn / MỘT bài thì các
    đoạn khác không được đổi bài theo chỉ vì phạt "vừa dùng" lan dọc cuốn."""
    pins = pins or {}
    keep = keep or {}
    banned = set(banned)
    chosen: list[dict[str, Any]] = []
    recent: list[str] = []
    for scene in scenes:
        key = scene_key(scene)
        result = dict(scene, key=key, pinned=False)
        if key in pins:
            result.update(link=pins[key], pinned=True, distance=None)
        elif key in keep and keep[key] not in banned:
            result.update(link=keep[key], distance=None)
        else:
            # Cùng một cách xếp hạng với "Đổi bài" (`rank`): bài máy chọn luôn là bài đầu danh sách gợi ý.
            best = rank(scene, candidates_near, book_key=book_key, family=family, banned=banned,
                        genre_styles=genre_styles, recent=recent, limit=1)
            if best:
                result.update(link=best[0]["link"], distance=best[0]["score"])
            else:
                result.update(link=None, distance=None)
        # Đoạn kề chọn trúng bài đang chơi: chơi tiếp, không phải bài "mới" (không tính là lặp).
        if result["link"] and (not recent or recent[-1] != result["link"]):
            recent.append(result["link"])
        chosen.append(result)
    return chosen


def rank(scene: dict[str, Any], candidates_near: Callable[[float, float], Iterable[dict[str, Any]]], *, book_key: str,
         family: str | None = None, banned: Iterable[str] = (), genre_styles: dict[str, float] | None = None,
         recent: list[str] | None = None, exclude: Iterable[str] = (), limit: int = 6) -> list[dict[str, Any]]:
    """Các bài thay thế cho MỘT đoạn ("Đổi bài"), tốt nhất trước: cùng bộ lọc và cùng điểm với `choose` (bỏ bài đã bỏ,
    bài quá ngắn, phong cách không hợp thế giới của cuốn; điểm = `score` + hoà điểm theo mã sách) và cùng ngưỡng
    MAX_DISTANCE: bài xa không khí của đoạn thì không gợi ý. `recent`: các bài đã chơi ở mấy đoạn trước; `exclude`: link
    không đưa ra (bài đang chọn). Mỗi mục: `{...bài, score}`, điểm càng thấp càng hợp."""
    banned, exclude = set(banned), set(exclude)
    target = (*target_of(scene), float(scene.get("tension") or 0.0))
    ceiling = MAX_DISTANCE + (FAMILY_PENALTY if family else 0.0)
    ranked: list[tuple[float, dict[str, Any]]] = []
    seen: set[str] = set()
    for track in candidates_near(target[0], target[1]):
        link = str(track.get("link") or "")
        if not link or link in seen or link in banned or link in exclude:
            continue
        seen.add(link)
        if int(track.get("duration") or 0) < MIN_TRACK_SECONDS or style_fit(track, genre_styles) <= 0.0:
            continue
        value = score(track, target, family=family, recent=(recent or [])[-RECENT_SCENES:], genre_styles=genre_styles)
        value += _tiebreak(book_key, link)
        if value <= ceiling:
            ranked.append((value, track))
    ranked.sort(key=lambda item: item[0])
    return [dict(track, score=round(value, 3)) for value, track in ranked[:limit]]


def scene_key(scene: dict[str, Any]) -> str:
    """Khoá bền của một đoạn: chương + câu đầu. Chia lại đoạn thì đoạn mới có khoá mới (ghim cũ không áp nhầm)."""
    return f"{scene.get('chapterId')}:{scene.get('firstSegment')}"
