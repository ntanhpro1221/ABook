"""Địa chỉ hiện cho người ghép máy: địa chỉ ra mạng chính đầu tiên, mạng riêng ảo cuối, không card ảo, không link-local.

Soát UX 29-09: "gõ 100.73.x.x:47630 hoặc 192.168.0.1:47630 hoặc 192.168.0.230:47630" - 192.168.0.1 là card WSL (điện thoại
không bao giờ tới được, lại trông như router), 100.73 là Tailscale; người dùng không biết gõ cái nào.
"""
from __future__ import annotations

import abook.webui.sync as sync


class _Probe:
    def __init__(self, *_args, **_kwargs):
        pass

    def connect(self, _target):
        pass

    def getsockname(self):
        return ("192.168.0.230", 50000)

    def close(self):
        pass


def test_the_address_to_type_comes_first_and_virtual_cards_are_gone(monkeypatch) -> None:
    found = ("100.73.36.27", "192.168.0.1", "169.254.1.2", "192.168.0.230", "127.0.0.1")
    monkeypatch.setattr(sync.socket, "socket", _Probe)
    monkeypatch.setattr(sync.socket, "getaddrinfo", lambda *_a, **_k: [(2, 1, 0, "", (ip, 0)) for ip in found])
    monkeypatch.setattr(sync, "_virtual_addresses", lambda: {"192.168.0.1"})
    assert sync.local_addresses() == ["192.168.0.230", "100.73.36.27"]


def test_the_cgnat_range_counts_as_a_private_network() -> None:
    assert sync._vpn_range("100.64.0.1") and sync._vpn_range("100.127.255.1")
    assert not sync._vpn_range("100.63.0.1") and not sync._vpn_range("100.128.0.1") and not sync._vpn_range("10.0.0.1")


def test_any_private_network_card_is_an_away_address(monkeypatch) -> None:
    # Không chỉ Tailscale: ZeroTier / WireGuard cấp địa chỉ 10.x, 172.x... - nhận theo tên card, không theo dải.
    for name in ("Tailscale", "ZeroTier One [8056c2e21c000001]", "wg0", "WireGuard Tunnel", "wt0", "OpenVPN TAP-Windows6"):
        assert sync._vpn_adapter(name), name
    for name in ("Wi-Fi", "Ethernet", "Local Area Connection* 2", "Bluetooth Network Connection"):
        assert not sync._vpn_adapter(name), name
    monkeypatch.setattr(sync, "vpn_addresses", lambda: {"10.147.17.5"})
    assert sync.away_addresses(["192.168.0.230", "10.147.17.5", "100.73.36.27"]) == ["10.147.17.5", "100.73.36.27"]


def test_a_zerotier_address_goes_last(monkeypatch) -> None:
    found = ("10.147.17.5", "192.168.0.230")
    monkeypatch.setattr(sync.socket, "socket", _Probe)
    monkeypatch.setattr(sync.socket, "getaddrinfo", lambda *_a, **_k: [(2, 1, 0, "", (ip, 0)) for ip in found])
    monkeypatch.setattr(sync, "_virtual_addresses", lambda: set())
    monkeypatch.setattr(sync, "vpn_addresses", lambda: {"10.147.17.5"})
    assert sync.local_addresses() == ["192.168.0.230", "10.147.17.5"]
