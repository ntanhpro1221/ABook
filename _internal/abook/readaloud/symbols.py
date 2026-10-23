"""Ký hiệu trong "Nghe ngay" đọc theo NGỮ CẢNH (±3 chữ quanh ký hiệu, có khi cả câu): "/" là ngày, "mỗi", "phần" hay "trên"; "-" trước số là "âm", "trừ" hay "đến"; "x4" là "nhân bốn"...

Bộ chuẩn hoá của sea-g2p đọc mỗi ký hiệu một kiểu cố định (">" luôn "lớn hơn", "#" luôn "thăng", "·" luôn "nhân"), nên mặt cười ">.<" nghe thành "lớn hơn nhỏ hơn". Đo 04-10 trên 5.052 mẫu có nhãn
(Corpus/research/tn/symbols): app sai 3,79 chữ / 10k chữ ở ký hiệu - nhiều hơn cả im với mọi ký hiệu (3,12). Mô-đun này gồm tầng 0 (bảng tra: ký hiệu nào im + ngắt, nào luôn có lời) và tầng 1 (luật ±3 chữ; đặc tả là
`symbols/rules.py` của bộ nghiên cứu cùng các phán quyết của chủ sách 04-10 ghi ở `Corpus/research/tn/gold_spec.md`, mục "Ký hiệu - Lead quyết 04-10").

`read_symbols(toks, out)` sửa tại chỗ `out` (cách đọc từng chữ hiện), số chữ không đổi. Ngữ cảnh lấy từ `toks` (chữ hiện chưa đổi: "HP" chứ không phải "hát pê") khi có. Quy ước thay thế: một lời ("nhân", "mỗi") được
thêm khoảng trắng hai bên khi dính chữ / số; im (rỗng) thì hai chữ dính hai bên được tách bằng một khoảng trắng; "im + ngắt" thêm dấu phẩy khi ký hiệu nằm GIỮA hai chữ (cuối câu đã có dấu câu); không rõ nghĩa thì để nguyên
cho sea-g2p. Bản Kotlin y hệt: `readaloud/Symbols.kt`, chung fixture tests/fixtures/vieneu/android/text.json.
"""
from __future__ import annotations

import re
import unicodedata

from .abbreviations import LETTERS

OPEN = "\"'“‘([【「『《〈«{〔"
CLOSE = "\"'”’)]】」』》〉»}〕"
PUNCT_MARKS = ".,;:!?…"
# nhãn chỉ số của trò chơi: "-" hay ":" cạnh nó là giá trị (âm), "->" là đổi giá trị (thành), "+" là cộng dồn
FRACTION_HINTS = frozenset("bằng còn gấp hơn kém nửa chia".split())  # "bằng 1/3", "còn 2/5": phân số dù đứng cạnh nhãn chỉ số
FRACTION_WORDS = frozenset("phần chia nửa hết chiếm tổng mất sức".split())  # "hết 2/10 máu", "chiếm 3/8": a/b là phân số (một phần mười)
SCORE_WORDS = frozenset("điểm sao đánh câu hỏi đúng sai".split())  # "Đánh giá 4/5", "đúng 7/10 câu": điểm, đọc "trên"
STAT_WORDS = frozenset("hp mp sp exp xp lv lvl level cấp hạng rank điểm giá str agi vit int dex luk atk def máu mana tiền vàng tuổi sức mạnh nhanh nhẹn phòng thủ thể lực ma lực thiện cảm kinh nghiệm chỉ số tốc độ quyến "
                       "rũ cảm tính may mắn".split())
MASK_PLACES = frozenset("năm tầng lầu phòng khu lớp tập chương thứ tuổi đời".split())  # đứng trước số bị che ("tầng 8x", "năm 200x")
VALUE_WORDS = frozenset("là tới xuống đến mức khoảng dưới ở tầng thành hoặc đa âm bằng sang lên vì năm toán tổng đạt còn".split())  # chữ đứng ngay trước "-3" mà "-" chỉ có thể là dấu âm
PENALTY_WORDS = frozenset("mất thêm giảm phạt thất bại hao tổn thương".split())  # lượng bị trừ: "Mất thêm -15%", "Thất bại: -90%"
DATE_WORDS = frozenset("ngày mùng mồng hôm nhật lịch hạn sáng trưa chiều tối lễ tết niệm".split())  # chữ chỉ ngày trong ±3 chữ: "d/m" mới là ngày tháng
DATE_PREFIX = frozenset("ngày mùng mồng hôm".split())  # đã có chữ này ngay trước số thì không thêm "ngày"
WEEKDAY = re.compile(r"thứ (?:hai|ba|tư|năm|sáu|bảy)|chủ nhật")
TEMP_WORDS = frozenset("độ nhiệt °c oc f".split())
PER_PHYSICAL = frozenset("h s giờ phút giây min hr sec ms".split())  # "km/h", "cm/s": trên; "10 DP/ngày", "chương/tuần": mỗi
# "km/h", "50km/h", "kg/m2", "mg/ml": "/" dính liền giữa HAI đơn vị đo là "trên" - để nguyên cả cặp, sea-g2p đọc "ki lô mét trên giờ".
# Chữ thường như ký hiệu SI (trừ lít "L"): "M/L" là cỡ áo. Bên trái không lũy thừa, bên phải không "s2": sea-g2p đọc "m3/h", "m/s2" sai.
UNIT_BEFORE = re.compile(r"(?<![^\W\d_])(?:km|cm|dm|mm|m|kg|mg|g|ml|mL|l|L)$")
UNIT_AFTER = re.compile(r"(?:h|ms|s|giờ|phút|giây|(?:km|cm|dm|mm|m)[23²³]?|kg|mg|g|ml|mL|l|L)(?![^\W_])")
PER_NOUNS = frozenset("ngày tuần tháng năm máy người lần cái chương tập".split())
RATIO_WORDS = frozenset("tỉ tỷ chia cược kèo".split())  # "tỉ lệ 7:3", "chia 8:2", "chia tiền 7:3": hai số liền - chỉ chữ ĐỨNG TRƯỚC số
RATIO_AFTER_TI = frozenset("lệ số".split())  # "lệ" / "số" chỉ là tỉ lệ / tỉ số khi theo sau "tỉ": "6:00 lệ phí" là giờ
NOT_RATIO_AFTER_CHIA = frozenset("tay ly lìa buồn vui sẻ".split())  # "chia tay 9:05" là giờ
DUEL_WORDS = frozenset("đấu đối trận đơn song solo đánh".split())  # "đấu 1:1": một chọi một
RATIO_SLASH = frozenset("tỉ tỷ lệ xác suất chia".split())  # "tỉ lệ 1/100": một phần trăm
DIRECTION_WORDS = frozenset("tăng giảm lên xuống cao thấp up down".split())
DASHES = "—–―"
KEY_WORDS = frozenset("ctrl alt shift tab esc enter".split())
NUMBER_WORDS = frozenset("không một hai ba bốn năm sáu bảy tám chín mười".split())
KEYS = {"↑": "lên", "↓": "xuống", "←": "trái", "→": "phải", "↖": "lên trái", "↗": "lên phải", "↘": "xuống phải", "↙": "xuống trái"}
KEY_RUN = re.compile("[" + "".join(KEYS) + r"]{2,}(?:[A-Za-z]{1,4}(?![^\W\d_]))?")  # "↑↑↓↓←→←→BA": phím bấm (mỗi mũi tên một hướng, chữ dính sau đọc từng chữ cái); cùng một hướng "→→→→" chỉ là trang trí
QUANTITY_WORDS = STAT_WORDS | frozenset("sát thương damage dmg exp strength intelligence agility vitality dexterity luck attack defense speed power ngắm zoom phóng".split())  # danh từ mà "Nx" nhân lên: "10x Sức mạnh", "(2x Intelligence)", "kính ngắm 8x"
PHRASE_BREAK = re.compile(r"[:;.!?…,()\[\]【】「」『』“”\"]")  # ranh giới cụm khi đếm chữ hai bên "×"
MASK_MARKS = "〇○◯□■▽●△▲★☆%￥#@＃＠$"  # ký hiệu che chữ: "×" lẫn trong dãy này là một phần của chỗ che
KAOMOJI = "´゜∀◕◡‿≧≦╯╰╭ω∇ಠ益ﾉﾟдДᴗヮ꒳˶˘ʕʔᴥ◠ヽ٩۶ᕕᕗ꒪ↀ͜͡ʖ￣ェ⑉﹏"  # chỉ gặp trong mặt cười kiểu Nhật
KAOMOJI_SPAN = re.compile(r"[^\s\w?!.,…\"“”]*[" + KAOMOJI + r"][^\s\w?!.,…\"“”]*")
FACE_UNDERSCORE = re.compile(r"\([\^=;°]_+[\^=;°]\)")  # "(^_^)", "(=_=)": mặt cười có gạch dưới
GRAWLIX = re.compile(r"(?=[!@#$%^&*?]*[@#$%^&][!@#$%^&*?]*[@#$%^&])[!@#$%^&*?]{3,}")  # "!@#$%": chửi thề che đi, không đọc
POSTSCRIPT = re.compile(r"(?<![A-Za-z])[Pp]/[Ss](?![A-Za-z])")  # "P/s", "p/S": bút ngữ
URL = re.compile(r"(?:https?://|www\.)[^\s]+|(?<![\w.])[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|vn|jp|re|io|me|tv|info|co|app)/[^\s]*", re.IGNORECASE)
URL_TAIL = ".,;:!?)]}>”’\"'"  # dấu cuối câu dính vào đường dẫn: không thuộc đường dẫn
ENTITIES = {"&gt;": ">", "&lt;": "<", "&amp;": "&", "&quot;": "\""}
STARS = "★☆✩✪✫✬✭✮✯✰⭐"
STAR_FULL = "★✪✮⭐"
STAR_MARKS = STARS + "︎️"  # dấu chọn kiểu chữ / kiểu emoji đứng sau ngôi sao
FULL_WIDTH = {"／": "/", "＃": "#", "＠": "@", "＋": "+", "＝": "=", "＞": ">", "＜": "<", "＆": "&"}
SPECIAL = frozenset("/／=#＃@＠^·<>+＋-–—―xX×$°&＆♀♂≠☎☏:↑↓▲▼△▽") | frozenset(STARS)
_NUMBER = re.compile(r"[+-]?\d+(?:[.,]\d+)*%?")
_NUMBERISH = re.compile(r"\d+[A-Za-z%°]*")
DIGIT_WORDS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười")


def core(word: str) -> str:
    """Chữ của `word` bỏ dấu câu và ngoặc hai đầu ("[Cường" -> "Cường", "1940." -> "1940")."""
    first, last = 0, len(word)
    while first < last and not word[first].isalnum():
        first += 1
    while last > first and not word[last - 1].isalnum():
        last -= 1
    return word[first:last]


def _numberish(word: str) -> bool:
    return bool(_NUMBER.fullmatch(word) or _NUMBERISH.fullmatch(word))


def _has(char: str, chars: str) -> bool:
    """`char` (một ký tự, có thể rỗng khi hết chữ) thuộc `chars`: khác `char in chars` ở chỗ chuỗi rỗng không thuộc."""
    return bool(char) and char in chars


def _single(word: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]", word or ""))


def _decimal(number: str) -> str:
    """Số có phần lẻ đọc "phẩy": "0.15" là "0 phẩy mười lăm" (hai chữ số lẻ đọc như một số), "5,0" là "5 phẩy 0"; số nguyên giữ nguyên."""
    match = re.fullmatch(r"(\d+)[.,](\d+)", number)
    if not match:
        return number
    whole, fraction = match.groups()
    if len(fraction) == 2 and fraction[0] != "0":
        from .vieneu import vietnamese_number  # nhập muộn: vieneu nhập mô-đun này
        fraction = vietnamese_number(int(fraction))
    return f"{whole} phẩy {fraction}"


def _kind(char: str) -> str:
    if not char:
        return "edge"
    if char.isspace():
        return "space"
    if char.isdigit():
        return "digit"
    if char.isalpha():
        return "upper" if char.isupper() else "lower" if char.islower() else "alpha"
    if char in OPEN:
        return "open"
    if char in CLOSE:
        return "close"
    if char in PUNCT_MARKS:
        return "punct"
    return "sym"


class Spot:
    """Một ký hiệu `sym` và chữ quanh nó: `left` / `right` là mọi chữ hiện bên trái / bên phải trên cùng đoạn (cách nhau một khoảng trắng như `tokens`)."""

    def __init__(self, left: str, sym: str, right: str) -> None:
        left, right = unicodedata.normalize("NFC", left), unicodedata.normalize("NFC", right)  # chữ hiện có thể là dạng tổ hợp ("tự" = tu + dấu)
        self.sym, self.left, self.right = sym, left, right
        self.lch, self.rch = left[-1:], right[:1]
        self.ltype, self.rtype = _kind(self.lch), _kind(self.rch)
        self.glued_l = bool(left) and not left[-1].isspace()
        self.glued_r = bool(right) and not right[0].isspace()
        left_words, right_words = left.split(), right.split()
        before = [core(word) for word in left_words[-3:]][::-1]
        after = [core(word) for word in right_words[:3]]
        before += [""] * (3 - len(before))
        after += [""] * (3 - len(after))
        self.l1, self.l2, self.l3 = before
        self.r1, self.r2, self.r3 = after
        self.lw1, self.rw1 = self.l1.lower(), self.r1.lower()
        self.left3 = {word.lower() for word in before}
        self.right3 = {word.lower() for word in after}
        self.line_start = not left.strip(" \t" + OPEN + "-–—")
        self.line_end = not right.strip(" \t" + CLOSE + ".,!?…")
        sentence = re.search(r"[.!?…]\s+[^.!?…]*$", left)
        self.colon_before = ":" in (left[sentence.start() + 1:] if sentence else left)
        self.count = len(re.findall(re.escape(sym[:1]) + "+", left + sym + right))  # số chỗ có ký hiệu (">>>" tính một)

    def near(self, size: int = 20) -> str:
        return self.left[-size:] + self.sym + self.right[:size]


# ---- một ký hiệu: (lời nói ra / "" im / None để nguyên, có ngắt không) -------------------------------------------------------------------
KEEP = (None, False)
SILENT = ("", False)
PAUSE = ("", True)
OVER = ("trên", False)  # a/b giữa hai số: sea-g2p đọc "trên" (sai khi b trông như năm: "5/1000" thành "tháng năm một nghìn"); nói ra luôn để giọng Edge nhận cùng chữ


def unit_slash(left: str, right: str) -> bool:
    """"/" giữa `left` và `right` (chữ hai bên, dính liền) nối hai đơn vị đo: "km/h", "50km/h", "kg/m2". Studio dùng chung
    (text_processing.spoken_symbols_to_words) để không đổi cặp ấy thành quãng nghỉ."""
    return bool(UNIT_BEFORE.search(left[-8:]) and UNIT_AFTER.match(right[:8]))


def _slash(c: Spot) -> tuple:
    if len(c.sym) > 1:
        return SILENT  # "////", "//" còn lại: trang trí
    if unit_slash(c.left, c.right):
        return KEEP  # "50km/h", "3 kg/m2": hai đơn vị đo, sea-g2p đọc cả cặp "ki lô mét trên giờ"
    m = re.search(r"(\d+)\s?$", c.left[-14:])
    k = re.match(r"\s?(\d+)", c.right[:14])
    if m and k:
        a, b = int(m.group(1)), int(k.group(1))
        if re.search(r"\d\s?/\s?\d+\s?$", c.left[-12:]) or re.match(r"\s?\d+\s?/\s?\d", c.right[:14]):
            return KEEP  # ngày đủ "10/07/2010": sea-g2p đọc cả ngày
        words = c.left3 | c.right3
        valid = 1 <= a <= 31 and 1 <= b <= 12
        if a <= 12 and 1900 <= b <= 2100:
            return ("năm", False)  # "tháng 8/ 2021"
        if re.search(r"(?<![\d.,])\d+[.,]\d{1,2}\s?$", c.left[-14:]):
            return ("trên", False)  # "9.7/10": điểm thập phân (không phải "1,419" ngăn nghìn)
        scored = bool(words & SCORE_WORDS) or (a <= b <= 100 and re.search(r"(?:mức|lượng|độ)[^:：]{0,30}[:：]\s?\d+\s?$", c.left.lower()) is not None)  # "Đánh giá 4/5", "Mức độ quan trọng: 4/5": x trên y
        if not (c.glued_l and c.glued_r):
            if valid and a > b and not scored and not c.left3 & (STAT_WORDS - {"chỉ", "số"}):
                return ("tháng", False)  # "8 / 3" cách khoảng: a > b thì không phải phân số / điểm, là ngày tháng
            return OVER  # "5813 / 5813": thanh chỉ số, "trên" (nói ra luôn để Edge đọc đúng như sea-g2p)
        if c.left3 & (STAT_WORDS - {"chỉ", "số"}) and not (a < b <= 100 and c.left3 & FRACTION_HINTS):
            return OVER  # "HP: 120/300"; "lượng HP bằng 1/3" là phân số; "chỉ", "số" (nửa của "chỉ số") không đủ làm nhãn
        if c.left3 & RATIO_SLASH:
            return ("phần", False) if a < b else OVER  # "tỉ lệ 1/100"
        signal = (words & DATE_WORDS) - ({"tối"} if words & {"đa", "thiểu", "ưu", "cao"} else set())  # "tối đa 3/5" không phải buổi tối
        if valid and (signal or WEEKDAY.search((c.left[-30:] + " " + c.right[:30]).lower())):
            if c.l2.lower() in DATE_PREFIX:
                return ("tháng", False)  # "ngày 5/3": đã có "ngày"
            return (f"ngày {m.group(1)} tháng", False, len(m.group(1)))  # "sinh nhật 5/3"
        if scored:
            return ("trên", False)  # điểm / sao / câu đúng / "nhãn: 3/4": x trên y
        if (a, b) == (24, 7) or (a == b == 1) or (a == b and re.match(r"\d+\s?[)\]]", c.right)):
            return OVER  # "24/7", "(1/1)": đếm số
        if a < b <= 100 and (a == 1 or words & FRACTION_WORDS or re.search(r"[=+×]", c.left[-4:] + c.right[:6])):
            return ("phần", False)  # "1/10 thu nhập", "hết 2/10 máu", "3/4+1/6=...": phân số (một phần mười)
        if b in (10, 100) and a <= b:
            return OVER  # "8/10": đếm số
        if (a == 1 and b > 1) or (a < b <= 9):
            return ("phần", False)  # "1/3", "3/5": phân số bé
        if valid and a > b:
            return ("tháng", False)  # "8/3", "30/4": không có điểm / phân số thì là ngày tháng
        return OVER  # "15/8", "180/300": không có chữ chỉ ngày thì là chỉ số / tỉ lệ
    if c.lch == "?" and k:
        return ("trên", False)
    if k and not c.glued_l and not c.glued_r and c.l1[:1].isalpha() and c.l1.islower():
        return ("chia", False)  # "sức khỏe / 2": chia cho hai
    word = re.match(r"[^\W\d_]+", c.right)
    right_word = word.group().lower() if word else ""
    digit_near = c.ltype == "digit" or bool(re.search(r"\d\s?[^\W\d_]{1,4}$", c.left[-8:]))
    if digit_near and c.rtype in ("lower", "upper", "digit"):
        return ("trên", False) if right_word in PER_PHYSICAL else ("mỗi", False)
    glued = c.glued_l and c.glued_r and c.ltype in ("lower", "upper") and c.rtype in ("lower", "upper")
    if glued and right_word in PER_NOUNS:
        return ("mỗi", False)
    if glued and right_word in PER_PHYSICAL:
        return KEEP  # "km/h", "m/s"
    if c.line_end or not c.right.strip() or c.rtype in ("close", "punct") or c.lch in ("?", "!", "."):
        return SILENT
    if c.l1[:1].isalpha() and c.r1[:1].isalpha():
        return PAUSE  # "Tarot/Bói toán", "Hạ/trung/cao": hai mục nối nhau
    return SILENT


def _equals(c: Spot) -> tuple:
    if len(c.sym) >= 2:
        return SILENT  # "===Real's POV===", "=="
    if c.lch in "<>!" and c.lch:
        return KEEP  # "<=", ">=", "!=": so sánh
    smile = _has(c.rch, ")(]._[=") and not (_has(c.rch, "([") and c.ltype in ("lower", "upper", "digit") and re.match(r".[\w(]", c.right))
    if smile or _has(c.lch, "#$%^&=°") or c.rch == "°" or (c.lch == "(" and c.rch and c.rch != " "):
        return SILENT  # mặt cười "=))", "=.=", "=]]", "(=ㅅ=", "(°=°)"
    if re.search(r"[?&][\w%.-]*$", c.left[-14:]) and re.match(r"[\w%-]", c.right):
        return SILENT  # tham số của đường dẫn "?v=abc"
    glued_word = c.glued_l and c.glued_r and c.ltype in ("lower", "upper") and c.rtype in ("lower", "upper")
    if glued_word and len(c.l1) <= 2 and re.search(r"[\d²³¹⁰⁴-⁹]", c.right.split(" ")[0]):
        return ("bằng", False)  # "y=ax²", "z=x2": công thức
    if glued_word and (len(c.l1) >= 2 or len(c.r1) >= 2):
        return SILENT  # "Re=L": nối trong tên
    if _has(c.rch, "^%$#@"):
        return SILENT  # "#$h=^%": chữ bị che
    near = c.near(24)
    if re.match(r"\d", c.r1) or re.match(r"\d", c.l1[-1:]) or "+" in near or ">" in near or "cộng" in near.lower() or _single(c.l1) or _single(c.r1):
        return ("bằng", False)  # biểu thức
    return ("là", False)  # định nghĩa: "Vương đô = Thủ đô Hoàng gia"


def _plus(c: Spot) -> tuple:
    if len(c.sym) >= 2:
        return (" ".join(["cộng"] * min(len(c.sym), 3)), False) if c.glued_l and c.ltype in ("upper", "lower", "digit") else SILENT  # hạng "S++", "AAA+++"
    if c.line_start and not c.glued_r:
        return SILENT  # "+ Cám ơn": gạch đầu dòng
    if c.glued_r and not c.glued_l and c.rtype in ("upper", "lower") and c.ltype in ("space", "open", "edge"):
        return SILENT  # "+Dimensional Pocket": đầu tên kỹ năng
    if c.ltype == "sym" or c.rtype == "sym":
        return SILENT  # "❗+❗": trang trí giữa các biểu tượng
    if c.glued_l and c.ltype in ("upper", "digit") and c.rtype not in ("lower", "upper", "digit"):
        return KEEP  # hạng "A+", "18+", "10000+": sea-g2p đọc "cộng"
    if c.line_end or (c.lch == "(" and c.rch == ")") or c.lch == "_":
        return SILENT
    if c.rtype == "digit" or c.ltype == "digit":
        return KEEP
    if c.glued_l and c.glued_r and c.ltype != "sym" and c.rtype != "sym":
        if c.ltype in ("upper", "lower") and c.rtype in ("upper", "lower") and len(re.search(r"[^\W\d_]+$", c.left).group()) >= 2 and len(re.match(r"[^\W\d_]+", c.right).group()) >= 2:
            return ("và", False)  # "Trans+Edit": hai tên / hai từ nối nhau
        return ("cộng", False)  # "θ+α", "A+B": liền nhau, phép cộng
    if not c.l1 and c.left.strip() and not c.glued_l:
        return SILENT  # "/ + Có mùi": đứng sau một ký hiệu lạ là dấu đầu mục
    if re.search(r"\d$", c.l1) and c.l2[:1].isalpha() and c.r1[:1].isupper() and len(c.r1) >= 2 and not c.glued_l and not c.glued_r and not (c.left3 | c.right3) & STAT_WORDS:
        return ("và", False)  # "Chương 2-8 + Ngoại truyện 1": nối hai mục
    words = c.l1[:1].isalpha() and c.r1[:1].isalpha()
    if words and (c.lw1 in KEY_WORDS or c.rw1 in KEY_WORDS or c.l1.isupper() or c.r1.isupper()):
        return ("cộng", False)  # phím tắt "CTRL + F", hạng "S + A"
    if words and re.search(r"=|\bbằng\b", c.near(40)):
        return ("cộng", False)  # công thức "Đẹp trai + Dễ thương = Tuyệt vời"
    if words and not (c.left3 | c.right3) & STAT_WORDS and not any(char.isdigit() for char in c.l1 + c.r1):
        return ("và", False)  # "Đồ án + thi": hai cụm chữ
    return KEEP


def _hash(c: Spot) -> tuple:
    if len(c.sym) >= 2:
        return SILENT
    if c.lw1 in ("số", "no") and not c.glued_l:
        return SILENT  # "số #521": đã có chữ "số"
    if re.match(r"\s?\d", c.right) and (not c.line_start or c.glued_r) and c.ltype != "sym":
        return ("số", False)  # "Bài toán #5", "[Át chủ bài #1]", "#1 là Alaba"
    return SILENT  # hashtag "#Tên", đầu mục, trang trí: bỏ "#", chữ sau đọc như thường


def _at(c: Spot) -> tuple:
    if len(c.sym) >= 2:
        return SILENT
    word_l = c.ltype in ("lower", "upper") and c.glued_l
    word_r = c.rtype in ("lower", "upper") and c.glued_r
    smiley = bool(re.match(r"[wεoO_.-]{1,2}@", c.right)) or _has(c.lch, "wεoO_")
    if word_l and word_r and not smiley:
        if re.match(r"[\w-]+(?:\.[\w-]+)+", c.right):
            return KEEP  # email "ten@mail.com": sea-g2p đọc "a còng"
        left_word = re.search(r"[^\W\d_]+$", c.left).group() if re.search(r"[^\W\d_]+$", c.left) else ""
        right_word = re.match(r"[^\W\d_]+", c.right).group()
        if min(len(left_word), len(right_word)) <= 3:
            return ("a", False)  # leet "v@i", "Dor@emon"
        return ("a còng", False)  # "homosapiens@neighbour": tên tài khoản
    if c.left3 & {"ngày", "tháng", "năm"} or c.right3 & {"ngày", "tháng", "năm"}:
        return SILENT  # ô trống "Ngày @ tháng"
    if word_r and not word_l and c.ltype != "digit" and not smiley:
        leet = re.match(r"[a-zà-ỹ]{1,3}(?![\w])", c.right)
        return ("a", False) if leet else ("a còng", False)  # "@ss": leet "ass"; "@ten": nhắc tên / tài khoản
    if not c.glued_l and not c.glued_r and c.l1[:1].isalpha() and not c.line_end:
        return ("a còng", False)  # "vừa @ mà": nhắc tên đã bị cắt
    return SILENT


def _caret(c: Spot) -> tuple:
    if len(c.sym) == 1 and c.ltype == "digit" and c.rtype == "digit":
        return ("mũ", False)
    return SILENT


def _angle_mark(c: Spot) -> tuple:
    """"<" / ">" còn lại sau `_angle` (ngoặc <Tên> đã bỏ): so sánh (hai bên là số / biến một chữ) có lời, xếp hạng giữa các danh xưng ("A > B > C") là "hơn", chuỗi bước / mục ("[A] > [B]", "là: A > B") là "rồi"; còn lại (mặt cười ">.<", trích ">>", mũi tên) im."""
    if c.rch == "=" and len(c.sym) == 1:
        return KEEP  # ">=", "<=": so sánh
    if (c.sym == "<" and re.match(r"-+>", c.right)) or (c.sym == ">" and re.search(r"<-+$", c.left)):
        return KEEP  # "<->": mũi tên hai chiều, `_arrow` lo
    if c.ltype in ("open", "sym") or c.rtype in ("open", "sym"):
        return SILENT  # mặt cười "(>w<*)", "<-"
    spaced = not c.glued_l and not c.glued_r
    words = c.l1[:1].isalpha() and c.r1[:1].isalpha() and not c.line_start
    if len(c.sym) >= 2 and not (c.sym[0] == ">" and len(c.sym) <= 3 and spaced and words):
        return SILENT  # ">>>>>>>>>>", "<<<": trích dẫn, kẻ trang trí
    if (_numberish(c.l1) or _single(c.l1)) and (_numberish(c.r1) or _single(c.r1)) and c.rtype != "sym":
        return KEEP  # "a > 0", "3 < 5"
    if not words:
        return SILENT
    stat = lambda word: word.lower().rstrip("0123456789.") in STAT_WORDS
    if stat(c.l1) or stat(c.r1):
        return ("thành", False)  # "Lv.1 > Lv.2": đổi chỉ số
    word = "hơn" if c.sym[0] == ">" else "nhỏ hơn"
    chain = c.count >= 2
    listing = ":" in c.left[-80:] or _has(c.left.rstrip()[-1:], "])】」") or _has(c.right.lstrip()[:1], "[(【「")
    if chain and listing:
        return ("rồi", False)  # "Cấp bậc là: Giáo Hoàng > Thánh Nữ > ...", "[A] > [B]"
    if chain:
        return (word, False)
    if c.colon_before and c.sym == ">":
        return ("rồi", False)  # "Chương 159: Trộm vặt > Ăn cướp"
    if not spaced:
        return SILENT
    return (word, False) if c.r1[:1].isupper() else PAUSE


def _minus(c: Spot) -> tuple:
    """"-" liền trước số: "âm" khi là giá trị đứng một mình (sau ":", "=", trong ngoặc, năm, nhiệt độ, đầu biểu thức), "trừ" khi là phép trừ giữa hai vế ("10 - 3", "x -3") hay
    lượng đổi của chỉ số ("HP -20", "-50% Nhanh nhẹn", "[Thất bại: -90%]"), im khi là mã / số hiệu ("Blue -1", "■■■-5")."""
    after = c.right
    percent = bool(re.match(r"\d[\d.,]*\s?%", after))
    modifier = bool((c.left3 | c.right3) & ((STAT_WORDS - {"chỉ", "số"}) | PENALTY_WORDS))
    if c.line_start:
        if percent and c.right3 & STAT_WORDS:
            return ("trừ", False)  # "-50% Nhanh nhẹn"
        if re.match(r"\d[\d.,]*[A-Za-z]{1,3}", after):
            return ("trừ", False)  # "-40TP"
        if re.match(r"\d{1,3}(?:,\d{3})+|\d{4,}\b", after):
            return ("âm", False)  # "〔-29,900 / Mã 1〕"
        if re.match(r"\d[\d.,]*\s+(điểm|hp|mp)\b", after.lower()):
            return ("trừ", False) if _has(c.lch, "[【〔") else ("âm", False)  # "[-100 điểm]" mất điểm; "-14 điểm." đầu dòng
        if re.fullmatch(r"\d[\d.,]*[\s)\]】』」”’\"'.!?…]*", after):
            return ("âm", False)  # "-0!": cả dòng chỉ là một giá trị
        return ("âm", False)  # "-2 =))", "-517, -499", "\"-192√3": dính số là dấu âm dù đầu dòng (gạch đầu dòng thì có khoảng trắng: "- 7")
    follow = after[:14].lower()
    if re.search(r"(→|⇒|➜|➡|-+>|=+>)\s?$", c.left[-6:]) or re.search(r"[▲▼△▽↑↓]\($", c.left[-3:]):
        return ("âm", False)  # "100 → -50", "▼(-1.44)": giá trị mới
    if c.right3 & TEMP_WORDS or "°" in follow[:8] or re.match(r"\d[\d.,]*\s?(độ|mét|oc|of)", follow):
        return ("âm", False)
    if c.lch == ")" and c.glued_l:
        return SILENT  # "Qterw-()-62": mã
    if c.ltype == "space" and _has(c.left.rstrip()[-1:], "”’\""):
        return SILENT
    if re.match(r"\d+\s?[:：]", after):
        return ("trừ", False) if c.ltype == "space" and c.l1[:1].isalpha() else SILENT  # "tuyệt mệnh -10:" hậu tố của tên kỹ năng; "Chương 07 -2: Tên" im
    stat = bool(c.left3 & (STAT_WORDS - {"chỉ", "số"})) or (c.l1.isupper() and 2 <= len(c.l1) <= 4) or re.search(r"(?:máu|sinh lực)(?:\s+[^\W\d]+){0,3}\s$", c.left.lower()) is not None  # "HP -1", "MGC -8", "Thanh máu của Shido -1"
    previous = re.search(r"(\d+)(?:st|nd|rd|th)?\s$", c.left[-6:]) if c.ltype == "space" and not stat else None
    if previous and re.search(r"\d-\d+\s$", c.left[-10:]):
        return ("trừ", False)  # "1-2-3 -25 điểm": sau một dãy số
    if previous:
        number = re.match(r"\d+", after).group()
        return SILENT if number == previous.group(1) else ("đến", False)  # "1 -2 năm", "chap 104 -105", "80 -90%"; "50 -50" (hoà): im
    if percent and modifier:
        return ("trừ", False)  # "[Thất bại: -90% chỉ số]", "Mất thêm -15%": lượng đổi của chỉ số
    if re.search(r"[:：]\s?$", c.left) or re.search(r"(?<![\w])(?:[Ll]v|lờ vê)\.?$", c.left):
        return ("âm", False)  # "Độ thiện cảm: -20", "Lv.-1"
    if c.ltype == "space" and c.lw1 in VALUE_WORDS:
        return ("âm", False)  # "giờ là -200", "xuống -5": giá trị
    label = re.search(r"[\[【〔「『“‘(（]([^\[\]【】〔〕「」『』“”‘’()（）:：]{1,60})$", c.left) is not None and c.ltype == "space" and len(re.match(r"\d+", after).group()) <= 3
    if c.ltype == "space" and (stat or label or c.lw1 == "bị" or (re.match(r"\d[\d.,]*\s+\w+", after) and c.r2.lower() in STAT_WORDS)):
        return ("trừ", False)  # "HP -20", "Sức mạnh -5", "bị -20 điểm", "[Ẩn nấp -1]": lượng đổi của một nhãn
    if c.ltype == "sym" and not _has(c.lch, "=<>+*/×:~"):
        return SILENT  # "■■■-5": số hiệu dính ký hiệu lạ
    if c.ltype == "space" and (_single(c.l1) or _has(c.left.rstrip()[-1:], ")]】")):
        return ("trừ", False)  # "x -3", "(a+b) -3": có vế trái
    if c.ltype == "space" and c.l1[:1].isupper() and c.l1.isalpha() and len(c.l1) >= 2 and not percent and not c.colon_before and len(re.match(r"\d+", after).group()) <= 3:
        return SILENT  # "Blue -1": số hiệu sau một tên
    return ("âm", False)  # đứng một mình: "Bởi vì -1", "năm -2324", "『-36』", "-3/4+1/6"


def _dash_range(c: Spot) -> tuple:
    """Gạch đứng riêng giữa hai số ("7 – 8cm", "5 - 8 giờ"): đến; gạch nối "-" mà vế sau không lớn hơn vế trước ("10 - 3"), có "=" kề ("7 = 10 - 3") hay sau thanh "x/y" ("MP: 334/623 - 200") là phép trừ."""
    first = re.search(r"(\d+)\w{0,3}\s$", c.left[-8:])
    second = re.match(r"\s(\d+)", c.right[:6])
    if not (first and second):
        return KEEP
    if c.sym in "-－" and (int(first.group(1)) >= int(second.group(1)) or re.search(r"[=＝]", c.left[-8:] + c.right[:10]) or re.search(r"\d\s?/\s?\d+\s$", c.left[-12:])):
        return ("trừ", False)
    return ("đến", False)


def _grade_minus(c: Spot) -> tuple:
    """"A-" hạng ở cuối chữ (một chữ hoa dính "-" rồi hết chữ): trừ."""
    if c.colon_before and c.ltype == "upper" and c.glued_l and not re.search(r"[^\W\d_]{2}$", c.left) and c.rtype in ("space", "close", "edge"):
        return ("trừ", False)
    return KEEP


def _times_pre(c: Spot, sym: str) -> tuple:
    """"x4", "×3" (sym đứng trước số, không dính chữ): nhân; "X" hoa trước số ("X0", "X68K") là biến / tên: ích."""
    if sym == "X" and (c.right.startswith("0") or re.match(r"\d+[A-Za-z]", c.right)):
        return ("ích", False)  # "X0", "X68K": tên / biến
    return ("nhân", False)


def _times_post(c: Spot, sym: str) -> tuple:
    """"3x", "100x", "0,5x", "1x Cuộn phép", "194X" - sym ngay sau số. Trả (lời, ngắt, số chữ số đứng trước được gộp vào lời).
    Số + x là con số bị che ("9x", "thứ 9x", "3x tuổi", "10x xem") thì "ích", là hệ số nhân của một đại lượng ("10x Sức mạnh", "kính ngắm 8x", "3x.") thì "N lần"."""
    number = re.search(r"\d+(?:[.,]\d+)?$", c.left).group()
    start = c.left[: len(c.left) - len(number)]
    place = c.l2.lower() in MASK_PLACES  # "tầng 8x", "năm 200x", "chương thứ 9x": số bị che
    if sym == "X" or place or (re.search(r"\d{3}$", number) and not re.match(r"\s?[a-zà-ỹ]|\s+[A-ZĐ]", c.right)):
        return ("ích", False, 0)  # "194X"
    if (c.l2.lower() in ("đến", "tới") and re.search(r"từ\s", c.left[-40:].lower())) or (c.l2.lower() == "từ" and c.r1 in ("đến", "tới")):
        return (number.replace(".", ",") + " lần", False, len(number))  # "từ 0x đến 1x": mức gấp, đọc "không lần"
    if c.left3 & {"tuổi", "thế", "hệ", "gen", "đời", "sinh"} or c.right3 & {"km", "km/h", "m"} or c.rw1 in ("tuổi", "đời"):
        return ("ích", False, 0)  # "tuổi 9x", "16x km/h", "3x tuổi"
    if re.search(r"(?:sin|cos|tan|cot|log|ln)[\s(]*[\d/.,]*$", start.lower()):
        return ("ích", False, 0)  # "cos2/3x": biến của hàm số
    times = (number.replace(".", ",") + " lần", False, len(number))
    if c.rw1 in QUANTITY_WORDS or c.l2.lower() in QUANTITY_WORDS:
        return times  # "10x Sức mạnh", "(2x Intelligence)", "kính ngắm 8x"
    if re.search(r"[A-Za-z]$", start) or re.search(r"[+=(]", c.left[-4:] + c.right[:3]):
        return ("ích", False, 0)  # "Maxmalefic9x", "2x+3": biến
    if c.rch == "[" or (re.search(r"(?:^|[\s\[(–—-])$", start) and re.match(r"\s+[A-ZĐ]", c.right)):
        return ("", False, 0)  # "32x[1]", "– 1x Cuộn phép": một cuộn phép
    if not c.right.strip() or c.right[0] in CLOSE + PUNCT_MARKS:
        return times  # "3x.", "3x,": hệ số nhân đứng một mình
    if "." in number or "," in number:
        return times  # "0.5x": không phẩy năm lần
    if re.match(r"\s[a-zà-ỹ]", c.right):
        return ("ích", False, 0)  # "9x của", "2x mà", "10x xem": số bị che, không có đại lượng nào theo sau
    return ("gấp " + number, False, len(number))  # "3x": gấp ba


def _times_sign(c: Spot) -> tuple:
    """"×" ngoài số: cặp đôi giữa hai tên ("và"), tiêu đề giữa hai cụm nhiều chữ (ngắt), ô trống "Ngày × tháng", dấu sai / che chữ (im), "×Course" (ích); có số hay chữ thường kề thì sea-g2p đọc "nhân"."""
    if len(c.sym) >= 2:
        return SILENT  # "××": tên / số bị che
    if (c.left3 | c.right3) & {"ngày", "tháng", "năm"}:
        return SILENT  # ô trống "Ngày × tháng"
    if _numberish(c.l1) and (_numberish(c.r1) or re.match(r"\s?\d", c.right)):
        return ("nhân", False)  # "2 × 3"
    if _has(c.lch, MASK_MARKS + "+=") or _has(c.rch, MASK_MARKS + "+=×:"):
        return SILENT  # lẫn trong dãy ký hiệu che chữ "〇×▽", "×%￥#@"
    if _has(c.lch, "“\"") and _has(c.rch, "”\""):
        return ("ích", False)  # dấu “×”
    if (c.ltype == "digit" or c.rtype == "digit" or re.match(r"\s?\d", c.right)) or _numberish(c.l1) or _numberish(c.r1):
        return KEEP
    if c.glued_r and not c.glued_l and c.rtype in ("lower", "upper") and c.ltype in ("space", "open", "edge") and len(re.match(r"[^\W\d_]+", c.right).group()) >= 3:
        return ("ích", False)  # "×Course": chữ x
    if c.glued_l and c.glued_r and c.ltype in ("lower", "upper") and c.rtype in ("lower", "upper"):
        return SILENT  # "Fe×rari", "Hunter×Hunter"
    if c.l1[:1].isupper() and c.r1[:1].isupper():
        names = c.left.split()[-2:] + c.right.split()[:2]
        phrase = len([w for w in names if w[:1].isupper()]) >= 3 or c.l2[:1].isupper() or c.r2[:1].isupper()
        if not phrase and not c.left.rstrip().endswith(CLOSE) and c.lch != ")":
            return ("và", False)  # cặp đôi "Tadaoki × Christina"
        return PAUSE  # tiêu đề "Nhiệm Vụ × Nhiệm Vụ Phụ"
    spaced = not c.glued_l and not c.glued_r
    if re.match(r"\s?[(（\[【]", c.right):
        return KEEP  # "(Phòng ngủ) × (Thời gian)": tích hai tập
    if re.search(r"tính|bằng|=|công thức", re.split(r"[.!?…]\s", c.left)[-1][-30:].lower()) or re.match(r"\s?\S+(?:\s\S+){0,2}\s?[=＝<>＜＞≥≤]", c.right[:40]):
        return KEEP  # "tính bằng 'Sức mạnh × Cấp độ'", "A × B > C": công thức
    phrase_l, phrase_r = re.split(PHRASE_BREAK, c.left)[-1].split(), re.split(PHRASE_BREAK, c.right)[0].split()
    bracketed = c.ltype in ("sym", "close", "space", "punct") and c.rtype in ("sym", "open", "space", "punct")  # "≪A B≫×≪C D≫": dính ngoặc, không dính chữ
    if bracketed and len(phrase_l) >= 2 and len(phrase_r) >= 2:
        return PAUSE  # "Đảo hoang × Bạn thơ ấu": hai cụm nhiều chữ (không số) - một nhịp ngắn
    if not c.right.strip() or re.match(r"\s?[?!.,;:…)\]}/]", c.right) or (spaced and c.l1[:1].islower() and c.r1[:1].islower() and c.lw1 != "dấu"):
        return PAUSE  # dấu sai / dấu đánh dấu: "Cơ hội ×", "(×)", "Yan × /", "bị × luôn"
    return KEEP


def _dollar(c: Spot) -> tuple:
    """"$" đứng riêng: tên ký hiệu ("dấu $", "ký hiệu $") là "đô la", còn lại (chửi thề "$h*t", "$$$") im."""
    return ("đô la", False) if c.left3 & {"tự", "hình", "hiệu", "dấu"} or re.search(r"\b(dollar|usd)\b", c.right[:50].lower()) else SILENT


def _amp(c: Spot) -> tuple:
    """"&": hai chữ cái viết tắt ("S&M", "R&D") đọc chữ cái với "en"; hai từ ("Trans & edit") là "và"; bị che trong chữ ("F&CK") hay kề ký hiệu thì im."""
    if c.glued_l and c.glued_r and c.ltype in ("upper", "lower") and c.rtype in ("upper", "lower"):
        left_word = re.search(r"[^\W\d_]+$", c.left).group()
        right_word = re.match(r"[^\W\d_]+", c.right).group()
        if len(left_word) <= 2 and len(right_word) <= 2 and left_word.isupper() and right_word.isupper():
            return ("en", False) if left_word != right_word else ("và", False)  # "S&M": ét en em; "W&W": hai chữ như nhau là tên
        if left_word.isupper() and right_word.isupper():
            return SILENT  # "HOLYF&CKINGS": chữ bị che
        return ("và", False)  # "Yami&Kaguza", "Love&Peace"
    if c.ltype in ("sym", "punct") or c.rtype in ("sym", "punct") or c.ltype == "edge" or c.rtype == "edge":
        return SILENT
    if c.l1[:1].isalnum() and c.r1[:1].isalnum():
        return ("và", False)
    return SILENT


def _gender(c: Spot) -> tuple:
    """"♀" / "♂" đứng riêng sau chữ ("Tộc: ♀", "là ♀,") là "nữ" / "nam"; dính trong tên riêng thì im."""
    if (c.glued_l and c.ltype in ("lower", "upper")) or (c.glued_r and c.rtype in ("lower", "upper", "digit")):
        return SILENT
    if c.l1[:1].isalpha() or re.search(r"[:：]\s?$", c.left):
        return ("nữ" if c.sym == "♀" else "nam", False)
    return SILENT


def _updown(c: Spot, word: str) -> tuple:
    """"↑" "▲" "△" (tăng) / "↓" "▼" "▽" (giảm): kề chỉ số ("(↑1)", "45 → 49 ↑", "▲(0.15)") có lời; đã có chữ chỉ hướng cạnh bên, hay chỉ là dấu đầu dòng thì im."""
    if c.sym in "↑↓" and c.line_start and re.match(r"\s?[=:：]", c.right):
        return ("lên" if c.sym == "↑" else "xuống", False)  # "↓ = Có": phím / hướng ở đầu dòng trước dấu bằng
    if (c.left3 | c.right3) & DIRECTION_WORDS or c.line_start or _has(c.lch, DASHES + "-"):
        return SILENT  # "—↓]": mũi tên dính gạch là trang trí
    after_number = (_numberish(c.l1) and not (c.glued_l and c.l2[:1].isalpha() and c.l2.lower() not in STAT_WORDS)) or re.search(r"\(\d+(?:[.,]\d+)?$", c.left[-12:]) is not None or re.search(r"(→|⇒|-+>)\s?\S*\s?$", c.left[-14:]) is not None  # "Đông 4↓" là nhãn chỉ chỗ: im; "(9↓)": số sát trước
    before_number = bool(re.match(r"\(?\d", c.right))
    in_frame = c.sym in "↑↓" and c.l1[:1].isalpha() and _has(c.right.lstrip()[:1], "}])】")  # "{Khả năng phản bội ↓ }"
    labelled = (c.glued_l and c.lw1 in STAT_WORDS) or (c.l1[:1].isalpha() and re.search(r"[:：]\s?$", c.left) is not None)  # "HP↑", "DEF↓", "Lượt đọc: ↓"
    if after_number or before_number or in_frame or labelled:
        return (word + " dần" if re.search(r"xếp|sắp", c.left[-60:].lower()) else word, False)  # "Sắp xếp theo độ phổ biến ↓": giảm dần
    return SILENT


# ---- bước không cần ngữ cảnh ---------------------------------------------------------------------------------------------------------
def _gap(before: str, after: str, said: str = "") -> str:
    """`said` đặt giữa `before` và `after` (chữ quanh nó), thêm khoảng trắng khi dính chữ; im thì tách hai chữ dính."""
    space_before = bool(before) and (before[-1].isalnum() or before[-1] in "%)]”’")
    space_after = bool(after) and (after[0].isalnum() or after[0] in "$([“‘")
    if said:
        return (" " if space_before else "") + said + (" " if space_after else "")
    return " " if bool(before) and before[-1].isalnum() and bool(after) and after[0].isalnum() else ""


def _replace(token: str, pattern: re.Pattern, said, keep_tail: str = "") -> str:
    """Thay mọi chỗ khớp `pattern` trong `token` bằng `said` (chuỗi hay hàm của chỗ khớp), giữ dấu cuối `keep_tail` của chỗ khớp."""
    pieces: list[str] = []
    last = 0
    for match in pattern.finditer(token):
        text = match.group()
        end = match.end()
        if keep_tail:
            end -= len(text) - len(text.rstrip(keep_tail))
        pieces.append(token[last:match.start()])
        word = said(match) if callable(said) else said
        pieces.append(_gap("".join(pieces), token[end:], word))
        last = end
    pieces.append(token[last:])
    return "".join(pieces)


def _keys(match: re.Match) -> str:
    run = match.group()
    arrows = "".join(char for char in run if char in KEYS)
    if len(set(arrows)) < 2:
        return ""  # "→→→→", "↑↑": cùng một hướng là trang trí / nhấn mạnh, không phải phím
    return " ".join([KEYS[char] for char in arrows] + [LETTERS[char.lower()] for char in run[len(arrows):]])  # "←→BA": chữ dính sau đọc từng chữ cái


def prepare(out: list[str]) -> None:
    """Bước đầu của `reading_marks`: thực thể HTML ("&gt;"), "P/s", đường dẫn ("đường dẫn"), chuỗi chửi thề che ("!@#$%"), mặt cười kiểu Nhật và dãy phím mũi tên ("↑↑↓↓") - không cần ngữ cảnh, bỏ hay đổi nguyên chữ."""
    for index, token in enumerate(out):
        if not any(char in token for char in "&@#$%^*!?/_ωヽ´゜∀◕◡‿≧≦╯╰╭∇ಠ益ﾉﾟдДᴗヮ꒳˶˘ʕʔᴥ◠٩۶ᕕᕗ꒪ↀ͜͡ʖ￣ェ⑉﹏↑↓←→↖↗↘↙") or token in ("!", "?", "!!", "??"):
            continue
        for entity, char in ENTITIES.items():
            token = token.replace(entity, char)
        token = _replace(token, POSTSCRIPT, "pê ét")
        token = _replace(token, URL, "đường dẫn", URL_TAIL)
        token = _replace(token, GRAWLIX, "")
        token = _replace(token, KEY_RUN, _keys)
        token = _replace(token, FACE_UNDERSCORE, "")
        if token.strip(PUNCT_MARKS + OPEN + CLOSE) != "ω":  # "ω" đứng riêng giữa câu là chữ Hy Lạp (ô mê ga), để nguyên
            token = _replace(token, KAOMOJI_SPAN, "", "")
        out[index] = token


# ---- từng ký hiệu trong từng chữ --------------------------------------------------------------------------------------------------------
def _run(token: str, pos: int, chars: str) -> int:
    end = pos
    while end < len(token) and token[end] in chars:
        end += 1
    return end


def _word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _ratio_before(near: str, far: str) -> bool:
    """Hai chữ đứng ngay trước số bên trái dấu ":" (`near` sát số) báo tỉ lệ / tỉ số. Chữ SAU giờ không tính: "12:30 chia tay" là giờ."""
    near, far = near.lower(), far.lower()
    if near in RATIO_WORDS - {"chia"} or far in RATIO_WORDS - {"chia"}:
        return True
    if near in RATIO_AFTER_TI and far in {"tỉ", "tỷ"}:
        return True
    return near == "chia" or (far == "chia" and near not in NOT_RATIO_AFTER_CHIA)


def _ratio(c: Spot) -> tuple:
    """":" giữa hai số dính liền: "tỉ lệ 7:3" / "chia 8:2" hai số liền, "đấu 1:1" là một chọi một, "3.17:1" (cược) là "ba phẩy mười bảy ăn một", còn lại (giờ "12:30") để sea-g2p. Trả (lời, ngắt, số chữ đứng trước được gộp)."""
    number = re.search(r"\d+(?:[.,]\d+)?$", c.left).group()
    right = re.match(r"\d+", c.right).group()
    words = c.left3 | c.right3
    if ("." in number or "," in number) and right == "1":
        return (_decimal(number) + " ăn", False, len(number))  # "kèo cược 3.17:1"
    if _ratio_before(c.l2, c.l3):
        return ("", False, 0)
    if number == "1" and right == "1" and words & DUEL_WORDS:
        return ("chọi", False, 0)
    return (None, False, 0)


def _star(token: str, pos: int, c) -> tuple:
    """Dãy sao ("★★★☆☆", "★5,0", "★MAX", "5★"): thang đánh giá đọc "<n> sao", còn lại trang trí thì im. Trả (chỗ kết thúc, (lời, ngắt))."""
    end = _run(token, pos, STAR_MARKS)
    spot = c(end)
    stars = [char for char in token[pos:end] if char in STARS]
    full = sum(char in STAR_FULL for char in stars)
    after = re.match(r"(\d+(?:[.,]\d+)?)|(?:MAX|Max|max)\b", token[end:]) if len(stars) == 1 and full else None
    if after and after.group(1):
        return end + after.end(), (_decimal(after.group(1)) + " sao", False)  # "★5,0": năm phẩy không sao
    if after:
        return end + after.end(), ("sao tối đa", False)
    standing = spot.rtype not in ("lower", "upper", "digit")
    if standing and re.search(r"[★☆][★☆\s]*(?:→|⇒|➜|➡|-+>|=+>)\s*$", spot.left) and full:
        return end, (DIGIT_WORDS[full] + " sao", False)  # "★★☆ -> ★★★": thang sao mới
    if len(stars) == 1 and full and standing and (re.search(r"(?:^|[\s(\[])\d+(?:[.,]\d+)?$", spot.left) or (spot.lw1 in NUMBER_WORDS and spot.ltype == "space")):
        return end, ("sao", False)  # "5★", "một ★"
    if 3 <= len(stars) <= 10 and standing and not (spot.glued_l and spot.ltype in ("lower", "upper")):
        mixed = 0 < full < len(stars)
        if mixed or spot.lch == "[" or ":" in spot.left[-30:] or "để lại" in spot.left[-14:]:
            return end, (DIGIT_WORDS[full if mixed else len(stars)] + " sao", False)  # "★★★☆☆": ba sao
    return end, SILENT


def _dispatch(token: str, pos: int, spot) -> tuple | None:
    """Ký hiệu bắt đầu ở `token[pos]`: (chỗ kết thúc, (lời, ngắt)[, số chữ đứng trước được gộp]) hay None khi không phải ký hiệu cần xét. `spot(end)` dựng ngữ cảnh của đoạn token[pos:end]."""
    char = token[pos]
    before = token[pos - 1] if pos else ""
    after_char = token[pos + 1] if pos + 1 < len(token) else ""
    if char in "/／":
        end = _run(token, pos, "/／")
        said = _slash(spot(end))
        if said[0] == "phần" and re.match(r"4(?![\d.,]?\d)", token[end:]):
            return end + 1, ("phần tư", False)  # "3/4": ba phần tư (không phải "phần bốn")
        return (end, said[:2], said[2]) if len(said) == 3 else (end, said)  # "sinh nhật 5/3": lời gộp luôn số đứng trước
    if char == "=":
        end = _run(token, pos, "=")
        return end, _equals(spot(end))
    if char in "#＃":
        end = _run(token, pos, "#＃")
        if before == "S" and re.match(r"\.\d", token[end:]):
            return end + 1, ("cảnh", False), 1  # "S#.1": cảnh một
        return end, _hash(spot(end))
    if char in "@＠":
        end = _run(token, pos, "@＠")
        return end, _at(spot(end))
    if char == "^":
        end = _run(token, pos, "^")
        return end, _caret(spot(end))
    if char == "·":
        return pos + 1, PAUSE
    if char in "<>":
        end = _run(token, pos, char)
        if end == pos + 1 and token[end:end + 1] == "=" and not re.match(r"[=>)(\]]", token[end + 1:end + 2]):
            return end + 1, ("lớn hơn hoặc bằng" if char == ">" else "nhỏ hơn hoặc bằng", False)  # ">=", "<=": sea-g2p đọc thiếu "hoặc"
        return end, _angle_mark(spot(end))
    if char in "+＋":
        end = _run(token, pos, "+＋")
        return end, _plus(spot(end))
    if char == "-" and after_char.isdigit() and not _word_char(before):
        return pos + 1, _minus(spot(pos + 1))
    if char == "-" and before.isupper() and not after_char.isalnum() and (pos < 2 or not (token[pos - 2].isalnum() or token[pos - 2] == "-")):
        return pos + 1, _grade_minus(spot(pos + 1))
    if char in "–—―-" and token == char:
        return pos + 1, _dash_range(spot(pos + 1))
    if char == ":" and before.isdigit() and after_char.isdigit():
        said, stop, back = _ratio(spot(pos + 1))
        return (pos + 1, (said, stop), back) if said is not None else None
    if char in "xX" and token == char:
        around = spot(pos + 1)
        return pos + 1, ("nhân", False) if _numberish(around.l1) and _numberish(around.r1) else KEEP  # "60 x 60"
    if char in "xX×" and before.isdigit() and (after_char.isdigit() or (char == "×" and after_char in "⋯…")):
        return pos + 1, ("nhân", False)  # "4x3", "2×5": giữa hai số; "98×⋯×3": dãy tích
    if char in "xX×":
        if char == "×" and not before.isdigit() and not after_char.isdigit():
            end = _run(token, pos, "×")
            return end, _times_sign(spot(end))
        if after_char.isdigit() and not _word_char(before):
            return pos + 1, _times_pre(spot(pos + 1), char)
        masked = re.match(r"[xX×]{2,}(?![\w])", token[pos:]) if before.isdigit() else None
        if masked:
            return pos + len(masked.group()), (" ".join(["ích"] * len(masked.group())), False)  # "19××", "0 0××": chữ số bị che, giữ số và đọc từng "ích"
        if before.isdigit() and not after_char.isdigit() and not (after_char.isalpha() or after_char == "_"):
            said, stop, back = _times_post(spot(pos + 1), char)
            return pos + 1, (said, stop), back
        return None
    if char == "$":
        end = _run(token, pos, "$")
        number = re.match(r"\d+(?:[.,]\d+)*", token[end:]) if end == pos + 1 else None
        if number:
            return end + len(number.group()), (number.group() + " đô la", False)  # "$5": năm đô la (sea-g2p đọc "u s d" rời)
        if before.isdigit() and end == pos + 1:
            return end, ("đô la", False)  # "500$"
        return end, _dollar(spot(end))
    if char == "°":
        if re.search(r"\d\s?$", spot(pos + 1).left[-3:]):
            return None  # "30°C", "180 °": sea-g2p đọc "độ"
        return pos + 1, SILENT  # mặt cười "(°ロ°)"
    if char in "&＆":
        end = _run(token, pos, "&＆")
        match = re.match(r"[Aa]\b", token[end:]) if end == pos + 1 and before and before in "Qq" and not (pos >= 2 and token[pos - 2].isalpha()) else None
        if match:
            return end + 1, ("hỏi đáp", False), 1  # "Q&A"
        return end, _amp(spot(end))
    if char in "♀♂":
        return pos + 1, _gender(spot(pos + 1))
    if char == "≠":
        around = spot(pos + 1)
        return pos + 1, ("không phải là", False) if around.l1 and around.r1 and around.ltype != "sym" and around.rtype != "sym" else SILENT
    if char in "☎☏":
        return pos + 1, ("điện thoại", False) if re.match(r"\s?[\d(]", spot(pos + 1).right) else SILENT
    if char in "↑▲△":
        return _updown_run(token, pos, spot, "tăng")
    if char in "↓▼▽":
        return _updown_run(token, pos, spot, "giảm")
    if char in STARS:
        return _star(token, pos, spot)
    return None


def _updown_run(token: str, pos: int, spot, word: str) -> tuple:
    end = pos + 1
    said, stop = _updown(spot(end), word)
    if said:
        number = re.match(r"\(?(\d+(?:[.,]\d+)?)\)?", token[end:])
        if number:
            parens = token[end:end + number.end()]
            return end + number.end(), (word + " " + parens.replace(number.group(1), _decimal(number.group(1))), False)
    return end, (said, stop)


def _source_left(source: str, token: str, pos: int) -> str:
    """Phần chữ bên trái ký hiệu `token[pos]` trong ngữ cảnh: chữ hiện (`source`) khi chữ đã được đổi cách đọc ở bước trước nhưng phần từ ký hiệu trở đi còn nguyên ("ATK↑" đã thành "a tê ca↑": nhìn "ATK")."""
    tail = token[pos:]
    return source[:len(source) - len(tail)] if token != source and source.endswith(tail) else token[:pos]


def read_symbols(toks: list[str] | None, out: list[str]) -> None:
    """Đọc các ký hiệu còn lại trong từng chữ của `out` theo ngữ cảnh ±3 chữ (xem đầu mô-đun). `toks` là chữ hiện tương ứng (khi cùng số chữ), dùng làm ngữ cảnh."""
    plain = toks if toks is not None and len(toks) == len(out) else list(out)
    starts: list[int] = []
    line = ""
    for word in plain:
        starts.append(len(line))
        line += word + " "
    for index, token in enumerate(out):
        if not any(char in SPECIAL for char in token):
            continue
        base = starts[index]
        after_line = line[base + len(plain[index]):]
        pieces: list[str] = []
        lead_comma = False
        pos = 0
        while pos < len(token):
            found = _dispatch(token, pos, lambda end, pos=pos: Spot(line[:base] + _source_left(plain[index], token, pos), token[pos:end], token[end:] + after_line)) if token[pos] in SPECIAL else None
            if found is None:
                pieces.append(token[pos])
                pos += 1
                continue
            end, (said, stop), *rest = found
            if rest and rest[0]:  # lời gộp luôn số đứng trước ("3x" -> "gấp 3")
                pieces[:] = ["".join(pieces)[:-rest[0]]]
            if said is None:
                pieces.append(token[pos:end])
                pos = end
                continue
            before_text = "".join(pieces)
            left_char = (line[:base] + before_text).rstrip()[-1:]
            after_text = token[end:]
            right_char = (after_text + after_line).lstrip()[:1]
            piece = _gap(before_text, after_text, said)
            if stop and not said and left_char.isalnum() and (right_char.isalnum() or right_char in OPEN):
                if before_text:
                    piece = "," + (" " if after_text[:1].isalnum() else "")
                else:
                    lead_comma = True
            pieces.append(piece)
            pos = end
        out[index] = "".join(pieces)
        if lead_comma and index and out[index - 1][-1:].isalnum():
            out[index - 1] += ","
