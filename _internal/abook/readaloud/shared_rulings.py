"""Second tier for what the rules cannot tell from the letters: a small local model rules, once per book.

Two questions, both about words the first tier leaves in doubt:

1. A word that is both Vietnamese and English (`phoneme_policy.shared_word_verdicts`, the learned table). The table is
   sure of most occurrences. It is blind where the kinds of the neighbours are the same for both readings: a capital
   that is a title and not a name ("Kỵ Sĩ Tự Do", "guild Say xỉn"), a toneless word between a name and a Vietnamese
   word ("Yuna no đâu"), a sentence-initial "Do" before a borrowed noun. Those occurrences are asked one by one, with
   the sentence around.
2. The origin of a character's name (Vietnamese / Sino-Vietnamese, Japanese, Korean, other), name by name, from the
   character roster of the analysis. A book whose origin the name rules cannot settle still has a "Chiaki"; a Japanese
   book still has a "Jieun"; a Vietnamese book has an "An" that sea-g2p reads as the English article.

Studio already runs a small model through Ollama for the analysis; this pass asks that same model, on the same
server, right after the analysis (the hook of `webui/music_moods.py`). Nothing here runs while a listener waits.

The answers are kept in the project (`shared_rulings.json`) and travel inside the `.abook` (`sharedWords`), keyed by
what the phonemizer sees (`phoneme_policy.shared_word_contexts`), so synthesis, a resume and a phone with no model all
read the same answer. No file, no model, an answer that is not valid JSON: tier 1 alone decides, as before.

Deterministic: temperature 0, one seed derived from the model digest and the batch, answers kept per model digest and
prompt version. A different model or prompt asks again; the same one never does.
Only HTTP to Ollama (the `ollama` CLI starts the tray app when the server is down).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .phoneme_policy import Rulings

FILE = "shared_rulings.json"
VERSION = 2
MODEL = "abook-analyzer:v5"  # the analysis model (the worker passes the project's own): every Studio has it, and it answers both questions better than the music model (TEST_REPORT)
PROMPT_VERSION = "sw-2+no-3"
BATCH = 8  # items per request
NAME_LIMIT = 160  # roster names asked, in roster order (main characters first)
ROSTER_SHOWN = 5  # other roster names shown beside each name asked (the main characters)
CONTEXT_WORDS = 14  # shown words kept each side of the marked word
OPTIONS = {"temperature": 0, "num_ctx": 4096}
KEEP_ALIVE = "5m"
ORIGINS = ("vi", "ja", "ko", "en")
VIETNAMESE_KIND = "tu_viet"
KINDS = (VIETNAMESE_KIND, "ten_viet", "tieng_anh", "ten_ngoai")

SYSTEM = """Bạn giúp máy đọc truyện chọn cách phát âm. Mỗi mục là một câu trích từ truyện dịch sang tiếng Việt, trong đó MỘT chữ không dấu nằm trong [[ ]]. Câu có thể lẫn tiếng Anh, tên riêng nước ngoài, romaji.

Việc của bạn: cho biết chữ trong [[ ]] ĐƯỢC VIẾT bằng tiếng nào - không phải nó dịch ra tiếng Việt nghĩa là gì.
1. "cum": chép lại đúng cụm 2-3 chữ liền nhau trong câu mà chữ ấy thuộc về.
2. "loai": một trong bốn loại
   - "tu_viet": cụm ấy là lời văn tiếng Việt, chữ ấy là từ tiếng Việt không cần dấu (than vãn, to lớn, say sưa, bay lên, do dự, so sánh, leo thang, ban cho, in qua, no bụng, non nớt). Một từ tiếng Việt đứng ngay sau tên nước ngoài vẫn là "tu_viet": "Edward than vãn", "Leila in bóng lên cửa", "Naomi do dự". Viết hoa trong danh hiệu, tên kỹ năng tiếng Việt cũng là "tu_viet".
   - "ten_viet": tên người Việt hay Hán Việt (An, Yen, Can, Ban, Long), đi cùng họ tên / lời văn kiểu Việt - Trung.
   - "tieng_anh": chữ ấy nằm trong một câu hay cụm tiếng Anh (so high, to do, more than, I am, mini van, Zero Day, trust me), kể cả cụm tiếng Anh chen giữa câu tiếng Việt.
   - "ten_ngoai": một phần của tên riêng nước ngoài hay romaji, tiếng Hàn, Nhật, Pháp, Latin... (Do Hyun, An Hyeon-do, Ban Seong-cheol, Le Do-yoon, de Valis, Van Gogh, Marina Bay, Hikaru no Go, Ben, Leo).

Trả JSON, đủ mọi số thứ tự."""

# One worked batch, written for this prompt (no book's text): the model copies the shape and the care about names.
SHOTS = (
    ("Edward [[than]] vãn.", "Edward than vãn", "tu_viet"),
    ("\"[[So]], what do you want?\" Alice asked.", "So, what do", "tieng_anh"),
    ("0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0.", "0. Câu thử đã gỡ. 0."),
    ("Cậu ta mặc áo in dòng chữ \"I [[am]] happy\" rất buồn cười.", "I am happy", "tieng_anh"),
    ("Anh họ [[Do]] Hyun bước vào phòng.", "Do Hyun", "ten_ngoai"),
    ("Sakuya [[say]] sưa ngẩng đầu nhìn lên nóc nhà.", "say sưa", "tu_viet"),
    ("Danh hiệu mới: Kỵ Sĩ Tự [[Do]].", "Tự Do", "tu_viet"),
    ("\"[[An]] An, lại đây với mẹ.\" Lâm phu nhân gọi.", "An An", "ten_viet"),
    ("[[Do]] editor bận nên chương này ra trễ.", "Do editor bận", "tu_viet"),
)

NAME_SYSTEM = """Bạn giúp máy đọc truyện đọc đúng tên nhân vật. Mỗi mục là MỘT tên nhân vật viết bằng chữ Latin không dấu, có thể kèm trong ngoặc vài nhân vật khác của cùng cuốn truyện. Cho biết tên ấy gốc tiếng nào:
- "vi": tên Việt, hoặc tên Trung Quốc đọc theo âm Hán Việt (An An, Lan Anh, Tieu Yen, Long, Hung, Minh, Van, Son, Tan, Linh).
- "ja": tên Nhật viết romaji (Tanaka Kenji, Yuki, Akane, Shinomiya, Ryouta).
- "ko": tên Hàn (Kim Seo-yeon, Jihoon, Park Taehyun, Yejin, Eunbi).
- "en": tên Âu - Mỹ, tên fantasy, hay tên nào khác (Edward Elric, Alice, Ben, Dan, Leo, Van Helsing, Rimuru).
Xét chính cái tên trước: tên rõ là Nhật, Hàn hay Âu - Mỹ thì giữ gốc ấy dù truyện có nhân vật gốc khác. Chỉ tên ngắn không rõ gốc (An, Ban, Can, Long, Son, Van, Bin, Min) mới theo các nhân vật cùng truyện: cùng truyện với tên Việt / Hán Việt thì "vi", với tên Âu - Mỹ thì "en", với tên Hàn thì "ko".

Trả JSON dạng {"1": "ja", "2": "vi"}, đủ mọi số thứ tự."""

# (name, the other characters shown with it, origin)
NAME_SHOTS = (("Lan Anh", (), "vi"), ("Tanaka Kenji", (), "ja"), ("Kim Seo-yeon", (), "ko"), ("Edward Elric", (), "en"),
              ("Van", ("Tiêu Viêm", "Dược Lão", "Nạp Lan"), "vi"), ("Van", ("Alice", "Edward", "Helsing"), "en"),
              ("Yuki", ("Alice", "Edward", "William"), "ja"), ("Jihoon", ("Tanaka", "Akane", "Ryouta"), "ko"))


@dataclass(frozen=True)
class Doubt:
    """One occurrence the second tier is asked about."""

    key: str  # phoneme_policy.shared_word_contexts
    word: str
    shown: str  # the sentence as written, the word inside [[ ]]
    name: bool  # written as a name (a capital mid-sentence, shouting)


def marked(tokens: Sequence[str], index: int, start: int, end: int) -> str:
    """The shown words around `tokens[index]`, its letters `start:end` inside [[ ]]."""
    token = tokens[index]
    first, last = max(0, index - CONTEXT_WORDS), min(len(tokens), index + CONTEXT_WORDS + 1)
    middle = token[:start] + "[[" + token[start:end] + "]]" + token[end:]
    return " ".join([*tokens[first:index], middle, *tokens[index + 1:last]])


def _numbered(items: Iterable[str]) -> str:
    return "\n".join(f"{number}. {item}" for number, item in enumerate(items, 1))


def _seed(digest: str, user: str) -> int:
    """One seed per (model, batch): the same model gives the same answer on every run (analysis derives its seed the same way)."""
    return int(hashlib.sha256(f"{PROMPT_VERSION}|{digest}|{user}".encode("utf-8")).hexdigest()[:8], 16) % 2_000_000_000 + 1


def _body(model: str, digest: str, messages: list[dict[str, str]], schema: dict[str, Any], predict: int) -> dict[str, Any]:
    return {"model": model, "messages": messages, "stream": False, "think": False, "format": schema,
            "options": {**OPTIONS, "num_predict": predict, "seed": _seed(digest, messages[-1]["content"])}, "keep_alive": KEEP_ALIVE}


def payload(model: str, digest: str, batch: Sequence[Doubt]) -> dict[str, Any]:
    """The request for one batch of occurrences: the system prompt, one worked batch, the batch."""
    keys = [str(number) for number in range(1, len(batch) + 1)]
    item = {"type": "object", "properties": {"cum": {"type": "string"}, "loai": {"type": "string", "enum": list(KINDS)}},
            "required": ["cum", "loai"]}
    worked = {str(number): {"cum": phrase, "loai": kind} for number, (_, phrase, kind) in enumerate(SHOTS, 1)}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": _numbered(shown for shown, _, _ in SHOTS)},
                {"role": "assistant", "content": json.dumps(worked, ensure_ascii=False)},
                {"role": "user", "content": _numbered(doubt.shown for doubt in batch)}]
    return _body(model, digest, messages, {"type": "object", "properties": {key: item for key in keys}, "required": keys},
                 40 * len(batch) + 40)


def ambiguous(name: str) -> bool:
    """A name that holds a word of the table ("An An", "Van", "Son Goku"): its letters alone do not say which language."""
    from .phoneme_policy import _shared

    listed = _shared().listed
    return any(word.lower() in listed for word in name.replace("-", " ").split())


def name_item(name: str, roster: Sequence[str] = ()) -> str:
    """One name as it is asked. Only an ambiguous name is shown with the book's first other characters: beside
    Western names the model called "Chiaki" Western, beside Japanese ones it called "Minho" Japanese (TEST_REPORT)."""
    others = [other for other in roster if other != name][:ROSTER_SHOWN] if ambiguous(name) else []
    return f"{name} (cùng truyện: {', '.join(others)})" if others else name


def name_payload(model: str, digest: str, batch: Sequence[str], roster: Sequence[str] = ()) -> dict[str, Any]:
    """The request for one batch of roster names; `roster`: the book's names, main characters first."""
    keys = [str(number) for number in range(1, len(batch) + 1)]
    item = {"type": "string", "enum": list(ORIGINS)}
    worked = {str(number): origin for number, (_, _, origin) in enumerate(NAME_SHOTS, 1)}
    messages = [{"role": "system", "content": NAME_SYSTEM},
                {"role": "user", "content": _numbered(name_item(name, others) for name, others, _ in NAME_SHOTS)},
                {"role": "assistant", "content": json.dumps(worked, ensure_ascii=False)},
                {"role": "user", "content": _numbered(name_item(name, roster) for name in batch)}]
    return _body(model, digest, messages, {"type": "object", "properties": {key: item for key in keys}, "required": keys},
                 8 * len(batch) + 40)


def _answers(content: str, count: int) -> list[Any]:
    try:
        got = json.loads(content)
    except (TypeError, ValueError):
        got = None
    if not isinstance(got, dict):
        return [None] * count
    return [got.get(str(number)) for number in range(1, count + 1)]


def parse(content: str, count: int) -> list[bool | None]:
    """Vietnamese? for each of `count` occurrences; None where the model gave no usable answer. Only "a Vietnamese word"
    is Vietnamese: "a Vietnamese name" for one occurrence was wrong too often (An Jaehyun, Sun-woo Bin) - names are
    settled by the roster question."""
    out: list[bool | None] = []
    for answer in _answers(content, count):
        kind = answer.get("loai") if isinstance(answer, dict) else None
        out.append(kind == VIETNAMESE_KIND if kind in KINDS else None)
    return out


def parse_names(content: str, count: int) -> list[str | None]:
    return [answer if answer in ORIGINS else None for answer in _answers(content, count)]


def _post(base_url: str, body: dict[str, Any], session: Any, timeout: float, options: dict[str, Any] | None) -> str:
    if session is None:
        import requests

        session = requests
    if options:
        body["options"].update(options)
    reply = session.post(f"{base_url.rstrip('/')}/api/chat", json=body, timeout=timeout)
    reply.raise_for_status()
    return str((reply.json().get("message") or {}).get("content") or "")


def ask(base_url: str, model: str, digest: str, batch: Sequence[Doubt], *, session: Any = None, timeout: float = 300.0,
        options: dict[str, Any] | None = None) -> list[bool | None]:
    """One request for one batch of occurrences. Ollama failing raises (the pass stops and keeps what it has)."""
    return parse(_post(base_url, payload(model, digest, batch), session, timeout, options), len(batch))


def ask_names(base_url: str, model: str, digest: str, batch: Sequence[str], roster: Sequence[str] = (), *, session: Any = None,
              timeout: float = 300.0, options: dict[str, Any] | None = None) -> list[str | None]:
    """One request for one batch of roster names."""
    return parse_names(_post(base_url, name_payload(model, digest, batch, roster), session, timeout, options), len(batch))


def model_digest(base_url: str, model: str = MODEL) -> str | None:
    """The digest Ollama reports for `model`, None when it is not installed or Ollama does not answer."""
    import requests

    try:
        reply = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        reply.raise_for_status()
        models = reply.json().get("models") or []
    except (OSError, ValueError, AttributeError):
        return None
    names = {model, f"{model}:latest"}
    for entry in models:
        if isinstance(entry, dict) and names & {entry.get("name"), entry.get("model")}:
            return str(entry.get("digest") or "") or None
    return None


# ---- which occurrences are in doubt ---------------------------------------------------------------------------------------

def doubts(shown: str, spoken: str, source: str | None = None) -> list[Doubt]:
    """The occurrences of one stretch of text that tier 1 is unsure of AND sea-g2p reads English (only those can change).

    `spoken` is what the voice is given (after the text layer), `shown` what the reader sees - the model reads `shown`.
    The two are aligned by the order of the table's words; where the text layer moved one, the stretch is skipped.
    """
    from . import vieneu_engine as ve
    from .phoneme_policy import (_TOKEN, _listed_spans, _shared, capitalised, english_read, shared_word_contexts,
                                 shared_word_verdicts)

    from sea_g2p import punc_norm

    chunk = punc_norm(ve.normalize([spoken]))
    if not chunk.strip() or not _shared().find.search(chunk):
        return []
    capitals = capitalised(spoken, source or shown)
    verdicts = shared_word_verdicts(chunk, capitals)
    if all(sure for _, _, sure, _ in verdicts):
        return []
    pipeline = ve._sea()
    given = ve.keep_lone_o(chunk, pipeline.normalizer.normalize(chunk, punc_norm=True))
    english = english_read(given, pipeline.g2p.convert(given), pipeline.g2p.convert)
    if english is None or len(english) != len(verdicts) or [word for *_, word in _listed_spans(given)] != [word for word, *_ in verdicts]:
        return []
    listed = _shared().listed
    tokens = shown.split()
    places = []  # (token index, start, end) of every table word of the shown text, in order
    for index, token in enumerate(tokens):
        for match in _TOKEN.finditer(token):
            if match.group(2) and match.group(2).lower() in listed:
                places.append((index, *match.span()))
    if [tokens[index][start:end].lower() for index, start, end in places] != [word for word, *_ in verdicts]:
        return []
    keys = shared_word_contexts(chunk)
    return [Doubt(keys[position], word, marked(tokens, *places[position]), word in capitals)
            for position, (word, _, sure, _) in enumerate(verdicts) if not sure and english[position]]


# ---- the roster ------------------------------------------------------------------------------------------------------------

def _latin(word: str) -> bool:
    return len(word) > 1 and word.isascii() and word.replace("-", "").isalpha()


def roster_names(display_names: Iterable[str]) -> list[str]:
    """The roster as names a reader would write: the analysis keeps speakers in capitals ("KUCHINASHI"), the model knows
    "Kuchinashi". Order kept, duplicates and labels with no letter dropped."""
    out: list[str] = []
    for raw in display_names:
        name = " ".join("-".join(part.capitalize() for part in word.split("-")) if word.isupper() else word for word in str(raw).split())
        if name and any(char.isalpha() for char in name) and name not in out:
            out.append(name)
    return out


def asked_names(roster: Sequence[str]) -> list[str]:
    """Roster names whose origin changes how they are read: every word in plain Latin letters (a name written with
    Vietnamese diacritics is Vietnamese already, a label like "người gọi Lucy" is not a name)."""
    return [name for name in roster if all(_latin(word) for word in name.split())][:NAME_LIMIT]


def word_origins(origins: dict[str, str]) -> dict[str, str]:
    """Origin per single word of the names asked, where every name that holds the word agrees ("An" of "An An" and
    of "An Jaehyun" stays undecided)."""
    seen: dict[str, set[str]] = {}
    for name, origin in origins.items():
        for word in name.split():
            if _latin(word):
                seen.setdefault(word, set()).add(origin)
    return {word: next(iter(found)) for word, found in seen.items() if len(found) == 1}


def vietnamese_names(origins: dict[str, str]) -> list[str]:
    """Table words the roster uses as a Vietnamese name, lower-case (`Rulings.names`)."""
    from .phoneme_policy import _shared

    listed = _shared().listed
    return sorted({word.lower() for word, origin in word_origins(origins).items() if origin == "vi" and word.lower() in listed})


def foreign_names(origins: dict[str, str]) -> list[str]:
    """Words of the roster's names of the "en" origin ("Dan", "Tom" of a Western character) that are spelled like a
    Vietnamese syllable, lower-case (`Rulings.foreign`): sea-g2p reads such a word as that syllable wherever it
    stands, table word or not, so the book has to say it is a name (`phoneme_policy.foreign_names`)."""
    from ..analysis import is_vietnamese_syllable

    return sorted({word.lower() for word, origin in word_origins(origins).items()
                   if origin == "en" and word.isascii() and is_vietnamese_syllable(word.lower())})


def name_readings(origins: dict[str, str], book_origin: str | None) -> dict[str, str]:
    """{name word: what to say} where the name's own origin reads it differently from the book's origin: a Japanese or
    Korean name by its own romanization ("Chiaki" in a book of no origin, "Jieun" in a Japanese book), a Vietnamese
    name as written where the book's origin would have romanized it. "Other" changes nothing: the model answers it
    for one Japanese name in five ("Yukinoshita", "Yokohama"), and the book's own rules already keep "Alice" as written.
    Same shape as a book's `readings`."""
    from . import names

    out: dict[str, str] = {}
    for word, origin in sorted(word_origins(origins).items()):
        by_book = names.name_reading(word, book_origin)
        if origin in names.ORIGINS:
            reading = names.name_reading(word, origin)
            if reading and reading != by_book:
                out[word] = reading.replace("_", "")
        elif origin == "vi" and by_book:
            out[word] = word
    return out


# ---- the project's file ------------------------------------------------------------------------------------------------------

def valid(value: Any) -> bool:
    """The shape `rulings_of` and `.abook` readers rely on (also the `sharedWords` entry of `book.json`)."""
    return (isinstance(value, dict) and value.get("version") == VERSION
            and isinstance(value.get("contexts"), dict)
            and all(isinstance(key, str) and answer in ("v", "e") for key, answer in value["contexts"].items())
            and isinstance(value.get("names"), list) and all(isinstance(name, str) for name in value["names"])
            and isinstance(value.get("foreign"), list) and all(isinstance(name, str) for name in value["foreign"])
            and isinstance(value.get("readings"), dict)
            and all(isinstance(key, str) and isinstance(said, str) for key, said in value["readings"].items()))


def read(path: Path | str) -> dict[str, Any] | None:
    """The stored rulings when the file is this version's, else None."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if valid(value) else None


def rulings_of(value: dict[str, Any] | None) -> Rulings | None:
    if not value:
        return None
    contexts = {key: answer == "v" for key, answer in value["contexts"].items()}
    return Rulings(contexts, set(value["names"]), set(value["foreign"])) if contexts or value["names"] or value["foreign"] else None


def load(project_root: Path | str) -> Rulings | None:
    """The book's rulings, None when it has none (tier 1 alone)."""
    return rulings_of(read(Path(project_root) / FILE))


def shared(value: dict[str, Any]) -> dict[str, Any]:
    """What travels in the `.abook` (`book.json` `sharedWords`): the answers only, not which model gave them."""
    return {"version": VERSION, "contexts": value["contexts"], "names": value["names"], "foreign": value["foreign"], "readings": value["readings"]}


def tag(text: str, rulings: Rulings | None) -> str:
    """Mark for a clip cache key: "" when no ruling of the book touches `text` (the key is as before), else "w" + 16 hex
    digits of the rulings that do - a new ruling re-reads only the passages it changes."""
    if not rulings:
        return ""
    from . import vieneu_engine as ve
    from .phoneme_policy import _listed_spans, shared_word_contexts

    from sea_g2p import punc_norm

    chunk = punc_norm(ve.normalize([text]))
    found = sorted({(key, rulings.contexts[key]) for key in shared_word_contexts(chunk) if key in rulings.contexts})
    named = sorted({word for *_, word in _listed_spans(chunk) if word in rulings.names})
    foreign = sorted(set(re.findall("[a-z]+", chunk)) & rulings.foreign)
    if not found and not named and not foreign:
        return ""
    lines = [f"{key}\t{int(answer)}" for key, answer in found] + [f"name\t{word}" for word in named] + [f"foreign\t{word}" for word in foreign]
    return "w" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def compute(project_root: Path | str, stretches: Iterable[tuple[str, str]], roster: Sequence[str], base_url: str, *,
            book_origin: str | None = None, model: str = MODEL,
            stop_requested: Callable[[], bool] = lambda: False, pause_requested: Callable[[], bool] = lambda: False,
            log: Callable[[str], None] = print, session: Any = None, options: dict[str, Any] | None = None) -> dict[str, int]:
    """Ask the model about every doubtful occurrence of `stretches` ((shown, spoken) pairs, in book order) and about
    the roster's names, and write the file.

    Answers already stored for the same model digest and prompt are kept, so a stopped pass resumes; the file is
    written after every batch. Returns counts: doubts, names, asked, failed, seconds.
    """
    from ..io_utils import atomic_write_json

    project_root = Path(project_root)
    digest = model_digest(base_url, model)
    if digest is None:
        raise RuntimeError(f"Ollama chưa có model {model}")
    old = read(project_root / FILE)
    same = bool(old) and old.get("digest") == digest and old.get("prompt") == PROMPT_VERSION and old.get("model") == model
    contexts: dict[str, str] = dict(old["contexts"]) if same else {}
    origins: dict[str, str] = dict(old.get("origins") or {}) if same else {}
    found: dict[str, Doubt] = {}
    for shown, spoken in stretches:
        for doubt in doubts(shown, spoken):
            found.setdefault(doubt.key, doubt)
    roster = roster_names(roster)
    named = asked_names(roster)
    todo = [doubt for doubt in found.values() if doubt.key not in contexts]
    todo_names = [name for name in named if name not in origins]
    asked = failed = 0
    started = time.monotonic()

    def save(complete: bool) -> None:
        kept = {key: contexts[key] for key in sorted(contexts) if key in found}
        kept_origins = {name: origins[name] for name in named if name in origins}
        atomic_write_json(project_root / FILE, {
            "version": VERSION, "prompt": PROMPT_VERSION, "model": model, "digest": digest, "complete": complete,
            "bookOrigin": book_origin, "origins": kept_origins, "names": vietnamese_names(kept_origins), "foreign": foreign_names(kept_origins),
            "readings": name_readings(kept_origins, book_origin), "contexts": kept})

    def counts() -> dict[str, int]:
        return {"doubts": len(found), "names": len(named), "asked": asked, "failed": failed, "seconds": round(time.monotonic() - started)}

    def halted() -> bool:
        while pause_requested() and not stop_requested():
            time.sleep(1.0)
        return stop_requested()

    for at in range(0, len(todo_names), BATCH):
        if halted():
            save(False)
            return counts()
        batch = todo_names[at:at + BATCH]
        answers = ask_names(base_url, model, digest, batch, roster, session=session, options=options)
        asked += len(batch)
        for name, origin in zip(batch, answers):
            if origin is None:
                failed += 1
            else:
                origins[name] = origin
        save(False)
    for at in range(0, len(todo), BATCH):
        if halted():
            save(False)
            return counts()
        batch = todo[at:at + BATCH]
        answers = ask(base_url, model, digest, batch, session=session, options=options)
        asked += len(batch)
        for doubt, answer in zip(batch, answers):
            if answer is None:
                failed += 1
            else:
                contexts[doubt.key] = "v" if answer else "e"
        save(False)
    save(True)
    log(f"Chữ trùng Việt / Anh và gốc tên: {len(found)} chỗ nghi ngờ, {len(named)} tên; hỏi {asked} ({failed} không trả lời được) "
        f"trong {time.monotonic() - started:.0f} giây")
    return counts()


def release(base_url: str, model: str = MODEL) -> None:
    """Unload the model (keep_alive 0). Failing to is harmless."""
    try:
        import requests

        requests.post(f"{base_url.rstrip('/')}/api/generate", json={"model": model, "keep_alive": 0}, timeout=20)
    except Exception:  # noqa: BLE001 - cleanup only
        pass
