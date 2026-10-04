"""Studio: pha đọc tên (`analysis.reconcile_name_pronunciations`) theo cùng luật với "Nghe ngay" (docs/READING_FOREIGN_NAMES.md mục 8).

Trước đây Studio không biết gốc cuốn và Việt hoá MỌI tên Latin bằng CMU / LLM ("Haruto" theo âm Anh, "Michael" thành "Mai-cồ"). Giờ, trước CMU / LLM:
  - cuốn gốc Nhật / Hàn (`book_origin_for_project`, chính `readaloud.names.book_origin` trên chữ các chương): tên đọc được theo luật phiên âm
    khoá bằng luật (`rule_reading`, nguồn `rule_romanization`);
  - tên / từ tiếng Anh (danh sách từ Anh và tên Anh / Âu của "Nghe ngay") giữ nguyên chữ khi máy đọc nói được tiếng Anh (`keeps_english`,
    nguồn `keep_english`).
Còn lại (tên fantasy, tên luật không tách được) đi đường cũ: CMU, rồi LLM (có thêm gốc cuốn và vài phán quyết chủ sách trong prompt), rồi bộ dự phòng.
Mọi phần ở đây là luật dùng lại của "Nghe ngay"; không chép lại luật nào.
"""
from __future__ import annotations

from typing import Any

from .models import KEEP_ENGLISH_PRONUNCIATION_SOURCE, RULE_ROMANIZATION_PRONUNCIATION_SOURCE
from .readaloud import names as readaloud_names
from .vietnamese_syllable import valid_spoken_form

# Bảng cách đọc của dự án ghi chữ Anh để nguyên (nguồn `keep_english`) như cho máy đọc nói được tiếng Anh: VieNeu đi qua cùng sea-g2p với
# "Nghe ngay" (vieneu_utils.phonemize_text) - thử 04-10 trên CPU: "Kate", "Michael", "Washington" để nguyên được Whisper nghe "Kết", "Michael",
# "Washington". Máy không nói được (cờ `speaks_english` của adapter trong tts.py: Supertonic) Việt hoá mục ấy lúc đúc, theo giọng của từng đoạn.
STUDIO_ENGINE_SPEAKS_ENGLISH = True
RULE_READING_CONFIDENCE = 0.95  # luật đã chốt bằng phán quyết chủ sách, không phải đoán: trên ngưỡng tin cậy của pha đọc tên
# Ví dụ cho prompt LLM: chữ của ca chủ sách (tests/romanization_evidence.py, english_vi.OWNER); cách đọc do chính luật tính, không chép tay.
PROMPT_EXAMPLES = {
    "ja": ("Haruto-kun", "Kyouko", "Shinomiya", "Tsubasa"),
    "ko": ("Taehyun", "Seojun", "Yejin", "Chaeyeon"),
    None: ("Thomas", "Damien", "Darius", "Walker"),
}


def chapter_texts(db: Any) -> list[str]:
    """Chữ từng chương của dự án, theo thứ tự chương (ghép từ các đoạn)."""
    texts: dict[int, list[str]] = {}
    for row in db.list_segments():
        texts.setdefault(int(row["chapter_id"]), []).append(str(row["text"]))
    return ["\n".join(texts[int(chapter["id"])]) for chapter in db.list_chapters() if int(chapter["id"]) in texts]


def book_origin_for_project(db: Any) -> str | None:
    """"ja" / "ko" / None cho cả dự án, đoán như "Nghe ngay" (`readaloud.names.book_origin`, cùng số chương mẫu và ngưỡng). Studio chưa có chỗ
    cho người dùng ghi đè gốc; chữ dự án không đổi nên lần đoán lặp lại y hệt."""
    return readaloud_names.book_origin(chapter_texts(db))


def rule_reading(surface: str, origin: str | None) -> str | None:
    """Cách đọc theo luật phiên âm của tên `surface` (một hay nhiều chữ, có thể kèm hậu tố gọi: "Haruto-kun") trong cuốn gốc `origin`, hay None
    khi có chữ luật không đọc (từ Anh, âm tiết Việt, tiếng reo...) hoặc cách đọc ra có âm tiết bộ kiểm chặt không nhận."""
    words = surface.split()
    if origin not in readaloud_names.ORIGINS or not words:
        return None
    readings = [readaloud_names.name_reading(word, origin) for word in words]
    if any(reading is None for reading in readings):
        return None
    spoken = " ".join(readings)
    return spoken if valid_spoken_form(spoken) else None


def _english_word(word: str) -> bool:
    plain = word.replace("-", "").lower()
    return plain in readaloud_names.english_words() and readaloud_names.english_reading(word) is not None


def keeps_english(surface: str, origin: str | None, engine_speaks_english: bool) -> bool:
    """Tên / từ tiếng Anh để nguyên chữ cho máy đọc nói được tiếng Anh: mọi chữ có trong danh sách từ Anh và tên Anh / Âu của "Nghe ngay" (bỏ
    chữ TOÀN HOA, âm tiết Việt viết sẵn). Tên mà luật phiên âm của gốc cuốn đã đọc được thì không giữ (gốc cuốn quyết, như "Nghe ngay")."""
    words = surface.split()
    if not engine_speaks_english or not words or rule_reading(surface, origin) is not None:
        return False
    return all(_english_word(word) for word in words)


def planned_reading(surface: str, origin: str | None, engine_speaks_english: bool | None = None) -> tuple[str, str] | None:
    """(cách đọc, nguồn) khi luật quyết được cả tên, None khi để đường cũ (CMU / LLM). Tên nhiều chữ quyết từng chữ ("Haruto Smith" ->
    "Ha-ru-tô Smith", "Kim Seo-yeon" -> "Kim Xeo-gion": âm tiết Việt viết sẵn giữ nguyên), để cùng một chữ đứng riêng hay trong tên đầy đủ đọc
    như nhau; có một chữ nào luật không quyết thì cả tên đi đường cũ."""
    from .analysis import is_vietnamese_syllable

    if engine_speaks_english is None:
        engine_speaks_english = STUDIO_ENGINE_SPEAKS_ENGLISH
    spoken: list[str] = []
    by_rule = by_english = False
    for word in surface.split():
        reading = rule_reading(word, origin)
        if reading is not None:
            spoken.append(reading)
            by_rule = True
        elif keeps_english(word, origin, engine_speaks_english):
            spoken.append(word)
            by_english = True
        elif is_vietnamese_syllable(word.lower()):
            spoken.append(word)
        else:
            return None
    if not by_rule and not by_english:
        return None
    return " ".join(spoken), RULE_ROMANIZATION_PRONUNCIATION_SOURCE if by_rule else KEEP_ENGLISH_PRONUNCIATION_SOURCE


def lockable(surface: str, spoken_form: str) -> bool:
    """Bộ kiểm chặt cho cách đọc do luật sinh, trước khi khoá: từng chữ giữ nguyên mặt chữ (tiếng Anh), hoặc mọi âm tiết hợp lệ
    (`vietnamese_syllable.valid_spoken_form`)."""
    words, spoken = surface.split(), spoken_form.split()
    return len(words) == len(spoken) and all(said == word or valid_spoken_form(said) for word, said in zip(words, spoken))


def rule_word_corrections(pronunciations: list[Any]) -> dict[str, str]:
    """{tên nhiều chữ: cách đọc sửa} khi một chữ của nó đã có cách đọc do luật (đứng riêng) mà tên đầy đủ (đi CMU / LLM) đọc chữ ấy khác:
    "Michael" giữ tiếng Anh nhưng "Michael Godswill" khoá "Mai-cồ Gót-uyu" là một tên hai cách đọc. Chữ do luật thắng; `analysis.
    name_component_corrections` chạy sau và thấy hai bên đã khớp. Chỉ sửa khi số chữ và số nhóm âm tiết khớp nhau."""
    decided = {str(row["surface"]): str(row["spoken_form"]) for row in pronunciations
               if str(row["source"]) in (RULE_ROMANIZATION_PRONUNCIATION_SOURCE, KEEP_ENGLISH_PRONUNCIATION_SOURCE)
               and len(str(row["surface"]).split()) == 1}
    corrections: dict[str, str] = {}
    for row in pronunciations:
        words, groups = str(row["surface"]).split(), str(row["spoken_form"]).split()
        if len(words) < 2 or len(words) != len(groups):
            continue
        fixed = [decided.get(word, group) for word, group in zip(words, groups)]
        if fixed != groups:
            corrections[str(row["surface"])] = " ".join(fixed)
    return corrections


def prompt_context(origin: str | None) -> str:
    """Một câu cho prompt LLM: gốc cuốn và vài cách đọc chủ sách đã chốt, đúng gốc ấy."""
    if origin == "ja":
        head = "Cuốn này gốc Nhật: tên Nhật viết romaji đọc theo phiên âm, mỗi âm tiết như cách chủ sách đã chốt"
        examples = [(word, rule_reading(word, origin)) for word in PROMPT_EXAMPLES["ja"]]
    elif origin == "ko":
        head = "Cuốn này gốc Hàn: tên Hàn viết Latin đọc theo phiên âm, mỗi âm tiết như cách chủ sách đã chốt"
        examples = [(word, rule_reading(word, origin)) for word in PROMPT_EXAMPLES["ko"]]
    else:
        from .english_vi import vietnamized_english

        head = "Cách đọc tên tiếng Anh chủ sách đã chốt"
        examples = [(word, vietnamized_english(word)) for word in PROMPT_EXAMPLES[None]]
    shown = ", ".join(f"{word}→{reading}" for word, reading in examples if reading)
    return f"{head}: {shown}." if shown else ""
