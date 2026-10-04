"""Bộ hằng số cân bằng giọng: bảng, tempo, gain hằng số, offset, trần đỉnh, màu giọng."""
from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from abook import audio_io, tts, voice_balance
from abook.audio_io import (
    VOICE_BALANCE_FIELD,
    atomic_write_wav,
    level_segment,
    merge_wav_parts_atomic,
    normalize_segment_level,
    segment_gain_db,
    segment_offsets_db,
)
from abook.character_registry import voice_profile_spec
from abook.config import build_settings
from abook.runtime_contract import CRITICAL_RUNTIME_DISTRIBUTIONS
from abook.voice_balance import VoiceBalanceError
from abook.voice_catalog import (
    SPEED_FACTOR_MAX,
    SPEED_FACTOR_MIN,
    STYLE_NEWS,
    VIENEU_PRESETS,
    ENGINE_VOICES,
    base_pitch_for_preset,
    castable_engine_voices,
    casting_presets,
    narrator_presets,
    preset_by_name,
)

RATE = 48_000
KEY = "vieneu@3.8.3/Phạm Tuyên/f100"
OTHER_KEY = "vieneu@3.8.3/Đức Trí/f100"


def _tone(amplitude: float, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(RATE * seconds), dtype=np.float32) / RATE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def _segment(**fields) -> dict:
    return {
        "kind": "dialogue",
        "speaker": "Nhân vật",
        "volume": "normal",
        "emotion": "neutral",
        "intensity": 0,
        VOICE_BALANCE_FIELD: KEY,
        **fields,
    }


def _with_table(monkeypatch, **changes) -> dict:
    table = copy.deepcopy(voice_balance.load_table())
    table.update(changes)
    monkeypatch.setattr(voice_balance, "load_table", lambda: table)
    return table


# --- bảng -----------------------------------------------------------------------------


def test_the_table_loads_and_matches_the_pinned_engine() -> None:
    table = voice_balance.load_table()
    assert table["version"] == voice_balance.TABLE_VERSION
    # Một sự thật ghi hai chỗ: phiên bản engine của bảng phải là bản ghim ở runtime_contract.
    assert voice_balance.engine_version("vieneu") == CRITICAL_RUNTIME_DISTRIBUTIONS["vieneu"][1]


def test_every_castable_voice_has_a_record() -> None:
    keys = list(voice_balance.castable_keys())
    assert keys
    missing = [key for key in keys if key not in voice_balance.load_table()["voices"]]
    assert not missing, missing[:5]
    # Phủ ít nhất mọi giọng mà phân vai và người kể thật sự dùng, ở bậc formant gốc.
    version = voice_balance.engine_version("vieneu")
    for gender in ("male", "female"):
        for preset in casting_presets(gender) + narrator_presets(gender):
            voice_balance.constants_for("vieneu", version, preset["name"], 1.0)
    for name in voice_balance.balanced_preset_names():
        voice_balance.constants_for("vieneu", version, name, 1.0)


def test_the_table_holds_no_stray_voices() -> None:
    # Ngoài các khoá phân vai / chọn tay được: giọng máy khác đã đo mà chủ sách chưa chọn (vẫn trong danh mục, castable=False).
    measured = {f"{voice['engine']}@{voice_balance.engine_version(voice['engine'])}/{voice['name']}/f100" for voice in ENGINE_VOICES}
    expected = set(voice_balance.castable_keys()) | measured
    assert set(voice_balance.load_table()["voices"]) == expected


def test_the_table_covers_exactly_the_castable_and_narrator_voices() -> None:
    # Phân vai được ∪ người kể chọn được: giọng miền Trung không phân vai nhưng vẫn kể chuyện được nên phải có số; giọng Tin tức
    # không ở đâu chọn được nên không có bản ghi (khi casting mở chúng thì đo rồi mới thêm).
    names = set(voice_balance.balanced_preset_names())
    assert {"Quang Sơn", "Ngọc Trân"} <= names
    news = {preset["name"] for preset in VIENEU_PRESETS if preset["style"] == STYLE_NEWS}
    assert news and not news & names
    in_table = {key.split("/")[1] for key in voice_balance.load_table()["voices"] if key.startswith("vieneu@")}
    assert in_table == names
    # Máy đọc khác: đúng các giọng trong danh mục (chọn tay được hay chưa), mỗi giọng một bậc gốc.
    others = {key for key in voice_balance.load_table()["voices"] if not key.startswith("vieneu@")}
    assert others == {
        f"{voice['engine']}@{voice_balance.engine_version(voice['engine'])}/{voice['name']}/f100" for voice in ENGINE_VOICES
    }
    assert set(voice_balance.castable_keys()) <= set(voice_balance.load_table()["voices"])
    assert any(voice["castable"] for voice in castable_engine_voices())


def test_a_voice_missing_from_the_table_is_an_error_not_a_one() -> None:
    with pytest.raises(VoiceBalanceError, match="chưa có"):
        voice_balance.constants_for("vieneu", "3.8.3", "Giọng chưa đo", 1.0)
    with pytest.raises(VoiceBalanceError):
        voice_balance.constants_for("vieneu", "9.9.9", "Phạm Tuyên", 1.0)
    with pytest.raises(VoiceBalanceError):
        voice_balance.constants_for("vieneu", "3.8.3", "Phạm Tuyên", 1.37)  # bậc formant chưa đo
    with pytest.raises(VoiceBalanceError):
        voice_balance.preset_pitch_st("Giọng chưa đo")
    with pytest.raises(VoiceBalanceError):
        voice_profile_spec({"name": "Giọng chưa đo", "description": "x"}, 1.0)


def test_a_broken_table_is_refused(monkeypatch) -> None:
    good = voice_balance.load_table()
    for mutate in (
        lambda t: t.update(version=99),
        lambda t: t.update(x=3.0),
        lambda t: t.update(x=0.5, voices={**t["voices"], KEY: {**t["voices"][KEY], "r": 0.6}}),  # tempo 0,3
        lambda t: t["voices"][KEY].update(pitch_st=1.5),
        lambda t: t["voices"][KEY].pop("ref_lufs"),
        lambda t: t["voices"].update({"vieneu@9.9.9/X/f100": dict(t["voices"][KEY])}),
    ):
        table = copy.deepcopy(good)
        mutate(table)
        with pytest.raises(VoiceBalanceError):
            voice_balance._validate(table)


def test_profile_key_comes_from_engine_preset_and_formant() -> None:
    profile = {"engine": "vieneu", "preset_name": "Thanh Bình", "formant_ratio": 0.93}
    assert voice_balance.voice_key_for_profile(profile) == "vieneu@3.8.3/Thanh Bình/f093"
    assert voice_balance.constants_for_profile(profile).pitch_st == -4
    # Hàng thiếu engine/formant (hồ sơ dựng tay) đọc như VieNeu ở bậc gốc.
    assert voice_balance.voice_key_for_profile({"preset_name": "Đức Trí"}) == OTHER_KEY


# --- tốc độ ---------------------------------------------------------------------------


def test_the_measured_table_puts_every_voice_on_one_axis() -> None:
    # Số đo 04-10 (docs/VOICE_BALANCE.md, "Số đo"): r_v = mốc / tốc độ gốc, mốc = trung vị tốc độ gốc của 19 preset phân vai
    # ở f100 -> trung vị r của 19 preset ấy là 1. r theo PRESET (bậc formant đổi tốc độ ±0,5 %), x = 1 (chủ sách chốt).
    table = voice_balance.load_table()
    assert table["x"] == 1.0 and table["L_lufs"] == -25.0
    assert 0.9 <= table["pace_floor_scale"] <= 1.0
    by_preset: dict[str, set[float]] = {}
    for key, record in table["voices"].items():
        by_preset.setdefault(key.split("/")[1], set()).add(record["r"])
    assert all(len(rates) == 1 for rates in by_preset.values()), by_preset
    castable = [preset["name"] for gender in ("male", "female") for preset in casting_presets(gender)]
    assert len(castable) == 19
    middle = sorted(next(iter(by_preset[name])) for name in castable)[len(castable) // 2]
    assert middle == pytest.approx(1.0, abs=0.005)
    # Hệ số tay cũ bị THAY: 4 giọng kể chuyện chủ sách chọn 18-09 đọc chậm hơn mốc nên r > 1,1.
    for name in ("Đức Trí", "Thiền Tâm Đức", "Kim Thanh", "Mỹ Duyên"):
        assert next(iter(by_preset[name])) > 1.1, name


def test_tempo_is_x_times_r(monkeypatch) -> None:
    constants = voice_balance.constants_for_key(OTHER_KEY)
    assert voice_balance.tempo(constants) == pytest.approx(constants.r)
    _with_table(monkeypatch, x=0.85)
    assert voice_balance.tempo(constants) == pytest.approx(0.85 * constants.r)
    # Tempo chậm hơn 0,80 giờ được phép (x ~ 0,85 nhân r ~ 0,89).
    assert SPEED_FACTOR_MIN == 0.70 and SPEED_FACTOR_MAX == 1.50


def test_synthesis_applies_the_table_in_the_documented_order() -> None:
    source = inspect.getsource(tts.TTSCoordinator.synthesize_atomic)
    named = source.index("spoken_row[VOICE_BALANCE_FIELD]")
    # Giọng được đặt tên TRƯỚC ngân sách sinh và trước độ to; pitch -> tempo -> gain.
    assert named < source.index("vieneu_sampling_for_segment(")
    assert named < source.index("segment_duration_policy(")
    # Tempo được TÍNH trước khi sinh (máy tự đọc theo tempo nhận nó ở đó), nhưng ÁP sau cao độ.
    pitch = source.index("apply_pitch_variant(")
    tempo = source.index("voice_balance.tempo(voice_constants)")
    speed = source.index("apply_speed_change(")
    gain = source.index("atomic_write_wav(")
    assert named < tempo < pitch < speed < gain


# --- độ to ----------------------------------------------------------------------------


def test_gain_is_constant_whatever_the_clip_loudness() -> None:
    settings = build_settings()
    quiet, loud = _tone(0.03), _tone(0.20)
    quiet_out, quiet_info = level_segment(quiet, RATE, _segment(), settings)
    loud_out, loud_info = level_segment(loud, RATE, _segment(), settings)
    assert quiet_info["level_gain_db"] == pytest.approx(loud_info["level_gain_db"])
    expected = (
        voice_balance.level_lufs() + 0.0 - voice_balance.constants_for_key(KEY).ref_lufs
    )
    assert quiet_info["level_gain_db"] == pytest.approx(expected)
    assert quiet_info["peak_limited_db"] == 0.0 == loud_info["peak_limited_db"]
    ratio = (np.max(np.abs(loud_out)) / np.max(np.abs(quiet_out))) / (0.20 / 0.03)
    assert ratio == pytest.approx(1.0, rel=1e-3)  # khoảng cách giữa hai câu còn nguyên
    assert normalize_segment_level(quiet, RATE, _segment(), settings) == pytest.approx(quiet_out)


def test_the_voice_trim_adds_in_db(monkeypatch) -> None:
    settings = build_settings()
    base = segment_gain_db(_segment(), settings)
    table = _with_table(monkeypatch)
    table["voices"][KEY]["o_db"] = 1.5
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 1.5)
    table["voices"][KEY]["ref_lufs"] = table["voices"][KEY]["ref_lufs"] - 2.0
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 3.5)
    monkeypatch.undo()
    table2 = _with_table(monkeypatch, L_lufs=voice_balance.level_lufs() + 2.0)
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 2.0)
    assert table2["L_lufs"] == -23.0


def test_offsets_add_on_top_of_the_voice_gain() -> None:
    settings = build_settings()
    audio_cfg = settings["audio"]
    normal = segment_gain_db(_segment(), settings)
    targets = audio_cfg["segment_target_lufs"]
    soft = segment_gain_db(_segment(volume="soft"), settings)
    loud = segment_gain_db(_segment(volume="loud"), settings)
    assert soft - normal == pytest.approx(float(targets["soft"]) - float(targets["normal"]))
    assert loud - normal == pytest.approx(float(targets["loud"]) - float(targets["normal"]))
    assert soft - normal == pytest.approx(-3.0) and loud - normal == pytest.approx(1.2)
    narrator = segment_gain_db(_segment(speaker="NARRATOR"), settings)
    assert narrator - normal == pytest.approx(float(audio_cfg["segment_narrator_offset_db"]))
    angry = segment_gain_db(_segment(emotion="angry", intensity=3), settings)
    assert angry - normal == pytest.approx(audio_io.LOUDNESS_EMOTION_OFFSETS_DB["angry"])
    half = segment_gain_db(_segment(emotion="angry", intensity=1), settings)
    assert half - normal == pytest.approx(audio_io.LOUDNESS_EMOTION_OFFSETS_DB["angry"] / 3.0)
    # volume khác normal thì không cộng cảm xúc (như cũ).
    assert segment_offsets_db(_segment(volume="loud", emotion="angry", intensity=3), settings) == pytest.approx(1.2)


def test_voices_meet_on_one_axis() -> None:
    # Hai giọng có LUFS thô khác nhau (ref_lufs) ra cùng mức sau gain: đó là mục đích của bảng.
    settings = build_settings()
    table = voice_balance.load_table()
    ref_a, ref_b = table["voices"][KEY]["ref_lufs"], table["voices"][OTHER_KEY]["ref_lufs"]
    gain_a = segment_gain_db(_segment(), settings)
    gain_b = segment_gain_db(_segment(**{VOICE_BALANCE_FIELD: OTHER_KEY}), settings)
    assert ref_a + gain_a == pytest.approx(ref_b + gain_b)


def test_the_peak_ceiling_still_holds_and_is_reported() -> None:
    settings = build_settings()
    segment = _segment(emotion="angry", intensity=3)
    desired = segment_gain_db(segment, settings)
    # Trần mặc định -2 dBFS: một bản thô vừa đủ nhỏ thì gain hằng số áp nguyên vẹn.
    out, info = level_segment(_tone(0.2), RATE, segment, settings)
    assert info["peak_limited_db"] == 0.0 and info["level_gain_db"] == pytest.approx(desired)
    # Hạ trần xuống -12 dBFS: đỉnh vượt thì hạ cho vừa, phần hạ thêm được ghi lại.
    tight = copy.deepcopy(settings)
    tight["audio"]["segment_peak_dbfs"] = -12.0
    out, info = level_segment(_tone(0.9), RATE, segment, tight)
    assert info["peak_limited_db"] > 0
    assert 20 * np.log10(float(np.max(np.abs(out)))) == pytest.approx(-12.0, abs=0.01)
    assert info["level_gain_db"] == pytest.approx(desired - info["peak_limited_db"])


def test_a_segment_without_a_voice_cannot_be_levelled() -> None:
    settings = build_settings()
    segment = _segment()
    segment.pop(VOICE_BALANCE_FIELD)
    with pytest.raises(VoiceBalanceError, match="voice_balance_key"):
        level_segment(_tone(0.1), RATE, segment, settings)
    with pytest.raises(VoiceBalanceError, match="chưa có"):
        level_segment(_tone(0.1), RATE, _segment(**{VOICE_BALANCE_FIELD: "vieneu@3.8.3/Giọng chưa đo/f100"}), settings)


def test_locked_rms_books_keep_their_per_sentence_policy() -> None:
    settings = build_settings()
    legacy = copy.deepcopy(settings)
    legacy["audio"].pop("segment_target_lufs")
    segment = _segment()
    segment.pop(VOICE_BALANCE_FIELD)  # sách cũ không cần giọng
    quiet, _ = level_segment(_tone(0.03), RATE, segment, legacy)
    loud, _ = level_segment(_tone(0.20), RATE, segment, legacy)
    assert float(np.max(np.abs(quiet))) == pytest.approx(float(np.max(np.abs(loud))), rel=0.01)


def test_writing_a_wav_records_the_gain_and_a_merge_does_not_apply_it_twice(tmp_path: Path) -> None:
    settings = build_settings(overrides={"tts": {"min_seconds_per_100_chars": 0.2}})
    rate = int(settings["tts"]["sample_rate"])
    t = np.arange(rate * 2, dtype=np.float32) / rate
    raw = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    text = "Một câu kiểm tra độ to."
    segment = _segment(pace="normal")
    one = tmp_path / "one.wav"
    _, metrics = atomic_write_wav(one, raw, rate, text, settings, segment)
    assert metrics["level_gain_db"] == pytest.approx(segment_gain_db(segment, settings))
    assert metrics["peak_limited_db"] == 0.0
    merged = tmp_path / "merged.wav"
    _, merged_metrics = merge_wav_parts_atomic([one], merged, text, settings, segment=segment)
    assert merged_metrics["level_gain_db"] == 0.0
    import soundfile as sf

    first, _ = sf.read(one, dtype="float32")
    again, _ = sf.read(merged, dtype="float32")
    assert float(np.max(np.abs(again))) == pytest.approx(float(np.max(np.abs(first))), rel=0.01)


# --- cổng nhịp ------------------------------------------------------------------------


def test_the_pace_floor_follows_the_shared_knob_and_x(monkeypatch) -> None:
    base = voice_balance.pace_gate_scale()
    assert base == pytest.approx(voice_balance.pace_floor_scale() * voice_balance.x())
    _with_table(monkeypatch, x=0.9)
    assert voice_balance.pace_gate_scale() == pytest.approx(voice_balance.pace_floor_scale() * 0.9)
    settings = build_settings("high_quality")
    t = np.arange(int(RATE * 3.0)) / RATE
    audio = (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    text = "Người kể chuyện đọc thật chậm rãi từng chữ một trong đêm dài"
    _, metrics = audio_io.validate_audio_array(
        audio, text, settings, RATE, {"pace": "normal", "kind": "narration"}
    )
    assert metrics["pace_scale"] == pytest.approx(voice_balance.pace_floor_scale() * 0.9)


def test_at_x_085_the_finished_floor_drops_and_the_raw_floor_does_not(monkeypatch) -> None:
    # pace_floor_scale là giá trị ở x = 1 (đo: 0,996). Núm x = 0,85 (nhịp 4 giọng kể chuyện chủ sách chọn 18-09): sàn của bản
    # đã áp tempo hạ theo x, còn sàn của bản THÔ (trước tempo) giữ nguyên vì x triệt tiêu - giọng đọc chậm hơn là do tempo,
    # không phải do model đọc chậm.
    constants = voice_balance.constants_for_key(KEY)
    raw_at_one = voice_balance.raw_pace_floor_scale(constants)
    _with_table(monkeypatch, x=0.85)
    assert voice_balance.pace_gate_scale() == pytest.approx(voice_balance.pace_floor_scale() * 0.85)
    assert voice_balance.raw_pace_floor_scale(voice_balance.constants_for_key(KEY)) == pytest.approx(raw_at_one)
    assert voice_balance.tempo(voice_balance.constants_for_key(KEY)) == pytest.approx(0.85 * constants.r)


# --- màu giọng ------------------------------------------------------------------------


def test_register_keeps_its_old_values() -> None:
    expected = {"Thanh Bình": -4, "Adam bựa": -2, "Quốc Tuấn": -2}
    # Cao độ đọc từ bảng: chỉ giọng có số (phân vai ∪ người kể) mới có; giọng Tin tức không chọn được nên không có.
    for name in voice_balance.balanced_preset_names():
        assert base_pitch_for_preset(name) == expected.get(name, 0), name
        assert voice_balance.preset_pitch_st(name) == expected.get(name, 0), name


def test_casting_takes_the_register_from_the_table_and_adds_age() -> None:
    spec = voice_profile_spec(preset_by_name("Thanh Bình"), 1.0, age_pitch=3)
    assert spec["pitch_semitones"] == -4 + 3
    assert spec["voice_key"] == "preset_thanh_binh_f100_p-01"
    plain = voice_profile_spec(preset_by_name("Phạm Tuyên"), 0.93)
    assert plain["pitch_semitones"] == 0 and plain["voice_key"].endswith("_f093_p+00")


# --- script nhập số -------------------------------------------------------------------


def _import_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "voice_balance_import.py"
    spec = importlib.util.spec_from_file_location("voice_balance_import", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_import_script_round_trips_the_table_byte_for_byte() -> None:
    script = _import_script()
    raw = voice_balance.TABLE_PATH.read_bytes()
    assert b"\r" not in raw
    assert script.render(json.loads(raw.decode("utf-8"))) == raw


def test_the_import_script_turns_measurements_into_constants() -> None:
    script = _import_script()
    table = json.loads(voice_balance.TABLE_PATH.read_text(encoding="utf-8"))
    rates = {
        "median_syll_per_s": 4.56,
        "voices": {OTHER_KEY: {"syll_per_s": 4.0}, KEY: {"r": 1.0}},
    }
    gains = {"voices": {OTHER_KEY: {"lufs": -21.5, "o_db": 0.4}}}
    touched = script.merge(table, rates, gains)
    assert set(touched) == {OTHER_KEY, KEY}
    assert table["voices"][OTHER_KEY]["r"] == pytest.approx(1.14)
    assert table["voices"][OTHER_KEY]["ref_lufs"] == -21.5
    assert table["voices"][OTHER_KEY]["o_db"] == 0.4
    assert table["voices"][OTHER_KEY]["pitch_st"] == 0  # màu giọng không bao giờ bị đổi
    voice_balance._validate(json.loads(script.render(table).decode("utf-8")))
    with pytest.raises(SystemExit):
        script.merge(table, {"voices": {"vieneu@3.8.3/Giọng mới/f100": {"r": 1.0}}}, {"voices": {}})


def test_world_leaves_a_take_too_short_to_hold_speech_alone() -> None:
    # pyworld.harvest trên 2 mẫu làm hỏng heap native và giết cả tiến trình (đo 04-10, test_voice_profile_lock sập cả lượt
    # pytest khi giọng có r khác 1). Bản ngắn hơn WORLD_MIN_SECONDS đi qua nguyên vẹn; cổng "audio too short" loại nó sau.
    tiny = np.asarray([0.1, -0.1], dtype=np.float32)
    assert np.array_equal(tts.apply_speed_change(tiny, RATE, 0.9), tiny)
    assert np.array_equal(tts.apply_pitch_variant(tiny, RATE, -2), tiny)
