"""Giọng VieNeu trên điện thoại (mobile/android/.../vieneu/) chép cứng vài thứ của máy tính: ghim từng file của mô-đun (vieneu_module.py), độ to
từng giọng (loudness.py), các hằng số chia khúc / tự đo (vieneu.py, vieneu_engine.py). Đổi bên Python mà quên bên Kotlin thì điện thoại tải file
khác / đọc khác máy tính - test này bắt điều đó. Số học thì các bài thử JVM so với tests/fixtures/vieneu/android; test cuối kiểm các file ấy
không cũ so với code hiện tại (scripts/vieneu_android_fixtures.py viết lại)."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from abook.readaloud import loudness, vieneu, vieneu_engine
from abook.webui import vieneu_module, voice_module

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
FIXTURES = Path(__file__).parent / "fixtures" / "vieneu" / "android"


def _kotlin(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_phone_downloads_the_same_pinned_model_files_as_the_computer():
    source = _kotlin("vieneu/VieneuModule.kt")
    bases = dict(re.findall(r'private const val (\w+_BASE) = "([^"]+)"', source))
    assert 'private const val NANO_INT8_BASE = VoiceModule.APP_MODELS + "vieneu-nano-int8/"' in source
    bases["NANO_INT8_BASE"] = voice_module.APP_MODELS + "vieneu-nano-int8/"
    # Nano has one tier on both platforms: no fast estimator, files, choice or speed family on the phone
    assert not hasattr(vieneu_module, "NANO_FAST") and not hasattr(vieneu_module, "FAST_CHOICE")
    for fast_name in ("NANO_FAST", "FAST_CHOICE", "nano_fast", "VoiceSpeed.Family"):
        assert fast_name not in source, fast_name
    for tier, files in (("turbo", vieneu_module.TURBO_FILES), ("nano", vieneu_module.NANO_FILES)):
        rows = re.findall(rf'file\("{tier}", (\w+), "([^"]+)", "([0-9a-f]{{64}})", ([\d_]+), ', source)
        assert {name for _, name, *_ in rows} == {item.name for item in files}, tier
        for base, name, sha256, size in rows:
            item = next(item for item in files if item.name == name)
            assert (bases[base] + name, sha256, int(size.replace("_", ""))) == (item.url, item.sha256, item.size), name


def test_the_phone_takes_the_dictionary_and_the_voices_from_the_computers_pinned_wheels():
    source = _kotlin("vieneu/VieneuModule.kt")
    dictionary = re.search(r'val DICTIONARY = Part\("g2p/sea_g2p.bin", "([0-9a-f]{64})", ([\d_]+),\s*"([^"]+)",\s*Packed\("([0-9a-f]{64})", ([\d_]+)', source)
    assert dictionary and (dictionary.group(3), dictionary.group(4), int(dictionary.group(5).replace("_", ""))) == \
        (vieneu_module.G2P.url, vieneu_module.G2P.sha256, vieneu_module.G2P.size)
    voices = re.search(r'val VOICES = Part\("voices/[^"]+", "([0-9a-f]{64})", ([\d_]+),\s*"([^"]+)"', source)
    assert voices and (voices.group(3), voices.group(1), int(voices.group(2).replace("_", ""))) == \
        (vieneu_module.VOICES.url, vieneu_module.VOICES.sha256, vieneu_module.VOICES.size)
    members = dict(re.findall(r'"(turbo|nano)" to "(vieneu/assets/voices_v3_\w+\.json)"', source))
    assert {members[tier] for tier in ("turbo", "nano")} == set(vieneu_module.VOICE_MEMBERS)
    sea = pytest.importorskip("sea_g2p")
    import hashlib

    data = (Path(sea.__file__).parent / "sea_g2p.bin").read_bytes()
    assert (hashlib.sha256(data).hexdigest(), len(data)) == (dictionary.group(1), int(dictionary.group(2).replace("_", "")))


def test_the_jni_library_is_pinned_for_every_abi_the_build_script_makes():
    prepare = _script("prepare_sea_g2p_android")
    source = _kotlin("vieneu/VieneuModule.kt")
    rows = re.findall(r'"([\w-]+)" to g2pLib\("([\w-]+)", "([0-9a-f]{64})", ([\d_]+), "([0-9a-f]{64})", ([\d_]+)\)', source)
    assert {abi for abi, *_ in rows} == set(prepare.ABIS)
    assert all(abi == again for abi, again, *_ in rows)
    assert f"sea-g2p/{prepare.VERSION}/" in source
    # the JNI symbols of the Rust wrapper are the Kotlin externs
    rust = (ROOT / "mobile" / "sea_g2p_jni" / "src" / "lib.rs").read_text(encoding="utf-8")
    exported = set(re.findall(r"Java_vn_abook_player_vieneu_SeaG2pNative_(\w+)", rust))
    declared = set(re.findall(r"@JvmStatic external fun (\w+)", _kotlin("vieneu/SeaG2p.kt")))
    assert exported == declared and declared


def test_the_phone_plays_each_voice_at_the_computers_loudness():
    source = _kotlin("readaloud/VoiceGain.kt")
    table = {voice: float(level) for voice, level in re.findall(r'"([^"]+)" to (-?[\d.]+),', source)}
    assert table == loudness.MEASURED_LUFS
    assert f"const val TARGET_LUFS = {loudness.TARGET_LUFS}" in source


def test_the_phone_lifts_quiet_clips_with_the_computers_constants():
    source = _kotlin("readaloud/ClipLift.kt")
    for name, value in (("DEADBAND_DB", loudness.LIFT_DEADBAND_DB), ("MAX_DB", loudness.LIFT_MAX_DB), ("CEILING_DBTP", loudness.LIFT_CEILING_DBTP),
                        ("SAFETY_DB", loudness.LIFT_SAFETY_DB), ("PAD_SECONDS", loudness.LIFT_PAD_SECONDS), ("MIN_SECONDS", loudness.LIFT_MIN_SECONDS),
                        ("MIN_LUFS", loudness.LIFT_MIN_LUFS)):
        assert re.search(rf"const val {name} = {re.escape(str(value))}$", source, re.M), name
    assert f'const val TAG = "{loudness.LIFT_TAG}"' in source and "val PREFIXES = listOf(" + ", ".join(f'"{prefix}"' for prefix in loudness.LIFT_PREFIXES) + ")" in source


def test_the_phone_cuts_and_measures_like_the_computer():
    speaker = _kotlin("vieneu/VieneuSpeaker.kt")
    assert f'val MAX_CHARS = mapOf("turbo" to {vieneu.MAX_CHARS["turbo"]}, "nano" to {vieneu.MAX_CHARS["nano"]})' in speaker
    assert f"const val MIN_UNIT_CHARS = {vieneu.MIN_UNIT_CHARS}" in _kotlin("vieneu/VieneuUnits.kt")
    audio = _kotlin("vieneu/VieneuAudio.kt")
    for name, seconds in vieneu_engine.GAP_SECONDS.items():
        assert f'"{name}" to {seconds:.2f}' in audio
    voices = _kotlin("vieneu/VieneuVoices.kt")
    assert f'const val BENCH_TEXT = "{vieneu.BENCH_TEXT}"' in voices
    assert f"const val SLOW_RTF = {vieneu_module.SLOW_RTF}" in _kotlin("vieneu/VoiceModule.kt")
    assert f"MAX_NEW_FRAMES = {vieneu_engine.MAX_NEW_FRAMES}" in speaker
    assert f"const val STEPS = {vieneu_engine.NANO_STEPS}" in _kotlin("vieneu/VieneuNano.kt")
    assert f"const val CFG_ENDS = {str(vieneu_engine.NANO_CFG_ENDS).lower()}" in _kotlin("vieneu/VieneuNano.kt")


def test_the_shared_fixtures_are_what_the_current_desktop_code_gives():
    pytest.importorskip("sea_g2p")
    fixtures = _script("vieneu_android_fixtures")
    text = fixtures.text_fixture()
    assert text == json.loads((FIXTURES / "text.json").read_text(encoding="utf-8"))
    assert fixtures.rng_fixture() == json.loads((FIXTURES / "rng.json").read_text(encoding="utf-8"))
    assert fixtures.audio_fixture() == json.loads((FIXTURES / "audio.json").read_text(encoding="utf-8"))
    bpe = vieneu_engine.ByteBPE(FIXTURES / "turbo_tokenizer.json")
    for case in json.loads((FIXTURES / "tokens.json").read_text(encoding="utf-8"))["cases"]:
        assert bpe.encode(case["text"]) == case["ids"], case["text"]
    assert text["sentences"] >= 200
