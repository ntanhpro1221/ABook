"""Known first-use authentication gap; protocol design is in the external a80fix report."""
import json
from contextlib import contextmanager
from io import BytesIO

import pytest

from abook.webui import remote_books


@pytest.mark.xfail(strict=True, reason="First-use MITM requires a cross-platform pairing protocol change; design only in a80fix report")
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
