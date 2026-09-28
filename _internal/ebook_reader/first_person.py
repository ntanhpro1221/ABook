"""Truyện kể ngôi thứ nhất? Và "tôi" có thể là ai? - gợi ý cho câu hỏi lúc tạo sách (không LLM, không GPU).

Dòng prompt "người kể xưng 'tôi' là X" (`analysis._narrator_line`, bật bằng `voices.first_person_identity`) đưa model
tinh chỉnh từ 34,0% lên 89,4% người nói trên chương test ngôi thứ nhất YMP 248 (2026-09-27, docs/LLM_EVAL.md). Máy
đoán được TRUYỆN NÀO kể ngôi thứ nhất - tỉ lệ đoạn lời kể có "tôi/tớ/mình" (bỏ "mình" phản thân sau "của/tự"): 34-58% ở
các truyện ngôi thứ nhất của kho, 7-23% ở truyện ngôi thứ ba. Còn "tôi" LÀ AI thì chỉ gợi ý (tên viết hoa hay gặp nhất)
để người dùng chọn: đoán tự động từ văn bản thô từng nhận "Portal" cho YMP, vì 40 chương đầu của truyện ấy nhắc
"Samael" 103 lần ngay trong lời kể.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .io_utils import decode_text_bytes
from .text_processing import natural_key, segment_chapter_text

FIRST_PERSON_RATE = 0.30
# "mình" sau "của"/"tự" là phản thân ("cảm xúc của mình") - đầy trong truyện ngôi thứ ba.
NARRATOR_I = re.compile(r"(?<!của )(?<!tự )(?<!\w)(tôi|tớ|mình)(?!\w)", re.IGNORECASE)
_UPPER = "A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ"
_WORD = rf"[{_UPPER}][\w'-]*"
# Cụm viết hoa 1-3 chữ KHÔNG đứng đầu câu (sau chữ thường hoặc dấu phẩy): gần như luôn là tên riêng.
_NAME = re.compile(rf"(?<=[\w,;]\s)({_WORD}(?:\s{_WORD}){{0,2}})")
_HONORIFIC = re.compile(r"-(san|sama|kun|chan|sensei|senpai|dono|nii|nee)$", re.IGNORECASE)
# Chữ viết hoa giữa câu mà không phải tên (danh xưng, từ Hán-Việt hay viết hoa) - không gợi ý chúng.
_NOT_NAMES = {
    "Người", "Thần", "Chủ", "Cậu", "Tôn", "Học", "Tiểu", "Công", "Cổng", "Thẻ", "Ngài", "Anh", "Chị", "Em", "Cô",
    "Ông", "Bà", "Đại", "Thánh", "Vương", "Hoàng", "Thiếu", "Lão", "Sư", "Tộc", "Hội", "Viện", "Học Viện", "Portal",
}


def _names(text: str) -> list[str]:
    names = []
    for match in _NAME.finditer(text):
        name = _HONORIFIC.sub("", match.group(1))
        if len(name) >= 3 and name not in _NOT_NAMES and name.split()[0] not in _NOT_NAMES:
            names.append(name)
    return names


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
    """Đọc `chapters` chương đầu: {"rate", "firstPerson", "suggestions"} cho câu hỏi "'Tôi' là ai?" lúc tạo sách, và
    "chapters": các chương đổi góc kể trên CẢ cuốn (`pov_chapters`)."""
    narration = with_i = 0
    names: Counter = Counter()
    for index, path in enumerate(files[:chapters], 1):
        for row in segment_chapter_text(index, decode_text_bytes(Path(path).read_bytes())):
            text = str(row["text"])
            if row["kind_hint"] != "dialogue":
                narration += 1
                with_i += bool(NARRATOR_I.search(text))
            names.update(_names(text))
    rate = with_i / max(1, narration)
    return {
        "rate": round(rate, 3),
        "firstPerson": rate >= FIRST_PERSON_RATE,
        "suggestions": [name for name, _count in names.most_common(limit)],
        "chapters": pov_chapters(files),
    }
