"""Optional descriptive book fields, independent of story text and audio identity."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_bytes

FIELDS = ("author", "illustrator", "altTitles", "genres", "summary", "source")
FILE = "book_metadata.json"


def validate(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - set(FIELDS):
        raise ValueError("Invalid book metadata fields")
    result = {}
    for key, value in raw.items():
        if key in ("altTitles", "genres"):
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        elif key == "source":
            valid = isinstance(value, dict) and set(value) == {"url", "site"} and all(isinstance(v, str) for v in value.values())
        else:
            valid = isinstance(value, str)
        if not valid:
            raise ValueError(f"Invalid book metadata: {key}")
        strings = value if isinstance(value, list) else list(value.values()) if isinstance(value, dict) else [value]
        if any(any(ord(c) < 32 and c not in "\n\t" for c in text) for text in strings):
            raise ValueError(f"Invalid book metadata text: {key}")
        result[key] = [item for item in value if item.strip()] if key in ("altTitles", "genres") else value
    return result


def present(raw: dict[str, Any]) -> dict[str, Any]:
    return validate({key: raw[key] for key in FIELDS if raw.get(key)})


def load(root: Path) -> dict[str, Any]:
    path = Path(root) / FILE
    return validate(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else {}


def save(root: Path, changes: dict[str, Any]) -> dict[str, Any]:
    result = {**load(root), **validate(changes)}
    atomic_write_bytes(Path(root) / FILE, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


def overlay(book: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """Publish descriptive edits in book.json while retaining the listener edit ledger."""
    changes = {key: edits[key] for key in FIELDS if key in edits}
    if not changes:
        return book
    result = dict(book)
    for key, value in validate(changes).items():
        if value:
            result[key] = value
        else:
            result.pop(key, None)
    from .webui.listen_view import metadata_version
    result["metaVersion"] = metadata_version(result)
    return result


class _Description(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.rsplit(":", 1)[-1]
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "div", "br", "li", "section", "blockquote"):
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        tag = tag.rsplit(":", 1)[-1]
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "div", "li", "section", "blockquote"):
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def description(text: str) -> str:
    parser = _Description()
    parser.feed(text)
    return "\n\n".join(re.sub(r"[ \t\r\n]+", " ", part).strip() for part in "".join(parser.parts).split("\n\n") if part.strip())


_HEAD = re.compile(r"^\s*(?:#+\s*)?(Tác giả|Author|Họa sĩ|Hoạ sĩ|Illustrator|Tên khác|Thể loại|Tóm tắt)\s*[:：]\s*(.*)$", re.I)
_KEYS = {"tác giả": "author", "author": "author", "họa sĩ": "illustrator", "hoạ sĩ": "illustrator", "illustrator": "illustrator",
         "tên khác": "altTitles", "thể loại": "genres", "tóm tắt": "summary"}


def text_header(text: str) -> dict[str, Any]:
    result = {}
    lines = text.splitlines()
    summary_end = -1
    for index, line in enumerate(lines[:64]):
        if index <= summary_end:
            continue
        if re.match(r"^\s*(?:Chương|Chapter)\s+", line, re.I):
            break
        match = _HEAD.fullmatch(line)
        if not match:
            continue
        key, value = _KEYS[match[1].casefold()], match[2].strip()
        if key == "summary":
            # A header summary ends at a chapter heading, metadata key or Markdown section.
            parts = [value] if value else []
            for end, next_line in enumerate(lines[index + 1:], index + 1):
                if _HEAD.fullmatch(next_line) or re.match(r"^\s*(?:#+\s|(?:Chương|Chapter)\s+)", next_line, re.I):
                    break
                parts.append(next_line)
                summary_end = end
            value = "\n".join(parts).strip()
        elif key in ("altTitles", "genres"):
            value = [item.strip() for item in re.split(r"[;|]" if key == "altTitles" else r"[,;|]", value) if item.strip()]
        result[key] = value
    return present(result)


def from_folder(folder: Path) -> dict[str, Any]:
    for name in (FILE, "import.json", "metadata.json"):
        path = folder / name
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if name == "metadata.json" and isinstance(raw.get("source"), str):
                url = raw.get("url") or ("https://docln.net" + raw["path"] if raw.get("path") else "")
                raw["source"] = {"url": url, "site": "Hako"} if url else None
            result = present(raw)
            if name == "metadata.json" and "source" not in result and raw.get("path"):
                result["source"] = {"url": "https://docln.net" + raw["path"], "site": "Hako"}
            return result
    files = sorted(folder.glob("*.txt"))
    if files:
        from .io_utils import decode_text
        text, _encoding = decode_text(files[0].read_bytes())
        return text_header(text)
    return {}
