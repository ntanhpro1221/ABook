"""Multi-address persistence and pinned failover; only loopback sockets and synthetic routes."""
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import peer_addresses as addresses, remote_books, route, tls

PIN = "ab" * 32


@pytest.fixture(autouse=True)
def isolated_resolver():
    remote_books._ROUTES.reset()
    yield
    remote_books._ROUTES.reset()


def test_eighth_live_address_is_not_starved_by_seven_slow_failures(monkeypatch):
    targets = tuple(f"10.19.1.{i}:47630" for i in range(1, 9))
    attempts = []
    connection = SimpleNamespace(sock=None, timeout=0, close=lambda: None)
    def dial(endpoint, *args, **kwargs):
        attempts.append(endpoint.target)
        if endpoint.target != targets[-1]:
            time.sleep(1.2)
            raise OSError("unreachable")
        return connection
    monkeypatch.setattr(remote_books, "_dial", dial)
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    endpoint = remote_books.Endpoint("10.19.1.1", 47630, PIN, target=targets[0], alternatives=targets[1:])
    assert remote_books._connect(endpoint, 60) is connection
    assert targets[-1] in attempts


def test_concurrent_callers_share_a_failed_round_and_short_negative_cache(monkeypatch):
    targets = tuple(f"10.20.1.{i}:47630" for i in range(1, 9))
    attempts = []
    gate = threading.Barrier(3)
    def dial(endpoint, *args, **kwargs):
        attempts.append(endpoint.target)
        time.sleep(0.02)
        raise OSError("unreachable")
    monkeypatch.setattr(remote_books, "_dial", dial)
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    endpoint = remote_books.Endpoint("10.20.1.1", 47630, PIN, target=targets[0], alternatives=targets[1:])
    def caller():
        gate.wait(2)
        with pytest.raises(OSError):
            remote_books._connect(endpoint, 4)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(caller) for _ in range(3)]
        for job in jobs:
            job.result(timeout=3)
    with pytest.raises(OSError):
        remote_books._connect(endpoint, 4)
    assert sorted(attempts) == sorted(targets)


def test_slow_dns_for_one_peer_never_occupies_another_peers_slots(monkeypatch):
    release, both_started = threading.Event(), threading.Event()
    attempts = []
    connection = SimpleNamespace(sock=None, timeout=0, close=lambda: None)
    def dial(endpoint, *args, **kwargs):
        attempts.append(endpoint.target)
        if endpoint.fingerprint == PIN:
            if len(attempts) == 2:
                both_started.set()
            release.wait(2)
            raise OSError("slow DNS")
        return connection
    monkeypatch.setattr(remote_books, "_dial", dial)
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    monkeypatch.setattr(route, "PROBE_SECONDS", 0.1)
    slow = remote_books.Endpoint("old.local", 47630, PIN, target="old.local:47630", alternatives=("old2.local:47630",))
    good = remote_books.Endpoint("192.168.1.5", 47630, "cd" * 32, target="192.168.1.5:47630")
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(remote_books._connect, slow, 4)
        try:
            assert both_started.wait(1)
            assert remote_books._connect(good, 4) is connection
        finally:
            release.set()
        with pytest.raises(OSError):
            job.result(timeout=2)


def test_failure_cache_is_invalidated_by_network_discovery_or_changed_candidates():
    from abook.webui.peer_routing import Resolver
    resolver = Resolver()
    attempts = []
    def dead(target):
        attempts.append(target)
        raise OSError("down")
    def fail(targets, network="wifi"):
        with pytest.raises(OSError):
            resolver.connect("pin", targets, dead, 0.01, network=network)
    try:
        fail(["a:1"])
        fail(["a:1"])
        assert len(attempts) == 1
        fail(["a:1"], "vpn")
        assert len(attempts) == 2
        resolver.invalidate("pin")  # authenticated discovery
        fail(["a:1"], "vpn")
        assert len(attempts) == 3
        fail(["a:1", "b:1"], "vpn")
        assert "b:1" in attempts
    finally:
        resolver.reset()


def test_stuck_jobs_do_not_accumulate_a_queue_or_duplicate_probes():
    from abook.webui.peer_routing import Resolver
    resolver = Resolver()
    resolver.FAILURE_SECONDS = 0
    release = threading.Event()
    attempts = []
    def stuck(target):
        attempts.append(target)
        release.wait(2)
        raise OSError("stuck")
    try:
        for _ in range(3):
            with pytest.raises(OSError):
                resolver.connect("pin", ["a:1", "b:1", "c:1"], stuck, 0.02)
        assert len(attempts) == 2
        assert len(resolver.peers["pin"].pending) == 2
    finally:
        release.set()
        resolver.reset()


def test_mapped_ipv6_advertisements_use_the_embedded_ipv4_scope():
    rows = json.loads((Path(__file__).parent / "fixtures/peer_addresses.json").read_text())
    peer = {"fingerprint": PIN, "addresses": []}
    for row in rows:
        assert bool(addresses.valid(row["address"], advertised=True)) == row["valid"], row
    addresses.learn(peer, [row["address"] for row in rows], PIN)
    assert set(addresses.ordered(peer)) == {row.get("canonical", row["address"]) for row in rows if row["valid"]}


def test_full_successful_history_keeps_active_and_new_advertised_host_and_port():
    old = [f"10.0.0.{i}:47630" for i in range(1, 9)]
    peer = {"fingerprint": PIN, "addresses": [{"address": host, "lastSuccess": i} for i, host in enumerate(old, 1)]}
    fresh = ["192.168.7.8:47631", "100.73.1.2:47632"]
    addresses.learn(peer, fresh, PIN, success=old[-1], at=20)
    assert len(peer["addresses"]) == 8
    assert addresses.ordered(peer)[0] == old[-1]
    assert set(fresh) <= set(addresses.ordered(peer))
    assert {item["lastSuccess"] for item in peer["addresses"] if item["address"] in fresh} == {0}


def test_legacy_computer_is_upgraded_once_with_original_host_first(tmp_path):
    path = tmp_path / "computers.json"
    path.write_text(json.dumps({"computers": {"peer": {"host": "100.73.1.2", "port": 47630, "token": "t", "fingerprint": PIN}}}), encoding="utf-8")
    computers = remote_books.Computers(path)
    assert computers.get("peer")["addresses"] == [{"address": "100.73.1.2:47630", "lastSuccess": 0}]
    before = path.read_bytes()
    assert computers.get("peer")["token"] == "t"
    assert path.read_bytes() == before
    # Address list is now authoritative; no perpetual fallback to the old host.
    computers.note("peer", addresses=[])
    assert computers.get("peer")["addresses"] == []


def test_wrong_identity_cannot_teach_addresses_or_success():
    peer = {"fingerprint": PIN, "addresses": []}
    assert not addresses.learn(peer, ["192.168.1.8:47630"], "cd" * 32, success="192.168.1.8:47630", at=12)
    assert peer["addresses"] == []


def test_discover_rejects_invalid_ports_and_isolates_one_failed_future(tmp_path, monkeypatch):
    computers = remote_books.Computers(tmp_path / "computers.json")
    computers._write({"computers": {"peer": {"fingerprint": PIN, "addresses": []}}})
    replies = iter([
        ({"port": 10**100, "name": "oversized"}, "192.168.1.2"),
        ({"port": 0, "name": "zero"}, "192.168.1.3"),
        ({"port": 47630, "name": "bad"}, "192.168.1.4"),
        ({"port": 47631, "name": "good"}, "192.168.1.5"),
    ])
    class UDP:
        def setsockopt(self, *args): pass
        def settimeout(self, *args): pass
        def sendto(self, *args): pass
        def close(self): pass
        def recvfrom(self, *args):
            try:
                value, host = next(replies)
            except StopIteration:
                raise TimeoutError
            return json.dumps({"app": "abook", "fingerprint": PIN, **value}).encode(), (host, 47631)
    attempted = []
    def remember(store, candidate, entry):
        attempted.append(candidate["host"])
        if candidate["name"] == "bad":
            raise OverflowError("one broken responder")
    monkeypatch.setattr(remote_books.socket, "socket", lambda *args: UDP())
    monkeypatch.setattr(remote_books, "own_addresses", lambda: set())
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    monkeypatch.setattr(remote_books, "_remember_discovered", remember)
    result = remote_books.discover(timeout=0.03, targets=["192.168.1.255"])
    assert {row["name"] for row in result} == {"bad", "good"}
    assert set(attempted) == {"192.168.1.4", "192.168.1.5"}


def test_discovery_must_verify_actual_tls_before_learning_a_claimed_route(tmp_path, monkeypatch):
    computers = remote_books.Computers(tmp_path / "computers.json")
    computers._write({"computers": {"peer": {"host": "100.73.1.2", "port": 47630, "token": "t", "fingerprint": PIN, "addresses": []}}})
    entry = computers.get("peer")
    candidate = {"host": "192.168.1.8", "port": 47630, "fingerprint": PIN}

    def wrong(*args, **kwargs):
        raise tls.PinError("forged discovery identity")

    monkeypatch.setattr(remote_books, "_dial", wrong)
    remote_books._remember_discovered(computers, candidate, entry)
    assert computers.get("peer")["addresses"] == []
    closed = []
    monkeypatch.setattr(remote_books, "_dial", lambda *args, **kwargs: SimpleNamespace(peer_fingerprint=PIN, close=lambda: closed.append(True)))
    remote_books._remember_discovered(computers, candidate, entry)
    assert addresses.ordered(computers.get("peer")) == ["192.168.1.8:47630"]
    assert closed == [True]


def test_wrong_claim_in_a_verified_library_reply_cannot_teach_routes(tmp_path, monkeypatch):
    from contextlib import contextmanager

    computers = remote_books.Computers(tmp_path / "computers.json")
    computers._write({"computers": {"peer": {"fingerprint": PIN, "addresses": []}}})
    @contextmanager
    def opened(*args, **kwargs):
        yield None, PIN
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    monkeypatch.setattr(remote_books, "_open", opened)
    monkeypatch.setattr(remote_books, "_read", lambda *args, **kwargs: json.dumps({"fingerprint": "cd" * 32, "addresses": ["192.168.1.8:47630"]}).encode())
    remote_books._exchange(remote_books.Endpoint("192.168.1.8", 47630, PIN, computer="peer"), "GET", "/sync/v1/library", "t")
    assert computers.get("peer")["addresses"] == []


def test_cap_dedup_filters_and_remembers_the_last_success():
    peer = {"fingerprint": PIN, "addresses": []}
    values = [f"10.0.0.{i}:47630" for i in range(1, 21)]
    values += ["127.0.0.1:47630", "169.254.1.2:47630", "[fe80::1]:47630", "[::1]:47630", "[fd00::7]:47630", "bad.local:1234", "0.0.0.0:22"]
    addresses.learn(peer, values, PIN, success="100.64.1.2:47630", at=20)
    assert len(peer["addresses"]) == addresses.LIMIT
    assert addresses.ordered(peer)[0] == "100.64.1.2:47630"
    addresses.learn(peer, ["[fd00::7]:47630"] * 2, PIN, success="[fd00::7]:47630", at=30)
    assert len(peer["addresses"]) == addresses.LIMIT
    assert addresses.ordered(peer)[0] == "[fd00::7]:47630"
    for bad in values[20:24] + values[25:]:
        assert addresses.valid(bad, advertised=True) is None
    assert addresses.split("[fd00::7]:47630") == ("fd00::7", 47630)


@pytest.mark.parametrize("failure", [OSError("down"), tls.PinError("wrong certificate")])
def test_dead_or_wrong_first_route_uses_another_before_any_http(monkeypatch, failure):
    route.reset()
    called = []
    connection = SimpleNamespace(sock=None, timeout=0, close=lambda: None)

    def dial(endpoint, timeout, **kwargs):
        called.append((endpoint.target, timeout, endpoint.fingerprint))
        if endpoint.target == "100.64.1.2:47630":
            raise failure
        return connection

    monkeypatch.setattr(remote_books, "_dial", dial)
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    endpoint = remote_books.Endpoint("100.64.1.2", 47630, PIN, target="100.64.1.2:47630", alternatives=("192.168.1.8:47630",))
    assert remote_books._connect(endpoint, 60) is connection
    assert called == [("100.64.1.2:47630", 1.5, PIN), ("192.168.1.8:47630", 1.5, PIN)]
    assert connection.timeout == 60


def test_mismatched_alternative_does_not_silently_fall_back_to_bluetooth(monkeypatch):
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    def dial(endpoint, *args, **kwargs):
        if endpoint.target == "100.64.1.2:47630":
            raise OSError("down")
        raise tls.PinError("wrong certificate")
    monkeypatch.setattr(remote_books, "_dial", dial)
    monkeypatch.setattr(remote_books, "_tunnel", lambda *args: pytest.fail("pin error hidden by Bluetooth"))
    endpoint = remote_books.Endpoint("100.64.1.2", 47630, PIN, target="100.64.1.2:47630", fallback="AA:BB:CC:DD:EE:FF",
                                     alternatives=("192.168.1.8:47630",))
    with pytest.raises(tls.PinError):
        remote_books._connect(endpoint, 4)


def test_slow_first_lookup_has_a_total_deadline_and_late_socket_is_closed(monkeypatch):
    release, closed = threading.Event(), threading.Event()
    winner = SimpleNamespace(sock=None, timeout=0, close=lambda: pytest.fail("winning socket closed"))
    loser = SimpleNamespace(sock=None, timeout=0, close=closed.set)
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    monkeypatch.setattr(route, "PROBE_SECONDS", 0.05)
    def dial(endpoint, *args, **kwargs):
        if endpoint.host == "old.local":
            release.wait(2)
            return loser
        return winner
    monkeypatch.setattr(remote_books, "_dial", dial)
    try:
        endpoint = remote_books.Endpoint("old.local", 47630, PIN, target="old.local:47630", alternatives=("192.168.1.8:47630",))
        assert remote_books._connect(endpoint, 60) is winner
    finally:
        release.set()
    assert closed.wait(1), "a late DNS/TLS result must not leak its socket"


@pytest.mark.skipif(not socket.has_dualstack_ipv6(), reason="OS has no dual-stack listener")
def test_ipv4_and_ipv6_reach_the_same_identity_and_advertisements_are_filtered(library, tmp_path, monkeypatch):
    from abook.webui import sync

    lib, _, listening = library
    devices = sync.Devices(tmp_path / "dual-devices.json")
    app = sync.SyncApp(lib, listening, devices, "Dual")
    monkeypatch.setattr(sync, "network_addresses", lambda: ["192.168.1.8", "100.73.1.2", "fd00::7", "fe80::7", "::1", "127.0.0.1"])
    server = sync.SyncServer(app, host="0.0.0.0", port=0, discovery_port=0).start()
    try:
        computers = remote_books.Computers(tmp_path / "dual-computers.json")
        paired = computers.pair(f"127.0.0.1:{server.port}", devices.start_pairing()["code"], "Test")
        entry = computers.get(paired["id"])
        raw, seen = remote_books._exchange(remote_books.Endpoint("::1", server.port, entry["fingerprint"]), "GET", "/sync/v1/library", entry["token"])
        assert seen == server.fingerprint
        assert json.loads(raw)["addresses"] == [f"192.168.1.8:{server.port}", f"100.73.1.2:{server.port}", f"[fd00::7]:{server.port}"]
    finally:
        server.stop()


def test_actual_pinned_tls_fails_over_without_sending_token_to_wrong_server(library, tmp_path, monkeypatch):
    from abook.webui.sync import Devices, SyncApp, SyncServer

    lib, _, listening = library
    devices = Devices(tmp_path / "devices.json")
    app = SyncApp(lib, listening, devices, "Đúng máy")
    good = SyncServer(app, host="127.0.0.1", port=0).start()
    wrong_devices = Devices(tmp_path / "wrong-devices.json")
    wrong = SyncServer(SyncApp(lib, listening, wrong_devices, "Sai máy"), host="127.0.0.1", port=0,
                       identity=tls.load_or_create(tmp_path / "wrong-identity.json")).start()
    computers = remote_books.Computers(tmp_path / "computers.json")
    try:
        paired = computers.pair(f"127.0.0.1:{good.port}", devices.start_pairing()["code"], "Test")
        monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
        monkeypatch.setattr(route, "_reachable", lambda _: True)
        good_address = f"127.0.0.1:{good.port}"
        wrong_address = f"127.0.0.1:{wrong.port}"
        computers.note(paired["id"], addresses=[{"address": wrong_address, "lastSuccess": 20}, {"address": good_address, "lastSuccess": 10}])
        entry = computers.get(paired["id"])
        # Wrong server must never see the HTTP token (pin rejected during handshake).
        monkeypatch.setattr(wrong_devices, "identify", lambda *_: pytest.fail("credential sent to wrong peer"))
        app.addresses = lambda: ["100.73.1.2:47630", "[fd00::7]:47630"]
        reply = json.loads(remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"]))
        assert reply["name"] == "Đúng máy"
        saved = computers.get(paired["id"])
        assert addresses.ordered(saved)[0] == good_address
        assert saved["connectedVia"] == good_address
        assert "[fd00::7]:47630" in addresses.ordered(saved)
    finally:
        good.stop()
        wrong.stop()
        route.reset()


# Shared fixture constructs a tiny local library; no GPU/model work.
from tests.test_webui_listen_and_sync import library  # noqa: E402,F401
