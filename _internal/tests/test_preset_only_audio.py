"""Hợp đồng mới: mỗi preset một giọng, chỉ tempo và gain hằng số."""
from __future__ import annotations

import copy
import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from abook import audio_io, tts, voice_balance as vb, voice_catalog
from abook.character_registry import PresetAllocator, voice_profile_spec
from abook.config import build_settings
from abook.pipeline import BookPipeline


@pytest.mark.parametrize('volume', ['soft', 'normal', 'loud'])
@pytest.mark.parametrize('emotion', ['neutral', 'angry', 'sad', 'whispering'])
def test_gain_ignores_all_line_labels_and_book_settings(volume, emotion):
    key = 'vieneu@3.8.3/Ngọc Linh'
    row = {'voice_balance_key': key, 'volume': volume, 'emotion': emotion,
           'intensity': 3, 'speaker': 'NARRATOR', 'kind': 'narration'}
    constants = vb.constants_for_key(key)
    expected = vb.level_lufs() + constants.o_db - constants.ref_lufs
    assert audio_io.segment_gain_db(row, {}) == pytest.approx(expected)
    settings = build_settings()
    settings['audio']['loudness_lufs'] = -15
    assert audio_io.segment_gain_db(row, settings) == pytest.approx(expected)
    settings['audio']['loudness_lufs'] = -22
    assert audio_io.segment_gain_db(row, settings) == pytest.approx(expected)


def test_no_pitch_formant_or_emotion_dsp_in_take_to_mp3_path():
    for module, names in [(tts, ['apply_pitch_variant', 'apply_voice_variant', '_praat_formant_shift']),
                          (voice_catalog, ['age_pitch_semitones', 'formant_ratio_for_age',
                                           'CHARACTER_FORMANT_STEPS', 'CHARACTER_PITCH_VARIANTS'])]:
        assert all(not hasattr(module, name) for name in names)
    for module in (tts, audio_io):
        source = inspect.getsource(module)
        assert 'import pyworld' not in source
        assert 'import parselmouth' not in source
    source = inspect.getsource(BookPipeline._chapter_delivery_wavs)
    assert 'shape_segment' not in source and 'apply_voice_variant' not in source


@pytest.mark.parametrize('emotion', ['neutral', 'angry', 'sad', 'whispering'])
def test_delivery_preserves_samples_and_structural_pause(tmp_path, emotion):
    rate = 24000
    x = (.08*np.sin(2*np.pi*160*np.arange(rate)/rate)).astype(np.float32)
    x[:300] = 0
    x[-300:] = 0
    source = tmp_path/'take.wav'
    sf.write(source, x, rate, subtype='PCM_16')
    row = {'wav_path': str(source), 'voice_profile_id': 1, 'seq': 1, 'break_ms': 200,
           'scene_break': 0, 'emotion': emotion, 'intensity': 3, 'kind': 'dialogue', 'text': 'Xin chào.'}
    p = object.__new__(BookPipeline)
    p.settings = build_settings()
    p.paths = SimpleNamespace(work=tmp_path/'work')
    p.db = SimpleNamespace(list_voice_profiles=lambda: [{'id': 1}])
    p.log = lambda *_: None
    [(delivered, pause)] = p._chapter_delivery_wavs({'id': 1, 'chapter_index': 1}, [row])
    assert Path(delivered).read_bytes() == source.read_bytes()
    assert pause == 200


@pytest.mark.parametrize('pause_ms', [0, 170, 210, 230, 380, 1500])
def test_pause_between_lines_ignores_emotion_intensity_and_speech_tags(tmp_path, pause_ms):
    rate = 24000
    source = tmp_path / 'take.wav'
    sf.write(source, np.zeros(rate, dtype=np.float32), rate, subtype='PCM_16')
    p = object.__new__(BookPipeline)
    p.settings = build_settings()
    p.paths = SimpleNamespace(work=tmp_path / 'work')
    p.db = SimpleNamespace(list_voice_profiles=lambda: [])
    p.log = lambda *_: None
    base = dict(wav_path=str(source), voice_profile_id=0, kind='dialogue',
                emotion='neutral', intensity=0, text='Xin chào.', scene_break=0)
    for emotion in ['neutral', 'angry', 'afraid', 'sad']:
        for intensity in range(4):
            for text in ['Anh nói:', 'Một câu kể dài. ' * 6]:
                rows = [dict(base, seq=1, break_ms=pause_ms, emotion=emotion, intensity=intensity),
                        dict(base, seq=2, break_ms=0, kind='narration', text=text,
                             emotion=emotion, intensity=intensity)]
                entries = p._chapter_delivery_wavs({'id': 1, 'chapter_index': 1}, rows)
                assert [ms for _, ms in entries] == [pause_ms, 0]


@pytest.mark.parametrize('gender', ['male', 'female'])
def test_age_does_not_change_preset_choice(gender):
    choices = []
    for age in ['child', 'teen', 'adult', 'elderly', 'unknown']:
        allocator = PresetAllocator('Đức Trí')
        choices.append(allocator.choose(gender, npc=False, age=age)['name'])
    assert len(set(choices)) == 1


def test_presets_are_used_once_before_sharing_and_share_one_profile():
    allocator = PresetAllocator('Đức Trí')
    n = len([p for p in voice_catalog.casting_presets('male') if p['name'] != 'Đức Trí'])
    selected = [allocator.choose('male', npc=False, who=str(i)) for i in range(n+1)]
    assert len({p['name'] for p in selected[:n]}) == n
    repeated = next(p for p in selected[:n] if p['name'] == selected[-1]['name'])
    assert voice_profile_spec(repeated) == voice_profile_spec(selected[-1])


def test_casting_allocates_unique_presets_to_the_roles_with_most_lines_first(tmp_path):
    from tests.test_character_casting import _identity_db
    from abook.character_registry import build_registry_and_cast
    settings = build_settings()
    narrator = settings['voices']['narrator_voice']
    capacity = len([p for p in voice_catalog.casting_presets('male') if p['name'] != narrator])
    # Vai ít lời nằm đầu nguồn để thứ tự gặp không lấn thứ tự số câu.
    names = 'ALBERT BERNARD CHARLES DENNIS EDWARD FRANCIS GEORGE HENRY ISAAC JACOB KEVIN LUCAS MARTIN NOLAN OSCAR PETER'.split()
    speakers = [(names[i], 'male') for i in range(capacity+2) for _ in range(i+2)]
    db = _identity_db(tmp_path, speakers)
    build_registry_and_cast(db, settings, lambda _: None)
    with db.connect() as conn:
        rows = conn.execute("SELECT c.canonical_name, COUNT(*) AS n, MIN(v.preset_name) AS preset "
                            "FROM segments s JOIN characters c ON c.id=s.canonical_character_id "
                            "JOIN voice_profiles v ON v.id=s.voice_profile_id "
                            "WHERE c.canonical_name <> 'NARRATOR' GROUP BY c.id ORDER BY n DESC").fetchall()
    assert len(rows) == capacity+2
    assert len({r['preset'] for r in rows[:capacity]}) == capacity


def test_variant_keys_and_extra_record_fields_are_rejected():
    key = 'vieneu@3.8.3/Ngọc Linh'
    with pytest.raises(vb.VoiceBalanceError):
        vb.constants_for_key(key+'/f100')
    for field in ['pitch_st', 'formant_ratio', 'measured_pitch_st']:
        table = copy.deepcopy(vb.load_table())
        table['voices'][key][field] = 1
        with pytest.raises(vb.VoiceBalanceError):
            vb._validate(table)


def test_peak_safety_remains_after_constant_gain():
    rate = 24000
    x = np.full(rate, 2.0, dtype=np.float32)
    y, evidence = audio_io.level_segment(x, rate, {'voice_balance_key': 'vieneu@3.8.3/Ngọc Linh'}, build_settings())
    assert np.max(abs(y)) <= 10**(-2/20) + 1e-6
    assert evidence['peak_limited_db'] > 0
