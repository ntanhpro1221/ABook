""""Tốc độ giọng trên máy" (webui/voice_speed.py): Tự động theo lần tự đo, lựa chọn của người dùng luôn thắng, file bậc "Nhanh hơn" chỉ tải khi bậc ấy
được chọn (và kiểm SHA-256 như mọi phần), Nghe ngay đọc bậc nhanh với dấu riêng trong khoá bộ đệm, việc xuất luôn đọc bậc chất lượng. Không chạm mạng:
studio_setup.download là bản giả (trừ bài kiểm băm sai, tải từ file cục bộ); engine giả hay phiên onnxruntime giả.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from abook.readaloud import cache, supertonic, vieneu_engine, vieneu_gguf
from abook.readaloud.model import VoiceError
from abook.readaloud.service import ReadAloud
from abook.readaloud.supertonic import Installed, SupertonicEngine, SupertonicProvider
from abook.webui import music_module, studio_setup, supertonic_module, vieneu_module, voice_speed, word_timing
from tests.test_readaloud_supertonic import FakeEngine
from tests.test_readaloud_vieneu import Network


# ---- luật chọn bậc ---------------------------------------------------------------------------------------------------------------------
def test_auto_follows_the_measured_speed_of_the_quality_tier() -> None:
    assert voice_speed.decide(voice_speed.AUTO, None) == voice_speed.QUALITY, "chưa đo: giữ chất lượng"
    assert voice_speed.decide(voice_speed.AUTO, vieneu_module.SLOW_RTF - 0.01) == voice_speed.QUALITY
    assert voice_speed.decide(voice_speed.AUTO, vieneu_module.SLOW_RTF) == voice_speed.FAST, "máy đọc chậm hơn tốc độ nghe"
    assert voice_speed.decide(voice_speed.AUTO, 2.4) == voice_speed.FAST


def test_an_explicit_choice_always_wins() -> None:
    assert voice_speed.decide(voice_speed.QUALITY, 3.0) == voice_speed.QUALITY, "chọn chất lượng: không bao giờ tự đổi sang nhanh"
    assert voice_speed.decide(voice_speed.FAST, 0.1) == voice_speed.FAST, "chọn nhanh: máy nhanh cũng không đổi"


def test_the_choice_is_one_per_machine_and_kept(tmp_path: Path) -> None:
    voice_speed.configure(None)
    assert voice_speed.choice() == voice_speed.AUTO
    with pytest.raises(ValueError):
        voice_speed.set_choice(voice_speed.FAST)
    voice_speed.configure(tmp_path / voice_speed.FILE)
    try:
        assert voice_speed.choice() == voice_speed.AUTO, "mặc định Tự động"
        voice_speed.set_choice(voice_speed.FAST)
        assert voice_speed.choice() == voice_speed.FAST
        assert json.loads((tmp_path / voice_speed.FILE).read_bytes())["choice"] == "fast"
        with pytest.raises(ValueError):
            voice_speed.set_choice("turbo")
        (tmp_path / voice_speed.FILE).write_bytes(b"{hong")
        assert voice_speed.choice() == voice_speed.AUTO, "file hỏng: về Tự động"
    finally:
        voice_speed.configure(None)


def test_only_supertonic_and_nano_have_two_tiers() -> None:
    assert voice_speed.family("supertonic:F1") == "supertonic" and voice_speed.family("vieneu:nano/Nhẹ") == "nano"
    assert voice_speed.family("vieneu:turbo/A") == "" and voice_speed.family("edge:vi-VN-HoaiMyNeural") == ""
    assert vieneu_engine.NANO_STEPS == 8, "bậc chất lượng của Nano: 8 bước"
    assert vieneu_module.NANO_FAST == ("nano_fast/vector_estimator.onnx", 10) and supertonic.FAST == ("fast/vector_estimator.onnx", 5)


# ---- mô-đun: file bậc nhanh chỉ tải khi cần ----------------------------------------------------------------------------------------------
@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setattr(vieneu_gguf, "unsupported_reason", lambda: "máy thử")
    network = Network()
    monkeypatch.setattr(studio_setup, "download", network.download)
    measured: list[str] = []
    rates = {"supertonic": 0.25, "nano": 0.3, "turbo": 0.3}

    def bench(tier: str) -> dict[str, Any]:
        measured.append(tier)
        return {"rtf": rates[tier], "firstAudioMs": 900, "loadMs": 1000, "audioSeconds": 5.0}

    music_module.configure(tmp_path / "music")
    vieneu_module.configure(tmp_path / "vieneu", benchmark=bench)
    supertonic_module.configure(tmp_path / "supertonic", benchmark=bench)
    voice_speed.configure(tmp_path / voice_speed.FILE)
    yield network, measured, rates, tmp_path
    supertonic_module.join(10)
    vieneu_module.join(10)
    voice_speed.configure(None)
    supertonic_module.configure(None)
    vieneu_module.configure(None)
    music_module.configure(None)
    importlib.invalidate_caches()


FAST_NAME = supertonic_module.FAST_FILES[0].name
REAL_DOWNLOAD = studio_setup.download


def _ids(status: dict[str, Any]) -> list[str]:
    return [choice["id"] for choice in status["choices"]]


def test_the_supertonic_fast_file_is_offered_and_downloaded_only_when_that_tier_is_chosen(env) -> None:
    network, measured, _rates, root = env
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    assert measured == ["supertonic"] and FAST_NAME not in network.calls, "tải giọng không kéo theo bản nhanh hơn"
    assert _ids(supertonic_module.status()) == ["supertonic"], "máy kịp tốc độ nghe: không mời tải bản nhanh hơn"
    assert voice_speed.live_tag("supertonic:F1") == ""
    (line,) = voice_speed.status()["voices"]
    assert line == {"id": "supertonic", "name": "Giọng Supertonic", "module": "supertonic", "fastChoice": "supertonic_fast", "rtf": 0.25,
                    "tier": "quality", "using": "quality", "fastBytes": 81_526_521}

    voice_speed.set_choice(voice_speed.FAST)
    status = supertonic_module.status()
    fast = status["choices"][1]
    assert fast["id"] == "supertonic_fast" and fast["bytes"] == 81_526_521 and not fast["installed"] and fast["requires"] == ["supertonic"]
    assert voice_speed.live_tag("supertonic:F1") == "", "chưa tải bản nhanh hơn: Nghe ngay vẫn đọc bậc chất lượng"
    assert voice_speed.status()["voices"][0] | {} == line | {"tier": "fast"}, "muốn nhanh, đang dùng chất lượng, còn thiếu 82 MB"

    network.calls.clear()
    measured.clear()
    supertonic_module.start(["supertonic_fast"])
    supertonic_module.join(10)
    assert network.calls == [FAST_NAME] and measured == [], "chỉ tải đúng một file; lần tự đo (bậc chất lượng) không chạy lại"
    found = supertonic_module.installed_fast()
    assert found is not None and found.estimator == root / "supertonic" / "fast" / FAST_NAME and found.steps == 5
    assert found.folder == root / "supertonic" / "model"
    stamp = json.loads((root / "supertonic" / "module.json").read_bytes())
    assert stamp["pins"]["supertonic_fast"] == supertonic_module.pin(supertonic_module.FAST_FILES)
    assert voice_speed.live_tag("supertonic:F1") == "fast5" and voice_speed.live_tag("vieneu:turbo/A") == ""
    assert voice_speed.status()["voices"][0]["using"] == "fast" and voice_speed.status()["voices"][0]["fastBytes"] == 0

    voice_speed.set_choice(voice_speed.QUALITY)
    assert voice_speed.live_tag("supertonic:F1") == "", "bạn chọn chất lượng: file nhanh có trên máy cũng không dùng"
    assert supertonic_module.status()["choices"][1]["installed"], "đã tải thì vẫn hiện để gỡ"
    supertonic_module.remove("supertonic_fast")
    assert not (root / "supertonic" / "fast").exists() and supertonic_module.installed() is not None and supertonic_module.installed_fast() is None
    assert _ids(supertonic_module.status()) == ["supertonic"]


def test_auto_offers_the_fast_tier_on_a_slow_machine_and_removing_the_voice_takes_it_along(env) -> None:
    network, _measured, rates, root = env
    rates["supertonic"] = 1.1
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    status = supertonic_module.status()
    assert _ids(status) == ["supertonic", "supertonic_fast"] and status["choices"][1]["default"], "Tự động + máy chậm: mời tải, đánh dấu sẵn"
    line = voice_speed.status()["voices"][0]
    assert line["tier"] == "fast" and line["using"] == "quality" and line["rtf"] == 1.1
    supertonic_module.start(["supertonic_fast"])
    supertonic_module.join(10)
    assert voice_speed.live_tag("supertonic:M4") == "fast5"
    supertonic_module.remove()
    assert not (root / "supertonic" / "model").exists() and not (root / "supertonic" / "fast").exists()
    assert "supertonic_fast" not in json.loads((root / "supertonic" / "module.json").read_bytes())["pins"]
    assert voice_speed.status()["voices"] == [] and voice_speed.live_tag("supertonic:M4") == ""


def test_the_fast_file_must_match_its_pinned_hash(env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    supertonic_module.start(["supertonic"])
    supertonic_module.join(10)
    monkeypatch.setattr(studio_setup, "download", REAL_DOWNLOAD)  # bài này kiểm băm thật, từ file cục bộ
    source = tmp_path / "fast.bin"
    source.write_bytes(b"not the pinned int8 estimator")
    monkeypatch.setattr(supertonic_module, "FAST_FILES", (studio_setup.Download(FAST_NAME, source.as_uri(), "ab" * 32, source.stat().st_size),))
    voice_speed.set_choice(voice_speed.FAST)
    supertonic_module.start(["supertonic_fast"])
    supertonic_module.join(30)
    status = supertonic_module.status()
    assert status["state"] == "error" and "ghim" in status["error"]
    assert not (tmp_path / "supertonic" / "fast" / FAST_NAME).exists() and supertonic_module.installed_fast() is None
    assert voice_speed.live_tag("supertonic:F1") == ""


def test_the_nano_fast_part_and_its_engine(env, monkeypatch: pytest.MonkeyPatch) -> None:
    network, measured, _rates, root = env
    vieneu_module.start(["nano"])
    vieneu_module.join(10)
    assert "nano_fast" not in _ids(vieneu_module.status()) and voice_speed.live_tag("vieneu:nano/A") == ""
    voice_speed.set_choice(voice_speed.FAST)
    choice = {item["id"]: item for item in vieneu_module.status()["choices"]}["nano_fast"]
    assert choice["bytes"] == sum(item.size for item in vieneu_module.NANO_FAST_FILES) and choice["requires"] == ["nano"]
    network.calls.clear()
    measured.clear()
    vieneu_module.start(["nano_fast"])
    vieneu_module.join(10)
    assert sorted(network.calls) == ["LICENSE", "vector_estimator.onnx"] and measured == [], "chỉ file bậc nhanh (+ giấy phép); không đo lại"
    assert (root / "vieneu" / "nano_fast" / "vector_estimator.onnx").is_file()
    assert voice_speed.live_tag("vieneu:nano/A") == f"fast{vieneu_module.NANO_FAST[1]}" and voice_speed.live_tag("vieneu:turbo/A") == ""
    line = {item["id"]: item for item in voice_speed.status()["voices"]}["nano"]
    assert line["name"] == "Giọng VieNeu Nano" and line["using"] == "fast" and line["module"] == "vieneu" and line["fastChoice"] == "nano_fast"

    made: list[dict[str, Any]] = []
    monkeypatch.setattr(vieneu_engine, "NanoEngine", lambda folder, **options: made.append({"folder": folder, **options}) or "nano-engine")
    monkeypatch.setattr(vieneu_module, "make_engine", lambda tier, _found: f"{tier}-engine")
    found = vieneu_module.installed()
    assert found is not None
    assert vieneu_module.make_fast_engine("nano", found) == "nano-engine"
    assert made == [{"folder": root / "vieneu" / "nano", "estimator": root / "vieneu" / "nano_fast" / "vector_estimator.onnx", "steps": vieneu_module.NANO_FAST[1]}]
    assert vieneu_module.make_fast_engine("turbo", found) == "turbo-engine", "Turbo không có bậc nhanh"


# ---- engine: file bộ khử nhiễu + số bước theo bậc ---------------------------------------------------------------------------------------
class _Session:
    def __init__(self, path: Path, runs: list[tuple[str, float]]) -> None:
        self.path, self.runs = path, runs

    def run(self, _outputs: Any, inputs: dict[str, Any]) -> list[Any]:
        name = self.path.stem
        if name == "duration_predictor":
            return [np.array([0.2], dtype=np.float32)]
        if name == "text_encoder":
            return [np.zeros((1, 4, inputs["text_ids"].shape[1]), dtype=np.float32)]
        if name == "vocoder":
            return [np.full((1, 44_100), 0.1, dtype=np.float32)]
        self.runs.append((str(self.path), float(inputs["total_step"][0])))
        return [inputs["noisy_latent"]]


def _model(folder: Path) -> Path:
    (folder / "onnx").mkdir(parents=True)
    (folder / "voice_styles").mkdir()
    config = {"ae": {"sample_rate": 44_100, "base_chunk_size": 512}, "ttl": {"chunk_compress_factor": 6, "latent_dim": 4}}
    (folder / supertonic.CONFIG_FILE).write_bytes(json.dumps(config).encode())
    (folder / supertonic.INDEXER_FILE).write_bytes(json.dumps(list(range(0x2000))).encode())
    style = {"style_ttl": {"data": [0.0] * 4, "dims": [1, 1, 4]}, "style_dp": {"data": [0.0] * 4, "dims": [1, 1, 4]}}
    (folder / supertonic.STYLE_DIR / "F1.json").write_bytes(json.dumps(style).encode())
    return folder


def test_each_tier_reads_its_own_estimator_with_its_own_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[tuple[str, float]] = []
    monkeypatch.setattr(vieneu_engine, "_session", lambda path, _options, _device: _Session(Path(path), runs))
    folder = _model(tmp_path / "model")
    SupertonicEngine(folder, 1).infer("Xin chào.", "F1", np.random.RandomState(1))
    assert {path for path, _ in runs} == {str(folder / "onnx" / "vector_estimator.onnx")} and len(runs) == 8 and runs[0][1] == 8, "chất lượng: 8 bước"
    runs.clear()
    fast = tmp_path / "fast" / "vector_estimator.onnx"
    SupertonicEngine(folder, 1, estimator=fast, steps=supertonic.FAST[1]).infer("Xin chào.", "F1", np.random.RandomState(1))
    assert {path for path, _ in runs} == {str(fast)} and len(runs) == 5 and runs[0][1] == 5, "nhanh hơn: bộ khử nhiễu riêng, 5 bước"
    runs.clear()
    provider = SupertonicProvider(lambda: Installed(folder, False, estimator=fast, steps=5), aligner=lambda: None, normalize=" ".join)
    provider.synthesize("Xin chào.", "F1")
    assert runs and {path for path, _ in runs} == {str(fast)}, "nhà cung cấp dựng engine theo bậc của Installed"


# ---- dịch vụ: Nghe ngay đọc bậc nhanh, xuất luôn bậc chất lượng, khoá bộ đệm theo bậc -------------------------------------------------------
def test_live_listening_reads_the_fast_tier_and_an_export_only_ever_gets_quality(tmp_path: Path) -> None:
    quality, fast = FakeEngine(), FakeEngine()
    found = Installed(tmp_path, False)
    tag = {"now": "fast5"}

    def provider(engine: FakeEngine) -> SupertonicProvider:
        return SupertonicProvider(lambda: found, engines=lambda _found: engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces))

    service = ReadAloud(tmp_path / "cache", [provider(quality)], speed=lambda _voice: tag["now"])
    service.fast[supertonic.PREFIX] = provider(fast)
    text = "Trời hôm nay đẹp quá."
    live = service.clip("supertonic:F1", text)
    assert len(fast.calls) == 1 and quality.calls == [], "Nghe ngay: bậc nhanh"
    assert live["file"].startswith(cache.clip_key("supertonic", "F1", text, "fast5")), "dấu bậc nằm trong khoá"
    with pytest.raises(VoiceError) as error:
        service.clip("supertonic:F1", text, cached_only=True, quality=True)
    assert error.value.reason == "uncached", "clip bậc nhanh không bao giờ đứng thay clip chất lượng"
    exported = service.clip("supertonic:F1", text, quality=True)
    assert len(quality.calls) == 1 and exported["file"].startswith(cache.clip_key("supertonic", "F1", text)) and exported != live
    assert service.clip("supertonic:F1", text, quality=True) == exported and len(quality.calls) == 1, "lần xuất sau lấy bộ đệm"
    tag["now"] = ""
    assert service.clip("supertonic:F1", text) == exported and len(fast.calls) == 1, "về bậc chất lượng: Nghe ngay dùng lại clip chất lượng"


def test_a_voice_without_a_second_tier_keeps_its_key(tmp_path: Path) -> None:
    engine = FakeEngine()
    found = Installed(tmp_path, False)
    plain = SupertonicProvider(lambda: found, engines=lambda _found: engine, aligner=lambda: None, normalize=lambda pieces: " ".join(pieces))
    service = ReadAloud(tmp_path / "cache", [plain], speed=lambda _voice: "fast5")  # không có nhà cung cấp bậc nhanh
    clip = service.clip("supertonic:F1", "Xin chào.")
    assert clip["file"].startswith(cache.clip_key("supertonic", "F1", "Xin chào.")) and len(engine.calls) == 1
