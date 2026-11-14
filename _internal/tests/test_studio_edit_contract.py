"""Android-generated request cases against the real web handlers; all sample sentences are original."""
import json
from pathlib import Path

import pytest

from abook.config import build_settings, save_settings
from abook import aliases, names
from abook.listener_overrides import read_overrides
from abook.webui.actions import FakeRunner
from abook.webui.library import Preferences, book_id
from abook.webui.server import App, Server
from tests import test_listener_speakers as speakers
from tests.test_webui_listen_and_sync import _request

CASES = json.loads((Path(__file__).parent / 'fixtures/studio_edits/cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', [c for c in CASES if not c.get('transport')], ids=lambda c: c['id'])
def test_android_requests_persist_without_editing_source(tmp_path, monkeypatch, case):
    monkeypatch.setattr(speakers, 'LINES', [
        ('c1s0', 'narration', 'NARRATOR', 'Đèn sân đã sáng.'),
        ('c1s1', 'dialogue', 'Lucien', 'Xin đặt ghế ở đây.'),
        ('c1s2', 'dialogue', 'Lucien', 'Tôi sẽ lấy thêm nước.'),
        ('c1s3', 'dialogue', 'NATASHA', 'Cảm ơn, ghế đã đủ rồi.'),
        ('c1s4', 'dialogue', 'UNKNOWN', 'Cổng phía đông còn mở.'),
    ])
    paths, db = speakers._book(tmp_path)
    save_settings(paths.settings, build_settings())
    original = (paths.root / 'sources/001.txt').read_bytes()
    with db.connect() as connection:
        before = list(connection.execute('SELECT stable_id,text,text_sha256 FROM segments ORDER BY seq'))
        before = [tuple(row) for row in before]
    prefs = Preferences(tmp_path / 'prefs/preferences.json')
    prefs.update({'libraryRoot': str(tmp_path)})
    app = App(preferences=prefs, runner=FakeRunner(), token='fixture')
    server = Server(app, port=0).start()
    url = '/api/books/' + book_id(paths.root)

    def call(endpoint, body):
        status, raw, _ = _request(server.port, 'POST', url + '/' + endpoint, headers={'X-Ebook-Token': 'fixture'}, body=body)
        return status, json.loads(raw)

    try:
        stamp = None
        if case['op'] == 'unmerge':
            status, answer = call('characters/merge', {'from': 'LUCIEN', 'into': 'NATASHA'})
            assert status == 200, answer
            stamp = answer['requestedAt']
        for step in case['expected']:
            body = dict(step['body'])
            if stamp is not None:
                body['requestedAt'] = stamp
            status, answer = call(step['endpoint'], body)
            assert status == case.get('status', 200), answer
            if case['id'] == 'no-voice':
                assert answer['error'] == case['error']
        assert (paths.root / 'sources/001.txt').read_bytes() == original
        with db.connect() as connection:
            assert [tuple(row) for row in connection.execute('SELECT stable_id,text,text_sha256 FROM segments ORDER BY seq')] == before
        # A fresh reader sees the exact wishes, separate from unchanged production rows.
        wishes = read_overrides(paths.root)
        if case.get('status', 200) != 200:
            assert not wishes.get('speakers')
        elif case['op'] == 'assign':
            assert set(wishes['speakers']) == set(case['ids'])
            assert {w['speaker'] for w in wishes['speakers'].values()} == {case.get('speaker', 'NATASHA')}
        elif case['op'] == 'delivery':
            assert wishes['lines']['c1s0']['kind'] == case['kind']
            assert wishes['speakers']['c1s0']['speaker'] == 'NATASHA'
        elif case['op'] == 'rename':
            assert names.shown(paths.root, 'LUCIEN') == 'Bác Trực'
        elif case['op'] == 'gender':
            assert wishes['voices']['LUCIEN']['gender'] == 'female'
        elif case['op'] == 'merge':
            assert set(wishes['speakers']) == {'c1s1', 'c1s2'}
            assert aliases.load(paths.root) == {aliases.key('LUCIEN'): 'NATASHA'}
        elif case['op'] == 'unmerge':
            assert not wishes.get('speakers') and not aliases.load(paths.root)
    finally:
        server.stop()
        app.close()


def test_parity_reads_unaccented_shared_tuple_labels():
    from scripts import ui_parity
    scan = ui_parity.Scan()
    ui_parity.web_scan_file(Path(__file__).parents[1] / 'ui/src/studio/ScriptTab.tsx', scan)
    assert any(item.text == 'Vui' and item.kind == 'shared-copy' for item in scan.items)
