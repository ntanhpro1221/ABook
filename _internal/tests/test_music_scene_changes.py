"""Nhạc nền đổi bài chỉ ở ranh giới CÓ LÝ DO (docs/MUSIC_RESEARCH.md 06-10, đo bằng music/track_changes2.py): dấu hiệu đổi
cảnh trong chữ thành cờ `sceneBreak` (music_scenes), mảnh chia đều chơi tiếp bài, bài hết vòng nối bài anh em ở điểm kết tự nhiên,
đầu cảnh phạt bài ngắn hơn cảnh, bước âm lượng trong cảnh (music_select.choose) - và mốc của trình phát / gói sách mang đủ những
thứ ấy (music_plan)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.io_utils import atomic_write_json
from abook.webui import music_plan, music_select
from abook.webui.music_scenes import book_scenes, chapter_scenes, cue_bounds, cue_kind, with_scene_breaks
from abook.webui.music_select import choose, scene_key
from tests.test_music_scenes import _battle, _calm, _script


def _track(name: str, valence: float, arousal: float, tension: float, duration: float) -> dict:
    return {"link": f"https://x/{name}.mp3", "valence": valence, "arousal": arousal, "tension": tension,
            "duration": duration, "source": "incompetech"}


CALM = _track("calm", 0.25, -0.15, -0.2, 600)
BATTLE = _track("battle", -0.65, 0.75, 0.8, 300)
TRACKS = {track["link"]: track for track in (CALM, BATTLE)}


def _near(tracks: list[dict]):
    return lambda _v, _a: tracks


def _chapter() -> list[dict]:
    """Một cảnh êm ~9 phút (ba mảnh chia đều), rồi một dòng thời gian / nơi chốn mở cảnh trận (hai mảnh)."""
    lines = _calm(85) + [("Trong khi đó, ở kinh thành phía nam.", "neutral", 0, 4.0)] + _battle(40)
    return chapter_scenes(_script(lines))


def test_cue_lines_are_recognised_like_the_research_rule() -> None:
    assert cue_kind({"text": "Trong khi đó, ở kinh thành."}) == "time_place"
    assert cue_kind({"text": "Sáng hôm sau, trời trong."}) == "time_place"
    assert cue_kind({"text": "Góc nhìn của Lâm"}) == "subhead"
    assert cue_kind({"text": "【Ngoại truyện】"}) == "subhead"
    assert cue_kind({"text": "◇ ◇ ◇"}) == "separator"
    assert cue_kind({"text": "Chương 2", "kind": "heading"}) == "heading"
    assert cue_kind({"text": "Phần lớn mọi người đã về nhà từ sớm, chỉ còn vài người ở lại dọn dẹp sân."}) is None
    segments = [{"id": i, "text": text} for i, text in enumerate(["Mở.", "Một.", "* * *", "Hai.", "Góc nhìn của Lâm", "Ba."], 1)]
    # dòng ký hiệu: cảnh mới từ câu SAU nó; tiêu đề phụ: từ chính nó
    assert cue_bounds(segments) == {4: "separator", 5: "subhead"}


def test_a_cue_line_starts_a_new_scene_flagged_like_a_scene_break_line() -> None:
    scenes = _chapter()
    assert [scene["reason"] for scene in scenes] == ["chapter_start", "length", "length", "time_place", "length"]
    assert scenes[3]["firstSegment"] == 86


def test_a_third_boundary_source_plugs_in_as_the_same_flag_with_its_source() -> None:
    lines = _calm(85) + [("Trong khi đó, ở kinh thành phía nam.", "neutral", 0, 4.0)] + _battle(40)
    script = _script(lines)
    flagged = with_scene_breaks(script["segments"], {"llm": {40: "llm", 86: "llm"}})
    assert flagged[38]["sceneBreak"] and flagged[38]["sceneSource"] == "llm"
    assert flagged[84]["sceneSource"] == "cue", "cùng chỗ: nguồn đứng trước (dấu hiệu trong chữ) thắng"
    assert "sceneBreak" not in script["segments"][38], "câu gốc không bị sửa"
    scenes = chapter_scenes(script, boundaries={"llm": {40: "llm"}})
    assert ("llm", 40) in [(scene["reason"], scene["firstSegment"]) for scene in scenes]
    assert ("llm", 40) not in [(scene["reason"], scene["firstSegment"]) for scene in chapter_scenes(script)]
    by_chapter = book_scenes([script], boundaries={7: {"llm": {40: "llm"}}})
    assert [scene["firstSegment"] for scene in by_chapter] == [scene["firstSegment"] for scene in scenes]


def test_length_pieces_continue_the_track_and_only_the_cue_changes_it() -> None:
    chosen = choose(_chapter(), _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get)
    assert [entry["link"] for entry in chosen] == [CALM["link"]] * 3 + [BATTLE["link"]] * 2
    assert [bool(entry.get("continued")) for entry in chosen] == [False, True, True, False, True]
    assert not any(entry.get("siblings") for entry in chosen), "bài 10 phút phủ cả cảnh 9 phút: không nối bài nào"


def test_a_scene_head_prefers_a_track_long_enough_for_the_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    short = _track("short", 0.23, -0.14, -0.21, 120)  # hợp hơn chút nhưng chỉ 2 phút cho cảnh 9 phút
    tracks = [short, CALM]
    assert choose(_chapter()[:3], _near(tracks), book_key="b", track_info=TRACKS.get)[0]["link"] == CALM["link"]
    monkeypatch.setattr(music_select, "SHORT_TRACK_PENALTY", 0.0)
    assert choose(_chapter()[:3], _near(tracks), book_key="b", track_info=TRACKS.get)[0]["link"] == short["link"]


def test_a_track_that_ends_inside_its_scene_hands_over_to_a_sibling_at_its_natural_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_select, "SHORT_TRACK_PENALTY", 0.0)
    first = _track("a", 0.25, -0.15, -0.2, 200)
    sibling = _track("b", 0.27, -0.18, -0.2, 200)
    stranger = _track("far", 0.25, 0.3, 0.3, 200)  # còn trong ngưỡng im lặng của cảnh nhưng xa bài đang chơi
    tracks = [first, sibling, stranger]
    assert music_select.z_distance(stranger, (0.25, -0.15, -0.2)) > music_select.SIBLING_Z
    scenes = _chapter()[:3]
    chosen = choose(scenes, _near(tracks), book_key="b", track_info={t["link"]: t for t in tracks}.get)
    head = chosen[0]["link"]
    other = sibling["link"] if head == first["link"] else first["link"]
    # Bài đầu hết ở giây 200 của nhạc - giữa mảnh 2 (thời gian nhạc chỉ chạy trong các mảnh).
    at = round(scenes[1]["start"] + 200 - (scenes[0]["end"] - scenes[0]["start"]), 3)
    assert chosen[1]["siblings"] == [{"at": at, "link": other}]
    # Bài anh em hết ở giây 400: bài đầu đã dùng trong chương, bài lạ quá xa -> lặp, không đổi bài.
    assert [entry["link"] for entry in chosen] == [head, head, other] and "siblings" not in chosen[2]
    cues = music_plan.chapter_cues({"enabled": True, "scenes": chosen}, 7)
    assert [(cue["link"], cue["start"], cue["end"], cue.get("sibling", False)) for cue in cues] == [
        (head, 0.0, at, False), (other, at, scenes[2]["end"], True)]


def _manual(*pieces: tuple[float, float, float, str]) -> list[dict]:
    """(start, end, tension, reason) -> đoạn cùng không khí êm, chương 1."""
    return [{"chapterId": 1, "firstSegment": index * 10 + 1, "start": start, "end": end, "valence": 0.25, "arousal": -0.15,
             "tension": tension, "confidence": 0.8, "reason": reason} for index, (start, end, tension, reason) in enumerate(pieces)]


def test_volume_steps_follow_the_pieces_tension_against_the_scene_head() -> None:
    scenes = _manual((0, 180, 0.0, "chapter_start"), (180, 360, 0.3, "length"), (360, 540, 0.9, "length"),
                     (540, 560, 0.9, "length"), (600, 700, 0.0, "separator"))
    chosen = choose(scenes, _near([CALM]), book_key="b", track_info=TRACKS.get)
    # 6 dB / đơn vị tension, kẹp +-3; mảnh cách bước trước < 40 s giữ mức trước; đầu cảnh mới về 0
    assert [entry.get("stepDb") for entry in chosen] == [None, 1.8, 3.0, 3.0, None]
    held = choose(_manual((0, 180, 0.0, "chapter_start"), (180, 200, 0.3, "length"), (200, 380, -0.2, "length")),
                  _near([CALM]), book_key="b", track_info=TRACKS.get)
    assert [entry.get("stepDb") for entry in held] == [None, 1.8, 1.8]
    [cue] = music_plan.chapter_cues({"enabled": True, "scenes": chosen[:4]}, 1)
    assert cue["steps"] == [{"at": 180.0, "db": 1.8}, {"at": 360.0, "db": 3.0}]


def test_a_pin_or_a_silence_on_a_piece_still_wins_and_a_kept_track_does_not() -> None:
    scenes = _manual((0, 180, 0.0, "chapter_start"), (180, 360, 0.0, "length"), (360, 540, 0.0, "length"))
    first = choose(scenes, _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get)
    assert {entry["link"] for entry in first} == {CALM["link"]}
    pinned = choose(scenes, _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get,
                    pins={scene_key(scenes[1]): BATTLE["link"]})
    # ghim một mảnh = người dùng muốn đổi ở đó; mảnh sau nối theo bài ghim
    assert [entry["link"] for entry in pinned] == [CALM["link"], BATTLE["link"], BATTLE["link"]]
    assert pinned[1]["pinned"] and pinned[2].get("continued")
    silent = choose(scenes, _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get, silenced=[scene_key(scenes[1])])
    assert silent[1]["link"] is None and silent[1]["silenced"] is True
    assert silent[2]["link"] == CALM["link"] and not silent[2].get("continued"), "sau chỗ im lặng mảnh tự chọn bài"
    kept = choose(scenes, _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get,
                  keep={scene_key(scenes[1]): BATTLE["link"]})
    assert [entry["link"] for entry in kept] == [CALM["link"]] * 3, "mảnh nối tiếp đi theo đầu cảnh, không theo bài cũ"


def test_a_new_chapter_always_chooses_again() -> None:
    scenes = _manual((0, 180, 0.0, "chapter_start"), (180, 360, 0.0, "length"))
    scenes[1]["chapterId"] = 2
    chosen = choose(scenes, _near([CALM]), book_key="b", track_info=TRACKS.get)
    assert not any(entry.get("continued") for entry in chosen)


def test_steps_and_sibling_cues_travel_through_the_book_package(tmp_path: Path) -> None:
    project = tmp_path / "book"
    project.mkdir()
    scenes = [
        {"chapterId": 1, "key": "1:1", "start": 0.0, "end": 180.0, "link": CALM["link"]},
        {"chapterId": 1, "key": "1:30", "start": 180.4, "end": 360.0, "link": CALM["link"], "continued": True, "stepDb": 1.8,
         "siblings": [{"at": 250.0, "link": BATTLE["link"]}]},
    ]
    atomic_write_json(project / music_plan.PLAN_FILE, {"version": music_plan.PLAN_VERSION, "enabled": True, "levelDb": -20.0,
                                                       "scenes": scenes, "tracks": {}})
    cues = music_plan.chapter_cues(music_plan.read_plan(project), 1)
    assert cues == [
        {"start": 0.0, "end": 250.0, "link": CALM["link"], "key": "1:1", "steps": [{"at": 180.4, "db": 1.8}]},
        {"start": 250.0, "end": 360.0, "link": BATTLE["link"], "key": "1:30", "sibling": True,
         "steps": [{"at": 250.0, "db": 1.8}]},
    ]
    folder = tmp_path / "cache"
    folder.mkdir()

    def file(link: str) -> Path:
        path = folder / music_plan.track_name(link).split("/")[1]
        path.write_bytes(b"ID3")
        return path

    music, _files = music_plan.package(project, [1], file)
    packed = music["chapters"]["1"]
    assert [cue.get("sibling", False) for cue in packed] == [False, True]
    assert [cue["steps"] for cue in packed] == [[{"at": 180.4, "db": 1.8}], [{"at": 250.0, "db": 1.8}]]
    # đọc lại như sách đã đóng gói (book.json); bước hỏng bị bỏ, bước xếp theo giây
    packed[0]["steps"] = [{"at": 300, "db": -1}, {"at": "x", "db": 2}, {"at": 180.4, "db": 1.8}]
    back = music_plan.packaged_cues(json.loads(json.dumps(music)), 1)
    assert back[0]["steps"] == [{"at": 180.4, "db": 1.8}, {"at": 300.0, "db": -1.0}] and "sibling" not in back[0]
    assert back[1]["sibling"] is True and back[1]["steps"] == [{"at": 250.0, "db": 1.8}]
