"""Hai thẻ "Việc cần duyệt" của A+ (abook/teller_voice.py): giọng lời dẫn khác giới người kể "tôi", và nội tâm của chính "tôi".
Chỉ hiện khi máy KHÔNG tự áp được (sách đã thu, hay người dùng đã chọn giọng dẫn); mặc định không áp; áp bằng đúng ý muốn người nghe có sẵn."""
from __future__ import annotations

import json
from pathlib import Path

from abook import teller_voice
from abook.listener_overrides import read_overrides, request_voice
from abook.webui import work_items as work
from tests.test_teller_voice import _book, _settings


def _with_settings(paths, settings) -> Path:
    (paths.root / "book_settings.json").write_bytes(json.dumps(settings, ensure_ascii=False).encode("utf-8"))
    return paths.root


def _cards(root: Path, kind: str) -> list[dict]:
    return [item for item in work.work_items(root)["items"] if item["kind"] == kind]


def test_only_the_narration_voice_card_is_offered(tmp_path):
    paths,db,settings=_book(tmp_path,recorded=True)
    root=_with_settings(paths,settings)
    voice,=_cards(root,'teller-voice')
    assert voice['voiceChoices'][0]['character']=='NARRATOR'
    assert _cards(root,'teller-thought')==[]
    assert read_overrides(root).get('voices') in (None,{})


def test_a_voice_the_user_chose_gets_the_card_not_an_automatic_change(tmp_path: Path) -> None:
    paths, db, settings = _book(tmp_path, narrator_auto=False)
    root = _with_settings(paths, settings)

    teller_voice.ensure(root, db, settings)

    assert len(_cards(root, "teller-voice")) == 1
    assert _cards(root, "teller-thought") == [], "nội tâm của chính “tôi” vẫn tự về giọng dẫn khi chưa thu"


def test_an_unselected_narration_voice_is_offered_without_changing_thoughts(tmp_path):
    paths,db,settings=_book(tmp_path)
    root=_with_settings(paths,settings)
    teller_voice.ensure(root,db,settings)
    assert len(_cards(root,'teller-voice'))==1
    assert _cards(root,'teller-thought')==[]


def test_keeping_the_current_narration_voice_hides_its_card(tmp_path):
    paths,db,settings=_book(tmp_path,recorded=True)
    root=_with_settings(paths,settings)
    request_voice(root,'NARRATOR',preset='',now=1.0)
    assert _cards(root,'teller-voice')==[]
    assert _cards(root,'teller-thought')==[]


def test_a_third_person_book_has_no_cards(tmp_path: Path) -> None:
    paths, _db, settings = _book(tmp_path, recorded=True, settings=_settings(identity=""))
    root = _with_settings(paths, settings)

    assert _cards(root, "teller-voice") == [] and _cards(root, "teller-thought") == []


def test_the_screenplay_and_the_inbox_ask_who_is_the_teller_by_one_rule(tmp_path: Path) -> None:
    narrator_dir = tmp_path
    from abook import narrator_sections

    narrator_sections.decide(narrator_dir, 1, 2, 3, accepted=True, narrator="Bao", source="owner")
    (narrator_dir / "book_settings.json").write_bytes(json.dumps(_settings(chapters={"2": "Linh"})).encode("utf-8"))

    identity, chapters, chapter_of, row_of = work.first_person_lookup(narrator_dir, {10: 1, 20: 2})

    assert identity == "Mai" and chapters == {2: "Linh"}
    assert chapter_of(10) == "Mai" and chapter_of(20) == "Linh"
    assert row_of is not None and row_of({"chapter_id": 10, "seq": 2}) == "Bao" and row_of({"chapter_id": 10, "seq": 0}) == "Mai"
    (narrator_dir / "book_settings.json").write_bytes(json.dumps(_settings(identity="")).encode("utf-8"))
    assert work.first_person_lookup(narrator_dir, {10: 1})[3] is None


def test_explicit_teller_mode_has_no_default_narration_voice_card(tmp_path):
    paths,db,settings=_book(tmp_path,recorded=True)
    root=_with_settings(paths,settings)
    assert _cards(root,'teller-voice')
    teller_voice.set_mode(root,'teller')
    assert _cards(root,'teller-voice')==[] and _cards(root,'teller-thought')==[]
