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
from .text_processing import segment_chapter_text

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


def first_person_hint(files: list[Path], chapters: int = 20, limit: int = 6) -> dict[str, Any]:
    """Đọc `chapters` chương đầu: {"rate", "firstPerson", "suggestions"} cho câu hỏi "'Tôi' là ai?" lúc tạo sách."""
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
    }
