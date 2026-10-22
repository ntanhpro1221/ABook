"""a96 V9: publishing retries the validated candidate, not synthesis/QA."""
import errno
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


def test_persistent_wav_lock_does_not_start_another_tts_attempt(tmp_path, monkeypatch):
    from abook.config import build_settings
    from abook.pipeline import BookPipeline
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline.settings = build_settings()
    pipeline.quality_policy_hash = "test"
    pipeline._chunk_path = lambda row: tmp_path / "sentence.wav"
    pipeline._wait_pause_or_stop = lambda: None
    pipeline.db = SimpleNamespace(mark_generating=lambda *args, **kwargs: None)
    pipeline.log = lambda text: None
    calls = []
    class Resynthesized(BaseException):
        pass
    def synthesize(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) > 1:
            raise Resynthesized("A rename failure must not synthesize a new take")
        raise PermissionError("file đang bị ứng dụng khác giữ / quyền thư mục")
    pipeline.tts = SimpleNamespace(generation_seed=lambda *args: 123, synthesize_atomic=synthesize)
    monkeypatch.setattr("abook.pipeline.time.sleep", lambda seconds: None)
    with pytest.raises(PermissionError):
        pipeline._process_single_segment({"id": 1, "stable_id": "same"}, {})
    assert len(calls) == 1


def test_pool_publish_permission_error_cannot_be_discarded_as_a_bad_take(tmp_path):
    from abook.pipeline import BookPipeline, TTS_POOL_MIN_BATCH
    pipeline = BookPipeline.__new__(BookPipeline)
    pipeline._synthesis_pool = lambda: SimpleNamespace(synthesize_many=lambda jobs: [
        {"stable_id": "same", "error": "PermissionError: file đang bị ứng dụng khác giữ / quyền thư mục"}
    ])
    pipeline._chunk_path = lambda row: tmp_path / "sentence.wav"
    rows = [{"id": i, "stable_id": "same"} for i in range(TTS_POOL_MIN_BATCH)]
    with pytest.raises(PermissionError):
        pipeline._prefetch_segment_batch(rows, seed_salt_prefix="primary", repair_short_utterance=False, delivery_mode="primary")


@pytest.mark.parametrize("persistent", [False, True])
def test_wav_publish_lock_retries_the_same_validated_bytes(tmp_path, monkeypatch, persistent):
    from abook import audio_io as audio, io_utils
    from abook.config import build_settings
    out = tmp_path / "sentence.wav"
    out.write_bytes(b"previous audio")
    candidate = out.with_name("sentence.part.wav")
    validations, attempts, delays = [], [], []
    monkeypatch.setattr(audio, "validate_audio_array", lambda array, *args, **kwargs: (array, {}))
    def inspect(path, *args, **kwargs):
        validations.append(path)
        return True, {}, "ok"
    monkeypatch.setattr(audio, "inspect_wav", inspect)
    monkeypatch.setattr(io_utils.time, "sleep", delays.append)
    real_replace = audio.os.replace
    def locked(src, dst):
        attempts.append(Path(src).read_bytes())
        if persistent or len(attempts) < 3:
            raise PermissionError(errno.EACCES, "held by another application")
        real_replace(src, dst)
    monkeypatch.setattr(audio.os, "replace", locked)
    if persistent:
        with pytest.raises(PermissionError, match="ứng dụng khác.*quyền"):
            audio.atomic_write_wav(out, np.zeros(16000), 16000, "text", build_settings())
        assert out.read_bytes() == b"previous audio"
        assert candidate.exists()
        assert len(attempts) == io_utils.REPLACE_RETRY_ATTEMPTS
        assert len(delays) == io_utils.REPLACE_RETRY_ATTEMPTS - 1
    else:
        checksum, _ = audio.atomic_write_wav(out, np.zeros(16000), 16000, "text", build_settings())
        assert checksum == hashlib.sha256(out.read_bytes()).hexdigest()
        assert not candidate.exists()
        assert len(attempts) == 3
    assert len(set(attempts)) == 1
    assert validations == [candidate]

@pytest.mark.parametrize("persistent", [False, True])
def test_mp3_transient_rename_lock_retries_without_encoding_or_qa_again(tmp_path, monkeypatch, persistent):
    import numpy as np
    from abook import audio_io as audio, io_utils
    from abook.config import build_settings
    source, out = tmp_path / 'input.wav', tmp_path / 'chapter.mp3'
    source.write_bytes(b'fixture-placeholder')
    out.write_bytes(b'old published audio')
    monkeypatch.setattr(audio, '_cap_segment_edge_silence', lambda entries, *args: (entries, []))
    monkeypatch.setattr(audio, '_source_timeline', lambda *args: (1, [], []))
    monkeypatch.setattr(audio, '_measure_loudness', lambda *args, **kwargs: {})
    monkeypatch.setattr(audio, '_second_pass_loudnorm_filter', lambda *args: 'fake-filter')
    monkeypatch.setattr(audio, 'ffmpeg_executable', lambda: 'never-run-ffmpeg')
    encodes = []
    def encode(command, **kwargs):
        encodes.append(command)
        Path(command[-1]).write_bytes(b'x' * 5000)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(audio, 'run_hidden', encode)
    monkeypatch.setattr(audio, '_decode_mp3_candidate', lambda *args: (np.zeros(16000), 16000, 1))
    monkeypatch.setattr(audio, '_evaluate_chapter_quality', lambda *args: SimpleNamespace(hard_failures=[], review_flags=[]))
    real_replace = audio.os.replace
    attempts = []
    monkeypatch.setattr(io_utils.time, "sleep", lambda seconds: None)
    def flaky(src, dst):
        if Path(dst) == out:
            attempts.append(1)
            if persistent or len(attempts) == 1:
                raise PermissionError(errno.EACCES, 'temporary antivirus lock', str(out))
        return real_replace(src, dst)
    monkeypatch.setattr(audio.os, 'replace', flaky)
    if persistent:
        with pytest.raises(PermissionError, match="ứng dụng khác.*quyền"):
            audio.assemble_chapter_atomic_with_metrics([source], out, build_settings(), title='Chương', book_title='Sách', track=1)
        assert len(attempts) == io_utils.REPLACE_RETRY_ATTEMPTS
        assert len(encodes) == 1
        assert out.read_bytes() == b'old published audio'
        assert (tmp_path / 'chapter.part.mp3').read_bytes() == b'x' * 5000
        return
    result = audio.assemble_chapter_atomic_with_metrics([source], out, build_settings(), title='Chương', book_title='Sách', track=1)
    assert len(attempts) == 2
    assert len(encodes) == 1
    assert result.checksum == hashlib.sha256(b'x' * 5000).hexdigest()
    assert out.read_bytes() == b'x' * 5000
    assert not (tmp_path / 'chapter.part.mp3').exists()
