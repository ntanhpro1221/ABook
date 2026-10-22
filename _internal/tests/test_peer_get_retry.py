import http.client
import ssl
from unittest.mock import Mock

import pytest

from abook.webui import remote_books, tls


@pytest.mark.parametrize("fault", ["closed", "tls_eof", "busy"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_only_get_retries_admission_failures(monkeypatch, fault, method):
    connections = [Mock(peer_fingerprint="aa") for _ in range(3)]
    response = Mock(status=200)
    for connection in connections:
        connection.getresponse.return_value = response
    if fault in ("closed", "tls_eof"):
        for connection in connections[:2]:
            connection.getresponse.side_effect = http.client.RemoteDisconnected() if fault == "closed" else ssl.SSLEOFError()
    else:
        for connection in connections[:2]:
            connection.getresponse.return_value = Mock(status=503)
    connect = Mock(side_effect=connections)
    pause = Mock()
    monkeypatch.setattr(remote_books, "_connect", connect)
    monkeypatch.setattr(remote_books.time, "sleep", pause)
    monkeypatch.setattr(remote_books, "_read", lambda *a, **kw: b'{}')
    endpoint = remote_books.Endpoint("127.0.0.1", 1, "aa")
    if method == "GET":
        with remote_books._open(endpoint, method, "/test", "token") as (got, _):
            assert got is response
        assert [call.args[0] for call in pause.call_args_list] == [0.2, 0.8]
        assert connect.call_count == 3
        assert all(connection.close.call_count == 1 for connection in connections)
    else:
        with pytest.raises(remote_books.RemoteError):
            with remote_books._open(endpoint, method, "/test", "token"):
                pytest.fail("POST replayed")
        assert connect.call_count == 1
        pause.assert_not_called()


def test_pin_failure_never_retries(monkeypatch):
    connect = Mock(side_effect=tls.PinError("changed"))
    monkeypatch.setattr(remote_books, "_connect", connect)
    with pytest.raises(remote_books.RemoteError):
        with remote_books._open(remote_books.Endpoint("127.0.0.1", 1, "aa"), "GET", "/", "token"):
            pytest.fail("pin bypassed")
    assert connect.call_count == 1


def test_get_retry_budget_is_finite(monkeypatch):
    connection = Mock()
    connection.getresponse.side_effect = http.client.RemoteDisconnected()
    connect = Mock(return_value=connection)
    monkeypatch.setattr(remote_books, "_connect", connect)
    monkeypatch.setattr(remote_books.time, "sleep", Mock())
    with pytest.raises(remote_books.RemoteError):
        with remote_books._open(remote_books.Endpoint("127.0.0.1", 1, "aa"), "GET", "/", "token"):
            pytest.fail("closed connection accepted")
    assert connect.call_count == 3
    assert connection.close.call_count == 3


def test_offline_port_is_not_retried_as_an_admission_failure(monkeypatch):
    connect = Mock(side_effect=ConnectionRefusedError())
    monkeypatch.setattr(remote_books, "_connect", connect)
    with pytest.raises(remote_books.RemoteError):
        with remote_books._open(remote_books.Endpoint("127.0.0.1", 1, "aa"), "GET", "/", "token"):
            pytest.fail("offline port accepted")
    assert connect.call_count == 1
