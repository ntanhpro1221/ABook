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
_STRUCTURAL = re.compile(RULES["structural"], _FLAGS)
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


def opening_line(text: str) -> tuple[str, bool]:
    """(first non-empty line, an empty line follows it). A volume wrapper is skipped as in `first_heading`."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    at = next((i for i, line in enumerate(lines) if clean_line(line)), None)
    if at is None:
        return "", False
    if _VOLUME.fullmatch(clean_line(lines[at])):
        at = next((i for i in range(at + 1, len(lines)) if clean_line(lines[i])), None)
        if at is None:
            return "", False
    return clean_line(lines[at]), at + 1 < len(lines) and not lines[at + 1].strip()


def _ends_like_prose(line: str) -> bool:
    return line[-1] in ".,;:" or not line[0].isalpha() or not line[0].isupper()


def structural_parts(line: str) -> tuple[str, str, str] | None:
    """"Lần gặp thứ 92 - Lời hứa" -> ("lần gặp", "Lần gặp thứ 92", "Lời hứa"): a few lead words, a number (digits, Roman, or
    number words), then an optional subtitle. The lead is the pattern a book repeats; on its own this proves nothing."""
    line = clean_line(line)
    if not line or len(line) > RULES["maxHeading"] or _ends_like_prose(line):
        return None
    match = _STRUCTURAL.fullmatch(line)
    if match is None or not all(any(c.isalpha() for c in word) for word in match[2].split()):
        return None
    return match[2].casefold(), match[1], (match[3] or "").strip()


def _loose_heading(line: str) -> bool:
    """A standalone first line in a book whose other chapters are all titled: length and closing punctuation still decide."""
    return bool(line) and len(line) <= RULES["maxHeading"] and not _ends_like_prose(line) and not heading_parts(line) \
        and line[0] not in "-–—('\"“‘«"


def book_headings(texts: list[str], stored_titles: list[str]) -> list[str]:
    """Chapter headings decided for the whole book, never one chapter at a time (Hello, 15-11: "Lần gặp thứ N - …" was 12 words,
    over the standalone limit, so one chapter showed its real name and the rest "Chương N").

    1. A keyword heading ("Chương 3: …", "Mở đầu") always counts (`first_heading`).
    2. A repeated structure ("Lần gặp thứ N", "Hồi ký số N" + subtitle) that opens most untitled chapters, each line followed by
       an empty line, counts for every chapter that has it, whatever its length (up to `maxHeading`).
    3. A book never mixes real names with numbered fallbacks: when most chapters are titled, a remaining chapter's standalone
       first line counts too; if one still has none, or titled chapters are the minority, the guessed names give way to numbers.
    Keyword headings and named file labels never change. Lines ending like a sentence (".", ",", ";", ":") never count."""
    base = [first_heading(text) for text in texts]
    lines = [opening_line(text) for text in texts]
    keyword = [bool(heading and heading_parts(heading)) for heading in base]
    open_ = [at for at in range(len(texts)) if not keyword[at]]
    keys: dict[str, int] = {}
    for at in open_:
        line, blank = lines[at]
        parts = structural_parts(line) if blank else None
        if parts:
            keys[parts[0]] = keys.get(parts[0], 0) + 1
    out = list(base)
    if keys:
        key, count = max(keys.items(), key=lambda item: item[1])
        if count >= 2 and count * 2 > len(open_):
            for at in open_:
                line, blank = lines[at]
                parts = structural_parts(line) if blank else None
                if parts and parts[0] == key:
                    out[at] = line
    positions = fallback_positions(stored_titles)
    titled = [at for at in open_ if out[at]]
    untitled = [at for at in open_ if not out[at] and positions[at] is not None]
    if titled and untitled:
        if len(titled) > len(untitled):
            for at in untitled:
                line, blank = lines[at]
                if blank and _loose_heading(line):
                    out[at] = line
        if any(not out[at] for at in untitled):
            for at in titled:
                out[at] = ""
    return out


def heading_name(heading: str) -> tuple[str, str]:
    """(name, subtitle) of a heading `book_headings` accepted: keyword parts, else the repeated structure, else the line."""
    parts = heading_parts(heading)
    if parts:
        return parts
    structure = structural_parts(heading)
    if structure:
        return structure[1][:1].upper() + structure[1][1:], structure[2]
    return clean_line(heading), ""


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


def is_named_matter(heading: str) -> bool:
    """The chapter's own heading names it as front/back matter or an extra ("Mở đầu", "Phần kết", "Ngoại truyện")."""
    return bool(heading) and _NAMED.fullmatch(clean_line(heading)) is not None


def fallback_numbers(positions: list[int | None], named_matter: list[bool]) -> list[int | None]:
    """Display numbers for chapters without a heading: book order counting only real chapters. A prologue headed "Mở đầu"
    takes no number, so the first unheaded chapter after it is "Chương 1", not "Chương 2" (Hello, 15-11)."""
    out: list[int | None] = []
    count = 0
    for position, matter in zip(positions, named_matter):
        if not matter:
            count += 1
        # Named matter keeps its own heading; a named file label (position None) keeps its name.
        out.append(None if position is None or matter else count)
    return out


def distinct_fallbacks(names: list[str], fallback: list[bool], stored: list[str]) -> list[str]:
    """A position fallback ("Chương N", chapter without a heading) never repeats a name another chapter has: it shows its
    file number instead ("000" -> "Chương 0"), and its file label when that clashes too. A prologue without a recognized
    heading before a real "Chương 1" used to become a second "Chương 1" (Những gì em, 15-11). Headed names never change."""
    out = list(names)
    for at, is_fallback in enumerate(fallback):
        if not is_fallback:
            continue
        others = {name.casefold() for other, name in enumerate(out) if other != at}
        if out[at].casefold() not in others:
            continue
        for candidate in (full_name(chapter_name(stored[at])), clean_line(stored[at])):
            if candidate and candidate.casefold() not in others:
                out[at] = candidate
                break
    return out


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
