"""B31 (Lead 11-10 21h): GỢI Ý xưng hô + neo tên cho từng câu thoại trong prompt generator - model tự cân, không phải luật.

Hàm THUẦN trên một dòng yêu cầu của generator (id/hint/previous_text/text/next_text) + danh sách tên đã biết của prompt, nên tính
y hệt khi dựng dữ liệu học (từ prompt có sẵn trong data_b9) và khi app chạy (cây đo ABook_b31 chép nguyên tệp này). Chỉ câu
hint == "dialogue". Thêm (nếu có) hai trường:
  "address_cue": {"self": [...], "addressee": [...], "either": [...]}   đại từ trong câu (danh sách đóng address_cues của app,
                  bỏ ngôi ba) chia theo vai: tự xưng / gọi người nghe / cả hai chiều (từ thân tộc).
  "name_cue":    {"vocative": [...], "narration": [...]}                 tên ĐÃ BIẾT bị gọi ở đầu/cuối câu (người được gọi - thường
                  KHÔNG phải người nói); tên đã biết trong lời kể kề bên (trước/sau, không phải câu thoại) có động từ nói (neo N B29).
Không đổi nhãn, không đổi trường nào khác.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

PRONOUNS = (
    "tôi", "tớ", "mình", "ta", "tao", "ngươi", "mày", "cậu", "ngài", "thiếp", "chàng", "nàng", "huynh", "đệ", "muội", "tỷ",
    "tỉ", "em", "anh", "chị", "cô", "ông", "bà", "con", "cháu", "bác", "chú", "nhóc", "lão", "bạn",
    "chúng ta", "chúng tôi", "chúng mình", "chúng tớ", "chúng mày", "bọn ta", "bọn mình", "bọn tao", "bọn mày",
)
_TOKEN = re.compile(r"(?<![\wÀ-ỹ])(" + "|".join(sorted(PRONOUNS, key=len, reverse=True)) + r")(?![\wÀ-ỹ])", re.IGNORECASE)
_THIRD_PERSON = re.compile(
    r"(?<![\wÀ-ỹ])(?:anh|chị|cô|ông|bà|cậu|em|con|chú|bác|lão|hắn|nó)\s+(?:ấy|kia|ta)(?![\wÀ-ỹ])", re.IGNORECASE
)
_NOT_PRONOUN = {"cô": re.compile(r"\s+(độc|gái|đơn|nương|bé|lập)", re.IGNORECASE)}
SELF = frozenset({"tôi", "tớ", "mình", "ta", "tao", "thiếp", "chúng ta", "chúng tôi", "chúng mình", "chúng tớ", "bọn ta",
                  "bọn mình", "bọn tao"})
ADDRESSEE = frozenset({"ngươi", "mày", "cậu", "ngài", "bạn", "chàng", "nàng", "nhóc", "chúng mày", "bọn mày"})
# còn lại (em, anh, chị, cô, ông, bà, con, cháu, bác, chú, lão, huynh, đệ, muội, tỷ, tỉ): vừa tự xưng vừa gọi người nghe
SAY = re.compile(r"(?<!\w)(nói|hỏi|đáp|trả lời|lên tiếng|cất tiếng|cất giọng|thì thầm|thì thào|lẩm bẩm|lầm bầm|hét|gào|la lên|"
                 r"kêu lên|quát|gắt|xen vào|ngắt lời|tiếp lời|dứt lời|giải thích|phản bác|càu nhàu|lí nhí|buột miệng|thốt lên|"
                 r"bảo|đề nghị|hỏi lại|nói tiếp|cười nói|trách|than|lên giọng|đáp lại|gọi)(?!\w)")
CAPW = re.compile(r"(?<![\w'])([A-ZÀ-ỸĐ][\w']*)")
VOC_HEAD = re.compile(r"^\W*([^\W\d_][\w'\- ]{0,30}?)\s*[,!?…]")
VOC_TAIL = re.compile(r",\s*([^\W\d_][\w'\- ]{0,30}?)\s*[.!?…]*\W*$")
QUOTES = "“”\"'「」『』[]"
GENERIC = ("NARRATOR", "UNKNOWN", "NPC", "SYSTEM")


def nfc(t: str) -> str:
    return unicodedata.normalize("NFC", t or "")


def pronouns(text: str) -> list[str]:
    """Đại từ theo thứ tự xuất hiện, không lặp (như address_cues.tokens của app, giữ thứ tự)."""
    text = _THIRD_PERSON.sub(" ", nfc(text))
    out: list[str] = []
    for m in _TOKEN.finditer(text):
        w = m.group(1).casefold()
        if w in _NOT_PRONOUN and _NOT_PRONOUN[w].match(text[m.end():m.end() + 8]):
            continue
        if w not in out:
            out.append(w)
    return out


def _tok(word: str) -> str:
    return word.split("-")[0].strip("'").casefold()


def name_index(known: list[str]) -> dict[str, list[str]]:
    """mảnh tên (chữ thường, bỏ đuôi kính ngữ) -> các tên đã biết chứa mảnh ấy (bỏ nhãn chung chung)."""
    idx: dict[str, list[str]] = {}
    for name in known:
        if not name or name.strip().upper().startswith(GENERIC):
            continue
        for w in re.split(r"[\s_]+", nfc(name)):
            t = _tok(w)
            if len(t) >= 2 and name not in idx.setdefault(t, []):
                idx[t].append(name)
    return idx


def _names_in(text: str, idx: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for m in CAPW.finditer(nfc(text)):
        for name in idx.get(_tok(m.group(1)), []):
            if name not in out:
                out.append(name)
    return out


def _is_quote(text: str) -> bool:
    t = nfc(text).lstrip()
    return bool(t) and t[0] in QUOTES


def hints(row: dict, idx: dict[str, list[str]]) -> dict:
    if row.get("hint") != "dialogue":
        return {}
    out: dict = {}
    ps = pronouns(str(row.get("text", "")))
    if ps:
        cue = {"self": [p for p in ps if p in SELF], "addressee": [p for p in ps if p in ADDRESSEE],
               "either": [p for p in ps if p not in SELF and p not in ADDRESSEE]}
        out["address_cue"] = {k: v for k, v in cue.items() if v}
    voc: list[str] = []
    t = nfc(str(row.get("text", ""))).strip().strip(QUOTES)
    for rx in (VOC_HEAD, VOC_TAIL):
        m = rx.search(t)
        if m:
            voc += [n for n in _names_in(m.group(1), idx) if n not in voc]
    narr: list[str] = []
    for key in ("previous_text", "next_text"):
        nb = str(row.get(key, "") or "")
        if nb and not _is_quote(nb) and SAY.search(nfc(nb).lower()):
            narr += [n for n in _names_in(nb, idx) if n not in narr]
    nc = {k: v for k, v in (("vocative", voc), ("narration", narr)) if v}
    if nc:
        out["name_cue"] = nc
    return out


def known_from_prompt(prompt: str) -> list[str]:
    """Tên đã biết từ khối 'Nhân vật đã biết từ các phần trước:' (dòng '- TÊN; số lần đã gặp=...')."""
    out = []
    on = False
    for line in prompt.splitlines():
        if line.startswith("Nhân vật đã biết từ các phần trước:"):
            on = True
            continue
        if on:
            if not line.startswith("- "):
                break
            out.append(line[2:].split("; số lần đã gặp=")[0])
    return out


def stats(rows: list[dict], idx: dict[str, list[str]]) -> Counter:
    c = Counter()
    for r in rows:
        if r.get("hint") != "dialogue":
            continue
        h = hints(r, idx)
        c["thoại"] += 1
        c["có address_cue"] += "address_cue" in h
        c["có vocative"] += "vocative" in h.get("name_cue", {})
        c["có narration"] += "narration" in h.get("name_cue", {})
    return c
