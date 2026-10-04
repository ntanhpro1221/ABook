"""B8 - ĐẦU RA CON TRỎ cho người nói (nhánh dev/breakthrough-eval, CHỈ để đo, không bao giờ gộp).

Bật bằng ABOOK_POINTER_MODE=1. Tắt (mặc định) thì bộ phân tích y hệt từng byte: không module nào gọi tới đây.

Model không sinh TÊN người nói mà TRỎ tới một mục do host liệt kê; host đổi con trỏ thành tên trước khi kiểm/lưu:

  @qk         cùng người nói với câu thoại/nội tâm thứ k TRƯỚC lô (k=1 là câu liền trước), trong cửa sổ POINTER_WINDOW
              đoạn trước lô cùng chương -> tên đã chốt của câu ấy (lúc chạy: quyết định của model; lúc học: gold;
              ABOOK_POINTER_GOLD_NAMES=<thư mục gold>: lấy từ gold để đo riêng dây chuyền lỗi)
  @S00k       cùng người nói với đoạn S00k ĐỨNG TRƯỚC trong chính lô (model trả theo thứ tự) -> người nói đã đổi của đoạn ấy
  @nk         người được nhắc tên ở mục k (cửa sổ chữ: các đoạn trong cửa sổ + lô + next_text của đoạn cuối lô) -> tên chuẩn
  @narrator   người kể ngôi thứ nhất (chỉ khi sách có voices.first_person_identity) -> danh tính ấy
  @new:<x>    người chưa có ở trên -> x là tên (chữ đầu viết hoa, hoặc trùng tên đã biết) thì tên ấy; không thì NPC_LOCAL:x;
              "@new:UNKNOWN" -> UNKNOWN
  NARRATOR / UNKNOWN   giữ nguyên (đoạn kể; nội tâm không rõ ai nghĩ)

Con trỏ hỏng (không có dạng trên, số ngoài danh sách, @S trỏ tới đoạn chưa trả hoặc là lời kể, @narrator khi sách
không có người kể ngôi 1, @new rỗng) -> PointerError (ValueError): vòng thử lại của _analyze_batch xử lý như JSON hỏng
(`except Exception` -> last_error, thử lại theo retry_count). Chỉ xét đoạn model trả kind dialogue/thought; đoạn
narration thì con trỏ (nếu có) bị bỏ, speaker=NARRATOR như cũ.

Tìm tên (gọn, tất định): (1) tên trong sổ nhân vật đã biết (đúng danh sách top-80 của prompt) - cả tên đầy đủ và từng
phần >= 3 ký tự nếu phần ấy không trùng giữa hai tên; mặt chữ trong văn bản phải viết hoa chữ đầu; (2) cụm chữ viết
hoa chữ đầu KHÔNG đứng đầu câu (bỏ từ xưng hô/đại từ ở đầu cụm) chưa có trong sổ -> tên chuẩn = mặt chữ. Một mục cho
mỗi tên chuẩn, tối đa POINTER_MAX_NAMES; thứ tự: tên có trong lô (theo lần xuất hiện đầu), rồi tên trong cửa sổ
(lần nhắc cuối gần lô nhất trước), rồi tên chỉ có ở next_text.

Cùng một hàm dựng khối dùng cho lúc chạy (analysis.py) và lúc dựng dữ liệu (LLM_Train/b8/build_b8.py).
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

POINTER_WINDOW = 9
POINTER_QUOTE_CHARS = 40
POINTER_NAME_CONTEXT = 12
POINTER_MAX_NAMES = 8
POINTER_NEW_MAX = 80

SYSTEM_RULE = """11. CHẾ ĐỘ CON TRỎ: speaker của đoạn dialogue/thought là MỘT con trỏ của khối "Con trỏ", không viết tên.
   Chọn con trỏ GẦN nhất trỏ đúng người; @new:<tên hoặc mô tả ngắn> khi người nói chưa có trong khối.
"""

_PRONOUN_HEADS = {
    "anh", "chị", "cô", "cậu", "em", "ông", "bà", "bác", "chú", "dì", "thím", "mợ", "cụ", "ngài", "nàng", "chàng",
    "lão", "tiểu", "thưa", "này", "ơi", "hỡi", "tôi", "ta", "mình", "tớ", "hắn", "họ", "nó", "con", "cháu", "thầy",
    "và", "nhưng", "rồi", "thì", "là", "của", "với", "cho", "khi", "nếu", "vì", "các", "những", "một", "người",
}
_SENTENCE_END = set(".!?…:;“‘«([—–-*")  # dấu đóng ngoặc kép KHÔNG: "“…” Anna hỏi" là chỗ lời dẫn nêu tên
_WORD = re.compile(r"[^\W\d_][\w’'-]*")
_POINTER = re.compile(r"@(?:(q)(\d+)|(n)(\d+)|(s)(\d{3})|(narrator)|new:(.*))", re.IGNORECASE | re.DOTALL)
_RESERVED = {"narrator": "NARRATOR", "unknown": "UNKNOWN"}


class PointerError(ValueError):
    """Con trỏ hỏng hoặc không tồn tại: lỗi định dạng, bộ phân tích thử lại như JSON hỏng."""


def enabled() -> bool:
    return os.environ.get("ABOOK_POINTER_MODE", "").strip() not in {"", "0"}


def gold_names_dir() -> str:
    return os.environ.get("ABOOK_POINTER_GOLD_NAMES", "").strip()


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", str(text or ""))


def _flat(text: str) -> str:
    return " ".join(_nfc(text).split())


def display_speaker(speaker: str) -> str:
    """Tên như prompt hiện (giống _previous_turns): NPC_LOCAL::c..::r..::nhãn -> NPC_LOCAL:nhãn."""
    speaker = str(speaker or "").strip() or "UNKNOWN"
    if speaker.startswith("NPC_LOCAL::"):
        return "NPC_LOCAL:" + speaker.rsplit("::", 1)[-1]
    return speaker


@dataclass
class Quote:
    kind: str
    speaker: str  # dạng hiện (display_speaker)
    text: str


@dataclass
class Mention:
    name: str  # tên chuẩn
    context: str


@dataclass
class PointerContext:
    quotes: list[Quote] = field(default_factory=list)  # @q1 = quotes[0] = câu liền trước lô
    names: list[Mention] = field(default_factory=list)  # @n1 = names[0]
    narrator: str = ""
    known: list[str] = field(default_factory=list)


# --- dựng ----------------------------------------------------------------------------------------------------


def _usable_known(known: Iterable[str]) -> list[str]:
    out = []
    for name in known:
        name = _nfc(name).strip()
        if not name or name.upper() in {"NARRATOR", "UNKNOWN"} or name.upper().startswith(("NPC_LOCAL", "NPC*")):
            continue
        if name.casefold() in _PRONOUN_HEADS:
            continue
        out.append(name)
    return out


def _alias_map(known: list[str]) -> dict[str, str]:
    """mặt chữ (casefold) -> tên chuẩn. Tên đầy đủ luôn có; từng phần >= 3 ký tự chỉ khi không trùng giữa hai tên."""
    aliases: dict[str, str] = {}
    parts: dict[str, set[str]] = {}
    for name in known:
        aliases.setdefault(name.casefold(), name)
        words = [w for w in re.split(r"[\s\-]+", name) if len(w) >= 3]
        if len(words) > 1:
            for word in words:
                parts.setdefault(word.casefold(), set()).add(name)
    for word, owners in parts.items():
        if len(owners) == 1 and word not in aliases and word not in _PRONOUN_HEADS:
            aliases[word] = next(iter(owners))
    return aliases


def _at_sentence_start(text: str, start: int) -> bool:
    before = text[:start].rstrip(" \t")
    return not before or before[-1] == "\n" or before[-1] in _SENTENCE_END


def _capitalised_runs(text: str) -> list[tuple[int, int, list[str]]]:
    """Các cụm từ liền nhau (cách một dấu cách) đều viết hoa chữ đầu: (đầu, cuối, các từ)."""
    runs: list[tuple[int, int, list[str]]] = []
    for match in _WORD.finditer(text):
        word = match.group(0)
        if not word[:1].isupper():
            continue
        if runs and text[runs[-1][1] : match.start()] == " ":
            runs[-1] = (runs[-1][0], match.end(), runs[-1][2] + [word])
        else:
            runs.append((match.start(), match.end(), [word]))
    return runs


def _mentions(text: str, aliases: dict[str, str]) -> list[tuple[int, str, int, int]]:
    """(vị trí, tên chuẩn, đầu, cuối) của mọi chỗ nhắc tên trong `text`."""
    found: list[tuple[int, str, int, int]] = []
    taken: list[tuple[int, int]] = []
    # (1) tên đã biết, dài trước
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.span()
            if not match.group(0)[:1].isupper() or any(s < end and start < e for s, e in taken):
                continue
            taken.append((start, end))
            found.append((start, aliases[alias], start, end))
    # (2) cụm viết hoa chữ đầu không đứng đầu câu, chưa có trong sổ
    for run_start, end, words in _capitalised_runs(text):
        start = run_start
        if _at_sentence_start(text, run_start) and len(words) == 1:
            continue  # một chữ viết hoa đầu câu: thường là chữ thường
        while words and words[0].casefold() in _PRONOUN_HEADS:
            start += len(words[0]) + 1
            words = words[1:]
        if not words or any(s < end and start < e for s, e in taken):
            continue
        surface = " ".join(words).strip("’'-")
        if len(surface) < 2 or surface.casefold() in _PRONOUN_HEADS or surface.isupper() and len(surface) <= 3:
            continue
        taken.append((start, end))
        found.append((start, aliases.get(surface.casefold(), surface), start, end))
    return sorted(found)


def build_context(
    window: list[tuple[str, str, str]],
    batch_rows: list[dict[str, Any]],
    known: Iterable[str],
    narrator: str = "",
) -> PointerContext:
    """window: (kind, speaker đã chốt, text) của tối đa POINTER_WINDOW đoạn trước lô (cũ -> mới); batch_rows: các dòng
    request của lô (text, next_text)."""
    known_list = _usable_known(known)
    quotes = [
        Quote(kind, display_speaker(speaker), _flat(text))
        for kind, speaker, text in reversed(window)
        if kind in {"dialogue", "thought"}
    ]
    window_text = "\n".join(_flat(text) for _kind, _speaker, text in window)
    batch_text = "\n".join(_flat(row.get("text", "")) for row in batch_rows)
    next_text = _flat(batch_rows[-1].get("next_text", "")) if batch_rows else ""
    full = window_text + "\n" + batch_text + "\n" + next_text
    batch_lo = len(window_text) + 1
    batch_hi = batch_lo + len(batch_text)
    aliases = _alias_map(known_list)
    best: dict[str, tuple[tuple[int, int], int, int]] = {}
    for position, name, start, end in _mentions(full, aliases):
        if batch_lo <= position < batch_hi:
            rank = (0, position)  # trong lô: theo lần đầu
        elif position < batch_lo:
            rank = (1, -position)  # cửa sổ: gần lô trước
        else:
            rank = (2, position)  # next_text
        if name not in best or rank < best[name][0]:
            best[name] = (rank, start, end)
    names = []
    for name, (_rank, start, end) in sorted(best.items(), key=lambda item: item[1][0])[:POINTER_MAX_NAMES]:
        lo, hi = max(0, start - POINTER_NAME_CONTEXT), min(len(full), end + POINTER_NAME_CONTEXT)
        context = full[lo:hi].replace("\n", " ").strip()
        names.append(Mention(name, ("…" if lo else "") + context + ("…" if hi < len(full) else "")))
    return PointerContext(quotes, names, narrator.strip(), known_list)


def block(context: PointerContext) -> str:
    """Khối chữ chèn ngay trước "Các đoạn liên tiếp:"."""
    lines = ["Con trỏ (@qk = người nói câu trước thứ k, @nk = người tên k, @S00k = người nói đoạn S00k ở trên trong lô"
             + (f", @narrator = {context.narrator}" if context.narrator else "") + "):"]
    for index, quote in enumerate(context.quotes, 1):
        text = quote.text if len(quote.text) <= POINTER_QUOTE_CHARS else quote.text[: POINTER_QUOTE_CHARS - 1] + "…"
        mark = " (nội tâm)" if quote.kind == "thought" else ""
        lines.append(f"@q{index} {quote.speaker}{mark}: {text}")
    for index, mention in enumerate(context.names, 1):
        lines.append(f"@n{index} {mention.name}: {mention.context}")
    return "\n".join(lines) + "\n\n"


# --- đổi ngược -----------------------------------------------------------------------------------------------


def _new_target(label: str, known: list[str]) -> str:
    label = " ".join(_nfc(label).split()).strip().strip("\"'“”<>")
    if not label or len(label) > POINTER_NEW_MAX:
        raise PointerError(f"@new rỗng hoặc dài quá {POINTER_NEW_MAX} ký tự")
    if label.casefold() in _RESERVED:
        return _RESERVED[label.casefold()]
    for name in known:
        if name.casefold() == label.casefold():
            return name
    if label[:1].isupper():
        return label
    return f"NPC_LOCAL:{label}"


def resolve_one(value: Any, context: PointerContext, earlier: dict[str, str]) -> str:
    """Một con trỏ -> tên. `earlier`: ID đoạn đứng trước trong lô (đã trả, dialogue/thought) -> người nói đã đổi."""
    raw = str(value or "").strip()
    if raw.casefold() in _RESERVED:
        return _RESERVED[raw.casefold()]
    match = _POINTER.fullmatch(raw)
    if match is None:
        raise PointerError(f"speaker {raw[:40]!r} không phải con trỏ")
    if match.group(1):
        k = int(match.group(2))
        if not 1 <= k <= len(context.quotes):
            raise PointerError(f"@q{k} ngoài danh sách ({len(context.quotes)} câu)")
        return context.quotes[k - 1].speaker
    if match.group(3):
        k = int(match.group(4))
        if not 1 <= k <= len(context.names):
            raise PointerError(f"@n{k} ngoài danh sách ({len(context.names)} tên)")
        return context.names[k - 1].name
    if match.group(5):
        batch_id = "S" + match.group(6)
        if batch_id not in earlier:
            raise PointerError(f"@{batch_id} không phải đoạn thoại đứng trước trong lô")
        return earlier[batch_id]
    if match.group(7):
        if not context.narrator:
            raise PointerError("@narrator nhưng sách không có người kể ngôi thứ nhất")
        return context.narrator
    return _new_target(match.group(8), context.known)


def resolve_payload(payload: dict[str, Any], context: PointerContext, batch_ids: list[str]) -> None:
    """Đổi speaker của mọi đoạn dialogue/thought trong payload (ID dạng S001, trước khi đổi sang stable_id) tại chỗ."""
    order = {batch_id: index for index, batch_id in enumerate(batch_ids)}
    earlier: dict[str, str] = {}
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        return
    for item in segments:
        if not isinstance(item, dict):
            continue
        batch_id = str(item.get("id", ""))
        kind = str(item.get("kind", ""))
        if kind not in {"dialogue", "thought"}:
            if str(item.get("speaker", "")).startswith("@"):
                item["speaker"] = "NARRATOR"
            continue
        allowed = {key: value for key, value in earlier.items() if order.get(key, 1 << 30) < order.get(batch_id, -1)}
        item["speaker"] = resolve_one(item.get("speaker"), context, allowed)
        if batch_id in order:
            earlier[batch_id] = item["speaker"]
