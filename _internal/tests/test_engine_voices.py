"""Giọng của nhiều máy đọc trong Studio (bước A): VieNeu cho phân vai tự động, ZeroTTS và Supertonic cho người nghe chọn tay.

- Điều phối viên giữ mỗi máy một adapter theo `voice_profiles.engine`, đổi bản thu về tần số dự án, tempo bằng WSOLA trừ máy tự
  đọc theo tốc độ (`native_tempo`: Supertonic, `engine_speed` của bảng, luật câu ngắn).
- Khoá cân bằng của máy khác: `<engine>@<phiên bản>/<giọng>/f100`; thiếu khoá là lỗi rõ, không thu bằng 1,0.
- Phân vai tự động KHÔNG đổi: cùng kịch bản chọn giọng ra đúng kết quả của main (14b4f06a).
- Người nghe chọn giọng ZeroTTS cho một nhân vật: hồ sơ ZeroTTS, mọi câu sang; giọng chủ sách chưa chọn (Supertonic F2) bị từ chối.
- Có mô-đun ZeroTTS trên máy (ABOOK_PREFERENCES trỏ tới thư mục có `zerotts/`): đúc ba câu thật trên CPU.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import abook.tts as tts_module
from abook import voice_balance
from abook.audio_io import VOICE_BALANCE_FIELD, AudioQualityError
from abook.character_registry import (
    PresetAllocator,
    assert_voice_stability,
    preset_gender_of_voice_key,
    voice_profile_spec,
)
from abook.config import build_settings
from abook.database import ProjectDB
from abook.listener_overrides import UNKNOWN_PRESET
from abook.tts import (
    SupertonicEngine,
    TTSCoordinator,
    VieNeuEngine,
    ZeroTTSEngine,
    is_fatal_tts_error,
)
from abook.voice_balance import VoiceBalanceError
from abook.voice_catalog import (
    ENGINE_VOICES,
    VIENEU_PRESETS,
    castable_engine_voices,
    casting_presets,
    engine_voice,
    narrator_presets,
)
from tests.test_listener_voices import _apply, _book, _character, _statuses, _voice

ZEROTTS = engine_voice("baotrang")
SUPERTONIC = engine_voice("F1")


def _profile(db: ProjectDB, spec: dict) -> dict:
    return dict(db.voice_profile(db.upsert_voice_profile(spec)))


# --- danh mục, khoá ---------------------------------------------------------------------------


def test_the_owner_approved_voices_are_in_the_catalog() -> None:
    assert {(voice["engine"], voice["name"]) for voice in castable_engine_voices()} == {
        ("zerotts", "baotrang"), ("zerotts", "giahuy"), ("zerotts", "huuduc"), ("zerotts", "kimoanh"), ("zerotts", "quangminh"),
        ("supertonic", "F1"), ("supertonic", "F3"), ("supertonic", "M4"), ("supertonic", "M5"),
    }
    # Sáu giọng Supertonic còn lại: có số cân bằng nhưng chủ sách chưa chọn.
    closed = {voice["name"] for voice in ENGINE_VOICES if not voice["castable"]}
    assert closed == {"F2", "F4", "F5", "M1", "M2", "M3"}
    # Không trùng tên với preset VieNeu: tên giọng là khoá trong DB và trong yêu cầu của người nghe.
    assert not {voice["name"] for voice in ENGINE_VOICES} & {preset["name"] for preset in VIENEU_PRESETS}


def test_an_engine_voice_profile_is_one_step_with_its_own_key() -> None:
    spec = voice_profile_spec(ZEROTTS, 1.0)
    assert spec["voice_key"] == "zerotts_baotrang_f100_p+00"
    assert (spec["engine"], spec["preset_name"], spec["pitch_semitones"], spec["formant_ratio"]) == ("zerotts", "baotrang", 0, 1.0)
    assert preset_gender_of_voice_key(spec["voice_key"]) == "female"
    assert preset_gender_of_voice_key(voice_profile_spec(engine_voice("giahuy"), 1.0)["voice_key"]) == "male"
    # VieNeu tra như trước.
    assert preset_gender_of_voice_key("preset_ngoc_linh_f093_p+00") == "female"
    assert preset_gender_of_voice_key("preset_pham_tuyen_f100_p+00") == "male"
    # Thang formant và cao độ theo tuổi là của VieNeu.
    with pytest.raises(ValueError):
        voice_profile_spec(ZEROTTS, 0.93)
    with pytest.raises(ValueError):
        voice_profile_spec(ZEROTTS, 1.0, age_pitch=3)


def test_engine_voices_have_balance_keys_and_a_missing_one_is_an_error() -> None:
    key = voice_balance.voice_key_for_profile({"engine": "zerotts", "preset_name": "baotrang", "formant_ratio": 1.0})
    assert key == "zerotts@0.1.5/baotrang/f100"
    constants = voice_balance.constants_for_key(key)
    assert constants.r == pytest.approx(1.0427) and constants.ref_lufs == pytest.approx(-22.56) and constants.pitch_st == 0
    for voice in castable_engine_voices():
        voice_balance.constants_for_profile({"engine": voice["engine"], "preset_name": voice["name"], "formant_ratio": 1.0})
    # Supertonic: tốc độ là tham số của máy (`engine_speed`), WSOLA không kéo thêm (r = 1).
    f3 = voice_balance.constants_for_profile({"engine": "supertonic", "preset_name": "F3", "formant_ratio": 1.0})
    assert (f3.key, f3.r, f3.engine_speed, f3.ref_lufs) == ("supertonic@3-724fb5ab/F3/f100", 1.0, pytest.approx(1.938), -26.03)
    assert voice_balance.engine_speed(f3) == pytest.approx(1.938)
    assert voice_balance.engine_speed(constants) is None
    # Sàn cổng nhịp riêng của Supertonic (x 0,9), các máy khác như cũ.
    assert voice_balance.pace_gate_scale(f3.key) == pytest.approx(voice_balance.pace_gate_scale() * 0.9)
    assert voice_balance.pace_gate_scale(key) == pytest.approx(voice_balance.pace_gate_scale())
    # Giọng chưa đo: lỗi rõ, không bao giờ 1,0.
    with pytest.raises(VoiceBalanceError, match="chưa có"):
        voice_balance.constants_for_profile({"engine": "zerotts", "preset_name": "maichi", "formant_ratio": 1.0})
    with pytest.raises(VoiceBalanceError):
        voice_balance.constants_for_profile({"engine": "zerotts", "preset_name": "baotrang", "formant_ratio": 0.93})
    with pytest.raises(VoiceBalanceError):
        voice_balance.engine_version("máy lạ")


# --- phân vai tự động không đổi -----------------------------------------------------------------

# sha256 của kịch bản dưới đây chạy trên main 14b4f06a (trước khung nhiều máy đọc).
ALLOCATOR_ON_MAIN = "fe9c6cbd4189b73cded4eb2f79cbd9559b15b04d6182821d5272e2820ff70fb9"


def test_automatic_casting_is_exactly_what_it_was() -> None:
    allocator = PresetAllocator("Phạm Tuyên", 2, other_narrators=("Đức Trí",))
    genders = ("male", "female", "unknown")
    ages = ("adult", "child", "teen", "elderly", "unknown", "adult")
    for index in range(36):
        allocator.note_chapters(f"P{index}", {index % 5, (index * 3) % 7})
    picks = []
    for index in range(36):
        preset, ratio, pitch = allocator.choose(genders[index % 3], npc=index % 4 == 3, age=ages[index % 6], who=f"P{index}")
        picks.append([preset["name"], round(ratio, 3), pitch])
    pools = {gender: [preset["name"] for preset in casting_presets(gender)] for gender in ("male", "female")}
    narrators = [preset["name"] for preset in narrator_presets()]
    data = json.dumps({"picks": picks, "pools": pools, "narrators": narrators}, ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(data.encode()).hexdigest() == ALLOCATOR_ON_MAIN
    engine_names = {voice["name"] for voice in ENGINE_VOICES}
    assert not engine_names & {name for name, _ratio, _pitch in picks}


# --- người nghe chọn tay ------------------------------------------------------------------------


def test_a_listener_picks_a_zerotts_voice_and_every_line_moves(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    result = _apply(db, "Lucien", preset="giahuy")

    assert result is not None and result["voice_key"] == "zerotts_giahuy_f100_p+00"
    assert _voice(db, "LUCIEN") == {"zerotts_giahuy_f100_p+00"}
    profile = db.voice_profile_by_key("zerotts_giahuy_f100_p+00")
    assert (profile["engine"], profile["preset_name"], profile["formant_ratio"]) == ("zerotts", "giahuy", 1.0)
    assert _statuses(db, "LUCIEN") == {"analyzed"}, "câu đã thu phải thu lại bằng giọng mới"
    assert _statuses(db, "NATASHA") == {"verified"}
    lucien = _character(db, "LUCIEN")
    assert (lucien["gender"], lucien["locked_voice_key"]) == ("male", "zerotts_giahuy_f100_p+00")
    assert_voice_stability(db)
    assert _apply(db, "LUCIEN", preset="giahuy") is None, "áp lại yêu cầu đã áp: không đổi gì"
    # Chọn giọng nữ của ZeroTTS: giới đi theo giọng, như với VieNeu.
    _apply(db, "NOAH", preset="kimoanh")
    assert _character(db, "NOAH")["gender"] == "female"


def test_a_voice_without_balance_numbers_cannot_be_picked(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    assert _apply(db, "Lucien", preset="F2") == {"problem": UNKNOWN_PRESET}


# --- điều phối viên ---------------------------------------------------------------------------


def test_the_coordinator_hands_each_profile_to_its_own_engine(tmp_path: Path) -> None:
    coordinator = TTSCoordinator(build_settings(), ProjectDB(tmp_path / "p.sqlite3"), lambda _message: None)
    assert isinstance(coordinator.engine_for_profile({"engine": "vieneu"}), VieNeuEngine)
    assert isinstance(coordinator.engine_for_profile({"engine": "zerotts"}), ZeroTTSEngine)
    assert isinstance(coordinator.engine_for_profile({"engine": "supertonic"}), SupertonicEngine)
    assert coordinator.engine("zerotts") is coordinator.engine("zerotts"), "một adapter mỗi máy"
    assert coordinator.vieneu is coordinator.engine("vieneu")
    with pytest.raises(AudioQualityError) as failure:
        coordinator.engine("máy lạ")
    assert is_fatal_tts_error(failure.value), "giọng của máy không có: dừng, không đổi giọng âm thầm"


def _row(db: ProjectDB, spec: dict, text: str = "Trời vừa sáng, cha đã nhờ thằng nhóc hàng xóm báo tin tới tận nơi.") -> dict:
    return {
        "voice_profile_id": int(db.upsert_voice_profile(spec)),
        "stable_id": "engine_1",
        "text": text,
        "kind": "dialogue",
        "speaker": "LUCIEN",
        "emotion": "neutral",
        "intensity": 0,
        "pace": "normal",
    }


def test_another_engine_is_resampled_and_balanced_like_vieneu(tmp_path: Path, monkeypatch) -> None:
    db = ProjectDB(tmp_path / "p.sqlite3")
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    row = _row(db, voice_profile_spec(ZEROTTS, 1.0))
    zerotts = coordinator.engine("zerotts")
    zerotts.sample_rate = 24_000
    calls: list[dict] = []

    def generate_one(spoken_row, profile, seed, *, sampling):
        calls.append({"engine": profile["engine"], "seed": seed, "frames": sampling["max_new_frames"]})
        return np.zeros(24_000, dtype=np.float32)

    speeds: list[tuple[int, float]] = []
    written: list[tuple[int, int, str]] = []
    monkeypatch.setattr(zerotts, "generate_one", generate_one)
    monkeypatch.setattr(tts_module, "apply_speed_change", lambda audio, rate, speed: speeds.append((rate, speed)) or audio)
    monkeypatch.setattr(
        tts_module,
        "atomic_write_wav",
        lambda _path, audio, rate, _text, _settings, segment: written.append((len(audio), rate, segment[VOICE_BALANCE_FIELD]))
        or ("checksum", {}),
    )

    _checksum, metrics, seed = coordinator.synthesize_atomic(row, tmp_path / "a.wav")

    assert calls and calls[0]["engine"] == "zerotts" and calls[0]["seed"] == seed
    # 24 kHz của máy -> 48 kHz của dự án, trước tempo và độ to.
    assert written == [(48_000, 48_000, "zerotts@0.1.5/baotrang/f100")]
    assert speeds == [(48_000, pytest.approx(1.0427))], "tempo x*r_v bằng WSOLA như VieNeu"
    assert metrics["effective_speed_factor"] == pytest.approx(1.0427)
    assert coordinator.vieneu.tts is None, "câu của giọng ZeroTTS không nạp VieNeu"


def test_an_engine_with_its_own_tempo_is_not_stretched_twice(tmp_path: Path, monkeypatch) -> None:
    db = ProjectDB(tmp_path / "p.sqlite3")
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    row = _row(db, voice_profile_spec(engine_voice("M4"), 1.0))
    supertonic = coordinator.engine("supertonic")
    given: list[float] = []
    stretched: list[float] = []
    table = copy.deepcopy(voice_balance.load_table())
    table["x"] = 0.9
    monkeypatch.setattr(voice_balance, "load_table", lambda: table)
    monkeypatch.setattr(supertonic, "generate_one", lambda *_a, sampling, speed: given.append(speed) or np.zeros(44_100, np.float32))
    monkeypatch.setattr(tts_module, "apply_speed_change", lambda audio, _rate, speed: stretched.append(speed) or audio)
    monkeypatch.setattr(tts_module, "atomic_write_wav", lambda *_args, **_kwargs: ("checksum", {}))

    _checksum, metrics, _seed = coordinator.synthesize_atomic(row, tmp_path / "a.wav")

    # Tham số tốc độ của máy nhân núm chung x; WSOLA không kéo lần hai.
    assert given == [pytest.approx(0.9 * 1.700)] and stretched == []
    assert metrics["speed_factor"] == metrics["effective_speed_factor"] == pytest.approx(0.9)


def test_a_kept_english_name_is_vietnamized_only_for_an_engine_that_cannot_speak_english(tmp_path: Path) -> None:
    """Mọi máy đọc hiện có nói được tiếng Anh (Supertonic: đo 2040 bản thu 04-10). Một máy không nói được (adapter giả, cờ False) nhận dạng
    Việt hoá của tên Anh để nguyên, cho riêng đoạn của nó."""
    from abook.english_vi import vietnamized_english
    from abook.models import KEEP_ENGLISH_PRONUNCIATION_SOURCE

    class NoEnglish(ZeroTTSEngine):
        speaks_english = False

    db = ProjectDB(tmp_path / "p.sqlite3")
    db.upsert_pronunciation(surface="Kate", normalized_surface="kate", spoken_form="Kate", confidence=0.95,
                            source=KEEP_ENGLISH_PRONUNCIATION_SOURCE, locked=True)
    settings = build_settings()
    coordinator = TTSCoordinator(settings, db, lambda _message: None)
    said = vietnamized_english("Kate")
    assert said and said != "Kate"
    assert VieNeuEngine.speaks_english and ZeroTTSEngine.speaks_english and SupertonicEngine.speaks_english

    vieneu_row = _row(db, voice_profile_spec(VIENEU_PRESETS[0], 1.0), "Kate gật đầu.")
    zerotts_row = _row(db, voice_profile_spec(ZEROTTS, 1.0), "Kate gật đầu.")
    supertonic_row = _row(db, voice_profile_spec(SUPERTONIC, 1.0), "Kate gật đầu.")
    for row in (vieneu_row, zerotts_row, supertonic_row):
        assert coordinator.spoken_text(row) == "Kate gật đầu."

    coordinator.engines[ZeroTTSEngine.name] = NoEnglish(settings, lambda _message: None)
    assert coordinator.spoken_text(vieneu_row) == "Kate gật đầu."
    assert coordinator.spoken_text(supertonic_row) == "Kate gật đầu."
    # Cùng chữ ấy là chữ khâu chấm ASR so (pipeline lấy `spoken_text`), nên đoạn của máy ấy được chấm theo dạng Việt hoá.
    assert coordinator.spoken_text(zerotts_row) == f"{said} gật đầu."


def test_short_supertonic_lines_slow_down_until_they_meet_the_voice_speed() -> None:
    assert tts_module.supertonic_speed("Về rồi?", 1.82) == pytest.approx(1.28)
    assert tts_module.supertonic_speed("Sao cô biết điều đó?", 1.82) == pytest.approx(1.28 + 0.06 * 3)
    long = "Trời vừa sáng, cha đã nhờ thằng nhóc hàng xóm báo tin tới tận nơi."
    assert tts_module.supertonic_speed(long, 1.82) == pytest.approx(1.82)
    assert tts_module.supertonic_speed(long, 1.468) == pytest.approx(1.468)


def test_a_long_zerotts_line_is_read_in_chunks_and_joined_with_a_pause() -> None:
    short = "Trời vừa sáng, cha đã nhờ thằng nhóc hàng xóm báo tin tới tận nơi."
    assert ZeroTTSEngine.chunks(short) == [short], "câu ngắn đọc một lần như trước"
    long = " ".join([short] * 4)
    chunks = ZeroTTSEngine.chunks(long)
    assert len(chunks) > 1 and all(len(chunk) <= ZeroTTSEngine.MAX_CHUNK_CHARS for chunk in chunks)
    assert " ".join(chunks) == long, "mọi chữ đọc đúng một lần, theo thứ tự, không qua phép đọc riêng của Nghe ngay"

    class FakeZeroTTS:
        frame_rate = 12.5
        sample_rate = 48_000

        def __init__(self) -> None:
            self.texts: list[str] = []

        def synthesize(self, text, *, voice, max_frames):
            self.texts.append(text)
            return np.full((1, 4_800), 0.5, dtype=np.float32)

    engine = ZeroTTSEngine(build_settings(), lambda _message: None)
    engine.tts, engine.voices, engine.sample_rate = FakeZeroTTS(), ["baotrang"], 48_000
    profile = {"engine": "zerotts", "preset_name": "baotrang", "voice_key": "k"}
    audio = engine.generate_one({"text": long, "speaker": "A", "pace": "normal"}, profile, 7, sampling={"max_new_frames": 300})
    assert engine.tts.texts == chunks
    silent = int(np.count_nonzero(audio == 0.0))
    assert audio.size == 4_800 * len(chunks) + silent and silent == int(0.2 * 48_000) * (len(chunks) - 1)


# --- máy thật (CPU) ---------------------------------------------------------------------------


def _engine_on_this_machine(engine: str) -> bool:
    from abook.webui import supertonic_module, zerotts_module

    module = {"zerotts": zerotts_module, "supertonic": supertonic_module}[engine]
    before = module._core.folder
    try:
        return module.locate() is not None
    finally:
        module._core.folder = before  # không để chỗ mặc định lọt sang bài khác


@pytest.mark.parametrize(
    ("engine", "voice", "preset"),
    [
        pytest.param("zerotts", "zerotts_huuduc_f100_p+00", "huuduc", marks=pytest.mark.skipif(
            not _engine_on_this_machine("zerotts"), reason="máy này chưa tải giọng ZeroTTS")),
        pytest.param("supertonic", "supertonic_m4_f100_p+00", "M4", marks=pytest.mark.skipif(
            not _engine_on_this_machine("supertonic"), reason="máy này chưa tải giọng Supertonic")),
    ],
)
def test_three_real_lines_in_a_listener_picked_voice(tmp_path: Path, monkeypatch, engine: str, voice: str, preset: str) -> None:
    import soundfile as sf

    from abook.webui import supertonic_module, zerotts_module

    for module in (zerotts_module, supertonic_module):  # adapter gọi locate(): trả lại sau bài
        monkeypatch.setattr(module._core, "folder", module._core.folder)
    _paths, db = _book(tmp_path)
    assert _apply(db, "Lucien", preset=preset) is not None
    profile_id = int(db.voice_profile_by_key(voice)["id"])
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    lines = (
        "Thứ mà ta truy cầu là chân lý của ma thuật, chứ không phải thần linh nào hết.",
        "Con cứ coi như không nghe thấy gì là được, đừng bận tâm làm chi cho mệt.",
        "Về rồi?",
    )
    checksums = []
    for index, text in enumerate(lines):
        row = {"voice_profile_id": profile_id, "stable_id": f"real_{index}", "text": text, "kind": "dialogue",
               "speaker": "LUCIEN", "emotion": "neutral", "intensity": 0, "pace": "normal"}
        output = tmp_path / f"real_{index}.wav"
        checksum, metrics, _seed = coordinator.synthesize_atomic(row, output)
        info = sf.info(str(output))
        assert (info.samplerate, info.channels) == (48_000, 1)
        assert metrics.get("pace_outlier", 0.0) == 0.0, (text, metrics.get("chars_per_second"))  # câu 1-3 tiếng không qua cổng nhịp
        checksums.append(checksum)
    # Cùng câu cùng giọng: cùng byte (hạt giống đi vào bộ lấy mẫu của máy).
    again, _metrics, _seed = coordinator.synthesize_atomic(
        {"voice_profile_id": profile_id, "stable_id": "real_0", "text": lines[0], "kind": "dialogue", "speaker": "LUCIEN",
         "emotion": "neutral", "intensity": 0, "pace": "normal"},
        tmp_path / "again.wav",
    )
    assert again == checksums[0]
    assert coordinator.vieneu.tts is None
