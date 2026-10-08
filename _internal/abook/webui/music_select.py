"""Chọn nhạc nền cho từng đoạn (music_scenes.py) từ danh mục (music_catalog.py) - máy tự làm hết; người dùng chỉ can thiệp
nếu muốn (ghim bài cho một đoạn, đổi không khí, chọn phong cách nhạc của cuốn), như sửa cách đọc tên hay giọng nhân vật.

Đoạn và bài nằm trên cùng không gian ba trục (năng lượng, căng thẳng, vui/buồn - docs/MUSIC_THEORY.md Lớp 1). Bài "tương
đương" = gần nhất trong không gian ấy, KHOẢNG CÁCH TÍNH THEO ĐỘ KHÔNG CHẮC: lệch một trục được bao nhiêu thì tuỳ đoạn và bài
lẫn lộn đến đâu (độ lệch chuẩn của đoạn, của bài, thêm độ không chắc của đoạn có ít câu có cảm xúc). Cộng:
- phạt khác PHONG CÁCH của cuốn (nếu đã chọn: cổ phong, giao hưởng, piano...);
- phạt bài ít hợp làm nền (giai điệu nổi), bài quá ngắn để lặp;
- phạt bài vừa dùng ở mấy đoạn trước - không lặp mãi một bài;
- phạt bài ngắn hơn cảnh (phải lặp nhiều vòng);
- hai đoạn liền nhau chọn trúng cùng bài thì nhạc chơi liền, không bắt đầu lại.
Bài chỉ đổi ở ranh giới có lý do (đầu chương, dòng ngăn cảnh, dấu hiệu đổi cảnh, đổi không khí); mảnh chia đều của một đoạn
dài chơi tiếp bài của cảnh, bài hết vòng thì nối sang bài anh em (xem `choose`).
Không bài nào đủ gần (MAX_Z) thì đoạn ấy IM LẶNG - im lặng tốt hơn nhạc sai không khí. Hoà điểm thì chọn tất định theo mã
sách: làm lại vẫn ra đúng bài cũ.
Khi cả đoạn lẫn bài có 13 cường độ cảm xúc (Lớp 2), độ giống nhau (cosine) được trừ khỏi điểm: nó chỉ xếp hạng các bài đã qua
ngưỡng im lặng, không cứu bài xa không khí.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, Iterable

from . import music_scenes

# Điểm Lớp 1-2 của docs/MUSIC_THEORY.md §5.3. Mọi hằng số dưới đây là GIÁ TRỊ KHỞI ĐẦU lấy từ tài liệu ấy và sẽ được học
# (E4: Bradley-Terry trên phán quyết cặp mù của máy chấm - nghe bằng model âm thanh + Claude chấm mù; chủ sách không chấm).
MAX_Z = 2.0                      # khoảng cách (đã chia theo độ không chắc) xa hơn mức này thì đoạn im lặng
AXIS_WEIGHTS = {"arousal": 1.0, "tension": 0.8, "valence": 0.6}   # năng lượng > căng thẳng > vui/buồn (theo độ tin cậy đo được)
TAU = 0.1                        # sàn độ không chắc mỗi trục: không bao giờ chia cho ~0
SCENE_SD_DEFAULT = 0.25          # đoạn chưa có `sd`
TRACK_SD_DEFAULT = 0.2           # bài chưa có `sd`
VET_VAR_WEIGHT = 0.1             # x `vetVar` (phương sai dư của bộ đoán, chỉ bài nhập có) cộng vào tử số mỗi trục - docs/MUSIC_RESEARCH.md "F2"
UNCERTAIN_SD = 0.35             # đoạn ít câu có cảm xúc (confidence thấp) được khoan dung thêm chừng này x (1 - confidence)
# x cosine 13 cảm xúc, trừ khỏi điểm (Lớp 2). TẮT: đo 02-10 trên 10 chương bộ cảnh 4 (57 đoạn, khoảng cách nhãn người
# tới đáp án, thấp = hợp): Lớp 1 riêng 0,824, main 0,845, +Lớp 2 trọng số 1 0,859, trọng số 3 0,936 - cảm xúc đoạn suy
# từ nhãn câu (LINE_EMOTIONS) còn quá thô. Bật lại khi đường LLM cho 13 cường độ của đoạn và đo lại (E4).
EMOTION_WEIGHT = 0.0
# Các phạt dưới đây tính trên CÙNG THANG với z_distance: khoảng cách đã chia cho độ không chắc điển hình
# sqrt(SCENE_SD_DEFAULT^2 + TRACK_SD_DEFAULT^2 + TAU^2) ~ 0,34, nên mỗi phạt = giá trị cũ trên thang Euclid / PENALTY_UNIT.
PENALTY_UNIT = math.sqrt(SCENE_SD_DEFAULT ** 2 + TRACK_SD_DEFAULT ** 2 + TAU ** 2)
STYLE_HALF_PENALTY = 0.3 / PENALTY_UNIT    # phong cách chỉ "dùng được" (0,5) với thể loại của cuốn
FAMILY_PENALTY = 0.35 / PENALTY_UNIT
FOREGROUND_PENALTY = 0.25 / PENALTY_UNIT   # x (1 - độ hợp làm nền)
RECENT_PENALTY = 0.3 / PENALTY_UNIT        # bài đã dùng trong RECENT_SCENES đoạn trước
RECENT_SCENES = 3
MIN_TRACK_SECONDS = 60
WEAK_MOOD = 0.2                 # đoạn không có không khí rõ (ít câu có cảm xúc) ...
CALM_TARGET = (0.15, -0.55)     # ... thì nhạc nền nhẹ, êm - nhạc mặc định bật (chủ sách 01-10)
# Đổi bài chỉ ở ranh giới CÓ LÝ DO (docs/MUSIC_RESEARCH.md 06-10, đo bằng music/track_changes2.py): mảnh `reason="length"`
# (chia đều đoạn dài) chơi tiếp bài của đoạn trước; trong một cảnh, bài hết thì nối sang bài ANH EM (gần bài đang chơi) đúng ở
# điểm kết tự nhiên của nó; bài cho đầu cảnh bị phạt nếu ngắn hơn cảnh (phải lặp nhiều vòng).
SIBLING_Z = 0.8                  # z_distance tối đa từ bài anh em tới bài đang chơi (chọn trên bộ 4+5)
SHORT_TRACK_PENALTY = 1.0        # x (1 - độ dài bài / độ dài cảnh): phạt bài ngắn hơn cảnh
SCENE_LENGTH_CAP = 900.0         # độ dài cảnh tính phạt kẹp ở 15 phút
HEAD_CANDIDATES = 30             # số bài xếp hạng xét phạt bài ngắn cho đầu cảnh
SIBLING_CANDIDATES = 50
# Bước âm lượng trong cảnh: mảnh nối tiếp nhích nhạc theo tension của nó so với đầu cảnh; bước sát bước trước thì giữ mức cũ.
STEP_DB_PER_TENSION = 6.0
STEP_MAX_DB = 3.0
STEP_HOLD_SECONDS = 40.0


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


def scene_sigma(scene: dict[str, Any]) -> dict[str, float]:
    """Độ không chắc của đoạn trên từng trục: độ lệch chuẩn các câu trong đoạn (`sd`, thiếu -> SCENE_SD_DEFAULT) cộng độ
    không chắc của đoạn ít câu có cảm xúc, UNCERTAIN_SD x (1 - confidence)."""
    sd = scene.get("sd") if isinstance(scene.get("sd"), dict) else {}
    extra = UNCERTAIN_SD * (1.0 - max(0.0, min(1.0, float(scene.get("confidence") or 0.0))))
    return {axis: math.hypot(float(sd.get(axis) if sd.get(axis) is not None else SCENE_SD_DEFAULT), extra)
            for axis in AXIS_WEIGHTS}


def z_distance(track: dict[str, Any], target: tuple[float, ...], sigma: dict[str, float] | None = None) -> float:
    """Khoảng cách đoạn - bài trên ba trục, mỗi trục (bình phương + VET_VAR_WEIGHT x vetVar) chia (sig_đoạn^2 + sig_bài^2 + TAU^2),
    nhân trọng số trục. Bài chưa có tension thì bỏ trục ấy (danh mục cũ). Bài chưa có `vetVar` (danh mục) thì không có số hạng
    phương sai. `sigma` None -> độ không chắc mặc định của đoạn."""
    sigma = sigma or {axis: SCENE_SD_DEFAULT for axis in AXIS_WEIGHTS}
    track_sd = track.get("sd") if isinstance(track.get("sd"), dict) else {}
    vet_var = track.get("vetVar") if isinstance(track.get("vetVar"), dict) else {}
    means = {"valence": (float(track["valence"]), target[0]), "arousal": (float(track["arousal"]), target[1])}
    if len(target) > 2 and track.get("tension") is not None:
        means["tension"] = (float(track["tension"]), target[2])
    total = 0.0
    for axis, (mine, wanted) in means.items():
        sig_m = float(track_sd.get(axis) if track_sd.get(axis) is not None else TRACK_SD_DEFAULT)
        var = float(vet_var[axis]) if vet_var.get(axis) is not None else 0.0
        total += AXIS_WEIGHTS[axis] * ((mine - wanted) ** 2 + VET_VAR_WEIGHT * var) / (sigma[axis] ** 2 + sig_m ** 2 + TAU ** 2)
    return math.sqrt(total)


def emotion_cosine(wanted: Any, track: Any) -> float | None:
    """Cosine giữa 13 cường độ cảm xúc của đoạn và của bài (khoá thiếu = 0); None nếu một bên không phải dict có dữ liệu
    (đường LLM chưa vào / danh mục cũ) hoặc vectơ bằng 0 - khi đó không có số hạng này."""
    if not isinstance(wanted, dict) or not isinstance(track, dict) or not wanted or not track:
        return None
    a, b = [], []
    for name in music_scenes.EMOTION_CLASSES:
        try:
            a.append(max(0.0, float(wanted.get(name) or 0.0)))
            b.append(max(0.0, float(track.get(name) or 0.0)))
        except (TypeError, ValueError):
            a.append(0.0)
            b.append(0.0)
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / norm if norm > 0 else None


def style_fit(track: dict[str, Any], genre_styles: dict[str, float] | None) -> float:
    """Độ hợp phong cách của bài với thế giới của cuốn (bảng thể loại x phong cách trong danh mục): 1 hợp, 0,5 dùng được,
    0 = LOẠI CỨNG. Chưa chọn thể loại -> không lọc."""
    if not genre_styles:
        return 1.0
    style = track.get("style")
    return float(genre_styles.get(style, 0.0)) if style else 0.5


def score(track: dict[str, Any], target: tuple[float, ...], *, family: str | None, recent: list[str],
          genre_styles: dict[str, float] | None = None, sigma: dict[str, float] | None = None) -> float:
    """Khoảng cách theo độ không chắc (`z_distance`) cộng các phạt; chưa có số hạng cảm xúc (xem `rank`)."""
    distance = z_distance(track, target, sigma)
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
           keep: dict[str, str | None] | None = None, kept_siblings: dict[str, list[str]] | None = None,
           available: Callable[[str], bool] | None = None, silenced: Iterable[str] = (),
           track_info: Callable[[str], dict[str, Any] | None] | None = None) -> list[dict[str, Any]]:
    """Mỗi đoạn kèm `link` (None = im lặng), `distance`, `pinned`. `pins`: {khoá đoạn: link} người dùng ghim
    (khoá = `scene_key`); `banned`: link người dùng đã bỏ (không chọn lại cho cuốn này); `silenced`: khoá các đoạn người
    dùng để im lặng (`silenced: True`).
    `keep`: {khoá đoạn: link đã chọn trước đó (None = đoạn đã im lặng)} - như ghim "mềm": đoạn nào có trong `keep` giữ
    nguyên bài cũ (không tính là ghim), trừ khi bài ấy đã bị bỏ thì chọn lại. Người dùng sửa MỘT đoạn / MỘT bài thì các
    đoạn khác không được đổi bài theo chỉ vì phạt "vừa dùng" lan dọc cuốn.
    `kept_siblings`: {khoá đoạn: link các bài anh em đã nối trong đoạn ấy lần trước} - đoạn nào cả chuỗi từ đầu cảnh tới nó
    vẫn y như lần trước (đầu cảnh giữ bài cũ, các mảnh nối tiếp cũng vậy) thì dùng lại đúng các bài anh em cũ thay vì xếp hạng
    lại: sửa một đoạn chỉ đổi cảnh của đoạn ấy, không đổi bài anh em ở chương khác (và khỏi xếp hạng cả cuốn - nhanh).
    Hai cảnh liền kề không cùng bài, trừ khi người dùng ghim như thế: đầu cảnh chọn theo xếp hạng không lấy bài đang chơi ở
    mảnh trước; đầu cảnh giữ bài cũ mà trùng bài đang chơi thì chọn lại nếu mảnh trước vừa đổi (bản cũ không bị sửa lan).
    `available(link)`: bài có dùng được TRÊN MÁY NÀY không (đã có trong bộ đệm hay tải được) - bài không dùng được thì không
    chọn, đoạn lấy bài hợp nhất kế tiếp thay vì im lặng. Bài ghim vẫn là lựa chọn của người dùng (ghim không bị xoá) nhưng
    lần dựng này đoạn ấy chọn theo xếp hạng và có `pinUnavailable`. None = bài nào cũng dùng được. Mỗi link chỉ hỏi một lần
    trong một lần chọn (hỏi là xem đĩa - cả cuốn xếp hạng hàng trăm nghìn lượt bài).

    Đổi bài chỉ ở ranh giới có lý do: mảnh `reason="length"` cùng chương, sau một đoạn đang có nhạc, CHƠI TIẾP bài ấy
    (`continued: True`, `stepDb` = bước âm lượng so với đầu cảnh) - ghim và im lặng của người dùng vẫn thắng, `keep` thì
    không (mảnh nối tiếp đi theo đầu cảnh). Đầu cảnh chọn bài bằng `rank` cộng phạt bài ngắn hơn cảnh. Trong cảnh, bài chơi
    hết một vòng thì nối sang bài anh em (`SIBLING_Z`, chưa dùng trong chương): `siblings` = [{at (giây trong chương), link}];
    không có thì bài lặp. `track_info(link)`: thông tin bài (độ dài, không khí) cho bài ghim / giữ không qua `rank`."""
    pins = pins or {}
    keep = keep or {}
    banned = set(banned)
    silenced = set(silenced)
    kept_siblings = kept_siblings or {}
    known: dict[str, dict[str, Any] | None] = {}
    if available is not None:
        asked: dict[str, bool] = {}
        ask = available

        def available(link: str) -> bool:
            if link not in asked:
                asked[link] = ask(link)
            return asked[link]

    def usable(link: str | None) -> bool:
        return link is None or available is None or available(link)

    def info(link: str) -> dict[str, Any] | None:
        if link not in known:
            known[link] = track_info(link) if track_info is not None else None
        return known[link]

    def ranked(scene: dict[str, Any], **extra: Any) -> list[dict[str, Any]]:
        found = rank(scene, candidates_near, book_key=book_key, family=family, banned=banned, genre_styles=genre_styles,
                     recent=recent, available=available, **extra)
        for track in found:
            known.setdefault(track["link"], track)
        return found

    def duration(link: str) -> float:
        return float((info(link) or {}).get("duration") or 0.0)

    heads = scene_heads(scenes)
    lengths: dict[int, float] = {}
    for index, head in enumerate(heads):
        lengths[head] = lengths.get(head, 0.0) + _seconds(scenes[index])

    chosen: list[dict[str, Any]] = []
    recent: list[str] = []
    used: set[str] = set()
    playing: str | None = None   # bài đang kêu ở cuối mảnh trước (kể cả bài anh em vừa nối)
    position = 0.0               # giây đã chơi của bài ấy
    head_tension = 0.0
    intact = True                # mảnh trước y như lần dựng trước (bài, vị trí trong bài) - xem `kept_siblings`
    for index, scene in enumerate(scenes):
        if index == 0 or scene.get("chapterId") != scenes[index - 1].get("chapterId"):
            used, playing, position, intact = set(), None, 0.0, True
        key = scene_key(scene)
        result = dict(scene, key=key, pinned=False)
        pin_down = key in pins and not usable(pins[key])
        follows = heads[index] != index and playing is not None
        if key in pins and not pin_down:
            result.update(link=pins[key], pinned=True, distance=None)
        elif key in silenced:
            result.update(link=None, distance=None, silenced=True)
        elif follows:
            result.update(link=playing, distance=None, continued=True)
        else:
            kept = keep.get(key) if key in keep and keep[key] not in banned and usable(keep[key]) else ""
            if kept != "" and (intact or kept is None or kept != playing):
                result.update(link=kept, distance=None)
            else:
                # Cùng một cách xếp hạng với "Đổi bài" (`rank`); đầu cảnh thêm phạt bài ngắn hơn cảnh. Tránh bài đang chơi
                # và bài đoạn kế đang giữ (hai cảnh liền kề không cùng bài); không còn bài nào khác thì mới chấp nhận trùng.
                want = min(lengths[heads[index]], SCENE_LENGTH_CAP)
                ahead = scenes[index + 1] if index + 1 < len(scenes) and heads[index + 1] == index + 1 else None
                after = scene_key(ahead) if ahead and ahead.get("chapterId") == scene.get("chapterId") else None
                avoid = {playing, pins.get(after) or keep.get(after) if after else None} - {None}
                options = ranked(scene, limit=HEAD_CANDIDATES, exclude=avoid) if avoid else []
                options = options or ranked(scene, limit=HEAD_CANDIDATES)
                best = min(options, default=None,
                           key=lambda track: track["score"] + SHORT_TRACK_PENALTY * _shortfall(track, want))
                if best is None and kept:
                    result.update(link=kept, distance=None)  # bài giữ trùng bài đang chơi mà không có bài nào khác
                else:
                    result.update(link=best["link"] if best else None, distance=best["score"] if best else None)
        if pin_down:
            result["pinUnavailable"] = True
        link = result["link"]
        # Cả chuỗi tới đây như lần trước thì bài anh em cũng như lần trước: dùng lại, khỏi xếp hạng.
        same = key in keep and key in kept_siblings and keep[key] == link
        intact = same and (intact if result.get("continued") or link == playing else True)
        if intact and any(old in banned or not usable(old) for old in kept_siblings[key]):
            intact = False  # bài anh em cũ vừa bị bỏ / máy này không lấy được: xếp hạng lại từ đây
        reuse = list(kept_siblings[key]) if intact else None
        if result.get("continued"):
            tension = float(scene.get("tension") or 0.0)
            result["stepDb"] = max(-STEP_MAX_DB, min(STEP_MAX_DB, STEP_DB_PER_TENSION * (tension - head_tension)))
        else:
            if link != playing:
                playing, position = link, 0.0
            head_tension = float(scene.get("tension") or 0.0)
        # Bài chạy qua mảnh này theo thời gian: hết một vòng thì nối bài anh em, không có thì lặp.
        length, elapsed = _seconds(scene), 0.0
        siblings: list[dict[str, Any]] = []
        while playing and length - elapsed > 1e-9:
            track_seconds = duration(playing) or math.inf
            step = min(length - elapsed, track_seconds - position)
            position, elapsed = position + step, elapsed + step
            if position < track_seconds - 1e-9:
                continue
            if reuse is not None:
                sibling = reuse.pop(0) if reuse else None
            else:
                sibling = _sibling(info(playing), ranked(scene, exclude=used | {playing}, limit=SIBLING_CANDIDATES))
            position = 0.0
            if sibling:
                playing = sibling
                used.add(sibling)
                siblings.append({"at": round(float(scene.get("start") or 0.0) + elapsed, 3), "link": sibling})
        if siblings:
            result["siblings"] = siblings
        if link:
            used.add(link)
            # Đoạn kề chọn trúng bài đang chơi: chơi tiếp, không phải bài "mới" (không tính là lặp).
            if not recent or recent[-1] != link:
                recent.append(link)
        chosen.append(result)
    _hold_steps(chosen)
    return chosen


def scene_heads(scenes: list[dict[str, Any]]) -> list[int]:
    """Với mỗi đoạn: vị trí đoạn ĐẦU CẢNH của nó - chính nó nếu mở bằng ranh giới có lý do (mọi `reason` trừ "length") hay là
    đoạn đầu chương; mảnh `length` thuộc cảnh của đoạn trước."""
    heads: list[int] = []
    for index, scene in enumerate(scenes):
        same_chapter = index > 0 and scene.get("chapterId") == scenes[index - 1].get("chapterId")
        heads.append(heads[index - 1] if same_chapter and scene.get("reason") == "length" else index)
    return heads


def _seconds(scene: dict[str, Any]) -> float:
    try:
        return max(0.0, float(scene["end"]) - float(scene["start"]))
    except (KeyError, TypeError, ValueError):
        return 0.0


def _shortfall(track: dict[str, Any], want: float) -> float:
    """Phần cảnh (độ dài `want`) mà bài không phủ nổi trong một vòng: 0 nếu bài dài hơn cảnh hay không biết độ dài."""
    if want <= 0:
        return 0.0
    length = float(track.get("duration") or 0.0) or want
    return max(0.0, 1.0 - length / want)


def _sibling(current: dict[str, Any] | None, candidates: list[dict[str, Any]]) -> str | None:
    """Bài anh em của bài đang chơi: bài đầu tiên (theo xếp hạng cho mảnh này) cách bài ấy không quá SIBLING_Z."""
    if not current or current.get("valence") is None or current.get("arousal") is None:
        return None
    target = (float(current["valence"]), float(current["arousal"]), float(current.get("tension") or 0.0))
    return next((track["link"] for track in candidates if z_distance(track, target) <= SIBLING_Z), None)


def _hold_steps(chosen: list[dict[str, Any]]) -> None:
    """Bước âm lượng cách bước trước (trong cùng cảnh) chưa đủ STEP_HOLD_SECONDS thì giữ mức trước; đầu cảnh về 0."""
    last_at, last_db = -math.inf, 0.0
    for scene in chosen:
        start = float(scene.get("start") or 0.0)
        if not scene.get("continued"):
            last_at, last_db = start, 0.0
            continue
        if start - last_at < STEP_HOLD_SECONDS:
            scene["stepDb"] = last_db
        elif scene["stepDb"] != last_db:
            last_at, last_db = start, scene["stepDb"]
        scene["stepDb"] = round(scene["stepDb"], 2)


def rank(scene: dict[str, Any], candidates_near: Callable[[float, float], Iterable[dict[str, Any]]], *, book_key: str,
         family: str | None = None, banned: Iterable[str] = (), genre_styles: dict[str, float] | None = None,
         recent: list[str] | None = None, exclude: Iterable[str] = (), limit: int = 6,
         available: Callable[[str], bool] | None = None) -> list[dict[str, Any]]:
    """Các bài thay thế cho MỘT đoạn ("Đổi bài"), tốt nhất trước: cùng bộ lọc và cùng điểm với `choose` (bỏ bài đã bỏ,
    bài quá ngắn, phong cách không hợp thế giới của cuốn; điểm = `score` + hoà điểm theo mã sách - số hạng cosine cảm xúc)
    và cùng ngưỡng MAX_Z: bài xa không khí của đoạn thì không gợi ý. `recent`: các bài đã chơi ở mấy đoạn trước; `exclude`: link
    không đưa ra (bài đang chọn). `available(link)` False (máy này không có và không tải được) thì bỏ như bài đã bỏ.
    Mỗi mục: `{...bài, score}`, điểm càng thấp càng hợp."""
    banned, exclude = set(banned), set(exclude)
    target = (*target_of(scene), float(scene.get("tension") or 0.0))
    ceiling = MAX_Z + (FAMILY_PENALTY if family else 0.0)
    sigma = scene_sigma(scene)
    ranked: list[tuple[float, dict[str, Any]]] = []
    seen: set[str] = set()
    for track in candidates_near(target[0], target[1]):
        link = str(track.get("link") or "")
        if not link or link in seen or link in banned or link in exclude:
            continue
        if available is not None and not available(link):
            continue
        seen.add(link)
        if int(track.get("duration") or 0) < MIN_TRACK_SECONDS or style_fit(track, genre_styles) <= 0.0:
            continue
        value = score(track, target, family=family, recent=(recent or [])[-RECENT_SCENES:], genre_styles=genre_styles,
                      sigma=sigma)
        value += _tiebreak(book_key, link)
        if value <= ceiling:  # ngưỡng im lặng chỉ tính trên khoảng cách + phạt; cosine chỉ xếp hạng các bài đã qua ngưỡng
            similarity = emotion_cosine(scene.get("emotions"), track.get("emotions"))
            ranked.append((value - EMOTION_WEIGHT * (similarity or 0.0), track))
    ranked.sort(key=lambda item: item[0])
    return [dict(track, score=round(value, 3)) for value, track in ranked[:limit]]


def scene_key(scene: dict[str, Any]) -> str:
    """Khoá bền của một đoạn: chương + câu đầu. Chia lại đoạn thì đoạn mới có khoá mới (ghim cũ không áp nhầm)."""
    return f"{scene.get('chapterId')}:{scene.get('firstSegment')}"
