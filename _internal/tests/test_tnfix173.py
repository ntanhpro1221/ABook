"""Original class tests shared with Android; source and book readings stay intact."""
import json
from pathlib import Path

import pytest

from abook.readaloud import vieneu
from abook.webui.word_timing import tokens
from scripts.tn_benchmark import SpeechBoundaries, normalize

CASES = json.loads((Path(__file__).parent / 'fixtures/readaloud/tnfix173/cases.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def boundaries():
    with SpeechBoundaries() as speech:
        yield speech


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_spoken_tnfix173_shared_with_android(case, boundaries):
    shown, parts = vieneu.units(case['text'], 256, case.get('origin'), direct_english=True)
    assert shown == tokens(case['text'])
    assert normalize(' '.join(piece for part in parts for piece in part.pieces if piece)) == normalize(case['spoken'])
    outputs, _ = boundaries.read(case)
    assert normalize(outputs['studio']) == normalize(case['studio'])


@pytest.mark.parametrize('text,surface', [
    ('Pin 12 V.', 'V'), ('Hẹn 6 AM.', 'AM'),
    ('Mã QZ76.', 'QZ76'), ('Chọn 4–9 nắp.', '4–9'),
])
def test_spoken_tnfix173_explicit_book_reading_wins(text, surface):
    output = vieneu.spoken_tokens(tokens(text), readings={surface:'cách đọc riêng'}, direct_english=True)
    assert 'cách-đọc-riêng' in ' '.join(output)


@pytest.mark.parametrize('text,expected', [
    ('Nguồn 1.000V.', 'Nguồn một nghìn vôn.'),
    ('Tệp 1,000 MB.', 'Tệp một nghìn mê ga bai.'),
    ('Ổ 0.5GB.', 'Ổ không phẩy năm ghi ga bai.'),
    ('Mức 15dB.', 'Mức mười lăm đề xi ben.'),
    ('Chuông 12 AM.', 'Chuông mười hai giờ đêm.'),
    ('Chuông 12 PM.', 'Chuông mười hai giờ trưa.'),
])
def test_spoken_tnfix173_grouped_joined_units_and_clock_boundaries(text, expected, boundaries):
    from abook.readaloud.vieneu_engine import phonemize
    from scripts.tn_benchmark import normalize_phonemes, studio_phonemes

    outputs, phones = boundaries.read({'text':text, 'category':'unit'})
    assert all(normalize(value) == normalize(expected) for value in outputs.values())
    assert normalize_phonemes(phones['nghe_ngay']) == normalize_phonemes(phonemize([expected], source=expected))
    assert normalize_phonemes(phones['studio']) == normalize_phonemes(studio_phonemes(expected, expected))
