"""Original native/web sentence cases exercise the existing wish persistence layer."""
import json
from pathlib import Path

import pytest

from abook.webui import book_edits, book_wishes

CASES = json.loads((Path(__file__).parent / 'fixtures/player_line/cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES, ids=lambda row: row['name'])
def test_player_requests_persist_without_touching_source_or_audio(tmp_path, case):
    source = tmp_path / 'original.txt'
    source.write_text(case['source']['text'], encoding='utf-8')
    audio = tmp_path / 'original.audio'
    audio.write_bytes(b'original synthetic test audio marker')
    before = source.read_bytes(), audio.read_bytes()
    for step in case['expectedSteps']:
        body = step['body']
        if step['endpoint'] == 'speaker':
            refs = [(ref['stableId'], ref['textSha256']) for ref in body['lines']]
            book_wishes.request_speakers(tmp_path, refs, body['speaker'], now=10, new_gender=body.get('newGender', ''))
        elif step['endpoint'] == 'line':
            fields = {key: value for key, value in body.items() if key not in {'stableId', 'textSha256', 'seen'}}
            book_wishes.request_line(tmp_path, body['stableId'], body['textSha256'], now=10, **fields)
        else:
            book_wishes.request_retakes(tmp_path, [(case['source']['stableId'], case['source']['textSha256'])], now=10)
    reopened = json.loads((tmp_path / 'edits.json').read_text(encoding='utf-8')) if case['expectedSteps'] else {}
    assert book_edits.load(tmp_path).get('wishes', {}) == reopened.get('wishes', {})
    for step in case['expectedSteps']:
        endpoint, body = step['endpoint'], step['body']
        section = {'speaker': 'speakers', 'line': 'lines', 'review': 'retakes'}[endpoint]
        entry = reopened['wishes'][section][case['source']['stableId']]
        assert entry['text_sha256'] == case['source']['textSha256']
        if endpoint == 'speaker':
            assert entry['speaker'] == body['speaker']
            if body.get('newGender'): assert entry['new'] == {'gender': body['newGender']}
        if endpoint == 'line':
            for field in ('kind', 'emotion', 'intensity', 'spoken'):
                if field in body: assert entry[field] == body[field]
    assert (source.read_bytes(), audio.read_bytes()) == before
