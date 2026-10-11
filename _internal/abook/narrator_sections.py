"""Người kể theo ĐOẠN (đoạn = khúc chương giữa hai dòng ngắt cảnh) của sách kể ngôi thứ nhất - bộ phát hiện, không model.

Sách có `voices.first_person_identity` mà một đoạn lại không kể bằng "tôi" của người ấy (chương đổi điểm nhìn, đoạn chèn ngôi
ba): model vẫn được dặn "người kể là X", nên gán thừa cho X những câu của người khác. Đo 07-10 (b14err/p_RESULT.md): bộ phát hiện
D dưới đây bắt 22/28 lỗi gán thừa kiểu ấy, báo nhầm 3/64 đoạn. Mỏng, nên app chỉ ĐỀ XUẤT; người dùng nhận mới áp.

D chỉ dùng chữ nguồn + tên người kể của sách (không nhãn model, không đáp án). Ngưỡng ĐÚNG như b14err/P_RULE.md, cố định:
báo "người kể của đoạn khác" khi (r3 >= 2 và r3 > r1/4) hoặc r1 < 1, với r1 = số "tôi"/"tớ" (và đại từ ưu thế của người kể ở
các chương quanh đó nếu không phải "tôi" - `narrator_pronouns`) và r3 = số lần tên người kể (đủ hay
một token tên riêng) trên 1.000 chữ LỜI DẪN của đoạn (lời dẫn = đoạn không nằm trong ngoặc thoại: `kind_hint == "narration"`).
Đoạn không có chữ lời dẫn nào thì không quyết được và KHÔNG bị báo.

Dòng tiêu đề góc nhìn ("[POV: Mai]", "~ Góc nhìn của Mai ~", "Quay lại góc nhìn thứ 3"): cũng là ranh đoạn, và nói thẳng ai kể -
đoạn mở bằng nó được đề xuất CÓ TÊN thay vì D. Đo 12-10 (LLM_Train/runs/DCHECK_12-10.md): 6 dòng trên 56 chương, cả 6 là mốc đổi
góc nhìn thật, trong đó có ca D không thấy được ("tôi" đổi sang người khác, 118 câu thoại).
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from .text_processing import segment_chapter_text

MAX_CHARS = 340
# Không phải ngưỡng của D: một khoảng được báo mà lời dẫn dưới ngần này chữ (thường chỉ là dòng tiêu đề chương, r1 = 0) không đáng
# làm phiền người dùng bằng một thẻ - khoảng nối liền với đoạn khác cũng bị báo thì đã cộng vào đủ chữ.
MIN_PROPOSAL_WORDS = 20
# Từ thường của tiếng Việt/Anh nằm trong tên người kể: chỉ khớp khi viết đủ tên, không khớp riêng một token.
COMMON_WORDS = frozenset({"Người", "Đưa", "Tang", "Master"})
BREAK_NUMBER = re.compile(r"^\s*(?:\d{1,3}|[IVXLC]{1,6})\s*[.)]?\s*$")
PRON = re.compile(r"(?<!\w)(?:tôi|tớ)(?!\w)", re.IGNORECASE)
# Người kể không xưng "tôi" (DCHECK_12-10 phụ lục 04:1x: người kể xưng "ta" thì r1 = 0 cả chương, D báo nhầm cả chương). Đại từ ưu
# thế đếm trên dòng lời dẫn của các chương quanh đó; mẫu = tôi|tớ ∪ {ưu thế}. "ta" đứng sau đại từ / danh từ chỉ người ("chúng ta",
# "hắn ta", "cô ta"...) không phải người kể.
NARRATOR_PRONOUNS = ("tôi", "tớ", "ta", "tao", "tại hạ", "bản tọa", "bổn tọa", "lão phu", "bổn vương", "trẫm")
_TA_AFTER = "".join(f"(?<!{word} )" for word in ("chúng", "hắn", "cô", "anh", "bọn", "gã", "lão", "bà", "ông", "mụ", "y", "nó"))
_DIALOGUE_START = tuple("\"“”「『-—'")
# Dưới ngần này chữ đại từ ứng viên (cả cửa sổ) thì không đủ để nói người kể xưng gì: một chương kể ngôi nhất thường có hàng chục
# "tôi" trong lời dẫn, còn vài chữ lẻ có thể chỉ là một câu trích - dùng mẫu mặc định.
MIN_PRONOUN_HITS = 20


def _pronoun_regex(words: Sequence[str]) -> re.Pattern[str]:
    # Lọc "chúng/hắn/cô... " chỉ cho "ta": "chúng tôi", "anh tôi" vẫn là người kể như ở PRON.
    alternatives = "|".join((_TA_AFTER if word == "ta" else "") + re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(r"(?<!\w)(?:" + alternatives + r")(?!\w)", re.IGNORECASE)


_CANDIDATES = {word: _pronoun_regex([word]) for word in NARRATOR_PRONOUNS}


def pronoun_counts(text: str) -> Counter[str]:
    """Số lần mỗi đại từ ứng viên của người kể trên các dòng LỜI DẪN của chữ nguồn (dòng mở bằng ngoặc / gạch thoại không tính)."""
    counts: Counter[str] = Counter()
    for line in _nfc(text).splitlines():
        line = line.strip()
        if not line or line.startswith(_DIALOGUE_START):
            continue
        for word, pattern in _CANDIDATES.items():
            found = len(pattern.findall(line))
            if found:
                counts[word] += found
    return counts


def pronoun_pattern(counts: Mapping[str, int]) -> re.Pattern[str]:
    """Mẫu đại từ của người kể từ số đếm (`pronoun_counts` cộng lại): PRON khi ưu thế là "tôi"/"tớ" hay chưa đủ chữ."""
    if sum(counts.values()) < MIN_PRONOUN_HITS:
        return PRON
    dominant = max(NARRATOR_PRONOUNS, key=lambda word: counts.get(word, 0))
    return PRON if dominant in ("tôi", "tớ") else _pronoun_regex(["tôi", "tớ", dominant])


def narrator_pronouns(texts: Sequence[str]) -> re.Pattern[str]:
    """Mẫu đại từ của người kể cho các chữ nguồn `texts` (chương đang xét và các chương quanh nó cùng người kể)."""
    total: Counter[str] = Counter()
    for text in texts:
        total.update(pronoun_counts(text))
    return pronoun_pattern(total)
# Dòng ngắt cảnh: toàn ký hiệu (* ◇ ◆ ─ ~ ・ ...) hoặc một số/số La Mã đứng riêng.
RULE_GLYPHS = frozenset("*~-=_#+·•‧・—–―‒─━═┄┈╌")
ORNAMENT_GLYPHS = frozenset("◆◇◈○●◎□■▪▫▲△▽▼★☆✦✧✱✲✶✷✻✽❖❀✿❁※⁂⁕⋆◦♦♢◊⸻§")
DASHES = frozenset("-—–―‒")


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def is_break_line(line: str) -> bool:
    """Một dòng chỉ gồm ký hiệu ngắt cảnh, hay một số / số La Mã đứng riêng."""
    stripped = line.strip()
    if not stripped:
        return False
    if BREAK_NUMBER.match(stripped):
        return True
    glyphs = [char for char in stripped if not char.isspace()]
    if not glyphs or len(glyphs) > 40 or not all(c in RULE_GLYPHS or c in ORNAMENT_GLYPHS for c in glyphs):
        return False
    if any(c in RULE_GLYPHS for c in glyphs) and len(glyphs) < 3 and all(c in DASHES for c in glyphs):
        return False  # một gạch ngang lẻ là dấu mở thoại, không phải ngắt cảnh
    return True


def name_pattern(narrator: str) -> re.Pattern[str]:
    """Tên người kể trong lời dẫn: đủ tên (mọi kiểu chữ) hoặc một token tên riêng viết hoa chữ đầu (trừ từ thường)."""
    full = _nfc(narrator.strip())
    tokens = []
    for token in full.split():
        titled = token.title()
        if titled in COMMON_WORDS or len(titled) < 2:
            continue
        tokens.append(titled)
    full_pattern = r"(?i:" + re.escape(full) + r")"
    token_pattern = "|".join(sorted({re.escape(token) for token in tokens}, key=len, reverse=True))
    pattern = full_pattern + (("|" + token_pattern) if token_pattern else "")
    return re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)")


def same_narrator(name: str, narrator: str) -> bool:
    """Hai cách viết cùng một người kể: đủ tên hay một token tên riêng của tên kia ("Minato" / "TANAKA MINATO"), hoa thường tuỳ ý."""
    name, narrator = " ".join(_nfc(name).split()), " ".join(_nfc(narrator).split())
    if not name or not narrator:
        return name == narrator
    return any(name_pattern(one).fullmatch(other) or name_pattern(one).fullmatch(other.title())
               for one, other in ((narrator, name), (name, narrator)))


# Dòng tiêu đề góc nhìn: dòng ngắn, TRỌN dòng là tiêu đề (bỏ ngoặc / ký hiệu trang trí hai đầu và số thứ tự khúc "4 - " ở đầu).
HEADING_MAX_CHARS = 60
POV_WORD = re.compile(r"(?i)\bP\.?O\.?V\b|góc nhìn")
_HEADING_EDGES = "[](){}<>【】「」『』《》〈〉«»\"'“”‘’*~=#+_|:·•・—–―‒─━═-" + "".join(ORNAMENT_GLYPHS)
_SECTION_NUMBER = re.compile(r"^(?:(?:[Pp]hần|[Pp]art)\s+)?(?:\d{1,3}|[IVXLC]{1,6})\s*[-.:)–—]\s*")
# "Trở lại / Quay về / Chuyển sang góc nhìn của X" (kể cả gõ nhầm "Trờ lại" như một bản dịch thật); câu thường mở bằng chữ khác
# ("Từ góc nhìn của tôi...") không khớp.
_POV_LEAD = re.compile(r"(?i)^(?:(?:trở|trờ|quay|chuyển|đổi|back)(?:\s+(?:lại|về|sang|qua|to))?\s+)?(?:góc\s+nhìn|p\.?o\.?v\.?)"
                       r"(?:\s*(?:của|from|of)(?!\w))?\s*[:\-–—]?\s*(?P<who>.*)$")
_POV_TAIL = re.compile(r"(?i)^(?P<who>.+?)(?:['’]s)?\s+p\.?o\.?v\.?$")  # "Mai's POV", "Third person POV"
_FILLER = re.compile(r"(?i)\s+(?:nào|nhé|nha|đây)$")
_THIRD_PERSON = re.compile(r"(?i)^(?:(?:ngôi\s+)?thứ\s*(?:3|ba)|người\s+(?:dẫn|kể)\s+chuyện|(?:third|3rd)[\s-]+person|narrator|tác\s+giả)$")
_NAME_TOKEN = re.compile(r"[^\W\d_][\w'’.-]*")


def pov_heading(line: str) -> str | None:
    """Tên người kể mà một dòng tiêu đề góc nhìn gọi ("Góc nhìn của Mai" -> "Mai"), "" khi dòng nói ngôi ba ("Góc nhìn thứ 3",
    "Góc nhìn người dẫn chuyện"), None khi dòng không phải tiêu đề góc nhìn - kể cả câu thường có chữ "góc nhìn"."""
    text = " ".join(_nfc(line).split())
    if not text or len(text) > HEADING_MAX_CHARS or not POV_WORD.search(text):
        return None
    text = _SECTION_NUMBER.sub("", text.strip(_HEADING_EDGES + " ")).strip(_HEADING_EDGES + " ")
    match = _POV_LEAD.match(text) or _POV_TAIL.match(text)
    if match is None:
        return None
    who = _FILLER.sub("", match.group("who").strip(_HEADING_EDGES + " ")).strip()
    if _THIRD_PERSON.match(who):
        return ""
    tokens = who.split()
    # Tên riêng: 1-4 chữ, chữ nào cũng viết hoa chữ đầu ("của tôi thì...", "của cô ấy" không phải tên).
    if not 1 <= len(tokens) <= 4 or not all(_NAME_TOKEN.fullmatch(token) and token[0].isupper() for token in tokens):
        return None
    return who


def heading_section_ids(rows: Sequence[Mapping[str, Any]], ids: Sequence[int]) -> list[int]:
    """Số đoạn của `section_ids` thêm ranh ở mỗi hàng là dòng tiêu đề góc nhìn (đánh số lại liên tục). Không đổi cách cắt chữ
    nguồn. Tiêu đề đứng một mình trước dòng ngắt cảnh thì đoạn của nó kéo sang khúc kế: tiêu đề nói về phần chữ phía sau."""
    out: list[int] = []
    section, previous, only_heading = -1, None, False
    for row, old in zip(rows, ids):
        heading = pov_heading(str(row["text"])) is not None
        if heading or (old != previous and not only_heading):
            section += 1
            only_heading = heading
        else:
            only_heading = False
        previous = old
        out.append(section)
    return out


def section_ids(raw_text: str, rows: Sequence[Mapping[str, Any]], *, max_chars: int = MAX_CHARS,
                drop_credits: bool = False, drop_tail_credits: bool = False) -> list[int] | None:
    """Số đoạn của từng hàng. Bộ chia câu bỏ dòng ngắt cảnh, nên cắt NGUỒN tại các dòng ấy, chia từng khúc bằng đúng bộ chia
    của app, và đối chiếu: ghép các khúc phải ra đúng chữ từng hàng. Lệch (nguồn sửa sau khi chia) -> None, không đoán."""
    chunks: list[list[str]] = [[]]
    for line in raw_text.splitlines(keepends=True):
        if is_break_line(line):
            chunks.append([])
        else:
            chunks[-1].append(line)
    ids: list[int] = []
    texts: list[str] = []
    section = 0
    last = max((index for index, chunk in enumerate(chunks) if "".join(chunk).strip()), default=-1)
    for position, chunk in enumerate(chunks):
        text = "".join(chunk)
        if not text.strip():
            continue
        # Dòng ghi công đầu chương ở khúc đầu, dòng ủng hộ / quảng cáo cuối chương ở khúc cuối - như bộ chia cả chương.
        part = segment_chapter_text(1, text, max_chars=max_chars, drop_credits=drop_credits and section == 0,
                                    drop_tail_credits=drop_tail_credits and position == last)
        if not part:
            continue
        ids += [section] * len(part)
        texts += [str(row["text"]) for row in part]
        section += 1
    if texts != [str(row["text"]) for row in rows]:
        return None
    return ids


def measure(rows: Sequence[Mapping[str, Any]], indexes: Sequence[int], name: re.Pattern[str] | None,
            pron: re.Pattern[str] = PRON) -> dict[str, Any]:
    """r1, r3 và cờ của một đoạn (`indexes` = vị trí các hàng của đoạn trong `rows`). Không có tên người kể (`name` None): chỉ
    đếm chữ lời dẫn, r3 None, không cờ."""
    words = pronouns = names = 0
    for index in indexes:
        if rows[index]["kind_hint"] != "narration":
            continue
        text = _nfc(str(rows[index]["text"]))
        words += len(text.split())
        pronouns += len(pron.findall(text))
        names += len(name.findall(text)) if name is not None else 0
    r1 = pronouns * 1000.0 / words if words else None
    r3 = names * 1000.0 / words if words and name is not None else None
    flagged = r3 is not None and r1 is not None and bool((r3 >= 2 and r3 > r1 / 4) or r1 < 1)
    return {"words": words, "r1": r1, "r3": r3, "flagged": flagged}


def detect(raw_text: str, rows: Sequence[Mapping[str, Any]], narrator: str, *, max_chars: int = MAX_CHARS,
           drop_credits: bool = False, drop_tail_credits: bool = False, pron: re.Pattern[str] = PRON) -> list[dict[str, Any]]:
    """Các đoạn của MỘT chương mà người kể có vẻ không phải `narrator` (dùng chữ nguồn + hàng đã chia: `text`, `kind_hint`, `seq`).

    Mỗi phần tử: {"from_seq", "to_seq", "r1", "r3", "words"} - gộp các đoạn liền nhau bị D báo thành một khoảng. Đoạn mở bằng
    dòng tiêu đề góc nhìn thì thay vào đó: {"from_seq", "to_seq", "heading": dòng ấy, "suggested": người kể nó gọi ("" = ngôi
    ba), "r1": None, "r3": None, "words"} - chỉ khi người ấy khác `narrator` (sách ngôi ba: chỉ tiêu đề CÓ TÊN). Không đối chiếu
    được chữ nguồn với các hàng thì trả rỗng: không có gì để đề xuất."""
    narrator = narrator.strip()
    if not rows:
        return []
    ids = section_ids(raw_text, rows, max_chars=max_chars, drop_credits=drop_credits, drop_tail_credits=drop_tail_credits)
    if ids is None:
        return []
    ids = heading_section_ids(rows, ids)
    name = name_pattern(narrator) if narrator else None
    members: dict[int, list[int]] = {}
    for index, section in enumerate(ids):
        members.setdefault(section, []).append(index)
    found: list[dict[str, Any]] = []
    for section in sorted(members):
        indexes = members[section]
        span = {"from_seq": int(rows[indexes[0]]["seq"]), "to_seq": int(rows[indexes[-1]]["seq"]), "_section": section}
        heading = pov_heading(str(rows[indexes[0]]["text"]))
        if heading is not None:
            # Hai loại không trùng nhau: đoạn có tiêu đề tin tiêu đề, không chạy D.
            if not same_narrator(heading, narrator):
                found.append({**span, "heading": " ".join(str(rows[indexes[0]]["text"]).split()), "suggested": heading,
                              "r1": None, "r3": None, "words": measure(rows, indexes, None)["words"]})
            continue
        if name is None:
            continue
        result = measure(rows, indexes, name, pron)
        if result["flagged"]:
            found.append({**span, "r1": result["r1"], "r3": result["r3"], "words": result["words"]})
    merged: list[dict[str, Any]] = []
    for item in found:
        if (merged and item["_section"] == merged[-1]["_section"] + 1
                and "heading" not in item and "heading" not in merged[-1]):
            merged[-1].update(to_seq=item["to_seq"], words=merged[-1]["words"] + item["words"], _section=item["_section"])
        else:
            merged.append(dict(item))
    for item in merged:
        item.pop("_section")
    return [item for item in merged if "heading" in item or item["words"] >= MIN_PROPOSAL_WORDS]


# --- Lựa chọn của người dùng, lưu cạnh sổ dự án ------------------------------------------------------------------------
# Không nằm trong `book_settings.json`: settings bị khoá theo băm từ lúc tạo sách (`initialize_book`), sửa một chữ là lần
# resume sau từ chối. Như `aliases.json`: máy chủ giao diện ghi, dây chuyền chỉ đọc - và đọc lại ở MỖI lô, nên resume thấy
# đúng giá trị đã lưu. Đề xuất không lưu (tính lại từ chữ nguồn, xem webui/narrator_cards.py); chỉ lưu QUYẾT ĐỊNH.
# {"version": 1, "sections": {"<chapter_index>": [{"from_seq", "to_seq", "narrator", "source", "accepted", "dismissed"}]}}
# `narrator` rỗng = đoạn ấy kể ở ngôi thứ ba (không có người kể xưng "tôi"); `source`: "auto" (người dùng đồng ý đề xuất) /
# "owner" (người dùng chọn người kể).
FILE_NAME = "narrator_sections.json"
MAX_NAME = 200


def load(project_root: Path | str) -> dict[int, list[dict[str, Any]]]:
    """{chapter_index: [quyết định]} - mọi quyết định (nhận hay bỏ qua). Không có file / file hỏng = chưa quyết gì."""
    try:
        data = json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    raw = data.get("sections") if isinstance(data, dict) else None
    sections: dict[int, list[dict[str, Any]]] = {}
    for key, entries in (raw.items() if isinstance(raw, dict) else ()):
        try:
            chapter = int(key)
        except (TypeError, ValueError):
            continue
        for entry in entries if isinstance(entries, list) else ():
            if not isinstance(entry, dict):
                continue
            try:
                first, last = int(entry["from_seq"]), int(entry["to_seq"])
            except (KeyError, TypeError, ValueError):
                continue
            if last < first:
                continue
            at = entry.get("at")
            sections.setdefault(chapter, []).append({
                "from_seq": first, "to_seq": last, "narrator": str(entry.get("narrator") or "").strip(),
                "source": "owner" if entry.get("source") == "owner" else "auto",
                "accepted": bool(entry.get("accepted")), "dismissed": bool(entry.get("dismissed")),
                # Lúc quyết: mở file dự án của cùng dự án thì quyết định mới hơn thắng (webui/workshop_merge.py).
                **({"at": float(at)} if isinstance(at, (int, float)) and not isinstance(at, bool) else {})})
    return sections


def accepted(sections: Mapping[int, Sequence[Mapping[str, Any]]]) -> dict[int, list[dict[str, Any]]]:
    """Chỉ các đoạn đã được nhận - những gì prompt phân tích và khoá lô đọc."""
    kept = {chapter: [dict(entry) for entry in entries if entry.get("accepted")] for chapter, entries in sections.items()}
    return {chapter: entries for chapter, entries in kept.items() if entries}


def narrator_at(sections: Mapping[int, Sequence[Mapping[str, Any]]], chapter_index: int, seq: int) -> str | None:
    """Người kể của câu `seq` ở chương `chapter_index` nếu một đoạn ĐÃ NHẬN chứa nó ("" = ngôi ba); None = không đoạn nào."""
    for entry in sections.get(chapter_index, ()):
        if entry.get("accepted") and int(entry["from_seq"]) <= seq <= int(entry["to_seq"]):
            return str(entry.get("narrator") or "")
    return None


def decide(project_root: Path | str, chapter_index: int, from_seq: int, to_seq: int, *, accepted: bool,
           narrator: str = "", source: str = "auto", now: float | None = None) -> None:
    """Ghi quyết định cho đoạn (chương, từ câu, đến câu): nhận (`accepted`, kèm người kể - "" = ngôi ba) hay bỏ qua."""
    sections = load(project_root)
    entries = [entry for entry in sections.get(int(chapter_index), []) if (entry["from_seq"], entry["to_seq"]) != (from_seq, to_seq)]
    entries.append({"from_seq": int(from_seq), "to_seq": int(to_seq), "narrator": narrator.strip()[:MAX_NAME],
                    "source": "owner" if source == "owner" else "auto", "accepted": bool(accepted), "dismissed": not accepted,
                    "at": time.time() if now is None else now})
    sections[int(chapter_index)] = sorted(entries, key=lambda entry: entry["from_seq"])
    _write(project_root, sections)


def forget(project_root: Path | str, chapter_index: int, from_seq: int, to_seq: int) -> bool:
    """Bỏ quyết định của đoạn (thẻ hỏi lại như chưa bấm). True khi file đổi."""
    sections = load(project_root)
    entries = sections.get(int(chapter_index), [])
    kept = [entry for entry in entries if (entry["from_seq"], entry["to_seq"]) != (from_seq, to_seq)]
    if len(kept) == len(entries):
        return False
    sections[int(chapter_index)] = kept
    _write(project_root, sections)
    return True


def _write(project_root: Path | str, sections: Mapping[int, Sequence[Mapping[str, Any]]]) -> None:
    target = Path(project_root) / FILE_NAME
    temporary = target.with_name(f".{FILE_NAME}.tmp")
    body = {"version": 1, "sections": {str(chapter): list(entries) for chapter, entries in sorted(sections.items()) if entries}}
    temporary.write_bytes(json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8"))
    os.replace(temporary, target)
