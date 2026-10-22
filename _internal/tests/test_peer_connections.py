from unittest.mock import Mock

from abook.webui.sync import ExclusiveHTTPServer, TlsHTTPServer, PEER_MAX_CONNECTIONS, PEER_MAX_PER_SOURCE


def test_eight_connections_from_one_paired_phone_are_admitted(monkeypatch):
    monkeypatch.setattr(ExclusiveHTTPServer, "__init__", lambda *a, **k: None)
    admitted = []
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request", lambda self, client, address: admitted.append(client))
    server = TlsHTTPServer(("127.0.0.1", 0), Mock(), Mock())
    server.shutdown_request = Mock()
    clients = [Mock() for _ in range(8)]
    for client in clients:
        server.process_request(client, ("127.0.0.1", 1))
    assert admitted == clients
    server.shutdown_request.assert_not_called()


class Clock:
    def __init__(self):
        self.now = 0
        self.timers = []

    def timer(self, seconds, callback):
        timer = Mock()
        timer.due = self.now + seconds
        timer.cancelled = False
        timer.cancel.side_effect = lambda: setattr(timer, "cancelled", True)
        timer.callback = callback
        self.timers.append(timer)
        return timer

    def advance(self, seconds):
        self.now += seconds
        for timer in self.timers:
            if not timer.cancelled and timer.due <= self.now:
                timer.cancelled = True
                timer.callback()


def test_paired_upload_receives_one_megabyte_over_35_seconds(monkeypatch):
    import os
    from http.server import BaseHTTPRequestHandler
    from abook.webui import sync
    clock = Clock()
    monkeypatch.setattr(sync.threading, "Timer", clock.timer)
    handler = sync.SyncHandler.__new__(sync.SyncHandler)
    handler.connection = Mock()
    handler.headers = {"Content-Length": str(1024 * 1024), "Authorization": "Bearer paired"}
    handler.app = Mock()
    handler.app.devices.identify.return_value = {"id": "paired"}
    body = b"a" * (1024 * 1024)
    class SlowBody:
        offset = 0
        def read(self, size):
            clock.advance(35 * size / len(body))
            if handler.connection.shutdown.called:
                raise ConnectionResetError("deadline cut the body")
            chunk = body[self.offset:self.offset + size]
            self.offset += len(chunk)
            return chunk
    handler.rfile = SlowBody()
    def request(self):
        path = self._upload(len(body))
        try:
            assert path.read_bytes() == body
            assert clock.now == 35
        finally:
            os.remove(str(path.resolve()))
    monkeypatch.setattr(BaseHTTPRequestHandler, "handle_one_request", request)
    handler.handle_one_request()


def test_unknown_peer_dripping_headers_is_cut_at_30_seconds(monkeypatch):
    from http.server import BaseHTTPRequestHandler
    from abook.webui import sync
    clock = Clock()
    monkeypatch.setattr(sync.threading, "Timer", clock.timer)
    handler = sync.SyncHandler.__new__(sync.SyncHandler)
    handler.connection = Mock()
    def request(self):
        for _ in range(29):
            clock.advance(1)
            self.connection.shutdown.assert_not_called()
        clock.advance(1)
        self.connection.shutdown.assert_called_once()
    monkeypatch.setattr(BaseHTTPRequestHandler, "handle_one_request", request)
    handler.handle_one_request()


def test_eight_parallel_authenticated_requests_are_served_over_tls(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from abook.webui import sync, tls
    devices = sync.Devices(tmp_path / "devices.json")
    token = devices.pair(devices.start_pairing()["code"], "Phone")
    app = Mock(devices=devices)
    barrier = threading.Barrier(8, timeout=5)
    def library():
        barrier.wait()
        return []
    app.library_view.side_effect = library
    app.name = "test"
    app.routes.return_value = {}
    server = sync.SyncServer(app, host="127.0.0.1", port=0).start()
    def request(_):
        connection = tls.PinnedHTTPSConnection("127.0.0.1", server.port, expected=server.fingerprint, timeout=10)
        try:
            connection.request("GET", "/sync/v1/library", headers={"Authorization": f"Bearer {token}"})
            response = connection.getresponse()
            assert response.status == 200
            assert b'"books": []' in response.read()
        finally:
            connection.close()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(request, range(8)))
    finally:
        server.stop()


def test_unpaired_upload_does_not_extend_deadline_or_read_body():
    from abook.webui import sync
    handler = sync.SyncHandler.__new__(sync.SyncHandler)
    handler.headers = {"Content-Length": "1048576"}
    handler._read_deadline = Mock()
    handler.rfile = Mock()
    assert handler._upload(1048576) is None
    handler._read_deadline.cancel.assert_not_called()
    handler.rfile.read.assert_not_called()
    assert handler.close_connection


def test_excess_connections_are_closed_before_threads_and_other_sources_can_run(monkeypatch):
    monkeypatch.setattr(ExclusiveHTTPServer, "__init__", lambda *a, **k: None)
    admitted = []
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request", lambda self, client, address: admitted.append((client, address)))
    server = TlsHTTPServer(("127.0.0.1", 0), Mock(), Mock())
    server.shutdown_request = Mock()
    clients = [Mock() for _ in range(PEER_MAX_PER_SOURCE + 4)]
    for i in range(PEER_MAX_PER_SOURCE + 1):
        server.process_request(clients[i], ("192.0.2.1", i))
    server.process_request(clients[PEER_MAX_PER_SOURCE + 1], ("192.0.2.2", 1))
    assert len(admitted) == PEER_MAX_PER_SOURCE + 1
    server.shutdown_request.assert_called_once_with(clients[PEER_MAX_PER_SOURCE])
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request_thread", lambda *a: None)
    server.process_request_thread(*admitted.pop(0))
    server.process_request(clients[PEER_MAX_PER_SOURCE + 2], ("192.0.2.1", 5))
    server.process_request(clients[PEER_MAX_PER_SOURCE + 3], ("192.0.2.3", 6))
    assert len(admitted) == PEER_MAX_PER_SOURCE + 2


def test_total_limit_and_thread_start_failure_release_capacity(monkeypatch):
    monkeypatch.setattr(ExclusiveHTTPServer, "__init__", lambda *a, **k: None)
    admitted = []
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request", lambda self, client, addr: admitted.append((client, addr)))
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request_thread", lambda *a: None)
    server = TlsHTTPServer(("127.0.0.1", 0), Mock(), Mock())
    server.shutdown_request = Mock()
    for i in range(PEER_MAX_CONNECTIONS):
        server.process_request(Mock(), (f"192.0.2.{i + 1}", 1))
    excess = Mock()
    server.process_request(excess, ("192.0.2.100", 1))
    assert len(admitted) == PEER_MAX_CONNECTIONS
    server.shutdown_request.assert_called_once_with(excess)
    server.process_request_thread(*admitted[0])
    failed = Mock()
    def fail(*a):
        raise RuntimeError("no thread")
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request", fail)
    import pytest
    with pytest.raises(RuntimeError):
        server.process_request(failed, ("192.0.2.100", 1))
    monkeypatch.setattr(ExclusiveHTTPServer, "process_request", lambda self, client, addr: admitted.append((client, addr)))
    server.process_request(Mock(), ("192.0.2.100", 1))
    assert len(admitted) == PEER_MAX_CONNECTIONS + 1


def test_read_deadline_covers_entire_request_and_is_cancelled_before_streaming(monkeypatch):
    from http.server import BaseHTTPRequestHandler
    from abook.webui import sync
    timer = Mock()
    factory = Mock(return_value=timer)
    monkeypatch.setattr(sync.threading, "Timer", factory)
    handler = sync.SyncHandler.__new__(sync.SyncHandler)
    handler.connection = Mock()
    def read_request(self):
        timer.start.assert_called_once()
        timer.cancel.assert_not_called()
        self.end_headers()
        timer.cancel.assert_called_once()
    monkeypatch.setattr(BaseHTTPRequestHandler, "handle_one_request", read_request)
    monkeypatch.setattr(BaseHTTPRequestHandler, "end_headers", lambda self: None)
    handler.handle_one_request()
    assert factory.call_args.args[0] == 30
    factory.call_args.args[1]()
    handler.connection.shutdown.assert_called_once()
