"""Cổng phát hành: một dòng chưa đạt không được làm biến mất chương có đủ lời đọc."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from abook import pipeline as pipeline_module
from abook.audio_io import AudioQualityError, pace_is_outlier
from abook.config import build_settings
from abook.database import ProjectDB, PRONUNCIATION_DELIVERY_LOCKED
from abook.io_utils import sha256_file
from abook.pipeline import BookPipeline
from abook.tts import TTSCoordinator, CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE
from abook.webui import audio_coverage, bookfile, store
from tests.test_pipeline_mock import _short_tts_pipeline, ScriptedShortTTS


def test_generated_tables_materialize_idempotently_and_split_without_cascading(tmp_path, monkeypatch):
    rng = random.Random(731)
    for trial in range(40):
        surface = f"Zed{trial}"
        middle = f"Ry{rng.randrange(100)}"
        table = [
            {"id": 1, "surface": surface, "spoken_form": middle + " cu-đên", "locked": 1, "source": "manual"},
            {"id": 2, "surface": middle, "spoken_form": "Rai", "locked": 1, "source": "manual"},
        ]
        for entry in table:
            entry['normalized_surface'] = entry['surface'].casefold()
        if trial % 2:
            table[0]['source'] = CONTEXTUAL_ENGLISH_NAME_PRONUNCIATION_SOURCE
        coordinator = TTSCoordinator(build_settings(), SimpleNamespace(list_pronunciations=lambda _minimum: table), lambda _: None)
        coordinator._book_origin = (None,)
        source = f"{surface} mang chiếc túi màu xanh đi qua con đường nhỏ trước căn nhà. Sau đó người ấy đặt túi xuống chiếc ghế gỗ bên cạnh cửa sổ. Người bạn mang thêm một ấm trà nóng ra bàn và mời mọi người ngồi xuống."
        row = {"text": source, "stable_id": "invented"}
        spoken, anchors = coordinator.spoken_text_with_anchors(row)
        assert middle + " cu-đên" in spoken and "Rai" not in spoken
        prepared = {**row, "_materialized_spoken": (PRONUNCIATION_DELIVERY_LOCKED, spoken, anchors)}
        assert coordinator.spoken_text_with_anchors(prepared) == (spoken, anchors)
        assert coordinator.spoken_text_with_anchors(prepared) == coordinator.spoken_text_with_anchors(prepared)
        materialized = coordinator._spoken_row(row)
        assert coordinator._spoken_row(materialized) == materialized
        pipeline = BookPipeline.__new__(BookPipeline)
        pipeline.settings = build_settings()
        pieces = []
        def synthesize(part, path, **kwargs):
            text, mapped = coordinator.spoken_text_with_anchors(part)
            assert all(text[a['spoken_start']:a['spoken_end']] == a['spoken_form'] for a in mapped)
            pieces.append(text)
            return 'a' * 64, {'spoken_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                              'pronunciation_delivery_variant': PRONUNCIATION_DELIVERY_LOCKED}, 7
        pipeline.tts = SimpleNamespace(spoken_text_with_anchors=coordinator.spoken_text_with_anchors,
                                       synthesize_atomic=synthesize, generation_seed=lambda *_: 7)
        monkeypatch.setattr(pipeline_module, 'merge_wav_parts_atomic', lambda *a, **k: None)
        pipeline._synthesize_split(row, tmp_path / 'split.wav')
        assert ' '.join(pieces) == spoken
        assert row['text'] == source


@pytest.mark.parametrize('flag', ['pace_outlier', 'repeated_utterance_score'])
def test_soft_rejections_keep_best_audio_and_failure_after_reopen(tmp_path, monkeypatch, flag):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    pipeline.settings['quality_profile'] = 'high_quality'
    outcomes = [{flag: 1.0}, {flag: 1.0}, AudioQualityError('engine failed'), AudioQualityError('engine failed')]
    pipeline.tts = ScriptedShortTTS(outcomes).bind(pipeline.settings, pipeline.db)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    pipeline._process_single_segment(row, chapter)
    reopened = ProjectDB(pipeline.db.path)
    kept = reopened.get_segment(row['id'])
    assert kept['status'] == 'failed' and kept['error']
    assert Path(kept['wav_path']).is_file()
    assert sha256_file(Path(kept['wav_path'])) == kept['wav_sha256']
    samples, _ = sf.read(kept['wav_path'])
    assert samples.size and np.any(samples)


def test_take_order_and_crash_keep_incumbent_until_better_checkpoint(tmp_path):
    pipeline, _, row = _short_tts_pipeline(tmp_path)
    for index, flags in enumerate([{'pace_outlier': 1, 'generation_ceiling_hit': 1}, {'pace_outlier': 1}, {'pace_outlier': 1, 'generation_ceiling_hit': 1}, {}]):
        path = tmp_path / f'take{index}.wav'
        sf.write(path, np.sin(np.arange(24000) / 30) * .1, 24000)
        metrics = {'duration': 1.0, **flags}
        pipeline.db.mark_generating(row['id'], index)
        pipeline._keep_usable_take(row, path, sha256_file(path), metrics, index)
        kept = pipeline.db.get_segment(row['id'])
        assert Path(kept['wav_path']).name == f'take{[0, 1, 1, 3][index]}.wav'
    kept = pipeline.db.get_segment(row['id'])
    pipeline._accept_retained_take(row)
    pipeline.db.mark_generating(row['id'], 999)
    reopened = ProjectDB(pipeline.db.path)
    reopened.reset_in_progress_segments()
    recovered = reopened.get_segment(row['id'])
    assert recovered['wav_sha256'] == kept['wav_sha256'] and recovered['generation_seed'] == kept['generation_seed']
    assert recovered['status'] == 'signal_passed'


def test_crash_before_quality_decision_retains_audio_without_passing_it(tmp_path):
    pipeline, _, row = _short_tts_pipeline(tmp_path)
    path = tmp_path / 'not-graded.wav'
    sf.write(path, .1 * np.sin(np.arange(24000) / 30), 24000)
    pipeline._keep_usable_take(row, path, sha256_file(path), {'duration': 1}, 9)
    reopened = ProjectDB(pipeline.db.path)
    reopened.reset_in_progress_segments('crash before quality decision')
    current = reopened.get_segment(row['id'])
    assert current['status'] == 'failed' and current['error']
    assert current['wav_sha256'] == sha256_file(path)
    assert json.loads(current['signal_json'])['quality_pending']


def test_provider_rejecting_after_writing_audio_cannot_lose_the_take(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    def reject(item, path, **kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, .1 * np.sin(np.arange(24000) / 30), 24000)
        raise AudioQualityError('provider rejected a decodable take')
    pipeline.tts = SimpleNamespace(generation_seed=lambda *a: 7, spoken_text=lambda r: r['text'], synthesize_atomic=reject)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    monkeypatch.setattr(pipeline.db, 'mark_signal_passed', lambda *a, **k: pytest.fail('rejected audio was marked passed'))
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row['id'])
    assert current['status'] == 'failed' and 'provider rejected' in current['error']
    assert current['wav_sha256'] == sha256_file(Path(current['wav_path']))
    assert json.loads(current['signal_json'])['signal_rejected']


def test_signal_validator_rejection_keeps_audio_and_allows_a_better_take(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    pipeline.tts = ScriptedShortTTS([{}, {}]).bind(pipeline.settings, pipeline.db)
    original = pipeline.db.mark_signal_passed
    rejected = []
    def validate(segment_id, **kwargs):
        if not rejected:
            current = pipeline.db.get_segment(segment_id)
            assert current['wav_sha256'] == sha256_file(Path(current['wav_path']))
            assert json.loads(current['signal_json'])['quality_pending']
            rejected.append(current['wav_path'])
            raise AudioQualityError('signal evidence rejected')
        return original(segment_id, **kwargs)
    monkeypatch.setattr(pipeline.db, 'mark_signal_passed', validate)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row['id'])
    assert current['status'] == 'signal_passed' and current['attempt_count'] == 2
    assert not json.loads(current['signal_json']).get('quality_pending')
    assert Path(rejected[0]).is_file()


@pytest.mark.parametrize('silent', [False, True])
def test_unusable_output_never_becomes_replacement_speech(tmp_path, monkeypatch, silent):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    def reject(item, path, **kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        if silent:
            sf.write(path, np.zeros(24000), 24000)
        else:
            path.write_bytes(b'not a WAV')
        raise AudioQualityError('no usable speech')
    pipeline.tts = SimpleNamespace(generation_seed=lambda *a: 7, spoken_text=lambda r: r['text'], synthesize_atomic=reject)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row['id'])
    assert current['status'] == 'failed' and not current['wav_path']


def test_undecodable_failures_have_no_audio(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    pipeline.tts = ScriptedShortTTS([AudioQualityError('no audio')] * 4).bind(pipeline.settings, pipeline.db)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    pipeline._process_single_segment(row, chapter)
    failed = pipeline.db.get_segment(row['id'])
    assert failed['status'] == 'failed' and not failed['wav_path']


@pytest.mark.parametrize('chapter_quality', ['pass', 'review', 'hard_failure'])
def test_release_gate_real_audio_keeps_failed_chapter_and_blocks_missing_line(tmp_path, monkeypatch, chapter_quality):
    from dataclasses import replace
    from abook import audio_io
    evaluate = audio_io._evaluate_chapter_quality
    def grade(*args, **kwargs):
        result = evaluate(*args, **kwargs)
        if chapter_quality == 'review':
            return replace(result, review_flags=('DC offset synthetic',))
        if chapter_quality == 'hard_failure':
            return replace(result, hard_failures=('DC offset too high: synthetic',))
        return result
    monkeypatch.setattr(audio_io, '_evaluate_chapter_quality', grade)
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một chiếc lá nhỏ nằm trên bàn.')
    pipeline.tts = ScriptedShortTTS([{}]).bind(pipeline.settings, pipeline.db)
    pipeline._process_single_segment(row, chapter)
    kept = pipeline.db.get_segment(row['id'])
    path = Path(kept['wav_path'])
    rate = pipeline.settings['tts']['sample_rate']
    samples = np.arange(int(rate * 2.5)) / rate
    sf.write(path, .1 * np.sin(2 * np.pi * 220 * samples), rate)
    with pipeline.db.connect() as connection:
        connection.execute('UPDATE segments SET wav_sha256=?,wav_duration=2.5 WHERE id=?', (sha256_file(path), row['id']))
    pipeline.db.mark_failed(row['id'], 'pace floor', warning_code='TTS_PACE_OUTLIER')
    pipeline._publish_verified_chapter(chapter)
    current = pipeline.db.list_chapters()[0]
    assert current['status'] == 'warning' and row['stable_id'] in current['last_error']
    assert Path(current['output_mp3']).is_file()
    assert store.chapters(pipeline.paths.root)[0]['statusLabel'] == 'Cần nghe lại'
    script = store.chapter_script(pipeline.paths.root, chapter['id'])
    assert script['timed'] and script['segments'][0]['status'] == 'failed'
    exported = bookfile.pack(pipeline.paths.root, tmp_path / 'complete.abook')
    with bookfile.BookFile(exported) as opened:
        opened.verify()
        assert opened.book['chaptersAvailable'] == opened.book['chaptersTotal'] == 1
        assert opened.book['chapters'][0]['qualityPassed'] is False
        assert opened.book['chapters'][0]['failedLines']
        assert 'Cần nghe lại' in opened.book['chapters'][0]['subtitle']
        concealed = copy.deepcopy(opened.book)
        concealed['chapters'][0]['qualityPassed'] = True
        with pytest.raises(ValueError, match='che dòng'):
            audio_coverage.verify(concealed, opened.read, lambda _: True)
    # Gói còn nguyên audio và mã băm nhưng bảng chương bị rơi mất: CLI vẫn phải bắt được.
    for remove_coverage in (False, True):
        damaged = tmp_path / f'chapter-lost-{remove_coverage}.abook'
        with zipfile.ZipFile(exported) as source, zipfile.ZipFile(damaged, 'w') as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == 'book.json':
                    manifest = json.loads(payload)
                    manifest.update(chapters=[], chaptersTotal=0, chaptersAvailable=0)
                    if remove_coverage:
                        manifest.pop('audioCoverage')
                    payload = json.dumps(manifest, ensure_ascii=False).encode()
                target.writestr(info, payload)
        assert bookfile.main(['verify', str(damaged)]) == 1
    # Phụ đề hỏng cú pháp cũng là chương thiếu bằng chứng khi đã chọn partial.
    partial_book, partial_files = bookfile.listening_layer(pipeline.paths.root)
    partial_files[partial_book['chapters'][0]['script']] = b'{'
    partial_coverage = audio_coverage.project(pipeline.paths.root, partial_book, partial_files, partial=True)
    assert partial_coverage['missing'][0]['id'] == chapter['id']
    assert not partial_book['chapters'][0]['file']
    with pipeline.db.connect() as connection:
        connection.execute('UPDATE segments SET wav_path=NULL,wav_sha256=NULL WHERE id=?', (row['id'],))
    pipeline._publish_verified_chapter(chapter)
    current = pipeline.db.list_chapters()[0]
    assert current['status'] == 'failed' and row['stable_id'] in current['last_error']
    assert not store.chapter_audio_paths(pipeline.paths.root)
    with pytest.raises(bookfile.BookFileError, match='Thiếu chương') as refused:
        bookfile.pack(pipeline.paths.root, tmp_path / 'refused.abook')
    assert row['stable_id'] in str(refused.value)


@pytest.mark.parametrize('damage', ['missing_chapter', 'hash', 'subtitle', 'decode', 'qa_label'])
def test_verifier_detects_omitted_chapters_bad_audio_hashes_and_subtitles(damage):
    audio = b'invented audio'
    expected = [{'id': 1, 'textSha256': hashlib.sha256('Lá xanh.'.encode()).hexdigest()}]
    script = {'timed': True, 'duration': 1, 'segments': [{**expected[0], 'text': 'Lá xanh.', 'start': 0, 'end': 1}]}
    chapter = {'id': 1, 'title': 'Lá xanh', 'file': 'chapters/1.mp3', 'script': 'scripts/1.json', 'sha256': hashlib.sha256(audio).hexdigest()}
    book = {'chapters': [chapter], 'chaptersTotal': 1, 'chaptersAvailable': 1, 'complete': True,
            'audioCoverage': {'expected': [{'id': 1, 'title': 'Lá xanh', 'segments': expected, 'audioSha256': chapter['sha256']}], 'missing': [], 'partial': False}}
    if damage == 'missing_chapter':
        book['chapters'] = []
    elif damage == 'hash':
        chapter['sha256'] = 'bad'
    elif damage == 'subtitle':
        script['segments'] = []
    elif damage == 'qa_label':
        book['audioCoverage']['expected'][0]['qualityPassed'] = False
        chapter['qualityPassed'] = True
    read = lambda name: audio if name.endswith('mp3') else json.dumps(script).encode()
    with pytest.raises(ValueError):
        audio_coverage.verify(book, read, lambda _: damage != 'decode')


def test_partial_manifest_requires_explicit_choice_and_names_missing_chapter(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path)
    pipeline.db.mark_failed(row['id'], 'no usable audio')
    with pytest.raises(bookfile.BookFileError, match='0/1'):
        bookfile.pack(pipeline.paths.root, tmp_path / 'refused.abook')
    path = bookfile.pack(pipeline.paths.root, tmp_path / 'partial.abook', partial=True)
    with bookfile.BookFile(path) as opened:
        opened.verify()
        coverage = opened.book['audioCoverage']
        assert coverage['partial'] and not opened.book['complete']
        assert '0/1' in audio_coverage.summary(coverage)
        assert chapter['title'] in audio_coverage.summary(coverage)
    assert bookfile.main(['verify', str(path)]) == 0


def test_normal_pace_floor_requires_both_measures():
    assert pace_is_outlier(12, 3, (12.5, 24.5))
    assert not pace_is_outlier(12, 5, (12.5, 24.5))
    assert not pace_is_outlier(13, 3, (12.5, 24.5))


@pytest.mark.parametrize('signal', ['active_edge', 'silence', 'nonfinite'])
def test_real_writer_rejection_keeps_only_decodable_non_silent_speech(tmp_path, monkeypatch, signal):
    import abook.tts as tts_module
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    coordinator = pipeline.tts
    rate = coordinator.sample_rate
    samples = (.1 * np.sin(np.arange(rate) / 30)).astype(np.float32)
    samples[:rate // 100] = .25
    if signal == 'silence':
        samples[:] = 0
    elif signal == 'nonfinite':
        samples[0] = np.nan
    engine = coordinator.engine_for_profile(coordinator._voice_profile_for_row(row))
    engine.sample_rate = rate
    monkeypatch.setattr(engine, 'generate_one', lambda *a, **k: samples)
    monkeypatch.setattr(tts_module, 'apply_speed_change', lambda audio, *a, **k: audio)
    monkeypatch.setattr(coordinator, 'release_inference_cache', lambda: None)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    pipeline._process_single_segment(row, chapter)
    kept = pipeline.db.get_segment(row['id'])
    assert kept['status'] == 'failed' and kept['error']
    if signal == 'active_edge':
        assert pipeline._has_real_audio(kept)
        assert json.loads(kept['signal_json'])['signal_rejected']
    else:
        assert not kept['wav_sha256'] and not pipeline._has_real_audio(kept)


def test_explicit_retry_keeps_audio_until_new_checkpoint(tmp_path):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path)
    pipeline.tts = ScriptedShortTTS([{}]).bind(pipeline.settings, pipeline.db)
    pipeline._process_single_segment(row, chapter)
    old = dict(pipeline.db.get_segment(row['id']))
    pipeline.db.mark_failed(row['id'], 'pace floor')
    pipeline.db.retry_failed_segments('explicit retry')
    reopened = ProjectDB(pipeline.db.path)
    current = reopened.get_segment(row['id'])
    assert current['wav_path'] == old['wav_path'] and current['wav_sha256'] == old['wav_sha256']
    assert sha256_file(Path(current['wav_path'])) == current['wav_sha256']


def test_signal_rejection_exhausts_as_failed_with_real_audio(tmp_path, monkeypatch):
    pipeline, chapter, row = _short_tts_pipeline(tmp_path, source_text='Một câu ngắn.')
    row = dict(row)
    row['pace'] = 'fast'
    pipeline.tts = ScriptedShortTTS([{}] * 4).bind(pipeline.settings, pipeline.db)
    monkeypatch.setattr(pipeline_module.time, 'sleep', lambda _: None)
    def reject(*args, **kwargs):
        raise AudioQualityError('signal rejected')
    monkeypatch.setattr(pipeline.db, 'mark_signal_passed', reject)
    pipeline._process_single_segment(row, chapter)
    current = pipeline.db.get_segment(row['id'])
    assert current['status'] == 'failed' and 'signal rejected' in current['error']
    assert pipeline._has_real_audio(current)


def test_candidate_archive_is_durable_and_keeps_the_best_without_claiming_pass(tmp_path):
    pipeline, _, row = _short_tts_pipeline(tmp_path)
    kept = None
    for index, flags in enumerate([{'pace_outlier': 1}, {'pace_outlier': 1}, {}]):
        path = tmp_path / f'candidate{index}.wav'
        sf.write(path, .1 * np.sin(np.arange(24000) / (30 + index)), 24000)
        pipeline._archive_usable_take(row, path, sha256_file(path), {'duration': 1, **flags}, index)
        current = pipeline.db.artifact_by_key(f"usable_take:{row['id']}")
        assert not current['verified'] and not json.loads(current['metadata_json'])['quality_passed']
        assert sha256_file(Path(current['path'])) == current['sha256']
        if index == 1:
            assert current['sha256'] == kept
        kept = current['sha256']


@pytest.mark.parametrize('partial', [False, True])
def test_http_export_demands_explicit_partial_and_displays_coverage(tmp_path, partial):
    from tests.test_export_series import _part, _post, _studio
    from tests.test_bookfile_job import _wait
    library = tmp_path / 'library'
    library.mkdir()
    project = _part(tmp_path, library, 'part', 'Lá xanh')
    _, server = _studio(tmp_path, library)
    try:
        status, _ = _post(server, project, 'bookfile-job', {'target': str(tmp_path / 'exports'), 'partial': partial})
        assert status == 202
        job = _wait(server, project, 'done' if partial else 'error')
    finally:
        server.stop()
    if partial:
        assert '1/2' in job['result']['coverage'] and '646' in job['result']['coverage']
    else:
        assert '1/2' in job['error'] and '646' in job['error']


def test_series_partial_names_parts_and_reports_the_full_chapter_count(tmp_path):
    from tests.test_export_series import _part, _post, _studio
    from tests.test_bookfile_job import _wait
    library = tmp_path / 'library'
    library.mkdir()
    first = _part(tmp_path, library, 'one', 'Lá xanh')
    _part(tmp_path, library, 'two', 'Lá xanh · Phần 2', first)
    _, server = _studio(tmp_path, library)
    try:
        assert _post(server, first, 'bookfile-job', {'target': str(tmp_path / 'exports'), 'series': True,
                                                    'single': False, 'partial': True})[0] == 202
        result = _wait(server, first)['result']
    finally:
        server.stop()
    assert result['coverage'].startswith('2/4 chương')
    assert 'Phần 1:' in result['coverage'] and 'Phần 2:' in result['coverage'] and '646' in result['coverage']
