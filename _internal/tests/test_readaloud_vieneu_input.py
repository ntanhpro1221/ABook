"""Synthetic input only: bounded VieNeu reads, deterministic PCM and stream units."""
from __future__ import annotations

import numpy as np
import pytest

from abook.readaloud import vieneu, vieneu_engine as ve, vieneu_input as cap
from abook.readaloud.model import hearing, VoiceError
from abook.vieneu_limits import VIENEU_HALVING_DEPTH


def test_native_fixture_and_policy_are_current():
    import json
    from pathlib import Path
    from abook.quality_policy import QUALITY_IMPLEMENTATION_FILES
    root = Path(__file__).parent
    for case in json.loads((root / 'fixtures/vieneu/android/readcap.json').read_text(encoding='utf-8')):
        text = (case['repeat'] * case['count'])[:case['chars']]
        _, parts = vieneu.units(text, case['limit'], direct_english=True)
        assert [cap.bounded_pieces(p.pieces, case['limit']) for p in parts] == case['chunks']
    assert {'vieneu_limits.py', 'vieneu_input_policy.json', 'readaloud/vieneu_input.py'} <= set(QUALITY_IMPLEMENTATION_FILES)
    assert cap.unit_limit(140) == 140 + 2 * vieneu.MIN_UNIT_CHARS
    import tomllib
    package = tomllib.loads((root.parent / 'pyproject.toml').read_text(encoding='utf-8'))
    assert 'vieneu_input_policy.json' in package['tool']['setuptools']['package-data']['abook']


@pytest.mark.parametrize('tier,limit', [('nano', 140), ('turbo', 256)])
@pytest.mark.parametrize('text', ['ồ' * 15023, 'a' * 5000, ('một hai ba bốn năm ' * 1200)[:20000], 'bcdfghjk' * 700, 'h' * 5000],
                         ids=['vowel', 'letter', 'paragraph', 'unbroken', 'consonant'])
def test_every_spoken_chunk_is_bounded_and_display_words_are_untouched(tier, limit, text):
    toks, parts = vieneu.units(text, limit, direct_english=True)
    assert ' '.join(toks) == text.strip()
    assert [i for p in parts for i in range(p.first, p.last + 1)] == list(range(len(toks)))
    for part in parts:
        chunks = cap.bounded_pieces(part.pieces, limit)
        assert chunks
        assert all(len(' '.join(chunk)) <= limit for chunk in chunks)
        assert all(max(map(len, ' '.join(chunk).split()), default=0) <= 64 for chunk in chunks)


def test_word_normalization_uses_studio_without_changing_an_ordinary_piece():
    from abook.text_processing import normalize_vocalizations_for_tts
    assert cap.bounded_pieces(['ồ' * 15023], 140) == [[normalize_vocalizations_for_tts('ồ' * 15023)]]
    assert cap.bounded_pieces(['a' * 5000], 140) == [[normalize_vocalizations_for_tts('a' * 5000)]]
    pieces = ['Xin chào, đây là một câu thử.', 'Câu thứ hai.']
    assert cap.bounded_pieces(pieces, 256) == [pieces]


def test_cache_refusal_rephonemizes_halves_in_order_with_no_loss():
    calls, accepted = [], []
    text = ' '.join(f'từ{i}' for i in range(32))
    def infer(ph):
        calls.append(ph)
        if len(ph) > 40:
            raise ValueError('does not fit a cache')
        accepted.extend(ph.split())
        return np.full(64, .2, np.float32)
    wave, _ = cap.read_unit([text], text, 256, 24000, lambda group, **kw: ' '.join(group), infer)
    assert accepted == text.split()
    assert len(calls) > 1 and wave.size > 0


@pytest.mark.parametrize('error', [ValueError('broken model'), MemoryError('out of memory'), VoiceError('cancelled', 'cancelled')])
def test_short_oom_cancellation_and_unrelated_errors_propagate(error):
    calls = []
    def infer(ph):
        calls.append(ph)
        raise error
    with pytest.raises(type(error)):
        cap.read_unit(['Xin chào.'], 'Xin chào.', 140, 24000, lambda g, **kw: ' '.join(g), infer)
    assert len(calls) == 1


def test_refusal_has_a_finite_depth():
    calls = []
    def infer(ph):
        calls.append(ph)
        raise ValueError('does not fit a cache')
    with pytest.raises(ValueError, match='does not fit'):
        cap.read_unit(['ab' * 1000], '', 256, 24000, lambda g, **kw: ' '.join(g), infer)
    assert len(calls) <= VIENEU_HALVING_DEPTH + 1


@pytest.mark.parametrize('tier', ['turbo', 'nano'])
@pytest.mark.parametrize('text', ['Chiếc thuyền nhỏ trôi giữa dòng sông. Trời hôm nay rất đẹp.', 'Một ' * 34 + '. Ừ.'],
                         ids=['ordinary', 'short-neighbour'])
def test_ordinary_pcm_seed_calls_and_word_spans_remain_byte_identical(monkeypatch, tmp_path, tier, text):
    calls = []
    class Engine:
        SAMPLE_RATE = 24000
        def infer(self, ph, speaker, extra, *, rng=None, seed=None):
            random = rng if rng is not None else np.random.RandomState(seed)
            audio = random.uniform(-.2, .2, 800).astype(np.float32)
            calls.append((ph, audio.tobytes()))
            return audio
    engine = Engine()
    installed = vieneu.Installed(tmp_path)
    preset = {'speaker_emb': [0], 'style': [[0]]}
    monkeypatch.setattr(ve, 'phonemize', lambda pieces, **kw: ' '.join(pieces))
    provider = vieneu.VieneuProvider(lambda: installed, engines=lambda *_: engine)
    events = []
    with hearing(lambda *args: events.append(args)):
        wave, rate, toks, parts, spans = provider._speak(tier, 'test', installed, preset, text)
    expected = engine.infer(' '.join(parts[0].pieces), np.array([0]), None,
                            rng=np.random.RandomState(vieneu.seed_of(tier, 'test', ' '.join(parts[0].pieces))))
    assert wave.tobytes() == expected.tobytes()
    assert calls[0] == calls[1]
    assert spans == [(0, len(expected))] and len(events) == 1
    assert events[0][0].tobytes() == wave.tobytes()


def test_long_oom_halves_but_short_halves_keep_the_same_input():
    calls = []
    text = 'abcd' * 70
    def infer(ph):
        calls.append(ph)
        if len(ph) > 256:
            raise MemoryError('out of memory')
        return np.full(100, .2, np.float32)
    wave, _ = cap.read_unit([text], text, 300, 24000, lambda g, **kw: ' '.join(g), infer)
    assert len(calls) == 3
    assert ''.join(calls[1:]).replace(' ', '') == text
    assert wave.size > 0


def test_retry_stream_reports_one_complete_display_unit(monkeypatch, tmp_path):
    class Engine:
        SAMPLE_RATE = 24000
        def infer(self, ph, *args, **kw):
            if len(ph) > 20:
                raise ValueError('does not fit a cache')
            return np.full(100, .2, np.float32)
    monkeypatch.setattr(ve, 'phonemize', lambda pieces, **kw: ' '.join(pieces))
    installed = vieneu.Installed(tmp_path)
    provider = vieneu.VieneuProvider(lambda: installed, engines=lambda *_: Engine())
    events = []
    with hearing(lambda *args: events.append(args)):
        wave, _, _, parts, spans = provider._speak('nano', 'test', installed, {'speaker_emb': [0], 'style': [[0]]},
                                                   'Một hai ba bốn năm sáu bảy tám chín mười.')
    assert len(parts) == len(events) == len(spans) == 1
    assert wave.tobytes() == events[0][0].tobytes()
