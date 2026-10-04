"""Studio đọc tên theo luật của "Nghe ngay" (abook/studio_names.py, docs/READING_FOREIGN_NAMES.md mục 8): gốc cuốn, phiên âm Nhật / Hàn,
giữ tên Anh cho máy đọc nói được tiếng Anh; chỉ phần luật không quyết mới đến CMU / LLM."""
from __future__ import annotations

import pytest

from abook import studio_names
from abook.analysis import OllamaBookAnalyzer, _cmu_phrase_to_vietnamese
from abook.asr import _passes_asr_content_thresholds, tone_folded_transcript_metrics
from abook.config import build_settings
from abook.database import LISTENER_PRONUNCIATION_SOURCE
from abook.models import KEEP_ENGLISH_PRONUNCIATION_SOURCE, RULE_ROMANIZATION_PRONUNCIATION_SOURCE
from abook.readaloud.names import name_reading
from abook.romanization import romanized_reading
from test_analysis_required import FakeDB

JAPANESE = ["Haruto", "Kyouko", "Shinomiya", "Tsubasa", "Yamato", "Ayaka", "Hajime", "Kenji", "Hiroshi", "Takeshi", "Yukino", "Kaori"]
KOREAN = ["Seojun", "Taehyun", "Yejin", "Chaeyeon", "Jihoon", "Minjun", "Hyunwoo", "Eunji", "Seoyeon", "Jiwoo", "Doyoon", "Sungmin"]
WESTERN = ["Kate", "Michael", "Thomas", "Gary", "Lucien", "Evans", "Rose", "Washington", "Benjamin", "Emma", "Jake", "Luke"]


class StudioDB(FakeDB):
    """FakeDB với `relock_machine_pronunciation` như ProjectDB: không bao giờ sửa cách đọc người nghe đã chọn."""

    def relock_machine_pronunciation(self, *, normalized_surface, spoken_form, source):
        for row in self.pronunciations:
            if row["normalized_surface"] != normalized_surface:
                continue
            if row["source"] == LISTENER_PRONUNCIATION_SOURCE or row["spoken_form"] == spoken_form:
                return False
            row["spoken_form"], row["source"] = spoken_form, source
            return True
        return False


def _book(names: list[str], *extra: str) -> StudioDB:
    """Một chương đủ dài để đoán gốc: mỗi tên sáu lần, cộng vài câu riêng."""
    db = StudioDB()
    sentences = [f"{name} nhìn quanh căn phòng." for name in names] * 6 + list(extra)
    db.rows = [
        {"id": index, "stable_id": f"c1s{index}", "chapter_id": 1, "text": text, "kind_hint": "narration", "status": "analyzed",
         "speaker": "NARRATOR"}
        for index, text in enumerate(sentences, 1)
    ]
    return db


def _analyzer(db: StudioDB, monkeypatch, answers: dict[str, str] | None = None) -> tuple[OllamaBookAnalyzer, list[list[str]]]:
    """Bộ phân tích với LLM giả: trả `answers` theo mặt chữ, ghi lại mặt chữ của mọi tên được gửi đi."""
    analyzer = OllamaBookAnalyzer(build_settings(), db, lambda _message: None)
    sent: list[list[str]] = []
    if answers is None:
        monkeypatch.setattr(analyzer, "ensure_available", lambda: pytest.fail("rule names must not start the model"))
        monkeypatch.setattr(analyzer, "_stream_json_response", lambda *_a, **_k: pytest.fail("rule names must not be sent to the model"))
        return analyzer, sent
    monkeypatch.setattr(analyzer, "ensure_available", lambda: True)
    monkeypatch.setattr(analyzer, "_verify_locked_model_digest", lambda _phase: None)
    analyzer._model_digest = "sha256:test"

    def respond(request, **_kwargs):
        import json

        items = json.loads(request["prompt"][request["prompt"].rindex("\n\n[") + 2:])
        sent.append([item["surface"] for item in items])
        return {"names": [{"id": item["id"], "convert": True, "spoken_form": answers[item["surface"]], "confidence": 0.9, "reason": "thử"}
                          for item in items]}

    monkeypatch.setattr(analyzer, "_stream_json_response", respond)
    return analyzer, sent


def _stored(db: StudioDB) -> dict[str, tuple[str, str]]:
    return {row["surface"]: (row["spoken_form"], row["source"]) for row in db.pronunciations}


def test_rule_reading_is_the_read_aloud_romanization() -> None:
    assert studio_names.rule_reading("Haruto-kun", "ja") == "Ha-ru-tô-cun"
    assert studio_names.rule_reading("Kyouko", "ja") == "Ki-âu-cô"
    assert studio_names.rule_reading("Haruto Shinomiya", "ja") == "Ha-ru-tô Si-nô-mi-a"
    assert studio_names.rule_reading("Seojun", "ko") == romanized_reading("Seojun", "ko")
    assert studio_names.rule_reading("Haruto", None) is None, "no origin, no romanization"
    assert studio_names.rule_reading("Rose", "ja") is None, "an English name is not a romaji name"


def test_english_names_are_kept_only_for_an_engine_that_speaks_english() -> None:
    for name in ("Kate", "Michael", "Washington", "Lucien Evans"):
        assert studio_names.keeps_english(name, None, True)
        assert not studio_names.keeps_english(name, None, False)
    assert not studio_names.keeps_english("Theosbane", None, True), "an invented name is not English"
    assert not studio_names.keeps_english("Hana", "ja", True), "the book's origin decides a name both sides know"


def test_planned_reading_decides_word_by_word() -> None:
    assert studio_names.planned_reading("Haruto Smith", "ja", True) == ("Ha-ru-tô Smith", RULE_ROMANIZATION_PRONUNCIATION_SOURCE)
    assert studio_names.planned_reading("Michael", "ja", True) == ("Michael", KEEP_ENGLISH_PRONUNCIATION_SOURCE)
    assert studio_names.planned_reading("Michael Godswill", None, True) is None, "a word no rule decides sends the whole name on"
    assert studio_names.planned_reading("Kate", None, False) is None


@pytest.mark.parametrize(("names", "origin"), [(JAPANESE, "ja"), (KOREAN, "ko"), (WESTERN, None)])
def test_book_origin_comes_from_the_chapters(names, origin) -> None:
    assert studio_names.book_origin_for_project(_book(names)) == origin


def test_a_japanese_book_reads_its_names_by_rule_and_asks_the_model_only_for_the_rest(monkeypatch) -> None:
    db = _book(JAPANESE, "Haruto-kun gật đầu với Rose.", "Rose mỉm cười.", "Xenlor bước vào.")
    analyzer, sent = _analyzer(db, monkeypatch, {"Xenlor": "Xen-lo"})

    analyzer.reconcile_name_pronunciations()

    stored = _stored(db)
    for name in JAPANESE:
        assert stored[name] == (name_reading(name, "ja"), RULE_ROMANIZATION_PRONUNCIATION_SOURCE), "the same reading as Nghe ngay"
    assert stored["Haruto-kun"] == ("Ha-ru-tô-cun", RULE_ROMANIZATION_PRONUNCIATION_SOURCE)
    assert stored["Rose"] == ("Rose", KEEP_ENGLISH_PRONUNCIATION_SOURCE)
    assert sent == [["Xenlor"]], "only the name no rule reads reaches the model"
    assert stored["Xenlor"][0] == "Xen-lo"


def test_the_model_prompt_carries_the_origin_and_owner_readings(monkeypatch) -> None:
    db = _book(JAPANESE, "Xenlor bước vào.")
    analyzer, _sent = _analyzer(db, monkeypatch, {"Xenlor": "Xen-lo"})
    prompts: list[str] = []
    respond = analyzer._stream_json_response
    monkeypatch.setattr(analyzer, "_stream_json_response", lambda request, **kw: prompts.append(request["prompt"]) or respond(request, **kw))

    analyzer.reconcile_name_pronunciations()

    assert "gốc Nhật" in prompts[0] and "Kyouko→Ki-âu-cô" in prompts[0]


def test_a_korean_book_reads_its_names_by_rule(monkeypatch) -> None:
    db = _book(KOREAN)
    analyzer, _sent = _analyzer(db, monkeypatch)

    analyzer.reconcile_name_pronunciations()

    stored = _stored(db)
    for name in KOREAN:
        assert stored[name] == (name_reading(name, "ko"), RULE_ROMANIZATION_PRONUNCIATION_SOURCE)


def test_an_english_book_keeps_its_english_names_as_written(monkeypatch) -> None:
    db = _book(WESTERN)
    analyzer, _sent = _analyzer(db, monkeypatch)

    analyzer.reconcile_name_pronunciations()

    assert _stored(db) == {name: (name, KEEP_ENGLISH_PRONUNCIATION_SOURCE) for name in WESTERN}


def test_a_locked_name_is_never_changed(monkeypatch) -> None:
    db = _book(JAPANESE)
    db.pronunciations = [
        {"surface": "Haruto", "normalized_surface": "haruto", "spoken_form": "Ha-ru-to", "confidence": 1.0, "source": LISTENER_PRONUNCIATION_SOURCE,
         "locked": 1},
        {"surface": "Kenji", "normalized_surface": "kenji", "spoken_form": "Ken-di", "confidence": 0.9, "source": "english_name_transliteration",
         "locked": 1},
    ]
    analyzer, _sent = _analyzer(db, monkeypatch)

    analyzer.reconcile_name_pronunciations()

    stored = _stored(db)
    assert stored["Haruto"] == ("Ha-ru-to", LISTENER_PRONUNCIATION_SOURCE)
    assert stored["Kenji"] == ("Ken-di", "english_name_transliteration")
    assert stored["Kyouko"] == ("Ki-âu-cô", RULE_ROMANIZATION_PRONUNCIATION_SOURCE)


def test_a_full_name_reads_its_kept_word_the_same_way(monkeypatch) -> None:
    """"Michael" giữ tiếng Anh; "Michael Godswill" đi LLM và về "Mai-cồ Gót-uyu" - một tên hai cách đọc. Chữ do luật thắng."""
    db = _book(WESTERN, *["Michael Godswill đứng dậy."] * 2)
    analyzer, sent = _analyzer(db, monkeypatch, {"Michael Godswill": "Mai-cồ Gót-uyu"})

    analyzer.reconcile_name_pronunciations()

    assert sent == [["Michael Godswill"]]
    assert _stored(db)["Michael Godswill"][0] == "Michael Gót-uyu"
    assert _stored(db)["Michael"] == ("Michael", KEEP_ENGLISH_PRONUNCIATION_SOURCE)


def test_a_full_name_read_from_the_dictionary_is_fixed_too(monkeypatch) -> None:
    """Không có tên nào phải hỏi LLM (đường trả về sớm) thì tên đầy đủ đi CMU vẫn được sửa cho khớp chữ giữ tiếng Anh."""
    db = _book(WESTERN, *["Michael Kowalski đứng dậy."] * 2)
    analyzer, _sent = _analyzer(db, monkeypatch)

    analyzer.reconcile_name_pronunciations()

    dictionary = _cmu_phrase_to_vietnamese("Michael Kowalski")
    assert dictionary.split()[0] != "Michael", "the dictionary reads the kept word its own way"
    assert _stored(db)["Michael Kowalski"][0] == "Michael " + dictionary.split()[1]


def test_the_strict_check_refuses_a_rule_reading_with_a_broken_syllable() -> None:
    assert studio_names.lockable("Haruto Smith", "Ha-ru-tô Smith")
    assert not studio_names.lockable("Haruto", "Ha-rut-tô")
    assert not studio_names.lockable("Haruto Smith", "Ha-ru-tô")


# Bản nghe thật (Whisper, VieNeu Studio trên CPU, 04-10) của chữ Anh để nguyên.
HEARD = [("Kate", "Kết"), ("Kate", "Kat"), ("Shadow", "Sado"), ("Portal", "Porto")]


@pytest.mark.parametrize(("written", "heard"), HEARD)
def test_whisper_spelling_of_a_kept_english_word_counts_as_that_word(written, heard) -> None:
    assert studio_names.heard_as_english(written, heard)


@pytest.mark.parametrize(("written", "heard"), [("Kate", "Bà"), ("Kate", "Mai"), ("Portal", "Phố"), ("Shadow", "Đi")])
def test_a_different_word_is_still_a_different_word(written, heard) -> None:
    assert not studio_names.heard_as_english(written, heard)


@pytest.mark.parametrize(("expected", "transcript"), [("Kate gật đầu.", "Kết gật đầu."), ("Shadow lao tới.", "Sado lao tới."),
                                                      ("Mở Portal ra!", "Mở Porto ra!"), ("Kate!", "Kết!")])
def test_the_studio_asr_gate_passes_a_short_line_with_a_kept_english_name(expected, transcript) -> None:
    """Trước khi so mềm, cả bốn câu ngắn này trượt ở ngưỡng high_quality (WER 0,33 / 1,0) dù giọng đọc đúng."""
    asr = build_settings()["asr"]
    similarity, wer, _evidence = tone_folded_transcript_metrics(expected, transcript)
    assert _passes_asr_content_thresholds(True, similarity, wer, min_similarity=asr["min_similarity"], max_wer=asr["max_wer"])


def test_soft_matching_never_rescues_a_wrong_word() -> None:
    asr = build_settings()["asr"]
    similarity, wer, _evidence = tone_folded_transcript_metrics("Kate gật đầu.", "Bà gật đầu.")
    assert not _passes_asr_content_thresholds(True, similarity, wer, min_similarity=asr["min_similarity"], max_wer=asr["max_wer"])
    assert studio_names.soften_english_words("ra lao", "ra lao") == "ra lao", "Vietnamese words are never treated as English"
