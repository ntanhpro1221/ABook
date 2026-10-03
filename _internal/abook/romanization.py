"""Đọc romaji Nhật (Hepburn) và phiên âm Latinh Hàn (RR) thành âm tiết tiếng Việt, theo `docs/READING_FOREIGN_NAMES.md` mục 1-3.

Quy ước ở tài liệu ấy là NGUỒN DUY NHẤT; mỗi lựa chọn dưới đây có ghi dòng của nó. Không dùng `ENGLISH_TO_VIETNAMESE.md`,
`_local_name_fallback` hay tên đã khoá. Bản Kotlin y hệt: `vn/abook/player/readaloud/Romanization.kt`; hai bên cùng đọc
`tests/fixtures/romanization/cases.json` (sinh bằng `scripts/build_romanization_fixture.py`), nên đổi một bên là phải đổi cả hai.

`romanized_reading(token, origin)` trả cách đọc nối gạch (các bộ phận của tên cách nhau dấu cách; hậu tố gọi -kun... nối gạch vào tên), hay None khi không chắc: chữ không
tách hết thành âm tiết của hệ ấy, viết hoa lạ, hay có âm tiết đầu ra mà `_valid_vietnamese_spoken_form` không nhận. CHƯA nối vào
đường đọc.

Ba loại cờ trong `romanized_reading_flags` (để người duyệt biết cách đọc dựa vào đâu):
  open:...    quy ước ghi "mở"; ở đây là một mặc định, chờ kiểm bằng âm thanh (`OPEN_CHOICES`)
  analogy:... quy ước không nói, suy theo hàng gần nhất của bảng
  fit:...     quy ước chọn một dạng mà bộ kiểm âm tiết không nhận, nên dùng dạng khác cũng có nguồn
"""
from __future__ import annotations

import unicodedata

# Chỗ quy ước còn "mở" (mục 3 dòng oe / wi / ui / we / wae, mục 7). Mặc định ở đây là quyết định tạm của app. Chủ sách 04-10 đã chốt (không còn mở): y + nguyên
# âm của cả Nhật lẫn Hàn -> gi + nguyên âm (Yamato -> Gia-ma-tô, Yoon -> Giun); k / t / p bật hơi của Hàn đọc như âm thường (Kang -> Cang, không kh); wo -> uô.
OPEN_CHOICES = {
    "y_after_vowel_pair": "hai nguyên âm rồi ya / yu / yo cuối từ mà luật y cuối từ không áp (Kouya, Raiya: âu / ai + y không thành vần): hiện y -> gi (Câu-gia)",
    "ko_rare_vowels": "oe / wi / ui / we / wae của tiếng Hàn: mặc định uê / uy / ưi / uê / oe theo âm (chưa có ví dụ chính thức)",
}

# Các điểm quy ước ghi [Chọn] / để ngỏ, và giá trị đang dùng. Giá trị là KẾT QUẢ QUÉT theo bằng chứng (scripts/sweep_romanization_variants.py:
# thử mọi biến thể, đếm dạng có nguồn khớp, ca "owner" x100, Bộ Ngoại giao x2, SGK x1, cộng đồng x0; hoà thì lấy biến thể có lý do ngữ âm và
# cho âm tiết hợp lệ). Bản Kotlin chỉ cài các giá trị mặc định này. KHÔNG nằm ở đây vì chủ sách đã chốt, cố định, không quét: u Nhật -> u
# ở mọi chỗ (fu phu, ku cu, ru ru, su xu, zu du, tsu xu, gu gu), hậu tố nối gạch (Haruto-kun -> Ha-ru-tô-cun), fu -> phu, e Nhật -> e
# (Hajime -> Ha-gi-me, Kôbe -> Cô-be), y + nguyên âm -> gi (Yamato -> Gia-ma-tô, Ayaka -> A-gia-ca; Yoon -> Giun), ee -> e, ii -> i (Onee -> One,
# Hiiragi -> Hi-ra-ghi), yu sau phụ âm tách (Ryuu -> Ri-u), shu -> su, k / t / p bật hơi của Hàn -> c / t / p, j Hàn -> gi, eo -> eo / e-o + coda
# (Seo -> Xeo, Jeong -> Gie-ong), wo -> uô (Won -> Guôn). "ei" dưới đây cũng đã chốt (Rei -> Rây), "g" trước i đọc "ghi" (Hiiragi) còn ji -> gi.
CHOICES = {
    "s": "x",                 # s Nhật (sa su se so): "x" | "s"
    "sh": "s",                # shi, sha, sho: "s" | "x"
    "ei": "ây",               # ei Nhật: CHỦ SÁCH 04-10 "Rei -> Rây, sensei -> xen-xây" (không quét); "e" | "ây" | "ay" là các dạng đã loại
    "k": "orth",              # "orth" (c / k theo chính tả) | "k_all" | "k_o" (k trước ô) - hai dạng sau bộ kiểm âm tiết không nhận
    "g": "gh",                # g trước i: CHỦ SÁCH 04-10 "Hiiragi -> hi-ra-ghi" (không quét); "gh" (ghi) | "gi" (gi, như ji) là dạng đã loại; trước e luôn ghe
    "kya": "ki_a",            # kya: "ki_a" (ki-a, như kyo -> ki-ô) | "kia"
    "ss": "t",                # ss Nhật khép âm tiết trước: "t" | "c"
    "ko_g": "k",              # g đầu từ của Hàn: "k" | "g"
    "ko_d": "t",              # d đầu từ: "t" | "đ"
    "ko_b": "b",              # b đầu từ: CHỦ SÁCH 04-10 "Busan -> bu-xan" (không quét; Park vẫn pắc vì chữ P là p): "p" | "b"
    "ko_s": "x",              # s của Hàn: CHỦ SÁCH 04-10 "Seojun -> xeo-giun" (không quét); "x" | "s"
    "ko_ye": "ê",             # ye sau phụ âm: "ê" | "iê"
    "ko_tense": "plain",      # kk tt pp jj ss: "plain" (c t p ch x) | "aspirated" (kh th ph ch x)
    "ko_a_short": True,       # a khép bằng k / t / p -> ă (Pắc) hay a (Pác)
}
# Bộ kiểm âm tiết có bật không (quét tắt đi để đếm cả biến thể mà bộ kiểm không nhận; dùng thật luôn bật).
_CHECK_SYLLABLES = True

_LONG_VOWELS = {
    "ā": "a", "ī": "i", "ū": "u", "ē": "e", "ō": "o", "â": "a", "î": "i", "û": "u", "ê": "e", "ô": "o",
    "Ā": "A", "Ī": "I", "Ū": "U", "Ē": "E", "Ō": "O", "Â": "A", "Î": "I", "Û": "U", "Ê": "E", "Ô": "O",
}
# Tiếng Nhật giữ ō / ô thành "ô" (nguyên âm dài viết bằng dấu -> ô), để phân biệt với "ou" viết ra hai chữ (-> âu: chủ sách 04-10)
_JA_LONG_O = {"ō": "ô", "Ō": "Ô", "ô": "ô", "Ô": "Ô"}
_ACUTE = "́"
_DIACRITIC_VOWELS = "ăâêôơư"
_FRONT = ("i", "e", "ê", "y")


class _Syl:
    """Một âm tiết đầu ra: phụ âm đầu (ký hiệu), vần, phụ âm cuối đã đổi sang chữ Việt (c, t, p, n, m, ng)."""

    __slots__ = ("onset", "nucleus", "coda")

    def __init__(self, onset: str, nucleus: str, coda: str = "") -> None:
        self.onset = onset
        self.nucleus = nucleus
        self.coda = coda


def _close(syllables: list[_Syl], coda: str) -> bool:
    """Khép âm tiết cuối bằng một phụ âm. Vần kết bằng i / u (ai, iu, ưi) không đứng trước phụ âm cuối: tách chữ cuối ra
    (analogy: "tách a-i khi hai âm tiết", mục 2 dòng ai)."""
    if not syllables or syllables[-1].coda:
        return False
    last = syllables[-1]
    if last.nucleus == "uy" or (last.nucleus.endswith("y") and len(last.nucleus) > 1):
        return False
    if len(last.nucleus) > 1 and last.nucleus[-1] in "iu":
        syllables[-1:] = [_Syl(last.onset, last.nucleus[:-1]), _Syl("", last.nucleus[-1], coda)]
    else:
        last.coda = coda
    return True


def _tone_acute(nucleus: str) -> str:
    """Thanh sắc cho vần của âm tiết khép p / t / c: lên chữ có dấu mũ / móc / trăng, không thì chữ cuối (oát, uýt)."""
    index = -1
    for position, letter in enumerate(nucleus):
        if letter in _DIACRITIC_VOWELS:
            index = position
    if index < 0:
        index = len(nucleus) - 1
    return unicodedata.normalize("NFC", nucleus[:index + 1] + _ACUTE + nucleus[index + 1:])


def _render(syllable: _Syl) -> str:
    onset, nucleus, coda = syllable.onset, syllable.nucleus, syllable.coda
    if onset == "S":
        onset = CHOICES["s"]
    if coda and nucleus == "ê":
        nucleus = "e"  # ê chỉ đứng cuối âm tiết mở; chỉ còn tiếng Hàn đi qua đây (ye -> ê), e Nhật đã là e
    if onset == "K":
        for glide in ("oai", "oa", "oe", "uy", "uê", "uơ", "uô"):
            if nucleus.startswith(glide):
                onset, nucleus = "qu", nucleus[1:]
                break
        else:
            onset = "k" if nucleus[:1] in _FRONT else "c"
            if CHOICES["k"] == "k_all" or (CHOICES["k"] == "k_o" and nucleus[:1] == "ô"):
                onset = "k"
    elif onset == "G":
        # g + i đọc "gi" (như ji) hay "ghi"; trước e, ê luôn "gh"
        onset = "gh" if nucleus[:1] in _FRONT and not (nucleus[:1] == "i" and CHOICES["g"] == "gi") else "g"
    elif onset == "gi" and nucleus[:1] == "i":
        nucleus = nucleus[1:]
    if coda in ("ng", "c") and nucleus.endswith(("i", "ê")) and nucleus[-2:-1] not in ("i", "y"):
        coda = "nh" if coda == "ng" else "ch"  # kinh, ích: -nh / -ch sau i, ê đơn (luật chính tả)
    if coda in ("c", "t", "p", "ch"):
        nucleus = _tone_acute(nucleus)
    return onset + nucleus + coda


def _validated(syllables: list[_Syl], capital: bool) -> str | None:
    from .analysis import _valid_vietnamese_spoken_form  # chỉ để kiểm, không sửa

    pieces = [_render(syllable) for syllable in syllables]
    if not pieces or (_CHECK_SYLLABLES and any(not _valid_vietnamese_spoken_form("", piece) for piece in pieces)):
        return None
    word = "-".join(pieces)
    return word[:1].upper() + word[1:] if capital else word


# ---- tiếng Nhật (mục 2) ----------------------------------------------------------------------------------------------

_JA_VOWELS = "aiueo"
_JA_VOWELS_LONG = _JA_VOWELS + "ô"  # ô: o viết bằng dấu (ō), đọc ô
_JA_VOWEL = {"a": "a", "i": "i", "u": "u", "e": "e", "o": "ô"}  # a i u e o -> a i u e ô (chủ sách 04-10: u -> u và e -> e ở mọi chỗ, không ư / ê)
# s -> x (luật 1.4), k / g theo chính tả (K, G), z -> d, d -> đ, h -> h, r -> r
_JA_SIMPLE = {"k": "K", "g": "G", "s": "S", "z": "d", "t": "t", "d": "đ", "n": "n", "h": "h", "b": "b", "p": "p", "m": "m", "r": "r"}
# Âm nào đi với nguyên âm nào trong Hepburn: không có ti, tu, di, du, si, zi, hu, wo, ye...
_JA_ALLOWED = {
    "k": "aiueo", "g": "aiueo", "n": "aiueo", "b": "aiueo", "p": "aiueo", "m": "aiueo", "r": "aiueo",
    "s": "aueo", "z": "aueo", "t": "aeo", "d": "aeo", "h": "aieo",
    "sh": "aiueo", "ch": "aiueo", "j": "aiueo", "ts": "u", "f": "u", "w": "a", "y": "auo",
    "ky": "auo", "gy": "auo", "ny": "auo", "hy": "auo", "by": "auo", "py": "auo", "my": "auo", "ry": "auo",
}
_JA_ONSETS = ("sh", "ch", "ts", "ky", "gy", "ny", "hy", "by", "py", "my", "ry")
_JA_GEMINATE_CODA = {"k": "c", "p": "p", "t": "t", "s": "ss"}  # kk pp tt ss: khép bằng c / p / t (ss: analogy, s không đứng cuối; CHOICES["ss"])


# Từ đã quen ở Việt Nam, chủ sách ghi đè cố định (04-10; không đổi luật): onigiri (cơm nắm) -> o-ni-gi-ri, trong khi g + i -> ghi (Hiiragi) vẫn đứng.
_JA_FIXED: dict[str, tuple[tuple[str, str], ...]] = {
    "onigiri": (("", "o"), ("n", "i"), ("gi", "i"), ("r", "i")),
}


def _ja_emit(onset: str, vowel: str, syllables: list[_Syl], flags: list[str]) -> bool:
    if onset == "":
        # chỉ là nguyên âm: o -> o khi đầu từ hay sau a / e (chủ sách 04-10: Osaka -> O-xa-ca, Aoi -> A-o-i, Naoki -> Na-o-ki), ô khi sau i / u như vần iô / uô
        # (Fumio -> Phu-mi-ô, Fukuoka -> Phu-cu-ô-ca); có phụ âm đầu thì o -> ô
        after_iu = bool(syllables) and not syllables[-1].coda and syllables[-1].nucleus[-1:] in ("i", "u")
        syllables.append(_Syl("", "o" if vowel == "o" and not after_iu else _JA_VOWEL[vowel]))
    elif onset in _JA_SIMPLE:
        syllables.append(_Syl(_JA_SIMPLE[onset], _JA_VOWEL[vowel]))
    elif onset == "sh":  # shi shu sha sho -> si su sa sô (luật 1.4; chủ sách 04-10: shu giữ s + u, không xiu)
        syllables.append(_Syl(CHOICES["sh"], _JA_VOWEL[vowel]))
    elif onset == "ch":  # chu -> chu (Chu-bu), u sau âm vòm
        syllables.append(_Syl("ch", _JA_VOWEL[vowel]))
    elif onset == "j":  # ji -> gi, ja -> gia, ju -> giu, jo -> giô
        syllables.append(_Syl("gi", _JA_VOWEL[vowel]))
    elif onset == "ts":  # tsu -> xu ở mọi chỗ (chủ sách 04-10: Tsubasa -> Xu-ba-xa; trước đó chu)
        syllables.append(_Syl("x", "u"))
    elif onset == "f":  # fu -> phu (chủ sách 04-10: Fukushima -> Phu-cu-si-ma)
        syllables.append(_Syl("ph", "u"))
    elif onset == "w":
        syllables.append(_Syl("", "oa"))  # wa -> oa (Ca-oa-xa-ki)
    elif onset == "y":  # y + nguyên âm -> gi + nguyên âm, đầu từ và giữa từ (chủ sách 04-10: Yamato -> Gia-ma-tô, Ayaka -> A-gia-ca); yu, yo theo ya
        if vowel != "a":
            flags.append("analogy:y_gi")
        syllables.append(_Syl("gi", _JA_VOWEL[vowel]))
    else:  # ky gy ny hy by py my ry: kyu -> ki-u, ri-u (chủ sách 04-10: tách như kyo, không kiu); kyo -> ki-ô, ri-ô (mục 2); kya -> ki-a theo hàng kyo
        head = _JA_SIMPLE[onset[0]]
        if vowel == "a":
            flags.append("analogy:cya")
        if vowel == "a" and CHOICES["kya"] == "kia":
            syllables.append(_Syl(head, "ia"))
        else:
            syllables.extend([_Syl(head, "i"), _Syl("", _JA_VOWEL[vowel])])
    return True


def _ja_word(word: str, flags: list[str]) -> list[_Syl] | None:
    fixed = _JA_FIXED.get(word)
    if fixed is not None:
        return [_Syl(onset, nucleus) for onset, nucleus in fixed]
    syllables: list[_Syl] = []
    i, size = 0, len(word)
    while i < size:
        c = word[i]
        after = word[i + 1:i + 2]
        # nn / kk / pp / tt / ss, tch, ssh: phụ âm đôi khép âm tiết trước (mục 2)
        if c in _JA_GEMINATE_CODA and (after == c or (c == "t" and word[i + 1:i + 3] == "ch")):
            if c == "s":
                flags.append("analogy:ss_t")
            if not _close(syllables, CHOICES["ss"] if c == "s" else _JA_GEMINATE_CODA[c]):
                return None
            i += 1
            continue
        if c == "n" and word[i + 1:i + 2] == "'":
            if not _close(syllables, "n"):
                return None
            i += 2
            continue
        if (c == "n" and after not in tuple(_JA_VOWELS_LONG) and not (after == "y" and word[i + 2:i + 3] in ("a", "u", "o"))) or (
            c == "m" and after in ("b", "m", "p")
        ):
            if not _close(syllables, "n"):  # ん: n khép âm tiết trước
                return None
            i += 1
            continue
        if c in _JA_VOWELS_LONG:
            onset, j = "", i
        else:
            onset = next((o for o in _JA_ONSETS if word.startswith(o, i)), c)
            j = i + len(onset)
            if onset not in _JA_ALLOWED:
                return None
        vowel = word[j:j + 1]
        long_o = vowel == "ô"
        if long_o:
            vowel = "o"
        if vowel == "" or vowel not in _JA_VOWELS or (onset and vowel not in _JA_ALLOWED[onset]):
            return None
        j += 1
        if onset == "y" and j == len(word) and syllables and not syllables[-1].coda and syllables[-1].nucleus in ("a", "ây"):
            # ya CUỐI từ sau nguyên âm: y thành bán âm cuối của âm tiết trước (ay, ây) + nguyên âm riêng (chủ sách 04-10: Maya -> May-a, Kaya -> Cay-a, Seiya -> Xây-a);
            # yu / yo cuối từ theo cùng cách là analogy (Mayu -> May-u, Sayo -> Say-ô); ya giữa / đầu từ vẫn gia (Ayaka -> A-gia-ca)
            if syllables[-1].nucleus == "a":
                syllables[-1].nucleus = "ay"
            if vowel != "a":
                flags.append("analogy:y_final")
            syllables.append(_Syl("", _JA_VOWEL[vowel]))
            i = j
            continue
        if onset == "y" and i >= 2 and word[i - 2] in _JA_VOWELS_LONG and word[i - 1] in _JA_VOWELS_LONG:
            flags.append("open:y_after_vowel_pair")  # Kouya, Raiya: hai nguyên âm rồi ya mà luật ya cuối từ không áp (âu / ai + y không thành vần): hiện y -> gi
        if not _ja_emit(onset, vowel, syllables, flags):
            return None
        # nguyên âm dài (không kéo dài): oo, ō -> ô, uu -> u, ee -> e, ii -> i, ei -> ây, ou viết ra -> âu (chủ sách 04-10); ai giữ là ai
        follow = "" if long_o else word[j:j + 1]
        if vowel == "e" and follow == "i":
            syllables[-1].nucleus = CHOICES["ei"]
            j += 1
        elif vowel == "o" and follow == "u":
            if onset in ("sh", "ch", "j"):
                flags.append("analogy:ou_vom")  # shou, chou, jou theo kyou / ryou của chủ sách (đã có âm vòm, không tách i-âu)
            syllables[-1].nucleus = "âu"
            j += 1
        elif vowel == follow and vowel in "oueia":
            j += 1  # nguyên âm kép viết lặp gộp một: oo -> ô, uu -> u, ee -> e, ii -> i, aa -> a (chủ sách 04-10: Onee -> O-ne, Hiiragi -> Hi-ra-ghi, Okaa -> O-ca)
        elif vowel == "a" and follow == "o":
            if j + 1 == len(word):
                syllables[-1].nucleus = "ao"  # ao CUỐI từ gộp một âm tiết (chủ sách 04-10: Nao -> Nao)
                j += 1
            else:
                flags.append("analogy:ao_split")  # ao giữa từ tách a-o (Aoi, Kaori: chủ sách; Naoki theo analogy): o tiếp theo tự đứng một âm tiết, đọc "o"
        elif vowel == "a" and follow == "i":
            syllables[-1].nucleus += "i"
            j += 1
        i = j
    return syllables


# ---- tiếng Hàn (mục 3) -----------------------------------------------------------------------------------------------

_KO_ONSETS = ("kk", "tt", "pp", "ss", "jj", "ch", "g", "k", "n", "d", "t", "r", "m", "b", "p", "s", "j", "h")
_KO_VOWELS = ("yeo", "yae", "wae", "eo", "eu", "ae", "ya", "yo", "yu", "ye", "wa", "wo", "we", "wi", "oe", "oi", "ui",
              "a", "e", "i", "o", "u")
_KO_CODAS = ("", "ng", "n", "m", "l", "k", "t", "p")
_KO_CODA_VIET = {"": "", "ng": "ng", "n": "n", "m": "m", "l": "n", "k": "c", "t": "t", "p": "p"}  # l cuối -> n; k t p -> c t p
_KO_VOWEL = {
    "a": "a", "eo": "eo", "o": "ô", "u": "u", "eu": "ư", "i": "i", "ae": "e", "e": "ê",
    "oe": "uê", "oi": "oi", "wi": "uy", "ui": "ưi", "wa": "oa", "wo": "uô", "we": "uê", "wae": "oe",
}
_KO_RARE = ("oe", "wi", "ui", "we", "wae")
# Myung -> mung là ca CỐ ĐỊNH của chủ sách 04-10 (Lee Myung-bak -> li mung-bắc; y sau m mất), không suy rộng: hyun / hyung vẫn hi-un / hi-ung.
# Cách viết Latinh quen dùng của tên Hàn, lệch khỏi RR (phần lớn là cách ghi của Bộ Ngoại giao / báo): đổi về RR trước khi tách.
_KO_SPELLINGS = {
    "kim": "gim", "park": "pak", "lee": "ri", "young": "yeong", "myung": "mung", "hyong": "hyeong", "hee": "hui",
    "soo": "su", "yoo": "yu", "yoon": "yun", "shin": "sin", "moon": "mun", "kwon": "gwon", "cho": "jo",
}


def _ko_parses(word: str, start: int, previous_coda: str | None, out: list[list[tuple[str, str, str]]],
               current: list[tuple[str, str, str]]) -> None:
    if start == len(word):
        out.append(list(current))
        return
    onsets = [o for o in _KO_ONSETS if word.startswith(o, start)]
    onsets.sort(key=len, reverse=True)
    onsets.append("")
    if previous_coda == "l" and word.startswith("l", start):
        onsets.insert(0, "l")  # ll: l thứ hai là phụ âm đầu
    for onset in onsets:
        at = start + len(onset)
        for vowel in _KO_VOWELS:
            if not word.startswith(vowel, at):
                continue
            after = at + len(vowel)
            for coda in _KO_CODAS:
                if coda and not word.startswith(coda, after):
                    continue
                current.append((onset, vowel, coda))
                _ko_parses(word, after + len(coda), coda, out, current)
                current.pop()


def _ko_best(word: str) -> list[tuple[str, str, str]] | None:
    """Cách tách duy nhất của một đoạn RR thành (phụ âm đầu, vần, phụ âm cuối), hay None khi không tách được / không chắc."""
    word = _KO_SPELLINGS.get(word, word)
    if not word or len(word) > 24 or any(doubled in word for doubled in ("aa", "ee", "ii", "oo", "uu")):
        return None  # RR không có nguyên âm đôi lặp (Yoo, Lee, Woo là cách viết quen, không phải RR)
    parses: list[list[tuple[str, str, str]]] = []
    _ko_parses(word, 0, None, parses, [])
    if not parses:
        return None
    # ít âm tiết nhất (ae là một vần, không phải a + e), rồi ít âm tiết không có phụ âm đầu nhất (Han-gang hơn Hang-ang)
    def rank(parse: list[tuple[str, str, str]]) -> tuple[int, int]:
        return len(parse), sum(1 for entry in parse[1:] if entry[0] == "")

    top = min(rank(parse) for parse in parses)
    best = [parse for parse in parses if rank(parse) == top]
    if any(parse != best[0] for parse in best):
        return None
    chosen = best[0]
    # ng hay n + g: RR viết giống nhau (Yong-in / Yon-gin, Han-gang / Hang-ang) - còn cách tách khác cùng số âm tiết thì không đoán
    for parse in parses:
        if parse != chosen and len(parse) == len(chosen):
            for left, right, other in zip(chosen, chosen[1:], parse):
                if left[2] == "n" and right[0] == "g" and other[2] == "ng":
                    return None
    return chosen


def _ko_words(segments: list[str], flags: list[str]) -> list[list[_Syl]] | None:
    """Các đoạn nối gạch của một tên Hàn (Geun-hye): cùng một từ về âm (g, d, b hữu thanh sau n, m, ng ngay cả qua dấu gạch), nhưng mỗi đoạn một bộ phận."""
    out: list[list[_Syl]] = []
    previous: str | None = None  # phụ âm cuối RR của âm tiết trước; None = đầu từ
    for segment in segments:
        parse = _ko_best(segment)
        if parse is None:
            return None
        syllables: list[_Syl] = []
        for position, (onset, vowel, coda) in enumerate(parse):
            viet_onset = _ko_onset(onset, previous, flags)
            after = parse[position + 1] if position + 1 < len(parse) else None
            part = _ko_nucleus(viet_onset, vowel, _KO_CODA_VIET[coda], flags, initial=previous is None,
                               before_u=after is not None and after[0] == "" and after[1] == "u")
            if part is None:
                return None
            syllables.extend(part)
            previous = coda
        out.append(syllables)
    return out


def _ko_onset(onset: str, previous: str | None, flags: list[str]) -> str | None:
    if onset in ("g", "d", "b"):
        # đầu từ vô thanh (c, t, p), giữa hai âm hữu thanh thì hữu thanh (g, đ, b): Cưn, Te, Pắc / Chang-đớc
        voiced = previous in ("", "n", "m", "ng")
        initial = {"g": "K" if CHOICES["ko_g"] == "k" else "G", "d": "t" if CHOICES["ko_d"] == "t" else "đ",
                   "b": "p" if CHOICES["ko_b"] == "p" else "b"}[onset]
        return {"g": "G", "d": "đ", "b": "b"}[onset] if voiced else initial
    if onset in ("k", "t", "p"):  # bật hơi: đọc như âm thường (chủ sách 04-10: Kang -> Cang, không kh; Taehyun -> Te-hi-un)
        return {"k": "K", "t": "t", "p": "p"}[onset]
    if onset in ("kk", "tt", "pp", "jj", "ss"):
        flags.append("analogy:ko_tense")
        if CHOICES["ko_tense"] == "aspirated":
            return {"kk": "kh", "tt": "th", "pp": "ph", "jj": "gi", "ss": CHOICES["ko_s"]}[onset]
        return {"kk": "K", "tt": "t", "pp": "p", "jj": "gi", "ss": CHOICES["ko_s"]}[onset]
    return {"s": CHOICES["ko_s"], "j": "gi", "ch": "ch", "r": "l" if previous is None else "r", "l": "l",
            "h": "h", "m": "m", "n": "n", "": ""}[onset]  # r đầu từ -> l, giữa từ -> r (mục 3)


def _ko_eo(onset: str, closing: str) -> list[_Syl]:
    """ㅓ: "eo" khi âm tiết mở (Seo -> Xeo, Jeo -> Gieo); có phụ âm cuối thì tách e-o + coda (Jeong -> Gie-ong, Seoul -> Xeo-un): chủ sách 04-10."""
    if not closing:
        return [_Syl(onset, "eo")]
    return [_Syl(onset, "e"), _Syl("", "o", closing)]


def _ko_nucleus(onset: str, vowel: str, closing: str, flags: list[str], initial: bool = True, before_u: bool = False) -> list[_Syl] | None:
    """Âm tiết (hay hai âm tiết) cho một vần RR, đã khép bằng `closing` (đã đổi sang chữ Việt). `initial`: đầu từ; `before_u`: âm tiết kế chỉ là "u"."""
    if vowel in _KO_RARE:
        flags.append("open:ko_rare_vowels")
    if vowel == "yae":
        return None
    if vowel in ("ya", "yo", "yu"):
        # y + nguyên âm -> gi + nguyên âm như tiếng Nhật (chủ sách 04-10: Yoon -> Giun); sau phụ âm tách i- (Hyun -> Hi-un, Hyung -> Hi-ung)
        letter = {"ya": "a", "yo": "ô", "yu": "u"}[vowel]
        pieces = [_Syl("gi", letter)] if onset == "" else [_Syl(onset, "i"), _Syl("", letter)]
    elif vowel == "yeo":
        # yeo: đầu từ gi + eo (Yeon -> Gie-on); sau phụ âm y MẤT, eo như bình thường (chủ sách 04-10: Gyeong -> Ghe-ong, Pyeong -> Pe-ong); g + y đọc g (ghe), không c / k
        flags.append("analogy:ko_yeo")
        pieces = _ko_eo("gi", closing) if onset == "" else _ko_eo("G" if onset == "K" else onset, closing)
        closing = ""
    elif vowel == "eo" and not closing and before_u:
        # eo mở đứng trước âm tiết u gộp thành e (chủ sách 04-10: Seoul -> Xe-un, không Xeo-un); analogy cho tên khác cùng dạng
        flags.append("analogy:ko_eo_u")
        pieces = [_Syl(onset, "e")]
    elif vowel == "eo":
        pieces = _ko_eo(onset, closing)
        closing = ""
    elif vowel == "ye":
        # ㅖ đọc như ㅔ sau phụ âm (Hê): ê; đầu từ thì gi + ê (y + nguyên âm -> gi)
        flags.append("analogy:ko_ye")
        if onset in ("K", "G"):
            pieces = [_Syl("G", "i")]  # gye -> ghi (chủ sách 04-10: Cheonggyecheon -> Che-ong-ghi-che-on)
        else:
            pieces = [_Syl(onset, "ê" if CHOICES["ko_ye"] == "ê" else "iê") if onset else _Syl("gi", "ê")]
    elif vowel == "wo" and onset == "":
        # w đầu từ -> gu (chủ sách 04-10: Won -> Guôn); giữa từ (Suwon) theo analogy cùng cách
        if not initial:
            flags.append("analogy:ko_w_gu")
        pieces = [_Syl("gu", "ô")]
    else:
        nucleus = _KO_VOWEL[vowel]
        if nucleus == "a" and closing in ("c", "t", "p") and CHOICES["ko_a_short"]:
            nucleus = "ă"  # Pắc, Bắc: a khép bằng k / t / p ngắn lại
        pieces = [_Syl(onset, nucleus)]
    if closing:
        if len(pieces) == 2:
            pieces[1].coda = closing
        else:
            tail = [_Syl(p.onset, p.nucleus) for p in pieces]
            if not _close(tail, closing):
                return None
            pieces = tail
    return pieces


# ---- cửa vào ---------------------------------------------------------------------------------------------------------

_JA_SUFFIXES = ("san", "kun", "chan", "sama", "senpai", "sensei", "dono", "tan", "nee", "nii")  # hậu tố gọi (mục 2): đọc theo chính bảng romaji, không có luật riêng


def _part_case(part: str) -> bool | None:
    """True nếu viết hoa chữ đầu, False nếu toàn chữ thường, None nếu không phải chữ hay viết hoa lạ (toàn hoa, hoa giữa chữ)."""
    if not part.replace("'", "").isalpha() or part.startswith("'") or part.endswith("'"):
        return None
    if part == part.lower():
        return False
    if part[0].isupper() and part[1:] == part[1:].lower():
        return True
    return None


def _read(token: str, origin: str) -> tuple[str, tuple[str, ...]] | None:
    value = unicodedata.normalize("NFC", token.strip())
    long_map = {**_LONG_VOWELS, **_JA_LONG_O} if origin == "ja" else _LONG_VOWELS
    value = "".join(long_map.get(ch, ch) for ch in value.replace("’", "'"))
    if not value or not all((ch.isascii() or ch in "ôÔ") and (ch.isalpha() or ch in "'- ") for ch in value):
        return None
    flags: list[str] = []
    words: list[str] = []
    for word in value.split():
        segments = word.split("-")
        cases = [_part_case(segment) for segment in segments]
        if any(case is None for case in cases):
            return None
        lowered = [segment.lower() for segment in segments]
        if origin == "ja":
            readings = []
            for segment in lowered:
                syllables = _ja_word(segment, flags)
                if not syllables:
                    return None
                readings.append(syllables)
        else:
            if any("'" in segment for segment in lowered):
                return None
            readings = _ko_words(lowered, flags)
            if readings is None:
                return None
        for index, syllables in enumerate(readings):
            # tên viết hoa thì mọi đoạn nối gạch viết hoa (Geun-hye -> Cưn Hê); hậu tố gọi (-san) giữ chữ thường và NỐI GẠCH vào tên thành một
            # chuỗi (chủ sách 04-10: Haruto-kun -> Ha-ru-tô-cun)
            # tên Hàn nối gạch cũng thành một chuỗi (chủ sách 04-10: Kim Jong-un -> Kim Giông-un, Lee Myung-bak -> Li Mung-bắc)
            suffix = index > 0 and (origin == "ko" or (origin == "ja" and lowered[index] in _JA_SUFFIXES))
            capital = False if suffix else cases[0]
            reading = _validated(syllables, bool(capital))
            if reading is None:
                return None
            if suffix:
                words[-1] += "-" + reading
            else:
                words.append(reading)
    if not words:
        return None
    return " ".join(words), tuple(dict.fromkeys(flags))


def romanized_reading_flags(token: str, origin: str | None) -> tuple[str, tuple[str, ...]] | None:
    """(cách đọc, cờ) hay None. `origin` "ja" / "ko" do cuốn sách cho biết; không biết gốc (None) thì không đoán: nhiều tên Nhật tách được
    cả theo RR (Hajime), nên đoán gốc từ chữ là đoán sai một nửa."""
    if origin not in ("ja", "ko"):
        return None
    return _read(token, origin)


def romanized_reading(token: str, origin: str | None) -> str | None:
    """Cách đọc nối gạch của một tên romaji Nhật / phiên âm Latinh Hàn, hay None khi không chắc."""
    found = romanized_reading_flags(token, origin)
    return None if found is None else found[0]
