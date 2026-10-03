"""Bộ phân tích nhạc trên điện thoại (MusicStudentSetup.kt, MusicStudent.kt) chép cứng vài hằng số của music_student.py: gói model
ghim (REPO_ID, REVISION, SHA-256 + cỡ từng file của đường onnx) và bảng hiệu chỉnh. Đổi bên Python mà quên bên Kotlin thì điện thoại
tải gói khác / ra số khác máy tính - test này bắt điều đó. (Số học thì MusicStudentTest.kt so với tests/fixtures/music_student.)"""
from __future__ import annotations

import json
import re
from pathlib import Path

from abook.webui import music_student

ANDROID = Path(__file__).resolve().parents[1] / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player"
FIXTURES = Path(__file__).parent / "fixtures" / "music_student"


def _kotlin(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def test_the_phone_downloads_the_same_pinned_package_as_the_computer():
    source = _kotlin("MusicStudentSetup.kt")
    assert f'REPO_ID = "{music_student.REPO_ID}"' in source
    assert f'REVISION = "{music_student.REVISION}"' in source
    listed = re.findall(r'Part\("([^"]+)", "([0-9a-f]{64})", ([\d_]+)\)', source)
    assert {name for name, *_ in listed} == set(music_student.PACKAGE_FILES["onnx"])
    for name, sha256, size in listed:
        assert music_student.PACKAGE_HASHES[name] == (sha256, int(size.replace("_", ""))), name


def test_the_phone_uses_the_onnx_calibration_of_the_computer():
    source = _kotlin("MusicStudent.kt")
    for axis, (shift, slope, variance) in music_student.CALIBRATION["onnx"].items():
        match = re.search(rf'"{axis}" to Triple\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)', source)
        assert match, axis
        assert tuple(float(value) for value in match.groups()) == (shift, slope, variance), axis
    assert f"CONFIDENCE = {music_student.CONFIDENCE}" in source


def test_the_phone_families_are_the_apps_families():
    from abook.webui import music_plan

    match = re.search(r"val FAMILIES = setOf\(([^)]*)\)", _kotlin("MusicStudent.kt"))
    assert match and set(re.findall(r'"(\w+)"', match.group(1))) == set(music_plan.FAMILIES)


def test_the_shared_goldens_are_what_the_current_python_student_gives():
    """Số vàng không được cũ: head.result khớp công thức hiện tại của _Head.predict trên chính vector nhúng đã lưu."""
    import numpy as np

    golden = json.loads((FIXTURES / "golden.json").read_text(encoding="utf-8"))

    class Head(music_student._Head):
        backend = "onnx"

    head = Head(FIXTURES / "student_head_A.npz")
    for name, entry in golden["head"].items():
        again = head.predict(np.array(entry["embedding"], dtype=np.float64))
        assert again == entry["result"], name


def test_the_phone_downloads_the_onnx_runtime_that_the_vendored_java_api_matches():
    """APK không mang ONNX Runtime: phần Java chép nguyên vào app/src/main/java/ai/onnxruntime, hai file .so của đúng ABI tải cùng "Gói nhạc".
    Hằng số của OrtRuntime.kt phải khớp script sinh file đặt trên máy chủ (scripts/prepare_ort_runtime.py) - lệch là tải về file không ai ghim."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("prepare_ort_runtime", Path(__file__).resolve().parents[1] / "scripts" / "prepare_ort_runtime.py")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    source = _kotlin("OrtRuntime.kt")
    assert f'VERSION = "{prepare.VERSION}"' in source
    gradle = (ANDROID.parents[5] / "build.gradle").read_text(encoding="utf-8")
    assert 'implementation "com.microsoft.onnxruntime' not in gradle, "APK không được mang ONNX Runtime"
    for abi in prepare.ABIS:
        assert f'"{abi}" to listOf(' in source
    rows = re.findall(r'part\("([\w-]+)", (CORE|JNI), "([0-9a-f]{64})", ([\d_]+), "([0-9a-f]{64})", ([\d_]+)\)', source)
    assert len(rows) == 2 * len(prepare.ABIS) and {abi for abi, *_ in rows} == set(prepare.ABIS)
    java = ANDROID.parents[2] / "ai" / "onnxruntime" / "OnnxRuntime.java"
    text = java.read_text(encoding="utf-8")
    loader = text.split("private static void load")[1].split("// 1)")[0]
    assert prepare.VERSION in text and "onnxruntime.native.path" in text
    assert "System.loadLibrary" not in loader and "System.load(" in loader, "chỉ nạp bằng đường tuyệt đối từ thư mục đã tải"
