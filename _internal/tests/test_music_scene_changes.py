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
from abook.webui.music_scenes import (book_scenes, chapter_scenes, cue_bounds, cue_kind, hard_break, music_onsets,
                                      with_scene_breaks)
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
    """Một cảnh êm ~9 phút (ba mảnh chia đều), rồi một tiêu đề phụ mở cảnh trận (hai mảnh)."""
    lines = _calm(85) + [(SUBHEAD, "neutral", 0, 4.0)] + _battle(40)
    return chapter_scenes(_script(lines))


SUBHEAD = "[Góc nhìn của Lâm]"


def test_cue_lines_are_recognised_like_the_research_rule() -> None:
    assert cue_kind({"text": "Trong khi đó, ở kinh thành."}) == "time_place"
    assert cue_kind({"text": "Sáng hôm sau, trời trong."}) == "time_place"
    assert cue_kind({"text": "Góc nhìn của Lâm"}) == "subhead"
    assert cue_kind({"text": "◇ ◇ ◇"}) == "separator"
    assert cue_kind({"text": "Chương 2", "kind": "heading"}) == "heading"
    assert cue_kind({"text": "Phần lớn mọi người đã về nhà từ sớm, chỉ còn vài người ở lại dọn dẹp sân."}) is None
    segments = [{"id": i, "text": text} for i, text in enumerate(["Mở.", "Một.", "* * *", "Hai.", "Góc nhìn của Lâm", "Ba."], 1)]
    # dòng ký hiệu: cảnh mới từ câu SAU nó; tiêu đề phụ: từ chính nó
    assert cue_bounds(segments) == {4: "separator", 5: "subhead"}


def test_a_bracket_is_world_text_unless_it_is_dashed_or_names_a_point_of_view() -> None:
    """docs/MUSIC_RESEARCH.md 07-10 BRACKET: [..], 【..】, 「..」 mặc định là chữ trong truyện, không phải đổi cảnh."""
    for text in ("[Nhiệm vụ hoàn thành]", "【Hệ thống】", "「Anh nghe thấy không?」"):
        assert cue_kind({"text": text}) is None, text
    for text in ("[Góc nhìn của Aria]", "【Yuki POV】", "[Shiro side]", "— Phần hai —", "-o0o-", "Góc nhìn của Aria"):
        assert cue_kind({"text": text}) == "subhead", text


def test_a_dashed_dialogue_tag_or_a_plain_sentence_is_not_a_subhead() -> None:
    """docs/MUSIC_RESEARCH.md 10-10 CUE-DASH: lời dẫn thoại kiểu Việt và câu thường mở bằng "Phần"/"Phía" không đổi cảnh."""
    for text in ("– Lizz nói –", "– Đừng lại gần. –", "Phần thưởng:", "Phía sau lưng hắn là cả một đội quân.",
                 "Phần lớn bọn họ"):
        assert cue_kind({"text": text}) is None, text
    for text in ("—Nanato—", "— Chương cuối —", "— 0● 0—", "- 3 -", "Phần 4:", "Phần hai", "[Yuki POV]"):
        assert cue_kind({"text": text}) == "subhead", text


def test_a_numbered_part_with_its_title_is_still_a_subhead() -> None:
    for text in ("Phần 1: Khởi đầu", "Phần II: Bóng tối", "Phần thứ hai", "Phần 3 - Cuộc gặp gỡ định mệnh", "Phần IV"):
        assert cue_kind({"text": text}) == "subhead", text
    for text in ("Phần hai của kế hoạch là đánh lạc hướng bọn chúng", "Phần thứ"):
        assert cue_kind({"text": text}) is None, text


def test_a_one_word_reply_sound_or_end_mark_between_dashes_is_not_a_name() -> None:
    for text in ("— Vâng —", "– Không –", "- Dạ -", "— Ừ —", "— Chạy —", "— Rầm —", "— Hết —", "— End —"):
        assert cue_kind({"text": text}) is None, text
    for text in ("— Selia —", "—Nanato—", "— Diệp Phàm —", "— Phần hai —"):
        assert cue_kind({"text": text}) == "subhead", text


def test_a_time_or_place_line_is_no_longer_a_boundary_but_a_time_jump_still_breaks() -> None:
    segments = [{"id": i, "text": text} for i, text in enumerate(["Mở.", "Một.", "Trong khi đó, ở thành phố phía nam.", "Hai."], 1)]
    assert 3 not in cue_bounds(segments) and cue_bounds(segments) == {}
    assert hard_break({"text": "Sáng hôm sau, trời trong."}) == "time_jump"
    assert hard_break({"text": "Trong khi đó, ở thành phố phía nam."}) is None


def test_a_cue_line_starts_a_new_scene_flagged_like_a_scene_break_line() -> None:
    scenes = _chapter()
    assert [scene["reason"] for scene in scenes] == ["chapter_start", "length", "length", "subhead", "length"]
    assert scenes[3]["firstSegment"] == 86


def test_a_third_boundary_source_plugs_in_as_the_same_flag_with_its_source() -> None:
    lines = _calm(85) + [(SUBHEAD, "neutral", 0, 4.0)] + _battle(40)
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


def test_a_track_ending_just_before_the_music_changes_rests_instead_of_a_short_sibling(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """TAIL (docs/MUSIC_RESEARCH.md 10-10): còn < TAIL_MIN_SECONDS tới hết cảnh thì bài kết tự nhiên rồi lặng - không có bài anh
    em mờ vào vài giây rồi lại bị đổi."""
    monkeypatch.setattr(music_select, "SHORT_TRACK_PENALTY", 0.0)
    scenes = _chapter()[:3]
    played = sum(scene["end"] - scene["start"] for scene in scenes)
    first = _track("a", 0.25, -0.15, -0.2, played - 10)  # hết 10 s trước khi cảnh hết
    sibling = _track("b", 0.27, -0.18, -0.2, played - 10)
    tracks = [first, sibling]
    chosen = choose(scenes, _near(tracks), book_key="b", track_info={t["link"]: t for t in tracks}.get)
    head = chosen[0]["link"]
    stop = round(scenes[2]["end"] - 10, 3)
    assert not any(entry.get("siblings") for entry in chosen)
    assert [entry["link"] for entry in chosen] == [head] * 3 and chosen[2]["stopAt"] == stop
    cues = music_plan.chapter_cues({"enabled": True, "scenes": chosen}, 7)
    assert [(cue["link"], cue["start"], cue["end"]) for cue in cues] == [(head, 0.0, stop)]
    monkeypatch.setattr(music_select, "TAIL_MIN_SECONDS", 5.0)
    longer = choose(scenes, _near(tracks), book_key="b", track_info={t["link"]: t for t in tracks}.get)
    assert [s["link"] for s in longer[2]["siblings"]] == [sibling["link"] if head == first["link"] else first["link"]]


def test_a_track_that_ended_early_is_not_reopened_by_the_next_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bài kết sớm (TAIL) rồi lặng: cảnh kế tránh nó như tránh bài đang chơi; không còn bài nào khác thì mở lại bài ấy SAU quãng
    lặng - hai mốc riêng, không gộp thành một mốc lặp bài từ đầu."""
    monkeypatch.setattr(music_select, "SHORT_TRACK_PENALTY", 0.0)
    scenes = _manual((0, 80, 0.0, "chapter_start"), (80, 150, 0.0, "separator"))
    short = _track("short", 0.25, -0.15, 0.0, 76)
    other = _track("other", 0.1, 0.3, 0.0, 300)
    tracks = {track["link"]: track for track in (short, other)}
    chosen = choose(scenes, _near([short, other]), book_key="b", track_info=tracks.get)
    assert [entry["link"] for entry in chosen] == [short["link"], other["link"]] and chosen[0]["stopAt"] == 76.0
    alone = choose(scenes, _near([short]), book_key="b", track_info=tracks.get)
    assert [entry["link"] for entry in alone] == [short["link"]] * 2
    cues = music_plan.chapter_cues({"enabled": True, "scenes": alone}, 1)
    assert [(cue["start"], cue["end"]) for cue in cues] == [(0.0, 76.0), (80.0, 150.0)]


def test_background_music_stops_where_the_story_starts_playing_music_and_returns_next_scene() -> None:
    """DIEGETIC (docs/MUSIC_RESEARCH.md 10-10, MUSIC-AUDIT lỗi 2): nền không chồng lên bản nhạc đang vang trong truyện."""
    onset = "Ngồi xuống trước cây đàn của mình, Lucien lại đặt tay lên bàn phím."
    lines = (_calm(20) + [(onset, "neutral", 0, 5.0), ("Phần mở đầu chậm rãi và bình yên.", "tender", 1, 6.0),
                          ("Mọi thứ trong bản sonata đều đẹp như một giấc mơ.", "tender", 1, 6.0)] + _calm(4)
             + [(SUBHEAD, "neutral", 0, 4.0)] + _calm(20))
    scenes = chapter_scenes(_script(lines))
    assert scenes[0]["musicAt"] == 128.0 and "musicAt" not in scenes[-1]
    chosen = choose(scenes, _near([CALM, BATTLE]), book_key="b", track_info=TRACKS.get)
    cues = music_plan.chapter_cues({"enabled": True, "scenes": chosen}, 7)
    assert cues[0]["start"] == 0.0 and cues[0]["end"] == 128.0
    assert len(cues) == 2 and cues[1]["start"] == scenes[-1]["start"]  # cảnh sau có nhạc lại, mốc riêng sau quãng lặng


def test_talk_about_music_is_not_music_playing() -> None:
    def onsets(*texts: tuple[str, str]) -> list[int]:
        return music_onsets([{"text": text, "kind": kind} for text, kind in texts])

    assert onsets(("Ta muốn chơi bản sonata cho Silvia nghe, cây đàn ở đâu?", "dialogue")) == []
    assert onsets(("Hai người nói chuyện về âm nhạc suốt buổi chiều.", "narration")) == []
    assert onsets(("Đàn ông trong làng kéo nhau ra đồng.", "narration"), ("Trời nắng.", "narration")) == []
    assert onsets(("Cô khe khẽ hát.", "narration"), ("Giai điệu buồn lan khắp phòng.", "narration")) == [0]
    assert onsets(("Tiếng đàn vang lên giữa quảng trường.", "narration"), ("Ai cũng dừng lại.", "narration")) == []


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


def test_editing_one_chapter_reuses_the_sibling_hand_overs_of_untouched_scenes_without_ranking(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(music_select, "SHORT_TRACK_PENALTY", 0.0)
    tracks = [_track("a", 0.25, -0.15, -0.2, 200), _track("b", 0.27, -0.18, -0.2, 200), _track("far", 0.25, 0.3, 0.3, 200)]
    info = {track["link"]: track for track in tracks}.get
    one = _chapter()[:3]
    two = [dict(scene, chapterId=8) for scene in one]
    asked: list[float] = []

    def near(valence: float, arousal: float) -> list[dict]:
        asked.append(valence)
        return tracks

    before = choose(one + two, near, book_key="b", track_info=info)
    keep = {entry["key"]: entry["link"] for entry in before}
    old = {entry["key"]: [sibling["link"] for sibling in entry.get("siblings") or []] for entry in before}
    assert old[before[4]["key"]], "chương 2 có nối bài anh em - phép thử có nghĩa"
    asked.clear()
    same = choose(one + two, near, book_key="b", keep=keep, kept_siblings=old, track_info=info)
    assert [(e["link"], e.get("siblings")) for e in same] == [(e["link"], e.get("siblings")) for e in before]
    assert asked == [], "không đoạn nào bị sửa: không xếp hạng gì"
    # Ghim đầu chương 1 sang bài khác: chương 1 tính lại, chương 2 nối ĐÚNG bài anh em cũ (kể cả khi xếp hạng sẽ ra bài khác).
    old[before[4]["key"]] = [tracks[2]["link"]]
    other = next(t["link"] for t in tracks[:2] if t["link"] != before[0]["link"])
    pinned = choose(one + two, near, book_key="b", pins={before[0]["key"]: other},
                    keep={k: v for k, v in keep.items() if k != before[0]["key"]}, kept_siblings=old, track_info=info)
    assert pinned[0]["link"] == other and pinned[1]["link"] == other
    assert [s["link"] for s in pinned[4]["siblings"]] == [tracks[2]["link"]]
    assert pinned[3]["link"] == before[3]["link"] and pinned[5]["link"] == tracks[2]["link"]  # mảnh sau chơi tiếp bài anh em ấy


def test_a_rechosen_scene_avoids_the_track_playing_before_it_and_the_track_its_next_neighbour_keeps() -> None:
    tracks = [_track("a", 0.25, -0.15, -0.2, 600), _track("b", 0.25, -0.16, -0.2, 600), _track("c", 0.2, -0.3, -0.3, 600)]
    scenes = [{"chapterId": 1, "firstSegment": first, "valence": 0.25, "arousal": -0.15, "confidence": 0.8,
               "tension": -0.2, "reason": "mood_shift"} for first in (1, 20, 40)]
    keys = [scene_key(scene) for scene in scenes]
    keep = {keys[0]: tracks[0]["link"], keys[2]: tracks[1]["link"]}
    chosen = choose(scenes, _near(tracks), book_key="b", keep=keep)
    assert [entry["link"] for entry in chosen] == [tracks[0]["link"], tracks[2]["link"], tracks[1]["link"]]
    # Không còn bài nào khác: trùng láng giềng còn hơn im lặng.
    chosen = choose(scenes, _near(tracks[:2]), book_key="b", keep=keep)
    assert chosen[1]["link"] in {tracks[0]["link"], tracks[1]["link"]}


def test_a_kept_head_that_now_repeats_a_changed_neighbour_is_chosen_again_but_an_unchanged_pair_stays() -> None:
    tracks = [_track("a", 0.25, -0.15, -0.2, 600), _track("b", 0.25, -0.16, -0.2, 600)]
    scenes = [{"chapterId": 1, "firstSegment": first, "valence": 0.25, "arousal": -0.15, "confidence": 0.8,
               "tension": -0.2, "reason": "mood_shift"} for first in (1, 20)]
    keys = [scene_key(scene) for scene in scenes]
    a, b = tracks[0]["link"], tracks[1]["link"]
    old = {keys[0]: [], keys[1]: []}
    # Người dùng ghim đoạn 1 vào đúng bài đoạn 2 đang giữ: đoạn 2 (không ghim) chọn bài khác.
    chosen = choose(scenes, _near(tracks), book_key="b", pins={keys[0]: b}, keep={keys[1]: b}, kept_siblings=old)
    assert [entry["link"] for entry in chosen] == [b, a]
    # Cặp trùng có sẵn từ lần dựng trước mà không ai sửa: giữ nguyên, sửa một đoạn không sửa lan.
    chosen = choose(scenes, _near(tracks), book_key="b", keep={keys[0]: b, keys[1]: b}, kept_siblings=old)
    assert [entry["link"] for entry in chosen] == [b, b]


def test_each_track_is_checked_for_this_machine_once_per_choice() -> None:
    tracks = [_track(f"t{i}", 0.25, -0.15 - i / 100, -0.2, 200) for i in range(5)]
    counts: dict[str, int] = {}

    def available(link: str) -> bool:
        counts[link] = counts.get(link, 0) + 1
        return True

    choose(_chapter() + [dict(scene, chapterId=8) for scene in _chapter()], _near(tracks), book_key="b",
           available=available, track_info={t["link"]: t for t in tracks}.get)
    assert counts and max(counts.values()) == 1
