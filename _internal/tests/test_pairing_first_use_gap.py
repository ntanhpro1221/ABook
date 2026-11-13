"""Lần ghép đầu không còn là TOFU (soát bảo mật 12-11): máy chen giữa trả chứng chỉ của nó thì mã 6 số KHÔNG được gửi - nhập mã tay
thì phải so mã nhận máy trước (PairConfirm), dán chuỗi ghép thì chứng chỉ phải khớp vân tay trong chuỗi."""
import json
from contextlib import contextmanager
from io import BytesIO

import pytest

from abook.webui import remote_books


def test_pairing_string_and_manual_display_match_android():
    expected = "0123456789abcdef" * 4
    assert remote_books.parse_pairing(remote_books.pairing_string("482913", expected)) == ("482913", expected)
    assert remote_books.parse_pairing("482 913") == ("482913", None)
    assert remote_books.short_fingerprint(expected) == "0123 4567 89AB CDEF"
    assert remote_books.parse_pairing("482913-" + expected[:63]) == ("", None)


def test_manual_code_requires_explicit_confirmation_without_sending_http(tmp_path, monkeypatch):
    expected = "0123456789abcdef" * 4
    sent = []
    monkeypatch.setattr(remote_books, "_probe", lambda *a: expected)
    monkeypatch.setattr(remote_books, "_exchange", lambda *a, **k: sent.append(a))
    computers = remote_books.Computers(tmp_path / "computers.json")
    with pytest.raises(remote_books.PairConfirm) as error:
        computers.pair("127.0.0.1:20001", "482913", "Client")
    assert error.value.fingerprint == expected
    assert sent == []
    assert not computers.path.exists()


def test_first_use_relay_must_not_become_the_pinned_computer(tmp_path, monkeypatch):
    fingerprint = "a" * 64
    class Answer(BytesIO):
        status = 200
        length = None
        def getheader(self, name, default=None):
            return default
    class Relay:
        peer_fingerprint = fingerprint
        sock = None
        sent = None
        def request(self, method, path, body=None, headers=None):
            self.sent = json.loads(body)
        def getresponse(self):
            return Answer(json.dumps({"token": "relayed-token", "fingerprint": fingerprint, "name": "Peer"}).encode())
        def close(self):
            pass
    relay = Relay()
    monkeypatch.setattr(remote_books, "_connect", lambda *a, **k: relay)
    computers = remote_books.Computers(tmp_path / "computers.json")
    with pytest.raises(remote_books.RemoteError):
        computers.pair("127.0.0.1:20001", "123456", "Client")
    assert relay.sent is None or "code" not in relay.sent


def test_a_pairing_string_for_another_certificate_never_sends_the_code(tmp_path, monkeypatch):
    sent = []

    class Relay:
        peer_fingerprint = "a" * 64
        sock = None

        def request(self, *args, **kwargs):
            sent.append(args)

        def close(self):
            pass

    monkeypatch.setattr(remote_books, "_connect", lambda *a, **k: Relay())
    computers = remote_books.Computers(tmp_path / "computers.json")
    with pytest.raises(remote_books.RemoteError, match="không khớp chuỗi ghép"):
        computers.pair("127.0.0.1:20001", remote_books.pairing_string("123456", "b" * 64), "Client")
    with pytest.raises(remote_books.RemoteError, match="không khớp chuỗi ghép"):
        computers.pair("127.0.0.1:20001", "123456", "Client", fingerprint="b" * 64)
    assert sent == []
