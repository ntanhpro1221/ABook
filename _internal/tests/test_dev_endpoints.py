"""Both phone installations are discoverable and dev Bluetooth never uses release SDP."""
import json
from types import SimpleNamespace

import pytest

from abook.webui import bluetooth, remote_books, sync
from abook.webui.peer_endpoints import DEBUG, RELEASE
from scripts import phone_diag

PHONE = "AA:BB:CC:DD:EE:FF"
PIN = "ab" * 32


def test_release_values_are_frozen_and_debug_endpoints_are_disjoint():
    assert RELEASE == {"port": 47630, "discoveryPort": 47631,
                       "serviceUuid": "a1f667fe-352a-49b7-9b91-a5463677cac0", "tunnelFirstPort": 47670}
    assert sync.SYNC_PORT == remote_books.LIBRARY_PORT == RELEASE["port"]
    assert sync.DISCOVERY_PORT == RELEASE["discoveryPort"]
    assert bluetooth.SERVICE_UUID.hex == RELEASE["serviceUuid"].replace("-", "")
    assert {RELEASE["port"], RELEASE["discoveryPort"]}.isdisjoint({DEBUG["port"], DEBUG["discoveryPort"]})
    assert bluetooth.DEV_SERVICE_UUID != bluetooth.SERVICE_UUID


def test_discovery_probes_both_apps_and_keeps_two_replies_on_the_same_phone(monkeypatch):
    sent = []
    replies = iter([
        {"app": "abook", "kind": "phone", "name": "Pixel", "port": RELEASE["port"]},
        {"app": "abook", "kind": "phone", "name": "Pixel (ABook .dev)", "port": DEBUG["port"]},
    ])
    class UDP:
        def setsockopt(self, *args): pass
        def settimeout(self, *args): pass
        def close(self): pass
        def sendto(self, data, target): sent.append(target)
        def recvfrom(self, size):
            try:
                return json.dumps(next(replies)).encode(), ("192.168.1.9", 1)
            except StopIteration:
                raise TimeoutError
    monkeypatch.setattr(remote_books.socket, "socket", lambda *args: UDP())
    monkeypatch.setattr(remote_books, "own_addresses", lambda: set())
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    found = remote_books.discover(timeout=0.01, targets=["192.168.1.9"])
    assert {port for _, port in sent} == {RELEASE["discoveryPort"], DEBUG["discoveryPort"]}
    assert {item["port"] for item in found} == {RELEASE["port"], DEBUG["port"]}
    assert any(".dev" in item["name"] for item in found)


def test_two_sdp_queries_use_different_uuids():
    queries = [bluetooth._ServiceQuery(PHONE, service) for service in (bluetooth.SERVICE_UUID, bluetooth.DEV_SERVICE_UUID)]
    assert [bytes(query.query.lpServiceClassId.contents) for query in queries] == [
        bluetooth.SERVICE_UUID.bytes_le, bluetooth.DEV_SERVICE_UUID.bytes_le]


def test_gateways_for_two_apps_never_share_a_connection_or_retry_the_other_uuid(monkeypatch):
    attempted = []
    def dial(address, *, service_uuid):
        attempted.append((address, service_uuid))
        raise OSError("fake radio unavailable")
    monkeypatch.setattr(bluetooth, "connect_rfcomm", dial)
    try:
        release = bluetooth.gateway(PHONE)
        dev = bluetooth.gateway(PHONE + "@dev")
        assert dev is not release and dev.port != release.port
        for gateway in (release, dev):
            with pytest.raises(OSError, match="fake radio"):
                gateway._link()
        assert attempted == [(PHONE, bluetooth.SERVICE_UUID), (PHONE, bluetooth.DEV_SERVICE_UUID)]
    finally:
        bluetooth.forget(PHONE)
        bluetooth.forget(PHONE + "@dev")


def test_bluetooth_pairing_persists_the_selected_build_and_routes_phone_diag(tmp_path, monkeypatch):
    computers = remote_books.Computers(tmp_path / "computers.json")
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    gateways = []
    def gateway(address):
        gateways.append(address)
        return SimpleNamespace(port=12345, warm=lambda: None)
    monkeypatch.setattr(bluetooth, "gateway", gateway)
    def exchange(endpoint, *args):
        dev = endpoint.bluetooth.endswith("@dev")
        pin = PIN if dev else "cd" * 32
        return json.dumps({"token": "dev" if dev else "release", "fingerprint": pin,
                           "name": "Pixel (ABook .dev)" if dev else "Pixel"}).encode(), pin
    monkeypatch.setattr(remote_books, "_exchange", exchange)
    release = computers.pair(PHONE, "123456", "Studio")
    dev = computers.pair(PHONE + "@dev", "123456", "Studio")
    assert release["id"] != dev["id"]
    assert release["port"] == RELEASE["port"] and dev["port"] == DEBUG["port"]
    entry = phone_diag.find(computers, ".dev")
    assert entry["id"] == dev["id"]
    assert remote_books._base(entry).bluetooth == PHONE + "@dev"
    assert gateways == [PHONE, PHONE + "@dev", PHONE + "@dev"]


def test_wifi_dev_fallback_to_bluetooth_selects_only_dev_service(tmp_path, monkeypatch):
    computers = remote_books.Computers(tmp_path / "computers.json")
    computers._write({"computers": {"dev": {"host": "192.168.1.9", "port": DEBUG["port"], "bt": PHONE,
                                           "fingerprint": PIN, "token": "dev"}}})
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    seen = []
    monkeypatch.setattr(bluetooth, "gateway", lambda address: seen.append(address) or SimpleNamespace(port=1234, warm=lambda: None))
    remote_books._tunnel(PHONE, PIN, "dev")
    assert seen == [PHONE + "@dev"]
    entry = computers.get("dev")
    monkeypatch.setattr(remote_books, "_COMPUTERS", None)
    assert remote_books._bluetooth_of(entry) == PHONE + "@dev"


def test_forgetting_one_app_does_not_close_the_other_apps_gateway(monkeypatch):
    closed = []
    monkeypatch.setattr(bluetooth, "forget", closed.append)
    remote_books._release_bluetooth({"bt": PHONE, "port": DEBUG["port"]}, [{"bt": PHONE, "port": RELEASE["port"]}])
    assert closed == [PHONE + "@dev"]
