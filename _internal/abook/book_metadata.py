"""Optional descriptive book fields, independent of story text and audio identity."""
from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_bytes

FIELDS = ("author", "illustrator", "altTitles", "genres", "summary", "source")
FILE = "book_metadata.json"
_LOG = logging.getLogger(__name__)


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


def blank(value: Any) -> bool:
    """A field with nothing to show: absent, "", [] or a source whose url and site are both empty.

    One rule for every comparison and every publish (Kotlin BookMetadata.blank is the same rule, shared cases in
    tests/fixtures/book_metadata/set_metadata.json): a draft that sends an empty field the book never had is not an edit.
    """
    if isinstance(value, dict):
        return all(not str(item or "").strip() for item in value.values())
    if isinstance(value, list):
        return not any(str(item).strip() for item in value)
    return value is None or (isinstance(value, str) and not value.strip())


def same(a: Any, b: Any) -> bool:
    return (blank(a) and blank(b)) or a == b


def clean(raw: Any) -> dict[str, Any]:
    """`validate` plus the author rule of every typed author (one line, NFC, capped): the same on every write path."""
    result = validate(raw)
    if "author" in result:
        from .webui.book_edits import AUTHOR_MAX, clean_text
        result["author"] = clean_text(result["author"], AUTHOR_MAX)
    return result


def present(raw: dict[str, Any]) -> dict[str, Any]:
    return validate({key: raw[key] for key in FIELDS if not blank(raw.get(key))})


def load(root: Path) -> dict[str, Any]:
    path = Path(root) / FILE
    return validate(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else {}


def save(root: Path, changes: dict[str, Any]) -> dict[str, Any]:
    result = {**load(root), **clean(changes)}
    atomic_write_bytes(Path(root) / FILE, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


def overlay(book: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """Publish descriptive edits in book.json while retaining the listener edit ledger."""
    changes = {key: edits[key] for key in FIELDS if key in edits}
    if not changes:
        return book
    result = dict(book)
    for key, value in validate(changes).items():
        if not blank(value):
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


_SUMMARY_END = re.compile(r"^\s*(?:#+\s|(?:Chương|Chapter)\s+)", re.I)
# A scene or section break ("***", "---", "* * *", "===", "~~~") closes the header block.
_BREAK = re.compile(r"^\s*(?:[*\-=~_#]\s*){3,}$")
HEADER_LINES = 64
C0_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f]")


def text_controls(text: str) -> str:
    """Drops invisible control characters; a form feed or separator control is a paragraph break. Every visible character stays."""
    return C0_CONTROLS.sub("", re.sub(r"[\x0b\x1c-\x1f]", "\n\n", text)).replace("\x0c", "\n\n")


def text_header(text: str) -> dict[str, Any]:
    """Header fields ("Tác giả: X", "Tóm tắt: ...") read from the first HEADER_LINES lines of a TXT.

    `text` is the decoded file, NOT the cleaned chapter text: cleaning folds runs of blank lines into one, and two blank lines
    are what close a summary. Import to listen and a Studio project both pass the decoded file and get the same fields.
    Lines split on \\n, \\r\\n and \\r only, like Kotlin `lines()` (BookImport.headerMetadata).
    """
    result = {}
    lines = text_controls(text).replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n").split("\n")[:HEADER_LINES]
    summary_end = -1
    for index, line in enumerate(lines):
        if index <= summary_end:
            continue
        if re.match(r"^\s*(?:Chương|Chapter)\s+", line, re.I):
            break
        match = _HEAD.fullmatch(line)
        if not match:
            continue
        key, value = _KEYS[match[1].casefold()], match[2].strip()
        if key == "summary":
            # A header summary ends at a chapter heading, metadata key, Markdown section, scene break or two blank lines,
            # and never runs past the header window: a short story with no "Chương" line is not its own summary.
            parts = [value] if value else []
            blanks = 0
            for end, next_line in enumerate(lines[index + 1:], index + 1):
                if _HEAD.fullmatch(next_line) or _SUMMARY_END.match(next_line) or _BREAK.match(next_line):
                    break
                blanks = blanks + 1 if not next_line.strip() else 0
                if blanks >= 2:
                    break
                parts.append(next_line)
                summary_end = end
            value = "\n".join(parts).strip()
        elif key in ("altTitles", "genres"):
            value = [item.strip() for item in re.split(r"[;|]" if key == "altTitles" else r"[,;|]", value) if item.strip()]
        if not blank(value):  # an empty "Tác giả:" line keeps what an earlier line gave, like Kotlin headerMetadata
            result[key] = value
    return present(result)


# Sidecars next to the source, in priority order: ABook's own file, the `extract` sidecar, a Hako download.
SIDECARS = (FILE, "import.json", "metadata.json")
# A metadata.json is a common name; only a Hako download (it records where it came from) is read as ours.
_HAKO_MARKS = ("path", "url", "source")


def _sidecar(path: Path) -> dict[str, Any] | None:
    """Fields of one sidecar, or None when it is not ours or is broken (logged; never fatal)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        if path.name == "metadata.json":
            if not any(raw.get(mark) for mark in _HAKO_MARKS):
                return None
            if isinstance(raw.get("source"), str):
                url = raw.get("url") or ("https://docln.net" + raw["path"] if isinstance(raw.get("path"), str) and raw["path"] else "")
                raw["source"] = {"url": url, "site": "Hako"} if isinstance(url, str) and url else None
        result = present(raw)
        if path.name == "metadata.json" and "source" not in result and isinstance(raw.get("path"), str) and raw["path"]:
            result["source"] = {"url": "https://docln.net" + raw["path"], "site": "Hako"}
        return result
    except (OSError, UnicodeDecodeError, ValueError, TypeError, AttributeError) as error:
        _LOG.warning("Skipped book metadata in %s: %s", path, error)
        return None


def from_sources(files: list[Path] | tuple[Path, ...]) -> dict[str, Any]:
    """Descriptive fields for a book made from these TXT files.

    A sidecar next to the files wins; otherwise the header of the first chosen file (natural order) - never another TXT
    that happens to share the folder. A broken or foreign sidecar is skipped with a warning, so it can never stop a project
    from being created or a folder from being imported.
    """
    if not files:
        return {}
    from .io_utils import decode_text, natural_key
    first = min((Path(file) for file in files), key=lambda file: natural_key(file.name))
    for name in SIDECARS:
        path = first.parent / name
        if path.is_file():
            found = _sidecar(path)
            if found is not None:
                return found
    try:
        text, _encoding = decode_text(first.read_bytes())
    except OSError as error:
        _LOG.warning("Skipped the TXT header of %s: %s", first, error)
        return {}
    try:
        return text_header(text)
    except ValueError as error:
        _LOG.warning("Skipped the TXT header of %s: %s", first, error)
        return {}
