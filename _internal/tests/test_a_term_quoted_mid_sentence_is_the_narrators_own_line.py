"""Embedded fragments require source syntax and safeguards for actual speech."""
from __future__ import annotations

import pytest

from abook.analysis import _repair_in_sentence_quote_speakers


def row(stable_id: str, paragraph: int, text: str) -> dict[str, object]:
    return {"stable_id": stable_id, "chapter_id": 1, "paragraph_index": paragraph, "text": text}


def data(kind: str, speaker: str) -> dict[str, object]:
    return {"kind": kind, "speaker": speaker, "personality_hint": "", "notes": ""}


def test_positive_metalinguistic_evidence_can_identify_an_unattributed_term():
    group=[row('a',3,'Mira giải nghĩa thuật ngữ'),row('b',3,'“cầu mưa”'),row('c',3,'trong bản ghi.')]
    result={'a':data('narration','NARRATOR'),'b':data('dialogue','UNKNOWN'),'c':data('narration','NARRATOR')}
    _repair_in_sentence_quote_speakers(group,result)
    assert result['b']['speaker']=='NARRATOR'


def test_a_real_line_keeps_its_speaker() -> None:
    group = [
        row("a", 3, "Lucien mỉm cười nói:"),
        row("b", 3, "“Tôi đã tìm ra lời giải.”"),
        row("c", 4, "Cả phòng lặng đi."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "LUCIEN"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "LUCIEN"
    assert "_host_note_markers" not in result["b"]


def test_a_whole_utterance_quoted_mid_sentence_keeps_its_speaker() -> None:
    # Hai thầy gán nhãn 05-10: câu nói có dấu phẩy giữa câu kể vẫn là lời của người nói, không phải thuật ngữ.
    group = [
        row("a", 7, "Minh nói"),
        row("b", 7, "“Bố mẹ tớ đến xem rồi, nên nhà tớ sẽ ăn cùng nhau”"),
        row("c", 7, "và vì vậy chúng tôi ăn riêng."),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "MINH"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "MINH"
    assert "_host_note_markers" not in result["b"]


def test_a_term_in_another_paragraph_is_not_touched() -> None:
    group = [
        row("a", 3, "Lucien không thể bảo rằng nếu là"),
        row("b", 4, "“Khoa Học”"),
        row("c", 5, 'thì phải thêm mục trên bảng kiểm.'),
    ]
    result = {"a": data("narration", "NARRATOR"), "b": data("dialogue", "LUCIEN"),
              "c": data("narration", "NARRATOR")}
    _repair_in_sentence_quote_speakers(group, result)
    assert result["b"]["speaker"] == "LUCIEN"


@pytest.mark.parametrize("speaker", ["Mira", "Tavin", "NPC_LOCAL::c00001::khách"])
@pytest.mark.parametrize("quoted,kind", [('“cầu mưa”', 'dialogue'), ('‘cầu mưa’', 'thought')])
def test_a_named_owner_does_not_turn_a_technical_term_into_speech(speaker, quoted, kind):
    group = [row('a', 3, 'Tờ ghi chú giải nghĩa thuật ngữ'),
             row('b', 3, quoted), row('c', 3, 'trong bản vẽ của chiếc máy.')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data(kind, speaker),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'NARRATOR'
    assert result['b']['kind'] == kind


@pytest.mark.parametrize('lead,quoted,tail', [
    ('Lúc chia tay, cô bé nói', '“chúc ngủ ngon”', '. Đèn ngoài hiên tắt.'),
    ('Điều chị ấy cần nghe là', '“Cảm ơn”', ', trước khi cánh cửa đóng lại.'),
    ('Thứ cậu ấy vẫn không tin là', '“tớ đã về”', ', ngay giữa đêm mưa.'),
    ('Cô bật ra tiếng cười nằm giữa', '“ehehe”', 'và một tiếng thở dài.'),
    ('Cô nhìn qua cửa sổ rồi khẽ thốt', '“Fufufu”', ', giữa căn phòng im lặng.'),
    ('Con mèo nhỏ kêu', '“meo”', 'như thể muốn xin ăn.'),
    ('Nếu chị nghe tôi nói', '“Xin lỗi”', ', liệu chị có bỏ đi không?'),
])
@pytest.mark.parametrize('speaker', ['Mira', 'NPC_LOCAL::c00001::khách'])
def test_short_speech_acts_keep_named_and_local_owners(lead, quoted, tail, speaker):
    group = [row('a', 3, lead), row('b', 3, quoted), row('c', 3, tail)]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', speaker),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == speaker
    assert '_host_note_markers' not in result['b']


@pytest.mark.parametrize('lead,quoted,tail', [
    ('Mira cười trước khi chỉnh lại chế độ', '“cầu mưa”', 'trên chiếc máy.'),
    ('Nếu anh ấy nói', '“Tớ còn một ngọn đèn”', 'thì cô sẽ yên tâm.'),
    ('Có người nào từng nói rằng', '“mày phải đi”', 'không?'),
    ('Lúc quay về, cô ấy đã nói ra', '“Bản Tín”', ', cái tên của thị trấn phía bắc.'),
    ('Chỉ cần nói một câu', '“Em vẫn còn chờ”', 'là đủ để báo cho mọi người.'),
])
def test_distant_speech_hypotheticals_and_metalinguistic_frames_are_distinct(lead, quoted, tail):
    group = [row('a', 3, lead), row('b', 3, quoted), row('c', 3, tail)]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', 'Mira'),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'NARRATOR'


def test_a_named_thought_with_a_speaking_self_keeps_its_identity():
    group = [row('a', 3, 'Tôi nhìn ra xa rồi tự nhủ'), row('b', 3, '‘tớ vẫn chờ’'),
             row('c', 3, ', mặc cho cơn mưa chưa dứt.')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('thought', 'Mira'),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'Mira'
    assert result['b']['kind'] == 'thought'


def test_a_named_fragment_is_preserved_when_the_other_sentence_half_is_missing():
    group = [row('a', 3, 'Mira ngồi bên cửa'), row('b', 3, '“màu xanh”')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', 'Mira')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'Mira'


def test_original_neighbors_protect_a_short_turn_at_a_batch_edge():
    from tests.test_analysis_required import _castrule_batch
    from abook.analysis import _original_neighbor_context, _validate
    rows, payload = _castrule_batch([
        ('Điều chị ấy cần nghe là', 'narration', 'NARRATOR'),
        ('“Cảm ơn”', 'dialogue', 'Mira'),
        (', trước khi cánh cửa đóng lại.', 'narration', 'NARRATOR'),
    ])
    context = _original_neighbor_context(rows)
    result = _validate([rows[1]], {'segments': [payload['segments'][1]]}, original_context=context)
    assert result['r1']['speaker'] == 'Mira'


@pytest.mark.parametrize('answer', ['phải', 'đúng rồi', 'được thôi', 'vâng ạ', 'dạ', 'ừ', 'chưa', 'không nhé'])
def test_short_answers_with_a_speech_cue_keep_the_reported_person(answer):
    group = [row('a', 3, 'Nếu chị ấy chỉ khẽ đáp'), row('b', 3, f'“{answer}”'),
             row('c', 3, 'thì chúng tôi sẽ đợi.')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', 'Mira'),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'Mira'


def test_a_short_answer_word_in_a_definition_has_no_speech_cue():
    group = [row('a', 3, 'Tờ ghi chú đang giải nghĩa cụm từ'), row('b', 3, '“đúng rồi”'),
             row('c', 3, 'trong bảng ví dụ.')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', 'Mira'),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'NARRATOR'


def test_a_speech_complement_with_modifiers_stays_in_its_own_clause():
    group = [row('a', 3, 'Trong lúc chờ, cô ấy nói vài điều rất khó tin với mọi người như là'),
             row('b', 3, '“giữ đèn sáng”'), row('c', 3, 'trước lúc trời tối.')]
    result = {'a': data('narration', 'NARRATOR'), 'b': data('dialogue', 'Mira'),
              'c': data('narration', 'NARRATOR')}
    _repair_in_sentence_quote_speakers(group, result)
    assert result['b']['speaker'] == 'Mira'


@pytest.mark.parametrize('spoken,expected', [(True, 'Tavin'), (False, 'NARRATOR')])
def test_coordinated_quotes_share_speech_evidence_without_copying_an_owner(spoken, expected):
    lead = 'Trong lúc làm việc, cô ấy khẽ lẩm bẩm' if spoken else 'Tờ giấy giải thích khái niệm'
    group = [row('a', 3, lead), row('b', 3, '“bền”'), row('c', 3, 'và'),
             row('d', 3, '“dẻo”'), row('e', 3, 'trước khi tấm vải được gấp lại.')]
    result = {r['stable_id']: data('narration', 'NARRATOR') for r in group}
    result.update(b=data('dialogue', 'Mira'), d=data('dialogue', 'Tavin'))
    _repair_in_sentence_quote_speakers(group, result)
    assert result['d']['speaker'] == expected
