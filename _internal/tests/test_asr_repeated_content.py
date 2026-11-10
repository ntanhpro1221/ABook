"""The ASR gate must catch audio that says MORE than the text, not only less.

Owner, 09-11: "thi thoảng có một câu ngắn bị lặp lại đọc 2 lần". The two books he was
hearing (All You Need Is Kill, Nơi mà hai ta đã gọi điện) carry the evidence in their own
stored transcripts: VieNeu read a short sentence or clause of a long segment twice, and the
gate passed it because one repeated clause is a small insertion against a long reference
(similarity 0.86-0.97 against a 0.78 floor). The transcripts below are those stored ones.
"""
from __future__ import annotations

import pytest

from abook import asr
from abook.config import build_settings


def _verifier() -> asr.WhisperVerifier:
    settings = build_settings()
    settings["asr"].update(min_similarity=0.78, max_wer=0.3, min_words=1)
    verifier = asr.WhisperVerifier(settings, lambda _message: None)
    verifier._last_transcription_timeline_impossible = False
    return verifier


# (written text, what the stored transcript heard) - every one verified before this gate.
HEARD_TWICE = [
    (  # AYNIK c3 id1628: the closing question, said twice
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "sao không?"),
    ),
    (  # NOIMA c3 id1079
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
    ),
    (  # AYNIK c2 id1218
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
    ),
    (  # NOIMA c2 id360: the text says "Nhỡ như" twice, the audio four times
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
        ("0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."
        "0. Câu thử đã gỡ. 0."),
    ),
    ("“Không.”", "Không. Không."),  # a whole one-word line said twice
    ("“Để anh ta yên đi.”", "Để anh ta yên đi Đi"),  # AYNIK id2586
]


@pytest.mark.parametrize("written,heard", HEARD_TWICE)
def test_a_repeated_clause_fails_the_gate_and_asks_for_a_new_take(written, heard):
    similarity, _wer = asr.transcript_metrics(written, heard)
    result = _verifier()._evaluate_transcript(written, heard, 20.0)
    assert result["passed"] is False, (similarity, result)
    assert result["verdict"] == asr.ASR_MISMATCH
    assert result["repairable"] is True
    evidence = result[asr.ASR_REPEATED_CONTENT_KEY]
    assert evidence["heard"] > evidence["written"]


HEARD_ONCE = [
    # The text itself repeats: reading it as written is not a repetition.
    ("“Đấm hắn! Đấm hắn! Đấm hắn!”", "Đấm hắn, đấm hắn, đấm hắn."),
    ("0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."),
    # Tone-only difference that makes Whisper's spelling look doubled ("gãi gãi" -> "gái gái").
    ("Hắn gãi gãi cằm.", "Hắn gái gái cầm."),
    ("Tôi lắc đầu quầy quậy.", "Tôi lắc đầu quậy quậy."),
    # A stammer the author wrote: same number of words, nothing extra was said.
    ("“C-Chào buổi sáng.”", "Chào, chào buổi sáng."),
    # One short word doubled inside a long sentence is Whisper noise as often as audio: the
    # broad single-word flags were often not supported by the waveform check.
    (
        "0. Câu thử đã gỡ. 0.",
        "0. Câu thử đã gỡ. 0.",
    ),
    # Whisper looping on a sound that is not in the text is a different failure with its own checks.
    ("“Keiji. Keiji Kiriya.”", "ừ ừ ừ ừ ừ ừ ừ ừ ừ ừ ừ"),
]


@pytest.mark.parametrize("written,heard", HEARD_ONCE)
def test_text_that_repeats_by_itself_is_not_flagged(written, heard):
    assert asr.heard_repeated_content(written, heard) is None


def test_repeated_short_context_counts_against_the_tiled_reference():
    verifier = _verifier()
    tiled = " ".join(["“Chưa.”"] * asr.SHORT_CONTEXT_REPEAT_COUNT)
    assert verifier._evaluate_transcript(tiled, "Chưa, chưa, chưa.", 5.0)["passed"] is True
    doubled_take = verifier._evaluate_transcript(tiled, "Chưa chưa, chưa chưa, chưa chưa.", 5.0)
    assert doubled_take["passed"] is False
    evidence = doubled_take[asr.ASR_REPEATED_CONTENT_KEY]
    assert evidence["heard"] > evidence["written"]


def test_a_repeated_last_word_is_not_hidden_by_the_three_copy_context():
    written = "Để anh ta yên đi."
    expected = " ".join([written] * asr.SHORT_CONTEXT_REPEAT_COUNT)
    heard = " ".join(["Để anh ta yên đi đi."] * asr.SHORT_CONTEXT_REPEAT_COUNT)
    result = _verifier()._evaluate_transcript(expected, heard, 20.0)
    assert result["passed"] is False
    assert result[asr.ASR_REPEATED_CONTENT_KEY]["ngram"] == asr.normalize_transcript("đi")


def test_a_canonical_name_rescue_cannot_wave_a_repetition_through():
    """The locked-name promotion turns a plain ASR_MISMATCH into a pass when the sentence
    without the names is fine. A repeated clause is not a name problem."""
    name = "Giô-na-ba-ru"
    written = (
        f"{name} lắc đầu chậm rãi rồi nhìn ra cửa sổ thật lâu mà không nói thêm một lời nào "
        "nữa với bất kỳ ai trong căn phòng nhỏ. Rồi hắn cười."
    )
    heard = written.replace("Rồi hắn cười.", "Rồi hắn cười. Rồi hắn cười.")
    raw = _verifier()._evaluate_transcript(written, heard, 20.0)
    anchors = [{
        "pronunciation_id": 7, "surface": "Yonabaru", "normalized_surface": "yonabaru",
        "spoken_form": name, "source": "cmudict_vietnamese_transliteration",
        "occurrence_index": 0, "order": 0, "source_start": 0, "source_end": 8,
        "spoken_start": 0, "spoken_end": len(name),
    }]
    result = asr.adjudicate_locked_name_anchors(
        written, raw, anchors, min_similarity=0.78, max_wer=0.3,
    )
    assert result["passed"] is False
    assert result["reason"] != asr.ASR_LOCKED_NAME_CANONICAL_PASS
    assert result.get("locked_name_review_eligible") is not True


def test_collapsed_repeat_rescue_refuses_a_repeated_take():
    raw = {
        "passed": False, "verdict": asr.ASR_MISMATCH, "reason": "ASR_MISMATCH",
        "transcript": "Phe rồn lắc đầu.", "similarity": 0.5, "wer": 0.5,
        "repairable": True, "severe": False,
        asr.ASR_REPEATED_CONTENT_KEY: {"ngram": "lắc đầu", "heard": 2, "written": 1},
    }
    anchors = [{
        "pronunciation_id": 7, "surface": "Ferrell", "normalized_surface": "ferrell",
        "spoken_form": "Ferrell", "source": "cmudict_vietnamese_transliteration",
        "occurrence_index": 0, "order": 0, "source_start": 0, "source_end": 7,
        "spoken_start": 0, "spoken_end": 7,
    }]
    assert asr.adjudicate_collapsed_repeated_short(
        "Ferrell lắc đầu.", raw, anchors,
        requested_repeat_count=asr.SHORT_CONTEXT_REPEAT_COUNT, min_similarity=0.78, max_wer=0.3,
    ) is None


def test_a_repeat_cannot_hide_behind_a_missing_clause():
    written = "Tôi đứng chờ ở sân ga. Rồi hắn cười. Tôi quay lại nhìn vào căn phòng nhỏ."
    heard = "Tôi đứng chờ ở sân ga. Rồi hắn cười. Rồi hắn cười."
    result = _verifier()._evaluate_transcript(written, heard, 20.0)
    assert result[asr.ASR_REPEATED_CONTENT_KEY]["ngram"] == "rồi hắn cười"
    assert result["passed"] is False


def test_rearranging_an_authors_repeated_phrase_adds_no_content():
    written = "Rồi hắn cười. Tôi đứng chờ ở sân ga. Rồi hắn cười."
    heard = "Rồi hắn cười. Rồi hắn cười. Tôi đứng chờ ở sân ga."
    assert asr.heard_repeated_content(written, heard) is None


def test_repeated_content_enters_the_deterministic_repair_schedule(tmp_path):
    import json

    from tests.test_pipeline_mock import _asr_signal_pipeline

    fingerprints = []
    for name in ("first", "replay"):
        folder = tmp_path / name
        folder.mkdir()
        pipeline, chapter, row, _expected = _asr_signal_pipeline(folder, repair_rounds=1)
        evaluator = _verifier()

        class SavedTranscriptVerifier:
            calls = 0

            def __init__(self, gate):
                self.gate = gate

            def unload(self):
                pass

            def can_verify_repeated_short(self, _text):
                return False

            def verify(self, text, _wav, *, confirmation=False):
                self.calls += 1
                # The bad incumbent is confirmed twice; the replacement says the text
                # once under both decodes. No actual TTS or ASR model runs here.
                heard = text + " độc lập." if self.calls <= 2 else text
                return self.gate._evaluate_transcript(text, heard, 20.0)

        pipeline._verify_chapter_audio(chapter, SavedTranscriptVerifier(evaluator))
        fresh = pipeline.db.get_segment(int(row["id"]))
        assert fresh["status"] == "verified"
        assert pipeline.tts.seed_salts == ["asr_clarity_candidate_0_0"]
        attempts = pipeline.db.segment_candidate_attempt_summary(
            int(row["id"]), pipeline.quality_policy_hash,
        )
        assert [attempt["state"] for attempt in attempts] == ["promoted"]
        with pipeline.db.connect() as conn:
            checks = conn.execute(
                "SELECT metrics_json FROM quality_checks "
                "WHERE stage='segment_asr_decode_v1' ORDER BY id",
            ).fetchall()
        rejected = [json.loads(check[0]) for check in checks
                    if json.loads(check[0]).get(asr.ASR_REPEATED_CONTENT_KEY)]
        assert len(rejected) >= 2
        assert all(check["passed"] is False for check in rejected)
        fingerprints.append((fresh["generation_seed"], fresh["wav_sha256"]))
    assert fingerprints[0] == fingerprints[1]
