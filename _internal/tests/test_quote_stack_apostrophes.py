"""An apostrophe inside a word cannot close a cross-paragraph thought."""
import pytest

from abook.text_processing import segment_chapter_text


@pytest.mark.parametrize("word", ["Ma'at", "I'm", "dấu ' cách"])
@pytest.mark.parametrize("in_first", [False, True])
@pytest.mark.parametrize("closer", ["’", "'"])
def test_word_apostrophe_keeps_the_thought_open_across_paragraphs(word, in_first, closer):
    lines = [
        f"‘Tôi đang kiểm {word}" if in_first else "‘Tôi đang kiểm chữ",
        "và vẫn tiếp tục suy nghĩ." if in_first else f"và nghĩ về {word}.",
        f"Còn một ý nữa.{closer}",
        "Một câu kể.",
    ]
    warnings = []
    rows = segment_chapter_text(1, "\n\n".join(lines), warnings=warnings)
    assert [(r["kind_hint"], r["text"]) for r in rows] == list(zip(
        ["thought", "thought", "thought", "narration"], lines,
    ))
    assert warnings == []
