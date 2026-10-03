"""Giọng VieNeu cho "Nghe ngay": chia đoạn thành khúc, bộ tách từ BPE, giọng với engine giả (clip + mốc chữ), mô-đun tải (ghim, phần dùng chung,
phần cũ, khuyên dùng, tự đo, đề nghị đổi) và đường máy chủ. Không chạm mạng: studio_setup.download là bản giả.

Bài so với gói vieneu 3.8.1 (`parity`) chỉ chạy khi máy có gói vieneu + model trong bộ đệm Hugging Face (máy dev): cùng phoneme -> cùng mã, cùng
sóng âm. Sai số cho phép 1e-5 (đo 03-10 trên máy dev: 0,0 - từng mẫu trùng nhau, vì cả hai bên gọi cùng đồ thị onnxruntime với cùng đầu vào và bốc
mẫu bằng cùng phép tính); máy khác CPU vẫn phải trùng vì hai bên chạy trên cùng một máy.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
import wave
import zipfile
from pathlib import Path

import numpy as np
import pytest

from abook.readaloud import vieneu, vieneu_engine
from abook.readaloud.service import ReadAloud
from abook.readaloud.vieneu import Installed, VieneuProvider, units
from abook.webui import music_module, studio_setup, vieneu_module, word_timing
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


# ---- chia đoạn ---------------------------------------------------------------------------------------------------------------------
def _cover(text: str, max_chars: int) -> list[str]:
    toks, parts = units(text, max_chars)
    assert [i for unit in parts for i in range(unit.first, unit.last + 1)] == list(range(len(toks))), "mỗi chữ hiện thuộc đúng một khúc"
    return [unit.text(toks) for unit in parts]


def test_sentences_are_packed_into_units_up_to_the_limit() -> None:
    text = "Trời hôm nay đẹp quá. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi. Anh ấy về nhà rất muộn hôm ấy."
    assert _cover(text, 256) == [text]
    assert _cover(text, 50) == ["Trời hôm nay đẹp quá.", "Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi.", "Anh ấy về nhà rất muộn hôm ấy."]


def test_a_long_sentence_is_cut_at_commas_then_at_spaces() -> None:
    text = "Một hai ba bốn năm, sáu bảy tám chín mười, mười một mười hai mười ba mười bốn mười lăm mười sáu mười bảy."
    pieces = _cover(text, 40)
    assert pieces[0] == "Một hai ba bốn năm, sáu bảy tám chín mười,"
    assert all(len(piece) <= 40 + vieneu.MIN_UNIT_CHARS + 1 for piece in pieces), "gộp khúc ngắn được vượt trần chút ít, như vieneu"
    assert len(pieces) >= 3


def test_a_short_unit_joins_its_shorter_neighbour() -> None:
    assert _cover("Ừ. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi suốt cả buổi chiều hôm ấy.", 40) == \
        ["Ừ. Cô gái đứng bên cửa sổ,", "lặng lẽ nhìn mưa rơi suốt cả buổi chiều hôm ấy."]
    _toks, parts = units("Ừ. Được.", 256)
    assert len(parts) == 1


# ---- số La Mã sau danh từ chung (biến đổi để đọc: chữ hiện giữ nguyên, chữ đem đọc đổi) ----------------------------------------------
def _said(text: str) -> str:
    toks, parts = units(text, 256)
    assert " ".join(unit.text(toks) for unit in parts) == " ".join(toks), "chữ hiện không đổi"
    return " ".join(piece for unit in parts for piece in unit.pieces)


@pytest.mark.parametrize("text, said", [
    ("Trường Phổ thông II và Trường Phổ thông III", "Trường Phổ thông hai và Trường Phổ thông ba"),
    ("Chương IV bắt đầu ở trang 132.", "Chương bốn bắt đầu ở trang 132."),
    ("Thế chiến II kết thúc năm 1945.", "Thế chiến hai kết thúc năm 1945."),
    ("Benedict III lên ngôi.", "Benedict ba lên ngôi."),
    ("Cuối chương XIV.", "Cuối chương mười bốn."),
    ("Mục XV, XXIV và XXXIX.", "Mục mười lăm, hai mươi bốn và ba mươi chín."),
    ("Học kỳ \"II\" bắt đầu.", "Học kỳ \"hai\" bắt đầu."),
    # số MỘT chữ (I, V, X) chỉ đọc thành số sau danh từ đánh số, hay hai tên riêng viết hoa liền nhau
    ("Chương I, thế kỷ X, thế chiến I và Phần V.", "Chương một, thế kỷ mười, thế chiến một và Phần năm."),
    ("Lớp V, hạng X, số I, bài V.", "Lớp năm, hạng mười, số một, bài năm."),
    ("Mục II, V và X.", "Mục hai, năm và X."),
    ("Vua Louis X lên ngôi.", "Vua Louis mười lên ngôi."),
])
def test_a_roman_numeral_after_a_word_is_read_as_a_number(text: str, said: str) -> None:
    assert _said(text) == said


@pytest.mark.parametrize("text, said", [
    ("I. Mở đầu", "một. Mở đầu"),  # đề mục đầu đoạn
    ("IX) Phụ lục", "chín) Phụ lục"),
    ("I am here.", "I am here."),  # chữ "I" đứng đầu câu, không có dấu chấm đề mục
    ("I.", "I."),
    ("Xong rồi. I am đây.", "Xong rồi. I am đây."),  # sau dấu câu là câu mới
    ("Anh ấy là MC của CV VIP, ở DIV.", "Anh ấy là MC của CV VIP, ở DIV."),  # viết tắt
    ("Mã XL và IIII và VX.", "Mã XL và IIII và VX."),  # không phải số La Mã hợp lệ / ngoài I..XXXIX
    ("Chương iv và Chương Iv.", "Chương iv và Chương Iv."),  # chỉ chữ HOA
    ("Khoa CV II", "Khoa CV II"),  # sau viết tắt (không có chữ thường) thì để nguyên
    # số MỘT chữ sau từ thường khác là chữ cái, không phải số
    ("Ông X, nhân vật X, tia X, điểm V, loại I.", "Ông X, nhân vật X, tia X, điểm V, loại I."),
    ("Ông ta nói rằng I", "Ông ta nói rằng I"),
    ("Hoàng đế Napoleon I và Napoleon I.", "Hoàng đế Napoleon I và Napoleon I."),  # tên riêng đứng sau từ thường / đầu đoạn
    ("Trường Phổ thông I", "Trường Phổ thông I"),
])
def test_other_capitals_and_headings_are_left_alone(text: str, said: str) -> None:
    assert _said(text) == said


def test_roman_numbers_read_as_vietnamese() -> None:
    assert [vieneu.vietnamese_number(n) for n in (1, 4, 5, 10, 11, 14, 15, 20, 21, 24, 25, 30, 31, 35, 39)] == [
        "một", "bốn", "năm", "mười", "mười một", "mười bốn", "mười lăm", "hai mươi", "hai mươi mốt", "hai mươi bốn", "hai mươi lăm",
        "ba mươi", "ba mươi mốt", "ba mươi lăm", "ba mươi chín"]
    assert [vieneu.roman_value(r) for r in ("I", "IV", "IX", "XIV", "XXXIX", "XL", "IIII", "VX", "")] == [1, 4, 9, 14, 39, None, None, None, None]


def test_resample_keeps_length_and_a_low_tone() -> None:
    rate = 48_000
    t = np.arange(rate) / rate
    tone = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    out = vieneu.resample(tone, rate)
    assert out.shape == (16_000,)
    reference = np.sin(2 * np.pi * 440 * np.arange(16_000) / 16_000)
    assert float(np.abs(out[100:-100] - reference[100:-100]).max()) < 1e-3


# ---- engine: phần thuần numpy -------------------------------------------------------------------------------------------------------
def test_frame_cap_follows_syllables_for_short_chunks() -> None:
    assert vieneu_engine.phoneme_syllables("tʃˈəː2j hˈom nˈaj.") == 3
    assert vieneu_engine.max_expected_frames("ˈy2.") == 13
    assert vieneu_engine.max_expected_frames("tʃˈəː2j hˈom.") == 18
    long = "kˈo ɣˈaːɜj ɗˈyɜŋ bˈen kˈyə4 sˈo4, lˈa6ŋ lˈɛ4 ɲˈi2n mˈyə zˈəːj."
    assert vieneu_engine.max_expected_frames(long) == 24 + 2 * len(long)


def test_join_pads_to_the_minimum_pause_and_reports_spans() -> None:
    rate = 1000
    loud = np.ones(100, dtype=np.float32) * 0.5
    joined, spans = vieneu_engine.join([loud, loud], rate, [0.3])
    assert spans == [(0, 100), (400, 500)] and joined.shape == (500,)


def test_byte_bpe_merges_by_rank_and_splits_special_tokens(tmp_path: Path) -> None:
    letters = {chr(c): i for i, c in enumerate(range(ord("a"), ord("z") + 1), start=10)}
    spec = {
        "normalizer": {"type": "NFC"},
        "added_tokens": [{"id": 1, "content": "<|x|>"}],
        "model": {"type": "BPE", "unk_token": "<unk>", "vocab": {"<unk>": 0, "<|x|>": 1, "Ġ": 2, "ab": 3, "abc": 4, "Ġa": 5, **letters},
                  "merges": ["a b", "ab c", "Ġ a"]},
    }
    path = tmp_path / "tokenizer.json"
    path.write_bytes(json.dumps(spec).encode())
    bpe = vieneu_engine.ByteBPE(path)
    assert bpe.encode("abc") == [4]
    assert bpe.encode("abc a") == [4, 5], "dấu cách dính vào chữ sau (Ġ), rồi ghép theo thứ hạng"
    assert bpe.encode("ab<|x|>c") == [3, 1, letters["c"]]
    assert bpe.encode("ă") == [0, 0], "byte không có trong từ điển -> unk, mỗi byte một lần"


# ---- giọng với engine giả -----------------------------------------------------------------------------------------------------------
class FakeEngine:
    """Mỗi khúc: một tiếng "bíp" dài theo số chữ, 50 ms im lặng hai đầu."""

    def __init__(self, rate: int) -> None:
        self.SAMPLE_RATE = rate
        self.calls: list[str] = []

    def infer(self, phonemes: str, *_args, **_kwargs) -> np.ndarray:
        self.calls.append(phonemes)
        words = max(1, len(phonemes.split()))
        quiet = np.zeros(int(0.05 * self.SAMPLE_RATE), dtype=np.float32)
        body = 0.3 * np.sin(np.arange(int(0.25 * words * self.SAMPLE_RATE)) / 3).astype(np.float32)
        return np.concatenate([quiet, body, quiet])


def _voices(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    turbo = {"presets": {"Thường": {"speaker_emb": [0.1] * 4, "codes": [[1] * 16], "gender": "male"},
                         "Chọn": {"featured": 1, "speaker_emb": [0.2] * 4, "gender": "female"}}}
    nano = {"presets": {"Nhẹ": {"speaker_emb": [0.1] * 4, "style": [[0.0] * 4]}}}
    (folder / "voices_v3_turbo.json").write_bytes(json.dumps(turbo).encode())
    (folder / "voices_v3_nano.json").write_bytes(json.dumps(nano).encode())
    return folder


@pytest.fixture
def fake_voices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vieneu_engine, "phonemize", lambda pieces: " ".join(pieces).lower().rstrip(".!?,") + ".")
    found = Installed(_voices(tmp_path / "voices"), (tmp_path, tmp_path), tmp_path, False)
    engines = {"turbo": FakeEngine(48_000), "nano": FakeEngine(24_000)}
    provider = VieneuProvider(lambda: found, engines=lambda tier, _found: engines[tier], aligner=lambda: None)
    return provider, engines


def test_voices_list_both_tiers_featured_first(fake_voices) -> None:
    provider, _ = fake_voices
    voices = provider.voices()
    assert [voice.id for voice in voices] == ["vieneu:turbo/Chọn", "vieneu:turbo/Thường", "vieneu:nano/Nhẹ"]
    assert all(not voice.online and not voice.default for voice in voices)
    assert voices[2].name == "Nhẹ (VieNeu Nano)"
    assert [voice.gender for voice in voices] == ["female", "male", ""], "nam / nữ lấy từ danh sách giọng; không ghi thì để trống"


def test_a_clip_has_one_timing_per_word_inside_its_unit(fake_voices, tmp_path: Path) -> None:
    provider, engines = fake_voices
    service = ReadAloud(tmp_path / "cache", [provider])
    text = "Khi ánh đèn vụt tắt, cả nhà chìm vào bóng tối. Chỉ còn tiếng đồng hồ - đều đặn!"
    clip = service.clip("vieneu:turbo/Thường", text)
    words = clip["words"]
    assert len(words) == len(text.split())
    assert all(a <= b for a, b in words) and all(words[i][0] <= words[i + 1][0] for i in range(len(words) - 1))
    assert words[-1][1] <= clip["duration_ms"]
    with wave.open(io.BytesIO((tmp_path / "cache" / clip["file"]).read_bytes())) as handle:
        assert handle.getframerate() == 48_000 and handle.getnchannels() == 1
    assert len(engines["turbo"].calls) == 1, "cả đoạn vừa một khúc"
    again = service.clip("vieneu:turbo/Thường", text)
    assert again == clip and len(engines["turbo"].calls) == 1, "lần sau lấy bộ đệm"


def test_units_get_the_pause_vieneu_puts_between_chunks(fake_voices) -> None:
    provider, _ = fake_voices
    found = provider.locate()
    preset = provider.presets("nano", found)["Nhẹ"]
    text = "Câu đầu tiên dài vừa đủ một khúc. " * 6
    audio, rate, _toks, parts, spans = provider._speak("nano", "Nhẹ", found, preset, text.strip())
    assert len(parts) > 1 and rate == 24_000
    for (_a, stop), (start, _b) in zip(spans, spans[1:]):
        assert start - stop >= int(0.5 * rate) - 2 * int(0.05 * rate), "nghỉ tối thiểu 0,5 giây sau câu (tính cả im lặng sẵn có)"


def test_an_unknown_or_missing_voice_says_so(fake_voices) -> None:
    provider, _ = fake_voices
    with pytest.raises(vieneu.VoiceError) as error:
        provider.synthesize("Xin chào.", "turbo/Không có")
    assert error.value.reason == "voice"
    gone = VieneuProvider(lambda: None)
    assert gone.voices() == []


def test_benchmark_reports_speed(fake_voices) -> None:
    provider, _ = fake_voices
    result = provider.benchmark("nano")
    assert result["audioSeconds"] > 1 and result["rtf"] >= 0 and result["firstAudioMs"] >= 0


# ---- mô-đun tải --------------------------------------------------------------------------------------------------------------------
class Network:
    """Hugging Face / PyPI giả: wheel sea-g2p có gói sea_g2p, wheel vieneu có hai file giọng; file model ghi nội dung giả. Đếm từng lần tải."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(self, item, target: Path, progress, cancelled) -> Path:
        self.calls.append(item.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.name == "sea-g2p":
            with zipfile.ZipFile(target, "w") as bundle:
                bundle.writestr("sea_g2p/__init__.py", "")
        elif item.name == "vieneu":
            with zipfile.ZipFile(target, "w") as bundle:
                for member in vieneu_module.VOICE_MEMBERS:
                    bundle.writestr(member, json.dumps({"presets": {"A": {"speaker_emb": [0.1]}}}))
        elif str(target).endswith(".whl"):
            with zipfile.ZipFile(target, "w") as bundle:
                bundle.writestr(f"{item.name}/__init__.py", "")
        else:
            target.write_bytes(item.sha256.encode())
        progress(item.size, item.size)
        return target


@pytest.fixture
def module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "path", sys.path.copy())  # sea_g2p giả của bài thử không được lọt sang bài khác
    monkeypatch.setenv(vieneu_module.ENV_DOWNLOAD, "1")
    monkeypatch.setenv(music_module.ENV_DOWNLOAD, "1")
    monkeypatch.delenv(word_timing.ENV_DIR, raising=False)
    monkeypatch.delenv(word_timing.ENV_RUNTIME, raising=False)
    monkeypatch.setattr(word_timing, "_more", [])
    monkeypatch.setattr(word_timing, "_studio", None)
    monkeypatch.setattr(word_timing, "model_dir", lambda: next((d for d in word_timing._more if word_timing._complete(d)), None))
    monkeypatch.setattr(vieneu_module, "_g2p_external", lambda: False)
    monkeypatch.setattr(music_module, "_libs_external", lambda: True)
    monkeypatch.setattr(vieneu_module, "_facts", {"cores": 16, "ramGb": 16.0, "gpu": "", "runs": "cpu"})
    network = Network()
    monkeypatch.setattr(studio_setup, "download", network.download)
    music_module.configure(tmp_path / "music")
    measured: list[str] = []

    def bench(tier: str) -> dict:
        measured.append(tier)
        return {"rtf": 1.2 if tier == "turbo" else 0.3, "firstAudioMs": 900, "loadMs": 1000, "audioSeconds": 5.0}

    vieneu_module.configure(tmp_path / "vieneu", benchmark=bench)
    yield network, measured, tmp_path / "vieneu"
    vieneu_module.join(10)
    vieneu_module.configure(None)
    music_module.configure(None)
    importlib.invalidate_caches()


def _sizes(files) -> int:
    return sum(item.size for item in files)


def test_sizes_count_only_what_this_machine_lacks(module) -> None:
    status = vieneu_module.status()
    assert status["state"] == "missing"
    by_id = {choice["id"]: choice for choice in status["choices"]}
    shared = vieneu_module.G2P.size + vieneu_module.VOICES.size
    assert by_id["turbo"]["bytes"] == shared + _sizes(vieneu_module.TURBO_FILES), "thư viện máy đã có: không tính"
    assert by_id["nano"]["bytes"] == shared + _sizes(vieneu_module.NANO_FILES)
    assert by_id["aligner"]["bytes"] == _sizes(studio_setup.WORD_ALIGN_FILES)
    assert by_id["turbo"]["recommended"] and not by_id["nano"]["recommended"] and by_id["aligner"]["default"]


def test_shared_parts_download_once_and_the_stamp_records_pins(module) -> None:
    network, measured, folder = module
    vieneu_module.start(["turbo", "nano"])
    vieneu_module.join(10)
    assert network.calls.count("sea-g2p") == 1 and network.calls.count("vieneu") == 1
    assert network.calls.count("config.json") == 2, "config.json của Turbo và của Nano là hai file khác nhau"
    status = vieneu_module.status()
    assert status["state"] == "ready" and status["error"] == ""
    assert all(choice["bytes"] == 0 for choice in status["choices"] if choice["id"] != "aligner")
    stamp = json.loads((folder / "module.json").read_bytes())
    assert stamp["pins"]["nano"] == vieneu_module.pin(vieneu_module.NANO_FILES)
    assert sorted(measured) == ["nano", "turbo"], "tải xong tự đo cả hai giọng"
    assert status["benchmark"]["turbo"]["rtf"] == 1.2
    assert status["suggestion"] == {"tier": "turbo", "rtf": 1.2, "switchTo": "nano", "installed": True}
    found = vieneu_module.installed()
    assert found is not None and found.turbo == (folder / "turbo", folder / "turbo") and found.nano == folder / "nano"
    assert (folder / "voices" / "voices_v3_turbo.json").is_file() and (folder / "lib" / "sea_g2p").is_dir()


def test_a_changed_pin_updates_only_that_part(module, monkeypatch: pytest.MonkeyPatch) -> None:
    network, _measured, _folder = module
    vieneu_module.start(["nano"])
    vieneu_module.join(10)
    network.calls.clear()
    changed = tuple(studio_setup.Download(item.name, item.url, ("0" * 64) if item.name == "config.json" else item.sha256, item.size)
                    for item in vieneu_module.NANO_FILES)
    monkeypatch.setattr(vieneu_module, "NANO_FILES", changed)
    monkeypatch.setitem(vieneu_module.FILES, "nano", changed)
    status = vieneu_module.status()
    assert status["state"] == "outdated" and status["outdatedParts"] == ["Giọng VieNeu Nano"]
    assert status["outdatedBytes"] == _sizes(changed)
    vieneu_module.start(None)
    vieneu_module.join(10)
    assert sorted(set(network.calls)) == sorted(item.name for item in changed), "chỉ phần đổi ghim"
    assert vieneu_module.status()["state"] == "ready"


def test_downloads_off_says_why(module, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(vieneu_module.ENV_DOWNLOAD, "0")
    vieneu_module.start(["nano"])
    status = vieneu_module.status()
    assert status["state"] == "error" and "tắt" in status["error"]
    with pytest.raises(ValueError):
        vieneu_module.start(["khác"])


def test_recommendation_and_suggestion_rules() -> None:
    assert vieneu_module.recommend({"cores": 16, "ramGb": 16}) == "turbo"
    assert vieneu_module.recommend({"cores": 16, "ramGb": 0}) == "turbo", "không đọc được RAM: theo số lõi"
    assert vieneu_module.recommend({"cores": 4, "ramGb": 16}) == "nano"
    assert vieneu_module.recommend({"cores": 8, "ramGb": 4}) == "nano"
    fast = {"turbo": {"rtf": 0.3}, "nano": {"rtf": 0.3}}
    assert vieneu_module.suggestion(fast, ["turbo", "nano"]) is None
    assert vieneu_module.suggestion({"turbo": {"rtf": 0.9}}, ["turbo"]) == {"tier": "turbo", "rtf": 0.9, "switchTo": "nano", "installed": False}
    assert vieneu_module.suggestion({"nano": {"rtf": 1.5}}, ["nano"]) == {"tier": "nano", "rtf": 1.5, "switchTo": "online", "installed": True}
    both = {"turbo": {"rtf": 1.1}, "nano": {"rtf": 0.9}}
    assert vieneu_module.suggestion(both, ["turbo", "nano"])["switchTo"] == "online"


def test_the_server_shows_and_starts_the_module(studio, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    status, view = _call(server, "GET", "/api/readaloud/vieneu")
    assert status == 200 and {choice["id"] for choice in view["choices"]} == {"turbo", "nano", "aligner"}
    status, view = _call(server, "POST", "/api/readaloud/vieneu", {"choices": ["nano"]})
    assert status == 200 and view["state"] == "error", "bài thử tắt việc tải (conftest)"
    status, answer = _call(server, "POST", "/api/readaloud/vieneu", {"choices": "nano"})
    assert status == 400
    assert app.readaloud.vieneu is not None and "vieneu" in app.readaloud.providers


# ---- so với gói vieneu 3.8.1 (máy dev) --------------------------------------------------------------------------------------------
def _cached(repo: str, revision: str, patterns: list[str]) -> Path | None:
    """Model trong bộ đệm Hugging Face: của runtime (abook đặt HF_HUB_CACHE) hay của người dùng (~/.cache, nơi gói vieneu tự tải về)."""
    import os

    from huggingface_hub import snapshot_download

    for cache in (os.environ.get("HF_HUB_CACHE"), str(Path.home() / ".cache" / "huggingface" / "hub")):
        try:
            found = Path(snapshot_download(repo, revision=revision, allow_patterns=patterns, local_files_only=True, cache_dir=cache))
        except Exception:  # noqa: BLE001 - không có ở chỗ này: thử chỗ kế
            continue
        if any(path.is_file() for path in found.rglob("*.onnx")):  # bộ đệm dở (chỉ có refs) trả về thư mục rỗng
            return found
    return None


def _parity_dirs():
    import importlib.util

    if importlib.util.find_spec("vieneu") is None or importlib.util.find_spec("sea_g2p") is None:
        pytest.skip("máy không có gói vieneu")
    turbo = _cached("pnnbao-ump/VieNeu-TTS-v3-Turbo", "61b85e3d937fbbacb387714180e8182823512523", ["onnx_int8/*"])
    codec = _cached("OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX", "ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae", ["moss_audio_tokenizer_decode_*"])
    nano = _cached("pnnbao-ump/VieNeu-TTS-v3-Nano", "aba295eb96a6fa6003ebe417cc1f2802a7adc1dc", ["*"])
    if turbo is None or codec is None or nano is None:
        pytest.skip("model VieNeu chưa có trong bộ đệm Hugging Face")
    return turbo / "onnx_int8", codec, nano


SENTENCES = ["Trời hôm nay đẹp quá.", "Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi.", "Năm 2024, giá 100$ tăng 5%.", "Ừ."]
TOLERANCE = 1e-5


def test_parity_text_front_end_and_tokenizer() -> None:
    turbo, _codec, _nano = _parity_dirs()
    from tokenizers import Tokenizer
    from vieneu_utils.phonemize_text import normalize_to_chunks_v3_with_gaps, phonemize_text_with_emotions

    reference = Tokenizer.from_file(str(turbo / "tokenizer.json"))
    mine = vieneu_engine.ByteBPE(turbo / "tokenizer.json")
    for sentence in SENTENCES + ['"Thế à?" anh hỏi.', "Email: a.b@x.com, web https://abc.vn/x?y=1", "OK, iPhone 15 Pro Max — 30.000.000đ!"]:
        chunk = normalize_to_chunks_v3_with_gaps(sentence, max_chars=256)[0][0]
        phonemes = phonemize_text_with_emotions(chunk)
        assert vieneu_engine.phonemize([sentence]) == phonemes
        assert mine.encode(phonemes) == reference.encode(phonemes, add_special_tokens=False).ids


def test_parity_turbo_and_nano_waveforms(monkeypatch: pytest.MonkeyPatch) -> None:
    turbo, codec, nano = _parity_dirs()
    import vieneu as package
    import vieneu.v3nano as v3nano
    from vieneu._v3_turbo_engine.onnx_runtime_lite import OnnxV3LiteEngine
    from vieneu_utils.core_utils import strip_encoder_pad_frame

    assets = Path(package.__file__).parent / "assets"
    voices = json.loads((assets / "voices_v3_turbo.json").read_bytes())
    preset = voices["presets"][voices["default_voice"]]
    speaker = np.asarray(preset["speaker_emb"], np.float32)
    codes = strip_encoder_pad_frame(np.asarray(preset["codes"], np.int64))
    monkeypatch.setattr(OnnxV3LiteEngine, "_load_denoiser", lambda self: None)  # chỉ cho nhân bản giọng; nạp nó thì vieneu tải 42 MB từ mạng
    reference = OnnxV3LiteEngine(onnx_dir=str(turbo), codec_dir=str(codec), threads=4)
    mine = vieneu_engine.TurboEngine(turbo, codec, threads=4)
    for index, sentence in enumerate(SENTENCES):
        phonemes = vieneu_engine.phonemize([sentence])
        np.random.seed(100 + index)
        expected = reference.infer(phonemes=phonemes, speaker_emb=speaker, ref_codes=codes)
        got = mine.infer(phonemes, speaker, codes, rng=np.random.RandomState(100 + index))
        assert got.shape == expected.shape and float(np.abs(got - expected).max()) <= TOLERANCE, sentence

    voices = json.loads((assets / "voices_v3_nano.json").read_bytes())
    preset = voices["presets"][voices["default_voice"]]
    speaker, style = np.asarray(preset["speaker_emb"], np.float32), np.asarray(preset["style"], np.float32)
    reference = v3nano.OnnxV3NanoEngine(local_dir=str(nano), threads=4)
    mine = vieneu_engine.NanoEngine(nano, threads=4)
    for index, sentence in enumerate(SENTENCES[:2]):
        phonemes = vieneu_engine.phonemize([sentence])
        expected = reference.infer(phonemes, speaker, style, seed=7 + index)
        got = mine.infer(phonemes, speaker, style, seed=7 + index)
        assert got.shape == expected.shape and float(np.abs(got - expected).max()) <= TOLERANCE, sentence


def test_the_shipped_code_does_not_import_vieneu() -> None:
    import re

    for path in (Path(vieneu.__file__), Path(vieneu_engine.__file__), Path(vieneu_module.__file__)):
        assert not re.search(r"^\s*(import|from) vieneu", path.read_bytes().decode("utf-8"), re.M), path.name


# ---- "Làm trước" -------------------------------------------------------------------------------------------------------------------
def test_prepare_takes_only_what_fits_the_cache_share() -> None:
    from abook.readaloud import prepare

    texts = ["a" * 1400] * 10  # 100 giây nghe mỗi đoạn
    assert len(prepare.accept("vieneu:turbo/A", texts, 96_000 * 250)) == 2
    assert len(prepare.accept("vieneu:nano/A", texts, 96_000 * 250)) == 5, "Nano 24 kHz: nửa số byte"
    assert len(prepare.accept("vieneu:turbo/A", texts, 1)) == 1, "luôn nhận ít nhất một đoạn"


def test_prepare_fills_the_cache_and_yields_to_the_listener(fake_voices, tmp_path: Path) -> None:
    provider, engines = fake_voices
    service = ReadAloud(tmp_path / "cache", [provider], rtf=lambda _voice: 0.5)
    texts = [f"Đoạn số {n} của chương sau, đủ dài để thành một khúc." for n in range(4)]
    service._live = 1  # người nghe đang chờ một clip: việc nền đứng yên
    status = service.prepare.start("vieneu:nano/Nhẹ", texts, "Chương 2")
    assert status["state"] == "running" and status["total"] == 4 and status["secondsLeft"] == round(sum(map(len, texts)) / 14 * 0.5)
    import time

    time.sleep(0.5)
    assert service.prepare.status()["done"] == 0 and not engines["nano"].calls
    service._live = 0
    service.prepare.join(10)
    done = service.prepare.status()
    assert done["state"] == "done" and done["done"] == 4 and len(engines["nano"].calls) == 4
    for text in texts:
        service.clip("vieneu:nano/Nhẹ", text, cached_only=True)  # đã nằm sẵn trong bộ đệm
    service.prepare.start("vieneu:nano/Nhẹ", texts * 50, "")
    service.prepare.cancel()
    assert service.prepare.status()["state"] in ("cancelled", "done")


def test_the_server_starts_and_stops_preparing(studio) -> None:  # noqa: F811
    _paths, _app, server, _runner = studio
    status, answer = _call(server, "POST", "/api/readaloud/prepare", {"voice": "vieneu:turbo/Không", "texts": ["Xin chào."]})
    assert status == 400, "giọng chưa có trên máy"
    status, answer = _call(server, "GET", "/api/readaloud/prepare")
    assert status == 200 and answer["state"] == "idle"
    status, answer = _call(server, "DELETE", "/api/readaloud/prepare")
    assert status == 200
