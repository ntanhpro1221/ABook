"""Tên Nhật / Hàn trong "Nghe ngay": đọc bằng luật phiên âm (`abook/romanization.py`) thay vì âm tiếng Anh của sea-g2p.

sea-g2p đọc mọi chữ Latin bằng âm Anh ("Haruto" -> hɑːɹɹˈuːɾoʊ, "Kyouko" -> kˈaɪoʊ jˈuːkoʊ). Cuốn có gốc Nhật / Hàn thì tên của nó đã có cách đọc theo quy ước
(docs/READING_FOREIGN_NAMES.md): ở đây ta quyết (1) cuốn nào có gốc nào (`book_origin`), (2) token nào là tên cần đọc theo luật (`read_names`, gọi từ
`vieneu.spoken_tokens` - biến đổi để đọc, chữ hiện không đổi). Bản Kotlin y hệt: `readaloud/Names.kt` + `EnglishWords.kt`; hai bên cùng đọc
`tests/fixtures/readaloud/names.json` (sinh bằng scripts/build_names_fixture.py).

Một token được đọc theo luật khi: viết hoa chữ đầu (không toàn HOA: viết tắt không đụng), là chữ Latin, không phải từ tiếng Anh thật
(`english_words.txt`, scripts/build_english_words.py - "Rose", "Mike", "Level" để sea-g2p đọc), không phải âm tiết tiếng Việt đã viết sẵn ("Hoa", "Nam"), không
phải tiếng reo (chữ lặp ba lần: "Aaaa"), và luật tách được hết thành âm tiết. Hậu tố gọi (-kun, -san) đi cùng tên. Cái gì luật không chắc thì giữ nguyên.

Gốc của cuốn tự đoán từ chính tên trong cuốn: tỉ lệ lần xuất hiện của tên đọc được bằng romaji (hay RR) trên mọi tên. Ngưỡng nằm ở
`JA_SHARE` / `KO_SHARE`, chọn bằng đo trên kho truyện thử (docs/READING_FOREIGN_NAMES.md "Nối vào Nghe ngay"). Người dùng ghi đè được (`BookOrigins.override`).
"""
from __future__ import annotations

import collections
import json
import os
import threading
from functools import lru_cache
from itertools import islice
from pathlib import Path
from typing import Callable, Iterable

from ..romanization import _JA_SUFFIXES as JA_SUFFIXES
from ..romanization import romanized_reading

ENGLISH_FILE = Path(__file__).with_name("english_words.txt")
ORIGINS = ("ja", "ko")
SAMPLE_CHAPTERS = 40  # đoán gốc từ chừng ấy chương đầu (đo: 12 chương nhận 40 / 68 cuốn Nhật, 40 chương 46 / 68, cả cuốn 50 / 68; chạy một lần ở luồng nền)
MIN_NAMES = 10  # ít nhất chừng ấy tên khác nhau đọc được theo luật thì mới đủ tin
MIN_OCCURRENCES = 60  # và tên (kể cả không đọc được) xuất hiện ít nhất chừng ấy lần trong phần mẫu
JA_SHARE = 0.75  # tỉ lệ lần xuất hiện của tên đọc được bằng romaji trên mọi tên: từ đây là cuốn Nhật (đo: mọi cuốn từ 0,75 lên đều là tên Nhật)
HON_MIN = 20  # lần xuất hiện của tên romaji đi kèm hậu tố gọi (trong phần mẫu) đủ để tin dấu hiệu Nhật
HON_NAMES = 3  # và ít nhất chừng ấy tên khác nhau như vậy
HON_JA_SHARE = 0.3  # khi có dấu hiệu hậu tố, tỉ lệ ja chỉ cần từ đây
KO_SHARE = 0.85  # như trên cho RR; luật RR dễ tính (Mirabelle, Ruel, Alon của truyện Hàn cũng tách được) nên đòi cao hơn và thêm KO_ONLY_SHARE
KO_ONLY_SHARE = 0.5  # phần lần xuất hiện của tên đọc được bằng RR mà KHÔNG đọc được bằng romaji (Si-eun, Seo-ram...)
RULE_VERSION = 2  # đổi khi đổi cách đoán: gốc đã lưu của cuốn được đoán lại
ENGLISH_READING = 1  # đổi khi đổi cách Việt hoá từ Anh (`english_vi`, `english_reading`): clip đã đệm của giọng Việt hoá được đọc lại (dấu "en<số>" của khoá clip)
_ALLOWED_MARKS = "āīūēōâîûêôĀĪŪĒŌÂÎÛÊÔ"
HONORIFICS = ("san", "kun", "chan", "sama", "senpai", "sensei", "dono")  # hậu tố gọi Nhật nối gạch (JA_SUFFIXES còn "tan", "nee", "nii": dễ lẫn với chữ thường nên chỉ đi theo tên đã nhận)
KOREAN_TERMS = {"oppa": "ốp-pa", "unnie": "un-ni", "noona": "nu-na", "hyung": "hi-ung", "ssi": "si", "nim": "nim"}  # tiếng gọi Hàn cố định (bộ thử TN); luật RR chưa khớp quy ước ở "ssi", "unnie", "oppa"
KOREAN_ALONE = ("oppa", "unnie", "noona", "hyung")  # đứng riêng cũng đọc (không cần tên đi trước)
_SUFFIXES = frozenset(HONORIFICS) | frozenset(KOREAN_TERMS)


@lru_cache(maxsize=1)
def english_words() -> frozenset[str]:
    return frozenset(ENGLISH_FILE.read_text(encoding="utf-8").split())


def split_token(token: str) -> tuple[str, str, str]:
    """(dấu câu đầu, lõi từ chữ cái đầu tới chữ cái cuối, dấu câu cuối)."""
    start, end = 0, len(token)
    while start < end and not token[start].isalpha():
        start += 1
    while end > start and not token[end - 1].isalpha():
        end -= 1
    return token[:start], token[start:end], token[end:]


def _head(core: str) -> str | None:
    """Lõi bỏ hậu tố gọi (Haruto-kun -> Haruto) nếu nó có dáng một tên Latin; None nếu không (không viết hoa, toàn HOA, tiếng reo, chữ lạ)."""
    segments = core.split("-")
    while len(segments) > 1 and segments[-1].lower() in JA_SUFFIXES:
        segments.pop()
    head = "-".join(segments)
    first = segments[0]
    if len(head) < 2 or not first[:1].isupper() or first[1:] != first[1:].lower():
        return None
    if not all(segment[:1].isalpha() for segment in segments):
        return None
    if not all(ch.isascii() or ch in _ALLOWED_MARKS for ch in head):
        return None
    lowered = head.lower()
    if any(lowered[i] == lowered[i + 1] == lowered[i + 2] for i in range(len(lowered) - 2)):
        return None  # "Aaaa", "Haaa": tiếng reo, không phải tên
    if not any(ch.isascii() and ch.isalpha() and ch not in "aeiou" for ch in lowered):
        return None  # chỉ nguyên âm ("Aa", "Ooo")
    if not any(ch in "aeiouy" or not ch.isascii() for ch in lowered):
        return None  # không nguyên âm ("Hm", "Nn", "Shh"): tiếng reo
    return head


def _known_word(head: str) -> bool:
    """Từ tiếng Anh thật, hay âm tiết tiếng Việt đã viết sẵn: để nguyên cho sea-g2p."""
    from ..analysis import is_vietnamese_syllable

    plain = head.replace("-", "").lower()
    return plain in english_words() or ("-" not in head and is_vietnamese_syllable(plain))


@lru_cache(maxsize=8192)
def name_reading(core: str, origin: str | None) -> str | None:
    """Cách đọc nối gạch của `core` (đã bỏ dấu câu quanh) khi nó là tên theo luật của `origin`, None khi để nguyên."""
    if origin not in ORIGINS:
        return None
    head = _head(core)
    if head is None or _known_word(head):
        return None
    return romanized_reading(core, origin)


def read_names(toks: list[str], out: list[str], origin: str | None) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi so với `toks`) là tên bằng cách đọc của nó, giữ dấu câu quanh; số chữ không đổi."""
    if origin not in ORIGINS:
        return
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        reading = name_reading(core, origin) if core else None
        if reading:
            out[index] = before + reading + after


def closing(after: str, reading: str) -> str:
    """Dấu câu sau chữ, đổi cho vừa với cách đọc: sea-g2p đọc nháy đơn đóng sau MỘT chữ cái ("a’", "nha… a'") là "phẩy", nên khi cách đọc kết thúc bằng một chữ cái
    đứng riêng thì ’ và ' thành dấu ngoặc kép đóng ” (bỏ qua khi đọc)."""
    lone = len(reading) >= 1 and reading[-1].isalpha() and not reading[-2:-1].isalpha()
    return after.replace("’", "”").replace("'", "”") if lone else after


def _suffix(segment: str) -> bool:
    return segment.lower() in _SUFFIXES and not (len(segment) > 1 and segment.isupper())


def _term(segment: str) -> str:
    lowered = segment.lower()
    return KOREAN_TERMS.get(lowered) or romanized_reading(lowered, "ja") or lowered


@lru_cache(maxsize=8192)
def honorific_reading(core: str, origin: str | None) -> str | None:
    """Cách đọc nối gạch của `core` (đã bỏ dấu câu quanh) khi nó mang hậu tố gọi nối gạch ("Sora-sama", "hiệp sĩ-sama", "Mary-san", "Lane-ssi") hay là tiếng gọi Hàn đứng riêng
    ("oppa"), None khi để nguyên. Hậu tố đọc theo bảng của nó với MỌI cuốn; phần tên đứng trước đọc theo luật romaji khi nó là tên Nhật rõ (cuốn gốc Hàn thì để `read_names`),
    còn lại (tên Âu, từ Việt, từ Anh) giữ nguyên chữ."""
    segments = core.split("-")
    if not all(segment.replace("'", "").isalpha() for segment in segments):
        return None
    popped: list[str] = []
    while segments and _suffix(segments[-1]):
        popped.insert(0, segments.pop())
    if not popped or (not segments and popped[0].lower() not in KOREAN_ALONE):
        return None
    terms = "-".join(_term(segment) for segment in popped)
    head = "-".join(segments)
    if not head:
        return terms
    if origin != "ko" and all(segment.lower() in HONORIFICS for segment in popped):
        if head[:1].isupper():
            whole = name_reading(core, "ja")
        else:
            whole = romanized_reading(core, "ja") if head.isascii() and head == head.lower() and not _known_word(head) else None
        if whole:
            return whole
    return f"{head}-{terms}"


def read_honorifics(toks: list[str], out: list[str], origin: str | None) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi) mang hậu tố gọi bằng cách đọc của nó (`honorific_reading`), giữ dấu câu quanh; số chữ không đổi."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        reading = honorific_reading(core, origin) if core else None
        if reading:
            out[index] = before + reading + after


@lru_cache(maxsize=8192)
def english_reading(core: str) -> str | None:
    """Cách đọc nối gạch của một từ / tên tiếng Anh bằng âm tiết Việt (`english_vi.vietnamized_english`), None khi để nguyên: viết tắt TOÀN HOA, âm tiết
    tiếng Việt viết sẵn ("ba", "con"), chữ một ký tự, chữ lạ hay luật không chắc."""
    from ..analysis import is_vietnamese_syllable
    from ..english_vi import vietnamized_english

    parts = core.split("-")
    if any(len(part) < 2 or not part.isascii() or not part.isalpha() or part.isupper() for part in parts):
        return None
    if all(is_vietnamese_syllable(part.lower()) for part in parts):
        return None
    return vietnamized_english(core)


def read_english(toks: list[str], out: list[str]) -> None:
    """Thay tại chỗ, trong `out`, token (chưa bị đổi) là từ / tên tiếng Anh bằng cách đọc Việt hoá của nó, giữ dấu câu quanh; số chữ không đổi. Chữ dính
    số ("10kg", "5 m") để bộ chuẩn hoá của sea-g2p đọc đơn vị."""
    for index, token in enumerate(toks):
        if out[index] != token:
            continue
        before, core, after = split_token(token)
        if not core or before[-1:].isdigit() or after[:1].isdigit() or (index and toks[index - 1][-1:].isdigit()):
            continue
        reading = english_reading(core)
        if reading:
            out[index] = before + reading + after


def spoken_names(toks: list[str], origin: str | None, speaks_english: bool, out: list[str] | None = None) -> list[str]:
    """Chữ hiện -> chữ đem đọc cho tên và từ nước ngoài, dùng chung cho mọi giọng; thay tại chỗ trong `out` (mặc định bản sao của `toks`) và trả nó.
    Tên Nhật / Hàn của cuốn có gốc (`origin`) đọc theo luật phiên âm với MỌI giọng. Từ / tên tiếng Anh: giọng nói được âm Anh (`speaks_english`, VieNeu, Edge...)
    giữ nguyên chữ cho nó đọc; giọng chỉ nói được âm tiết Việt (Supertonic nuốt "Rose", "Haruto") thì Việt hoá thành âm tiết (`english_reading`)."""
    if out is None:
        out = list(toks)
    read_names(toks, out, origin)
    read_honorifics(toks, out, origin)
    if not speaks_english:
        read_english(toks, out)
    return out


# ---- gốc của cuốn ---------------------------------------------------------------------------------------------------------

def scan_names(texts: Iterable[str]) -> tuple[collections.Counter[str], collections.Counter[str]]:
    """(mỗi tên đã bỏ hậu tố gọi và số lần nó xuất hiện, riêng những lần nó đi kèm hậu tố gọi kiểu Nhật: Haruto-kun, Aqua-sama). Tên: chữ viết hoa chữ đầu,
    Latin, không phải từ Anh / âm tiết Việt / tiếng reo."""
    found: collections.Counter[str] = collections.Counter()
    suffixed: collections.Counter[str] = collections.Counter()
    for text in texts:
        for token in text.split():
            _, core, _ = split_token(token)
            if len(core) < 2 or not core[0].isupper():
                continue
            head = _head(core)
            if head is not None and not _known_word(head):
                found[head] += 1
                if head != core:
                    suffixed[head] += 1
    return found, suffixed


def name_counts(texts: Iterable[str]) -> collections.Counter[str]:
    return scan_names(texts)[0]


def origin_shares(counts: collections.Counter[str], suffixed: collections.Counter[str] | None = None) -> dict[str, float | int]:
    """Số liệu để quyết gốc: `total` lần xuất hiện, `names` tên khác nhau, `ja` / `ko` tỉ lệ lần xuất hiện đọc được, `ko_only` phần chỉ RR đọc được,
    `ja_names` / `ko_names` số tên khác nhau đọc được; `honorific` / `honorific_names`: lần xuất hiện / số tên khác nhau của tên đọc được bằng romaji
    mà đi kèm hậu tố gọi (`suffixed`)."""
    total = sum(counts.values())
    ja = ko = ko_only = 0
    ja_names = ko_names = 0
    for name, times in counts.items():
        by_ja = romanized_reading(name, "ja") is not None
        by_ko = romanized_reading(name, "ko") is not None
        ja += times if by_ja else 0
        ko += times if by_ko else 0
        ko_only += times if by_ko and not by_ja else 0
        ja_names += by_ja
        ko_names += by_ko
    share = (lambda value: value / total) if total else (lambda value: 0.0)
    honorific = {name: times for name, times in (suffixed or {}).items() if romanized_reading(name, "ja") is not None}
    return {"total": total, "names": len(counts), "ja": share(ja), "ko": share(ko), "ko_only": share(ko_only), "ja_names": ja_names, "ko_names": ko_names,
            "honorific": sum(honorific.values()), "honorific_names": len(honorific)}


def decide(shares: dict[str, float | int]) -> str | None:
    if shares["total"] < MIN_OCCURRENCES:
        return None
    if shares["ja_names"] >= MIN_NAMES and shares["ja"] >= JA_SHARE:
        return "ja"
    if shares["honorific"] >= HON_MIN and shares["honorific_names"] >= HON_NAMES and shares["ja_names"] >= MIN_NAMES and shares["ja"] >= HON_JA_SHARE:
        return "ja"  # hậu tố gọi (-san, -kun, -sama...) đi cùng tên romaji là dấu hiệu Nhật mạnh: đủ để hạ ngưỡng tỉ lệ (truyện Nhật hay có thêm tên kiểu Âu)
    if shares["ko_names"] >= MIN_NAMES and shares["ko"] >= KO_SHARE and shares["ko_only"] >= KO_ONLY_SHARE:
        return "ko"
    return None


def book_origin(texts: Iterable[str], *, sample: int | None = SAMPLE_CHAPTERS) -> str | None:
    """"ja" / "ko" khi tên trong cuốn gần như toàn là romaji Nhật / RR Hàn, None khi không chắc (cuốn Việt, Trung, Âu, hay tên lẫn lộn).
    `texts`: chữ các chương theo thứ tự; chỉ `sample` chương đầu được xét (None = hết)."""
    return decide(origin_shares(*scan_names(texts if sample is None else islice(texts, sample))))


class BookOrigins:
    """Gốc từng cuốn: máy đoán (`guess`, lưu để không đoán lại) và người dùng ghi đè (`override`: "ja" / "ko" / "none"; chưa ghi thì theo máy). Một file JSON
    nhỏ cạnh bộ đệm clip, ghi qua file tạm."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            data = json.loads(self.path.read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict[str, object]]) -> None:
        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_bytes((json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        os.replace(temp, self.path)

    def get(self, book_id: str) -> dict[str, object]:
        """`{"guess": "ja" | "ko" | "none" | None, "override": "ja" | "ko" | "none" | None}` (None = chưa có)."""
        entry = self._load().get(book_id) or {}
        guess = entry.get("guess") if entry.get("rule") == RULE_VERSION else None
        return {"guess": guess, "override": entry.get("override")}

    def origin(self, book_id: str, texts: Callable[[], Iterable[str]]) -> str | None:
        """Gốc dùng để đọc cuốn này: ghi đè của người dùng nếu có, không thì lần đoán đã lưu, chưa có thì đoán từ `texts()` và lưu."""
        with self._lock:
            data = self._load()
            entry = data.setdefault(book_id, {})
            override = entry.get("override")
            if override in ORIGINS or override == "none":
                return override if override in ORIGINS else None
            guess = entry.get("guess") if entry.get("rule") == RULE_VERSION else None
            if guess is None:
                guess = book_origin(texts()) or "none"
                entry["guess"], entry["rule"] = guess, RULE_VERSION
                self._save(data)
            return guess if guess in ORIGINS else None

    def override(self, book_id: str, value: str | None) -> None:
        """Người dùng chọn gốc của cuốn: "ja" / "ko" / "none" (không phiên âm gì); None = bỏ ghi đè, theo máy đoán."""
        if value is not None and value not in (*ORIGINS, "none"):
            raise ValueError("Gốc phải là ja, ko, none hay bỏ trống")
        with self._lock:
            data = self._load()
            entry = data.setdefault(book_id, {})
            if value is None:
                entry.pop("override", None)
            else:
                entry["override"] = value
            self._save(data)
