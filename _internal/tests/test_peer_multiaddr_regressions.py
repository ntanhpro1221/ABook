"""a117r2 F1-F6: bounded selection, socket ownership, normalization and privacy."""
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import diagnostics, peer_addresses as pa, peer_routing as pr, remote_books as rb, route, tls

PIN = "ab" * 32
FIXTURES = Path(__file__).parent / "fixtures"


def rows(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def dispose(resolver):
    for peer in resolver.peers.values():
        peer.pool.shutdown(wait=True, cancel_futures=True)
    resolver.reset()


def test_f1_shared_aliases_leave_room_and_keep_max_success():
    aliases = rows("peer_address_aliases.json")
    for group in aliases:
        for value in group["aliases"]:
            assert pa.valid(value, advertised=group["advertised"]) == group["canonical"]
    values = aliases[0]["aliases"] + aliases[1]["aliases"]
    assert pa.candidates(values) == (aliases[0]["canonical"], aliases[1]["canonical"])
    peer = {"fingerprint": PIN, "addresses": [
        {"address": aliases[0]["aliases"][1], "lastSuccess": 9},
        {"address": aliases[0]["aliases"][2], "lastSuccess": 2}]}
    pa.learn(peer, values, PIN)
    assert pa.ordered(peer) == [aliases[0]["canonical"], aliases[1]["canonical"]]
    assert peer["addresses"][0]["lastSuccess"] == 9
    pa.learn(peer, [f"10.0.0.{i}:47630" for i in range(1, 12)], PIN)
    assert pa.ordered(peer)[0] == aliases[0]["canonical"]
    assert len(peer["addresses"]) == 8


def test_f2_waiter_redial_uses_slot_deadline_and_closes_late_socket():
    resolver = pr.Resolver()
    entered, release, redial, finish, close = (threading.Event() for _ in range(5))
    attempts, errors, winners = [], [], []
    def dial(target):
        attempts.append(target)
        if len(attempts) == 1:
            entered.set()
            release.wait(1)
            return SimpleNamespace(close=lambda: None)
        redial.set()
        finish.wait(1)
        return SimpleNamespace(close=close.set)
    def leader():
        winners.append(resolver.connect("peer", ["phone:1"], dial, .08)[0])
    def waiter():
        try:
            winners.append(resolver.connect("peer", ["phone:1"], dial, .08)[0])
        except OSError:
            errors.append(True)
    first, second = threading.Thread(target=leader), threading.Thread(target=waiter)
    try:
        first.start()
        assert entered.wait(1)
        second.start()
        time.sleep(.01)
        release.set()
        assert redial.wait(1)
        second.join(.3)
        assert not second.is_alive() and errors == [True]
        assert len(resolver.peers["peer"].pending) == 1
        finish.set()
        assert close.wait(1)
        assert attempts == ["phone:1", "phone:1"]
    finally:
        release.set(); finish.set()
        first.join(1); second.join(1)
        for connection in winners:
            connection.close()
        dispose(resolver)


def test_f3_tcp_hints_drop_surplus_jobs_without_a_queue(monkeypatch):
    release, started = threading.Event(), threading.Event()
    pool = ThreadPoolExecutor(max_workers=2)
    attempts = []
    def probe(target):
        attempts.append(target)
        if len(attempts) == 2:
            started.set()
        release.wait(1)
        return False
    monkeypatch.setattr(route, "_pool", pool)
    route.reset()
    try:
        route.pick(["10.0.0.1:1", "10.0.0.2:1"], None, probe=probe)
        assert started.wait(1)
        for i in range(20):
            route.pick([f"peer-{i}-{j}:1" for j in range(8)], None, probe=probe)
        assert pool._work_queue.qsize() == 0
        assert len(route._probing) == 2
    finally:
        release.set()
        pool.shutdown(wait=True)
        route.reset()


def test_f3_hostname_tcp_hint_does_not_enter_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: pytest.fail("background DNS"))
    assert not route._reachable("private-phone.local:47630")


@pytest.mark.parametrize("row", rows("peer_diagnostics.json"))
def test_f4_shared_tail_hosts_and_source_locations(row):
    text = diagnostics.redact(row["message"])
    if "hidden" in row:
        assert row["hidden"] not in text
    if "kept" in row:
        assert row["kept"] in text


def test_f4_structured_host_fields_are_hidden_recursively():
    assert diagnostics.redact_report({"nested": [{"host": "private-phone", "hostname": "private-phone.local.",
        "address": "private-phone:47630"}]}) == {"nested": [{"host": "***", "hostname": "***", "address": "***"}]}


@pytest.mark.parametrize("stage", ["learn", "note"])
def test_f5_persistence_failure_closes_before_socket_handoff(monkeypatch, stage):
    closed = []
    connection = SimpleNamespace(sock=None, _context=None, peer_fingerprint=PIN, connect=lambda: None, close=lambda: closed.append(True))
    def fail(*args, **kwargs):
        raise PermissionError("computers.json locked")
    store = SimpleNamespace(learn=fail if stage == "learn" else lambda *a, **k: None,
                            note=fail if stage == "note" else lambda *a, **k: None)
    monkeypatch.setattr(tls, "PinnedHTTPSConnection", lambda *a, **k: connection)
    monkeypatch.setattr(rb, "_COMPUTERS", store)
    monkeypatch.setattr(rb, "_look_for_bluetooth", lambda *args: None)
    endpoint = rb.Endpoint("10.0.0.1", 1234, PIN, target="10.0.0.1:1234", computer="peer")
    resolver = pr.Resolver()
    monkeypatch.setattr(rb, "_ROUTES", resolver)
    try:
        with pytest.raises(PermissionError):
            rb._connect(endpoint, .1)
        assert closed, "persistence must not abandon ownership of the connected socket"
    finally:
        dispose(resolver)


class FakeSocket:
    def __init__(self, *args):
        self.timeout = None
        self.closed = False
        self.host = ""
    def settimeout(self, value): self.timeout = value
    def close(self): self.closed = True
    def setsockopt(self, *args): pass
    def getpeercert(self, **kwargs): return b"cert"


def test_f6_eighth_route_after_slow_tcp_tls_uses_real_connect_deadline(monkeypatch):
    attempted, sockets, tls_timeouts = [], [], []
    class Raw(FakeSocket):
        def __init__(self, *args):
            super().__init__(*args)
            sockets.append(self)
        def connect(self, address):
            self.host = address[0]
            attempted.append(self.host)
            if self.host != "10.1.0.8":
                time.sleep(.09)
    class Context:
        def wrap_socket(self, raw, **kwargs):
            if raw.host != "10.1.0.8":
                tls_timeouts.append(raw.timeout)
                time.sleep(min(.09, raw.timeout))
                raise TimeoutError("TLS consumed remaining time")
            return raw
    real_connection = tls.PinnedHTTPSConnection
    def connection(*args, **kwargs):
        result = real_connection(*args, **kwargs)
        result._context = Context()
        return result
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, port))])
    monkeypatch.setattr(socket, "socket", Raw)
    monkeypatch.setattr(tls.ssl, "SSLSocket", Raw)
    monkeypatch.setattr(tls, "fingerprint", lambda der: PIN)
    monkeypatch.setattr(tls, "PinnedHTTPSConnection", connection)
    monkeypatch.setattr(route, "PROBE_SECONDS", .1)
    monkeypatch.setattr(rb, "_COMPUTERS", None)
    resolver = pr.Resolver()
    monkeypatch.setattr(rb, "_ROUTES", resolver)
    targets = tuple(f"10.1.0.{i}:1234" for i in range(1, 9))
    try:
        conn = rb._connect(rb.Endpoint("10.1.0.1", 1234, PIN, target=targets[0], alternatives=targets[1:]), 60)
        assert conn.host == "10.1.0.8"
        conn.close()
        assert set(attempted) == {f"10.1.0.{i}" for i in range(1, 9)}
        assert all(0 < value < .09 for value in tls_timeouts)
    finally:
        dispose(resolver)
    assert all(sock.closed for sock in sockets)


def test_f6_dns_and_multiple_tcp_addresses_share_one_deadline(monkeypatch):
    now = [0.0]
    timeouts, sockets = [], []
    class Raw(FakeSocket):
        def __init__(self, *args):
            super().__init__(*args)
            sockets.append(self)
        def connect(self, address):
            timeouts.append(self.timeout)
            now[0] += .03
            raise OSError("down")
    def dns(*args):
        now[0] += .04
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (f"10.0.0.{i}", 443)) for i in range(1, 4)]
    connection = tls.PinnedHTTPSConnection("manual.local", 443, expected=PIN, timeout=.1)
    monkeypatch.setattr(tls.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    monkeypatch.setattr(socket, "socket", Raw)
    with pytest.raises(OSError):
        connection.connect()
    assert timeouts == pytest.approx([.06, .03])
    assert all(raw.closed for raw in sockets)


@pytest.mark.parametrize("row", rows("peer_discovery_ports.json"))
def test_discovery_original_json_integer_contract_shared_with_kotlin(row):
    assert bool(pa.discovery_endpoint("192.168.1.8", row["port"])) == row["valid"]


def test_discovery_scope_matches_advertised_scope_except_explicit_local_probe():
    for host in ("127.0.0.1", "169.254.1.1", "::1", "fe80::1", "0.0.0.0"):
        assert pa.discovery_endpoint(host, 47630) is None
    assert pa.discovery_endpoint("127.0.0.1", 47630, advertised=False) == "127.0.0.1:47630"


def test_f5_socket_setup_failure_closes_before_resolver_handoff(monkeypatch):
    closed = []
    def fail(*args):
        raise OSError("socket closed while setting request timeout")
    connection = SimpleNamespace(sock=SimpleNamespace(settimeout=fail), close=lambda: closed.append(True))
    monkeypatch.setattr(rb, "_dial", lambda *a, **k: connection)
    monkeypatch.setattr(rb, "_COMPUTERS", None)
    resolver = pr.Resolver()
    monkeypatch.setattr(rb, "_ROUTES", resolver)
    try:
        with pytest.raises(OSError):
            rb._connect(rb.Endpoint("10.0.0.1", 123, PIN, target="10.0.0.1:123"), 1)
        assert closed == [True]
    finally:
        dispose(resolver)


def test_f3_manual_hostname_recovers_without_global_dns_hints(monkeypatch):
    route.reset()
    monkeypatch.setattr(route, "_reachable", lambda *args: pytest.fail("hostname hint must not resolve DNS"))
    target = "manual-phone.local:47630"
    try:
        assert route.pick([target], "bt").lan == target
        assert not route._probing
        route.mark_down(target)
        assert route.pick([target], "bt").bluetooth == "bt"
        assert route.pick([target], "bt", now=time.time() + route.FRESH_SECONDS + 1).lan == target
        assert not route._probing
    finally:
        route.reset()
