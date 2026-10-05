"""V hợp của Nhạc của tôi (webui/music_valence.py, docs/MUSIC_IMPORT.md "Đo cảm xúc nhạc chính xác hơn"): phép tính từ vector nhúng khớp tám bài vàng của
danh mục (CI, chỉ số - không có âm thanh), luồng nền ghi đè valence của trò một cách làm-tiếp-được / làm-lại-không-hại, tuỳ chọn chỉ cho máy đủ RAM và chỉ
tải khi bật. Kiểm đầu-cuối từ mp3 chỉ chạy cục bộ (không có file thì bỏ qua)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile

from abook.webui import music_local, music_student, music_valence
from tests.test_a_project_can_be_renamed_or_deleted import studio  # noqa: F401 - fixture dùng chung

FIXTURES = Path(__file__).parent / "fixtures" / "music_valence"
PACKAGE = Path("D:/Novels/LLM_Train/models/abook_music_student")  # gói đầy đủ (kể cả muq/) của máy dựng
AUDIO = Path("D:/Novels/LLM_Train/music/audio")  # bản sao mp3 của tám bài vàng (không nằm trong repo)


@pytest.fixture(scope="module")
def golden() -> list[dict]:
    return json.loads((FIXTURES / "vhop_golden.json").read_text(encoding="utf-8"))["tracks"]


@pytest.fixture(scope="module")
def reference(tmp_path_factory) -> music_valence.Reference:
    """load_reference đọc <thư mục gói>/muq/...: dựng một thư mục có hình ấy từ hai file fixture."""
    package = tmp_path_factory.mktemp("package")
    (package / "muq").mkdir()
    shutil.copyfile(FIXTURES / "valence_text.npz", package / "muq" / "valence_text.npz")
    shutil.copyfile(FIXTURES / "vhop_scale.json", package / "muq" / "vhop_scale.json")
    return music_valence.load_reference(package)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    music_valence.join(5)
    music_valence.configure(None, lambda: False, lambda value: None)
    music_student.reset()
    music_student.configure(None)
    monkeypatch.delenv(music_student.ENV_DIR, raising=False)
    monkeypatch.delenv(music_student.ENV_BACKEND, raising=False)
    music_local.set_analyzer(None)
    yield
    music_valence.join(5)
    music_valence.configure(None, lambda: False, lambda value: None)
    music_student.reset()
    music_student.configure(None)
    music_local.set_analyzer(None)


# ---- phép tính ---------------------------------------------------------------------------------------------------------------
def test_the_fixture_constants_are_exactly_the_files_the_app_downloads() -> None:
    """Hằng số / vector chữ trong fixture là byte-đúng hai file ghim ở gói model (muq/valence_text.npz, muq/vhop_scale.json): app tải về đúng cái đã kiểm."""
    for name, pinned in (("valence_text.npz", "muq/valence_text.npz"), ("vhop_scale.json", "muq/vhop_scale.json")):
        data = (FIXTURES / name).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == music_student.PACKAGE_HASHES[pinned], name


def test_eight_golden_tracks_give_the_catalog_valence_from_their_embeddings(golden, reference) -> None:
    """Từ vector nhúng CLAP + MuQ đã lưu, hằng số và vector chữ -> valence trong ±0,001 của số mong đợi (V hợp đổi sang hạng như danh mục)."""
    assert len(golden) == 8
    for row in golden:
        clap, muq = np.array(row["clap_embedding"]), np.array(row["muq_embedding"])
        clap, muq = clap / np.linalg.norm(clap), muq / np.linalg.norm(muq)
        value = music_valence.valence_from_embeddings(clap, muq, reference)
        assert value == pytest.approx(row["app_valence_expected"], abs=0.001), row["id"]
        assert abs(value - row["catalog_valence"]) < 0.01, row["id"]  # và sát hạng danh mục
        # từng nửa: số thô của danh mục (CLAP đủ dài để khác ~0,3 điểm thô ở bài opengameart: ffmpeg đọc độ dài file ấy khác)
        assert music_valence.muq_raw(muq, reference) == pytest.approx(row["muq_valence_raw_catalog"], abs=1e-3), row["id"]
        assert music_valence.clap_raw(clap, reference) == pytest.approx(row["clap_valence_raw_catalog"], abs=0.5), row["id"]


def test_the_rank_clamps_at_both_ends_like_np_interp(reference) -> None:
    low = music_valence.hybrid_valence(-1000.0, -10.0, reference)
    high = music_valence.hybrid_valence(1000.0, 10.0, reference)
    assert low == -1.0 and high == 1.0
    middle = music_valence.hybrid_valence(reference.clap_mean, reference.muq_mean, reference)
    assert -0.2 < middle < 0.2


def test_muq_windows_follow_the_clap_cut_at_24_khz_and_wrap_short_ones() -> None:
    rate, size = music_valence.MUQ_RATE, music_valence.MUQ_SAMPLES
    assert music_valence.muq_clips(np.zeros(rate * 2, dtype=np.float32)) == [], "dưới 3 giây: bỏ"
    short = np.arange(rate * 5, dtype=np.float32)
    (clip,) = music_valence.muq_clips(short)
    assert len(clip) == size and np.array_equal(clip[:len(short)], short) and np.array_equal(clip[len(short):], short[:size - len(short)]), "nối vòng từ đầu"
    long = np.arange(rate * 100, dtype=np.float32)
    clips = music_valence.muq_clips(long)
    n = len(long)
    assert len(clips) == 3
    for clip, fraction in zip(clips, (0.2, 0.5, 0.8)):
        start = min(max(int(n * fraction) - size // 2, 0), n - size)
        assert np.array_equal(clip, long[start:start + size])
    assert len(music_valence.muq_clips(np.zeros(size, dtype=np.float32))) == 1 and len(music_valence.muq_clips(np.zeros(size + 1, dtype=np.float32))) >= 1


# ---- sổ nhạc: đánh dấu nguồn, làm tiếp được -------------------------------------------------------------------------------------------
def _wav(path: Path, seconds: int = 12, hz: float = 220.0) -> Path:
    rate = 8000
    soundfile.write(path, (0.3 * np.sin(2 * np.pi * hz * np.arange(rate * seconds) / rate)).astype("float32"), rate)
    return path


STUDENT_RESULT = {"valence": -0.3, "arousal": 0.4, "tension": 0.1, "vetVar": {"valence": 0.07, "arousal": 0.03, "tension": 0.04},
                  "emotions": {"joy": 0.2}, "confidence": 0.5}


def test_the_hybrid_valence_replaces_only_the_valence_and_its_variance(tmp_path: Path) -> None:
    store = music_local.LocalMusic(tmp_path / "mine")
    music_local.set_analyzer(lambda path: dict(STUDENT_RESULT, vetVar=dict(STUDENT_RESULT["vetVar"])))
    music_local.set_analyzer_id("model-a")
    track, _ = store.import_file(_wav(tmp_path / "a.wav"))
    digest = music_local.music_plan.local_hash(track["link"])
    assert track["valence"] == -0.3 and "valenceBy" not in track and [d for d, _ in store.valence_pending("vhop1")] == [digest]
    assert store.set_valence(digest, 0.62, "vhop1") is True
    info = store.entries()[0]
    assert info["valence"] == 0.62 and info["valenceBy"] == "vhop1" and info["arousal"] == 0.4 and info["tension"] == 0.1
    assert info["vetVar"] == {"arousal": 0.03, "tension": 0.04}, "V hợp cùng thang với danh mục: không còn vetVar.valence, các trục khác giữ"
    assert store.valence_pending("vhop1") == [] and [d for d, _ in store.valence_pending("vhop2")] == [digest], "đổi bản V hợp thì đo lại"
    # ghi ra đĩa và đọc lại
    again = music_local.LocalMusic(tmp_path / "mine").entries()[0]
    assert again["valence"] == 0.62 and again["valenceBy"] == "vhop1"
    assert store.set_valence("0" * 40, 0.1, "vhop1") is False
    assert store.set_valence(digest, 5.0, "vhop1") and store.entries()[0]["valence"] == 1.0


def test_a_reanalysis_by_the_student_drops_the_mark_so_the_track_is_measured_again(tmp_path: Path) -> None:
    store = music_local.LocalMusic(tmp_path / "mine")
    music_local.set_analyzer(lambda path: dict(STUDENT_RESULT))
    music_local.set_analyzer_id("model-a")
    track, _ = store.import_file(_wav(tmp_path / "a.wav"))
    digest = music_local.music_plan.local_hash(track["link"])
    store.set_valence(digest, 0.62, "vhop1")
    music_local.set_analyzer_id("model-b")
    assert store.reanalyse() == 1
    assert store.entries()[0]["valence"] == -0.3 and [d for d, _ in store.valence_pending("vhop1")] == [digest]


# ---- luồng nền, công tắc, tải ----------------------------------------------------------------------------------------------------------
class _FakeScorer:
    made = 0
    scored: list[Path] = []

    def __init__(self, directory: Path) -> None:
        type(self).made += 1

    def score(self, path: Path) -> float | None:
        type(self).scored.append(path)
        return 0.5 if path.suffix == ".wav" else None

    def close(self) -> None:
        pass


@pytest.fixture
def worker(tmp_path: Path, monkeypatch):
    """Kho có hai bài đã phân tích bằng đầu trò, tuỳ chọn BẬT và đủ file (giả), tháp MuQ thay bằng bản giả."""
    _FakeScorer.made, _FakeScorer.scored = 0, []
    store = music_local.LocalMusic(tmp_path / "mine")
    music_local.set_analyzer(lambda path: dict(STUDENT_RESULT, vetVar=dict(STUDENT_RESULT["vetVar"])))
    music_local.set_analyzer_id("model-a")
    first = store.import_file(_wav(tmp_path / "a.wav", hz=220))[0]
    second = store.import_file(_wav(tmp_path / "b.wav", hz=330))[0]
    flag = {"on": True}
    music_valence.configure(store, lambda: flag["on"], lambda value: flag.update(on=value))
    monkeypatch.setattr(music_valence, "Scorer", _FakeScorer)
    monkeypatch.setattr(music_valence, "present", lambda directory=None: True)
    monkeypatch.setattr(music_student, "package_dir", lambda: tmp_path)
    return store, flag, [music_local.music_plan.local_hash(t["link"]) for t in (first, second)]


def test_the_background_pass_overwrites_every_pending_track_once_and_is_idempotent(worker) -> None:
    store, flag, digests = worker
    music_valence.kick()
    music_valence.join(10)
    assert {info["valence"] for info in store.entries()} == {0.5} and {info["valenceBy"] for info in store.entries()} == {"vhop1"}
    assert _FakeScorer.made == 1 and len(_FakeScorer.scored) == 2
    music_valence.kick()
    music_valence.join(10)
    assert _FakeScorer.made == 1 and len(_FakeScorer.scored) == 2, "làm lại không hại: bài đã đo thì không đo nữa, cả tháp cũng không nạp lại"
    status = music_valence.status()
    assert status["state"] == "ready" and status["pending"] == 0 and status["working"] is False


def test_a_track_added_later_is_picked_up_by_the_next_pass(worker, tmp_path: Path) -> None:
    store, flag, digests = worker
    music_valence.kick()
    music_valence.join(10)
    store.import_file(_wav(tmp_path / "c.wav", hz=440))
    music_valence.kick()
    music_valence.join(10)
    assert len(_FakeScorer.scored) == 3 and _FakeScorer.made == 2
    assert {info["valenceBy"] for info in store.entries()} == {"vhop1"}


def test_a_track_that_cannot_be_scored_keeps_the_student_numbers_and_is_not_retried(worker, monkeypatch) -> None:
    store, flag, digests = worker
    monkeypatch.setattr(_FakeScorer, "score", lambda self, path: None)
    music_valence.kick()
    music_valence.join(10)
    assert {info["valence"] for info in store.entries()} == {-0.3} and all("valenceBy" not in info for info in store.entries())
    assert _FakeScorer.made == 1


def test_nothing_runs_when_the_option_is_off_or_files_are_missing_or_there_is_no_student(worker, monkeypatch) -> None:
    store, flag, digests = worker
    flag["on"] = False
    music_valence.kick()
    music_valence.join(10)
    assert _FakeScorer.made == 0 and music_valence.status()["state"] == "off"
    flag["on"] = True
    monkeypatch.setattr(music_valence, "present", lambda directory=None: False)
    music_valence.kick()
    music_valence.join(10)
    assert _FakeScorer.made == 0 and music_valence.status()["state"] == "missing"
    monkeypatch.setattr(music_valence, "present", lambda directory=None: True)
    music_local.set_analyzer(None)
    music_valence.kick()
    music_valence.join(10)
    assert _FakeScorer.made == 0, "chưa có bộ phân tích CLAP: không có vector nhúng để hợp"


def test_turning_the_option_off_stops_before_the_next_track(worker, monkeypatch) -> None:
    store, flag, digests = worker

    def score(self, path):
        flag["on"] = False  # người dùng tắt giữa chừng
        return 0.5

    monkeypatch.setattr(_FakeScorer, "score", score)
    music_valence.kick()
    music_valence.join(10)
    assert sorted(info.get("valenceBy", "") for info in store.entries()) == ["", "vhop1"]


def test_the_option_is_for_machines_with_enough_ram_and_off_by_default(worker, monkeypatch) -> None:
    store, flag, digests = worker
    flag["on"] = False
    monkeypatch.setattr(music_valence, "ram_bytes", lambda: 4 * 1024 ** 3)
    monkeypatch.setattr(music_valence, "present", lambda directory=None: False)
    status = music_valence.status()
    assert status["state"] == "unavailable" and "8 GB" in status["reason"]
    with pytest.raises(ValueError, match="8 GB"):
        music_valence.enable()
    assert flag["on"] is False, "máy không đủ sức thì không bật"
    from abook.webui.library import DEFAULT_PREFERENCES

    assert DEFAULT_PREFERENCES["preciseMusicMood"] is False
    monkeypatch.setattr(music_valence, "ram_bytes", lambda: 8 * 1024 ** 3)
    assert music_valence.cannot_use() == "" and music_valence.status()["state"] == "off"


def test_turning_it_on_downloads_the_pinned_files_then_measures(worker, monkeypatch, tmp_path: Path) -> None:
    store, flag, digests = worker
    flag["on"] = False
    monkeypatch.setattr(music_valence, "ram_bytes", lambda: 16 * 1024 ** 3)
    have = {"files": False}
    monkeypatch.setattr(music_valence, "present", lambda directory=None: have["files"])
    seen: list[tuple[str, str, int]] = []

    def fake_download(part, target, progress):
        seen.extend((item.name, item.url, item.size) for item in part.downloads)
        progress(part.size)
        have["files"] = True

    monkeypatch.setattr(music_valence.voice_module, "download_files", fake_download)
    music_valence.enable()
    assert flag["on"] is True
    music_valence.join(10)
    music_valence.join(10)  # luồng tải rồi tới luồng đo
    assert [name for name, _, _ in seen] == list(music_student.PACKAGE_FILES["muq"])
    assert all(url == f"https://huggingface.co/{music_student.REPO_ID}/resolve/{music_student.REVISION}/{name}" for name, url, _ in seen)
    assert sum(size for _, _, size in seen) == music_valence.total_bytes() >= 1_273_000_000
    assert {info["valenceBy"] for info in store.entries()} == {"vhop1"}


def test_a_failed_download_is_one_sentence_and_does_not_turn_the_measuring_on_by_itself(worker, monkeypatch) -> None:
    store, flag, digests = worker
    flag["on"] = False
    monkeypatch.setattr(music_valence, "ram_bytes", lambda: 16 * 1024 ** 3)
    monkeypatch.setattr(music_valence, "present", lambda directory=None: False)

    def broken(part, target, progress):
        raise OSError("đầy ổ")

    monkeypatch.setattr(music_valence.voice_module, "download_files", broken)
    music_valence.enable()
    music_valence.join(10)
    status = music_valence.status()
    assert status["state"] == "error" and "Không tải được" in status["error"] and _FakeScorer.made == 0


# ---- kiểm đầu-cuối từ mp3 (chỉ cục bộ) ---------------------------------------------------------------------------------------------------
def _local_tracks(golden, monkeypatch):
    pytest.importorskip("onnxruntime")
    if not all((PACKAGE / name).is_file() for name in (*music_student.PACKAGE_FILES["onnx"], *music_student.PACKAGE_FILES["muq"])):
        pytest.skip("không có gói model đầy đủ ở " + str(PACKAGE))
    tracks = [(row, AUDIO / f"{row['id']}.mp3") for row in golden if (AUDIO / f"{row['id']}.mp3").is_file()]
    if not tracks:
        pytest.skip("không có bản sao mp3 của bài vàng ở " + str(AUDIO))
    monkeypatch.setenv(music_student.ENV_DIR, str(PACKAGE))
    monkeypatch.setenv(music_student.ENV_BACKEND, "onnx")
    assert music_student.register() is True
    return tracks


def test_the_whole_path_from_mp3_stays_near_the_catalog(golden, monkeypatch) -> None:
    """Giải mã -> CLAP (đầu A) -> MuQ ONNX -> V hợp, đúng đường của app, so với V danh mục. Nửa MuQ khớp danh mục tới 1e-3 (cùng cửa sổ, cùng tháp); nửa CLAP lệch vì app
    cắt cửa sổ trên mẫu đã giải mã còn analyze_clap nhảy ffmpeg -ss theo độ dài ghi ở đầu file - với bài có tiếng gảy / gõ rõ, vài chục mili giây đã đẩy cos nhúng xuống
    0,976-0,9995 (đo 05-10) và V hợp lệch tới 0,046, nên ngưỡng ở đây là 0,06 chứ không 0,02. Cần gói đầy đủ ở LLM_Train và bản sao mp3 (không nằm trong repo): thiếu thì bỏ qua."""
    tracks = _local_tracks(golden, monkeypatch)
    scorer = music_valence.Scorer(PACKAGE)
    try:
        for row, path in tracks:
            muq = scorer.embedding(music_valence.music_mel.decode(path, music_valence.MUQ_RATE))
            assert music_valence.muq_raw(muq, scorer.ref) == pytest.approx(row["muq_valence_raw_catalog"], abs=1e-3), row["id"]
            value = scorer.score(path)
            assert value is not None and abs(value - row["catalog_valence"]) <= 0.06, f"{row['id']}: {value} so với {row['catalog_valence']}"
    finally:
        scorer.close()


def test_with_the_catalog_window_cut_the_whole_path_matches_within_0_02(golden, monkeypatch) -> None:
    """Cùng đường nhưng ba cửa sổ CLAP cắt như analyze_clap (ffmpeg -ss theo độ dài ghi ở đầu file): hết khác biệt cắt cửa sổ thì V hợp trong ±0,02 của danh mục."""
    import re
    import subprocess

    from abook.io_utils import ffmpeg_executable

    tracks = _local_tracks(golden, monkeypatch)
    scorer = music_valence.Scorer(PACKAGE)
    student = music_student._load()
    try:
        for row, path in tracks:
            header = subprocess.run([ffmpeg_executable(), "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True, check=False).stderr.decode("utf-8", "replace")
            hours, minutes, seconds = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", header).groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            clips = []
            for fraction in (0.2, 0.5, 0.8):
                raw = subprocess.run([ffmpeg_executable(), "-v", "error", "-ss", f"{max(0.0, duration * fraction - 5):.2f}", "-t", "10", "-i", str(path),
                                      "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=False).stdout
                clips.append(np.frombuffer(raw, dtype=np.float32))
            clap = student.embed(clips)
            muq = scorer.embedding(music_valence.music_mel.decode(path, music_valence.MUQ_RATE))
            value = music_valence.valence_from_embeddings(clap, muq, scorer.ref)
            assert abs(value - row["catalog_valence"]) <= 0.02, f"{row['id']}: {value} so với {row['catalog_valence']}"
    finally:
        scorer.close()


# ---- xoá file MuQ ------------------------------------------------------------------------------------------------------------------------
def _put_package(folder: Path) -> list[Path]:
    """Gói nhạc giả: file của đường onnx + ba file muq/ (+ một .part dở dang)."""
    for name in music_student.PACKAGE_FILES["onnx"]:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"giu")
    muq = [folder / name for name in music_student.PACKAGE_FILES["muq"]]
    for path in muq:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)
    (folder / "muq" / "muq_mulan_audio.onnx.part").write_bytes(b"part")
    return muq


def test_removing_the_files_takes_only_the_muq_files_and_only_when_the_option_is_off(worker, tmp_path: Path) -> None:
    store, flag, digests = worker
    muq = _put_package(tmp_path)
    assert music_valence.status()["removable"] is False, "đang bật: chưa xoá được"
    with pytest.raises(ValueError, match="tắt"):
        music_valence.remove_files()
    assert all(path.is_file() for path in muq)
    flag["on"] = False
    assert music_valence.status()["removable"] is True
    freed = music_valence.remove_files()
    assert freed == 10 * len(muq) + len(b"part"), "trả số byte lấy lại, kể cả .part dở dang"
    assert not any(path.exists() for path in muq) and not (tmp_path / "muq").exists(), "gỡ đúng các file muq/ rồi dọn thư mục trống"
    assert all((tmp_path / name).read_bytes() == b"giu" for name in music_student.PACKAGE_FILES["onnx"]), "các file khác của gói nhạc giữ nguyên"
    assert music_valence.status()["removable"] is False
    assert music_valence.remove_files() == 0, "xoá lần nữa không hại"


def test_removing_is_refused_while_downloading_or_measuring(worker, tmp_path: Path) -> None:
    store, flag, digests = worker
    _put_package(tmp_path)
    flag["on"] = False
    for key in ("downloading", "working"):
        music_valence._state[key] = True
        try:
            assert music_valence.status()["removable"] is False
            with pytest.raises(ValueError, match="chờ xong"):
                music_valence.remove_files()
        finally:
            music_valence._state[key] = False
    assert music_valence.status()["removable"] is True


def test_the_server_removes_the_muq_files_through_the_api_and_turning_it_on_again_downloads_again(studio, monkeypatch) -> None:  # noqa: F811
    from tests.test_a_project_can_be_renamed_or_deleted import _call

    _paths, app, server, _runner = studio
    folder = music_student.package_dir()
    assert folder is not None
    muq = _put_package(folder)
    app.preferences.update({"preciseMusicMood": True})
    status, data = _call(server, "POST", "/api/music/local/precise/remove")
    assert status == 409 and "tắt" in data["error"] and all(path.is_file() for path in muq)
    app.preferences.update({"preciseMusicMood": False})
    status, view = _call(server, "GET", "/api/music/local")
    assert status == 200 and view["module"]["precise"]["removable"] is True
    status, view = _call(server, "POST", "/api/music/local/precise/remove")
    assert status == 200 and view["module"]["precise"]["removable"] is False and view["module"]["precise"]["present"] is False
    assert not any(path.exists() for path in muq) and (folder / "student_head_A.npz").read_bytes() == b"giu"
    # bật lại: file không còn nên phải tải lại (tải giả, không chạm mạng)
    monkeypatch.setattr(music_valence, "ram_bytes", lambda: 16 * 1024 ** 3)
    seen: list[str] = []
    monkeypatch.setattr(music_valence.voice_module, "download_files", lambda part, target, progress: seen.extend(item.name for item in part.downloads))
    music_local.set_analyzer(lambda path: None)  # "đã có bộ phân tích" cho cổng của máy chủ
    status, _ = _call(server, "POST", "/api/music/local/precise", {"enabled": True})
    music_valence.join(10)
    assert status == 200 and seen == list(music_student.PACKAGE_FILES["muq"])
