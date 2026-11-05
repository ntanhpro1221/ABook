"""Thẻ "Gọi hay nói" (webui/vocatives.py): câu thoại gán cho X mà chính câu ấy gọi X - người được gọi thường là người nghe.

Luật gốc (`first_person.addressed_names`, dùng chung với luật tự sửa của dây chuyền) không đổi; hộp việc bắt thêm lời gọi có
chức danh, tên trần ở rìa một câu giữa lời thoại, tên sau tiểu từ cuối câu, và cặp lời gọi. Chữ trong bài thử là chữ tự viết.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from test_a_self_addressed_line_becomes_a_who_says_this_card import _registered

from abook.first_person import addressed_names
from abook.listener_overrides import NARRATOR, UNNAMED
from abook.webui.casting_review import casting_chapter
from abook.webui.vocatives import caller_doubts, extra_calls, mentions
from abook.webui.work_items import work_items

NAMES = frozenset({"Rowan", "Mina", "Kiri"})
TITLED = frozenset({"Minh", "Lan"})


@pytest.mark.parametrize("text, called", [
    ("“Đừng lo, anh Rowan. Mọi chuyện ổn cả.”", {"Rowan"}),
    ("“Hôm nay trời đẹp quá. Thưa tiểu thư Mina, xe đã sẵn sàng.”", {"Mina"}),
    ("“Cô, cô Mina! Chờ tôi với!”", {"Mina"}),
    ("“Giáo sư Rowan. Tôi nộp bài đây.”", {"Rowan"}),
    ("“Được rồi, Kiri. Giờ thì về nhà thôi.”", {"Kiri"}),
    ("“Thế là xong rồi. Mina, cậu mang cái này về nhé.”", {"Mina"}),
    ("“Cậu ổn chứ Rowan?”", {"Rowan"}),
    ("“Oi Kiri. Lại đây xem này.”", {"Kiri"}),
    # Tên Việt một âm tiết cần lời gọi rõ, không bắt chỉ vì có nhắc tên.
    ("“Anh Minh ơi, đợi em với!”", {"Minh"}),
    ("“Thưa chị Lan, cơm chín rồi.”", {"Lan"}),
    ("“Minh, đi thôi.”", {"Minh"}),
    ("“Đi thôi, Minh!”", {"Minh"}),
    ("“Này Minh, đi thôi.”", {"Minh"}),
    ("“Thưa Minh, xe tới rồi.”", {"Minh"}),
    ("“Minh đang đi học.”", set()),
    # Nói VỀ người ấy, không gọi.
    ("“Không lẽ… anh Rowan đang giấu gì sao?”", set()),
    ("“Hôm qua, cô Mina đã ghé qua đây.”", set()),
    ("“Tôi đi với Mina và Kiri.”", set()),
    ("“Người ta gọi là Rowan, nghe lạ nhỉ.”", set()),
    ("“Tôi là Rowan. Rất vui được gặp.”", set()),
])
def test_the_extra_calls_catch_titled_and_mid_line_calls_and_leave_mentions(text: str, called: set[str]) -> None:
    assert extra_calls(text, NAMES, TITLED) | addressed_names(text, set(NAMES)) == called


def test_the_extra_calls_are_on_top_of_the_shared_rule() -> None:
    """Lời gọi luật gốc đã bắt thì vẫn được bắt (thẻ cũ không mất câu nào); luật gốc không học thêm gì từ hộp việc."""
    assert addressed_names("“Mina, lại đây.”", set(NAMES)) == {"Mina"}
    assert addressed_names("“Đừng lo, anh Rowan. Mọi chuyện ổn cả.”", set(NAMES)) == set(), "luật tự sửa của dây chuyền giữ nguyên"


def test_a_single_syllable_name_is_mentioned_only_after_a_title() -> None:
    assert mentions("“Chị Lan nói thế à?”", NAMES, TITLED) == {"Lan"}
    assert mentions("“Lan can ở đâu?”", NAMES, TITLED) == set()


def _rows(lines: list[tuple[str, str, str]]) -> list[dict]:
    return [{"id": seq + 1, "chapter_id": 1, "seq": seq, "kind": kind, "speaker": speaker, "text": text}
            for seq, (kind, text, speaker) in enumerate(lines)]


@pytest.mark.parametrize("text", [
    "“Minh, đi thôi.”", "“Đi thôi, Minh!”", "“Này Minh, đi thôi.”", "“Anh Minh ơi, đợi em.”", "“Thưa Minh, xe tới rồi.”",
    "“Akira-san, lại đây.”", "“Đi thôi, Akira-kun!”", "“Akira-senpai, đợi em.”",
])
def test_registered_aliases_trigger_the_card_without_changing_the_rows(text: str) -> None:
    rows = _rows([("dialogue", text, "NGUYỄN MINH"), ("dialogue", "“Được rồi.”", "LAN")])
    before = [dict(row) for row in rows]
    found = caller_doubts(rows, {"NGUYỄN MINH": {"Minh", "Akira"}, "LAN": {"Lan"}})
    assert 1 in found and "NGUYỄN MINH" not in found[1].people
    assert rows == before


def test_a_reply_that_names_the_person_just_called_is_asked_with_the_caller_first() -> None:
    rows = _rows([
        ("dialogue", "“Mina, mai cậu có đi không?”", "ROWAN"),
        ("dialogue", "“Mina nhất định phải đi đấy nhé.”", "MINA"),
        ("dialogue", "“Ừ, để tớ nghĩ đã.”", "KIRI"),
    ])
    aliases = {"ROWAN": {"Rowan"}, "MINA": {"Mina"}, "KIRI": {"Kiri"}}
    found = caller_doubts(rows, aliases)
    assert list(found) == [2]
    assert found[2].caller == "ROWAN" and found[2].people[0] == "ROWAN"


def test_a_reply_that_does_not_name_the_person_called_is_not_asked() -> None:
    rows = _rows([
        ("dialogue", "“Mina, mai cậu có đi không?”", "ROWAN"),
        ("dialogue", "“Ừ, mai tớ đi.”", "MINA"),
    ])
    assert caller_doubts(rows, {"ROWAN": {"Rowan"}, "MINA": {"Mina"}}) == {}


def test_the_people_asked_first_are_those_talking_with_the_one_called() -> None:
    """Câu gán cho Mina mà gọi Mina: Kiri vừa gọi Mina ở câu khác - Kiri đang nói chuyện với Mina, nên đứng trước Rowan dù
    Rowan nói gần hơn."""
    rows = _rows([
        ("dialogue", "“Mina, xong chưa đấy?”", "KIRI"),
        ("narration", "Cả nhóm đứng chờ.", "NARRATOR"),
        ("dialogue", "“Tới giờ rồi.”", "ROWAN"),
        ("dialogue", "“Nhanh lên, Mina!”", "MINA"),
    ])
    found = caller_doubts([row for row in rows if row["kind"] != "narration"],
                          {"ROWAN": {"Rowan"}, "MINA": {"Mina"}, "KIRI": {"Kiri"}})
    assert found[4].people == ["KIRI", "ROWAN"] and found[4].caller == ""


def _book(tmp_path: Path) -> Path:
    db, project = _registered(tmp_path / "a", [
        (1, "dialogue", "“Mina, mai cậu có đi không?”", "ROWAN", "male"),
        (2, "dialogue", "“Mina nhất định phải đi đấy nhé.”", "MINA", "female"),
        (3, "narration", "Kiri bật cười.", "NARRATOR", "unknown"),
        (4, "dialogue", "“Đừng lo, chị Mina. Em sẽ đi cùng.”", "MINA", "female"),
        (5, "dialogue", "“Vậy thì tốt.”", "KIRI", "female"),
        (6, "dialogue", "“Tôi cũng đi.”", "SORA", "male"),
        (7, "dialogue", "“Cả tôi nữa.”", "TOBI", "male"),
    ])
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='verified', wav_path='kiri.wav', wav_duration=3.5 WHERE speaker='KIRI'")
    return project


def test_the_inbox_asks_both_calls_with_three_people_the_narrator_and_the_unnamed_extra(tmp_path: Path) -> None:
    project = _book(tmp_path)
    cards = {item["lines"][0]["stableId"]: item for item in work_items(project)["items"] if item["kind"] == "vocative"}
    assert set(cards) == {"s1", "s3"}
    reply, titled = cards["s1"], cards["s3"]
    assert "Rowan" in reply["problem"] and reply["doubt"] < titled["doubt"], "cặp lời gọi: mẫu đo nhỏ, hỏi nhẹ hơn"
    assert [choice["value"] for choice in reply["choices"]][0] == "ROWAN"
    for card in (reply, titled):
        values = [choice["value"] for choice in card["choices"]]
        assert values[-2:] == [NARRATOR, UNNAMED] and len(values) == 5 and "MINA" not in values
        assert card["chapters"] == [1]
        assert card["examples"][0].get("before") is not None, "câu liền trước làm ngữ cảnh, như thẻ Ai nói câu này"
    (kiri,) = [choice for choice in titled["choices"] if choice["value"] == "KIRI"]
    assert isinstance(kiri.get("sampleId"), int), "người đề xuất đã có câu thu: nghe thử giọng ngay trên thẻ"
    assert all("sampleId" not in choice for choice in titled["choices"] if choice["value"] != "KIRI")


def test_the_script_tab_explains_a_reply_pair_and_suggests_the_caller(tmp_path: Path) -> None:
    project = _book(tmp_path)
    hint = next(line["hint"] for line in casting_chapter(project, 1)["lines"] if line["stableId"] == "s1")
    assert hint["kind"] == "vocative" and hint["suggest"] == "ROWAN" and "Rowan" in hint["note"]


def test_before_recording_the_choices_offer_existing_preset_samples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui import voice_picker
    project = _book(tmp_path)
    monkeypatch.setattr(voice_picker, "preview_file", lambda _preset: tmp_path / "synthetic-preview.wav")
    card = next(item for item in work_items(project)["items"] if item["key"] == "vocative:4")
    rowan = next(choice for choice in card["choices"] if choice["value"] == "ROWAN")
    kiri = next(choice for choice in card["choices"] if choice["value"] == "KIRI")
    assert rowan["samplePreset"] == "Thanh Bình" and "sampleId" not in rowan
    assert isinstance(kiri["sampleId"], int) and "samplePreset" not in kiri
