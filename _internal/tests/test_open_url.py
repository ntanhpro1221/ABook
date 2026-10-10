"""`actions.open_url`: cửa vào từ trang web, chỉ http/https sạch; mọi thứ khác bị từ chối trước khi tới trình duyệt/ShellExecute."""
from __future__ import annotations

import pytest

from abook.webui import actions


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    monkeypatch.setattr(actions.webbrowser, "open", lambda url: seen.append(url) or True)
    return seen


@pytest.mark.parametrize("url", [
    "https://example.com/a?b=c&d=e#frag",
    "http://127.0.0.1:8080/x%20y",
])
def test_clean_http_links_open_unchanged(url: str, opened: list[str]) -> None:
    actions.open_url(url)
    assert opened == [url]


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/System32/calc.exe",
    "javascript:alert(1)",
    "ms-settings:privacy",
    "https:///nohost",
    "https://example.com/a b",
    'https://example.com/a"b',
    "https://example.com/a<b",
    "https://example.com/a>b",
    "https://example.com\\evil",
    "https://example.com/a\x01b",
    "https://example.com/a\tb",
    "https://example.com/a\nb",
    "https://example.com/a\x7fb",
    "https://example.com/?",  # urlsplit viết lại thành không có dấu hỏi
    "https://example.com/" + "a" * 2000,
])
def test_unsafe_or_rewritten_links_are_refused(url: str, opened: list[str]) -> None:
    with pytest.raises(ValueError):
        actions.open_url(url)
    assert opened == []
