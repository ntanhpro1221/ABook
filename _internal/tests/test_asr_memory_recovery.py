"""a96 V6: fake Whisper load/inference OOM, no model or GPU is opened."""
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest
import soundfile as sf

from abook.asr import WhisperVerifier
from abook.config import build_settings
from abook.pipeline import BookPipeline


@pytest.mark.parametrize("where", ["load", "inference", "repeat"])
@pytest.mark.parametrize("required", [True, False])
@pytest.mark.parametrize("engine", ["openai", "faster"])
def test_whisper_oom_retries_same_wav_without_cpu_switch(tmp_path, monkeypatch, where, required, engine):
    settings = build_settings()
    settings["asr"].update(engine=engine, required=required, failure_policy="fail" if required else "warn", cpu_fallback=True)
    verifier = WhisperVerifier(settings, lambda text: None)
    calls, loads, releases, waits = [], [], [], []
    wav = tmp_path / "same.wav"
    sf.write(wav, np.zeros(16000, dtype=np.float32), 16000)
    before = wav.read_bytes()
    class Model:
        def transcribe(self, audio, **kwargs):
            calls.append((verifier.device, audio.copy(), kwargs))
            if where != "load" and len(calls) == 1:
                raise RuntimeError("CUDA out of memory. Tried to allocate 1.00 GiB")
            if engine == "faster":
                return iter([SimpleNamespace(text="Bạn hãy nghe câu chuyện này.", start=0, end=1)]), None
            return {"text": "Bạn hãy nghe câu chuyện này.", "segments": []}
    def load(*args, **kwargs):
        loads.append(kwargs)
        if where == "load" and len(loads) == 1:
            raise RuntimeError("CUDA out of memory")
        return Model()
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, empty_cache=lambda: releases.append("cache"))))
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(_MODELS={}, load_model=load))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=load))
    monkeypatch.setattr("abook.asr.trim_process_working_set", lambda: None)
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline._recover_from_memory_pressure = lambda *args: waits.append(args) or True
    expected = "Bạn hãy nghe" if where == "repeat" else "Bạn hãy nghe câu chuyện này."
    result = pipeline._verify_with_memory_recovery(verifier, expected, wav, confirmation=False, repeated=where == "repeat")
    assert "verdict" in result
    assert len(waits) == 1
    assert releases, "Even a partial load must release the CUDA allocator cache"
    assert len(loads) == 2
    assert all(item["device"] == "cuda" for item in loads)
    assert wav.read_bytes() == before
    if len(calls) == 2:
        np.testing.assert_array_equal(calls[0][1], calls[1][1])
        assert calls[0][2] == calls[1][2]


@pytest.mark.parametrize("recovers,expected_waits,expected_calls", [(True, 2, 3), (False, 1, 1)])
def test_whisper_recovery_has_attempt_and_wait_ceiling(recovers, expected_waits, expected_calls):
    calls, releases, waits = [], [], []
    def verify(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("CUDA out of memory")
    verifier = SimpleNamespace(verify=verify, unload=lambda **kwargs: releases.append(1))
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline._recover_from_memory_pressure = lambda *args: waits.append(args) or recovers
    with pytest.raises(RuntimeError, match="thiếu bộ nhớ card đồ hoạ"):
        pipeline._verify_with_memory_recovery(verifier, "same text", Path("same.wav"), confirmation=True)
    assert len(calls) == expected_calls
    assert len(waits) == expected_waits
    assert len(releases) == expected_calls


def test_non_memory_whisper_error_is_not_retried():
    original = RuntimeError("CUBLAS_STATUS_EXECUTION_FAILED")
    def fail(*args, **kwargs):
        raise original
    pipeline = BookPipeline.__new__(BookPipeline)
    verifier = SimpleNamespace(verify=fail)
    with pytest.raises(RuntimeError) as caught:
        pipeline._verify_with_memory_recovery(verifier, "text", Path("same.wav"), confirmation=False)
    assert caught.value is original


def test_successful_decode_is_returned_unchanged_without_recovery():
    pipeline = BookPipeline.__new__(BookPipeline)
    result = {"passed": True, "verdict": "pass", "transcript": "Bạn hãy nghe", "similarity": 1.0, "wer": 0.0}
    calls = []
    def verify(*args, **kwargs):
        calls.append((args, kwargs))
        return result
    verifier = SimpleNamespace(verify=verify)
    assert pipeline._verify_with_memory_recovery(verifier, "Bạn hãy nghe", Path("same.wav"), confirmation=True) is result
    assert calls == [(("Bạn hãy nghe", Path("same.wav")), {"confirmation": True})]


@pytest.mark.parametrize("fallback", [True, False])
def test_cuda_unavailable_keeps_declared_cpu_fallback_policy(monkeypatch, fallback):
    settings = build_settings()
    settings["asr"].update(engine="openai", cpu_fallback=fallback)
    loads = []
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, "whisper", SimpleNamespace(_MODELS={}, load_model=lambda *args, **kwargs: loads.append(kwargs) or object()))
    verifier = WhisperVerifier(settings, lambda text: None)
    if fallback:
        assert verifier.load()
        assert loads[0]["device"] == "cpu"
    else:
        with pytest.raises(RuntimeError, match="CUDA unavailable"):
            verifier.load()
        assert not loads


def test_candidate_caller_recovers_before_recording_decode_evidence():
    calls, evidence, waits = [], [], []
    def verify(expected, wav, **kwargs):
        calls.append((expected, wav, kwargs))
        if len(calls) == 1:
            raise RuntimeError("CUDA out of memory")
        return {"passed": True, "verdict": "pass", "transcript": expected,
                "similarity": 1.0, "wer": 0.0, "reason": "ok"}
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline.settings = build_settings()
    pipeline._spoken_text_and_anchors = lambda item: ("Bạn hãy nghe câu chuyện này.", [])
    pipeline._recover_from_memory_pressure = lambda *args: waits.append(args) or True
    def record(*args, **kwargs):
        evidence.append(kwargs)
        return {"quality_check_id": 91}
    pipeline._record_segment_asr_decode_evidence = record
    verifier = SimpleNamespace(verify=verify, unload=lambda **kwargs: None)
    result = pipeline._decode_audio_candidate({"wav_path": "same.wav"}, verifier, confirmation=False,
                                              repair_round=None, delivery_mode="primary")
    assert result["selected_quality_check_id"] == 91
    assert len(calls) == 2 and calls[0] == calls[1]
    assert len(waits) == 1 and len(evidence) == 1
