"""Quiet-name repair preserves ordinary pauses and runs before final audio QA."""
from __future__ import annotations

import numpy as np
import pytest

from abook.readaloud import japanese_audio as audio, japanese_delivery
from abook.readaloud.japanese_policy import NAMESPACE


def wave(rate=48_000):
    signal = (0.1 * np.sin(np.arange(rate * 3) * (2 * np.pi * 220 / rate))).astype(np.float32)
    for start, end in [(0, .2), (.5, .9), (1.2, 1.6), (2.1, 2.18), (2.8, 3)]:
        signal[round(start * rate):round(end * rate)] = 0
    return signal


@pytest.mark.parametrize("rate", [16_000, 24_000, 48_000])
def test_only_long_gaps_inside_the_aligned_word_are_shortened(rate):
    original = wave(rate)
    result, evidence = audio.shorten(original, rate, [(.3, 1.0), (1.8, 2.5)])
    assert len(evidence['edits']) == 1
    assert len(original) - len(result) == sum(e['removed_samples'] for e in evidence['edits'])
    assert np.array_equal(original[:round(.4 * rate)], result[:round(.4 * rate)])
    assert np.array_equal(original[round(1.0 * rate):], result[round(1.0 * rate)-len(original)+len(result):])
    # The between-word pause, short closure and sentence edges remain byte exact.
    runs, _ = audio.low_energy_runs(result, rate)
    assert sum((b-a)/rate >= .12 for a,b in runs) == 3
    assert np.array_equal(original, wave(rate)), "source audio must stay immutable"


@pytest.mark.parametrize("ranges", [[(-1, 1)], [(1, float('nan'))], [(1, .5)], [(0, 2), (1, 3)]])
def test_invalid_alignment_cannot_edit_audio(ranges):
    with pytest.raises(ValueError):
        audio.shorten(wave(), 48_000, ranges)


@pytest.mark.parametrize("confidence", [0, .69, float('nan')])
def test_no_guessing_when_alignment_is_unreliable(confidence):
    class Aligner:
        def align(self, _wave, _text): return [None] * 3, confidence

    original = wave()
    result, evidence = audio.repair(original, 48_000, 'Nô-pa-mi', [(0, 8)], Aligner())
    assert result is original and evidence['edits'] == []


def test_missing_model_and_listener_spans_preserve_audio_without_loading():
    original = wave()
    result, evidence = audio.repair(original, 48_000, 'Nô-pa-mi', [(0, 8)], None)
    assert result is original and evidence['status'] == 'no_alignment_model'
    anchor = dict(reading_namespace=NAMESPACE, source='listener_choice', spoken_start=0,spoken_end=8,spoken_form='Nô-pa-mi')
    assert japanese_delivery.anchor_spans('Nô-pa-mi', [anchor]) == []
    assert audio.word_spans('Nô-pa-mi và Nô-pa-mi-na.', {'nô-pa-mi'}) == [(0, 8)]


def test_punctuation_is_outside_each_exact_aligned_occurrence():
    class Aligner:
        def align(self, _wave, text):
            assert text == 'nô pa mi đã về'
            return [[.3,.35],[.92,.95],[.96,1.0],[1.8,1.9],[2.2,2.3]], .95

    text = '“Nô-pa-mi?!”, đã về.'
    result, evidence = audio.repair(wave(),48_000,text,[(1,9)],Aligner())
    assert evidence['status']=='repaired' and len(evidence['edits'])==1
    assert len(result)<len(wave())


def test_studio_repairs_names_after_tempo_before_final_qa(tmp_path, monkeypatch):
    from abook import tts
    from abook.config import build_settings
    from abook.database import ProjectDB
    from abook.webui import word_timing

    class Aligner:
        def align(self, _wave, target):
            assert target == 'nô pa mi đã về nhà'
            return [[.3,.35],[.92,.95],[.96,1.0],[1.8,1.9],[2.2,2.3],[2.5,2.6]], .95

    db = ProjectDB(tmp_path/'project.sqlite3')
    profile = db.upsert_voice_profile(dict(voice_key='test',engine='vieneu',preset_name='Xuân Vĩnh',description='Test',seed=1234,status='ready'))
    coordinator = tts.TTSCoordinator(build_settings(),db,lambda _:None)
    monkeypatch.setattr(coordinator,'_origin_of_book',lambda:'ja')
    monkeypatch.setattr(coordinator.vieneu,'generate_one',lambda *_a,**_k:wave())
    monkeypatch.setattr(coordinator,'release_inference_cache',lambda:None)
    monkeypatch.setattr(word_timing,'get_aligner',lambda:Aligner())
    seen=[]
    def tempo(samples,rate,speed):
        seen.append(('tempo',len(samples)))
        return samples
    def write(_out,samples,rate,text,_settings,**_kwargs):
        assert text == 'Nô-pa-mi đã về nhà.'
        seen.append(('qa',len(samples)))
        return 'checksum', {}
    monkeypatch.setattr(tts,'apply_speed_change',tempo)
    monkeypatch.setattr(tts,'atomic_write_wav',write)
    _, metrics, _ = coordinator.synthesize_atomic(dict(voice_profile_id=profile,stable_id='name',text='Nopami đã về nhà.',kind='dialogue',speaker='TEST'),tmp_path/'output.wav')
    assert metrics['japanese_name_audio']['status']=='repaired'
    assert seen[-1][0]=='qa' and seen[-1][1]<len(wave())
    assert all(n==len(wave()) for kind,n in seen if kind=='tempo')


def test_render_implementation_is_fingerprinted():
    from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES
    assert 'readaloud/japanese_audio.py' in QUALITY_IMPLEMENTATION_FILES
