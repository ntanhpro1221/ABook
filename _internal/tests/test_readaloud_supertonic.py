"""Giọng Supertonic cho "Nghe ngay": liệt kê giọng, đọc một đoạn ra WAV (engine giả), chữ đưa vào model, mô-đun tải (ghim, kiểm SHA-256, dùng chung bộ đọc
chữ với VieNeu, tự đo, gỡ), đường máy chủ. Không chạm mạng: studio_setup.download là bản giả (trừ bài kiểm băm sai, tải từ file cục bộ).

Bài so với gói `supertonic` 1.3.1 của hãng (`parity`) và bài đọc thật chỉ chạy khi máy có model Supertonic 3 (thư mục ~/.cache/supertonic3 của
gói hãng, hay mô-đun đã tải vào dữ liệu app): cùng nhiễu khởi đầu -> cùng sóng âm.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from abook import english_vi
from abook.readaloud import cache, prepare, readings, supertonic
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed, SupertonicEngine, SupertonicProvider
from abook.webui import music_module, studio_setup, supertonic_module, vieneu_module, word_timing
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_readaloud_vieneu import Network


# ---- chữ đưa vào model ----------------------------------------------------------------------------------------------------------------
def test_clean_follows_the_vendor_text_rules() -> None:
    assert supertonic.clean("  Xin   chào ,  bạn  ") == unicode_nfkd("Xin chào, bạn.")
    assert supertonic.clean("Ừ !") == unicode_nfkd("Ừ!")
    assert supertonic.clean("“Đi nào” – anh nói") == unicode_nfkd('"Đi nào" - anh nói.')
    assert supertonic.clean("vui 😀 quá ♥") == unicode_nfkd("vui quá.")
    assert supertonic.clean("giá <en>u s d</en> nhé") == unicode_nfkd("giá u s d nhé.")
    assert supertonic.clean("") == ""


def unicode_nfkd(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", text)


def test_numbers_dates_and_times_become_words_before_the_model() -> None:
    pytest.importorskip("sea_g2p")
    text = supertonic.normalize_pieces(["Yamada-senpai hẹn gặp Kim Jaehun lúc 7 giờ 30 tối ngày 14 tháng 2, ở phòng số 404."])
    assert "bảy giờ ba mươi" in text and "mười bốn tháng hai" in text and "bốn trăm lẻ bốn" in text
    assert not any(char.isdigit() for char in text)


def test_unknown_characters_are_dropped_not_fatal(tmp_path: Path) -> None:
    engine = SupertonicEngine.__new__(SupertonicEngine)
    engine.indexer = np.full(256, -1, dtype=np.int64)
    for code, char in enumerate("<vi>/abc. "):
        engine.indexer[ord(char)] = code
    ids = engine.ids("a b中c.")  # chữ Hán không có trong bảng; 'ord' > 255 cũng không làm hỏng
    assert ids.tolist() == [engine.indexer[ord(c)] for c in "<vi>a bc.</vi>"]


# ---- giọng với engine giả -----------------------------------------------------------------------------------------------------------
class FakeEngine:
    """Mỗi khúc: một tiếng "bíp" dài theo số chữ, 50 ms im lặng hai đầu."""

    SAMPLE_RATE = 44_100

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def infer(self, text: str, name: str, _rng, _speed: float = supertonic.SPEED) -> np.ndarray:
        self.calls.append((name, text))
        words = max(1, len(text.split()))
        quiet = np.zeros(int(0.05 * self.SAMPLE_RATE), dtype=np.float32)
        body = 0.3 * np.sin(np.arange(int(0.25 * words * self.SAMPLE_RATE)) / 3).astype(np.float32)
        return np.concatenate([quiet, body, quiet])


@pytest.fixture
def fake_voices(tmp_path: Path):
    engine = FakeEngine()
    found = Installed(tmp_path, False)
    provider = SupertonicProvider(lambda: found, engines=lambda _found: engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces).lower())
    return provider, engine


def test_voices_list_the_four_good_ones_first_with_gender(fake_voices) -> None:
    provider, _ = fake_voices
    voices = provider.voices()
    assert [voice.id for voice in voices][:4] == ["supertonic:F1", "supertonic:F3", "supertonic:M4", "supertonic:M5"], "bốn giọng chủ sách nghe thấy tốt"
    assert sorted(voice.id for voice in voices) == sorted(f"supertonic:{sex}{n}" for sex in "FM" for n in range(1, 6))
    assert voices[0].name == "Supertonic F1" and all(not voice.online and not voice.default for voice in voices)
    assert {voice.id: voice.gender for voice in voices}["supertonic:M4"] == "male" and voices[0].gender == "female"
    assert SupertonicProvider(lambda: None).voices() == [], "chưa tải: không có giọng nào"


def test_a_clip_is_a_wav_with_one_timing_per_word(fake_voices, tmp_path: Path) -> None:
    provider, engine = fake_voices
    provider.speaks_english = False
    service = ReadAloud(tmp_path / "cache", [provider])
    text = "Khi ánh đèn vụt tắt, cả nhà chìm vào bóng tối. Chỉ còn tiếng đồng hồ - đều đặn!"
    clip = service.clip("supertonic:M4", text)
    words = clip["words"]
    assert len(words) == len(text.split()) and all(a <= b for a, b in words) and words[-1][1] <= clip["duration_ms"]
    with wave.open(io.BytesIO((tmp_path / "cache" / clip["file"]).read_bytes())) as handle:
        assert handle.getframerate() == 44_100 and handle.getnchannels() == 1
        assert abs(handle.getnframes() / 44_100 * 1000 - clip["duration_ms"]) < 5
    assert len(engine.calls) == 1 and engine.calls[0][0] == "M4", "cả đoạn vừa một khúc; đúng giọng"
    assert service.clip("supertonic:M4", text) == clip and len(engine.calls) == 1, "lần sau lấy bộ đệm"


def test_the_text_goes_through_the_normalizer_per_unit(fake_voices) -> None:
    provider, engine = fake_voices
    provider.synthesize("Lúc 7 giờ. Anh đến.", "F1")
    assert engine.calls == [("F1", "lúc 7 giờ. anh đến.")]


def test_an_unknown_voice_or_no_install_says_so(fake_voices) -> None:
    provider, _ = fake_voices
    with pytest.raises(supertonic.VoiceError) as error:
        provider.synthesize("Xin chào.", "X9")
    assert error.value.reason == "voice"
    with pytest.raises(supertonic.VoiceError):
        SupertonicProvider(lambda: None).synthesize("Xin chào.", "F1")


def test_benchmark_reports_speed(fake_voices) -> None:
    provider, _ = fake_voices
    result = provider.benchmark()
    assert result["audioSeconds"] > 1 and result["rtf"] >= 0 and result["firstAudioMs"] >= 0


def test_prepare_counts_wav_bytes_at_the_real_sample_rate() -> None:
    assert prepare.bytes_per_second("supertonic:F1") == 2 * 44_100


def test_every_file_the_engine_reads_is_in_the_download_list() -> None:
    names = {item.name for item in supertonic_module.FILES}
    needed = {f"onnx/{name}.onnx" for name in supertonic.ONNX} | {supertonic.CONFIG_FILE, supertonic.INDEXER_FILE, "LICENSE", "config.json"}
    needed |= {f"{supertonic.STYLE_DIR}/{name}.json" for name in supertonic.NAMES}
    assert needed == names
    assert all(item.url == f"https://huggingface.co/{supertonic_module.SOURCE_REPO}/resolve/{supertonic_module.SOURCE_REVISION}/{item.name}"
               for item in supertonic_module.FILES), "nơi tải là MỘT hằng (repo + commit)"
    assert len(supertonic_module.SOURCE_REVISION) == 40 and all(len(item.sha256) == 64 for item in supertonic_module.FILES)


# ---- mô-đun tải --------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "path", sys.path.copy())  # sea_g2p giả của bài thử không được lọt sang bài khác
    for variable in (vieneu_module.ENV_DOWNLOAD, supertonic_module.ENV_DOWNLOAD, music_module.ENV_DOWNLOAD):
        monkeypatch.setenv(variable, "1")
    monkeypatch.delenv(word_timing.ENV_DIR, raising=False)
    monkeypatch.delenv(word_timing.ENV_RUNTIME, raising=False)
    monkeypatch.setattr(word_timing, "_more", [])
    monkeypatch.setattr(word_timing, "_studio", None)
    monkeypatch.setattr(word_timing, "model_dir", lambda: None)
    monkeypatch.setattr(vieneu_module, "_g2p_external", lambda: False)
    monkeypatch.setattr(music_module, "_libs_external", lambda: True)
    monkeypatch.setattr(vieneu_module, "_facts", {"cores": 16, "ramGb": 16.0, "gpu": "", "runs": "cpu"})
    network = Network()
    monkeypatch.setattr(studio_setup, "download", network.download)
    music_module.configure(tmp_path / "music")
    measured: list[str] = []
    forgotten: list[int] = []

    def bench(tier: str) -> dict:
        measured.append(tier)
        return {"rtf": 0.25, "firstAudioMs": 900, "loadMs": 1000, "audioSeconds": 5.0}

    vieneu_module.configure(tmp_path / "vieneu")
    supertonic_module.configure(tmp_path / "supertonic", benchmark=bench, after_install=lambda: forgotten.append(1))
    yield network, measured, forgotten, tmp_path
    supertonic_module.join(10)
    supertonic_module.configure(None)
    vieneu_module.configure(None)
    music_module.configure(None)
    importlib.invalidate_caches()


def test_size_counts_only_what_this_machine_lacks(module) -> None:
    status = supertonic_module.status()
    (choice,) = status["choices"]
    model = sum(item.size for item in supertonic_module.FILES)
    assert status["state"] == "missing" and choice["id"] == "supertonic" and choice["installed"] is False
    assert choice["bytes"] == model + vieneu_module.G2P.size, "thư viện chạy model máy đã có: không tính; bộ đọc chữ chưa có thì tính"
    assert 380_000_000 < model < 420_000_000
    assert status["benchmark"] == {} and status["suggestion"] is None


def test_install_downloads_pinned_files_measures_and_shares_the_g2p_part(module) -> None:
    network, measured, forgotten, root = module
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    status = supertonic_module.status()
    assert status["state"] == "ready" and status["error"] == "", status
    assert sorted(set(network.calls)) == sorted({item.name for item in supertonic_module.FILES} | {"sea-g2p"})
    assert measured == ["supertonic"] and status["benchmark"]["supertonic"]["rtf"] == 0.25 and status["suggestion"] is None
    assert forgotten, "tải xong thì giọng đang nạp được bỏ để nạp lại"
    stamp = json.loads((root / "supertonic" / "module.json").read_bytes())
    assert stamp["pins"] == {"supertonic": supertonic_module.pin(supertonic_module.FILES)}, "ghim của bộ đọc chữ nằm ở dấu của VieNeu"
    assert vieneu_module.g2p_state() == "current" and (root / "vieneu" / "lib" / "sea_g2p").is_dir()
    found = supertonic_module.installed()
    assert found is not None and found.folder == root / "supertonic" / "model" and (found.folder / "voice_styles" / "F1.json").is_file()
    assert supertonic_module.rtf("supertonic:F1") == 0.25 and supertonic_module.rtf("vieneu:turbo/A") is None
    assert vieneu_module.status()["state"] == "missing", "bộ đọc chữ có rồi nhưng giọng VieNeu thì chưa"


def test_the_g2p_part_is_not_downloaded_twice(module) -> None:
    network, _measured, _forgotten, _root = module
    vieneu_module.start(["nano"])
    vieneu_module.join(10)
    network.calls.clear()
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    assert "sea-g2p" not in network.calls and supertonic_module.status()["state"] == "ready"


def test_a_slow_machine_is_offered_the_online_voice_never_switched(module) -> None:
    assert supertonic_module.suggestion({"supertonic": {"rtf": 0.9}}, ["supertonic"]) == {
        "tier": "supertonic", "rtf": 0.9, "switchTo": "online", "installed": True}
    assert supertonic_module.suggestion({"supertonic": {"rtf": 0.3}}, ["supertonic"]) is None
    assert supertonic_module.suggestion({"supertonic": {"rtf": 2.0}}, []) is None, "chưa tải: không đề nghị"


def test_a_changed_pin_updates_only_that_file(module, monkeypatch: pytest.MonkeyPatch) -> None:
    network, _measured, _forgotten, _root = module
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    network.calls.clear()
    changed = tuple(studio_setup.Download(item.name, item.url, ("0" * 64) if item.name == "config.json" else item.sha256, item.size)
                    for item in supertonic_module.FILES)
    monkeypatch.setattr(supertonic_module, "FILES", changed)
    status = supertonic_module.status()
    assert status["state"] == "outdated" and status["outdatedParts"] == ["Giọng Supertonic"]
    supertonic_module.start(None)
    supertonic_module.join(10)
    assert set(network.calls) == {item.name for item in changed}, "phần đổi ghim tải lại cả phần (file nào đã khớp băm thì không tải lại - đây là bản giả)"
    assert supertonic_module.status()["state"] == "ready"


def test_remove_gives_the_space_back_and_forgets_the_pin(module) -> None:
    _network, _measured, forgotten, root = module
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    before = len(forgotten)
    supertonic_module.remove()
    status = supertonic_module.status()
    assert not (root / "supertonic" / "model").exists() and status["state"] == "missing" and status["benchmark"] == {}
    assert len(forgotten) == before + 1 and "supertonic" not in json.loads((root / "supertonic" / "module.json").read_bytes())["pins"]
    assert supertonic_module.installed() is None
    with pytest.raises(ValueError):
        supertonic_module.remove("khác")


def test_a_wrong_hash_is_deleted_and_reported(module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.undo()  # trả studio_setup.download thật: bài này kiểm băm thật, từ file cục bộ
    source = tmp_path / "source.bin"
    source.write_bytes(b"not the pinned weights")
    bad = studio_setup.Download("onnx/vocoder.onnx", source.as_uri(), "ab" * 32, source.stat().st_size)
    target = tmp_path / "out" / "onnx" / "vocoder.onnx"
    with pytest.raises(studio_setup.SetupError) as error:
        studio_setup.download(bad, target, lambda *_: None, lambda: False)
    assert "không đúng bản đã ghim" in str(error.value)
    assert not target.exists() and not target.with_name(target.name + ".part").exists()


def test_the_module_reports_a_wrong_hash_as_an_error_with_no_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (vieneu_module.ENV_DOWNLOAD, supertonic_module.ENV_DOWNLOAD):
        monkeypatch.setenv(variable, "1")
    monkeypatch.setattr(music_module, "_libs_external", lambda: True)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    source = tmp_path / "source.bin"
    source.write_bytes(b"x")
    bad = (studio_setup.Download("onnx/vocoder.onnx", source.as_uri(), "ab" * 32, 1),)
    monkeypatch.setattr(supertonic_module, "FILES", bad)
    monkeypatch.setattr(vieneu_module, "_g2p_external", lambda: True)
    music_module.configure(tmp_path / "music")
    supertonic_module.configure(tmp_path / "supertonic")
    vieneu_module.configure(tmp_path / "vieneu")
    try:
        supertonic_module.start(["supertonic"])
        supertonic_module.join(30)
        status = supertonic_module.status()
        assert status["state"] == "error" and "Không tải được giọng Supertonic" in status["error"] and "ghim" in status["error"]
        assert not (tmp_path / "supertonic" / "model" / "onnx" / "vocoder.onnx").exists()
        assert supertonic_module.installed() is None
    finally:
        supertonic_module.configure(None)
        vieneu_module.configure(None)
        music_module.configure(None)


def test_downloads_off_says_why(module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(supertonic_module.ENV_DOWNLOAD, "0")
    supertonic_module.start(["supertonic"])
    status = supertonic_module.status()
    assert status["state"] == "error" and "tắt" in status["error"]
    with pytest.raises(ValueError):
        supertonic_module.start(["khác"])


def test_the_server_shows_starts_and_removes_the_module(studio) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    status, view = _call(server, "GET", "/api/readaloud/supertonic")
    assert status == 200 and [choice["id"] for choice in view["choices"]] == ["supertonic"] and view["state"] == "missing"
    status, view = _call(server, "POST", "/api/readaloud/supertonic", {"choices": ["supertonic"]})
    assert status == 200 and view["state"] == "error", "bài thử tắt việc tải (conftest)"
    status, _ = _call(server, "POST", "/api/readaloud/supertonic", {"choices": "supertonic"})
    assert status == 400
    status, _ = _call(server, "POST", "/api/readaloud/supertonic", {"choices": ["khác"]})
    assert status == 400
    status, view = _call(server, "POST", "/api/readaloud/supertonic/remove", {})
    assert status == 200 and view["state"] != "downloading"
    status, view = _call(server, "POST", "/api/readaloud/supertonic/measure", {})
    assert status == 200
    assert app.readaloud.supertonic is not None and "supertonic" in app.readaloud.providers
    status, voices = _call(server, "GET", "/api/readaloud/voices")
    assert status == 200 and not [voice for voice in voices if voice["provider"] == "supertonic"], "chưa tải: không có giọng"


# ---- model thật (máy dev) ---------------------------------------------------------------------------------------------------------
def _model_folder() -> Path:
    home = Path.home() / ".cache" / "supertonic3"
    for folder in (home, supertonic_module._model_dir()):
        if folder is not None and (folder / supertonic.CONFIG_FILE).is_file() and (folder / "onnx" / "vocoder.onnx").is_file():
            return folder
    pytest.skip("máy chưa có model Supertonic 3 (~/.cache/supertonic3 hay mô-đun đã tải)")


def test_the_real_model_reads_a_sentence_with_the_pinned_sample_rate() -> None:
    folder = _model_folder()
    engine = SupertonicEngine(folder)
    assert engine.SAMPLE_RATE == supertonic.SAMPLE_RATE
    wave_data = engine.infer("Xin chào, đây là một câu thử.", "F1", np.random.RandomState(1))
    assert 0.8 < len(wave_data) / engine.SAMPLE_RATE < 3.0 and float(np.abs(wave_data).max()) > 0.05
    again = engine.infer("Xin chào, đây là một câu thử.", "F1", np.random.RandomState(1))
    assert np.array_equal(wave_data, again), "cùng hạt giống thì cùng audio"


def test_parity_with_the_vendor_package(monkeypatch: pytest.MonkeyPatch) -> None:
    reference = pytest.importorskip("supertonic")
    from abook.readaloud import vieneu_engine

    folder = _model_folder()
    monkeypatch.setattr(vieneu_engine, "trim_and_fade", lambda wave_data, _rate: wave_data)  # hãng không cắt im lặng
    tts = reference.TTS(model="supertonic-3", intra_op_num_threads=4)
    engine = SupertonicEngine(folder, 4)
    for index, text in enumerate(["Xin chào, đây là một câu thử nghiệm của tôi.", "Anh ấy về nhà rất muộn hôm ấy, mệt lả người."]):
        np.random.seed(7 + index)
        expected, _ = tts.synthesize(text, voice_style=tts.get_voice_style("M4"), lang="vi", speed=supertonic.SPEED, total_steps=supertonic.STEPS)
        got = engine.infer(text, "M4", np.random.RandomState(7 + index))
        expected = np.asarray(expected).reshape(-1)[:len(got)]
        assert len(expected) == len(got) and float(np.abs(expected - got).max()) <= 1e-5, text


def test_clips_are_raised_to_the_shared_loudness_without_clipping() -> None:
    import numpy as np

    quiet = np.full(100, 0.1, dtype=np.float32)
    assert np.allclose(supertonic.louder(quiet), 0.1 * 10 ** (supertonic.GAIN_DB / 20))
    loud = np.array([0.0, 0.95, -0.5], dtype=np.float32)
    assert np.max(np.abs(supertonic.louder(loud))) <= max(0.95, supertonic.PEAK_CEILING) + 1e-6, "đỉnh cao thì không nâng quá trần"
    assert supertonic.louder(np.zeros(0, dtype=np.float32)).size == 0


def test_short_lines_are_read_slower_so_they_are_not_swallowed() -> None:
    assert supertonic.speed_for("về rồi?") == supertonic.SHORT_SPEED
    assert supertonic.speed_for("sao cô biết?") == supertonic.SHORT_SPEED
    long_line = "gió đêm lùa qua khung cửa sổ mang theo mùi mưa và tiếng chuông xa xa"
    assert supertonic.speed_for(long_line) == supertonic.SPEED
    middle = supertonic.speed_for("cậu định đứng đó nhìn tớ mãi à")
    assert supertonic.SHORT_SPEED < middle < supertonic.SPEED


# ---- tên và từ nước ngoài (names.spoken_names): Supertonic không nói được âm Anh --------------------------------------------------------------
def test_english_and_japanese_names_reach_the_model_as_syllables(fake_voices) -> None:
    provider, engine = fake_voices
    provider.speaks_english = False  # đường Việt hoá (Supertonic chưa quyết, mặc định giữ chữ Anh)
    provider.synthesize("Tôi gặp Rose và Mike.", "F1")
    provider.synthesize("Kyouko và Haruto đi học.", "F1", "ja")
    provider.synthesize("Kyouko và Haruto đi học.", "F1")
    rose = english_vi.vietnamized_english("Rose").lower()
    assert [text for _, text in engine.calls] == [f"tôi gặp {rose} và mi-ke.", "ki-âu-cô và ha-ru-tô đi học.",
                                                  f"{english_vi.vietnamized_english('Kyouko').lower()} và {english_vi.vietnamized_english('Haruto').lower()} đi học."]


def test_the_clip_key_follows_the_reading(fake_voices, tmp_path: Path) -> None:
    provider, engine = fake_voices
    provider.speaks_english = False
    service = ReadAloud(tmp_path / "cache", [provider])
    plain = service.clip("supertonic:F1", "Tôi về nhà.", origin="ja")
    assert service.clip("supertonic:F1", "Tôi về nhà.") == plain, "không từ nước ngoài nào: chung clip, có hay không có gốc"
    english = service.clip("supertonic:F1", "Tôi gặp Rose.")
    count = len(engine.calls)
    assert service.clip("supertonic:F1", "Tôi gặp Rose.", origin="ja") == english and len(engine.calls) == count, "gốc không làm đoạn này nghe khác"
    named = service.clip("supertonic:F1", "Kyouko gặp Rose.", origin="ja")
    assert named["file"] != service.clip("supertonic:F1", "Kyouko gặp Rose.")["file"], "gốc làm tên đổi: clip riêng"
    assert service.clip("supertonic:F1", "Kyouko gặp Rose.", origin="ja", cached_only=True) == named
    provider.speaks_english = True  # cùng đoạn, giọng khác cách đọc: khoá phải khác
    assert service.clip("supertonic:F1", "Tôi gặp Rose.")["file"] != english["file"]


def test_the_books_own_readings_come_after_the_names(fake_voices, tmp_path: Path) -> None:
    """"Đọc từ này là…" (readings.py) như VieNeu: áp sau bước đọc tên nên thắng luật phiên âm; khoá có gốc cuốn lẫn dấu cách đọc. Bản điện thoại:
    SupertonicSpeakerTest + bộ ví dụ chung tests/fixtures/book_edits/readings/speech.json."""
    provider, engine = fake_voices
    service = ReadAloud(tmp_path / "cache", [provider])
    text = "Haruto gặp Kyouko."
    table = {"Haruto": "Ha-ru-to"}
    clip = service.clip("supertonic:F1", text, origin="ja", readings=table)
    assert engine.calls[-1] == ("F1", "ha-ru-to gặp ki-âu-cô."), "cách đọc của người nghe thắng luật phiên âm, tên khác vẫn theo gốc cuốn"
    assert len(clip["words"]) == len(text.split())
    tag = f"{provider.reading_tag(text, 'ja')}+{readings.tag(text, table)}"
    assert tag.startswith("ja+r") and clip["file"].startswith(cache.clip_key("supertonic", "F1", text, tag))
    assert service.clip("supertonic:F1", text, origin="ja")["file"] != clip["file"], "bỏ cách đọc: clip khác"
