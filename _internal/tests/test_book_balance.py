"""Vòng kín trên giọng tổng hợp, qua FFmpeg thật; không cần model hay audio của sách."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from abook.audio_io import assemble_chapter_atomic_with_metrics, delivery_gain_copy
from abook.book_levels import balance_finished_book, balance_limits, balance_satisfied, measure_finished_book
from abook.chapter_loudness import chapter_level_plan
from abook.config import build_settings
from abook.io_utils import sha256_file


def synthetic_book(tmp_path):
    settings = build_settings()
    rate = settings['tts']['sample_rate']
    rows, chapters, wavs = [], [], {}
    t = np.arange(2*rate)/rate
    for chapter, frequency in ((1, 160), (2, 2500)):
        x = .035*np.sin(2*np.pi*frequency*t)
        x[:2400] *= np.linspace(0, 1, 2400)
        x[-2400:] *= np.linspace(1, 0, 2400)
        wav = tmp_path/f'synthetic_{chapter}.wav'
        sf.write(wav, x, rate, subtype='PCM_16')
        wavs[chapter] = wav
        rr = []
        for i in range(12):
            row = dict(chapter_id=chapter, id=chapter*100+i, seq=i, stable_id=f's{chapter}_{i}',
                       voice_profile_id=chapter, wav_duration=2, wav_sha256=sha256_file(wav),
                       signal_json='{"level_speech_seconds": 2, "applied_level_offset_db": 0}')
            rr.append(row)
        rows += rr
        chapters.append(dict(id=chapter, file=tmp_path/f'final_{chapter}.mp3', segments=[]))
    profiles = [dict(id=i, preset=f'synthetic{i}', voice_key=f'synthetic{i}') for i in (1, 2)]
    return settings, rows, chapters, wavs, profiles


def test_real_ffmpeg_closed_loop_idempotent_and_timing(tmp_path, monkeypatch):
    from abook import voice_balance
    monkeypatch.setattr(voice_balance, 'voice_key_for_profile', lambda p: str(p['id']))
    settings, rows, chapters, wavs, profiles = synthetic_book(tmp_path)
    renders, accepted = [], []

    def render(corrections, round_no):
        plan = chapter_level_plan(rows, profiles, settings, corrections)
        trial = []
        for ch in chapters:
            number = ch['id']
            gain = corrections.get('voices', {}).get(str(number), 0)
            source = tmp_path/f'delivery_{round_no}_{number}.wav'
            delivery_gain_copy(wavs[number], source, gain, settings)
            rr = [r for r in rows if r['chapter_id'] == number]
            result = assemble_chapter_atomic_with_metrics([(source, 0)]*12,
                tmp_path/f'round_{round_no}_{number}.mp3', settings, title='Synthetic',
                book_title='Synthetic', track=number, target_lufs=plan[number]['target_lufs'])
            assert len(result.timeline) == 12
            assert result.timeline[-1][1] == pytest.approx(result.quality.decoded_duration_seconds)
            assert all(a <= b <= result.quality.decoded_duration_seconds+.001 for a, b in result.timeline)
            trial.append(dict(id=number, file=tmp_path/f'round_{round_no}_{number}.mp3', segments=[
                dict(voice=str(number), stable_id=r['stable_id'], start=a, end=b)
                for r, (a, b) in zip(rr, result.timeline)]))
        renders.append(round_no)
        return trial, trial

    baseline, _ = render({}, 0)
    before = [sha256_file(p) for p in wavs.values()]
    result = balance_finished_book(baseline, render=render, accept=lambda receipt: accepted.append(receipt))
    assert not result.get('error'), result
    assert balance_limits(result['rounds'][0]['measurement'])[0] > 1.5
    assert balance_satisfied(result['best']), [balance_limits(r['measurement']) for r in result['rounds']]
    count = len(renders)
    again = balance_finished_book(accepted[-1], render=render, accept=lambda _: pytest.fail('must reuse'), previous=result)
    assert again == result and len(renders) == count
    assert before == [sha256_file(p) for p in wavs.values()]
    # Vòng cố tình bù ngược cũng qua FFmpeg/meter thật, phải bị bỏ nguyên vẹn.
    baseline_hashes = [sha256_file(ch['file']) for ch in baseline]
    def reversed_render(corrections, round_no):
        reversed_corrections = copy.deepcopy(corrections)
        reversed_corrections['voices'] = {k:-v for k,v in corrections.get('voices', {}).items()}
        return render(reversed_corrections, round_no+10)
    discarded = balance_finished_book(baseline,render=reversed_render,
        accept=lambda _: pytest.fail('worse real master must be discarded'))
    assert not discarded.get('error'), discarded
    assert discarded['rounds'][-1]['accepted'] is False
    assert balance_limits(discarded['rounds'][-1]['measurement'])[0] > balance_limits(discarded['best'])[0]
    assert baseline_hashes == [sha256_file(ch['file']) for ch in baseline]


@pytest.mark.parametrize('failure', ['meter', 'master', 'worse', 'publish'])
def test_failed_or_worse_round_keeps_audio(tmp_path, failure):
    path = tmp_path/'current.mp3'
    path.write_bytes(b'current verified audio')
    initial = dict(verdict='warning', book_mean_phon=50, voice_spread_phon=6,
                   voices={'a': {'n': 12, 'mean_phon': 47}, 'b': {'n': 12, 'mean_phon': 53}},
                   chapters={'1': {'n': 12, 'mean_phon': 47, 'delta_phon': -3},
                             '2': {'n': 12, 'mean_phon': 53, 'delta_phon': 3}})
    calls = []
    def measure(_):
        if calls and failure == 'meter':
            raise RuntimeError('synthetic meter failure')
        value = copy.deepcopy(initial)
        if calls:
            value['voice_spread_phon'] = 3 if failure == 'publish' else 9
            if failure == 'publish':
                for row in value['chapters'].values():
                    row['delta_phon'] *= .5
        return value
    def render(*_):
        calls.append(True)
        if failure == 'master':
            raise RuntimeError('synthetic master failure')
        return [{'id': 1, 'file': path}], None
    result = balance_finished_book([{'id': 1, 'file': path}], render=render,
        accept=(lambda _: (_ for _ in ()).throw(RuntimeError('synthetic publish failure')))
               if failure == 'publish' else (lambda _: pytest.fail('must retain current audio')), measure=measure)
    assert path.read_bytes() == b'current verified audio'
    assert result['best']['voice_spread_phon'] == 6 if failure == 'worse' else result['verdict'] == 'warning'
    if failure == 'publish':
        assert not result['rounds'][-1]['accepted']
        assert result['error'] == 'synthetic publish failure'


def test_independent_holdout_excludes_all_fit_lines(tmp_path):
    from test_book_levels import _book
    chapters, opener = _book(0)
    fit = measure_finished_book(chapters, opener)
    holdout = measure_finished_book(chapters, opener, seed='holdout-v2', exclude=set(fit['measured_ids']))
    assert not set(holdout['measured_ids']) & set(fit['measured_ids'])
    assert holdout['verdict'] == 'insufficient_data'


def test_pipeline_uses_final_audio_and_reuses_completed_balance(tmp_path, monkeypatch):
    from abook import voice_balance
    from abook.pipeline import BookPipeline
    from abook.webui import store, word_timing
    monkeypatch.setattr(voice_balance, 'voice_key_for_profile', lambda p: str(p['id']))
    settings, rows, inputs, wavs, profiles = synthetic_book(tmp_path)
    for p in profiles:
        p['formant_ratio'] = 1.0
    for r in rows:
        r.update(wav_path=str(wavs[r['chapter_id']]), break_ms=0, emotion='neutral',
                 intensity=0, kind='narration', text='', scene_break=0, volume='normal', speaker='')
    chapters, artifacts, spans = [], {}, {}
    for ch in inputs:
        chapter_id = ch['id']
        assembly = assemble_chapter_atomic_with_metrics([(wavs[chapter_id], 0)]*12, ch['file'],
            settings, title='Synthetic', book_title='Synthetic', track=chapter_id, target_lufs=-20)
        chapters.append(dict(id=chapter_id, chapter_index=chapter_id, status='completed',
                             title='Synthetic', output_mp3=str(ch['file'])))
        rr = [r for r in rows if r['chapter_id'] == chapter_id]
        spans.update({r['id']: span for r, span in zip(rr, assembly.timeline)})
        artifacts[f'chapter_mp3:{chapter_id}'] = dict(artifact_key=f'chapter_mp3:{chapter_id}', kind='chapter_mp3',
            sha256=assembly.checksum, verified=1, metadata_json='{}')
    pipeline = object.__new__(BookPipeline)
    pipeline.paths = SimpleNamespace(root=tmp_path, work=tmp_path/'work', reports=tmp_path/'reports')
    pipeline.paths.reports.mkdir()
    pipeline.settings = settings
    pipeline.quality_policy_hash = 'synthetic-policy'
    pipeline.log = pipeline.emit = pipeline._progress = lambda *a, **kw: None
    pipeline._wait_pause_or_stop = lambda: None
    pipeline._resource_gate = lambda *a, **kw: None
    pipeline._validate_chapter_source = lambda ch: None
    pipeline._high_quality_blocking_segment_warnings = lambda rr: []
    pipeline._chapter_has_current_segment_audio_qa = lambda _: True
    def register(**kw):
        artifacts[kw['artifact_key']] = dict(artifact_key=kw['artifact_key'],kind=kw['kind'],
            sha256=kw['sha256'],verified=kw['verified'],metadata_json=json.dumps(kw['metadata']))
    pipeline.db = SimpleNamespace(list_segments=lambda: rows, list_voice_profiles=lambda: profiles,
        book=lambda: {'title':'Synthetic'}, chapter_is_publishable=lambda _: True,
        artifact_by_key=artifacts.get, register_artifact=register, event=lambda *a: None,
        quality_metadata_for_current_policy=lambda: {}, record_quality_check=lambda **kw: None,
        quality_checks=lambda **kw: [], update_chapter_status=lambda *a: None)
    pipeline._next_chapter_quality_attempt = lambda _: 1
    def script(root, chapter_id):
        ch = next(ch for ch in chapters if ch['id']==chapter_id)
        path = Path(ch['output_mp3'])
        rr = [r for r in rows if r['chapter_id']==chapter_id]
        timed, actual, _, duration = store._sentence_timeline(root,ch,rr)
        return dict(timed=timed,duration=duration,segments=[
            dict(id=r['id'],start=a,end=b) for r,(a,b) in zip(rr,actual)])
    monkeypatch.setattr(store,'chapter_script',script)
    # Mốc words đóng trước sửa không được gắn với MP3 mới.
    stamps = {c['id']: Path(c['output_mp3']).stat() for c in chapters}
    for ch in chapters:
        old_segments = script(tmp_path,ch['id'])['segments']
        word_timing._save(tmp_path,ch['id'],{'version':word_timing.VERSION,
            'audio':{'size':stamps[ch['id']].st_size,'mtimeNs':stamps[ch['id']].st_mtime_ns},
            'lines':{str(g['id']): {'textSha256':word_timing.text_sha(''),
                     'span':word_timing._milliseconds(g),'words':[]} for g in old_segments}})
        assert word_timing.attach(tmp_path,ch['id'],old_segments,Path(ch['output_mp3'])) == 12
    pipeline._check_finished_book_levels(chapters)
    result = pipeline._book_levels
    assert not result.get('error'), result
    assert balance_satisfied(result['best']), result
    assert not (pipeline.paths.work/'book_level_publish.json').exists()
    hashes = [sha256_file(Path(c['output_mp3'])) for c in chapters]
    for ch in chapters:
        path = Path(ch['output_mp3'])
        data = json.loads(path.with_suffix('.mp3.levels.json').read_text(encoding='utf8'))
        assert data['audio_sha256'] == sha256_file(path)
        assert pipeline._chapter_level_is_current(ch)
        actual = script(tmp_path,ch['id'])
        assert word_timing.attach(tmp_path,ch['id'],actual['segments'],path) == 0
        assert actual['segments'][-1]['end'] == pytest.approx(actual['duration'], abs=.001)
    pipeline._check_finished_book_levels(chapters)
    assert pipeline._book_levels == result
    assert pipeline._book_level_manifest_is_current(chapters)
    assert hashes == [sha256_file(Path(c['output_mp3'])) for c in chapters]


@pytest.mark.parametrize('checkpointed', [False, True])
def test_publication_journal_recovers_a_whole_round(tmp_path, checkpointed):
    from abook.pipeline import BookPipeline
    pipeline = object.__new__(BookPipeline)
    pipeline.paths = SimpleNamespace(root=tmp_path, work=tmp_path/'work', reports=tmp_path/'reports')
    pipeline.paths.work.mkdir()
    pipeline.paths.reports.mkdir()
    backups = pipeline.paths.work/'book_level_publish'
    backups.mkdir()
    target = tmp_path/'current.mp3'
    target.write_bytes(b'new verified master')
    backup = backups/'1'
    backup.write_bytes(b'previous verified master')
    old = {'artifact_key':'chapter_mp3:1','kind':'chapter_mp3','sha256':sha256_file(backup),
           'verified':1,'metadata_json':'{}'}
    journal = [dict(target=str(target),backup=str(backup),chapter_id=1,sidecar=False,artifact=old)]
    (pipeline.paths.work/'book_level_publish.json').write_text(json.dumps(journal),encoding='utf8')
    if checkpointed:
        (pipeline.paths.reports/'book_levels.json').write_text(json.dumps(
            {'audio_sha256':{'1':sha256_file(target)}}),encoding='utf8')
    restored = []
    pipeline.db = SimpleNamespace(register_artifact=lambda **kw: restored.append(kw))
    pipeline._recover_book_level_publication()
    assert target.read_bytes() == (b'new verified master' if checkpointed else b'previous verified master')
    assert bool(restored) is not checkpointed
    assert not (pipeline.paths.work/'book_level_publish.json').exists()
    assert not backups.exists()


def test_delivery_reuses_base_and_invalidates_when_source_changes(tmp_path, monkeypatch):
    from abook.pipeline import BookPipeline
    settings, rows, _, wavs, profiles = synthetic_book(tmp_path)
    for p in profiles:
        p['formant_ratio'] = 1.0
    r = rows[0]
    r.update(wav_path=str(wavs[1]),break_ms=0,emotion='neutral',intensity=0,
             kind='narration',text='',scene_break=0)
    pipeline = object.__new__(BookPipeline)
    pipeline.settings = settings
    pipeline.paths = SimpleNamespace(work=tmp_path/'work')
    pipeline.db = SimpleNamespace(list_voice_profiles=lambda: profiles)
    pipeline.log = lambda *a: None
    pipeline._apply_book_level_gains = lambda chapter, ordered, rendered, profiles: rendered
    reads = []
    real_read = sf.read
    def tracked(*a, **kw):
        reads.append(True)
        return real_read(*a, **kw)
    monkeypatch.setattr(sf,'read',tracked)
    chapter = {'id':1,'chapter_index':1}
    a = pipeline._chapter_delivery_wavs(chapter,[r])
    first = len(reads)
    assert first > 0
    assert pipeline._chapter_delivery_wavs(chapter,[r]) == a
    assert len(reads) == first
    # Mất bộ nhớ tiến trình vẫn đọc lại đúng cache byte trên đĩa, không dựng lại âm sắc.
    del pipeline._delivery_base_cache
    assert pipeline._chapter_delivery_wavs(chapter,[r]) == a
    assert len(reads) == first
    r['status'] = 'warning'
    profiles[0]['used_count'] = 123
    del pipeline._delivery_base_cache
    assert pipeline._chapter_delivery_wavs(chapter,[r]) == a
    assert len(reads) == first
    r['wav_sha256'] = 'new source identity'
    pipeline._chapter_delivery_wavs(chapter,[r])
    assert len(reads) > first


def test_one_voice_book_can_go_directly_to_chapter_residual(tmp_path):
    path = tmp_path/'current.mp3'
    path.write_bytes(b'synthetic current artifact')
    before = dict(verdict='warning',book_mean_phon=50,voice_spread_phon=None,
                  voices={'a':{'n':24,'mean_phon':50}},chapters={
                      '1':{'n':12,'mean_phon':48,'delta_phon':-2},
                      '2':{'n':12,'mean_phon':52,'delta_phon':2}})
    after = copy.deepcopy(before)
    for row in after['chapters'].values():
        row.update(mean_phon=50,delta_phon=0)
    rendered = []
    def render(corrections, round_no):
        rendered.append((corrections,round_no))
        return [{'id':1,'file':path}],None
    result = balance_finished_book([{'id':1,'file':path}],render=render,accept=lambda _: None,
        measure=lambda _: after if rendered else before)
    assert len(rendered) == 1 and rendered[0][1] == 2
    assert rendered[0][0]['chapters'] == {'1':2,'2':-2}
    assert balance_satisfied(result['best'])


def test_zero_eligible_lines_is_reported_without_a_voice_delta():
    from test_book_levels import _book
    chapters, opener = _book(0)
    chapters[0]['segments'].append(dict(voice='sparse',stable_id='sparse',start=0,end=.1,volume='soft'))
    result = measure_finished_book(chapters,opener)
    assert result['insufficient_voices']['sparse'] == 0
    assert 'sparse' not in result['voices']


def test_no_measured_deltas_never_remasters_a_sparse_book(tmp_path):
    path = tmp_path/'current.mp3'
    path.write_bytes(b'synthetic current artifact')
    result = balance_finished_book([{'id':1,'file':path}],
        render=lambda *_: pytest.fail('no eligible correction'),accept=lambda _: None,
        measure=lambda _: dict(verdict='insufficient_data',voices={},chapters={},
                               voice_spread_phon=None,book_mean_phon=None))
    assert result['verdict'] == 'warning'
    assert result['corrections'] == {}


@pytest.mark.parametrize('chapter_delta', [.8, 1.1])
def test_better_goal_score_can_use_the_chapter_margin(tmp_path, chapter_delta):
    path=tmp_path/'current.mp3'
    path.write_bytes(b'synthetic current artifact')
    before=dict(verdict='warning',book_mean_phon=50,voice_spread_phon=3,
                voices={'a':{'n':12,'mean_phon':48.5},'b':{'n':12,'mean_phon':51.5}},
                chapters={'1':{'n':12,'mean_phon':49.6,'delta_phon':-.4},
                          '2':{'n':12,'mean_phon':50.4,'delta_phon':.4}})
    after=copy.deepcopy(before)
    after['voice_spread_phon']=.5
    after['chapters']['1']['delta_phon']=-chapter_delta
    after['chapters']['2']['delta_phon']=chapter_delta
    calls=[]
    accepted=[]
    def render(corrections, round_no):
        calls.append(round_no)
        return [{'id':1,'file':path}],round_no
    result=balance_finished_book([{'id':1,'file':path}],render=render,accept=accepted.append,
        measure=lambda _: after if calls else before)
    assert accepted == [1]
    assert result['best']['voice_spread_phon'] == .5
    assert result['rounds'][1]['accepted'] is True
    if chapter_delta <= 1:
        assert balance_satisfied(result['best'])
