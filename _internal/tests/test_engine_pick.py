"""Chọn máy đọc mặc định theo số đo của máy (readaloud/engine_pick.py, webui/voice_pick.py): luật chọn, nơi lưu, phép đo, khung máy đọc trên máy."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from abook.readaloud import engine_pick
from abook.readaloud.model import Synthesis, Voice, unit_made
from abook.readaloud.service import ReadAloud, is_local
from abook.readaloud.supertonic import Installed, SupertonicProvider
from abook.webui import voice_pick


def _row(rtf: float = 0.3, cer: float | None = 0.03, natural: float | None = 3.0, **extra: object) -> dict[str, object]:
    return {"rtf": rtf, "cer": cer, "natural": natural, "ramMb": 500, **extra}


# ---- luật chọn ----------------------------------------------------------------------------------------------------------------------
def test_engine_of_groups_voices_by_model() -> None:
    assert engine_pick.engine_of("vieneu:turbo/Đức Trí") == "vieneu:turbo"
    assert engine_pick.engine_of("vieneu:nano/Ái Hân") == "vieneu:nano"
    assert engine_pick.engine_of("supertonic:F1") == "supertonic"


def test_the_most_natural_fit_engine_wins() -> None:
    rows = {"vieneu:turbo": _row(natural=2.96), "vieneu:nano": _row(natural=2.64), "supertonic": _row(natural=3.25)}
    assert engine_pick.choose(rows) == "supertonic"


def test_a_failed_engine_is_never_the_default() -> None:
    rows = {"supertonic": {"error": "onnxruntime chết", "rtf": None}, "vieneu:nano": _row(natural=2.6)}
    assert engine_pick.verdict(rows["supertonic"]) == "error"
    assert engine_pick.choose(rows) == "vieneu:nano"


def test_a_mumbling_engine_is_gated_out_however_natural() -> None:
    rows = {"supertonic": _row(cer=engine_pick.CER_GATE + 0.01, natural=4.5), "vieneu:turbo": _row(cer=0.05, natural=2.9)}
    assert engine_pick.verdict(rows["supertonic"]) == "unclear"
    assert engine_pick.choose(rows) == "vieneu:turbo"


def test_an_engine_too_slow_for_live_listening_is_not_the_default() -> None:
    rows = {"vieneu:turbo": _row(rtf=engine_pick.LIVE_RTF, natural=3.2), "vieneu:nano": _row(rtf=0.2, natural=2.6)}
    assert engine_pick.verdict(rows["vieneu:turbo"]) == "slow"
    assert engine_pick.choose(rows) == "vieneu:nano"


def test_naturalness_within_the_tie_band_goes_to_the_clearer_then_faster_engine() -> None:
    near = engine_pick.NATURAL_TIE / 2
    rows = {"a": _row(natural=3.0, cer=0.05, rtf=0.2), "b": _row(natural=3.0 - near, cer=0.02, rtf=0.5)}
    assert engine_pick.choose(rows) == "b", "ngang tự nhiên: rõ hơn thắng"
    rows = {"a": _row(natural=3.0, cer=0.02, rtf=0.5), "b": _row(natural=3.0, cer=0.02, rtf=0.2)}
    assert engine_pick.choose(rows) == "b", "ngang cả độ rõ: nhanh hơn thắng"
    rows = {"b": _row(), "a": _row()}
    assert engine_pick.choose(rows) == "a", "trùng hết: theo mã, không theo thứ tự đo"


def test_a_clear_gap_in_naturalness_beats_clarity() -> None:
    rows = {"a": _row(natural=3.3, cer=0.06), "b": _row(natural=3.0, cer=0.01)}
    assert engine_pick.choose(rows) == "a"


def test_without_a_scorer_or_an_asr_the_pick_falls_to_speed() -> None:
    rows = {"a": _row(natural=None, cer=None, rtf=0.5), "b": _row(natural=None, cer=None, rtf=0.2)}
    assert engine_pick.choose(rows) == "b"
    rows = {"a": _row(natural=None, cer=0.02), "b": _row(natural=2.0, cer=0.02)}
    assert engine_pick.choose(rows) == "b", "máy đọc có điểm tự nhiên xếp trước máy đọc chấm hỏng"


def test_no_fit_engine_means_no_machine_default() -> None:
    assert engine_pick.choose({"a": _row(rtf=2.0), "b": {"error": "x"}}) is None
    assert engine_pick.choose({}) is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, True])
def test_invalid_numbers_cannot_win(bad: float) -> None:
    for key in ("rtf", "cer", "natural"):
        assert engine_pick.choose({"bad": _row(**{key: bad}), "good": _row()}) == "good"


# ---- nơi lưu --------------------------------------------------------------------------------------------------------------------------
def test_store_keeps_numbers_per_machine_and_the_choice_across_runs(tmp_path: Path) -> None:
    path = tmp_path / "voice-pick.json"
    here = engine_pick.PickStore(path, {"name": "may-a", "cores": 8})
    here.set_override("vieneu:nano")
    here.save_run({"vieneu:nano": _row()}, asr="whisper", natural="utmosv2", at="2026-11-05T00:00:00+00:00")
    loaded = here.load()
    assert loaded["engines"]["vieneu:nano"]["rtf"] == 0.3 and loaded["asr"] == "whisper" and loaded["natural"] == "utmosv2"
    assert loaded["override"] == "vieneu:nano", "đo lại không xoá lựa chọn tay"
    assert path.read_bytes().count(b"\r") == 0
    elsewhere = engine_pick.PickStore(path, {"name": "may-b", "cores": 8}).load()
    assert elsewhere["engines"] == {} and elsewhere["at"] == "", "số đo của máy khác không dùng"
    assert elsewhere["override"] == "vieneu:nano"


def test_a_broken_store_reads_as_nothing_measured(tmp_path: Path) -> None:
    path = tmp_path / "voice-pick.json"
    path.write_bytes(b"{nope")
    assert engine_pick.PickStore(path, {"name": "x"}).load()["engines"] == {}


# ---- phép đo ---------------------------------------------------------------------------------------------------------------------------
def test_measure_reads_speed_from_the_units_and_ram_from_the_peak() -> None:
    clock = iter(float(n) for n in range(100))
    memory = iter([100 * 2 ** 20] + [300 * 2 ** 20] * 500)

    def speak(text: str) -> None:
        unit_made(np.zeros(16_000, dtype=np.float32), 16_000, text, 0.25)  # 1 giây nghe, máy làm 0,25 giây

    numbers, takes = engine_pick.measure(speak, ("Câu một.", "Câu hai."), rss=lambda: next(memory), settle=lambda: None, clock=lambda: next(clock))
    assert numbers["rtf"] == 0.25 and numbers["audioSeconds"] == 2.0, "lần đọc khởi động không tính"
    assert numbers["ramMb"] == 200 and numbers["peakRamMb"] == 300
    assert [text for text, _wave, _rate in takes] == ["Câu một.", "Câu hai."] and takes[0][2] == 16_000


def test_measure_fails_an_engine_that_reports_no_audio() -> None:
    with pytest.raises(ValueError):
        engine_pick.measure(lambda _text: None, ("Câu.",), rss=lambda: 0, settle=lambda: None)


def test_clarity_is_one_minus_the_asr_similarity() -> None:
    takes = [("một", np.zeros(4), 16_000), ("hai", np.zeros(4), 16_000)]
    heard = {"một": 1.0, "hai": 0.8}
    cer = engine_pick.score_clarity(takes, lambda _wave, _rate: "x", lambda expected, _heard: heard[expected])
    assert cer == pytest.approx(0.1)
    assert engine_pick.score_naturalness(takes, lambda _wave, _rate: 3.0) == 3.0


# ---- khung máy đọc trên máy -----------------------------------------------------------------------------------------------------------
class _SupertonicEngine:
    SAMPLE_RATE = 44_100

    def infer(self, text: str, _name: str, _rng, _speed: float = 1.0) -> np.ndarray:
        return 0.3 * np.sin(np.arange(int(0.2 * max(1, len(text.split())) * self.SAMPLE_RATE)) / 3).astype(np.float32)


class _Broken:
    """Máy đọc cắm thêm giả: có engine (`forget`), đọc hỏng."""

    id = "broken"
    speaks_english = False

    def voices(self) -> list[Voice]:
        return [Voice("broken:only", "Hỏng", "broken", False)]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        raise RuntimeError("model hỏng")

    def forget(self) -> None:
        pass


class _Slow(_Broken):
    id = "slow"

    def voices(self) -> list[Voice]:
        return [Voice("slow:tier/A", "A", "slow", False), Voice("slow:tier/B", "B", "slow", False)]

    def synthesize(self, text: str, native_voice: str) -> Synthesis:
        unit_made(np.zeros(16_000, dtype=np.float32), 16_000, text, 2.0)
        return Synthesis(b"", [], 1000)


def _service(tmp_path: Path, *extra: object, pick=lambda: None) -> ReadAloud:
    supertonic = SupertonicProvider(lambda: Installed(tmp_path, False), engines=lambda _found: _SupertonicEngine(), aligner=lambda: None, normalize=" ".join)
    return ReadAloud(tmp_path / "cache", [supertonic, *extra], machine_pick=pick)  # type: ignore[list-item]


def test_local_engines_are_the_providers_with_a_model(tmp_path: Path) -> None:
    service = _service(tmp_path, _Slow())
    engines = service.local_engines()
    assert list(engines) == ["supertonic", "slow:tier"]
    assert engines["slow:tier"] == ["slow:tier/A", "slow:tier/B"]
    assert is_local(service.providers["supertonic"]) and not is_local(object())


def test_every_local_model_has_the_same_explicit_engine_interface(tmp_path: Path) -> None:
    from abook.readaloud.local_engine import LocalEngine

    adapters = _service(tmp_path, _Slow()).local_engine_adapters()
    assert {engine.id for engine in adapters} == {"supertonic", "slow:tier"}
    for engine in adapters:
        assert isinstance(engine, LocalEngine)
        assert engine.voices() and engine.capabilities()["offline"] is True
        assert engine.resource_needs() == {"device": "cpu", "runtime": "download-on-demand", "ramMb": None}
        with pytest.raises(ValueError):
            engine.synthesize("Xin chào.", "other:voice")


def test_zerotts_uses_the_same_interface_and_cpu_measurement(tmp_path: Path) -> None:
    from abook.readaloud.zerotts import ZeroTTSProvider

    class Engine:
        sample_rate = 24_000
        frame_rate = 12.5

        def synthesize(self, text: str, *, voice: str, max_frames: int) -> np.ndarray:
            assert voice == "baotrang" and max_frames > 0
            return np.sin(np.arange(24_000, dtype=np.float32) / 100) * 0.1

    provider = ZeroTTSProvider(lambda: object(), engines=lambda _: Engine(), normalize=str)
    service = ReadAloud(tmp_path / "cache", [provider])
    assert list(service.local_engines()) == ["zerotts"]
    numbers, takes = service.measure_engine("zerotts:baotrang", ("Trời trong xanh.",))
    assert numbers["audioSeconds"] == 1 and numbers["rtf"] >= 0
    assert len(takes) == 1 and provider._engine is None


def test_an_uninstalled_zerotts_does_not_load_or_download_a_runtime(tmp_path: Path) -> None:
    from abook.readaloud.zerotts import ZeroTTSProvider

    provider = ZeroTTSProvider(lambda: None, engines=lambda _: pytest.fail("must not load"))
    service = ReadAloud(tmp_path / "cache", [provider])
    assert service.local_engines() == {}


def test_measure_engine_runs_the_real_provider_and_releases_the_model(tmp_path: Path) -> None:
    service = _service(tmp_path)
    provider = service.providers["supertonic"]
    numbers, takes = service.measure_engine("supertonic:F1", ("Một câu ngắn thôi.",))
    assert numbers["rtf"] >= 0 and numbers["audioSeconds"] > 0 and len(takes) == 1
    assert provider._engine is None, "đo xong bỏ model: lần nghe kế nạp lại như thường"


def test_voices_mark_the_machine_pick_only_once_measured(tmp_path: Path) -> None:
    assert all("pick" not in voice for voice in _service(tmp_path, _Slow()).voices()), "chưa đo: không đánh dấu gì"
    listed = _service(tmp_path, _Slow(), pick=lambda: "slow:tier").voices()
    assert {voice["id"] for voice in listed if voice.get("pick")} == {"slow:tier/A", "slow:tier/B"}
    assert all(voice["pick"] is False for voice in listed if voice["provider"] == "supertonic")
    listed = _service(tmp_path, pick=lambda: "").voices()
    assert all(voice["pick"] is False for voice in listed), "đã đo mà không máy đọc nào đạt: không giọng nào được đánh dấu"


# ---- thẻ "Giọng theo máy" ---------------------------------------------------------------------------------------------------------------
def _configure(tmp_path: Path, service: ReadAloud, marks=lambda _voice: "m1", asr_seen: list[str] | None = None) -> None:
    def asr() -> voice_pick.Judge:
        return "fake-asr", lambda wave, _rate: "nghe", lambda: (asr_seen.append("closed") if asr_seen is not None else None)

    voice_pick.configure(tmp_path / voice_pick.FILE, service, marks=marks, asr=asr,
                         natural=lambda: ("fake-mos", lambda _wave, _rate: 3.1, lambda: None),
                         similarity=lambda: (lambda _expected, _heard: 0.97))


def test_a_run_measures_every_engine_and_picks_by_the_rule(tmp_path: Path) -> None:
    closed: list[str] = []
    service = _service(tmp_path, _Slow(), _Broken())
    _configure(tmp_path, service, asr_seen=closed)
    assert voice_pick.status()["state"] == "stale" and voice_pick.chosen() is None
    voice_pick.start()
    voice_pick.join(30)
    status = voice_pick.status()
    assert status["state"] == "ready", status
    rows = {row["engine"]: row for row in status["engines"]}
    assert rows["supertonic"]["verdict"] == "" and rows["supertonic"]["cer"] == pytest.approx(0.03) and rows["supertonic"]["natural"] == 3.1
    assert rows["slow:tier"]["verdict"] == "slow"
    assert rows["broken"]["verdict"] == "error" and "model hỏng" in rows["broken"]["error"]
    assert status["auto"] == status["chosen"] == "supertonic" and status["asr"] == "fake-asr" and status["natural"] == "fake-mos"
    assert closed == ["closed"], "bộ nghe nhả sau khi chấm"
    assert voice_pick.chosen() == "supertonic"


def test_the_listener_can_override_and_return_to_the_measured_pick(tmp_path: Path) -> None:
    service = _service(tmp_path, _Slow())
    _configure(tmp_path, service)
    voice_pick.start()
    voice_pick.join(30)
    voice_pick.set_override("slow:tier")
    assert voice_pick.status()["chosen"] == "slow:tier" and voice_pick.status()["auto"] == "supertonic"
    with pytest.raises(ValueError):
        voice_pick.set_override("vieneu:turbo")
    voice_pick.set_override("")
    assert voice_pick.chosen() == "supertonic"


def test_a_model_update_makes_the_numbers_stale_and_a_module_measure_reruns(tmp_path: Path) -> None:
    service = _service(tmp_path)
    mark = {"value": "m1"}
    _configure(tmp_path, service, marks=lambda _voice: mark["value"])
    voice_pick.start()
    voice_pick.join(30)
    assert voice_pick.status()["state"] == "ready"
    voice_pick.module_measured()
    assert voice_pick.status()["state"] == "ready", "số đo còn mới: mô-đun đo lại không kéo theo lượt đo các máy đọc"
    mark["value"] = "m2"
    assert voice_pick.status()["state"] == "stale" and voice_pick.chosen() is None
    voice_pick.module_measured()
    voice_pick.join(30)
    assert voice_pick.status()["state"] == "ready" and voice_pick.chosen() == "supertonic"
    saved = json.loads((tmp_path / voice_pick.FILE).read_bytes())
    assert saved["engines"]["supertonic"]["mark"] == "m2"


def test_without_an_asr_the_clarity_is_unmeasured_not_zero(tmp_path: Path) -> None:
    service = _service(tmp_path)
    voice_pick.configure(tmp_path / voice_pick.FILE, service, asr=lambda: None, natural=lambda: None, similarity=lambda: None)
    voice_pick.start()
    voice_pick.join(30)
    status = voice_pick.status()
    row = status["engines"][0]
    assert row["cer"] is None and row["natural"] is None and status["asr"] == "" and status["chosen"] == "supertonic"


def test_the_packaged_app_scores_in_the_optional_studio_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    import subprocess
    import sys
    from types import SimpleNamespace

    service = _service(tmp_path)
    studio = SimpleNamespace(python=Path(sys.executable), environment=lambda: {"ABOOK_RUNTIME": str(tmp_path / "runtime")})

    def run(args, **kwargs):
        assert args[0] == sys.executable and args[1:5] == ["-X", "utf8", "-m", "abook.webui.voice_pick_worker"]
        assert kwargs["env"]["CUDA_VISIBLE_DEVICES"] == "-1" and kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        if os.name == "nt":
            assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW
            assert kwargs["creationflags"] & subprocess.BELOW_NORMAL_PRIORITY_CLASS
        request = json.loads(Path(args[-2]).read_text(encoding="utf-8"))
        assert len(request["supertonic"]) == len(engine_pick.SENTENCES)
        assert all(Path(clip["file"]).is_file() for clip in request["supertonic"])
        Path(args[-1]).write_text(json.dumps({"engines": {"supertonic": {"cer": 0.02, "natural": 3.2}}, "asr": "whisper", "natural": "utmosv2"}), encoding="utf-8")

    monkeypatch.setattr(subprocess, "run", run)
    voice_pick.configure(tmp_path / voice_pick.FILE, service, studio=lambda: studio)
    voice_pick.start()
    voice_pick.join(30)
    status = voice_pick.status()
    assert status["engines"][0]["cer"] == 0.02 and status["engines"][0]["natural"] == 3.2
    assert status["asr"] == "whisper" and status["natural"] == "utmosv2"


def test_a_failed_studio_helper_keeps_real_synthesis_numbers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from types import SimpleNamespace

    def failed(*_args):
        raise RuntimeError("helper hỏng")

    monkeypatch.setattr(voice_pick, "score_in_studio", failed)
    voice_pick.configure(tmp_path / voice_pick.FILE, _service(tmp_path), studio=lambda: SimpleNamespace(python=Path(sys.executable)))
    voice_pick.start()
    voice_pick.join(30)
    status = voice_pick.status()
    assert status["engines"][0]["rtf"] >= 0 and status["engines"][0]["cer"] is None
    assert "helper hỏng" in status["error"]


def test_the_studio_worker_uses_the_app_judges_and_releases_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook.webui.voice_pick_worker import main
    import soundfile

    wave = tmp_path / "take.wav"
    soundfile.write(str(wave), np.zeros(16_000, dtype=np.float32), 16_000)
    source, target = tmp_path / "request.json", tmp_path / "scores.json"
    source.write_text(json.dumps({"test": [{"text": "Câu.", "file": str(wave)}]}), encoding="utf-8")
    closed = []
    monkeypatch.setattr(voice_pick, "default_similarity", lambda: lambda *_: 0.96)
    monkeypatch.setattr(voice_pick, "default_asr", lambda: ("asr", lambda *_: "nghe", lambda: closed.append("asr")))
    monkeypatch.setattr(voice_pick, "utmos_judge", lambda: ("mos", lambda *_: 3.2, lambda: closed.append("mos")))
    main(source, target)
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["engines"]["test"] == {"cer": 0.04, "natural": 3.2}
    assert closed == ["asr", "mos"]
