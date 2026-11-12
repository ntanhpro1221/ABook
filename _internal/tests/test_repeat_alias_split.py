"""VieNeu reads a phrase the text says twice one time too many - and a new seed does not help.

repeat_design.md (12-11-2026): every real repeat in four books has one shape. A phrase of two or
more syllables appears twice in the line ("Đấm hắn! Đấm hắn!", "là đồ bơi, là đồ bơi"); after
the second copy the model's implicit text pointer jumps back to just after the first and reads
the middle again. At Hello every seed did it (1915 6/6, 2153 6/6), so the seed-only repair round
never rescued the class, and four such segments were even published as `warning` through the
"keep the locked reading" path.

F0: repeated content heard on a decode blocks that exception path.
F1: two takes repeating the same phrase (or F4's duration evidence) send the next candidate to a
    split at the punctuation between the copies, so no VieNeu call sees two of them.
F3: the frame-ceiling flag is reported for any single-SDK-chunk line, not only <= 2 words.
F4: a 5-12 syllable line far longer than its syllables allow carries a duration flag.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from abook import asr, audio_io
from abook import database as database_module
from abook.audio_io import VIENEU_V3_CODEC_SAMPLES_PER_FRAME, atomic_write_wav
from tests.audio_fixtures import quiet_edges
from abook.config import build_settings
from abook.database import (
    KEEP_LOCKED_READING_ACTION,
    ProjectDB,
)
from abook.pipeline import BookPipeline
from abook.project import create_or_open_project
from abook.text_processing import (
    REPEAT_ALIAS_SPLIT_STRATEGY,
    SPLIT_REPEAT_NGRAM_FIELD,
    SPLIT_STRATEGY_FIELD,
    SYLLABLE_DURATION_OUTLIER_METRIC,
    SYLLABLE_DURATION_RATIO_METRIC,
    fold_vietnamese_tones,
    repeated_alias_phrase,
    split_text_at_repeated_phrase,
)
from abook.tts import GENERATION_CEILING_METRIC, VIENEU_SDK_CHUNK_MAX_CHARS


# --- the split itself -------------------------------------------------------------------------

DESIGN_CASES = [
    # (text, ASR n-gram, expected pieces) - the expected results written in repeat_design.md F1.
    ("Đấm hắn! Đấm hắn! Đấm hắn!", "dấm hắn", ["Đấm hắn!", "Đấm hắn!", "Đấm hắn!"]),
    (
        "0. Câu thử đã gỡ. 0.",
        "là dồ bơi",  # normalize_transcript: đ -> d, tones kept
        ["0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."],
    ),
    (
        "0. Câu thử đã gỡ. 0.",
        "một mình ngắm pháo hoa",
        ["0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."],
    ),
    (
        "0. Câu thử đã gỡ. 0.",
        "mùi hương của cô",
        ["0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."],
    ),
    (
        "0. Câu thử đã gỡ. 0.",
        "cậu ấy sẽ cười",
        ["0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."],
    ),
]


@pytest.mark.parametrize(("text", "ngram", "expected"), DESIGN_CASES)
def test_the_split_lands_between_the_copies_and_changes_no_character(text, ngram, expected):
    pieces = split_text_at_repeated_phrase(text, ngram)

    assert pieces == expected
    assert " ".join(pieces) == text
    # No call sees two copies of the phrase any more.
    gram = repeated_alias_phrase(text, ngram)
    for piece in pieces:
        assert repeated_alias_phrase(piece, " ".join(gram)) is None


def test_without_an_asr_phrase_the_longest_repeat_of_the_text_is_used():
    # "Ăn đi! x3" is heard as "anh đi": the heard phrase is not in the text at all.
    assert split_text_at_repeated_phrase("Ăn đi! Ăn đi! Ăn đi!", None) == ["Ăn đi!", "Ăn đi!", "Ăn đi!"]
    assert repeated_alias_phrase("Ăn đi! Ăn đi! Ăn đi!", "anh đi") is None


def test_an_unmapped_asr_phrase_does_not_pick_an_unrelated_repeat():
    text = "Đấm hắn! Đấm hắn! Đấm hắn!"
    assert BookPipeline._repeat_alias_pieces(text, "ngắm pháo hoa") == [text]
    assert BookPipeline._repeat_alias_pieces(text, "") == ["Đấm hắn!"] * 3


def test_two_long_hyphenated_words_are_still_a_two_word_line():
    text = "Giô-en! Giô-en!"
    assert split_text_at_repeated_phrase(text, None) == [text]


def test_a_one_syllable_repeat_and_a_repeat_without_punctuation_are_left_alone():
    # Segment 673: "không ... không" is one syllable; the next seed fixed it by itself.
    assert split_text_at_repeated_phrase("Tôi không thể không thấy nó.", "không") == [
        "Tôi không thể không thấy nó."
    ]
    # No punctuation between the copies: never cut inside a clause at this stage.
    assert split_text_at_repeated_phrase("đi mãi đi mãi mà không tới", None) == [
        "đi mãi đi mãi mà không tới"
    ]


def test_an_english_span_is_never_cut():
    text = "Xin chào <en>Mr. Smith, Mr. Smith</en> nhé."
    assert split_text_at_repeated_phrase(text, None) == [text]


def test_closing_quotes_after_the_mark_still_count_as_the_boundary():
    text = "“Đấm hắn!” “Đấm hắn!”"
    assert split_text_at_repeated_phrase(text, None) == ["“Đấm hắn!”", "“Đấm hắn!”"]


def test_tone_fold_matches_whisper_tone_errors():
    assert fold_vietnamese_tones("Gãi gãi") == fold_vietnamese_tones("gái gai")
    assert fold_vietnamese_tones("Đồ bơi") == fold_vietnamese_tones("dô bơi")
    assert fold_vietnamese_tones("giôn") == fold_vietnamese_tones("dôn")
    assert fold_vietnamese_tones("Đồ bơi") == " ".join(
        asr._tone_folded_words(asr.normalize_transcript("Đồ bơi").split())
    )


def test_the_database_reads_the_key_asr_writes():
    assert database_module.REPEATED_CONTENT_EVIDENCE_KEY == asr.ASR_REPEATED_CONTENT_KEY


# --- F0: a heard repeat is not a spelling test ------------------------------------------------

def _locked_reading(tmp_path: Path) -> tuple[ProjectDB, dict]:
    from tests.candidate_fixtures import locked_reading

    db = locked_reading(tmp_path)
    with db.connect() as conn:
        segment = dict(conn.execute(
            "SELECT * FROM segments WHERE stable_id LIKE ?", ("%feeb9dd9dda2",)
        ).fetchone())
    return db, segment


def _mark_repeated(db: ProjectDB, check_id: int) -> None:
    with db.transaction() as conn:
        raw = conn.execute("SELECT metrics_json FROM quality_checks WHERE id=?", (check_id,)).fetchone()[0]
        metrics = json.loads(raw)
        metrics[asr.ASR_REPEATED_CONTENT_KEY] = {"ngram": "có tên", "heard": 3, "written": 1}
        conn.execute("UPDATE quality_checks SET metrics_json=? WHERE id=?", (json.dumps(metrics), check_id))


@pytest.mark.parametrize("decode", ["beam_check_id", "greedy_check_id"])
def test_a_locked_reading_that_was_heard_repeating_is_not_kept(tmp_path: Path, decode: str) -> None:
    db, segment = _locked_reading(tmp_path)
    policy = str(segment["generation_policy_hash"])
    candidate = db.find_locked_reading_that_lost_only_the_spelling_test(int(segment["id"]), policy)
    assert candidate is not None  # the fixture is the ordinary "only the spelling" case

    _mark_repeated(db, int(candidate[decode]))

    assert db.find_locked_reading_that_lost_only_the_spelling_test(int(segment["id"]), policy) is None
    with pytest.raises(RuntimeError, match="một đường phiên nghe cụm lặp"):
        db.promote_segment_candidate(
            int(candidate["id"]),
            validated_wav_sha256=str(candidate["wav_sha256"]),
            repair_action=KEEP_LOCKED_READING_ACTION,
            attempt=99,
            warning_code="ASR_LOCKED_NAME_ANCHOR_MISMATCH",
            keeping_the_locked_reading=True,
        )
    assert str(db.get_segment(int(segment["id"]))["wav_sha256"]) == str(segment["wav_sha256"])


def test_a_finished_take_that_was_heard_repeating_does_not_replace_a_cut_off_one() -> None:
    gate = object.__new__(ProjectDB)
    segment = {"stable_id": "s", "text": '"Bất bại?"', "wav_duration": 1.92,
               "signal_json": json.dumps({"generation_ceiling_hit": 1.0})}
    candidate = {"id": 7, "repair_round": 1, "wav_duration": 1.1,
                 "failure_reason": "beam=ASR_MISMATCH; greedy=ASR_MISMATCH",
                 "signal_json": "{}", "beam_result_json": json.dumps({}),
                 "greedy_result_json": json.dumps({})}
    assert "tự kết thúc" in gate._require_candidate_beats_a_cut_off_incumbent(candidate, segment)

    candidate["greedy_result_json"] = json.dumps(
        {asr.ASR_REPEATED_CONTENT_KEY: {"ngram": "bất bại", "heard": 2, "written": 1}}
    )
    with pytest.raises(RuntimeError, match="ứng viên nghe cụm lặp"):
        gate._require_candidate_beats_a_cut_off_incumbent(candidate, segment)


# --- F1 through the real pipeline (fake TTS, saved-transcript ASR) ---------------------------

class _TextLengthTTS:
    """FakeTTS whose take length follows the text, so a merged split is not one fixed blob."""

    def __new__(cls, settings, db, seconds_per_syllable: float):
        from tests.test_pipeline_mock import FakeTTS, _voiced

        class Scaled(FakeTTS):
            def synthesize_atomic(self, row, output, seed_salt="", *, repair_short_utterance=False,
                                  delivery_mode="primary", pronunciation_delivery_variant="locked_spoken_v1"):
                import hashlib

                self.synthesize_calls += 1
                self.delivery_modes.append(str(delivery_mode))
                self.seed_salts.append(str(seed_salt))
                seed = self.generation_seed(row, seed_salt)
                text = self.spoken_text(row)
                samples = int(48_000 * seconds_per_syllable * max(2, audio_io.spoken_syllables(text)))
                phase = float(seed % 997) / 997.0
                audio = quiet_edges(np.sin(np.linspace(phase, 50 + phase, samples, dtype=np.float32)) * 0.12)
                checksum, metrics = atomic_write_wav(output, audio, 48_000, text, self.settings,
                                                     segment=_voiced(self.db, row))
                profile = self.db.voice_profile(int(row["voice_profile_id"]))
                metrics.update({
                    "tts_delivery_mode": str(delivery_mode).strip().casefold(),
                    "spoken_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "pronunciation_delivery_variant": pronunciation_delivery_variant,
                    "voice_profile_id": int(profile["id"]),
                })
                return checksum, metrics, seed

        return Scaled(settings, db)


def _pipeline(tmp_path: Path, text: str, *, incumbent_seconds: float, seconds_per_syllable: float):
    from tests.test_pipeline_mock import PassPerceptualVerifier, _assign_locked_test_narrator, _voiced

    source = tmp_path / "001.txt"
    source.write_text(text, encoding="utf-8")
    settings = build_settings(overrides={
        "asr": {"repair_rounds": 2},
        "perceptual_qa": {"enabled": True},
        "tts": {"min_seconds_per_100_chars": 0.2, "pace_chars_per_second": [1.0, 100.0]},
    })
    paths, db, settings = create_or_open_project([source], tmp_path / "out", settings, "Repeat alias")
    pipeline = BookPipeline(paths=paths, db=db, settings=settings, pause_requested=lambda: False,
                            stop_requested=lambda: False, emit=lambda _kind, _payload: None)
    pipeline.tts = _TextLengthTTS(settings, db, seconds_per_syllable)
    pipeline.perceptual_qa = PassPerceptualVerifier()
    pipeline._recover()
    pipeline._ensure_segments()
    _assign_locked_test_narrator(db)
    chapter = db.list_chapters()[0]
    row = db.list_segments(chapter_id=int(chapter["id"]))[0]
    wav = pipeline._chunk_path(row)
    audio = quiet_edges(np.sin(np.linspace(0, 50, int(48_000 * incumbent_seconds), dtype=np.float32)) * 0.12)
    checksum, metrics = atomic_write_wav(wav, audio, 48_000, str(row["text"]), settings,
                                         segment=_voiced(db, row))
    db.mark_signal_passed(int(row["id"]), wav_path=wav, wav_sha256=checksum,
                          duration=float(metrics["duration"]), signal=metrics, generation_seed=1)
    pipeline._resource_gate = lambda *_args, **_kwargs: None
    pipeline._progress = lambda *_args, **_kwargs: None
    return pipeline, chapter, dict(db.get_segment(int(row["id"])))


class _SavedTranscripts:
    """Whole-line takes repeat the phrase once more; a merged split reads the text as written."""

    def __init__(self, repeated: str, doubled: str):
        settings = build_settings()
        settings["asr"].update(min_similarity=0.78, max_wer=0.3, min_words=1)
        self.gate = asr.WhisperVerifier(settings, lambda _message: None)
        self.gate._last_transcription_timeline_impossible = False
        self.repeated, self.doubled = repeated, doubled
        self.calls: list[str] = []

    def unload(self):
        pass

    def can_verify_repeated_short(self, _text):
        return False

    def verify(self, text, wav, *, confirmation=False):
        merged = ".split" in Path(wav).name or _is_alias_take(Path(wav))
        heard = text if merged else text.replace(self.repeated, self.doubled)
        self.calls.append("clean" if merged else "repeated")
        return self.gate._evaluate_transcript(text, heard, 20.0)


_ALIAS_TAKES: set[str] = set()


def _is_alias_take(path: Path) -> bool:
    return str(path.resolve()).casefold() in _ALIAS_TAKES


def _watch_alias_takes(pipeline, monkeypatch):
    original = pipeline._synthesize_split

    def tracked(row, output, **kwargs):
        provenance = original(row, output, **kwargs)
        if kwargs.get("split_strategy") == REPEAT_ALIAS_SPLIT_STRATEGY:
            _ALIAS_TAKES.add(str(Path(output).resolve()).casefold())
        return provenance

    monkeypatch.setattr(pipeline, "_synthesize_split", tracked)


def _promoted(pipeline, row) -> dict:
    with pipeline.db.connect() as conn:
        candidate = conn.execute(
            "SELECT * FROM segment_candidates WHERE segment_id=? AND state='promoted'", (int(row["id"]),)
        ).fetchone()
    assert candidate is not None
    return dict(candidate)


TWO_COPIES = "0. Câu thử đã gỡ. 0."


def test_two_takes_repeating_one_phrase_send_the_next_candidate_to_the_alias_split(tmp_path, monkeypatch):
    fingerprints = []
    for name in ("first", "replay"):
        folder = tmp_path / name
        folder.mkdir()
        pipeline, chapter, row = _pipeline(folder, TWO_COPIES, incumbent_seconds=4.0, seconds_per_syllable=0.25)
        _watch_alias_takes(pipeline, monkeypatch)
        verifier = _SavedTranscripts("Là đồ bơi, là đồ bơi", "Là đồ bơi, là đồ bơi, là đồ bơi")

        pipeline._verify_chapter_audio(chapter, verifier)

        fresh = pipeline.db.get_segment(int(row["id"]))
        # Published, flagged like every split recovery so the joins stay visible in the report.
        assert (fresh["status"], fresh["warning_code"]) == ("warning", "TTS_SPLIT_RECOVERY")
        promoted = _promoted(pipeline, row)
        # Round 0 was the ordinary clarity seed and repeated like the primary take did; round 1
        # never tried a direct seed at all.
        assert int(promoted["repair_round"]) == 1
        assert promoted["generation_strategy"] == "split_v1"
        signal = json.loads(promoted["signal_json"])
        assert signal[SPLIT_STRATEGY_FIELD] == REPEAT_ALIAS_SPLIT_STRATEGY
        assert fold_vietnamese_tones(signal[SPLIT_REPEAT_NGRAM_FIELD]) == fold_vietnamese_tones("là đồ bơi")
        assert len(signal["split_parts"]) == 2
        assert [s for s in pipeline.tts.seed_salts if s.startswith("asr_clarity_candidate_1")] == [
            "asr_clarity_candidate_1_split_part_0",
            "asr_clarity_candidate_1_split_part_1",
        ]
        # The durable evidence rebuilds the same decision on its own.
        evidence = pipeline.db.repeat_alias_split_evidence(
            segment_id=int(row["id"]), policy_hash=pipeline.quality_policy_hash, repair_round=1,
            incumbent_sha256=str(promoted["incumbent_sha256"]),
        )
        assert evidence == {"trigger": "repeated_takes", "ngram": signal[SPLIT_REPEAT_NGRAM_FIELD]}
        fingerprints.append((promoted["generation_seed"], promoted["wav_sha256"]))
    assert fingerprints[0] == fingerprints[1]


def test_the_database_refuses_an_alias_split_without_its_stored_evidence(tmp_path, monkeypatch):
    pipeline, chapter, row = _pipeline(tmp_path, TWO_COPIES, incumbent_seconds=4.0, seconds_per_syllable=0.25)
    _watch_alias_takes(pipeline, monkeypatch)
    pipeline._verify_chapter_audio(
        chapter, _SavedTranscripts("Là đồ bơi, là đồ bơi", "Là đồ bơi, là đồ bơi, là đồ bơi")
    )
    promoted = _promoted(pipeline, row)
    signal = json.loads(promoted["signal_json"])
    with pipeline.db.connect() as conn:
        candidate = conn.execute("SELECT * FROM segment_candidates WHERE id=?", (promoted["id"],)).fetchone()
        ProjectDB._require_candidate_split_provenance(conn, candidate, signal)  # holds as stored
        forged = dict(signal, **{SPLIT_REPEAT_NGRAM_FIELD: "cái cảnh"})
        with pytest.raises(RuntimeError, match="repeat-alias phrase differs"):
            ProjectDB._require_candidate_split_provenance(conn, candidate, forged)
    with pipeline.db.transaction() as conn:
        for check_id, raw in conn.execute(
            "SELECT id, metrics_json FROM quality_checks WHERE segment_id=?", (int(row["id"]),)
        ).fetchall():
            metrics = json.loads(raw)
            metrics.pop(asr.ASR_REPEATED_CONTENT_KEY, None)
            conn.execute("UPDATE quality_checks SET metrics_json=? WHERE id=?", (json.dumps(metrics), check_id))
    with pipeline.db.connect() as conn:
        candidate = conn.execute("SELECT * FROM segment_candidates WHERE id=?", (promoted["id"],)).fetchone()
        with pytest.raises(RuntimeError, match="lacks its stored repeated-content evidence"):
            ProjectDB._require_candidate_split_provenance(conn, candidate, signal)


def test_one_repeating_take_still_gets_an_ordinary_new_seed(tmp_path, monkeypatch):
    pipeline, chapter, row = _pipeline(tmp_path, TWO_COPIES, incumbent_seconds=4.0, seconds_per_syllable=0.25)
    _watch_alias_takes(pipeline, monkeypatch)

    class FirstTakeOnly(_SavedTranscripts):
        def verify(self, text, wav, *, confirmation=False):
            first = Path(wav).resolve() == Path(row["wav_path"]).resolve()
            heard = text.replace(self.repeated, self.doubled) if first else text
            return self.gate._evaluate_transcript(text, heard, 20.0)

    pipeline._verify_chapter_audio(
        chapter, FirstTakeOnly("Là đồ bơi, là đồ bơi", "Là đồ bơi, là đồ bơi, là đồ bơi")
    )
    promoted = _promoted(pipeline, row)
    assert int(promoted["repair_round"]) == 0
    assert promoted["generation_strategy"] == "direct_v1"
    assert not any("split" in salt for salt in pipeline.tts.seed_salts)


class _SimulatedCrash(BaseException):
    """Escape the adapter's ordinary quality-error handlers like a process exit."""


@pytest.mark.parametrize("boundary", ["before_split", "after_signal", "before_promotion"])
def test_alias_split_resumes_at_its_durable_boundary_without_changing_the_incumbent(
    tmp_path, monkeypatch, boundary,
):
    outcomes = []
    for label in ("control", "crash"):
        folder = tmp_path / label
        folder.mkdir()
        pipeline, chapter, row = _pipeline(folder, TWO_COPIES, incumbent_seconds=4.0, seconds_per_syllable=0.25)
        _watch_alias_takes(pipeline, monkeypatch)
        verifier = _SavedTranscripts("Là đồ bơi, là đồ bơi", "Là đồ bơi, là đồ bơi, là đồ bơi")
        if label == "crash":
            incumbent_path = Path(row["wav_path"])
            incumbent_bytes = incumbent_path.read_bytes()
            with monkeypatch.context() as patch:
                if boundary == "before_split":
                    original = pipeline._synthesize_split

                    def before(*args, **kwargs):
                        raise _SimulatedCrash()

                    patch.setattr(pipeline, "_synthesize_split", before)
                elif boundary == "after_signal":
                    original = pipeline.db.checkpoint_segment_candidate_signal

                    def after(*args, **kwargs):
                        answer = original(*args, **kwargs)
                        if kwargs["signal"].get(SPLIT_STRATEGY_FIELD) == REPEAT_ALIAS_SPLIT_STRATEGY:
                            raise _SimulatedCrash()
                        return answer

                    patch.setattr(pipeline.db, "checkpoint_segment_candidate_signal", after)
                else:
                    original = pipeline.db.promote_segment_candidate

                    def promotion(candidate_id, **kwargs):
                        if pipeline.db.get_segment_candidate(candidate_id)["generation_strategy"] == "split_v1":
                            raise _SimulatedCrash()
                        return original(candidate_id, **kwargs)

                    patch.setattr(pipeline.db, "promote_segment_candidate", promotion)
                with pytest.raises(_SimulatedCrash):
                    pipeline._verify_chapter_audio(chapter, verifier)
            assert incumbent_path.read_bytes() == incumbent_bytes
            assert pipeline.db.get_segment(int(row["id"]))["wav_sha256"] == row["wav_sha256"]
            reopened = ProjectDB(pipeline.db.path)
            resumed = BookPipeline(paths=pipeline.paths, db=reopened, settings=pipeline.settings,
                                   pause_requested=lambda: False, stop_requested=lambda: False,
                                   emit=lambda *_args: None)
            resumed.tts = pipeline.tts
            resumed.perceptual_qa = pipeline.perceptual_qa
            resumed._resource_gate = lambda *_args, **_kwargs: None
            resumed._progress = lambda *_args, **_kwargs: None
            resumed._recover()
            _watch_alias_takes(resumed, monkeypatch)
            pipeline = resumed
        pipeline._verify_chapter_audio(chapter, verifier)
        promoted = _promoted(pipeline, row)
        assert promoted["repair_round"] == 1
        signal = json.loads(promoted["signal_json"])
        assert signal[SPLIT_STRATEGY_FIELD] == REPEAT_ALIAS_SPLIT_STRATEGY
        outcomes.append((promoted["wav_sha256"], promoted["generation_seed"], signal["split_parts"]))
    assert outcomes[0] == outcomes[1]


def test_two_decodes_of_one_seed_cannot_supply_the_two_take_trigger(tmp_path, monkeypatch):
    pipeline, chapter, row = _pipeline(tmp_path, TWO_COPIES, incumbent_seconds=4.0, seconds_per_syllable=0.25)
    _watch_alias_takes(pipeline, monkeypatch)
    pipeline._verify_chapter_audio(
        chapter, _SavedTranscripts("Là đồ bơi, là đồ bơi", "Là đồ bơi, là đồ bơi, là đồ bơi")
    )
    promoted = _promoted(pipeline, row)
    with pipeline.db.transaction() as conn:
        for check_id, raw in conn.execute("SELECT id,metrics_json FROM quality_checks").fetchall():
            metrics = json.loads(raw)
            metrics["generation_seed"] = 1
            conn.execute("UPDATE quality_checks SET metrics_json=? WHERE id=?", (json.dumps(metrics), check_id))
    assert pipeline.db.repeat_alias_split_evidence(
        segment_id=int(row["id"]), policy_hash=pipeline.quality_policy_hash,
        repair_round=1, incumbent_sha256=promoted["incumbent_sha256"],
    ) is None


SHOUT = "Đấm hắn! Đấm hắn! Đấm hắn!"


def test_a_shout_far_longer_than_its_syllables_goes_to_the_alias_split_after_one_take(tmp_path, monkeypatch):
    # aynik 1138: six syllables read as eight, 2.92 s against an expected 1.53 s.
    pipeline, chapter, row = _pipeline(tmp_path, SHOUT, incumbent_seconds=2.92, seconds_per_syllable=0.25)
    signal = json.loads(row["signal_json"])
    from abook import voice_balance
    reference = voice_balance.constants_for("vieneu", "3.8.3", "Xuân Vĩnh").seconds_per_syllable
    assert signal[SYLLABLE_DURATION_RATIO_METRIC] == pytest.approx(2.92 / (6 * reference), rel=1e-3)
    assert signal[SYLLABLE_DURATION_OUTLIER_METRIC] == 1.0
    _watch_alias_takes(pipeline, monkeypatch)

    pipeline._verify_chapter_audio(chapter, _SavedTranscripts(SHOUT, SHOUT + " Đấm hắn!"))

    promoted = _promoted(pipeline, row)
    assert int(promoted["repair_round"]) == 0
    promoted_signal = json.loads(promoted["signal_json"])
    assert promoted_signal[SPLIT_STRATEGY_FIELD] == REPEAT_ALIAS_SPLIT_STRATEGY
    assert len(promoted_signal["split_parts"]) == 3
    assert pipeline.db.get_segment(int(row["id"]))["warning_code"] == "TTS_SPLIT_RECOVERY"


def test_a_two_word_line_is_never_split_whatever_the_evidence(tmp_path):
    pipeline, _chapter, row = _pipeline(tmp_path, "Ăn đi!", incumbent_seconds=2.0, seconds_per_syllable=0.25)
    assert pipeline._repeat_alias_split_ngram(row, 1, "Ăn đi!", str(row["wav_sha256"])) is None


# --- F4: the duration ruler only measures 5-12 syllables ---------------------------------------

@pytest.mark.parametrize(("syllables", "ratio", "outlier"), [
    (6, 1.80, 0.0), (6, 1.82, 1.0), (10, 1.51, 0.0), (10, 1.53, 1.0),
])
@pytest.mark.parametrize("preset", ["Đức Trí", "Ngọc Linh"])
def test_the_duration_flag_uses_the_p999_of_its_length_band(syllables, ratio, outlier, preset):
    from abook import voice_balance
    constants = voice_balance.constants_for("vieneu", "3.8.3", preset)
    seconds = syllables * constants.seconds_per_syllable * ratio
    text = " ".join(["ba"] * syllables) + "."
    audio = quiet_edges(np.sin(np.linspace(0, 50, int(48_000 * seconds), dtype=np.float32)) * 0.12)
    _array, metrics = audio_io.validate_audio_array(
        audio, text, build_settings(), 48_000,
        segment={"kind": "dialogue", "pace": "normal", audio_io.VOICE_BALANCE_FIELD: constants.key},
    )
    assert metrics[SYLLABLE_DURATION_OUTLIER_METRIC] == outlier


@pytest.mark.parametrize("syllables", [3, 13])
def test_outside_five_to_twelve_syllables_no_duration_flag_is_written(syllables):
    text = " ".join(["ba"] * syllables) + "."
    audio = quiet_edges(np.sin(np.linspace(0, 50, 48_000 * 3, dtype=np.float32)) * 0.12)
    _array, metrics = audio_io.validate_audio_array(
        audio, text, build_settings(), 48_000, segment={"kind": "dialogue", "pace": "normal"},
    )
    assert SYLLABLE_DURATION_OUTLIER_METRIC not in metrics


def test_an_uncalibrated_preset_has_no_duration_opinion():
    # The missing calibration must never silently become a shared 255ms reference.
    _array, metrics = audio_io.validate_audio_array(
        quiet_edges(np.sin(np.arange(48_000 * 3) / 30).astype(np.float32) * 0.12),
        "Đấm hắn! Đấm hắn! Đấm hắn!", build_settings(), 48_000,
        segment={"kind": "dialogue"},
    )
    assert SYLLABLE_DURATION_RATIO_METRIC not in metrics


# --- F3: the ceiling flag is no longer reserved for two-word lines ------------------------------

@pytest.mark.parametrize(("text", "flagged"), [
    ("Tôi hay đi một mình, ăn kem một mình, ngắm pháo hoa một mình.", True),
    (("Một câu rất dài, " * 20).strip(), False),  # > 256 chars: the SDK splits it, the cap is per chunk
])
def test_a_long_line_that_used_every_frame_is_flagged(tmp_path, monkeypatch, text, flagged):
    import abook.tts as tts_module
    from tests.test_pipeline_mock import _short_tts_pipeline

    pipeline, _chapter, row = _short_tts_pipeline(tmp_path, source_text=text)
    coordinator = pipeline.tts
    engine = coordinator.engine_for_profile(coordinator._voice_profile_for_row(row))
    engine.sample_rate = coordinator.sample_rate
    spoken_row = coordinator._spoken_row(row, pronunciation_delivery_variant="locked_spoken_v1")
    from abook import voice_balance

    profile = coordinator._voice_profile_for_row(row)
    spoken_row[tts_module.VOICE_BALANCE_FIELD] = voice_balance.constants_for_profile(profile).key
    frames = int(tts_module.vieneu_sampling_for_segment(spoken_row, coordinator.settings)["max_new_frames"])
    samples = frames * VIENEU_V3_CODEC_SAMPLES_PER_FRAME
    audio = quiet_edges((0.1 * np.sin(np.arange(samples) / 30)).astype(np.float32))
    monkeypatch.setattr(engine, "generate_one", lambda *a, **k: audio)
    monkeypatch.setattr(tts_module, "apply_speed_change", lambda audio, *a, **k: audio)
    monkeypatch.setattr(coordinator, "release_inference_cache", lambda: None)
    assert (len(str(spoken_row["text"])) <= VIENEU_SDK_CHUNK_MAX_CHARS) is flagged

    _checksum, metrics, _seed = coordinator.synthesize_atomic(row, tmp_path / "take.wav", "f3")

    assert bool(metrics.get(GENERATION_CEILING_METRIC)) is flagged
    assert sf.info(str(tmp_path / "take.wav")).frames > 0
