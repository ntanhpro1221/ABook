"""Hồi quy a89: ghi theo nhóm và khớp cách đọc của người nghe."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json
import unicodedata

import pytest

from abook import listener_overrides as lo
from abook.webui import server
from abook.webui import book_wishes
from tests.test_book_wishes import _producer, _line


@pytest.mark.parametrize('reject_second', [False, True])
def test_review_redo_writes_one_group(tmp_path: Path, monkeypatch, reject_second):
    """Phán quyết cả nhóm nguyên tử; retake ghi đúng một nhóm khi được nhận."""
    def review(_project, stable_ids, *_args, **_kwargs):
        if reject_second and 's2' in stable_ids:
            raise ValueError('Bản thu đã đổi')

    handler = object.__new__(server.Handler)
    handler.app = SimpleNamespace(
        _mutating=lambda: None, _book=lambda _value: tmp_path,
        _editable=lambda _value: tmp_path,
        reviews=SimpleNamespace(get=lambda _project: {}, set_many=review))
    handler._body = lambda: {'verdict': 'redo', 'lines': [
        {'stableId': 's1'}, {'stableId': 's2'}, {'stableId': 'missing'}]}
    handler._send_json = Mock()
    monkeypatch.setattr(server.packages, 'is_package', lambda _project: False)
    monkeypatch.setattr(server.store, 'segment_text_sha256',
                        lambda _project, sid: {'s1': 'sha1', 's2': 'sha2'}.get(sid))
    write = Mock(wraps=lo._write)
    batch = Mock(wraps=lo.request_retakes)
    monkeypatch.setattr(lo, '_write', write)
    monkeypatch.setattr(lo, 'request_retakes', batch)
    if reject_second:
        with pytest.raises(server.ApiError, match='Bản thu đã đổi'):
            handler.post_review({}, 'book')
    else:
        handler.post_review({}, 'book')
        assert handler._send_json.call_args.args[1]['lines'] == 2
    if reject_second:
        assert batch.call_count == write.call_count == 0
        assert lo.read_overrides(tmp_path) == {}
        return
    expected = [('s1', 'sha1'), ('s2', 'sha2')]
    assert batch.call_count == 1
    assert batch.call_args.args == (tmp_path, expected)
    assert write.call_count == 1
    assert set(lo.read_overrides(tmp_path)['retakes']) == {sid for sid, _sha in expected}


def test_fold_retake_operation_is_one_receipt_and_one_group(tmp_path, monkeypatch):
    project, db = _producer(tmp_path)
    lines = [_line(db, f'c1s{i}') for i in (1, 2, 3)]
    wishes = {'retakes': {sid: {'text_sha256': sha, 'requested_at': 5.0,
                              'operation_id': 'a' * 32} for sid, sha in lines}}
    receipt_write = Mock(wraps=book_wishes.atomic_write_json)
    batch = Mock(wraps=lo.request_retakes)
    override_write = Mock(wraps=lo._write)
    monkeypatch.setattr(book_wishes, 'atomic_write_json', receipt_write)
    monkeypatch.setattr(lo, 'request_retakes', batch)
    monkeypatch.setattr(lo, '_write', override_write)
    assert book_wishes.fold(project, wishes, now=100.) == {'requests': 3, 'skipped': 0}
    assert receipt_write.call_count == batch.call_count == override_write.call_count == 1
    assert batch.call_args.args == (project, lines)
    before = lo.read_overrides(project)
    assert book_wishes.fold(project, wishes, now=200.) == {'requests': 0, 'skipped': 0}
    assert lo.read_overrides(project) == before
    assert receipt_write.call_count == batch.call_count == override_write.call_count == 1


@pytest.mark.parametrize('when', ['after_receipt', 'before_override', 'after_override'])
def test_fold_retake_group_recovers_without_loss_or_duplicate(tmp_path, monkeypatch, when):
    project, db = _producer(tmp_path)
    lines = [_line(db, f'c1s{i}') for i in (1, 2, 3)]
    wishes = {'retakes': {sid: {'text_sha256': sha, 'requested_at': 5.0,
                              'operation_id': 'a' * 32} for sid, sha in lines}}
    receipt_write, override_write = book_wishes.atomic_write_json, lo._write

    def receipt_then_crash(*args, **kwargs):
        receipt_write(*args, **kwargs)
        raise SystemExit('after receipt')

    def override_crash(*args, **kwargs):
        if when == 'after_override':
            override_write(*args, **kwargs)
        raise SystemExit(when)

    with monkeypatch.context() as patch:
        if when == 'after_receipt':
            patch.setattr(book_wishes, 'atomic_write_json', receipt_then_crash)
        else:
            patch.setattr(lo, '_write', override_crash)
        with pytest.raises(SystemExit):
            book_wishes.fold(project, wishes, now=100.)
    if when == 'after_override':
        assert set(lo.read_overrides(project)['retakes']) == {sid for sid, _sha in lines}
    book_wishes.fold(project, wishes, now=200.)
    retakes = lo.read_overrides(project)['retakes']
    assert {sid: item['requested_at'] for sid, item in retakes.items()} == {sid: 100. for sid, _sha in lines}
    lo.cancel_retake(project, lines[0][0])
    assert book_wishes.fold(project, wishes, now=300.)['requests'] == 0
    assert lines[0][0] not in lo.read_overrides(project)['retakes']


@pytest.mark.parametrize('surface', ['Nguyễn', 'NGUYỄN', '  Nguyễn  ',
    unicodedata.normalize('NFD', 'Nguyễn'), 'Nguy\u200bễn', 'Ngu\u200cyễn',
    'Nguyễn\ufeff', 'Nguyễn\u2060', 'Nguy\u00adễn', 'Nguy\u034fễn'])
def test_surface_key_matches_composed_book_word(surface):
    assert lo.surface_key(surface) == 'nguyễn'


@pytest.mark.parametrize('surface', ['Hailkes', ' Lan, ', '“Lan”', 'Straße', 'A  B', 'ĐỨC', 'a-b'])
def test_ordinary_surface_key_keeps_its_meaning(surface):
    assert lo.surface_key(surface) == ' '.join(surface.strip().casefold().split())


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('surface', [unicodedata.normalize('NFD', 'Nguyễn'), 'Nguy\u200bễn'])
def test_pronunciation_matches_book_and_preserves_saved_wish(tmp_path, surface, legacy):
    from tests.test_listener_overrides import _book, _Pipeline
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text='Nguyễn gật đầu.' WHERE stable_id='c1s0'")
        conn.execute("UPDATE segments SET text='NGUYỄN!' WHERE stable_id='c3s0'")
        conn.execute("UPDATE segments SET text='Nguyễnn đứng dậy.' WHERE stable_id='c3s1'")
    db.finalize_casting()
    if legacy:
        key = ' '.join(surface.strip().casefold().split())
        lo.overrides_path(paths.root).write_text(json.dumps({'version': 1, 'pronunciations': {
            key: {'surface': surface, 'spoken_form': 'Nguyên', 'requested_at': 1.}}}, ensure_ascii=False), encoding='utf-8')
    else:
        lo.request_pronunciation(paths.root, surface, 'Nguyên', now=1.)
    saved = lo.overrides_path(paths.root).read_bytes()
    pipeline = _Pipeline(paths, db)
    assert pipeline._apply_listener_overrides() == {1, 3}
    rows = {row['stable_id']: row for row in db.list_segments()}
    assert rows['c1s0']['status'] != 'verified' and rows['c3s0']['status'] != 'verified'
    assert rows['c3s1']['status'] == 'verified'
    assert any(row['normalized_surface'] == 'nguyễn' for row in db.list_pronunciations(0.))
    assert pipeline._apply_listener_overrides() == set()
    assert lo.overrides_path(paths.root).read_bytes() == saved


def test_pipeline_reads_empty_overrides_once_at_sweep_start(tmp_path, monkeypatch):
    from abook import pipeline as pipeline_module
    from tests.test_listener_overrides import _book, _Pipeline
    paths, db = _book(tmp_path)
    db.finalize_casting()
    read = Mock(return_value={})
    monkeypatch.setattr(pipeline_module, 'read_overrides', read)
    assert _Pipeline(paths, db)._apply_listener_overrides() == set()
    read.assert_called_once_with(paths.root)


def test_fold_operations_keep_separate_stamps_and_legacy_done_receipts(tmp_path):
    project, db = _producer(tmp_path)
    lines = [_line(db, f'c1s{i}') for i in (1, 2, 3)]
    wishes = {'retakes': {sid: {'text_sha256': sha, 'requested_at': 5. + i,
                              'operation_id': chr(97+i) * 32} for i, (sid, sha) in enumerate(lines)}}
    receipt = {'a' * 32: {'at': 10., 'lines': {lines[0][0]: {'sha': lines[0][1], 'done': True}}}}
    (project / 'retake_receipts.json').write_text(json.dumps(receipt), encoding='utf-8')
    assert book_wishes.fold(project, wishes, now=100.) == {'requests': 2, 'skipped': 0}
    retakes = lo.read_overrides(project)['retakes']
    assert lines[0][0] not in retakes
    assert [retakes[sid]['requested_at'] for sid, _sha in lines[1:]] == [100.001, 100.002]
    before = lo.read_overrides(project)
    assert book_wishes.fold(project, wishes, now=200.)['requests'] == 0
    assert lo.read_overrides(project) == before


def test_fold_pending_group_does_not_overwrite_newer_request(tmp_path, monkeypatch):
    project, db = _producer(tmp_path)
    sid, sha = _line(db, 'c1s1')
    wishes = {'retakes': {sid: {'text_sha256': sha, 'requested_at': 5., 'operation_id': 'a' * 32}}}
    with monkeypatch.context() as patch:
        patch.setattr(lo, '_write', Mock(side_effect=SystemExit('before commit')))
        with pytest.raises(SystemExit):
            book_wishes.fold(project, wishes, now=100.)
    lo.request_retake(project, sid, sha, now=150.)
    book_wishes.fold(project, wishes, now=200.)
    assert lo.read_overrides(project)['retakes'][sid]['requested_at'] == 150.
    assert book_wishes.fold(project, wishes, now=300.)['requests'] == 0
