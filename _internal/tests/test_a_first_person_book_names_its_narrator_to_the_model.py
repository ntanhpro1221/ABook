"""Mỗi prompt phân tích của một cuốn kể ngôi thứ nhất nói cho model biết "tôi" là ai - đo 2026-09-27.

`voices.first_person_identity` trước đây chỉ gộp các nhãn ĐẠI TỪ ("tôi", "ME") về người kể sau khi phân tích xong
(`resolve_first_person_labels`, xem test_a_first_person_book_knows_who_i_is.py). Trên chương test ngôi thứ nhất YMP 248
thì phần lớn lời của người kể không hề mang nhãn đại từ: model tinh chỉnh gán 22 câu của Samael cho chính người đang nói
chuyện với anh ta (VINCE 13 lần) - 34,0% người nói. Thêm MỘT dòng vào prompt mỗi batch ("người kể xưng 'tôi' là
SAMAEL..."): 89,4% (qwen3:8b 31,9% -> 61,7%). docs/LLM_EVAL.md.

Cuốn kể ngôi thứ ba phải thấy đúng prompt và đúng dấu vân tay sổ ứng viên như trước, để sách đã phân tích resume y hệt.
"""
from __future__ import annotations

from abook.analysis import OllamaBookAnalyzer, _analysis_policy_fingerprint
from abook.config import build_settings
from test_analysis_required import FakeDB, FakeSession, analysis_group, analysis_item


def _analyzer(identity: str | None) -> OllamaBookAnalyzer:
    settings = build_settings()
    if identity is not None:
        settings["voices"]["first_person_identity"] = identity
    analyzer = OllamaBookAnalyzer(settings, FakeDB(), lambda _message: None)
    analyzer._model_digest = "sha256:test-model-digest"  # như fixture của test_analysis_required.py
    return analyzer


def _prompt(identity: str | None) -> str:
    analyzer = _analyzer(identity)
    session = FakeSession({"segments": [analysis_item("S001"), analysis_item("S002")]})
    analyzer.session = session
    analyzer._request(analysis_group())
    assert session.request is not None
    return str(session.request["json"]["prompt"])


def test_a_first_person_book_names_its_narrator_in_every_batch_prompt() -> None:
    prompt = _prompt("SAMAEL")

    assert 'người kể chuyện xưng "tôi"' in prompt
    assert "speaker=SAMAEL" in prompt
    # trước danh sách nhân vật đã biết, để model đọc nó trước khi đọc các đoạn
    assert prompt.index("speaker=SAMAEL") < prompt.index("Nhân vật đã biết")


def test_a_third_person_book_sees_exactly_the_prompt_it_always_saw() -> None:
    prompt = _prompt(None)

    assert "ngôi thứ nhất" not in prompt
    assert _prompt("") == prompt


def test_a_pronoun_identity_names_nobody() -> None:
    assert _prompt("tôi") == _prompt(None)
    assert _prompt("ME") == _prompt(None)


def test_the_ledger_fingerprint_changes_only_when_a_narrator_is_named() -> None:
    third_person = _analyzer(None).analysis_policy_fingerprint

    assert third_person == _analysis_policy_fingerprint(build_settings()["analysis"], None)
    assert _analyzer("").analysis_policy_fingerprint == third_person
    assert _analyzer("SAMAEL").analysis_policy_fingerprint != third_person
    assert _analyzer("SAMAEL").analysis_policy_fingerprint != _analyzer("JULIANA").analysis_policy_fingerprint
