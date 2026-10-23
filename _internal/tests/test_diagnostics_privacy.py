"""Regression cases from a115/review_probe.py, exercising the real bundle/App method."""
import io
import json
import types
import zipfile

import pytest

from abook.webui import diagnostics, remote_books
from abook.webui.server import App


@pytest.mark.parametrize("private", [
    '"key":"0123456789abcdef0123456789abcdef"',
    'methodName: pair, methodData: {"code":"123456"}',
    'apiKey=short', 'secret=x', 'password=x', 'code=123456', 'pair 123456',
    'Authorization: Bearer private-token-123456789',
    '/c/' + 'ab' * 16 + '.mp3', 'ab' * 32,
    r'C:\Users\Alice\Private\novel.txt',
    '/storage/emulated/0/Books/private.mp3', '/data/user/0/com.app/files/key.txt',
    'content://com.provider/private/book.mp3',
    '192.168.123.9', '2001:db8::1234', '::1', '::ffff:192.168.1.1',
    '192.168.123.9.', '2001:db8::1234.', 'pairing code is 123456', 'mã ghép là 123456',
])
def test_private_values_are_removed_but_error_and_stack_survive(private):
    text = f'IllegalStateException: {private}\n    at vn.abook.Playback.play(Playback.kt:306)'
    clean = diagnostics.redact(text)
    # The whole sensitive fixture must disappear; stack frames and error types remain.
    assert private not in clean
    assert 'IllegalStateException:' in clean
    assert 'at vn.abook.Playback.play(Playback.kt:306)' in clean


def test_actual_own_diagnostics_scrubs_all_metadata_and_log_strings(tmp_path):
    secret = 'fixture-private-bearer-123456789'
    fingerprint = 'ab' * 32
    private_path = r'C:\Users\Alice\Private\novel.txt'
    ip = '192.168.123.9'
    log = tmp_path / 'logs'
    log.mkdir()
    (log / 'host.log').write_text(f'FileNotFoundError: {private_path}\nconnect {ip}\nBearer {secret}', encoding='utf-8')
    app = types.SimpleNamespace(version='Bearer ' + secret, sync_server=None, sync_error='Bearer ' + secret,
        computers=types.SimpleNamespace(list=lambda: [{'name': 'Bearer ' + secret, 'kind': 'phone',
            'lastSeen': 1, 'error': 'token=' + secret + ' fingerprint=' + fingerprint}]),
        devices=types.SimpleNamespace(list=lambda: []),
        preferences=types.SimpleNamespace(path=tmp_path / 'preferences.json', get=lambda: {}))
    with zipfile.ZipFile(io.BytesIO(App.own_diagnostics(app))) as archive:
        text = '\n'.join(archive.read(name).decode('utf-8') for name in archive.namelist())
        info = json.loads(archive.read('thong-tin.json'))
    assert info['sync']['error'] == 'Bearer ***'
    for private in (secret, fingerprint, private_path, ip):
        assert private not in text
    assert 'FileNotFoundError' in text


def test_nested_bundle_metadata_is_scrubbed(tmp_path):
    info = {'nested': [{'error': {'message': 'Bearer private-token-123456789'}, 'key': 'private-azure-key'}]}
    with zipfile.ZipFile(io.BytesIO(diagnostics.bundle(info, None))) as archive:
        data = archive.read('thong-tin.json').decode()
        assert 'private-token' not in data
        assert 'private-azure-key' not in data


def test_address_lists_hide_names_and_ipv6_in_raw_logs_and_structured_reports():
    text = 'routes addresses=[{"address":"private-phone.local:47630","lastSuccess":12},{"address":"[fd00::7]:47630"}] failed'
    clean = diagnostics.redact(text)
    assert 'private-phone' not in clean and 'fd00' not in clean
    assert 'failed' in clean
    assert diagnostics.redact('addresses=[private-phone.local:47630, [fd00::7]:47630] failed') == 'addresses=*** failed'
    assert diagnostics.redact_report({'nested': {'addresses': ['private-phone.local:47630']}}) == {'nested': {'addresses': '***'}}


def test_pretty_and_truncated_address_lists_are_scrubbed_in_log_bundle(tmp_path):
    payload = json.dumps({"addresses": [{"address": "private-phone.local:47630", "note": 'brackets ] [ and escaped " quote'}]}, indent=2)
    for text in (payload + "\nfinished", payload[:-8], payload.split("[", 1)[1]):
        safe = diagnostics.redact(text)
        assert "private-phone" not in safe
    assert "finished" in diagnostics.redact(payload + "\nfinished")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "host.log").write_text(payload, encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(diagnostics.bundle({}, logs))) as archive:
        assert b"private-phone" not in archive.read("nhat-ky/host.log")


def test_phone_report_is_scrubbed_at_the_shared_network_boundary(monkeypatch):
    monkeypatch.setattr(remote_books, '_COMPUTERS', types.SimpleNamespace(get=lambda _: {
        'host': '127.0.0.1', 'port': 12345, 'token': 'fixture', 'name': 'phone',
        'addresses': [{'address': '127.0.0.1:12345', 'lastSuccess': 0}]}))
    monkeypatch.setattr(remote_books, '_request', lambda *args, **kwargs: json.dumps({
        'playback': {'error': 'IllegalStateException: Bearer private-token-123456789'},
        'exitReasons': [{'description': r'C:\Users\Alice\Private\novel.txt', 'trace': 'connect 2001:db8::1'}],
        'sync': {'error': '"code":"123456"'}, 'secret': 'private-plain-value',
    }).encode())
    report = remote_books.diagnostics('paired-device')
    text = json.dumps(report)
    for private in ('private-token', 'Alice', '2001:db8', '123456', 'private-plain-value'):
        assert private not in text
    assert 'IllegalStateException' in text
