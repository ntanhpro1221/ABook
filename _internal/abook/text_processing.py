from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from .io_utils import decode_text_bytes, natural_key, sha256_bytes, sha256_file, sha256_text, slugify


QUOTE_PATTERN = re.compile(r"([“\"][^”\"]{1,1600}[”\"])", re.DOTALL)
# Bản dịch hay mở ‘ rồi đóng bằng dấu ' thẳng ("được gọi là ‘tổng hợp ý kiến'."): dấu ' bám cuối chữ và theo sau là khoảng
# trắng / dấu câu / hết dòng thì đóng ‘. Dấu ' nằm GIỮA chữ (tên phiên âm "Ma'at", "I'm") không đóng gì. Không nhận nó
# thì nội tâm không bao giờ đóng và khoá giọng nội tâm tràn sang mọi câu kể phía sau.
THOUGHT_CLOSING_PATTERN = re.compile(r"’|(?<=\S)'(?!\w)")
THOUGHT_QUOTE_PATTERN = re.compile(
    rf"(‘[^’]{{1,1600}}?(?:{THOUGHT_CLOSING_PATTERN.pattern}))",
    re.DOTALL,
)
CURLY_QUOTE_SPECS = (
    ("“", "”", "dialogue"),
    ("‘", "’", "thought"),
)
QUOTE_CLOSING_MARKS = {"”", "’", '"'}
QUOTE_CLOSING_PATTERNS = {"’": THOUGHT_CLOSING_PATTERN}
# Một dòng NGUYÊN VẸN trong 『…』 là một giọng nói: kẻ nhập xác (Yamiyo no Hotaru), bảng thông báo game (Năng lực bá
# đạo), tiếng qua loa/điện thoại (Two Childhood Friends). Cụm 『…』 nằm GIỮA câu kể là thuật ngữ - để yên, vì đổi giọng
# giữa một câu kể là sai. 『 cố ý KHÔNG vào CURLY_QUOTE_SPECS: theo lối Nhật nó là ngoặc lồng trong 「…」 (nay là “”).
WHITE_CORNER_QUOTE_LINE_PATTERN = re.compile(r"『[^』]{1,1600}』")
# Cũng vậy với [ … ] và 【 … 】 nguyên dòng: bản dịch LN dùng [ ] cho lời thoại, nội tâm, bảng thông báo game/hệ thống, tiếng
# quái vật, tiếng qua điện thoại (đếm Corpus 05-10: Hige wo Soru 6.765 dòng [..] trên 867 “; Hero Summoning 8.873 trên 881);
# 【 】 chủ yếu là bảng hệ thống ("【Bạn đã lên cấp.】", 6.249 dòng, Tensei dragon-egg 2.496). Để chúng là lời kể thì cả cuốn gần
# như một giọng. Ai nói (kể cả người kể / "Hệ thống") là việc của model phân tích - parser chỉ khoá ranh giới "đây là một
# giọng", giống 『…』. Ngoặc GIỮA câu kể (thuật ngữ, chú thích) và dòng không có chữ cái ("[...]", "[12]", "[________!]")
# ở yên như cũ.
LETTERED_VOICE_LINE_PATTERNS = (
    re.compile(r"\[[^\]]{1,1600}\]"),
    re.compile(r"【[^】]{1,1600}】"),
)
# GHI CHÚ của người dịch / nhóm dịch nguyên dòng trong ngoặc ("[Note: Tui tiểu đường mất!!!]", "[TL note: ...]", "[Từ chương này
# mình sẽ bắt đầu dịch từ bản Jap...]") không phải giọng nào: ở yên là lời kể như cũ. Nhận bằng NHÃN MỞ ĐẦU (sau ngoặc, bỏ khoảng
# trắng và * _ ~) kết bằng dấu hai chấm / gạch / hết dòng - "[Ghi chú? Cậu đang nói gì vậy?]" là lời thoại thật, không có nhãn -
# và câu xưng "mình ... dịch" trong một câu; "đại dịch / dịch chuyển / dịch vụ / dịch bệnh" là từ thường, không tính.
# "Ghi chú" / "Chú thích" đứng một mình KHÔNG phải nhãn: game dùng chúng cho bảng hệ thống ("【Chú thích: Cây sáo của thần Pan…】"),
# và loại nhầm giọng hệ thống thì mất vai, còn để lọt một ghi chú thật chỉ đổi giọng đọc. Chỉ "Ghi chú của dịch giả" mới tính.
TRANSLATOR_NOTE_LABEL_PATTERN = re.compile(
    r"^[\s*_~]*(?:lời\s+)?(?:t/n|n/t|n/a|tl[\s-]*note|tl|translator(?:'s)?[\s-]*note|trans(?:lator)?|editor|edit|note|nd|n\.d|"
    r"người dịch|dịch giả|(?:ghi chú|chú thích)(?=\s+của\s+(?:dịch giả|người dịch|nhóm dịch))|nhóm dịch|raw|eng|"
    r"bản\s+(?:jap|eng))"
    r"(?:\s+của\s+(?:dịch giả|người dịch|nhóm dịch|editor))?(?:\s*\d+)?\s*(?:[:：]|[-–—](?=\s)|$)",
    re.IGNORECASE,
)
TRANSLATOR_SELF_REFERENCE_PATTERN = re.compile(
    r"\b(?:bọn mình|tụi mình|nhóm mình|mình)\b[^.!?]{0,80}?(?<!đại )(?<!ôn )\bd[ịi]ch\b(?!\s+(?:chuyển|vụ|bệnh|hạch|tễ))",
    re.IGNORECASE,
)
INLINE_REFERENCE_MARKER_PATTERN = re.compile(r"\[\s*note\d+\s*\]", re.IGNORECASE)
# Dòng ghi công người dịch / biên tập ở đầu chương ("*Edit: Lắc", "TL : NicK", "Translator: NicK", "Editor: Deemo"): TTS
# từng đọc to như một câu kể - 17 chương Throne, 172 chương Nise (quét kho 29-09). Chỉ trong vài dòng đầu chương, nhãn ghi
# công rõ ràng, phần tên ngắn không kết câu: "Tác giả: Lucien Evans X, Arcanist cấp một…" ở giữa chương 211 là câu truyện
# và ở lại ("tác giả" không phải nhãn ở đây, và dòng ấy không ở đầu chương).
CREDIT_LINE_PATTERN = re.compile(
    r"^[*_~#>\-–—\s]*(?:edit(?:or|ed by)?|tl|t/l|trans(?:lator|lated by)?|dịch(?: giả)?|người dịch|biên tập(?: viên)?|"
    r"beta(?:[- ]?reader)?|converter|cvt|proof ?read(?:er)?|typesetter)\s*[:：]\s*[^\s.!?…\"“”][^.!?…\"“”]{0,39}$",
    re.IGNORECASE,
)
CREDIT_WINDOW_LINES = 6
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…;:])\s+")
CLAUSE_BOUNDARY = re.compile(r"(?<=[.!?…;:,])\s+")
SENTENCE_SPLIT_STRATEGY = "sentence_v1"
SENTENCE_SPLIT_MAX_CHARS = 170
CLAUSE_SPLIT_STRATEGY = "clause_v1"
CLAUSE_SPLIT_MAX_CHARS = 120
CLAUSE_SPLIT_MIN_TAIL_CHARS = 32
SPLIT_STRATEGY_FIELD = "split_strategy"
SPLIT_MAX_CHARS_FIELD = "split_max_chars"
SPLIT_MAX_CHARS_BY_STRATEGY = {
    SENTENCE_SPLIT_STRATEGY: SENTENCE_SPLIT_MAX_CHARS,
    CLAUSE_SPLIT_STRATEGY: CLAUSE_SPLIT_MAX_CHARS,
}
SPEECH_VERB_PATTERN = re.compile(
    r"\b(?:nói|hỏi|đáp|trả lời|quát|hét|gào|thì thầm|lẩm bẩm|kêu|bảo|ra lệnh|cười)\b",
    re.IGNORECASE,
)
# Dòng mở bằng gạch là lượt thoại ở chương viết thoại bằng gạch (Tắt đèn, Tam quốc). Ở chương viết thoại trong ngoặc kép,
# một dòng gạch hiếm hoi thường là gạch ngang của LỜI KỂ ("-Hoặc không, vì hắn đã nhảy tránh được."): thầy gán nhãn a2w4
# (06-10) và đáp án gold (evil_lord 02:57, re_zero 065a:130, eiyuu_to_majo 05:56) đều trả lời lời kể cho những dòng như
# thế. Chỉ đổi khi cả chương lẫn dòng cùng nói vậy (`_dash_line_is_narration`, thận trọng: hai dòng gold sau vẫn khoá
# thoại). Quét Corpus 06-10: 1.069 đoạn đổi sang lời kể; dòng gạch có lời nói thật ở chương ngoặc kép (Villain 22: 11 dòng
# gạch của một nhân vật) đều giữ thoại.
DASH_LINE_PATTERN = re.compile(r"^[—–-]+\s*(?=\S)")
QUOTE_LED_LINE_PATTERN = re.compile(r"^[“\"‘「『]")
QUOTED_CHAPTER_MIN_QUOTE_LINES = 10
QUOTED_CHAPTER_MAX_DASH_LINES = 3
_THIRD_PERSON = r"(?:hắn|họ|gã|lão|(?:anh|cô|ông|bà|cậu|nàng|chàng)\s+(?:ta|ấy))"
THIRD_PERSON_PATTERN = re.compile(rf"(?<!\w){_THIRD_PERSON}(?!\w)", re.IGNORECASE)
# Chủ ngữ ngôi ba + đã/đang/vừa/liền/bèn + động từ: "hắn đã nhảy", "Silk đã kháng cự" - không phải "Đợi đã.".
NARRATIVE_SUBJECT_PATTERN = re.compile(
    rf"(?<!\w)(?:{_THIRD_PERSON}"
    r"|(?!(?:Tôi|Mình|Ta|Chúng|Bọn|Cô|Nó|Anh|Em|Cậu|Ngài|Bạn|Người|Hãy|Đừng)(?!\w))[A-ZĐ]\w*(?:[\s-][A-ZĐ]\w*)*)"
    r"\s+(?:đã|đang|vừa|liền|bèn)\s+\w"
)
# Dấu hiệu lời nói: xưng hô ngôi một/hai (sau khi bỏ "cậu ta", "cô ấy"...), câu hỏi/cảm thán, tiểu từ cuối câu nói.
SPEECH_PRONOUN_PATTERN = re.compile(
    r"(?<!\w)(?:ta|ngươi|tớ|mày|tao|ngài|tui|mi|cậu|nàng|anh|em|con|tôi|mình|bạn|ông|bà|cháu|chị|chúng|bọn)(?!\w)",
    re.IGNORECASE,
)
# Ngôi một/hai chỉ có trong lời nói - kể cả dòng viết thường ("--giờ mới nhớ, cái đó là kỹ thuật gì mà ta.").
SPEECH_ONLY_PRONOUN_PATTERN = re.compile(r"(?<!\w)(?:ta|ngươi|tớ|mày|tao|ngài|tui|mi)(?!\w)", re.IGNORECASE)
SPEECH_MARK_PATTERN = re.compile(r"[?!~…*“”\"‘’「」『』\[\]〔〕()]|\.\.")
SPEECH_FINAL_PARTICLE_PATTERN = re.compile(
    r"(?<!\w)(?:chăng|à|ư|nhỉ|hả|nhé|nha|chứ|vậy|đấy|đâu|nào|ạ|mà|rồi|sao|thôi)\W*$",
    re.IGNORECASE,
)
# Từ dẫn một THUẬT NGỮ trong ngoặc (không phải lời nói): "gọi là “bang hội,”", "mang danh “thợ săn,”".
TERM_INTRODUCER_PATTERN = re.compile(
    r"\b(?:là|gọi|tên|chữ|từ|cụm|câu|hiệu|danh|như|kiểu|thành|mệnh danh|xưng)$",
)
PUNCTUATION_BREAK_MS = {
    ",": 180,
    ".": 320,
    "…": 600,
}
VOCAL_CUE_SPOKEN_FORMS = {
    "cười": "Ha ha...",
    "chuckle": "Ha ha...",
    "thở dài": "Hầy...",
    "sigh": "Hầy...",
    "hắng giọng": "Khụ khụ...",
    "clear throat": "Khụ khụ...",
}
VOCAL_CUE_PATTERN = re.compile(
    r"\[(cười|chuckle|thở\s+dài|sigh|hắng\s+giọng|clear\s+throat)\]",
    re.IGNORECASE,
)
STRETCHED_SIGH_PATTERN = re.compile(r"(?<!\w)ha+i+z+(?!\w)", re.IGNORECASE)
STRETCHED_HUM_PATTERN = re.compile(r"(?<!\w)(?:hừ+m+|h+m+)(?!\w)", re.IGNORECASE)
COMPACT_VOCALIZATION_PATTERN = re.compile(
    r"(?<!\w)(?P<syllable>ha|he|hi|hu)(?P=syllable){1,7}(?!\w)",
    re.IGNORECASE,
)
# The same laugh with a vowel in front of it: "Ahaha", "Ohoho", "Ehehe". Recognising these
# is only safe for the *predicate*, never for the rewriter above, which counts repetitions
# by dividing the match length by the syllable length - a leading vowel would make it count
# one repetition too many and stretch the laugh.
#
# Why it matters: `"...Ha! Ahaha! Á á! Haha!"` is laughter in every token but "Ahaha", and
# one unrecognised token is enough for is_vocalization_only to say no. ASR then judged
# laughter as if it were words, could not match it, exhausted five repair rounds and blocked
# chapter 013 of alpha.55 - a chapter that was otherwise finished.
LEADING_VOWEL_LAUGH_PATTERN = re.compile(
    r"^(?P<lead>[aeou])(?P<syllable>ha|he|hi|hu)(?P=syllable){0,7}$",
    re.IGNORECASE,
)
STANDALONE_GASP_PATTERN = re.compile(
    r"^(?P<prefix>\s*[“\"'‘—–-]?\s*)ha(?:…|\.{2,})(?P<suffix>\s*[”\"'’]?\s*)$",
    re.IGNORECASE,
)
# Một nguyên âm dẫn đầu CÓ DẤU THANH được phép: "ÁAAAAA" là một tiếng hét chứ không phải hai.
# Bản trước đòi token chỉ gồm một nguyên âm lặp, nên Á (một ký tự khác A) đứng trước làm
# `(?<!\w)` thất bại và cả chuỗi đi nguyên vào TTS - lô 9 chương 223: năm ứng viên 0,96 s rồi
# bản cuối chạm trần khung, cùng hình với "Argh" ở đầu file. Hàm thay kiểm chữ cái gốc của
# nguyên âm dẫn đầu (bỏ dấu thanh, giữ mũ/móc/trăng) có trùng nguyên âm kéo dài không.
STRETCHED_OPEN_VOWEL_PATTERN = re.compile(
    r"(?<!\w)(?P<lead>[À-ỹ])?(?P<vowel>[aeiouyưăâêôơ])(?P=vowel){2,}h*(?!\w)",
    re.IGNORECASE,
)
_TONE_MARKS = frozenset({"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"})


def _without_tone_marks(letter: str) -> str:
    """Chữ cái gốc: bỏ dấu thanh (huyền, sắc, ngã, hỏi, nặng), giữ mũ, móc và trăng."""
    import unicodedata

    decomposed = unicodedata.normalize("NFD", letter)
    kept = "".join(ch for ch in decomposed if ch not in _TONE_MARKS)
    return unicodedata.normalize("NFC", kept).casefold()
SPOKEN_WORD_PATTERN = re.compile(r"[A-Za-zÀ-ỹĐđ]+")
SPEAKABLE_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
# The r/g cries of pain and effort - argh, aargh, ugh - which the vowel-and-h forms above
# cannot reach. Left out, they were taken for English names and locked as transliterations:
# "Argh" was read "A-rag", Whisper naturally failed to hear that in a scream, and the
# resulting anchor mismatch blocked a chapter. Twenty-four segments across the corpus.
#
# No Vietnamese word ends in -gh, so this cannot swallow one: ghe and nghe carry a vowel
# after the digraph and the token must end at the h.
PAIN_CRY_PATTERN = r"a+r*g+h*|u+r*g+h*|g+r+h*"
# The same cries, to be replaced rather than recognised. "Argh" is English on the page
# and a Vietnamese voice has nothing to say for it: handed the letters, the model ran to
# its frame ceiling on a two-second scream, the only take in 948 segments to do so, and
# the ceiling then counted as evidence the take was cut off. Vietnamese writes a cry of
# pain "Á".
PAIN_CRY_SPOKEN_PATTERN = re.compile(
    r"(?<![\w])(?:" + PAIN_CRY_PATTERN + r")(?![\w])",
    re.IGNORECASE,
)
PAIN_CRY_SPOKEN_FORM = "\u00c1"
FOLDED_VOCALIZATION_PATTERN = re.compile(
    r"^(?:a+h*|u+h*|o+h*|you|ha+|he+|hi+|hu+|huc|hac|hay|hum|hm+|khu+|ho+|"
    + PAIN_CRY_PATTERN
    + r"|[a-z])$",
    re.IGNORECASE,
)
# A held sound written out: the same vowel three times or more, anywhere in the token.
# Neither language repeats a vowel that many times, and the book bears it out - of 11,524
# distinct tokens across both books, 87 match and every one is a cry, a shout or a word
# stretched out ("Khôôôông", "Saaaaaaam"). The only other things that match are Roman
# numerals, which have their own guard.
#
# Narrower versions kept missing: anchoring at the start missed "Tuuuuu", and allowing only
# consonants in front missed "THWAAAM", "Booyaaa" and "ARAAAAH".
STRETCHED_SOUND_TOKEN_PATTERN = re.compile(
    r"(?P<vowel>[aeiouyăâêôơư])(?P=vowel){2,}",
    re.IGNORECASE,
)
# A regnal number, not a held sound. "III" folds to a run of one vowel and would otherwise
# be read as a scream; the book says "Benedict III" 164 times. Uppercase only, so a
# stretched "Iiii" is still a sound.
ROMAN_NUMERAL_TOKEN_PATTERN = re.compile(r"^[IVXLCDM]+$")
ROMAN_NUMERAL_VALUES = {
    "I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000,
}
# Vietnamese for the numbers a regnal name reaches. Beyond twenty the pattern is regular and
# built from these; nothing in a book needs more than that.
VIETNAMESE_UNITS = (
    "không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín",
)
# Bậc của từng nhóm ba chữ số, từ phải sang: nhóm 0 không có tên.
VIETNAMESE_SCALES = ("", "nghìn", "triệu", "tỷ")


# Ký tự sách có mà giọng đọc không đọc được. Chúng đi thẳng tới TTS và không tạo ra khoảng
# nghỉ nào, nên một chú thích bị nuốt vào thành một thành phần của câu: chủ sách nghe
# "Thường (Common) (C) » Hiếm" ra thành "Thường Common C hiếm" - dính liền, không nhịp.
#
# Có hai loại, và loại thứ hai là chỗ dễ làm sai:
#   - Ký tự MANG NGHĨA phải thành CHỮ. "↓ 1.000 Đơn vị" nghĩa là *giảm* 1.000 đơn vị; bỏ nó
#     đi là bỏ mất nghĩa của câu.
#   - Ký tự NGĂN CÁCH phải thành DẤU PHẨY, không được bỏ trần. Bỏ trần thì chú thích lẫn vào
#     câu văn như một thành phần bình thường, đúng cái lỗi đang phải sửa.
SPOKEN_SYMBOL_WORDS = {
    "↓": "giảm",
    "↑": "tăng",
    # Ký hiệu toán trong một công thức: giọng đọc phát ra CHỮ và Whisper viết lại CHỮ ("cộng",
    # "bằng"), nên chuỗi đối chiếu cũng phải là chữ - cuốn 2 lô 1 chương 025, "Nấm xác chết + Mô
    # não thủy quỷ + … = Linh Hồn Than Khóc" đo 0,73 với bản thu hoàn toàn đúng, năm ứng viên
    # sửa đều trượt cùng một cách, và đoạn bị đánh hỏng vì thước đo chứ không vì giọng.
    # "%" cố ý KHÔNG có ở đây: Whisper viết lại "25%" đúng ký hiệu (6/6 đoạn cuốn 1 verified).
    "+": "cộng",
    "=": "bằng",
    "≥": "lớn hơn hoặc bằng",
    "≤": "nhỏ hơn hoặc bằng",
    "^": "mũ",
    "×": "nhân",
    "÷": "chia",
}
# Ngoặc và mũi tên ngăn cách: thành dấu phẩy để giọng nghỉ đúng một nhịp trước và sau phần
# được ngăn. `,` và `()` đều đã nằm trong PAUSE_GROUP_PATTERN của audio_io nên số nhóm nghỉ
# không đổi - thay đổi duy nhất là giọng NGHỈ THẬT ở chỗ thước đo vốn đã luôn tính là có
# nghỉ. Trên c00009_s0000018 thước đo trừ 6,90s khoảng lặng của 11,80s âm thanh mà giọng
# không hề nghỉ, thổi nhịp từ 10,76 lên 25,92 chars/s và vượt cận trên 24,5.
# `|` is here because the voice reads it as mathematics. alpha.55 chapter 011 lists skills as
# "Hỏa Cầu (Fireball) (Thường) || Sương Giáng (Mistfall) …" and Whisper transcribed the take
# as "Fireball thường giá trị tuyệt đối của xương dáng" - the voice said "absolute value of"
# between every entry. In this book `||` separates list items; a pause is what it means.
# 24 of them across 4 chapters, so rare, and wrong every single time.
SPOKEN_SEPARATORS = "»«›‹→⇒▸▶►([{)]}|"
# Đầu dòng đánh dấu mục, không ngăn cách gì với thứ đứng trước vì không có gì đứng trước.
SPOKEN_DROPPED = "•▪◦*"
_SPOKEN_COMMA_RUN = re.compile(r"(?:\s*,)+(?=\s*,)")
_SPOKEN_SPACE_RUN = re.compile(r"[ \t]{2,}")
# A comma this introduced has to attach to the word before it. "C , B" puts the silence in
# the wrong place, which is the defect being fixed rather than a cosmetic detail.
_SPOKEN_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:…])")
# A separator immediately before real punctuation is a pause with nothing after it -
# "(Spirit Essence Units)." would otherwise close on a hanging comma.
#
# Deliberately NOT anchored at the end of the string, and there is no matching rule for the
# start, because this function must leave a *fragment* of its own output alone - see
# spoken_symbols_to_words. A boundary is the one piece of context a fragment does not share
# with the text it came from.
_SPOKEN_TRAILING_COMMA = re.compile(r",(\s*[.!?…:;])")
# A slash between words is an alternative and wants the pause a comma gives. Between digits
# it is a fraction, and Vietnamese reads that slash aloud as "trên" - "8.5/10" is "tám phẩy
# năm trên mười", which is right. The voice applies the fraction reading to both, so
# "Mạnh hơn / khó tìm hơn" came out "mạnh hơn TRÊN khó tìm hơn": the symbol stopped being a
# separator and became a word inside the sentence, which is the exact thing the owner
# refused - "cái đó nó bị lẫn vào làm một thành phần trong câu văn là không được".
#
# Letters on both sides only, so the book's one real fraction keeps its reading. Checked
# across all 948 segments: 8 word/word, 1 digit/digit.
_SPOKEN_WORD_SLASH = re.compile(r"(?<=[^\W\d_])\s*/\s*(?=[^\W\d_])", re.UNICODE)
# Separators sitting at either end of the whole text are removed before conversion rather
# than trimmed away as commas afterwards. Same result, but stable: a fragment of converted
# text contains no separators at all, so this can never fire a second time. ↓ and ↑ are not
# in here - they mean "giảm" and "tăng", and a word does not stop meaning something because
# it happens to start the line.
_SPOKEN_BOUNDARY_TRIM = SPOKEN_SEPARATORS + SPOKEN_DROPPED + " \t\r\n"
# Chữ bị CHE bằng ký hiệu ("Cái #&!@!", "dưới *** à") là một khoảng ngừng, không phải tên ký hiệu.
# Lô 6 cuốn 2 chương 225: giọng đọc tự nở # & @ thành "thăng", "và", "a còng" ngay giữa câu chửi.
# Luật và các ca KHÔNG đụng tới: xem scripts/pending_patches/patch_a_censored_word_is_a_pause.py.
_CENSOR_RUN = re.compile(r"[#&@$%*!?]{3,}")
_CENSOR_MARKS = "#&@$"
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def _censored_words_as_pauses(text: str) -> str:
    if not _HAS_LETTER.search(text):
        return text

    def pause(match: re.Match[str]) -> str:
        run = match.group(0)
        if any(mark in run for mark in _CENSOR_MARKS) or run.count("*") >= 3:
            return "…"
        return run

    return _CENSOR_RUN.sub(pause, text)


def _spoken_symbols_in_span(text: str) -> str:
    result = []
    for character in text:
        if character in SPOKEN_SYMBOL_WORDS:
            result.append(f" {SPOKEN_SYMBOL_WORDS[character]} ")
        elif character in SPOKEN_SEPARATORS:
            result.append(", ")
        elif character in SPOKEN_DROPPED:
            result.append("")
        else:
            result.append(character)
    return "".join(result)


def spoken_symbols_to_words(text: str) -> str:
    """Turn characters the voice cannot say into words it can, or into a pause.

    The book's own text is never changed - this is only what gets handed to the voice, and
    to the transcript comparison that has to match it.

    Square brackets carry two different jobs in this book and only one of them is a
    separator. "[A-rank]" is an annotation the voice should pause around; "[thở dài]" is a
    stage direction normalize_vocalizations_for_tts turns into an actual breath, "Hầy...".
    Converting the second kind to commas destroys the cue before that function ever sees it,
    which is what the anchor tests caught. Vocal cues are therefore passed through untouched
    and normalized later, as they always were.

    **Stable on its own output, including fragments of it.** The repair path splits a long
    segment into pieces of the already-converted text and then re-derives each piece to check
    the boundary text did not move; a rule that reads the start or end of the string sees a
    different context in a piece than in the text it came from, and the check fails. alpha.45
    died that way at chapter 2: "(Legendary)" became ", Legendary," which pushed the segment
    to 174 characters over a 170 cap, so the splitter cut at a comma this function had just
    created, and the second pass trimmed that now-trailing comma back off.

    So nothing here is anchored to a boundary. Separators at either end are removed *before*
    conversion instead, which reaches the same tidy result - a fragment of converted text has
    no separators left in it, so that rule cannot fire twice.
    """
    # "=>" là một mũi tên, không phải "bằng" rồi "lớn hơn": đổi thành → trước mọi bước khác, để
    # luật sẵn có của SPOKEN_SEPARATORS lo phần còn lại (đầu dòng thì cắt, giữa câu thì phẩy).
    source = _censored_words_as_pauses(str(text).replace("=>", "→"))
    spans: list[tuple[str, bool]] = []
    position = 0
    for match in VOCAL_CUE_PATTERN.finditer(source):
        spans.append((source[position:match.start()], False))
        spans.append((match.group(0), True))
        position = match.end()
    spans.append((source[position:], False))
    # Trim the two ends of the whole text, never a vocal cue: the brackets delimiting
    # "[thở dài]" are separators too, and eating the opening one leaves a cue the later
    # vocalization pass no longer recognises - it read out "thở dài," as words.
    if not spans[0][1]:
        spans[0] = (spans[0][0].lstrip(_SPOKEN_BOUNDARY_TRIM), False)
    if not spans[-1][1]:
        spans[-1] = (spans[-1][0].rstrip(_SPOKEN_BOUNDARY_TRIM), False)
    out = "".join(
        span if is_cue else _spoken_symbols_in_span(span) for span, is_cue in spans
    )
    out = _SPOKEN_WORD_SLASH.sub(", ", out)
    out = _SPOKEN_SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = _SPOKEN_COMMA_RUN.sub("", out)
    out = _SPOKEN_TRAILING_COMMA.sub(r"\1", out)
    out = _SPOKEN_SPACE_RUN.sub(" ", out)
    return out.strip()


def roman_numeral_value(token: str) -> int | None:
    """The number a Roman numeral spells, or None when the token is not one.

    A single letter is only ever read as one when it is "I". This book ranks things
    "C » B » A » S", so a lone C or D or M is a grade rather than a hundred, and no
    monarch is numbered V without the letters around it to say so.
    """
    if ROMAN_NUMERAL_TOKEN_PATTERN.fullmatch(token) is None:
        return None
    if len(token) == 1 and token != "I":
        return None
    total = 0
    previous = 0
    for character in reversed(token):
        value = ROMAN_NUMERAL_VALUES[character]
        total += -value if value < previous else value
        previous = max(previous, value)
    return total or None


def vietnamese_number_words(value: int) -> str:
    """A number written the way it is said, for the numerals a book carries.

    Vietnamese changes the unit inside a compound: 15 is "mười lăm", not "mười năm", and
    from twenty up 1 becomes "mốt" and 4 "tư".
    """
    if value < 0:
        raise ValueError(value)
    if value < 10:
        return VIETNAMESE_UNITS[value]
    if value < 20:
        unit = value - 10
        if unit == 0:
            return "mười"
        return "mười " + ("lăm" if unit == 5 else VIETNAMESE_UNITS[unit])
    if value < 100:
        tens, unit = divmod(value, 10)
        head = f"{VIETNAMESE_UNITS[tens]} mươi"
        if unit == 0:
            return head
        if unit == 1:
            return head + " mốt"
        if unit == 4:
            return head + " tư"
        if unit == 5:
            return head + " lăm"
        return f"{head} {VIETNAMESE_UNITS[unit]}"
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        head = f"{VIETNAMESE_UNITS[hundreds]} trăm"
        if rest == 0:
            return head
        # Vietnamese says "lẻ" for the empty tens: 105 is "một trăm lẻ năm".
        if rest < 10:
            return f"{head} lẻ {VIETNAMESE_UNITS[rest]}"
        return f"{head} {vietnamese_number_words(rest)}"
    if value < 1_000_000_000_000:
        # Nhóm ba chữ số từ phải sang: nghìn, triệu, tỷ. Nhóm giữa mà dưới 100 đọc "không
        # trăm" (và "lẻ" nếu dưới 10): 1.005 là "một nghìn không trăm lẻ năm", 2.024 là "hai
        # nghìn không trăm hai mươi tư"; nhóm bằng 0 bỏ hẳn. Đây là ngữ pháp số đếm, không phải
        # ước lượng - và `asr.py` vẫn dừng ở `NUMBER_FOLD_CEILING`, vì năm tháng trong bản ghi
        # không có một dạng nói duy nhất để gộp.
        groups: list[int] = []
        remaining = value
        while remaining:
            remaining, group = divmod(remaining, 1000)
            groups.append(group)
        words: list[str] = []
        for index in range(len(groups) - 1, -1, -1):
            group = groups[index]
            if group == 0:
                continue
            if index == len(groups) - 1:
                spoken = vietnamese_number_words(group)
            elif group < 10:
                spoken = f"không trăm lẻ {VIETNAMESE_UNITS[group]}"
            elif group < 100:
                spoken = f"không trăm {vietnamese_number_words(group)}"
            else:
                spoken = vietnamese_number_words(group)
            words.append(spoken if index == 0 else f"{spoken} {VIETNAMESE_SCALES[index]}")
        return " ".join(words)
    raise ValueError(f"number beyond what a book numbers things with: {value}")
MAX_VOCALIZATION_REPETITIONS = 4


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    # Cả họ zero-width, không chỉ U+200B. Dòng cũ đã có đúng ý định này và chỉ bắt một trong
    # bốn ký tự - đủ để đọc như đã xong.
    #
    # Nguồn có **thuỷ ấn ẩn**: 53 ký tự U+200C/U+200D xen kẽ nhau thành một dãy nhị phân,
    # chèn vào một chỗ trong 15 file (015, 026, 038, 086, 092, 097, 114, 127, 140, 164, 176,
    # 188, 229, 256, 278). Mắt không thấy, và không phép kiểm nào của dự án nhìn chúng.
    #
    # Chúng KHÔNG hại chất lượng - đo ở alpha.56: đoạn mang thuỷ ấn ra `verified`, sim 0,966,
    # vì VieNeu đọc lướt qua và `speakable_chars` đếm `isalnum()`. Cái chúng hại là **tính
    # tái lập**: `stable_id` là hash của văn bản, hạt giống sinh audio lấy từ `stable_id`, nên
    # trang nguồn cấp lại một dãy nhị phân khác - đúng việc mà thuỷ ấn sinh ra để làm - sẽ đổi
    # audio của một câu chữ y hệt, và mọi phán quyết của người nghe cho đoạn ấy lặng lẽ hết
    # hiệu lực.
    #
    # ZWJ có nghĩa thật trong chuỗi emoji và trong Devanagari/Ả Rập. Trong văn xuôi tiếng Việt
    # thì không, và nguồn này không có chữ nào ngoài Latin - đã quét cả 478 file.
    for zero_width in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"):
        text = text.replace(zero_width, "")
    # Ngoặc góc của bản dịch light novel Nhật (「Ừ. Hiểu rồi.」) là ngoặc thoại: đổi thành “…” ở đây, một chỗ, để mọi luật
    # phía sau - tách thoại, ngoặc nhiều dòng, khoá thoại nối tiếp, luật host, ngắt nghỉ TTS - thấy đúng dấu chúng biết.
    # Yamiyo no Hotaru có 30.941 dòng thoại như thế từng bị khoá là lời kể. 『…』 thì để yên: truyện dùng nó cho thuật
    # ngữ, bảng hệ thống và ngoặc lồng trong 「…」. Truyện không có 「 thì chuỗi không đổi - stable_id không đổi.
    text = text.replace("\u300c", "\u201c").replace("\u300d", "\u201d")
    text = INLINE_REFERENCE_MARKER_PATTERN.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    result: list[str] = []
    current = ""
    for sentence in SENTENCE_BOUNDARY.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            result.append(current)
            current = ""
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            result.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        current = sentence
    if current:
        result.append(current)
    return result


def _split_unit_at_word_boundaries(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            raise ValueError(
                "clause split cannot preserve an unbroken token within max_chars"
            )
        candidate = f"{current} {word}".strip()
        if not current or len(candidate) <= max_chars:
            current = candidate
            continue
        chunks.append(current)
        current = word
    if current:
        chunks.append(current)
    return chunks


def _rebalance_short_clause_tail(
    part_units: list[list[str]],
    max_chars: int,
) -> list[list[str]]:
    if len(part_units) < 2:
        return part_units
    minimum_tail = min(CLAUSE_SPLIT_MIN_TAIL_CHARS, max_chars // 3)
    while len(" ".join(part_units[-1])) < minimum_tail:
        if len(part_units[-2]) < 2:
            break
        moved_unit = part_units[-2][-1]
        next_tail = " ".join([moved_unit, *part_units[-1]])
        next_previous = " ".join(part_units[-2][:-1])
        if len(next_tail) > max_chars or len(next_previous) < minimum_tail:
            break
        part_units[-2].pop()
        part_units[-1].insert(0, moved_unit)
    return part_units


def split_text_by_clauses(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if max_chars <= 0:
        raise ValueError("clause split max_chars must be positive")
    if len(text) <= max_chars:
        return [text]

    clauses = [clause.strip() for clause in CLAUSE_BOUNDARY.split(text) if clause.strip()]
    units: list[str] = []
    for clause in clauses:
        if len(clause) <= max_chars:
            units.append(clause)
        else:
            units.extend(_split_unit_at_word_boundaries(clause, max_chars))

    part_units: list[list[str]] = []
    current_units: list[str] = []
    for unit in units:
        candidate = " ".join([*current_units, unit])
        if not current_units or len(candidate) <= max_chars:
            current_units.append(unit)
            continue
        part_units.append(current_units)
        current_units = [unit]
    if current_units:
        part_units.append(current_units)
    part_units = _rebalance_short_clause_tail(part_units, max_chars)
    parts = [" ".join(part) for part in part_units]
    if " ".join(parts) != text:
        raise RuntimeError("clause-aware split changed the source text")
    return parts


def split_text_for_strategy(text: str, strategy: str) -> tuple[list[str], int]:
    try:
        max_chars = SPLIT_MAX_CHARS_BY_STRATEGY[strategy]
    except KeyError as exc:
        raise ValueError(f"Unsupported split strategy: {strategy}") from exc
    parts = (
        split_text_by_clauses(text, max_chars)
        if strategy == CLAUSE_SPLIT_STRATEGY
        else split_long_text(text, max_chars)
    )
    return parts, max_chars


def _split_long(text: str, max_chars: int) -> list[str]:
    return split_long_text(text, max_chars)


def has_spoken_content(text: str) -> bool:
    return any(char.isalnum() for char in text)


FRAMED_NAME_MAX_WORDS = 4
FRAMED_NAME_PUNCTUATION = ".!?…~,;"
# Một chữ duy nhất trong khung là TIẾNG KÊU / THÁN TỪ thì vẫn là giọng, không phải tên: một chữ cái lặp từ 3 lần liền ("Kkkkk",
# "Hmmm", "Aaaa") hoặc nằm trong danh sách này. Có dấu hay không đều tính. "ban" cố ý KHÔNG có: "[Ban]" là tiêu đề.
FRAMED_INTERJECTIONS = frozenset(
    "hmm hm hừm khụ ừ ừm ờ à á ồ ơ ê hả hử hừ hứ hì hehe haha hihi ối ui úi ây chậc chẹp xì phù hự oa wow "
    "vâng dạ hế haiz haizz hây nhưng phải không được thôi".split()
)
_REPEATED_LETTER_PATTERN = re.compile(r"([^\W\d_])\1{2,}", re.IGNORECASE)


def _is_framed_name_or_title(inner: str) -> bool:
    """Tên / tiêu đề trong khung ("[Lớp A]", "[Mateo Jordana]", "[Sổ Hướng Dẫn]"): tối đa 4 chữ, không dấu kết / cảm / phẩy, mọi chữ
    mở đầu bằng chữ HOA hoặc số. Một tên không phải ai đang nói. Tiếng hét toàn hoa có "!!" ("[GDESAAAAA!!]") vẫn là giọng."""
    if any(mark in inner for mark in FRAMED_NAME_PUNCTUATION):
        return False
    words = [word for word in inner.split() if any(char.isalnum() for char in word)]
    if not words or len(words) > FRAMED_NAME_MAX_WORDS:
        return False
    if len(words) == 1:
        sound = "".join(char for char in words[0] if char.isalnum()).casefold()
        if sound in FRAMED_INTERJECTIONS or _REPEATED_LETTER_PATTERN.search(sound):
            return False
    for word in words:
        first = next(char for char in word if char.isalnum())
        if not (first.isdigit() or first.isupper()):
            return False
    return True


def is_whole_line_voice(line: str) -> bool:
    """Dòng nguyên vẹn trong 『…』, [ … ] hay 【…】 là MỘT GIỌNG (lời thoại), không phải lời kể. 『』 cần có chữ hoặc số (như
    trước); [ ] và 【】 cần ít nhất một chữ cái - "[12]" và "[...]" không phải giọng nào - và không phải ghi chú của người dịch."""
    stripped = line.strip()
    if WHITE_CORNER_QUOTE_LINE_PATTERN.fullmatch(stripped):
        return has_spoken_content(stripped)
    if not any(pattern.fullmatch(stripped) for pattern in LETTERED_VOICE_LINE_PATTERNS) or _HAS_LETTER.search(stripped) is None:
        return False
    inner = stripped[1:-1]
    return not (
        TRANSLATOR_NOTE_LABEL_PATTERN.match(inner)
        or TRANSLATOR_SELF_REFERENCE_PATTERN.search(inner)
        or _is_framed_name_or_title(inner)
    )


def _speakable_tokens(text: str) -> list[str]:
    return SPEAKABLE_TOKEN_PATTERN.findall(text)


def _fold_vocalization_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFD", token.casefold().replace("đ", "d"))
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _is_vocalization_token(token: str) -> bool:
    if ROMAN_NUMERAL_TOKEN_PATTERN.fullmatch(token) is not None:
        return False
    folded = _fold_vocalization_token(token)
    return (
        FOLDED_VOCALIZATION_PATTERN.fullmatch(folded) is not None
        or COMPACT_VOCALIZATION_PATTERN.fullmatch(folded) is not None
        or LEADING_VOWEL_LAUGH_PATTERN.fullmatch(folded) is not None
        or STRETCHED_SOUND_TOKEN_PATTERN.search(token) is not None
    )


def is_vocalization_only(text: str) -> bool:
    tokens = SPOKEN_WORD_PATTERN.findall(text)
    return bool(tokens) and all(_is_vocalization_token(token) for token in tokens)


def is_standalone_ha_gasp(text: str) -> bool:
    return STANDALONE_GASP_PATTERN.fullmatch(text) is not None


def normalize_vocalizations_for_tts(text: str) -> str:
    """Turn stylized vocal spellings into ordinary pronounceable Vietnamese text.

    The source text remains untouched in SQLite. This function only prepares the
    copy sent to VieNeu and deliberately avoids the model's experimental
    non-verbal cue tokens.
    """

    def replace_cue(match: re.Match[str]) -> str:
        key = " ".join(match.group(1).casefold().split())
        return VOCAL_CUE_SPOKEN_FORMS[key]

    def separate_compact_vocalization(match: re.Match[str]) -> str:
        syllable = match.group("syllable").casefold()
        count = min(
            MAX_VOCALIZATION_REPETITIONS,
            len(match.group(0)) // len(match.group("syllable")),
        )
        return " ".join([syllable] * count).capitalize()

    def separate_stretched_vowel(match: re.Match[str]) -> str:
        vowel = match.group("vowel").casefold()
        lead = match.group("lead") or ""
        if lead:
            # "ÁAAAAA" là một tiếng hét: giữ nguyên âm có dấu làm đầu tiếng. "Ôaaa" thì không
            # phải một âm kéo dài - để yên, đừng đoán.
            if _without_tone_marks(lead) != vowel:
                return match.group(0)
            return f"{lead}... {vowel}"
        return f"{vowel.upper()}... {vowel}"

    gasp = STANDALONE_GASP_PATTERN.fullmatch(text)
    if gasp is not None:
        return f"{gasp.group('prefix')}Ha ha.{gasp.group('suffix')}"

    result = VOCAL_CUE_PATTERN.sub(replace_cue, text)
    result = PAIN_CRY_SPOKEN_PATTERN.sub(PAIN_CRY_SPOKEN_FORM, result)
    result = STRETCHED_SIGH_PATTERN.sub("Hầy", result)
    result = STRETCHED_HUM_PATTERN.sub("Hừm", result)
    result = COMPACT_VOCALIZATION_PATTERN.sub(separate_compact_vocalization, result)
    result = STRETCHED_OPEN_VOWEL_PATTERN.sub(separate_stretched_vowel, result)
    return re.sub(r"\.{4,}", "...", result)


def _quoted_span_is_dialogue(line: str, match: re.Match[str]) -> bool:
    quoted = match.group(1).strip()
    inner = quoted[1:-1].strip()
    if not has_spoken_content(inner):
        return False
    if line.strip() == quoted:
        return True
    if any(mark in inner for mark in ("?", "!", "…")) or inner.endswith("."):
        return True
    before = line[: match.start()].rstrip()
    after = line[match.end() :].lstrip()
    if before.endswith(":"):
        return True
    # “Được,” Liz gật đầu. - câu trong ngoặc kết thúc bằng dấu phẩy là lời nói nối vào lời dẫn, dù động từ dẫn là gì
    # (gật đầu, lầm bầm, lên tiếng, thở dài...: danh sách động từ không bao giờ đủ). Quét Corpus 28-09: 1.826 câu như thế
    # bị khoá lời kể - đọc bằng giọng người kể - ở YMP (Hàn) và Nageki; trừ 5 câu thuật ngữ đặt dấu phẩy kiểu Anh ngay
    # sau "là", "gọi", "danh", "thành" ("họ gọi tôi là “đội trưởng,” đơn giản vì...") thì đều là thoại.
    if inner.endswith(",") and not TERM_INTRODUCER_PATTERN.search(before.casefold()):
        return True
    context = f"{before[-100:]} {after[:100]}"
    return SPEECH_VERB_PATTERN.search(context) is not None


def _join_fragments(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    if right[0] in ",.;:!?…)]}”":
        return left + right
    return f"{left} {right}"


_WHOLE_SPAN_PATTERN = re.compile(r"(.+)", re.DOTALL)


def _nested_dialogue_quote_spans(line: str) -> list[tuple[int, int]]:
    """Cặp “…” có “…” lồng bên trong, khi cả dòng cân dấu: “Haha! “Cậu sẽ bị phạt” chứ gì? Cứ làm đi!”.

    QUOTE_PATTERN dừng ở dấu ” đầu tiên, nên nửa sau câu nói của người ấy thành lời kể. Chỉ khi mọi “ ” trên dòng
    khớp thành cặp lồng nhau - dòng gõ nhầm dấu thì để luật cũ lo.
    """
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    nested = False
    for index, char in enumerate(line):
        if char == "“":
            if depth == 0:
                start, nested = index, False
            else:
                nested = True
            depth += 1
        elif char == "”":
            depth -= 1
            if depth < 0:
                return []
            if depth == 0 and nested:
                spans.append((start, index + 1))
    return spans if depth == 0 else []


def _dialogue_quote_matches(line: str) -> list[re.Match[str]]:
    matches = list(QUOTE_PATTERN.finditer(line))
    nested = _nested_dialogue_quote_spans(line)
    if not nested:
        return matches
    matches = [
        match
        for match in matches
        if not any(start <= match.start() < end for start, end in nested)
    ]
    for start, end in nested:
        span = _WHOLE_SPAN_PATTERN.match(line, start, end)
        if span is not None:
            matches.append(span)
    return sorted(matches, key=lambda match: match.start())


def _line_pieces(line: str) -> list[tuple[str, str]]:
    if re.match(r"^[—–-]\s*\S", line):
        return [(line, "dialogue")]
    if is_whole_line_voice(line):
        return [(line, "dialogue")]
    matches = [
        (match, "dialogue" if _quoted_span_is_dialogue(line, match) else "narration")
        for match in _dialogue_quote_matches(line)
    ]
    matches.extend((match, "thought") for match in THOUGHT_QUOTE_PATTERN.finditer(line))
    matches.sort(key=lambda item: (item[0].start(), -item[0].end()))
    non_overlapping: list[tuple[re.Match[str], str]] = []
    occupied_until = -1
    for match, hint in matches:
        if match.start() < occupied_until:
            continue
        non_overlapping.append((match, hint))
        occupied_until = match.end()
    matches = non_overlapping
    if not matches:
        hint = "thought" if line.startswith("(") and line.endswith(")") else "narration"
        return [(line, hint)]

    raw: list[tuple[str, str]] = []
    cursor = 0
    for match, hint in matches:
        if match.start() > cursor:
            raw.append((line[cursor : match.start()], "narration"))
        raw.append((match.group(1), hint))
        cursor = match.end()
    if cursor < len(line):
        raw.append((line[cursor:], "narration"))

    merged: list[tuple[str, str]] = []
    pending_prefix = ""
    for text, hint in raw:
        text = text.strip()
        if not text:
            continue
        if not has_spoken_content(text):
            if merged:
                previous_text, previous_hint = merged[-1]
                merged[-1] = (_join_fragments(previous_text, text), previous_hint)
            else:
                pending_prefix = _join_fragments(pending_prefix, text)
            continue
        if pending_prefix:
            text = _join_fragments(pending_prefix, text)
            pending_prefix = ""
        if merged and merged[-1][1] == hint:
            previous_text, _ = merged[-1]
            merged[-1] = (_join_fragments(previous_text, text), hint)
        else:
            merged.append((text, hint))
    return merged


def _find_quote_closing(line: str, closing_mark: str, start: int = 0) -> int:
    """Where `closing_mark` closes in `line` from `start`, counting the closers it accepts in its place (‘…')."""
    pattern = QUOTE_CLOSING_PATTERNS.get(closing_mark)
    if pattern is None:
        return line.find(closing_mark, start)
    match = pattern.search(line, start)
    return match.start() if match is not None else -1


def _balanced_quote_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for opening_mark, closing_mark, _ in CURLY_QUOTE_SPECS:
        cursor = 0
        while cursor < len(line):
            opening_index = line.find(opening_mark, cursor)
            if opening_index < 0:
                break
            closing_index = _find_quote_closing(line, closing_mark, opening_index + 1)
            if closing_index < 0:
                cursor = opening_index + 1
                continue
            spans.append((opening_index, closing_index + 1))
            cursor = closing_index + 1
    ascii_quote_positions = [index for index, char in enumerate(line) if char == '"']
    spans.extend(
        (opening_index, closing_index + 1)
        for opening_index, closing_index in zip(
            ascii_quote_positions[0::2],
            ascii_quote_positions[1::2],
        )
    )
    return spans


def _unmatched_curly_quote_openings(line: str) -> list[tuple[int, str, str]]:
    balanced_spans = _balanced_quote_spans(line)
    unmatched: list[tuple[int, str, str]] = []
    for opening_mark, closing_mark, hint in CURLY_QUOTE_SPECS:
        cursor = 0
        while cursor < len(line):
            opening_index = line.find(opening_mark, cursor)
            if opening_index < 0:
                break
            closing_index = _find_quote_closing(line, closing_mark, opening_index + 1)
            if closing_index >= 0:
                cursor = closing_index + 1
                continue
            nested_in_balanced_quote = any(
                start < opening_index < end
                for start, end in balanced_spans
            )
            if not nested_in_balanced_quote:
                unmatched.append((opening_index, closing_mark, hint))
            cursor = opening_index + 1
    return unmatched


def _terminal_alternative_quote_closing(line: str, expected_closing_mark: str) -> int:
    stripped = line.rstrip()
    if not stripped:
        return -1
    terminal_mark = stripped[-1]
    if terminal_mark == expected_closing_mark or terminal_mark not in QUOTE_CLOSING_MARKS:
        return -1
    if any(
        end == len(stripped) and stripped[start] in "“‘"
        for start, end in _balanced_quote_spans(stripped)
    ):
        # Dấu cuối dòng đóng cặp của chính nó ("...cô gái vẫn thì thầm, ‘ba’"): không phải dấu đóng nhầm của ngoặc đang mở.
        return -1
    return len(stripped) - 1


def _line_pieces_with_quote_state(
    line: str,
    quote_state: tuple[str, str] | None,
) -> tuple[list[tuple[str, str]], tuple[str, str] | None]:
    if quote_state is not None:
        hint, closing_mark = quote_state
        closing_index = _find_quote_closing(line, closing_mark)
        if closing_index < 0:
            alternative_closing_index = _terminal_alternative_quote_closing(
                line,
                closing_mark,
            )
            if alternative_closing_index >= 0:
                return [(line[: alternative_closing_index + 1], hint)], None
            return [(line, hint)], quote_state
        pieces = [(line[: closing_index + 1], hint)]
        remainder = line[closing_index + 1 :].strip()
        if not remainder:
            return pieces, None
        tail, next_state = _line_pieces_with_quote_state(remainder, None)
        return pieces + tail, next_state

    # Một giọng nguyên dòng tự đóng: dấu “ lẻ bên trong ("[Hắn gầm: “Chết đi!]") không được mở một lời thoại treo qua đoạn sau.
    if is_whole_line_voice(line):
        return [(line, "dialogue")], None
    unmatched_openings = _unmatched_curly_quote_openings(line)
    ascii_quote_positions = [index for index, char in enumerate(line) if char == '"']
    if len(ascii_quote_positions) % 2:
        opening_index = ascii_quote_positions[-1]
        nested_in_balanced_quote = any(
            start < opening_index < end
            for start, end in _balanced_quote_spans(line)
        )
        if not nested_in_balanced_quote:
            unmatched_openings.append((opening_index, '"', "dialogue"))
    if not unmatched_openings:
        return _line_pieces(line), None

    opening_index, closing_mark, hint = min(unmatched_openings, key=lambda item: item[0])
    pieces = _line_pieces(line[:opening_index].strip()) if opening_index > 0 else []
    alternative_closing_index = _terminal_alternative_quote_closing(line, closing_mark)
    if alternative_closing_index > opening_index:
        quoted = line[opening_index : alternative_closing_index + 1].strip()
        if quoted:
            pieces.append((quoted, hint))
        remainder = line[alternative_closing_index + 1 :].strip()
        if remainder:
            tail, next_state = _line_pieces_with_quote_state(remainder, None)
            return pieces + tail, next_state
        return pieces, None
    quoted = line[opening_index:].strip()
    if quoted:
        pieces.append((quoted, hint))
    return pieces, (hint, closing_mark)


def _fresh_quote_opening(line: str, quote_state: tuple[str, str]) -> int:
    """Where a later paragraph opens a NEW quote although `quote_state` is still open, or -1.

    A quote that really runs on either carries on without a mark until its closer, or (the
    English convention) starts each further paragraph with the opener again. A paragraph that
    opens a fresh “ in the middle of its text before closing anything, or starts with an opener
    after a paragraph that did not, shows the earlier quote never ran on: its closer is missing.
    """
    _hint, closing_mark = quote_state
    if line.startswith("“") or (closing_mark == "’" and line.startswith("‘")):
        return 0
    if line.startswith('"') and len(line) > 1 and not line[1].isspace():
        return 0
    if closing_mark == '"':
        return -1
    openers = "“‘" if closing_mark == "’" else "“"
    closing_index = _find_quote_closing(line, closing_mark)
    before_closing = line if closing_index < 0 else line[:closing_index]
    return next((index for index, char in enumerate(before_closing) if char in openers), -1)


def _chapter_writes_dialogue_in_quotes(paragraphs: list[str]) -> bool:
    """Thoại của chương nằm trong ngoặc kép và dòng mở bằng gạch chỉ lác đác vài dòng."""
    lines = [line.strip() for paragraph in paragraphs for line in paragraph.splitlines() if line.strip()]
    quote_led = sum(1 for line in lines if QUOTE_LED_LINE_PATTERN.match(line))
    dash_led = sum(1 for line in lines if DASH_LINE_PATTERN.match(line))
    return quote_led >= QUOTED_CHAPTER_MIN_QUOTE_LINES and dash_led <= QUOTED_CHAPTER_MAX_DASH_LINES


def _dash_line_is_narration(line: str) -> bool:
    """Dòng gạch đọc như lời kể: viết thường nối câu trước ("-bởi vì..."), hay chủ ngữ ngôi ba kể việc đã xảy ra,
    và không có dấu hiệu lời nói nào. Chỉ dùng ở chương viết thoại trong ngoặc kép."""
    dash = DASH_LINE_PATTERN.match(line)
    if dash is None:
        return False
    body = line[dash.end() :]
    if not has_spoken_content(body) or SPEECH_MARK_PATTERN.search(body) or SPEECH_FINAL_PARTICLE_PATTERN.search(body):
        return False
    without_third_person = THIRD_PERSON_PATTERN.sub(" ", body)
    if SPEECH_ONLY_PRONOUN_PATTERN.search(without_third_person):
        return False
    if body[:1].islower():
        return True
    if SPEECH_PRONOUN_PATTERN.search(without_third_person):
        return False
    return NARRATIVE_SUBJECT_PATTERN.search(body) is not None


def _punctuation_break_ms(text: str) -> int:
    return max(
        (duration for mark, duration in PUNCTUATION_BREAK_MS.items() if mark in text),
        default=230,
    )


def _walk_paragraphs(
    chapter_index: int,
    paragraphs: list[str],
    max_chars: int,
    close_at_end_of: frozenset[int],
    dialogue_in_quotes: bool = False,
) -> tuple[list[dict[str, Any]], tuple[str, str] | None, int | None]:
    """One pass over the chapter, returning its rows and how the quote state ended.

    ``close_at_end_of`` names the paragraphs whose quote is forced shut when the paragraph
    ends - the recovery lever. The third return value is the paragraph that opened whatever
    quote is still hanging at the end, which is the paragraph that needs the lever next.
    ``dialogue_in_quotes`` (`_chapter_writes_dialogue_in_quotes`) lets a dash-led line that
    reads as narration stay narration instead of opening a dash turn.
    """
    rows: list[dict[str, Any]] = []

    def append_piece(piece: str, hint: str, paragraph_index: int) -> None:
        if not has_spoken_content(piece):
            if rows:
                rows[-1]["break_ms"] = max(int(rows[-1]["break_ms"]), _punctuation_break_ms(piece))
            return
        for chunk in _split_long(piece.strip(), max_chars):
            seq = len(rows)
            stable_id = f"c{chapter_index:05d}_s{seq:07d}_{sha256_text(chunk)[:12]}"
            rows.append(
                {
                    "stable_id": stable_id,
                    "seq": seq,
                    "paragraph_index": paragraph_index,
                    "break_ms": 170 if hint == "dialogue" else (210 if hint == "thought" else 230),
                    "text": chunk,
                    "text_sha256": sha256_text(chunk),
                    "kind_hint": hint,
                    "kind": hint,
                    "speaker": "NARRATOR" if hint == "narration" else "UNKNOWN",
                    "status": "pending",
                }
            )

    quote_state: tuple[str, str] | None = None
    opened_at: int | None = None
    # Có đoạn nào từ chỗ mở tới đây KHÔNG mở lại bằng dấu ngoặc (lối viết một ngoặc cho cả lời nói dài).
    ran_on_unmarked = False
    for paragraph_index, paragraph in enumerate(paragraphs):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        for line in lines:
            was_open = quote_state is not None
            if quote_state is not None and paragraph_index != opened_at:
                fresh_opening = _fresh_quote_opening(line, quote_state)
                if fresh_opening > 0 or (fresh_opening == 0 and ran_on_unmarked):
                    # Ngoặc mở ở `opened_at` thiếu dấu đóng; để nó trôi tới đây thì lời kể ở giữa thành lời
                    # thoại/nội tâm. Trả về khi vẫn mở: vòng hồi phục đóng nó ở cuối đoạn đã mở rồi chia lại.
                    return rows, quote_state, opened_at
                if fresh_opening < 0:
                    ran_on_unmarked = True
            if quote_state is None and dialogue_in_quotes and _dash_line_is_narration(line):
                pieces = [(line, "narration")]
            else:
                pieces, quote_state = _line_pieces_with_quote_state(line, quote_state)
            if quote_state is None:
                opened_at = None
            elif not was_open:
                opened_at = paragraph_index
                ran_on_unmarked = False
            if not pieces and rows:
                rows[-1]["break_ms"] = max(int(rows[-1]["break_ms"]), _punctuation_break_ms(line))
            for piece, hint in pieces:
                append_piece(piece, hint, paragraph_index)
        if quote_state is not None and paragraph_index in close_at_end_of:
            quote_state = None
            opened_at = None
    return rows, quote_state, opened_at


def _credit_line_indexes(lines: list[str]) -> set[int]:
    """Chỉ số các dòng ghi công trong CREDIT_WINDOW_LINES dòng có chữ đầu tiên của chương (dòng tiêu đề tính là một)."""
    found: set[int] = set()
    seen = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if seen >= CREDIT_WINDOW_LINES:
            break
        seen += 1
        if CREDIT_LINE_PATTERN.match(stripped):
            found.add(index)
    return found


def credit_lines(text: str) -> list[str]:
    """Đúng những dòng `drop_credit_lines` sẽ bỏ - trình tạo sách đếm và cho xem trước khi hỏi người dùng bỏ hay giữ."""
    lines = normalize_text(text).split("\n")
    return [lines[index].strip() for index in sorted(_credit_line_indexes(lines))]


def drop_credit_lines(text: str) -> str:
    """Bỏ dòng ghi công ở đầu chương (`credit_lines`)."""
    lines = text.split("\n")
    drop = _credit_line_indexes(lines)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for index, line in enumerate(lines) if index not in drop)).strip()


def segment_chapter_text(
    chapter_index: int,
    text: str,
    max_chars: int = 340,
    *,
    warnings: list[str] | None = None,
    drop_credits: bool = False,
) -> list[dict[str, Any]]:
    """Split a chapter into segments, recovering from a source that never closes a quote.

    A quotation may legitimately run across blank-line-separated paragraphs, so the quote
    state is threaded through the whole chapter rather than reset at each paragraph. The
    price of that reach is that ONE missing quote mark leaves the state open all the way to
    the end, and this function used to raise and refuse the chapter - which stops a whole
    book on a single typo, in a source nobody here wrote. Eight of this book's 478 chapters
    trip it.

    So it recovers. The paragraph that opened the hanging quote has its quote forced shut
    where that paragraph ends, and the chapter is parsed again; if that is not enough the
    next culprit is added, and the last resort closes every paragraph at its own end, which
    cannot leave anything open. The same lever pulls earlier when a later paragraph shows the
    quote never ran on (`_fresh_quote_opening`): left alone, the missing closer would be
    found at the NEXT quote's closer and every narration line in between would be locked as
    dialogue or thought. Recovery may read a stretch as dialogue that was narration
    or the reverse, which costs a voice. It cannot lose or reorder a word - the token check
    at the bottom of this function still proves that on every chapter, recovered or not.

    Pass ``warnings`` to hear about it; the list is appended to, never read.

    ``drop_credits=True`` leaves out translator/editor credit lines at the top of the chapter.
    Only a book whose owner ACCEPTED that suggestion in the creation wizard asks for it
    (settings ``text.drop_credit_lines``); the text is never edited on the app's own initiative,
    and every other book - including all made before 29-09 - splits exactly as it always has.
    """
    text = normalize_text(text)
    if drop_credits:
        text = drop_credit_lines(text)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]

    close_at_end_of: frozenset[int] = frozenset()
    dialogue_in_quotes = _chapter_writes_dialogue_in_quotes(paragraphs)
    rows, quote_state, opened_at = _walk_paragraphs(
        chapter_index, paragraphs, max_chars, close_at_end_of, dialogue_in_quotes
    )
    while quote_state is not None:
        if opened_at is None or opened_at in close_at_end_of:
            close_at_end_of = frozenset(range(len(paragraphs)))
        else:
            close_at_end_of = close_at_end_of | {opened_at}
        rows, quote_state, opened_at = _walk_paragraphs(
            chapter_index, paragraphs, max_chars, close_at_end_of, dialogue_in_quotes
        )
        if quote_state is not None and len(close_at_end_of) >= len(paragraphs):
            raise RuntimeError(
                f"Unclosed {quote_state[0]} quote at the end of chapter {chapter_index} "
                f"survived closing every paragraph; expected {quote_state[1]!r}"
            )

    if close_at_end_of and warnings is not None:
        where = ", ".join(str(index + 1) for index in sorted(close_at_end_of))
        warnings.append(
            f"Chapter {chapter_index}: unclosed quote recovered by closing it at the end of "
            f"paragraph {where}; a stretch of this chapter may be cast as the wrong voice."
        )

    for index, row in enumerate(rows):
        if index + 1 >= len(rows):
            row["break_ms"] = 0
        elif rows[index + 1]["paragraph_index"] != row["paragraph_index"]:
            row["break_ms"] = max(int(row["break_ms"]), 380)
    source_tokens = _speakable_tokens(text)
    segmented_tokens = [token for row in rows for token in _speakable_tokens(str(row["text"]))]
    if segmented_tokens != source_tokens:
        raise RuntimeError("Segmentation changed the spoken token sequence")
    return rows


def build_chapter_manifest(input_files: list[Path], chapters_output_dir: Path) -> list[dict[str, Any]]:
    paths = sorted((p.resolve() for p in input_files), key=lambda p: natural_key(p.name))
    manifest: list[dict[str, Any]] = []
    for index, path in enumerate(paths, 1):
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".txt":
            raise ValueError(f"Only .txt input is supported: {path}")
        manifest.append(
            {
                "chapter_index": index,
                "title": path.stem,
                "input_path": str(path),
                "input_sha256": sha256_file(path),
                "input_size": path.stat().st_size,
                "output_mp3": str(chapters_output_dir / f"{index:05d}_{slugify(path.stem, 72)}.mp3"),
            }
        )
    return manifest


def input_manifest_hash(manifest: list[dict[str, Any]]) -> str:
    canonical = "\n".join(
        f"{row['chapter_index']}|{row['input_path']}|{row['input_sha256']}|{row['input_size']}"
        for row in manifest
    )
    return sha256_text(canonical)


def load_and_segment_chapter(
    chapter: dict[str, Any],
    max_chars: int,
    *,
    warnings: list[str] | None = None,
    drop_credits: bool = False,
) -> list[dict[str, Any]]:
    source = Path(chapter["input_path"])
    raw = source.read_bytes()
    expected_size = int(chapter["input_size"])
    expected_sha256 = str(chapter["input_sha256"])
    if len(raw) != expected_size or sha256_bytes(raw) != expected_sha256:
        raise RuntimeError(f"Source chapter changed while it was being loaded: {source}")
    text = decode_text_bytes(raw)
    return segment_chapter_text(
        int(chapter["chapter_index"]),
        text,
        max_chars=max_chars,
        warnings=warnings,
        drop_credits=drop_credits,
    )
