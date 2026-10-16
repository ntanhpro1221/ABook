"""Sinh bộ ví dụ DÙNG CHUNG cho đường N0 của nhạc nền theo cảnh (không học sinh): `tests/fixtures/music/n0/`.

Bản Python (`abook/webui/music_scenes.py` + `music_select.py` + `music_plan.chapter_cues`, `text_processing.segment_chapter_text`) và
bản Kotlin của điện thoại (`SceneCues`, `SceneScenes`, `SceneChoose`, `SceneSegmenter`, `SceneMusic`) cùng đọc các file này
(tests/test_music_n0_fixtures.py, SceneMusicTest.kt) và phải ra GIỐNG HỆT: từng đoạn (ranh, lý do, giây ước), bài chọn, bài anh em,
`stopAt`, `stepDb`, các mốc của chương, vòng lặp của bài.

    catalog.json         ô danh mục TỰ DỰNG quanh đích êm (9 ô v 1-3 x a 0-2), thứ tự `near`, hằng số, mẫu khoảng cách / hoà điểm
    case_*.json          mỗi file một "cuốn": chương (chữ + câu), lựa chọn (họ nhạc, thể loại, ghim, bỏ, im lặng, bài không dùng được) và kết quả Python
    regex_cases.json     mỗi regex của cue_kind / hard_break / bracket_is_subhead / subhead_words / is_heading: ca khớp + không khớp, có chữ Việt có dấu
    segmenter_cases.json chữ -> câu của segment_chapter_text (ngoặc kép, nội tâm, gạch thoại, dòng ngăn cảnh, ...)

Chữ và bài trong đây đều TỰ DỰNG (kho công khai): không có chữ truyện, không có link nhạc thật.
Sinh lại (chỉ khi cố ý đổi luật):  runtime/.venv/Scripts/python.exe scripts/music_n0_fixtures.py
Chỉ kiểm file trên đĩa còn khớp mã:  ... scripts/music_n0_fixtures.py --check
"""
from __future__ import annotations

import bisect
import json
import math
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook import text_processing  # noqa: E402
from abook.readaloud import paragraphs as reading_paragraphs  # noqa: E402
from abook.webui import humanize, music_catalog, music_mix, music_plan, music_scenes, music_select  # noqa: E402
from abook.webui.server import MUSIC_TRACK_MAX_BYTES  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "music" / "n0"
TARGET = (0.15, -0.55)
# Cỡ (byte) theo MẢNH `tracks/` của danh mục - ô `cells/` không có `bytes`. Bài trùng toạ độ với bài tốt nhất của ô giữa, nên nếu không lọc cỡ thì chúng thắng:
# nhờ vậy bộ ví dụ thật sự kiểm "bài quá MUSIC_TRACK_MAX_MB không bao giờ được chọn" (server._music_oversize, Kotlin MusicCatalog.usable).
TRACK_BYTES = {"https://example.invalid/n0/big1.mp3": MUSIC_TRACK_MAX_BYTES + 1, "https://example.invalid/n0/big2.mp3": MUSIC_TRACK_MAX_BYTES * 3,
               "https://example.invalid/n0/edge.mp3": MUSIC_TRACK_MAX_BYTES, "https://example.invalid/n0/small.mp3": 5_000_000}
TAXONOMY = {"genres": {"gen_a": {"styles": {"style_a": 1.0, "style_b": 0.5}}, "gen_b": {"styles": {"style_c": 1.0}}}}


# ---- danh mục tự dựng ---------------------------------------------------------------------------------------------------------------
def make_catalog() -> dict[str, list[dict[str, Any]]]:
    """9 ô quanh đích êm (cell_of(.15, -.55) = (2, 1), bán kính 1). Bài tự dựng: link giả, số do bộ sinh cố định hạt giống."""
    rng = random.Random(20261016)
    cells: dict[str, list[dict[str, Any]]] = {}
    families = ["eastern", "orchestral", "piano", "ambient", "acoustic", "electronic", "other"]
    styles = ["style_a", "style_b", "style_c", None]
    sources = ["incompetech", "freepd", "jamendo", "other"]
    number = 0

    def entry(valence: float, arousal: float, tension: float | None, *, duration: Any, family: str | None = None, link: str | None = None) -> dict[str, Any]:
        nonlocal number
        number += 1
        item: dict[str, Any] = {
            "link": link or f"https://example.invalid/n0/t{number:03d}.mp3",
            "valence": valence, "arousal": arousal,
            "style": rng.choice(styles), "family": family or rng.choice(families),
            "background": rng.choice([None, 0.0, 0.3, 0.55, 0.8, 1.0]),
            "duration": duration, "source": rng.choice(sources),
        }
        if tension is not None:
            item["tension"] = tension
        return item

    for vi in range(1, 4):
        for ai in range(0, 3):
            v_low, v_high = -1.0 + vi * 0.4, -1.0 + (vi + 1) * 0.4
            a_low, a_high = -1.0 + ai * 0.4, -1.0 + (ai + 1) * 0.4
            items = []
            for _ in range(14):
                duration = rng.choice([75, 90, 110, 140, 170, 200, 260, 330, 420, 61, 60])
                items.append(entry(round(rng.uniform(v_low + 0.001, v_high - 0.001), 3), round(rng.uniform(a_low + 0.001, a_high - 0.001), 3),
                                   round(rng.uniform(-1.0, 1.0), 3) if rng.random() > 0.08 else None, duration=duration))
            cells[f"{vi}_{ai}"] = items
    centre = cells["2_1"]
    # Ba bài sát đích với hai bản SAO TOẠ ĐỘ (hoà điểm thật, tách bằng `_tiebreak`), độ dài khác nhau để có bài ngắn và bài rất dài.
    for tension, duration in ((-0.1, 150), (-0.1, 150), (-0.1, 95), (0.0, 1800), (0.0, 80)):
        centre.append(entry(0.15, -0.55, tension, duration=duration))
    # Bài ngắn dưới 60 giây (bị loại), bài không biết độ dài (số 0 / thiếu) và bài độ dài thực kiểu float.
    centre.append(entry(0.15, -0.55, -0.1, duration=59))
    centre.append(entry(0.15, -0.55, -0.1, duration=0))
    centre.append(entry(0.16, -0.54, -0.1, duration=119.6))
    # Một bài nằm ở HAI ô (link trùng: `seen` giữ lần gặp đầu).
    cells["3_2"].append(dict(centre[-1]))
    # Bài quá cỡ (và bài đúng bằng trần - còn dùng được) ngay tại đích, cùng tension với bài tốt nhất.
    for link in TRACK_BYTES:
        centre.append(entry(0.15, -0.55, 0.0, duration=1800, link=link))
    # Họ nhạc: vài bài sát đích mang họ "piano" và "eastern" (cho lựa chọn family).
    for family, tension in (("piano", -0.1), ("eastern", -0.05)):
        cells["1_1"].append(entry(0.1, -0.5, tension, duration=240, family=family))
    return cells


def near_of(cells: dict[str, list[dict[str, Any]]]) -> music_catalog.MusicCatalog:
    """`MusicCatalog` thật (hàm `near` thật) nhưng ô lấy từ bộ tự dựng."""
    class Fake(music_catalog.MusicCatalog):
        def __init__(self) -> None:  # noqa: D107 - không gọi super: không có thư mục đệm
            pass

        def manifest(self, *, refresh: bool = False) -> dict[str, Any]:
            return {"grid": 5, "cells": {name: len(items) for name, items in cells.items()}}

        def cell(self, valence_index: int, arousal_index: int) -> list[dict[str, Any]]:
            return list(cells.get(f"{valence_index}_{arousal_index}", []))

    return Fake()


def catalog_file(cells: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    catalog = near_of(cells)
    order = [item["link"] for item in catalog.near(*TARGET, radius=1)]
    scene = {"valence": 0.0, "arousal": 0.0, "tension": 0.0, "confidence": 0.0, "sd": {"valence": 0.0, "arousal": 0.0, "tension": 0.0}}
    target = (*music_select.target_of(scene), 0.0)
    sigma = music_select.scene_sigma(scene)
    samples = []
    for item in catalog.near(*TARGET, radius=1)[:40]:
        samples.append({"link": item["link"], "z": music_select.z_distance(item, target, sigma),
                        "score": music_select.score(item, target, family=None, sigma=sigma),
                        "tiebreak": music_select._tiebreak("book-alpha", item["link"])})
    return {
        "cells": cells, "taxonomy": TAXONOMY, "nearOrder": order,
        "constants": {
            "target": list(target), "sigma": [sigma["valence"], sigma["arousal"], sigma["tension"]],
            "penaltyUnit": music_select.PENALTY_UNIT, "styleHalfPenalty": music_select.STYLE_HALF_PENALTY,
            "familyPenalty": music_select.FAMILY_PENALTY, "foregroundPenalty": music_select.FOREGROUND_PENALTY,
            "recentPenalty": music_select.RECENT_PENALTY,
        },
        "samples": samples, "trackBytes": TRACK_BYTES, "maxBytes": MUSIC_TRACK_MAX_BYTES,
        "mix": {"tailMinSeconds": music_select.TAIL_MIN_SECONDS, "cueMergeGapSeconds": music_select.CUE_MERGE_GAP_SECONDS,
                "loopCrossfadeSeconds": music_mix.LOOP_CROSSFADE_SECONDS},
    }


# ---- chữ tự dựng --------------------------------------------------------------------------------------------------------------------
SUBJECTS = ["Lan", "Minh", "người lính gác", "bà chủ quán", "cậu bé", "con mèo xám", "Hạ Vân", "ông thầy đồ", "đội thương nhân", "cô nương áo xanh"]
VERBS = ["bước qua", "đứng nhìn", "mang về", "lặng lẽ mở", "nhặt lên", "giấu kỹ", "đặt xuống", "gói lại", "xem xét"]
OBJECTS = ["chiếc hộp gỗ", "bức thư cũ", "cây đèn dầu", "tấm bản đồ rách", "bó thảo dược", "chùm chìa khoá", "chén trà nguội", "con dấu đồng"]
PLACES = ["ở góc sân", "bên bờ suối", "sau cánh cửa mục", "trong gian bếp tối", "dưới gốc đa già", "trước cổng làng", "giữa chợ sớm"]
ENDINGS = [".", ".", ".", "!", "?", "…"]


def sentence(rng: random.Random) -> str:
    return _capital(f"{rng.choice(SUBJECTS)} {rng.choice(VERBS)} {rng.choice(OBJECTS)} {rng.choice(PLACES)}{rng.choice(ENDINGS)}")


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def line(rng: random.Random, sentences: int, extra: str = "") -> str:
    text = " ".join(sentence(rng) for _ in range(sentences))
    return f"{text} {extra}".strip()


def paragraphs(rng: random.Random, count: int, sentences: tuple[int, int] = (2, 4), extra: str = "") -> list[str]:
    return [line(rng, rng.randint(*sentences), extra if index % 7 == 3 else "") for index in range(count)]


def chapter_text(blocks: list[str | tuple[str, int]], rng: random.Random) -> str:
    """Chương từ các khối: chuỗi = nguyên dòng (đứng riêng một đoạn); (kiểu, n) = n đoạn chữ."""
    out: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            out.append(block)
        else:
            kind, count = block
            extra = "🌸 𠀋 🌸" if kind == "emoji" else ""
            out.extend(paragraphs(rng, count, extra=extra))
    return "\n\n".join(out) + "\n"


def chapter_script(chapter_id: int, title: str, text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Kịch bản trần như `music_nnscene.chapter_script`: câu của `segment_chapter_text`, chỉ id / text / kind / sceneBreak."""
    rows = text_processing.segment_chapter_text(chapter_id, text)
    segments = []
    for index, row in enumerate(rows):
        segments.append({"id": int(row["seq"]), "text": str(row["text"]),
                         "kind": "heading" if index == 0 and humanize.is_heading(str(row["text"])) else "narration",
                         **({"sceneBreak": True} if row.get("scene_break") else {})})
    return {"chapterId": chapter_id, "title": title, "segments": segments}, rows


def _letters(text: str) -> int:
    return sum(1 for char in text if unicodedata.category(char)[0] in "LN")


def paragraph_ids(sentences: list[str], body: str) -> list[int]:
    """Bản sao `music_nnscene.paragraph_ids` (dev/nnscene, chưa vào main): mã đoạn của màn đọc chứa chỗ mỗi câu bắt đầu. Khi nnscene vào main thì gọi thẳng."""
    pieces = reading_paragraphs.split_paragraphs(body)
    if not pieces:
        return [0] * len(sentences)
    starts, total = [], 0
    for piece in pieces:
        starts.append(total)
        total += _letters(piece.text)
    spoken = sum(_letters(text) for text in sentences)
    scale = total / spoken if spoken and total else 1.0
    out, seen = [], 0
    for text in sentences:
        out.append(max(0, bisect.bisect_right(starts, round(seen * scale)) - 1))
        seen += _letters(text)
    return out


def first_segments(chapter: dict[str, Any], chosen: list[dict[str, Any]], cues: list[dict[str, Any]]) -> list[int | None]:
    """`music_nnscene.chapter_cues`: mốc mở một cảnh mang mã đoạn màn đọc nơi cảnh bắt đầu (mốc nối bài anh em: None)."""
    by_sentence = {segment["id"]: chapter["paragraphIds"][index] for index, segment in enumerate(chapter["segments"])}
    heads = {scene["key"]: by_sentence.get(scene.get("firstSegment"), 0) for scene in chosen if scene.get("chapterId") == chapter["chapterId"]}
    return [None if cue.get("sibling") or cue["key"] not in heads else heads[cue["key"]] for cue in cues]


def seg(sid: int, text: str, kind: str = "narration", scene_break: bool = False) -> dict[str, Any]:
    return {"id": sid, "text": text, "kind": kind, **({"sceneBreak": True} if scene_break else {})}


# ---- chạy đường N0 trên Python ---------------------------------------------------------------------------------------------------------
def n0_plan(scripts: list[dict[str, Any]], cells: dict[str, list[dict[str, Any]]], *, book_key: str, family: str | None = None,
            genre: str | None = None, pins: dict[str, str] | None = None, banned: list[str] | None = None,
            silenced: list[str] | None = None, unavailable: list[str] | None = None,
            size_cap: bool = True) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenes = music_scenes.book_scenes(scripts, None, None, None)
    for scene in scenes:  # đường N0 = mọi số cảm xúc là hằng; Kotlin viết tắt bằng hằng nên mất hằng thì fixture phải báo
        assert (scene["valence"], scene["arousal"], scene["tension"], scene["confidence"], scene["sd"]) == (
            0.0, 0.0, 0.0, 0.0, {"valence": 0.0, "arousal": 0.0, "tension": 0.0}), scene
        assert scene["moodSource"] == "labels", scene
    catalog = near_of(cells)
    styles = (TAXONOMY["genres"].get(genre) or {}).get("styles") if genre else None
    blocked = set(unavailable or [])

    def available(link: str) -> bool:  # như server.music_track_available: bài đã chặn hay quá cỡ theo mảnh `tracks/` thì không
        return link not in blocked and not (size_cap and music_catalog.over_size_cap({"bytes": TRACK_BYTES.get(link)}, MUSIC_TRACK_MAX_BYTES))

    chosen = music_select.choose(scenes, lambda v, a: catalog.near(v, a, radius=1), book_key=book_key, family=family, pins=pins,
                                 banned=banned or (), genre_styles=styles, silenced=silenced or (),
                                 available=available)
    return scenes, chosen


def scene_json(scene: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapterId": scene["chapterId"], "firstSegment": scene["firstSegment"], "lastSegment": scene["lastSegment"],
        "start": scene["start"], "end": scene["end"], "reason": scene["reason"], "lines": scene["lines"], "key": scene["key"],
        "pinned": scene["pinned"], "link": scene["link"], "distance": scene["distance"], "continued": bool(scene.get("continued")),
        "silenced": bool(scene.get("silenced")), "pinUnavailable": bool(scene.get("pinUnavailable")), "stepDb": scene.get("stepDb"),
        "stopAt": scene.get("stopAt"), "siblings": [{"at": s["at"], "link": s["link"]} for s in scene.get("siblings") or []],
    }


def loops_of(chosen: list[dict[str, Any]], cells: dict[str, list[dict[str, Any]]]) -> dict[str, list[Any]]:
    by_link: dict[str, dict[str, Any]] = {}
    for items in cells.values():
        for item in items:
            by_link.setdefault(item["link"], item)
    links = sorted({link for scene in chosen for link in [scene.get("link")] + [s["link"] for s in scene.get("siblings") or []] if link})
    out = {}
    for link in links:
        track = by_link.get(link) or {}  # bài ghim ngoài danh mục: không biết độ dài
        first, last, period, crossfade = music_mix.loop_bounds(track.get("seconds") or track.get("duration"), track.get("audibleStart"), track.get("audibleEnd"))
        out[link] = [None if math.isinf(x) else x for x in (first, last, period)] + [crossfade]
    return out


def case_file(name: str, chapters_file: str, chapters: list[dict[str, Any]], cells: dict[str, list[dict[str, Any]]], **options: Any) -> dict[str, Any]:
    scripts = [{"chapterId": ch["chapterId"], "segments": ch["segments"]} for ch in chapters]
    book_key = options["book_key"]
    scenes, chosen = n0_plan(scripts, cells, **options)
    plan = {"enabled": True, "scenes": chosen}
    cues, unclamped, heads = {}, {}, {}
    for ch in chapters:
        seconds = round(sum(music_scenes._durations(ch["segments"])), 3)
        ch["seconds"] = seconds
        cues[str(ch["chapterId"])] = music_plan.chapter_cues(plan, ch["chapterId"], seconds)
        unclamped[str(ch["chapterId"])] = music_plan.chapter_cues(plan, ch["chapterId"])
        if "paragraphIds" in ch:
            heads[str(ch["chapterId"])] = first_segments(ch, chosen, cues[str(ch["chapterId"])])
    return {
        "name": name, "bookKey": book_key, "chaptersFile": chapters_file,
        "options": {key: value for key, value in options.items() if key != "book_key" and value},
        "expected": {"scenes": [scene_json(scene) for scene in chosen], "cues": cues, "cuesUnclamped": unclamped, "firstSegments": heads,
                     "loops": loops_of(chosen, cells)},
    }


def build_cases(cells: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rng = random.Random(7)
    texts: dict[int, str] = {}
    # Chương 1: tiêu đề, dòng ngăn cảnh nhiều kiểu, tiêu đề phụ ngoặc / POV / gạch, cảnh đầu và cảnh giữa ngắn (gộp), cảnh dài.
    texts[1] = chapter_text(["Chương 1: Cổng thành", ("p", 2), "***", ("p", 9), "* * *", ("p", 1), "[Yuki POV]", ("p", 8), "— Phần hai —", ("p", 10),
                             "◆", ("p", 2), "◇◇◇", ("p", 7), "Góc nhìn của Minh", ("p", 9), "---", ("p", 3)], rng)
    # Chương 2: một mạch dài (cắt thành nhiều mảnh "length"), nhảy thời gian, "Trong khi đó" (không cắt), dòng ngăn cảnh, đuôi ngắn.
    texts[2] = chapter_text([("p", 34), "Sáng hôm sau, Lan dậy rất sớm và đi ra cổng.", ("p", 12), "Trong khi đó, ở một nơi khác, người lính vẫn đứng gác.",
                             ("p", 9), "Ba ngày sau, đội thương nhân tới.", ("p", 11), "◆", ("p", 3), "Phần 3", ("p", 8), "Mấy ngày sau chuyện đã lắng.", ("p", 1)], rng)
    # Chương 3: ngắn (< 60 giây), có ký tự ngoài BMP.
    # Thêm một đoạn dài hơn 340 ký tự (một đoạn màn đọc -> nhiều câu) và vài dòng thoại / nội tâm, để ánh xạ câu -> đoạn không chỉ là 1-1.
    long_line = line(random.Random(99), 9)
    texts[3] = chapter_text(["Chapter 3 - Cổng sau", ("emoji", 3), long_line, "“Cậu đi đâu đấy?” Lan hỏi. Minh không đáp.", "‘Mình phải đi thôi,’ Minh nghĩ."], rng)
    # Chương 4: nhiều cảnh vừa phải, ký tự ngoài BMP rải đều (độ dài đoạn phụ thuộc đếm code point), dòng "-o0o-" và "— Hết —".
    texts[4] = chapter_text([("emoji", 12), "-o0o-", ("emoji", 14), "— Hết —", ("emoji", 4), "[Hệ thống: Nhiệm vụ mới]", ("emoji", 10), "※", ("emoji", 13)], rng)
    # Chương 5: chữ giống hệt chương 1 (bài chọn theo mã sách và "vừa dùng" khác nhau, không phụ thuộc chữ).
    texts[5] = texts[1].replace("Chương 1: Cổng thành", "Chương 5: Trở lại")
    chapters = []
    for chapter_id in (1, 2, 3, 4, 5):
        script, _rows = chapter_script(chapter_id, f"Chương {chapter_id}", texts[chapter_id])
        chapters.append({"chapterId": chapter_id, "title": script["title"], "text": texts[chapter_id], "segments": script["segments"],
                         "paragraphIds": paragraph_ids([segment["text"] for segment in script["segments"]], texts[chapter_id])})

    # Không lọc cỡ thì bài quá cỡ thắng ít nhất một đoạn (ví dụ có tác dụng); lọc rồi thì không đoạn nào dùng bài quá cỡ.
    unfiltered = n0_plan([{"chapterId": ch["chapterId"], "segments": ch["segments"]} for ch in chapters], cells, book_key="book-alpha", size_cap=False)[1]
    assert any(TRACK_BYTES.get(scene["link"], 0) > MUSIC_TRACK_MAX_BYTES for scene in unfiltered), "bài quá cỡ không bao giờ thắng: ví dụ vô nghĩa"
    cases = {"alpha": case_file("alpha", "chapters_main.json", chapters, cells, book_key="book-alpha"),
             "beta": case_file("beta", "chapters_main.json", chapters, cells, book_key="book-beta")}
    base = cases["alpha"]["expected"]["scenes"]
    linked = [scene for scene in base if scene["link"]]
    banned = [linked[0]["link"], linked[3]["link"]]
    pins = {linked[1]["key"]: linked[5]["link"], linked[6]["key"]: linked[7]["link"], linked[9]["key"]: "https://example.invalid/n0/t999.mp3"}
    silenced = [linked[2]["key"], linked[8]["key"]]
    unavailable = [linked[4]["link"], linked[7]["link"], linked[1]["link"]]
    cases["options"] = case_file("options", "chapters_main.json", chapters, cells, book_key="book-alpha", family="piano", genre="gen_a", banned=banned, pins=pins,
                                 silenced=silenced, unavailable=unavailable)
    cases["family"] = case_file("family", "chapters_main.json", chapters, cells, book_key="book-gamma", family="eastern", genre="gen_b")
    hand = handmade_chapters()
    cases["handmade"] = case_file("handmade", "chapters_handmade.json", hand, cells, book_key="book-hand")
    return cases, {"chapters_main.json": chapters, "chapters_handmade.json": hand}


def handmade_chapters() -> list[dict[str, Any]]:
    """Câu dựng tay: tiêu đề GIỮA chương, dòng ngăn cảnh là câu, cờ sceneBreak có sẵn của sách, câu rỗng / chỉ ký hiệu, đoạn đúng 60 và 180 giây."""
    def run(first: int, count: int, chars: int, word: str = "chữ") -> list[dict[str, Any]]:
        return [seg(first + index, (word + " ") * (chars // (len(word) + 1))) for index in range(count)]

    # Mỗi câu 923 ký tự ~ 60 giây (923 x 0,065 = 59,995): kề mốc 60.
    chapter1 = run(0, 2, 923) + [seg(2, "Chương hai", "heading")] + run(3, 3, 400) + [seg(6, "***")] + run(7, 4, 300)
    chapter2 = [seg(0, "Mở đầu", "heading")] + run(1, 3, 1000) + [seg(4, "Cuối cảnh", scene_break=True)] + run(5, 5, 900) + [seg(10, "Đêm sau, chuyện lạ xảy ra.")] + run(11, 2, 200)
    chapter3 = [seg(0, "Chỉ một câu rất ngắn.")]
    chapter4 = [seg(0, "Chương bốn", "heading"), seg(1, "[POV Lan]"), seg(2, "Phần hai: Cửa ải"), seg(3, "Sau khi ăn xong họ rời đi.")] + run(4, 6, 700)
    chapter5 = run(0, 4, 2800) + run(4, 2, 2800)  # mỗi câu 182 giây: một đoạn 6 câu / nhiều lần chia
    return [{"chapterId": 11, "title": "t11", "segments": chapter1}, {"chapterId": 12, "title": "t12", "segments": chapter2},
            {"chapterId": 13, "title": "t13", "segments": chapter3}, {"chapterId": 14, "title": "t14", "segments": chapter4},
            {"chapterId": 15, "title": "t15", "segments": chapter5}]


# ---- ca regex -----------------------------------------------------------------------------------------------------------------------
REGEX_STRINGS = [
    # SEPARATOR / CUE_SYMBOLS
    "***", "* * *", "  ***  ", "~~~", "###", "===", "___", "- - -", "---", "·••", "ooo", "o0O", "OOO", "000", "o O o", "oOo", "◇", "◆◆◆", "※", "✦ ✦", "＊＊＊", "◇ ◆ ○", "●", "♦",
    "**", "*", "-", "a***", "*** a", "***\n", "\n***", "o", "oo", "***　", " *** ", "* * *",
    # TIME_JUMP / CUE_TIME_PLACE
    "Sáng hôm sau, họ đi.", "sáng hôm sau", "SÁNG HÔM SAU", "Tối sau đó", "Đêm hôm sau trời mưa", "Hôm sau", "Ngày hôm sau", "Ngày sau", "Sáng sớm hôm sau", "Trưa sau nữa",
    "Ba ngày sau, chuyện lắng xuống.", "Mấy tuần sau", "Vài tháng sau", "5 ngày sau", "12 năm sau", "Một canh giờ sau", "Bảy năm sau", "Chín ngày sau", "Mười ngày sau",
    "The next morning, she left.", "next day", "A few days later", "Several weeks later", "3 months later", "Two days later", "— Ba ngày sau", "...Ba ngày sau", "“Hôm sau",
    "Trong khi đó, ở xa", "TRONG KHI ĐÓ", "Cùng lúc đó", "Cùng lúc ấy", "Lúc ấy ở cổng thành", "Lúc đó ở phía nam", "Vài giờ sau", "Mấy tiếng sau", "Hai phút sau", "Sáng hôm ấy", "Chiều ngày đó",
    "Ngày hôm đó", "Quay lại với Lan", "Trở lại với Minh", "Ở một nơi khác", "Tại một nơi khác", "Sau đó vài ngày", "Sau khi ăn", "Hôm qua", "Đêm qua", "Đêm nay",
    # CUE_SUBHEAD / subhead_words / CUE_HEAD_WORD / CUE_NUMERAL
    "Góc nhìn của Minh", "GÓC NHÌN CỦA LAN", "Góc nhìn thứ ba", "POV Lan", "pov: Yuki", "POVERTY", "Phần hai", "Phần 3", "Phần II", "Phần thứ hai", "Phần thứ 2", "Phần 1: Khởi đầu",
    "Phần II: Bóng tối", "Phần 3 - Cuộc gặp gỡ", "Phần thưởng:", "Phần thưởng đã tới.", "Phần lớn", "Phần", "Phần:", "Phần 4:", "Phần ba mươi", "Phần cuối", "Phần kết", "Phần đầu",
    "Interlude", "interlude 2", "Side story", "side-story", "Sidestep", "Phía sau lưng hắn…", "Phía bắc", "Phía sau", "Phía:", "Phần hai.", "phần hai", "PHẦN HAI", "Phầnhai",
    # CUE_BRACKETED / bracket_is_subhead / CUE_BRACKET_POV / CUE_DECOR / CUE_NAME_PUNCT / CUE_VIET_LETTERS / CUE_END_WORDS
    "[Yuki POV]", "[Góc nhìn của Lan]", "[Hệ thống: Nhiệm vụ mới]", "[Side: Minh]", "[Sidekick]", "【Nhiệm vụ】", "【Góc nhìn Lan】", "「Ừ」", "「POV」", "[ ]", "[]", "[12]", "[POV]", "[pov]",
    "— Phần hai —", "-o0o-", "– Lizz nói –", "– Đừng lại gần. –", "— Hết —", "—end—", "—Fin—", "—Nanato—", "— Selia —", "—Rầm—", "— Vâng —", "— Hoàng Thượng —", "— Nguyễn Văn Nam —",
    "— Một Hai Ba Bốn —", "— Chương 5 —", "— Chương năm —", "—II—", "—iv.—", "—12.—", "- Hết chương -", "—Quyển hạ—", "—Epilogue—", "—Kết—", "—Ngoại truyện—", "—Ngoại  truyện—", "—Mở đầu—", "—Vĩ thanh—",
    "—0●0—", "—o0o—", "— ○ —", "—— xin chào ——", "-- Hết --", "— Đêm nay —", "— Ánh Sáng —", "— ÁNH SÁNG —", "—Ôi—", "—Đ—", "—Ê Ê Ê—", "—ABC—",
    "—a, b—", "—Lan!—", "—Lan?—", "— Lan… —", "—“Lan”—", "—Lan*—", "—Lan:—",
    # CUE_PLAIN_END / chữ cuối câu
    "Phần 4:", "Phần hai…", "Phần hai!", "Phần hai?", "Phần hai,", "Phần hai;", "Phần hai”", "Phần hai)", "Phần hai'", "Phần hai’", "Phần hai.\n", "Phần hai \n",
    # chữ có dấu / hoa thường / ký tự lạ, ký tự ngoài BMP
    "Sáng hôm sau 🌸", "🌸 Sáng hôm sau", "𠀋 Phần hai", "Phần hai 𠀋", "Đêm sau", "ĐÊM SAU", "đêm sau", "Ðêm sau", "Sáng hôm sau", "Sáng　hôm　sau", "Sáng hôm sau",
    "Ngày sau", "\u0085Sáng hôm sau", "​Sáng hôm sau", "Sáng hôm sau", "Hô̂m sau",
]
HEADINGS = ["Chương 1", "Chương 12: Cổng thành", "chương 5 - nhỏ", "CHƯƠNG 7. Mở", "Chapter 3 - Cổng sau", "Chapter IV", "Hồi 2", "Quyển 3: Gió", "Phần 2 · Núi", "Tiết 9", "Chương", "Chương một", "Chương X: Tên",
            "Chương 5 — Tên dài", "Chương 5 | Đường về", "Chương12", "Chương 1" + "x" * 200, "Prologue", "Phần hai", "Tập 3", "  Chương 8  ", "Chương 1a", "Chương IVX Đảo", "Hồi CL: lạ", "Chương 3.", "Chương 3 (1)"]


def regex_cases() -> dict[str, Any]:
    out = []
    for text in REGEX_STRINGS + HEADINGS:
        item: dict[str, Any] = {"text": text}
        stripped = text.strip()
        item["SEPARATOR"] = bool(music_scenes.SEPARATOR.match(text))
        item["TIME_JUMP"] = bool(music_scenes.TIME_JUMP.match(text))
        item["CUE_SYMBOLS"] = bool(music_scenes.CUE_SYMBOLS.match(text))
        item["CUE_SUBHEAD"] = bool(music_scenes.CUE_SUBHEAD.match(text))
        item["CUE_BRACKETED"] = bool(music_scenes.CUE_BRACKETED.match(text))
        item["CUE_BRACKET_POV"] = bool(music_scenes.CUE_BRACKET_POV.search(text))
        item["CUE_DECOR"] = bool(music_scenes.CUE_DECOR.match(text))
        item["CUE_HEAD_WORD"] = bool(music_scenes.CUE_HEAD_WORD.match(text))
        item["CUE_NUMERAL"] = bool(music_scenes.CUE_NUMERAL.match(text))
        item["CUE_NAME_PUNCT"] = bool(music_scenes.CUE_NAME_PUNCT.search(text))
        item["CUE_VIET_LETTERS"] = bool(music_scenes.CUE_VIET_LETTERS.search(text))
        item["CUE_PLAIN_END"] = bool(music_scenes.CUE_PLAIN_END.search(text))
        item["CUE_TIME_PLACE"] = bool(music_scenes.CUE_TIME_PLACE.match(text))
        item["bracketIsSubhead"] = music_scenes.bracket_is_subhead(text)
        item["subheadWords"] = music_scenes.subhead_words(stripped)
        item["cueKind"] = music_scenes.cue_kind({"text": text, "kind": "narration"})
        item["cueKindHeading"] = music_scenes.cue_kind({"text": text, "kind": "heading"})
        item["isHeading"] = humanize.is_heading(text)
        prev_plain = {"text": "x", "sceneBreak": True}
        prev_cue = {"text": "x", "sceneBreak": True, "sceneSource": "cue", "sceneCue": "subhead"}
        item["hardBreak"] = music_scenes.hard_break({"text": text, "kind": "narration"}, None)
        item["hardBreakPlain"] = music_scenes.hard_break({"text": text, "kind": "narration"}, prev_plain)
        item["hardBreakCue"] = music_scenes.hard_break({"text": text, "kind": "narration"}, prev_cue)
        out.append(item)
    return {"cases": out}


# ---- ca tách câu --------------------------------------------------------------------------------------------------------------------
SEGMENTER_TEXTS = [
    "Lan bước vào quán. Bà chủ nhìn cô.\n\nLan hỏi: “Có phòng trống không?” Bà chủ gật đầu.",
    "“Anh đi đâu đấy?” Minh hỏi. “Tôi đi chợ,” Lan đáp. “Về sớm nhé.”",
    "“Hôm nay trời đẹp quá!” Cô nhìn ra cửa sổ, “mà lòng vẫn nặng.”",
    "— Anh đi đâu đấy?\n— Tôi đi chợ.\n- Về sớm nhé.\n–Ừ.",
    "Hắn bước vào. Hắn nhìn quanh.\n\n- Có ai không?\n\nKhông ai đáp.",
    "‘Mình phải đi thôi,’ Lan nghĩ thầm. Rồi cô đứng dậy.",
    "'Chà, chắc mình phải chăm chỉ thêm thôi.'\n\nMinh gõ cửa.",
    "Lan nói với Ma'at rằng I'm fine, rồi đi.",
    "「Ừ. Hiểu rồi.」 Minh gật đầu. 「Mai gặp lại.」",
    "『Hệ thống đã khởi động』\n\nLan mở mắt.",
    "[Bạn đã lên cấp.]\n\n【Nhiệm vụ mới】\n\nLan đọc bảng thông báo.",
    "[Note: Mình dịch chương này hơi vội]\n\nLan tới nơi.",
    "[Tên Dài Của Bảng]\n\n[Lớp A]\n\n[Hmm]\n\n[Kkkkk]\n\n[Ôi!!]",
    "Gió thổi.\n\n***\n\nTrời tối.\n\n◆\n\nSáng hôm sau.",
    "Gió thổi.\n***\nTrời tối.\n* * *\nTrời sáng.",
    "***\n\nGió thổi.\n\n***",
    "Gió thổi.\n\n*\n\nTrời tối.\n\n-\n\nTrời sáng.\n\n--\n\nHết.",
    "Gió thổi.\n\n...\n\n“...”\n\nTrời tối.",
    "Cô nói “thợ săn” rồi cười. Họ gọi tôi là “đội trưởng,” đơn giản vì thế.",
    "Cô đọc “Cơ hội hoàn hảo”? Rồi lắc đầu.",
    "“Haha! “Cậu sẽ bị phạt” chứ gì? Cứ làm đi!” Cô cười.",
    "“Một câu nói chưa đóng ngoặc.\n\nLan tiếp tục đi.\n\nMinh quay lại.",
    "“Một câu nói dài\n\n“Tiếp theo đây” Lan đáp.\n\nCô đi.",
    "Lan nói: “Đừng lo.\" rồi đi.",
    "\"Anh ơi\" cô gọi. \"Đợi em với\" cô nói thêm.",
    "Một dòng có dấu \" lẻ loi.\n\nDòng tiếp theo.",
    "Câu thứ nhất. Câu thứ hai. " * 40,
    ("Một câu rất dài không có dấu chấm nào để cắt " * 12) + "kết thúc.",
    "Lan  nói    nhiều   khoảng trắng.\n\n\n\nVà   nhiều dòng trống.\n \n \nHết.",
    "Đây là dòng một\nđây là dòng hai bị bẻ\ndòng ba.",
    "Dòng [note123] có chú thích [Note54360] và [note].\n\nHết.",
    "Zero​width‍text‌ với﻿ ký tự ẩn.\n\nHết.",
    "NBSP giữa  chữ.\n\nDòng\r\nCRLF.\r\rHết.",
    "Dòng có ngắt dòng Unicode và\u0085nữa.",
    "“Ừ.” “Cô chắc chứ?” “Chắc.”",
    "“a”, “b”, “c” là ba chữ.",
    "Anh đọc “Lan”.",
    "“Lan”. Rồi anh đi.",
    "Chương này có cả chữ Hán 北京 và emoji 🌸 trong câu 𠀋.",
    "(Mình không nên nói ra.)\n\n(Hừm) Lan nghĩ.",
    "Lan đến.\n\n— Chào.\n\nHắn đã nhảy tránh được.\n\n-bởi vì hắn đã thấy trước.\n\n“Ừ.”",
    "“Một.”\n“Hai.”\n“Ba.”\n“Bốn.”\n“Năm.”\n“Sáu.”\n“Bảy.”\n“Tám.”\n“Chín.”\n“Mười.”\n-Hoặc không, vì hắn đã nhảy tránh được.\n- Hắn đã chạy vội về phía cổng.\nCô lùi lại.",
    "Hắn nói “không\n\nLan đáp “có” và “nữa\n\nHết rồi.",
    "Không ngoặc đóng: “mở rồi quên.\n\nĐoạn hai.\n\nĐoạn ba.\n\n“Đoạn bốn mở lại.” Xong.",
    "Dòng cuối là ***\n\n***",
    "Lan thì thầm ‘đừng đi’ rồi ‘ở lại’ và khóc.",
    "Gió “thổi” ‘mạnh’ và \"rất\" mạnh.",
    "Hết chương. Ủng hộ mình tại momo 0123456789.",
    "Dịch: NicK\n\nLan bước đi.",
    "Câu 1: abc, câu 2: def; câu 3! Câu 4? Câu 5… Câu 6.",
    "x" * 700,
    ("a" * 100 + " ") * 9,
    ("Lời. " * 70 + "\n\n") * 3,
]


def segmenter_cases() -> dict[str, Any]:
    out = []
    for text in SEGMENTER_TEXTS:
        try:
            rows = text_processing.segment_chapter_text(7, text)
            expected = [{"id": int(row["seq"]), "text": row["text"], "sceneBreak": bool(row["scene_break"])} for row in rows]
            item = {"text": text, "segments": expected}
        except RuntimeError as error:
            item = {"text": text, "error": str(error)[:60]}
        out.append(item)
    return {"cases": out}


# ---- ghi ----------------------------------------------------------------------------------------------------------------------------
def dump(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def build() -> dict[str, bytes]:
    cells = make_catalog()
    files = {"catalog.json": dump(catalog_file(cells)), "regex_cases.json": dump(regex_cases()), "segmenter_cases.json": dump(segmenter_cases())}
    cases, chapters = build_cases(cells)
    for name, case in cases.items():
        files[f"case_{name}.json"] = dump(case)
    for name, value in chapters.items():
        files[name] = dump({"chapters": value})
    return files


def coverage(files: dict[str, bytes]) -> dict[str, Any]:
    """Các nhánh mà bộ ví dụ phải chạm tới, để một lần sinh lại không lặng lẽ mất độ phủ."""
    reasons: dict[str, int] = {}
    seen = {"siblings": 0, "stopAt": 0, "continued": 0, "silenced": 0, "pinned": 0, "pinUnavailable": 0, "noLink": 0, "stepDb": 0}
    for name, raw in files.items():
        if not name.startswith("case_"):
            continue
        for scene in json.loads(raw)["expected"]["scenes"]:
            reasons[scene["reason"]] = reasons.get(scene["reason"], 0) + 1
            seen["siblings"] += bool(scene["siblings"])
            seen["stopAt"] += scene["stopAt"] is not None
            seen["continued"] += scene["continued"]
            seen["silenced"] += scene["silenced"]
            seen["pinned"] += scene["pinned"]
            seen["pinUnavailable"] += scene["pinUnavailable"]
            seen["noLink"] += scene["link"] is None
            seen["stepDb"] += scene["stepDb"] is not None
    return {"reasons": reasons, **seen}


def main(argv: list[str]) -> int:
    files = build()
    if "--check" in argv:
        stale = [name for name, raw in files.items() if not (OUT / name).is_file() or (OUT / name).read_bytes() != raw]
        stale += [path.name for path in OUT.glob("*.json") if path.name not in files]
        print("khớp" if not stale else f"LỆCH: {stale}")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (OUT / name).write_bytes(raw)  # LF, UTF-8 (không dùng write_text: Windows ghi CRLF)
    print(json.dumps(coverage(files), ensure_ascii=False))
    print(f"đã ghi {len(files)} file vào {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
