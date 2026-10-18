"""Giọng Supertonic trên điện thoại (mobile/android/.../readaloud/SupertonicTts.kt, SupertonicModule.kt) chép cứng vài thứ của máy tính: ghim
từng file model (supertonic_module.py), các hằng số đọc (supertonic.py), byte bộ đệm mỗi giây (prepare.py). Đổi bên Python mà quên bên Kotlin thì
điện thoại tải file khác / đọc khác máy tính - test này bắt điều đó. Phần tính toán thì bài thử JVM (SupertonicParityTest) và bài thử trên máy
Android (SupertonicBenchTest#parity) so với tests/fixtures/readaloud/supertonic/supertonic.json; test cuối kiểm file ấy không cũ so với code
hiện tại (scripts/supertonic_android_fixtures.py viết lại)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path

import pytest

from abook.readaloud import prepare, supertonic
from abook.webui import supertonic_module, voice_module

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
FIXTURE = Path(__file__).parent / "fixtures" / "readaloud" / "supertonic" / "supertonic.json"


def _kotlin(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_phone_downloads_the_same_pinned_model_files_as_the_computer():
    source = _kotlin("readaloud/SupertonicModule.kt")
    base = re.search(r'private const val BASE = "([^"]+)"', source).group(1)
    assert base == f"https://huggingface.co/{supertonic_module.SOURCE_REPO}/resolve/{supertonic_module.SOURCE_REVISION}/"
    rows = re.findall(r'file\("([^"]+)", "([0-9a-f]{64})", ([\d_]+)\)', source)
    # the app's own files (int8 vector estimators): appFile(path on the phone, path in APP_MODELS, sha256, size, label)
    app = re.findall(r'appFile\(([^,]+), "([^"]+)", "([0-9a-f]{64})", ([\d_]+), ', source)
    assert f'const val APP_MODELS = "{voice_module.APP_MODELS}"' in _kotlin("vieneu/VoiceModule.kt")
    pinned = {(base + name, sha256, int(size.replace("_", ""))) for name, sha256, size in rows} | \
        {(voice_module.APP_MODELS + remote, sha256, int(size.replace("_", ""))) for _, remote, sha256, size in app}
    assert pinned == {(item.url, item.sha256, item.size) for item in supertonic_module.FILES + supertonic_module.FAST_FILES}
    # where the phone keeps them = where the desktop's engine reads them (tier pairs of supertonic.py)
    paths = {remote: path.strip('"').replace("$MODEL/", "model/") for path, remote, *_ in app}
    assert paths["supertonic3-int8/top30/vector_estimator.onnx"] == supertonic.QUALITY[0]
    assert re.search(r'const val FAST_ESTIMATOR = "([^"]+)"', _kotlin("readaloud/SupertonicTts.kt")).group(1) == supertonic.FAST[0]
    assert "appFile(SupertonicText.FAST_ESTIMATOR, \"supertonic3-int8/fast/vector_estimator.onnx\"" in source


def test_the_phone_reads_with_the_computers_settings():
    text = _kotlin("readaloud/SupertonicTts.kt")
    for name in ("STEPS", "SPEED", "SHORT_SPEED", "SHORT_SYLLABLES", "LONG_SYLLABLES", "MAX_CHARS", "GAIN_DB"):
        assert f"const val {name} = {getattr(supertonic, name)}" in text, name
    assert f"const val FAST_STEPS = {supertonic.FAST[1]}" in text
    assert f'const val FAST_CHOICE = "{supertonic_module.FAST_CHOICE}"' in _kotlin("readaloud/SupertonicModule.kt")
    assert f'const val LANGUAGE = "{supertonic.LANGUAGE}"' in text
    assert f'const val PREFIX = "{supertonic.PREFIX}"' in text
    assert f'const val BENCH_TEXT = "{supertonic.BENCH_TEXT}"' in text
    names = re.search(r"val NAMES = listOf\(([^)]*)\)", text).group(1)
    assert tuple(re.findall(r'"(\w+)"', names)) == supertonic.NAMES
    assert tuple(re.findall(r'"(\w+)"', re.search(r"val ONNX = listOf\(([^)]*)\)", text).group(1))) == supertonic.ONNX
    assert f'"supertonic:") -> {prepare.BYTES_PER_SECOND[supertonic.PREFIX + ":"]:_}' in _kotlin("readaloud/PreparePlan.kt")
    assert f"const val SLOW_RTF = {supertonic_module.SLOW_RTF}" in _kotlin("vieneu/VoiceModule.kt")


def test_the_shared_fixture_is_what_the_current_desktop_code_gives():
    pytest.importorskip("sea_g2p")
    fixtures = _script("supertonic_android_fixtures")
    stored = json.loads(FIXTURE.read_text(encoding="utf-8"))
    text = fixtures.text_fixture()
    assert {key: stored[key] for key in text} == text
    model = os.environ.get("ABOOK_SUPERTONIC_MODEL")
    if model and Path(model).is_dir():  # the parts that need the model files (ids, voice styles); the audio is the phone test's to compare
        fresh = fixtures.model_fixture(Path(model), text)
        for key in ("indexer", "ids", "styles"):
            assert stored[key] == fresh[key], key
