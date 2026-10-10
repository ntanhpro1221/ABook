"""`remote_books.is_own_host`: ghép với chính máy này (thư viện nhân đôi) bị từ chối dù gõ bằng tên, `.local` hay IPv6."""
from __future__ import annotations

import pytest

from abook.webui import remote_books


@pytest.fixture(autouse=True)
def this_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(remote_books, "own_addresses", lambda: {"192.168.1.20", "127.0.0.1"})
    monkeypatch.setattr(remote_books, "own_ipv6_addresses", lambda: {"2402:800:1::20", "fe80::1234"})
    monkeypatch.setattr(remote_books.socket, "gethostname", lambda: "May-Cua-Toi")


@pytest.mark.parametrize("host", [
    "192.168.1.20", " 192.168.1.20 ", "127.0.0.1", "127.5.6.7", "localhost", "LocalHost", "::1", "[::1]",
    "::ffff:127.0.0.1", "::ffff:192.168.1.20", "may-cua-toi", "May-Cua-Toi.local", "may-cua-toi.local.", "MAY-CUA-TOI.LOCAL",
    "2402:800:1::20", "[2402:800:1::20]", "2402:0800:0001:0000:0000:0000:0000:0020", "fe80::1234%12", "0:0:0:0:0:0:0:1",
])
def test_the_machines_own_names_and_addresses_are_recognised(host: str) -> None:
    assert remote_books.is_own_host(host)


@pytest.mark.parametrize("host", [
    "192.168.1.21", "10.0.0.5", "may-khac", "may-khac.local", "may-cua-toi.example.com", "2402:800:1::21", "::ffff:192.168.1.21",
    "::2", "",
])
def test_other_machines_are_not(host: str) -> None:
    assert not remote_books.is_own_host(host)
