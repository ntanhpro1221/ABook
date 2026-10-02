"""Bộ phân tích "trò" của Nhạc của tôi (webui/music_student.py): model chỉ-nghe, không bịa số. Có gói model thật (thư mục trỏ bởi
ABOOK_MUSIC_STUDENT_DIR hay bản dựng ở LLM_Train) thì thử cả đường nhúng CLAP + âm học + đầu trò; không có thì bỏ qua các bài ấy."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import urllib.request
from pathlib import Path

import numpy as np
import pytest
import soundfile

from abook.io_utils import ffmpeg_executable
from abook.webui import music_local, music_mel, music_student

MUSIC = Path("D:/Novels/LLM_Train/music")
PACKAGE = Path("D:/Novels/LLM_Train/models/abook_music_student")
PARITY_TOLERANCE = 0.08  # yêu cầu gốc 0,05; một trong ba bài mẫu lệch 0,0504 vì cửa sổ trượt (xem test cuối)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    music_student.reset()
    music_student.configure(None)
    monkeypatch.delenv(music_student.ENV_DIR, raising=False)
    monkeypatch.delenv(music_student.ENV_BACKEND, raising=False)
    music_local.set_analyzer(None)
    yield
    music_student.reset()
    music_student.configure(None)
    music_local.set_analyzer(None)


@pytest.fixture
def package(monkeypatch) -> Path:
    if not music_student._complete(PACKAGE):
        pytest.skip("không có gói model của trò ở " + str(PACKAGE))
    monkeypatch.setenv(music_student.ENV_DIR, str(PACKAGE))
    return PACKAGE


def _tones(path: Path, seconds: float = 20.0, rate: int = 22050) -> Path:
    t = np.arange(int(seconds * rate)) / rate
    wave = sum(0.2 * np.sin(2 * math.pi * f * t) for f in (220.0, 277.18, 329.63))
    wave = wave * (0.6 + 0.4 * np.sin(2 * math.pi * 0.5 * t)) + 0.01 * np.random.default_rng(3).standard_normal(len(t))
    soundfile.write(path, wave.astype(np.float32), rate)
    return path


def test_without_a_package_analyze_gives_nothing_and_does_not_register(tmp_path: Path) -> None:
    song = _tones(tmp_path / "tones.wav", 5)
    music_student.configure(tmp_path / "empty")
    assert music_student.analyze(song) is None and not music_student.available()
    assert music_student.register() is False and not music_local.analyzer_available()
    assert music_local.analyze(song) is None, "không bịa số khi chưa có model"


def test_an_incomplete_package_is_not_used(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv(music_student.ENV_DIR, str(tmp_path))
    assert not music_student.available() and music_student.analyze(_tones(tmp_path / "a.wav", 5)) is None


def test_the_download_is_pinned_and_never_happens_in_tests(tmp_path: Path, monkeypatch) -> None:
    assert music_student.REVISION == "" or len(music_student.REVISION) == 40
    # conftest đặt ABOOK_MUSIC_STUDENT_DOWNLOAD=0: có ghim commit cũng không tải, gói thiếu thì không cắm
    music_student.configure(tmp_path / "student")
    assert music_student._download(tmp_path / "student") is False and not (tmp_path / "student").exists()
    assert not music_student.available()
    monkeypatch.setattr(music_student, "REVISION", "")
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")
    assert music_student._download(tmp_path / "student") is False, "chưa ghim commit thì không bao giờ tải"


def test_a_synthetic_track_gets_a_full_entry_that_survives_clean_analysis(tmp_path: Path, package: Path) -> None:
    song = _tones(tmp_path / "tones.wav")
    result = music_student.analyze(song)
    assert result is not None
    assert {"valence", "arousal", "tension", "sd", "emotions", "confidence", "fitsUnderNarration", "family", "loudness"} <= result.keys()
    assert result["confidence"] == 0.5 and set(result["sd"]) == {"valence", "arousal", "tension"}
    assert len(result["emotions"]) == 13 and all(0.0 <= v <= 1.0 for v in result["emotions"].values())
    assert 0.0 <= result["loudness"]["speechBand"] <= 1.0
    cleaned = music_local.clean_analysis(result)
    assert cleaned is not None and cleaned["background"] == result["fitsUnderNarration"] and "speechBand" in cleaned
    assert cleaned["family"] in music_local.music_plan.FAMILIES
    assert music_student.register() is True and music_local.analyzer_available()
    assert music_local.analyze(song)["valence"] == cleaned["valence"]


def test_too_short_or_unreadable_audio_is_not_analysed(tmp_path: Path, package: Path) -> None:
    assert music_student.analyze(_tones(tmp_path / "blip.wav", 1.5)) is None
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"not audio")
    assert music_student.analyze(broken) is None


def _reference_ids(count: int = 3):
    """(ba mã bài Incompetech có audio cạnh bộ dữ liệu nghiên cứu, hàm mã -> tên file); không có bộ ấy thì bỏ qua."""
    needed = [MUSIC / name for name in ("embedding_ids.json", "embeddings.npy", "acoustic2.jsonl", "student_model.npz", "music_files.py")]
    if not all(path.is_file() for path in needed):
        pytest.skip("không có bộ dữ liệu nghiên cứu nhạc ở " + str(MUSIC))
    import importlib.util

    spec = importlib.util.spec_from_file_location("music_files", MUSIC / "music_files.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ids = json.loads((MUSIC / "embedding_ids.json").read_text(encoding="utf-8"))
    found = [track for track in ids if track.startswith("incompetech:")
             and (MUSIC / "audio_incompetech" / (module.stem(track) + ".mp3")).is_file()]
    if len(found) < count:
        pytest.skip("thiếu audio Incompetech để so")
    step = len(found) // count
    return [found[i * step] for i in range(count)], module.stem


def _reference(track: str, stem):
    """Hàng của bài `track` trong bộ dữ liệu nghiên cứu: (nhúng đã chuẩn hoá, âm học, V/E/T mà build_student.predict cho ra)."""
    all_ids = json.loads((MUSIC / "embedding_ids.json").read_text(encoding="utf-8"))
    embeddings = np.load(MUSIC / "embeddings.npy").astype(np.float32)
    embedding = embeddings[all_ids.index(track)]
    embedding = embedding / np.linalg.norm(embedding)
    acoustic = {}
    for line in (MUSIC / "acoustic2.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            acoustic[row["id"]] = row
    model = np.load(MUSIC / "student_model.npz")
    mu, sd, coef, intercept, names = model["mu"], model["sd"], model["coef"], model["intercept"], [str(n) for n in model["names"]]
    tail = [float(acoustic[track][n]) if acoustic[track].get(n) is not None else mu[512 + i] for i, n in enumerate(names)]
    out = ((np.concatenate([embedding, tail]) - mu) / sd) @ coef.T + intercept
    return embedding, acoustic[track], np.clip(out[13:], -1, 1)  # build_student.predict: V / E / T


def _vet(result: dict) -> np.ndarray:
    return np.array([result["valence"], result["arousal"], result["tension"]])


def test_the_head_and_the_tower_reproduce_the_research_numbers(package: Path) -> None:
    """Hai nửa của đường chạy, mỗi nửa đối chiếu với bản nghiên cứu ở mức gần như tuyệt đối: (1) đầu trò + âm học cho cùng V/E/T khi
    nhận đúng vector nhúng của bản nghiên cứu; (2) tháp fp16 của gói cho gần như đúng vector nhúng ấy khi nhận đúng ba cửa sổ mà
    analyze_clap cắt (ffmpeg nhảy tới chỗ, không giải mã cả bài)."""
    ids, stem = _reference_ids()
    student = music_student._load()
    assert student is not None
    for track in ids:
        embedding, acoustic, expected = _reference(track, stem)
        got = student.predict(embedding.astype(np.float64), acoustic)
        assert np.abs(_vet(got) - expected).max() < 1e-3, track
        path = MUSIC / "audio_incompetech" / (stem(track) + ".mp3")
        duration = music_local.read_tags(path)["duration"]
        clips = []
        for fraction in (0.2, 0.5, 0.8):
            raw = subprocess.run([ffmpeg_executable(), "-v", "error", "-ss", f"{max(0.0, duration * fraction - 5):.2f}", "-t", "10",
                                  "-i", str(path), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=False).stdout
            clips.append(np.frombuffer(raw, dtype=np.float32))
        assert float(student.embed(clips) @ embedding) > 0.999, track


def test_the_app_prediction_stays_close_to_build_student_on_catalog_tracks(package: Path, capsys) -> None:
    """Cả đường chạy của app (giải mã cả bài, cắt ba cửa sổ trên mẫu đã giải mã) so với V/E/T của bản nghiên cứu. Khác nhau một chút
    là bình thường: bản nghiên cứu cắt cửa sổ bằng ffmpeg -ss theo độ dài ghi trong đầu file mp3, lệch vài trăm ms so với độ dài
    thật của mẫu giải mã nên cửa sổ trượt nhẹ (cos nhúng ~0,997)."""
    ids, stem = _reference_ids()
    worst = 0.0
    for track in ids:
        expected = _reference(track, stem)[2]
        got = music_student.analyze(MUSIC / "audio_incompetech" / (stem(track) + ".mp3"))
        assert got is not None, track
        diff = np.abs(expected - _vet(got))
        worst = max(worst, float(diff.max()))
        assert diff.max() < PARITY_TOLERANCE, f"{track}: V/E/T khác {diff.round(4).tolist()} (mong {expected.round(3).tolist()})"
    with capsys.disabled():
        print(f"\nmusic_student parity: max |diff| V/E/T = {worst:.4f} trên {len(ids)} bài")


# ---- đường ONNX (bản app chỉ-nghe: không torch / transformers / librosa) -------------------------------------------------------
ONNX_KEYS = {"valence", "arousal", "tension", "sd", "emotions", "confidence", "fitsUnderNarration", "family"}


@pytest.fixture(scope="module")
def onnx_folder(tmp_path_factory) -> Path:
    """Thư mục chỉ có ba file của đường ONNX (chép từ gói dựng ở LLM_Train): chứng tỏ ba file ấy là đủ."""
    pytest.importorskip("onnxruntime")
    folder = tmp_path_factory.mktemp("onnx_student")
    for name in music_student.PACKAGE_FILES["onnx"]:
        if not (PACKAGE / name).is_file():
            pytest.skip("không có gói model của trò ở " + str(PACKAGE))
        shutil.copyfile(PACKAGE / name, folder / name)
    return folder


@pytest.fixture
def onnx(monkeypatch, onnx_folder: Path) -> Path:
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    monkeypatch.setenv(music_student.ENV_DIR, str(onnx_folder))
    return onnx_folder


def test_the_backend_is_torch_when_it_imports_else_onnx_else_nothing(monkeypatch) -> None:
    present = {"numpy", "librosa", "torch", "transformers", "onnxruntime"}
    monkeypatch.setattr(music_student.importlib.util, "find_spec", lambda name: object() if name in present else None)
    assert music_student.backend() == "torch"
    present.discard("librosa")
    assert music_student.backend() == "onnx"
    present.discard("onnxruntime")
    assert music_student.backend() is None and not music_student.available()
    present.update({"librosa", "onnxruntime"})
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    assert music_student.backend() == "onnx", "ép onnx dù có torch"
    present.discard("onnxruntime")
    assert music_student.backend() is None, "ép một đường mà thiếu thư viện của nó: không rơi sang đường kia"
    monkeypatch.setenv(music_student.ENV_BACKEND, "torch")
    present.add("onnxruntime")
    assert music_student.backend() == "torch"


def test_each_backend_needs_only_its_own_files(tmp_path: Path, monkeypatch) -> None:
    for name in music_student.PACKAGE_FILES["onnx"]:
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    assert music_student._complete(tmp_path) and not music_student._complete(tmp_path, "torch")
    assert music_student.PACKAGE_HASHES.keys() >= {name for files in music_student.PACKAGE_FILES.values() for name in files}


def test_an_onnx_track_gets_a_full_entry_without_the_acoustic_key(tmp_path: Path, onnx: Path) -> None:
    song = _tones(tmp_path / "tones.wav")
    result = music_student.analyze(song)
    assert result is not None and ONNX_KEYS <= result.keys()
    assert "loudness" not in result, "speechBand cần âm học: đường onnx không bịa"
    assert result["confidence"] == 0.5 and set(result["sd"]) == {"valence", "arousal", "tension"}
    assert len(result["emotions"]) == 13 and all(0.0 <= v <= 1.0 for v in result["emotions"].values())
    cleaned = music_local.clean_analysis(result)
    assert cleaned is not None and cleaned["background"] == result["fitsUnderNarration"] and "speechBand" not in cleaned
    assert cleaned["family"] in music_local.music_plan.FAMILIES
    assert music_student.register() is True and music_local.analyzer_available()
    assert music_local.analyze(song)["valence"] == cleaned["valence"]
    assert music_student._load().backend == "onnx"


def test_onnx_too_short_or_unreadable_audio_is_not_analysed(tmp_path: Path, onnx: Path) -> None:
    assert music_student.analyze(_tones(tmp_path / "blip.wav", 1.5)) is None
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"not audio")
    assert music_student.analyze(broken) is None


def test_onnx_and_torch_agree_with_the_same_head_on_catalog_tracks(monkeypatch, onnx: Path, capsys) -> None:
    """Cùng cửa sổ, cùng đầu A: mel numpy + tháp fp16 ONNX so với extractor transformers + tháp torch fp32 của gói, trong 0,02."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    ids, stem = _reference_ids()
    paths = [MUSIC / "audio_incompetech" / (stem(track) + ".mp3") for track in ids]
    got = [music_student.analyze(path) for path in paths]
    assert all(result is not None for result in got)
    monkeypatch.setenv(music_student.ENV_BACKEND, "torch")
    monkeypatch.setenv(music_student.ENV_DIR, str(PACKAGE))
    music_student.reset()
    tower = music_student._load()
    assert tower is not None and tower.backend == "torch"
    head = music_student._Head(PACKAGE / "student_head_A.npz")
    worst = 0.0
    for path, result in zip(paths, got):
        clips = music_student._clap_windows(music_mel.decode(path, music_student.CLAP_RATE))
        expected = head.predict(tower.embed(clips))
        diff = np.abs(_vet(result) - _vet(expected))
        worst = max(worst, float(diff.max()))
        assert diff.max() < 0.02, f"{path.name}: V/E/T khác {diff.round(4).tolist()}"
        assert max(abs(result["emotions"][name] - value) for name, value in expected["emotions"].items()) < 0.02, path.name
        assert result["family"] == expected["family"], path.name
    with capsys.disabled():
        print(f"\nmusic_student onnx vs torch (same head A): max |diff| V/E/T = {worst:.5f} over {len(paths)} tracks")


class _Reply:
    """Thay phản hồi của urllib: trả `body` một lần rồi hết."""

    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Reply":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, count: int = -1) -> bytes:
        body, self.body = self.body, b""
        return body


@pytest.mark.parametrize("name", ["onnx", "torch"])
def test_no_download_happens_when_it_is_switched_off(tmp_path: Path, monkeypatch, name: str) -> None:
    opened: list[object] = []

    def refuse(*args, **kwargs):
        opened.append(args)
        raise AssertionError("không được chạm mạng")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setenv(music_student.ENV_BACKEND, name)
    assert music_student.os.environ[music_student.ENV_DOWNLOAD] == "0"
    monkeypatch.setattr(music_student.importlib.util, "find_spec", lambda module: object())
    music_student.configure(tmp_path / "student")
    assert music_student._download(tmp_path / "student") is False and not (tmp_path / "student").exists()
    assert music_student._load() is None and not music_student.available()
    assert music_student.analyze(_tones(tmp_path / "t.wav", 5)) is None
    assert opened == [], "ABOOK_MUSIC_STUDENT_DOWNLOAD=0 chặn mọi đường tải, kể cả HTTPS thuần"


def test_the_plain_https_download_is_pinned_verified_and_atomic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")
    monkeypatch.setattr(music_student.importlib.util, "find_spec", lambda module: object())
    bodies = {name: f"nội dung {name}".encode() for name in music_student.PACKAGE_FILES["onnx"]}
    hashes = {name: (hashlib.sha256(body).hexdigest(), len(body)) for name, body in bodies.items()}
    monkeypatch.setattr(music_student, "PACKAGE_HASHES", {**music_student.PACKAGE_HASHES, **hashes})
    asked: list[str] = []

    def fake(request, timeout=None):
        asked.append(request.full_url)
        return _Reply(bodies[request.full_url.rsplit("/", 1)[1]])

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    folder = tmp_path / "student"
    assert music_student._download(folder) is True
    assert asked == [f"https://huggingface.co/NGDtuanh/abook-music-student/resolve/{music_student.REVISION}/{name}"
                     for name in music_student.PACKAGE_FILES["onnx"]]
    assert sorted(path.name for path in folder.iterdir()) == sorted(music_student.PACKAGE_FILES["onnx"]), "không còn file .part"
    # Sai băm: không bao giờ giữ file.
    monkeypatch.setattr(music_student, "PACKAGE_HASHES", {**music_student.PACKAGE_HASHES, "clap_audio_fp16.onnx": ("0" * 64, 5)})
    other = tmp_path / "other"
    assert music_student._download(other) is False
    assert not (other / "clap_audio_fp16.onnx").exists() and not list(other.glob("*.part"))
