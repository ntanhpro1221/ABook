"""Địa chỉ hiện cho người ghép máy: địa chỉ ra mạng chính đầu tiên, Tailscale cuối, không card ảo, không link-local.

Soát UX 29-09: "gõ 100.73.x.x:47630 hoặc 192.168.0.1:47630 hoặc 192.168.0.230:47630" - 192.168.0.1 là card WSL (điện thoại
không bao giờ tới được, lại trông như router), 100.73 là Tailscale; người dùng không biết gõ cái nào.
"""
from __future__ import annotations

import ebook_reader.webui.sync as sync


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


def test_tailscale_is_the_cgnat_range_only() -> None:
    assert sync._tailscale("100.64.0.1") and sync._tailscale("100.127.255.1")
    assert not sync._tailscale("100.63.0.1") and not sync._tailscale("100.128.0.1") and not sync._tailscale("10.0.0.1")
