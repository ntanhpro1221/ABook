"""Read Hako volume boundaries and covers without adding headings to chapter text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from collections.abc import Callable

from .importers import Chapter, ImportedBook, ImportFailed, Volume, _page

HOSTS = {"docln.net", "docln.sbs", "hako.vn", "ln.hako.vn"}
MAX_PAGE = 20 * 1024 * 1024


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self) -> str:
        return " ".join(" ".join(c.text() if isinstance(c, Node) else c for c in self.children).split())

    def has(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()


class Tree(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node("root", {})
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict((key, value or "") for key, value in attrs), self.current)
        self.current.children.append(node)
        if tag not in {"img", "br", "hr", "meta", "input", "link", "source", "wbr"}:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _image(node: Node, base: str) -> str:
    for item in node.walk():
        if item.tag == "img":
            value = item.attrs.get("data-src") or item.attrs.get("src")
            if value:
                return urljoin(base, value)
        match = re.search(r"url\(\s*['\"]?([^)'\"]+)", item.attrs.get("style", ""))
        if match:
            return urljoin(base, match[1])
    return ""


def parse(page: str, base: str) -> tuple[str, list[dict], str]:
    root = Tree(page).root
    title = next((n.text() for n in root.walk() if n.has("series-name")), "")
    if not title:
        raise ImportFailed("Trang Hako thiếu tên sách")
    volumes = []
    seen = set()
    for block in root.walk():
        if not block.has("volume-list"):
            continue
        name = next((n.text() for n in block.walk() if n.has("sect-title") or n.has("volume-name")), "")
        chapters = []
        for node in block.walk():
            href = node.attrs.get("href", "")
            if node.tag == "a" and re.search(r"/c\d+(?:-|/|$)", href):
                link = urljoin(base, href)
                if link not in seen:
                    seen.add(link)
                    chapters.append((node.attrs.get("title") or node.text(), link))
        if chapters:
            volumes.append({"title": name or f"Quyển {len(volumes) + 1}", "cover": _image(block, base), "chapters": chapters})
    cover = next((_image(n, base) for n in root.walk() if n.has("series-cover") or n.has("series-img")), "")
    if not volumes:
        raise ImportFailed("Trang Hako không có danh sách quyển và chương")
    return title, volumes, cover


def fetch(url: str) -> bytes:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise ImportFailed("Đường dẫn nguồn phải dùng HTTPS")
    with urlopen(Request(url, headers={"User-Agent": "ABook/0.4"}), timeout=30) as response:
        data = response.read(MAX_PAGE + 1)
    if len(data) > MAX_PAGE:
        raise ImportFailed("Trang nguồn vượt giới hạn dung lượng")
    return data


def load(url: str, get: Callable[[str], bytes] | None = None) -> ImportedBook:
    get = get or fetch
    if urlsplit(url).hostname not in HOSTS:
        raise ImportFailed("Chỉ nhận đường dẫn sách Hako")
    title, volumes, cover = parse(get(url).decode("utf-8"), url)
    result = ImportedBook(title)
    if cover:
        result.cover_bytes, result.cover_type = get(cover), "image/jpeg"
    for number, definition in enumerate(volumes, 1):
        raw = get(definition["cover"]) if definition["cover"] else None
        result.volumes.append(Volume(number, number, definition["title"], raw, "image/jpeg" if raw else None))
        for name, link in definition["chapters"]:
            if urlsplit(link).hostname not in HOSTS:
                raise ImportFailed("Chương trỏ ra ngoài Hako")
            page = get(link).decode("utf-8")
            # Parse the chapter-content element with the existing text renderer.
            match = re.search(r'<[^>]+id=["\']chapter-content["\'][^>]*>', page, re.I)
            if not match:
                raise ImportFailed("Trang chương thiếu phần chữ")
            start = match.end()
            depth, end = 1, start
            for tag in re.finditer(r"</?div\b[^>]*>", page[start:], re.I):
                depth += -1 if tag[0].startswith("</") else 1
                if depth == 0:
                    end = start + tag.start()
                    break
            if end == start:
                raise ImportFailed("Trang chương bị cắt cụt")
            text = "\n\n".join(_page(page[start:end].encode("utf-8")).lines)
            result.chapters.append(Chapter(name, text, volume=number))
    return result
