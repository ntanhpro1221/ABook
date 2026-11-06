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
from abook.audio_io import VOICE_BALANCE_FIELD, atomic_write_wav, level_segment, merge_wav_parts_atomic, normalize_segment_level, segment_gain_db
from abook.character_registry import voice_profile_spec
from abook.config import build_settings
from abook.runtime_contract import CRITICAL_RUNTIME_DISTRIBUTIONS
from abook.voice_balance import VoiceBalanceError
from abook.voice_catalog import SPEED_FACTOR_MAX, SPEED_FACTOR_MIN, STYLE_NEWS, VIENEU_PRESETS, ENGINE_VOICES, castable_engine_voices, casting_presets, narrator_presets, preset_by_name, preset_eligible

RATE = 48_000
KEY = "vieneu@3.8.3/Phạm Tuyên"
OTHER_KEY = "vieneu@3.8.3/Đức Trí"


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
            voice_balance.constants_for("vieneu", version, preset["name"])
    for name in voice_balance.balanced_preset_names():
        voice_balance.constants_for("vieneu", version, name)


def test_the_table_holds_no_stray_voices() -> None:
    # Ngoài các khoá phân vai / chọn tay được: giọng máy khác đã đo mà chủ sách chưa chọn (vẫn trong danh mục, castable=False).
    measured = {f"{voice['engine']}@{voice_balance.engine_version(voice['engine'])}/{voice['name']}" for voice in ENGINE_VOICES}
    expected = set(voice_balance.castable_keys()) | measured
    assert set(voice_balance.load_table()["voices"]) == expected


def test_the_table_covers_exactly_the_castable_and_narrator_voices() -> None:
    # Phân vai được ∪ người kể chọn được: giọng miền Trung kể chuyện được; tin tức chỉ mở theo vai đã xếp hạng.
    names = set(voice_balance.balanced_preset_names())
    assert {"Quang Sơn", "Ngọc Trân"} <= names
    news = {preset["name"] for preset in VIENEU_PRESETS if preset["style"] == STYLE_NEWS}
    assert news and not news & names
    assert all(not preset_eligible(preset_by_name(name), "narrator") for name in news - names)
    in_table = {key.split("/")[1] for key in voice_balance.load_table()["voices"] if key.startswith("vieneu@")}
    assert in_table == names
    # Máy đọc khác: đúng các giọng trong danh mục (chọn tay được hay chưa), mỗi giọng một bậc gốc.
    others = {key for key in voice_balance.load_table()["voices"] if not key.startswith("vieneu@")}
    assert others == {
        f"{voice['engine']}@{voice_balance.engine_version(voice['engine'])}/{voice['name']}" for voice in ENGINE_VOICES
    }
    assert set(voice_balance.castable_keys()) <= set(voice_balance.load_table()["voices"])
    assert any(voice["castable"] for voice in castable_engine_voices())


def test_a_broken_table_is_refused(monkeypatch) -> None:
    good = voice_balance.load_table()
    for mutate in (
        lambda t: t.update(version=99),
        lambda t: t.update(x=3.0),
        lambda t: t.update(x=0.5, voices={**t["voices"], KEY: {**t["voices"][KEY], "r": 0.6}}),  # tempo 0,3
        lambda t: t["voices"][KEY].update(unknown=1.5),
        lambda t: t["voices"][KEY].pop("ref_lufs"),
        lambda t: t["voices"].update({"vieneu@9.9.9/X": dict(t["voices"][KEY])}),
    ):
        table = copy.deepcopy(good)
        mutate(table)
        with pytest.raises(VoiceBalanceError):
            voice_balance._validate(table)


# --- tốc độ ---------------------------------------------------------------------------


def test_tempo_is_x_times_r(monkeypatch) -> None:
    constants = voice_balance.constants_for_key(OTHER_KEY)
    assert voice_balance.tempo(constants) == pytest.approx(constants.r)
    _with_table(monkeypatch, x=0.85)
    assert voice_balance.tempo(constants) == pytest.approx(0.85 * constants.r)
    # Tempo chậm hơn 0,80 giờ được phép (x ~ 0,85 nhân r ~ 0,89).
    assert SPEED_FACTOR_MIN == 0.70 and SPEED_FACTOR_MAX == 1.50


# --- độ to ----------------------------------------------------------------------------


def test_gain_is_constant_whatever_the_clip_loudness() -> None:
    settings = build_settings()
    quiet, loud = _tone(0.03), _tone(0.20)
    quiet_out, quiet_info = level_segment(quiet, RATE, _segment(), settings)
    loud_out, loud_info = level_segment(loud, RATE, _segment(), settings)
    assert quiet_info["level_gain_db"] == pytest.approx(loud_info["level_gain_db"])
    expected = (
        voice_balance.level_lufs()
        + voice_balance.constants_for_key(KEY).o_db
        - voice_balance.constants_for_key(KEY).ref_lufs
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
    table["voices"][KEY]["o_db"] += 1.5
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 1.5)
    table["voices"][KEY]["ref_lufs"] = table["voices"][KEY]["ref_lufs"] - 2.0
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 3.5)
    monkeypatch.undo()
    table2 = _with_table(monkeypatch, L_lufs=voice_balance.level_lufs() + 2.0)
    assert segment_gain_db(_segment(), settings) == pytest.approx(base + 2.0)
    assert table2["L_lufs"] == -23.0


def test_reference_levels_include_perceptual_voice_offsets() -> None:
    # Mốc LUFS gặp nhau trước o_db; độ bù cảm nhận riêng không cần bằng nhau theo LUFS.
    settings = build_settings()
    table = voice_balance.load_table()
    ref_a, ref_b = table["voices"][KEY]["ref_lufs"], table["voices"][OTHER_KEY]["ref_lufs"]
    gain_a = segment_gain_db(_segment(), settings)
    gain_b = segment_gain_db(_segment(**{VOICE_BALANCE_FIELD: OTHER_KEY}), settings)
    assert ref_a + gain_a == pytest.approx(table["L_lufs"] + table["voices"][KEY]["o_db"])
    assert ref_b + gain_b == pytest.approx(table["L_lufs"] + table["voices"][OTHER_KEY]["o_db"])


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
        level_segment(_tone(0.1), RATE, _segment(**{VOICE_BALANCE_FIELD: "vieneu@3.8.3/Giọng chưa đo"}), settings)


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
    from tests.audio_fixtures import quiet_edges
    audio = quiet_edges(audio, RATE)
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
    voice_balance._validate(json.loads(script.render(table).decode("utf-8")))
    with pytest.raises(SystemExit):
        script.merge(table, {"voices": {"vieneu@3.8.3/Giọng mới": {"r": 1.0}}}, {"voices": {}})
