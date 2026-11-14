"""Original examples: channel evidence and explicitly chosen IDs, without inference."""
import json
import sqlite3
from pathlib import Path

import pytest

from abook.listener_overrides import read_overrides, request_speakers
from abook.webui.voice_review import nearby_dialogue
from abook.webui.work_items import work_items
from tests.test_work_items import make_book


def review_book(tmp_path, cue='Giọng nói từ bộ đàm vọng tới.'):
    project = make_book(tmp_path)
    with sqlite3.connect(project / 'project.sqlite3') as db:
        db.execute("UPDATE segments SET text='Một buổi tập yên tĩnh.'")
        db.execute("UPDATE segments SET text=? WHERE id=1", (cue,))
        db.execute("UPDATE segments SET kind='thought' WHERE id=4")
        db.execute("UPDATE segments SET text='Chờ tôi ở sân nhé.' WHERE id=2")
        db.execute("UPDATE segments SET text='Tôi đang đứng ngoài sân.' WHERE id=3")
        db.execute("UPDATE segments SET text='Tôi sẽ tới ngay.' WHERE id=5")
    return project


def card(project, kind='caller'):
    return next(item for item in work_items(project)['items'] if item['kind'] == kind)


def test_opening_context_preserves_db_sources_audio_and_wishes(tmp_path):
    project = review_book(tmp_path)
    audio = project / 'unchanged.wav'
    audio.write_bytes(b'original-synthetic-audio-marker')
    source = project / 'source.txt'
    source.write_text('Buổi tập bắt đầu.', encoding='utf-8')
    before = {path: path.read_bytes() for path in (project / 'project.sqlite3', audio, source)}
    item = card(project)
    assert item['lines'] == [{'stableId': 'b', 'textSha256': 'sha-b'}]
    assert [line['stableId'] for line in item['contextLines']] == ['b', 'c', 'e', 'f', 'g']
    assert item['suggested'] is False and 'confidence' not in item
    assert not read_overrides(project).get('speakers')
    assert all(path.read_bytes() == content for path, content in before.items())


def test_alternating_sides_are_context_not_a_single_inferred_person(tmp_path):
    project = review_book(tmp_path)
    item = card(project)
    assert {x['speaker'] for x in item['contextExamples']} >= {'Heidi', 'Lucien'}
    selected = [line for line in item['contextLines'] if line['stableId'] in {'b', 'e'}]
    request_speakers(project, [(x['stableId'], x['textSha256']) for x in selected], 'LUCIEN', now=10)
    assert set(read_overrides(project)['speakers']) == {'b', 'e'}


def test_private_decisions_including_stale_source_are_not_range_candidates(tmp_path):
    project = review_book(tmp_path)
    request_speakers(project, [('c', 'sha-c')], 'HEIDI', now=10)
    with sqlite3.connect(project / 'project.sqlite3') as db:
        db.execute("UPDATE segments SET text_sha256='changed' WHERE stable_id='c'")
    assert 'c' not in {x['stableId'] for x in card(project)['contextLines']}


def test_stale_selected_source_rejects_the_entire_request(tmp_path):
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = review_book(tmp_path)
    selected = card(project)['contextLines'][:2]
    with sqlite3.connect(project / 'project.sqlite3') as db:
        db.execute("UPDATE segments SET text_sha256='changed' WHERE stable_id='c'")
    prefs = Preferences(tmp_path / 'prefs.json')
    prefs.update({'libraryRoot': str(tmp_path)})
    server = Server(App(preferences=prefs, runner=FakeRunner(), token='t', listening=Listening(tmp_path / 'listen.json')), port=0).start()
    try:
        status, _, _ = _request(server.port, 'POST', f'/api/books/{book_id(project)}/speaker',
                                headers={'X-Ebook-Token': 't'}, body={'lines': selected, 'speaker': 'LUCIEN'})
        assert status == 400 and not read_overrides(project).get('speakers')
    finally:
        server.stop()


def test_context_is_bounded_to_the_chapter_and_only_complete_dialogue_ids():
    rows = [dict(chapter_id=chapter, seq=seq, kind=kind, stable_id=sid, text_sha256=sha)
            for chapter, seq, kind, sid, sha in [(1, 1, 'dialogue', 'a', 'sha'), (2, 1, 'dialogue', 'b', 'sha'),
                (1, 2, 'thought', 'c', 'sha'), (1, 10, 'dialogue', 'd', 'sha'), (1, 3, 'dialogue', 'e', '')]]
    assert nearby_dialogue(rows[0], rows, {}) == [rows[0]]


def test_shared_contract_keeps_only_selected_ids_in_original_groups():
    item = json.loads((Path(__file__).parent / 'fixtures/voice_review/contract.json').read_text(encoding='utf-8'))
    ids = set(item['selectedIds'])
    groups = [{**group, 'lines': [x for x in group['lines'] if x['stableId'] in ids]} for group in item['keepGroups']]
    assert [(x['speaker'], [line['stableId'] for line in x['lines']]) for x in groups if x['lines']] == [('MAI', ['near', 'far'])]
