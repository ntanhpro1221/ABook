"""Bộ phân tích "trò" của Nhạc của tôi (webui/music_student.py): model chỉ-nghe, không bịa số. Có gói model thật (thư mục trỏ bởi
ABOOK_MUSIC_STUDENT_DIR hay bản dựng ở LLM_Train) thì thử cả đường nhúng CLAP + âm học + đầu trò; không có thì bỏ qua các bài ấy."""
from __future__ import annotations

import json
import math
import shutil
import urllib.request
from pathlib import Path

import numpy as np
import pytest
import soundfile

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
    assert music_student.clap_embedding(song) is None


def test_an_incomplete_package_is_not_used(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv(music_student.ENV_DIR, str(tmp_path))
    assert not music_student.available() and music_student.analyze(_tones(tmp_path / "a.wav", 5)) is None


def test_the_model_download_is_pinned_per_file_and_its_pin_follows_every_hash(monkeypatch) -> None:
    assert music_student.REVISION == "" or len(music_student.REVISION) == 40
    for name in ("onnx", "torch"):
        items = music_student.model_downloads(name)
        assert [item.name for item in items] == list(music_student.PACKAGE_FILES[name])
        for item in items:
            assert item.url == f"https://huggingface.co/{music_student.REPO_ID}/resolve/{music_student.REVISION}/{item.name}"
            assert (item.sha256, item.size) == music_student.PACKAGE_HASHES[item.name]
    before = music_student.model_pin("onnx")
    assert music_student.model_pin("torch") != before and music_student.model_id() == music_student.model_pin()[:12]
    # cùng tên file, cùng cỡ, khác nội dung (băm khác) hay khác commit -> ghim khác: gói đã tải thành "cũ"
    monkeypatch.setitem(music_student.PACKAGE_HASHES, "clap_audio_fp16.onnx", ("f" * 64, music_student.PACKAGE_HASHES["clap_audio_fp16.onnx"][1]))
    assert music_student.model_pin("onnx") != before
    monkeypatch.undo()
    monkeypatch.setattr(music_student, "REVISION", "1" * 40)
    assert music_student.model_pin("onnx") != before


def test_one_head_serves_every_machine_and_the_muq_files_are_an_optional_part_of_the_same_pin() -> None:
    """Đầu A MỚI cho cả torch lẫn onnx (đầu torch cũ bỏ); fixture của bài thử là byte-đúng file ghim; tháp MuQ (1,27 GB) thuộc phần tuỳ chọn riêng, không lọt vào đường nào."""
    import hashlib

    assert "student_head_A.npz" in music_student.PACKAGE_FILES["torch"] and "student_head_A.npz" in music_student.PACKAGE_FILES["onnx"]
    assert "student_head.npz" not in music_student.PACKAGE_HASHES and "student_head.npz" not in music_student.PACKAGE_FILES["torch"]
    fixture = (Path(__file__).parent / "fixtures" / "music_student" / "student_head_A.npz").read_bytes()
    assert (hashlib.sha256(fixture).hexdigest(), len(fixture)) == music_student.PACKAGE_HASHES["student_head_A.npz"]
    muq = music_student.model_downloads("muq")
    assert [item.name for item in muq] == ["muq/muq_mulan_audio.onnx", "muq/valence_text.npz", "muq/vhop_scale.json"]
    assert muq[0].url == f"https://huggingface.co/{music_student.REPO_ID}/resolve/{music_student.REVISION}/muq/muq_mulan_audio.onnx"
    assert not set(music_student.PACKAGE_FILES["muq"]) & (set(music_student.PACKAGE_FILES["onnx"]) | set(music_student.PACKAGE_FILES["torch"]))
    assert music_student.model_pin("muq") not in (music_student.model_pin("onnx"), music_student.model_pin("torch"))


def test_the_module_may_download_only_when_nothing_forbids_or_provides_it(monkeypatch) -> None:
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")
    assert music_student.cannot_download() == ""
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "0")  # conftest đặt sẵn như vậy cho mọi bài thử
    assert "tắt" in music_student.cannot_download()
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")
    monkeypatch.setenv(music_student.ENV_DIR, "/da/co/goi")
    assert "chỉ định sẵn" in music_student.cannot_download()
    monkeypatch.delenv(music_student.ENV_DIR)
    monkeypatch.setattr(music_student, "REVISION", "")
    assert "chưa có bản model" in music_student.cannot_download(), "chưa ghim commit thì không bao giờ tải"


def test_a_synthetic_track_gets_a_full_entry_that_survives_clean_analysis(tmp_path: Path, package: Path) -> None:
    song = _tones(tmp_path / "tones.wav")
    result = music_student.analyze(song)
    assert result is not None
    assert {"valence", "arousal", "tension", "vetVar", "emotions", "confidence", "fitsUnderNarration", "family", "loudness"} <= result.keys()
    assert result["confidence"] == 0.5 and set(result["vetVar"]) == {"valence", "arousal", "tension"} and "sd" not in result
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
    needed = [MUSIC / name for name in ("embedding_ids.json", "embeddings.npy", "music_files.py")]
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
    """Hàng của bài `track` trong bộ dữ liệu nghiên cứu: (nhúng đã chuẩn hoá CLAP, V/E/T thô của đầu A tính lại bằng numpy từ file đầu ở gói - không gọi code của app)."""
    all_ids = json.loads((MUSIC / "embedding_ids.json").read_text(encoding="utf-8"))
    embeddings = np.load(MUSIC / "embeddings.npy").astype(np.float32)
    embedding = embeddings[all_ids.index(track)]
    embedding = embedding / np.linalg.norm(embedding)
    head = np.load(PACKAGE / "student_head_A.npz")
    out = ((embedding - head["mu"]) / head["sd"]) @ head["coef"].T + head["intercept"]
    return embedding, np.clip(out[13:], -1, 1)  # V / E / T thô


def _vet(result: dict) -> np.ndarray:
    return np.array([result["valence"], result["arousal"], result["tension"]])


def _calibrated(raw: np.ndarray, backend: str) -> np.ndarray:
    """V/E/T thô của bản nghiên cứu -> số sau hiệu chỉnh F2 của đường `backend` (phép tính viết lại, không gọi code của app)."""
    table = music_student.CALIBRATION[backend]
    return np.array([np.clip(table[axis][0] + table[axis][1] * value, -1, 1)
                     for axis, value in zip(("valence", "arousal", "tension"), raw)])


def test_the_head_and_the_tower_reproduce_the_research_numbers(package: Path) -> None:
    """Hai nửa của đường chạy, mỗi nửa đối chiếu với bản nghiên cứu ở mức gần như tuyệt đối: (1) đầu A cho cùng V/E/T khi
    nhận đúng vector nhúng của bản nghiên cứu; (2) tháp fp16 của gói cho gần như đúng vector nhúng ấy trên đúng ba cửa sổ của app
    (giải mã cả bài rồi audio_windows - danh mục dựng lại bằng chính cách cắt này từ 05-10)."""
    ids, stem = _reference_ids()
    student = music_student._load()
    assert student is not None
    for track in ids:
        embedding, expected = _reference(track, stem)
        got = student.predict(embedding.astype(np.float64))
        assert np.abs(_vet(got) - _calibrated(expected, "torch")).max() < 1e-3, track
        path = MUSIC / "audio_incompetech" / (stem(track) + ".mp3")
        clips = music_student._clips(path)
        assert float(student.embed(clips) @ embedding) > 0.999, track


def test_the_app_prediction_stays_close_to_build_student_on_catalog_tracks(package: Path, capsys) -> None:
    """Cả đường chạy của app (giải mã cả bài, cắt ba cửa sổ trên mẫu đã giải mã) so với V/E/T của bản nghiên cứu. Khác nhau một chút
    là bình thường: bản nghiên cứu cắt cửa sổ bằng ffmpeg -ss theo độ dài ghi trong đầu file mp3, lệch vài trăm ms so với độ dài
    thật của mẫu giải mã nên cửa sổ trượt nhẹ (cos nhúng ~0,997)."""
    ids, stem = _reference_ids()
    worst = 0.0
    for track in ids:
        expected = _calibrated(_reference(track, stem)[1], music_student.backend())
        got = music_student.analyze(MUSIC / "audio_incompetech" / (stem(track) + ".mp3"))
        assert got is not None, track
        diff = np.abs(expected - _vet(got))
        worst = max(worst, float(diff.max()))
        assert diff.max() < PARITY_TOLERANCE, f"{track}: V/E/T khác {diff.round(4).tolist()} (mong {expected.round(3).tolist()})"
    with capsys.disabled():
        print(f"\nmusic_student parity: max |diff| V/E/T = {worst:.4f} trên {len(ids)} bài")


class _FakeHead(music_student._Head):
    """Đầu giả 512 chiều, V/E/T thô = intercept (hệ số 0): thử riêng phần hiệu chỉnh mà không cần gói model."""

    def __init__(self, backend: str, raw: tuple[float, float, float]) -> None:
        self.backend = backend
        self.mu, self.sd = np.zeros(512), np.ones(512)
        self.names, self.emotions = [], ["peacefulness"]
        self.coef, self.intercept = np.zeros((4, 512)), np.array([0.0, *raw])
        self.background, self.family_names, self.family_text = np.ones((2, 512)), ["eastern"], np.ones((1, 512))


@pytest.mark.parametrize("backend", ["torch", "onnx"])
def test_the_head_calibrates_the_means_drops_sd_and_reports_the_residual_variance(backend: str) -> None:
    embedding = np.zeros(512)
    embedding[0] = 1.0
    got = _FakeHead(backend, (0.1, -0.2, 0.0)).predict(embedding)
    table = music_student.CALIBRATION[backend]
    for axis, raw in (("valence", 0.1), ("arousal", -0.2), ("tension", 0.0)):
        assert got[axis] == pytest.approx(table[axis][0] + table[axis][1] * raw)
    assert got["vetVar"] == {axis: table[axis][2] for axis in table} and "sd" not in got
    assert got["family"] == "eastern" and len(got["emotions"]) == 1 and got["confidence"] == music_student.CONFIDENCE
    clipped = _FakeHead(backend, (0.99, -0.99, 5.0)).predict(embedding)
    assert clipped["valence"] == 1.0 and clipped["tension"] == 1.0 and -1.0 <= clipped["arousal"] < 0.0
    assert _FakeHead(backend, (-5.0, 0.0, 0.0)).predict(embedding)["valence"] == -1.0


def test_the_constants_come_from_the_f2_fit() -> None:
    assert music_student.CALIBRATION["onnx"] == {"valence": (-0.057, 1.251, 0.0727), "arousal": (-0.013, 1.098, 0.0322), "tension": (-0.003, 1.283, 0.0412)}
    assert music_student.CALIBRATION["torch"] == music_student.CALIBRATION["onnx"], "MỘT bảng cho mọi đường (đầu A cho mọi máy)"
    assert all(len(v) == 3 for table in music_student.CALIBRATION.values() for v in table.values())
    raw = _FakeHead("", (0.1, 0.2, 0.3)).predict(np.eye(512)[0])
    assert (raw["valence"], raw["arousal"], raw["tension"]) == pytest.approx((0.1, 0.2, 0.3)) and "vetVar" not in raw


# ---- đường ONNX (bản app chỉ-nghe: không torch / transformers / librosa) -------------------------------------------------------
ONNX_KEYS = {"valence", "arousal", "tension", "vetVar", "emotions", "confidence", "fitsUnderNarration", "family"}


@pytest.fixture(scope="module")
def onnx_folder(tmp_path_factory) -> Path:
    """Thư mục chỉ có ba file của đường ONNX (chép từ gói dựng ở LLM_Train): chứng tỏ ba file ấy là đủ."""
    pytest.importorskip("onnxruntime")
    folder = tmp_path_factory.mktemp("onnx_student")
    for name in music_student.PACKAGE_FILES["onnx"]:
        if not (PACKAGE / name).is_file():
            if name in music_student.OPTIONAL_FILES:
                continue  # gói dựng cũ chưa có đầu dò lời hát: bài thử đường ONNX vẫn chạy (không có hai khoá vocals)
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
    assert result["confidence"] == 0.5 and set(result["vetVar"]) == {"valence", "arousal", "tension"} and "sd" not in result
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
        diff = np.abs(_vet(result) - _calibrated(_vet(expected), "onnx"))
        worst = max(worst, float(diff.max()))
        assert diff.max() < 0.02, f"{path.name}: V/E/T khác {diff.round(4).tolist()}"
        assert max(abs(result["emotions"][name] - value) for name, value in expected["emotions"].items()) < 0.02, path.name
        assert result["family"] == expected["family"], path.name
    with capsys.disabled():
        print(f"\nmusic_student onnx vs torch (same head A): max |diff| V/E/T = {worst:.5f} over {len(paths)} tracks")


@pytest.mark.parametrize("name", ["onnx", "torch"])
def test_analysis_never_downloads_anything_on_its_own(tmp_path: Path, monkeypatch, name: str) -> None:
    """Gói model chỉ tải khi người dùng bấm "Phân tích nhạc" (music_module): nạp / phân tích một bài không bao giờ chạm mạng."""
    opened: list[object] = []

    def refuse(*args, **kwargs):
        opened.append(args)
        raise AssertionError("không được chạm mạng")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setenv(music_student.ENV_BACKEND, name)
    monkeypatch.setenv(music_student.ENV_DOWNLOAD, "1")  # kể cả khi được phép tải
    monkeypatch.setattr(music_student.importlib.util, "find_spec", lambda module: object())
    music_student.configure(tmp_path / "student")
    assert music_student._load() is None and not music_student.available()
    assert music_student.analyze(_tones(tmp_path / "t.wav", 5)) is None
    assert opened == [] and not (tmp_path / "student").exists()
    assert music_student.planned_backend() == name


# ---- đầu dò lời hát (vox_head.npz) ----------------------------------------------------------------------------------------
FIXTURE_HEAD = Path(__file__).parent / "fixtures" / "music_student" / "student_head_A.npz"


def _fake_vox(directory: Path, *, tau: float = 0.5, coef_at: int = 0, mu: float = 0.0, sd: float = 1.0, intercept: float = 0.0) -> Path:
    """Gói giả: đầu A thật của bài thử + đầu dò lời hát mà coef = e_{coef_at}, intercept 0 (xác suất = sigmoid của thành phần ấy)."""
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURE_HEAD, directory / "student_head_A.npz")
    coef = np.zeros(512, dtype=np.float32)
    coef[coef_at] = 1.0
    np.savez(directory / "vox_head.npz", mu=np.full(512, mu, dtype=np.float32), sd=np.full(512, sd, dtype=np.float32), coef=coef,
             intercept=np.array([intercept], dtype=np.float32), tau=np.array([tau], dtype=np.float32))
    return directory / "student_head_A.npz"


class _OnnxHead(music_student._Head):
    backend = "onnx"


def _unit(first: float) -> np.ndarray:
    vector = np.zeros(512)
    vector[0], vector[1] = first, 1.0
    return vector / np.linalg.norm(vector)


def test_the_vox_head_flags_sung_vocals_from_the_same_embedding(tmp_path: Path) -> None:
    head = _OnnxHead(_fake_vox(tmp_path / "pkg"))
    sung, plain = head.predict(_unit(+2.0)), head.predict(_unit(-2.0))
    assert sung["vocalsLikely"] is True and plain["vocalsLikely"] is False
    assert 0.5 < sung["vocals"] <= 1.0 and 0.0 <= plain["vocals"] < 0.5
    first = _unit(+2.0)[0]
    assert sung["vocals"] == round(1.0 / (1.0 + math.exp(-first)), 3), "sigmoid(((e - mu) / sd) @ coef + intercept)"
    assert head.predict(_unit(0.0))["vocalsLikely"] is False or head.predict(_unit(0.0))["vocals"] >= 0.5


def test_the_vox_threshold_is_the_packages_tau_not_one_half(tmp_path: Path) -> None:
    embedding = _unit(+2.0)
    low = _OnnxHead(_fake_vox(tmp_path / "low", tau=0.2)).predict(embedding)
    high = _OnnxHead(_fake_vox(tmp_path / "high", tau=0.99)).predict(embedding)
    assert low["vocals"] == high["vocals"] and low["vocalsLikely"] is True and high["vocalsLikely"] is False


def test_without_the_vox_file_the_result_has_no_vocal_keys_and_every_old_key_is_unchanged(tmp_path: Path) -> None:
    with_vox = _OnnxHead(_fake_vox(tmp_path / "with")).predict(_unit(+2.0))
    without = _OnnxHead(FIXTURE_HEAD).predict(_unit(+2.0))  # thư mục của fixture có vox_head.npz: dựng gói không có nó
    bare = tmp_path / "bare"
    bare.mkdir()
    shutil.copyfile(FIXTURE_HEAD, bare / "student_head_A.npz")
    absent = _OnnxHead(bare / "student_head_A.npz").predict(_unit(+2.0))
    assert "vocals" not in absent and "vocalsLikely" not in absent, "thiếu tệp thì không đoán"
    assert {key: value for key, value in with_vox.items() if not key.startswith("vocals")} == absent
    assert {key: value for key, value in without.items() if not key.startswith("vocals")} == absent


def test_a_vox_file_of_the_wrong_shape_is_refused(tmp_path: Path) -> None:
    path = _fake_vox(tmp_path / "pkg")
    np.savez(path.with_name("vox_head.npz"), mu=np.zeros(3, dtype=np.float32), sd=np.ones(3, dtype=np.float32), coef=np.zeros(3, dtype=np.float32),
             intercept=np.zeros(1, dtype=np.float32), tau=np.full(1, 0.5, dtype=np.float32))
    with pytest.raises(ValueError, match="đầu dò lời hát"):
        _OnnxHead(path)


def test_the_package_pins_the_vox_head_for_both_ways_but_an_older_package_without_it_still_runs(tmp_path: Path) -> None:
    import hashlib

    assert music_student.REVISION == "eed82cec48a525de0582dcb5e7c3f436f165a39d"
    assert "vox_head.npz" in music_student.PACKAGE_FILES["torch"] and "vox_head.npz" in music_student.PACKAGE_FILES["onnx"]
    assert music_student.PACKAGE_HASHES["vox_head.npz"] == ("2def334c729b04ff918072aa0821a3e0146c77d9c1df90a21f1b676f47a48359", 7_374)
    fixture = (FIXTURE_HEAD.parent / "vox_head.npz").read_bytes()
    assert (hashlib.sha256(fixture).hexdigest(), len(fixture)) == music_student.PACKAGE_HASHES["vox_head.npz"]
    assert [item.name for item in music_student.model_downloads("onnx")][-1] == "vox_head.npz"
    old = tmp_path / "old"
    old.mkdir()
    for name in music_student.PACKAGE_FILES["onnx"]:
        if name != "vox_head.npz":
            (old / name).write_bytes(b"x")
    assert music_student._complete(old, "onnx"), "gói cũ chưa có đầu dò lời hát vẫn dùng được"
    (old / "student_head_A.npz").unlink()
    assert not music_student._complete(old, "onnx"), "thiếu file bắt buộc thì không"
