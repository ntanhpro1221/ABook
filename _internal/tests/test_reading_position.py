from abook.webui.listening import Listening, merge_states
from types import SimpleNamespace
import pytest
from abook.webui.listening import StalePlayback


def test_reading_keeps_anchor_timestamp_and_newest_wins(tmp_path):
    store = Listening(tmp_path / 'listening.json')
    anchor = {'segment': 2, 'charOffset': 0, 'textHash': 'fnv1a64:0123456789abcdef', 'paragraphHash': 'fnv1a64:0000000000000001'}
    rev = {'counter': 2, 'node': 'reader'}
    store.set_reading('book', 4, 2, at=200, anchor=anchor, rev=rev)
    with pytest.raises(StalePlayback):
        store.set_reading('book', 1, 0, at=300, rev={'counter': 1, 'node': 'reader'})
    expected = {'chapterId': 4, 'index': 2, 'at': 200, 'anchor': anchor, 'rev': rev}
    assert store.get('book')['reading'] == expected
    assert Listening(tmp_path / 'listening.json').get('book')['reading'] == expected
    assert merge_states({'reading': expected}, {'reading': {'chapterId': 1, 'index': 0, 'at': 100, 'rev': {'counter': 1, 'node': 'reader'}}})['reading'] == expected


def test_reading_flush_targets_held_profile(tmp_path):
    store = Listening(tmp_path / 'listening.json')
    first = store.create_record('book', 'Bạn')['id']
    second = store.create_record('book', 'Bạn khác')['id']
    store.activate('book', second)
    store.set_reading('book', 4, 10, at=100, record=first)
    assert 'reading' not in store.get('book')
    store.activate('book', first)
    assert store.get('book')['reading']['chapterId'] == 4


def test_reading_http_passes_anchor_timestamp_and_profile_without_socket():
    from abook.webui.server import Handler
    saved = []
    body = {'chapterId': 4, 'index': 20, 'at': 100, 'record': 'r-0123456789abcdef', 'anchor': {'segment': 20}, 'rev': {'counter': 1, 'node': 'reader'}}
    fake = SimpleNamespace(app=SimpleNamespace(_listenable=lambda value: None,
        listening=SimpleNamespace(set_reading=lambda *args, **kwargs: saved.append((args, kwargs)))),
        _body=lambda: body, _send_json=lambda *args: None)
    Handler.post_reading(fake, {}, 'book')
    assert saved == [(('book', 4, 20), {'at': 100, 'record': body['record'], 'anchor': body['anchor'], 'rev': body['rev']})]


def test_script_versions_follow_audio_and_word_timings(tmp_path, monkeypatch):
    from abook.webui import listen_view
    chapter = dict(id=1, index=0, displayTitle='Một', subtitle='', fullTitle='Một', seconds=100, playable=True, completedAt=123)
    monkeypatch.setattr(listen_view.store, 'chapters', lambda root: [chapter])
    monkeypatch.setattr(listen_view.word_timing, 'stamp', lambda root: 'w1')
    first = listen_view.chapters(tmp_path)
    assert first[0]['audioVersion'] == '123'
    assert first[0]['wordsVersion'] == 'w1'
    monkeypatch.setattr(listen_view.word_timing, 'stamp', lambda root: 'w2')
    assert listen_view.chapters(tmp_path)[0]['wordsVersion'] == 'w2'
