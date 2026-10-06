"""Truyện kể ngôi thứ nhất? Và "tôi" có thể là ai? - gợi ý cho câu hỏi lúc tạo sách (không LLM, không GPU).

Dòng prompt "người kể xưng 'tôi' là X" (`analysis._narrator_line`, bật bằng `voices.first_person_identity`) đưa model
tinh chỉnh từ 34,0% lên 89,4% người nói trên chương test ngôi thứ nhất YMP 248 (2026-09-27, docs/LLM_EVAL.md). Máy
đoán được TRUYỆN NÀO kể ngôi thứ nhất - đếm THEO CHƯƠNG: chương có >= 20% đoạn lời kể chứa "tôi/tớ/mình" (bỏ "mình"
phản thân sau "của/tự") là chương kể ngôi thứ nhất; truyện có >= 30% chương mẫu như thế thì hỏi. Kho 29-09 (12 truyện, 20
chương đầu): truyện ngôi thứ nhất 40-100% chương, ngôi thứ ba 0-15%. Tỉ lệ gộp cả cuốn (cách cũ, ngưỡng 30%) bỏ sót hai
truyện ngôi thứ nhất: HDST 29,6%, Nageki 24,1% - Nageki chen chương ngoại truyện kể ngôi ba, Yamiyo mở đầu bằng nhiều
chương ngôi ba. Còn "tôi" LÀ AI thì chỉ gợi ý để người dùng chọn: đoán tự động từ văn bản thô từng nhận "Portal" cho
YMP, vì 40 chương đầu của truyện ấy nhắc "Samael" 103 lần ngay trong lời kể. Gợi ý xếp tên theo độ giống người kể
(`_suggestions`): người kể xưng "tôi" gần như không có tên cạnh chữ "tôi" trong lời kể, nhưng người đối diện gọi tên họ luôn.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .io_utils import decode_text_bytes
from .text_processing import natural_key, segment_chapter_text

FIRST_PERSON_RATE = 0.30
# Theo chương (xem đầu file): ngưỡng một chương, tỉ lệ chương của cả cuốn, và số đoạn lời kể tối thiểu để một chương được
# tính (chương vài dòng không nói được gì).
CHAPTER_RATE = 0.20
FIRST_PERSON_SHARE = 0.30
MIN_NARRATION = 8
# "mình" sau "của"/"tự" là phản thân ("cảm xúc của mình") - đầy trong truyện ngôi thứ ba.
NARRATOR_I = re.compile(r"(?<!của )(?<!tự )(?<!\w)(tôi|tớ|mình)(?!\w)", re.IGNORECASE)
_UPPER = "A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
_WORD = rf"[{_UPPER}][\w'-]*"
# Cụm viết hoa 1-3 chữ KHÔNG đứng đầu câu (sau chữ thường hoặc dấu phẩy): gần như luôn là tên riêng.
_NAME = re.compile(rf"(?<=[\w,;]\s)({_WORD}(?:\s{_WORD}){{0,2}})")
_HONORIFIC = re.compile(r"-(san|sama|kun|chan|sensei|senpai|dono|nii|nee|nim|ssi|yah|hyung|nuna|noona|oppa|unnie)$", re.IGNORECASE)
# Chữ viết hoa giữa câu mà không phải tên (danh xưng, từ Hán-Việt hay viết hoa) - không gợi ý chúng.
_NOT_NAMES = {
    "Người", "Thần", "Chủ", "Cậu", "Tôn", "Học", "Tiểu", "Công", "Cổng", "Thẻ", "Ngài", "Anh", "Chị", "Em", "Cô",
    "Ông", "Bà", "Đại", "Thánh", "Vương", "Hoàng", "Thiếu", "Lão", "Sư", "Tộc", "Hội", "Viện", "Học Viện", "Portal",
}
# Đại từ và tiếng gọi người thân hay đứng một mình ở đầu/cuối câu thoại: được GỌI nhiều và lời kể không nhắc, nhìn như người
# kể nhưng không phải tên ai (chỉ lọc ở bước gợi ý, `pov_chapters` không dùng).
_NOT_NARRATOR = {
    "Ngươi", "Mày", "Hyung", "Oppa", "Noona", "Nuna", "Unnie", "Onii", "Onee", "Nii", "Nee", "Aniki", "Aneki", "Senpai",
    "Sensei", "Master",
}


def _bare(word: str) -> str:
    """Bỏ hậu tố kính ngữ chồng nhau ("Kin-chan-sama" -> "Kin") và dấu gạch cuối chữ."""
    while True:
        bare = _HONORIFIC.sub("", word.rstrip("-'"))
        if bare == word:
            return bare
        word = bare


def _names(text: str) -> list[str]:
    names = []
    for match in _NAME.finditer(text):
        name = " ".join(_bare(word) for word in match.group(1).split())
        if len(name) >= 3 and name not in _NOT_NAMES and name.split()[0] not in _NOT_NAMES:
            names.append(name)
    return names


# Người kể xưng "tôi" gần như không có tên trong lời kể, nhưng người đối diện GỌI tên họ - đúng chỗ `_NAME` bỏ sót: tên đứng
# ĐẦU câu thoại ("“Samael, cậu đến muộn rồi.”") không có chữ thường hay dấu phẩy phía trước. Nên sau khi lấy danh sách tên
# (`_names`), đếm lại từng tên THEO VỊ TRÍ: GỌI = tên kẹp giữa ngoặc/dấu câu hoặc sau danh xưng ("Ê, Kazuma-dono!").
_NAME_SUFFIX = r"(?:-[a-z]+)?(?![\w-])"
_CALL_BEFORE = "“\"‘'«(-–—,.!?…~:["
_CALL_AFTER = ",.!?…~;:”\"’')]»"
_CALL_TITLE = re.compile(r"(?<!\w)(?:ngài|anh|chị|cậu|em|cô|ông|bà|thầy|tiểu thư|công chúa|hoàng tử|điện hạ|đại nhân|sư phụ)$",
                         re.IGNORECASE)
# "tên tôi là X", "tôi là X", "gọi tôi là X": tự giới thiệu.
_SELF_INTRO = re.compile(
    rf"(?i:tên (?:của )?(?:tôi|mình|tớ) là|(?:tôi|tớ|mình)(?: tên)? là|gọi (?:tôi|tớ|mình) là|(?:tôi|tớ|mình) tên)"
    rf"\s+({_WORD}(?:\s{_WORD}){{0,2}})"
)
_TOKEN = re.compile(r"\w+(?:-\w+)*")
# Điểm = tổng có trọng số của log(1 + số lần), trọng số khớp (logit có điều kiện, 20 chương đầu, 25 truyện ngôi thứ nhất,
# 2026-10-06): gọi và nhắc trong lời thoại là dương; nhắc trong LỜI KỂ, nhất là câu lời kể có cả "tôi" ("Aqua nhìn tôi") là
# âm - người kể không nằm cạnh chính mình; tên trùng từ thường ("Quỷ", "Thịt") chỉ bị trừ nhẹ, không cấm (có thể là biệt danh).
_W_CALLED, _W_SPOKEN, _W_NARRATED, _W_WITH_I, _W_INTRO, _W_COMMON_WORD = 2.0, 1.2, -0.2, -0.8, 1.5, -0.5


def _count_names(rows: list[tuple[str, str]], names: set[str]) -> dict[str, Counter]:
    """{tên: Counter(called, spoken, narrated, with_i)} - `rows` là (kind, text) mỗi đoạn."""
    stats: dict[str, Counter] = {name: Counter() for name in names}
    pattern = re.compile(rf"(?<![\w-])({'|'.join(re.escape(name) for name in sorted(names, key=lambda n: (-len(n), n)))}){_NAME_SUFFIX}")
    for kind, text in rows:
        dialogue = kind == "dialogue"
        with_i = not dialogue and bool(NARRATOR_I.search(text))
        for match in pattern.finditer(text):
            found = stats[match.group(1)]
            if not dialogue:
                found["narrated"] += 1
                found["with_i"] += with_i
                continue
            found["spoken"] += 1
            before, after = text[:match.start(1)].rstrip(" "), text[match.end():].lstrip(" ")
            if (not before or before[-1] in _CALL_BEFORE or _CALL_TITLE.search(before)) and (not after or after[0] in _CALL_AFTER):
                found["called"] += 1
    return stats


def _merge_forms(stats: dict[str, Counter]) -> dict[str, list[str]]:
    """Gộp các dạng của một người: tên một chữ là họ/tên của cụm dài hơn ("Yangcheon" -> "Gu Yangcheon"; chọn cụm dài hay
    gặp nhất), hoặc là dạng gọi tắt đầu chữ ("Juli" -> "Juliana"). Trả {tên đại diện: các dạng}; đại diện là dạng hay gặp nhất."""
    def total(name: str) -> int:
        return stats[name]["spoken"] + stats[name]["narrated"]

    order = sorted(stats, key=lambda name: (-total(name), name))
    phrases = [name for name in order if " " in name]
    parent: dict[str, str] = {}
    for name in order:
        if " " in name:
            continue
        parent_name = next((phrase for phrase in phrases if name in (phrase.split()[0], phrase.split()[-1])), None)
        if parent_name is None:
            parent_name = next((other for other in order if other != name and " " not in other and other.startswith(name)
                                and len(other) - len(name) <= 4 and 2 * total(other) >= total(name)), None)
        if parent_name is not None:
            parent[name] = parent_name
    groups: dict[str, list[str]] = {}
    for name in order:
        root, hops = name, 0
        while root in parent and hops < 5:
            root, hops = parent[root], hops + 1
        groups.setdefault(root, []).append(name)
    return {max(forms, key=lambda name: (total(name), name)): forms for forms in groups.values()}


def _suggestions(rows: list[tuple[str, str]], limit: int) -> list[str]:
    """Xếp hạng tên theo độ giống người kể "tôi". Tên mà người khác GỌI nhiều và lời kể ít nhắc (nhất là cạnh chữ "tôi")
    lên đầu. Top-1 đúng: 72% -> 96% trên 25 truyện dò tham số, 71% -> 94% trên 17 truyện để riêng
    (top-3 94% -> 100%). Zenith: "Yangcheon" trước không lọt 6 gợi ý vì tên đứng đầu câu thoại không được đếm; YMP: "Samael"
    trước "Juli" (gọi tắt của Juliana). Chỉ là gợi ý, người dùng vẫn xác nhận - tên bằng chứng yếu vẫn có thể đứng đầu."""
    counts = Counter(name for _kind, text in rows for name in _names(text))
    names = {name for name, count in counts.items() if count >= 2 and name not in _NOT_NARRATOR}
    if not names:
        return []
    stats = _count_names(rows, names)
    # Chữ thường nào xuất hiện nhiều ("quỷ", "thịt") thì viết hoa giữa câu chỉ là danh xưng/thuật ngữ, không phải tên.
    lower: Counter = Counter(word for _kind, text in rows for word in _TOKEN.findall(text) if word[0].islower())
    intros: Counter = Counter()
    for _kind, text in rows:
        intros.update(" ".join(_bare(word) for word in match.group(1).split()) for match in _SELF_INTRO.finditer(text))
    scored = []
    for label, forms in _merge_forms(stats).items():
        total: Counter = Counter()
        for form in forms:
            total.update(stats[form])
        intro = sum(count for who, count in intros.items() if who in forms or label in who.split())
        common = min(lower[word.lower()] for word in label.split()) >= 3
        called, spoken = total["called"], total["spoken"] - total["called"]
        score = (_W_CALLED * math.log1p(called) + _W_SPOKEN * math.log1p(spoken) + _W_NARRATED * math.log1p(total["narrated"])
                 + _W_WITH_I * math.log1p(total["with_i"]) + _W_INTRO * math.log1p(intro) + _W_COMMON_WORD * common)
        scored.append((-score, label))
    return [label for _score, label in sorted(scored)[:limit]]


# "Chương 11: Yuuko Hayase" - tiêu đề chương là TÊN một nhân vật (2-3 chữ viết hoa, không số): light novel đặt thế cho
# chương kể bằng "tôi" của chính người ấy (Love Unseen 11-13).
_LOWER = "a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
_AFTER_LOWER = re.compile(rf"(?<=[{_LOWER}] )({_WORD})")
_POV_TITLE = re.compile(r"^\s*(?:chương|chapter|ch\.?)\s*[\divxlc]+\s*[:：.\-–—]\s*(.+?)\s*$", re.IGNORECASE)


def pov_chapters(files: list[Path], book_narrator: str = "", min_mentions: int = 5, top_names: int = 20) -> list[dict[str, Any]]:
    """Chương đổi góc kể: tiêu đề là tên một nhân vật VÀ lời kể của chương dùng "tôi" nhiều như truyện ngôi thứ nhất.
    Trả [{"chapter": số thứ tự trong sách (chapters.chapter_index, từ 1), "title", "name"}] - chỉ là gợi ý cho người
    dùng chọn; chương mà tên ấy chính là người kể cả cuốn thì bỏ (không có gì để đổi). Bản dịch viết hoa MỌI chữ của
    tên chương ("Chương 7: Tấm Khiên Thịt") nên chữ viết hoa chưa đủ: ít nhất một chữ của tên phải nằm trong
    `top_names` tên riêng cả cuốn nhắc nhiều nhất ("Hayase" - không phải "Khiên", "Teresa")."""
    ordered = sorted((Path(path) for path in files), key=lambda path: natural_key(path.name))
    texts = [decode_text_bytes(path.read_bytes()) for path in ordered]
    candidates: list[tuple[int, str, str]] = []
    for index, text in enumerate(texts, 1):
        title = next((line.strip() for line in text.splitlines() if line.strip()), "")
        match = _POV_TITLE.match(title)
        words = match.group(1).split() if match else []
        if not 2 <= len(words) <= 3 or any(not re.fullmatch(_WORD, word) or word in _NOT_NAMES for word in words):
            continue
        name = " ".join(words).upper()
        if name != book_narrator.strip().upper():
            candidates.append((index, title, name))
    if not candidates:
        return []
    # Tên riêng của cuốn: chữ viết hoa ngay sau một chữ THƯỜNG ("nói với Hayase") - không sau dấu phẩy hay đầu câu, nơi
    # bản dịch viết hoa cả chữ thường ("..., Không"). Lấy những chữ hay gặp nhất: nhân vật chính, không phải chữ lạc.
    mentions: Counter = Counter()
    for text in texts:
        mentions.update(match.group(1) for match in _AFTER_LOWER.finditer(text) if match.group(1) not in _NOT_NAMES)
    top = {word for word, count in mentions.most_common(top_names) if count >= min_mentions}
    found: list[dict[str, Any]] = []
    for index, title, name in candidates:
        if not any(word in top for word in title.split(":", 1)[-1].split()):
            continue
        rows = [row for row in segment_chapter_text(index, texts[index - 1]) if row["kind_hint"] != "dialogue"]
        rate = sum(bool(NARRATOR_I.search(str(row["text"]))) for row in rows) / max(1, len(rows))
        # Người kể không tự gọi tên mình trong lời kể; chương kể VỀ người ấy thì tên đầy lời kể ("Chương 8: Nguyền Kiếm"
        # của Nise - Alistar kể về thanh kiếm). Chương của Hayase chỉ có tên cô trong lời người khác gọi.
        words = [word for word in title.split(":", 1)[-1].split() if len(word) >= 3]
        told_about = sum(str(row["text"]).casefold().count(word.casefold()) for row in rows[1:] for word in words)
        if rate >= FIRST_PERSON_RATE and told_about <= 2:
            found.append({"chapter": index, "title": title, "name": name})
    return found


def first_person_hint(files: list[Path], chapters: int = 20, limit: int = 6) -> dict[str, Any]:
    """Đọc `chapters` chương đầu: {"rate", "firstPerson", "chaptersWithI", "chaptersSampled", "suggestions"} cho câu hỏi
    "'Tôi' là ai?" lúc tạo sách, và "chapters": các chương đổi góc kể trên CẢ cuốn (`pov_chapters`)."""
    narration = with_i = 0
    sampled = told_with_i = 0
    rows: list[tuple[str, str]] = []
    for index, path in enumerate(files[:chapters], 1):
        chapter_narration = chapter_with_i = 0
        for row in segment_chapter_text(index, decode_text_bytes(Path(path).read_bytes())):
            text = str(row["text"])
            if row["kind_hint"] != "dialogue":
                chapter_narration += 1
                chapter_with_i += bool(NARRATOR_I.search(text))
            rows.append((str(row["kind_hint"]), text))
        narration += chapter_narration
        with_i += chapter_with_i
        if chapter_narration >= MIN_NARRATION:
            sampled += 1
            told_with_i += chapter_with_i / chapter_narration >= CHAPTER_RATE
    rate = with_i / max(1, narration)
    share = told_with_i / sampled if sampled else 0.0
    return {
        "rate": round(rate, 3),
        "firstPerson": rate >= FIRST_PERSON_RATE or share >= FIRST_PERSON_SHARE,
        "chaptersWithI": told_with_i,
        "chaptersSampled": sampled,
        "suggestions": _suggestions(rows, limit),
        "chapters": pov_chapters(files),
    }
