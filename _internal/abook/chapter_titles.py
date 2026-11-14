"""Display metadata only. Never use these rules to split or rewrite source text.

chapter_titles.json is also compiled into Android BuildConfig. Structured document
headings remain authoritative; an unmarked line needs an empty following line.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RULES = json.loads((Path(__file__).parent / "webui/assets/chapter_titles.json").read_text(encoding="utf-8"))
_FLAGS = re.IGNORECASE
_NUMBERED = re.compile(RULES["numbered"], _FLAGS)
_NAMED = re.compile(RULES["named"], _FLAGS)
_PROSE = re.compile(RULES["prose"], _FLAGS)
_UNSAFE = re.compile(RULES["unsafe"], _FLAGS)
_VOLUME = re.compile(RULES["volume"], _FLAGS)
_ORDER = re.compile(r"^0\d*(?:\s*[-_.:]+\s*|\s+)(\S.*)$")
_NUMERIC = re.compile(r"(?:\d+|chương\s+\d+)", _FLAGS)


def clean_line(line: str) -> str:
    return unicodedata.normalize("NFC", " ".join(line.lstrip("\ufeff").split()))


def heading_parts(line: str) -> tuple[str, str] | None:
    """Recognize explicit headings without treating their opening words as proof."""
    line = clean_line(line)
    if not line or len(line) > RULES["maxHeading"]:
        return None
    match = _NUMBERED.fullmatch(line) or _NAMED.fullmatch(line)
    if match is None:
        return None
    name = match[1]
    # The illustration-page qualifier belongs to the name, not a subtitle.
    if len(match.groups()) > 2 and match[3]:
        name += " " + match[3]
    return name[:1].upper() + name[1:], (match[2] or "").strip()


def first_heading(text: str) -> str:
    """A bounded chapter opening -> a heading, or empty when prose is plausible."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    at = next((i for i, line in enumerate(lines) if clean_line(line)), None)
    if at is None:
        return ""
    first = clean_line(lines[at])
    if _VOLUME.fullmatch(first):
        # A volume wrapper is not the chapter title. Do not change source boundaries.
        following = next((clean_line(line) for line in lines[at + 1:] if clean_line(line)), "")
        return following if heading_parts(following) else ""
    if heading_parts(first):
        return first
    if at + 1 >= len(lines) or lines[at + 1].strip():
        return ""
    if not first or len(first) > RULES["maxStandalone"] or not RULES["minWords"] <= len(first.split()) <= RULES["maxWords"]:
        return ""
    if not first[0].isupper() or first[0] in "-–—('" or not any(c.isalpha() for c in first):
        return ""
    if _UNSAFE.search(first) or _PROSE.search(first):
        return ""
    return first


def explicit_heading(text: str) -> str:
    """First heading only when it carries a heading keyword; a bare standalone line is not enough."""
    heading = first_heading(text)
    return heading if heading_parts(heading) else ""


def file_number(stored: str) -> int | None:
    """"013", "Chương 13", "0013 - 13" -> 13; a real name -> None."""
    stored = clean_line(stored)
    order = _ORDER.fullmatch(stored)
    if order:
        stored = order[1]
    digits = re.fullmatch(r"(?:chương\s+)?(\d+)", stored, _FLAGS)
    return int(digits[1]) if digits else None


def fallback_positions(stored_titles: list[str]) -> list[int | None]:
    """Numeric file labels use book order, even when the file numbers are consecutive.

    An actual heading in the source still wins over this fallback. Named metadata
    is retained, including chapter names chosen by the reader.
    """
    return [at + 1 if not clean_line(stored) or file_number(stored) is not None else None
            for at, stored in enumerate(stored_titles)]


def chapter_name(stored: str, text: str = "", *, index: int | None = None) -> tuple[str, str]:
    """Actual heading wins. Numeric file labels use the book's display position."""
    heading = first_heading(text)
    if heading:
        return heading_parts(heading) or (heading, "")
    stored = clean_line(stored)
    order = _ORDER.fullmatch(stored)
    if order:
        stored = order[1]
    if index is not None and (not stored or _NUMERIC.fullmatch(stored)):
        return f"Chương {index}", ""
    if stored.isdecimal():
        return f"Chương {stored.lstrip('0') or '0'}", ""
    return stored, ""


def full_name(parts: tuple[str, str]) -> str:
    name, subtitle = parts
    return f"{name} · {subtitle}" if subtitle else name


def read_opening(path: Path | None) -> str:
    """Read only an already validated source path; never write book data."""
    if path is None:
        return ""
    from .io_utils import decode_text_bytes

    try:
        with path.open("rb") as handle:
            data = handle.read(8192)
    except OSError:
        return ""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        data = data[:len(data) // 2 * 2]
    elif b"\n" in data:
        data = data[:data.rfind(b"\n") + 1]
    return decode_text_bytes(data)
