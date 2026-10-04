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

import unicodedata
from typing import Any

from .models import KEEP_ENGLISH_PRONUNCIATION_SOURCE, RULE_ROMANIZATION_PRONUNCIATION_SOURCE
from .readaloud import names as readaloud_names
from .vietnamese_syllable import valid_spoken_form, valid_syllable

# Máy đọc nói được âm vị tiếng Anh (docs/READING_FOREIGN_NAMES.md mục 4 và 8, đo 04-10): VieNeu, ZeroTTS có; Supertonic nuốt "Rose", "Haruto".
ENGINE_SPEAKS_ENGLISH = {"vieneu": True, "zerotts": True, "supertonic": False}
# Studio ở nhánh này chỉ đúc bằng VieNeu (tts.VieNeuEngine từ chối hồ sơ giọng khác), và VieNeuEngine đi qua cùng sea-g2p với "Nghe ngay"
# (vieneu_utils.phonemize_text) - thử 04-10 trên CPU: "Kate", "Michael", "Washington" để nguyên được Whisper nghe "Kết", "Michael", "Washington".
STUDIO_ENGINE_SPEAKS_ENGLISH = ENGINE_SPEAKS_ENGLISH["vieneu"]
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


# Chữ Anh để nguyên thì Whisper (nghe tiếng Việt) hay viết lại theo âm nó nghe: "Kate" -> "Kết" / "Kat", "Shadow" -> "Sado", "Portal" -> "Porto"
# (đo 04-10, VieNeu Studio trên CPU). Ở câu ngắn một chữ như thế đủ đánh trượt cả câu ("Kate gật đầu.": WER 0,33), nên khâu so của ASR coi
# chữ nghe được là khớp khi khung phụ âm của nó gần khung của chữ Anh ở câu mong đợi. Bảng gộp phụ âm cùng âm (c / k / q, s / x / z / sh, ph / f...).
_SKELETON_DIGRAPHS = (("sh", "s"), ("ch", "c"), ("ph", "f"), ("th", "t"), ("ck", "k"), ("gh", "g"), ("ng", "n"), ("nh", "n"))
_SKELETON_LETTERS = str.maketrans({"c": "k", "q": "k", "x": "s", "z": "s", "j": "g", "v": "f", "đ": "d"})


def _skeleton(word: str) -> str:
    """Khung phụ âm: bỏ dấu, gộp phụ âm cùng âm, bỏ nguyên âm và h / w / y (bán âm, âm câm), gộp phụ âm lặp."""
    plain = "".join(ch for ch in unicodedata.normalize("NFD", word.casefold()) if unicodedata.category(ch) != "Mn")
    for digraph, single in _SKELETON_DIGRAPHS:
        plain = plain.replace(digraph, single)
    consonants = [ch for ch in plain.translate(_SKELETON_LETTERS) if ch.isalpha() and ch not in "aeiouhwy"]
    return "".join(ch for index, ch in enumerate(consonants) if not index or consonants[index - 1] != ch)


def heard_as_english(expected: str, heard: str) -> bool:
    """`heard` (một chữ Whisper viết) có phải là chữ Anh `expected` (để nguyên trong câu) đọc ra không: khung phụ âm trùng, hay lệch một phụ âm khi
    khung có từ ba phụ âm ("Portal" / "Porto"), và cùng phụ âm đầu."""
    want, got = _skeleton(expected), _skeleton(heard)
    if not want or not got or want[0] != got[0]:
        return False
    if want == got:
        return True
    from .asr import _edit_distance

    return len(want) >= 3 and _edit_distance(list(want), list(got)) <= 1


def soften_english_words(expected: str, actual: str) -> str:
    """Bản nghe (`actual`, đã chuẩn hoá như `asr.normalize_transcript`) với mỗi chữ nghe được của một chữ Anh trong câu mong đợi thay bằng chính chữ
    Anh ấy; chữ khác giữ nguyên. Chữ Anh: chữ Latin không dấu mà không là âm tiết tiếng Việt."""
    english = [word for word in expected.split() if word.isascii() and word.isalpha() and not valid_syllable(word)]
    if not english:
        return actual
    present = set(expected.split())
    words = actual.split()
    for index, word in enumerate(words):
        if word in present:
            continue
        match = next((candidate for candidate in english if heard_as_english(candidate, word)), None)
        if match is not None:
            words[index] = match
    return " ".join(words)


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
