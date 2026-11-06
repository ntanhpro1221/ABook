"""Giọng của nhiều máy đọc trong Studio (bước A): VieNeu cho phân vai tự động, ZeroTTS và Supertonic cho người nghe chọn tay.

- Điều phối viên giữ mỗi máy một adapter theo `voice_profiles.engine`, đổi bản thu về tần số dự án, tempo bằng WSOLA trừ máy tự
  đọc theo tốc độ (`native_tempo`: Supertonic, `engine_speed` của bảng, luật câu ngắn).
- Khoá cân bằng của máy khác: `<engine>@<phiên bản>/<giọng>`; thiếu khoá là lỗi rõ, không thu bằng 1,0.
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
from abook import voice_balance, voice_catalog
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


# --- phân vai tự động không đổi -----------------------------------------------------------------

# sha256 của kịch bản dưới đây chạy trên main 14b4f06a (trước khung nhiều máy đọc), sau khi đổi tên ba giọng Turbo theo
# VieNeu 3.8.2 (dev/upgrades-1004): tên là chỗ phân xử cuối của thứ tự bể giọng (`casting_preset_priority`), nên "Thiện Minh"
# (trước là "Anh Khôi") nay đứng sau "Thiền Tâm Đức" - 2 nhân vật đổi chỗ hai giọng ấy, 1 nhân vật đổi bậc cao độ (2 -> 3).
# Bản trên main 14b4f06a: fe9c6cbd4189b73cded4eb2f79cbd9559b15b04d6182821d5272e2820ff70fb9.
# 05-11 (dev/cast-rank) đổi CÓ CHỦ ĐÍCH: phán quyết giọng nam của chủ sách vào `assets/voice_rank.json` (nhân vật nam: Xuân Vĩnh trước,
# rồi Đức Trí/Thiền Tâm Đức/Phạm Tuyên, rồi Thái Sơn/Adam; nữ: Ngọc Linh, Đoan Trang, rồi nhóm ổn; thứ tự giọng dẫn theo bậc kể chuyện), Thái Sơn và
# Thục Đoan ra khỏi LAST_RESORT_PRESETS, trẻ con đi bằng preset nữ nguyên giọng (cao độ 0, formant 1,0).
# Bản trước đó: 2bffd9a02889d1cb634048d7236bdb6f470b872a43c3dac8441a706cd7339339.
# 06-11: Mai Anh withdrawn; narrator female starts with Đoan Trang, character female with Ngọc Linh.
ALLOCATOR_APPROVED = "136258871e0ca8626309ce49dfaafc877edfe46b0190e7671182babf8a38f3ec"


def test_every_vieneu_voice_has_one_fixed_cast_rank() -> None:
    names = [str(preset["name"]) for preset in voice_catalog.VIENEU_PRESETS]
    assert sorted(names) == sorted(voice_catalog.CAST_ORDER)
    assert len(set(voice_catalog.CAST_ORDER)) == len(voice_catalog.CAST_ORDER)


@pytest.mark.parametrize("old", ["Thiện Minh", "Adam", "Đức Trí"])
def test_renaming_a_voice_keeps_its_place_in_casting(old: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # VieNeu đổi tên giọng thì tên được sửa tại chỗ trong VIENEU_PRESETS và CAST_ORDER: thứ tự bể giọng và người kể giữ nguyên
    # dù tên mới đứng chỗ khác trong bảng chữ cái.
    def order() -> list[list[str]]:
        return [[str(p["name"]) for p in casting_presets(g)] for g in ("male", "female")] + [
            [str(p["name"]) for p in narrator_presets()]
        ]

    before = order()
    for new in ("Aaa thử", "Zzz thử"):
        with monkeypatch.context() as patch:
            presets = tuple({**p, "name": new} if p["name"] == old else p for p in voice_catalog.VIENEU_PRESETS)
            cast = tuple(new if name == old else name for name in voice_catalog.CAST_ORDER)
            patch.setattr(voice_catalog, "VIENEU_PRESETS", presets)
            patch.setattr(voice_catalog, "CAST_ORDER", cast)
            patch.setattr(voice_catalog, "_CAST_RANK", {name: rank for rank, name in enumerate(cast)})
            # Tên cũng nằm ở bảng xếp hạng của người nghe và ở giọng dẫn mặc định: đổi tên thì sửa tại chỗ ở cả hai.
            patch.setattr(
                voice_catalog,
                "VOICE_RANK",
                {
                    role: {
                        gender: tuple(tuple(new if name == old else name for name in tier) for tier in tiers)
                        for gender, tiers in genders.items()
                    }
                    for role, genders in voice_catalog.VOICE_RANK.items()
                },
            )
            patch.setattr(
                voice_catalog,
                "DEFAULT_NARRATOR_BY_GENDER",
                {gender: new if name == old else name for gender, name in voice_catalog.DEFAULT_NARRATOR_BY_GENDER.items()},
            )
            after = [[old if name == new else name for name in names] for names in order()]
        assert after == before, new


# --- người nghe chọn tay ------------------------------------------------------------------------


def test_a_listener_picks_a_zerotts_voice_and_every_line_moves(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    result = _apply(db, "Lucien", preset="giahuy")

    assert result is not None and result["voice_key"] == "zerotts@0.1.5/giahuy"
    assert _voice(db, "LUCIEN") == {"zerotts@0.1.5/giahuy"}
    profile = db.voice_profile_by_key("zerotts@0.1.5/giahuy")
    assert (profile["engine"], profile["preset_name"]) == ("zerotts", "giahuy")
    assert _statuses(db, "LUCIEN") == {"analyzed"}, "câu đã thu phải thu lại bằng giọng mới"
    assert _statuses(db, "NATASHA") == {"verified"}
    lucien = _character(db, "LUCIEN")
    assert (lucien["gender"], lucien["locked_voice_key"]) == ("male", "zerotts@0.1.5/giahuy")
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
    row = _row(db, voice_profile_spec(ZEROTTS))
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
    assert written == [(48_000, 48_000, "zerotts@0.1.5/baotrang")]
    assert speeds == [(48_000, pytest.approx(1.0427))], "tempo x*r_v bằng WSOLA như VieNeu"
    assert metrics["effective_speed_factor"] == pytest.approx(1.0427)
    assert coordinator.vieneu.tts is None, "câu của giọng ZeroTTS không nạp VieNeu"


def test_an_engine_with_its_own_tempo_is_not_stretched_twice(tmp_path: Path, monkeypatch) -> None:
    db = ProjectDB(tmp_path / "p.sqlite3")
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    row = _row(db, voice_profile_spec(engine_voice("M4")))
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

    vieneu_row = _row(db, voice_profile_spec(VIENEU_PRESETS[0]), "Kate gật đầu.")
    zerotts_row = _row(db, voice_profile_spec(ZEROTTS), "Kate gật đầu.")
    supertonic_row = _row(db, voice_profile_spec(SUPERTONIC), "Kate gật đầu.")
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
    # Mảnh nào cũng kết thúc bằng dấu chấm: lặng chèn = tổng theo dấu - phần mép chừa (tests/test_chunk_join.py).
    gap = round((tts_module.chunk_gap_seconds(".") - 2 * tts_module.CHUNK_TRIM_KEEP_SECONDS) * 48_000)
    assert audio.size == 4_800 * len(chunks) + gap * (len(chunks) - 1)


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
        pytest.param("zerotts", "zerotts@0.1.5/huuduc", "huuduc", marks=pytest.mark.skipif(
            not _engine_on_this_machine("zerotts"), reason="máy này chưa tải giọng ZeroTTS")),
        pytest.param("supertonic", "supertonic@3-724fb5ab/M4", "M4", marks=pytest.mark.skipif(
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


@pytest.mark.skipif(not _engine_on_this_machine("zerotts"), reason="máy này chưa tải giọng ZeroTTS")
def test_zerotts_reads_the_same_bytes_after_its_session_is_rebuilt(monkeypatch) -> None:
    from abook.webui import zerotts_module

    monkeypatch.setattr(zerotts_module._core, "folder", zerotts_module._core.folder)  # adapter gọi locate(): trả lại sau bài
    monkeypatch.setattr(ZeroTTSEngine, "RECYCLE_AFTER_CALLS", 1)  # nạp lại trước MỌI câu sau câu đầu
    engine = ZeroTTSEngine(build_settings(), lambda _message: None)
    profile = {"engine": "zerotts", "preset_name": "huuduc", "voice_key": "zerotts@0.1.5/huuduc"}
    row = {"text": "Con cứ coi như không nghe thấy gì là được.", "speaker": "A", "pace": "normal"}
    try:
        first = engine.generate_one(row, profile, 7, sampling={"max_new_frames": 300})
        session = engine.tts
        again = engine.generate_one(row, profile, 7, sampling={"max_new_frames": 300})
        assert engine.tts is not session, "phiên ONNX đã được nạp lại giữa hai lần gọi"
        assert first.tobytes() == again.tobytes(), "cùng câu, giọng, hạt giống: cùng byte trước và sau khi nạp lại"
    finally:
        engine.unload()

def test_engine_profile_is_a_preset_without_dsp_fields():
    spec = voice_profile_spec(ZEROTTS)
    assert spec['voice_key'] == 'zerotts@0.1.5/baotrang'
    assert spec['engine'] == 'zerotts' and spec['preset_name'] == 'baotrang'
    assert 'pitch_semitones' not in spec and 'formant_ratio' not in spec
    assert preset_gender_of_voice_key(spec['voice_key']) == 'female'


def test_engine_constants_keep_native_tempo_and_missing_key_errors():
    for voice in castable_engine_voices():
        constants = voice_balance.constants_for_profile({'engine': voice['engine'], 'preset_name': voice['name']})
        assert constants.r > 0
    f3 = voice_balance.constants_for_profile({'engine': 'supertonic', 'preset_name': 'F3'})
    assert f3.r == 1.0 and f3.engine_speed == pytest.approx(1.938)
    with pytest.raises(VoiceBalanceError):
        voice_balance.constants_for_profile({'engine': 'zerotts', 'preset_name': 'missing'})


def test_automatic_casting_uses_only_vieneu_presets_without_variants():
    allocator = PresetAllocator('Phạm Tuyên', other_narrators=('Đức Trí',))
    picks = [allocator.choose(gender, npc=False, age=age)['name']
             for gender in ('male','female','unknown') for age in ('child','teen','adult','elderly')]
    assert set(picks) <= {p['name'] for p in VIENEU_PRESETS}
    assert not set(picks) & {'Phạm Tuyên','Đức Trí'}
