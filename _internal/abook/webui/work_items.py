"""Hộp "Việc cần duyệt" của Studio (docs/STUDIO_REVIEW.md).

Dựng danh sách chỗ máy nghi ngờ từ SQLite của sách (mở chỉ đọc như mọi phần của webui), mỗi việc tự giải thích và xếp
theo LỢI TRÊN MỖI LẦN BẤM: `số câu bị ảnh hưởng x khả năng máy sai x độ chói tai`. Không việc nào chặn dây chuyền - máy
đã tự quyết và đang chạy tiếp. Sửa được ngay: cách đọc tên (bước 2) - giao diện ghi mong muốn vào `overrides.json`, dây
chuyền áp ở ranh giới an toàn (listener_overrides.py); việc đã áp thì biến khỏi danh sách.

Độ tin cậy do LLM tự báo KHÔNG dùng để xếp: đo trên Tập 18, câu thoại trung bình 0,91 và chỉ 14/1.157 câu dưới 0,8 - nó
quá tự tin. Các tín hiệu ở đây là tín hiệu có cấu trúc, kiểm được bằng mắt.
"""
from __future__ import annotations

import re
import json
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from .. import names as renames
from .. import narrator_sections
from ..listener_overrides import (
    NARRATOR, UNNAMED, pronunciation_requests, read_overrides, speaker_requests, surface_key, voice_requests,
)
from .. import speaker_logprobs
from . import narrator_cards, store
from .address_cues import address_doubts, split_doubts
from .humanize import shown_reading
from .reviews import review_items
from .reviews import speaker_label as _speaker_label

# Độ chói tai khi máy sai ở khía cạnh ấy (1 = người nghe nhận ra ngay: giọng sai người, sai giới).
SEVERITY = {
    "speaker": 1.0,
    "gender": 1.0,
    "vocative": 0.9,
    "turn": 1.0,
    "alias": 0.8,
    "bracket": 1.0,  # sai người nói ở cả một nhóm câu - như thẻ "Ai nói câu này"
    "shared-voice": 0.6,
    "pronunciation": 0.5,
    "unnamed": 0.3,
    "audio": 0.9,
    "narrator": 0.9,  # đoạn kể bởi người khác mà máy cứ gán lời họ cho "tôi": sai người ở cả một đoạn
}
EXAMPLES = 3
# Thẻ "gọi tên chính người nói": tối đa ngần này người nói quanh câu làm ứng viên đầu tiên.
NEARBY_CHOICES = 4
# Thẻ "Ai nói câu này" theo logprob (speaker_logprobs.py): câu mà token đầu của tên người nói có p_first dưới ngưỡng là câu
# đáng ngờ (19 chương cổng 09-10: duyệt 20% câu p_first thấp nhất -> 54% câu duyệt là câu sai, đúng chặt 75,4 -> 86,2), và chỉ hỏi
# tối đa ngần này phần số câu thoại có số đo của sách.
LOGPROB_DOUBT = 0.8
LOGPROB_SHARE = 0.20
# Thẻ "Lượt đối đáp" gộp một chuỗi câu liền nhau cùng người thành một thẻ, tối đa ngần này câu. Số CHẴN: khúc sau bắt đầu
# đúng nhịp xen kẽ của khúc trước (câu thứ 9 là câu giữ nguyên, như câu 1, 3...).
TURN_CHAIN_MAX = 8
# Thẻ biệt danh (3a): số lần sách viết danh hiệu SÁT tên (cách một dấu cách, hay "được mệnh danh/gọi là") mới hỏi.
EPITHET_EVIDENCE = 3
EPITHET_LINKS = ("được mệnh danh là", "được mệnh danh", "được gọi là", "được biết đến là")
_BOOK_TEXT: dict[tuple, str] = {}  # văn bản sách đã bỏ dấu, theo (file, mtime, cỡ) - chỉ giữ cuốn gần nhất
LEADING = re.compile(r"^[\s\-–—“”\"'‘’«»]+")


def _is_named(speaker: str) -> bool:
    """Người có tên thật: không phải người kể, nhãn dành riêng ("UNKNOWN" = vai phụ không tên) hay vai phụ cục bộ."""
    from ..character_registry import RESERVED_SPEAKERS  # nặng: chỉ nạp khi dựng hộp việc

    return (bool(speaker) and speaker.casefold() not in RESERVED_SPEAKERS and not speaker.startswith("NPC_LOCAL")
            and not speaker.upper().startswith("ANONYMOUS"))


def _mid(label: str) -> str:
    """Nhãn "Vai phụ không tên"/"Người kể" đứng GIỮA câu thì viết thường chữ đầu ("…của vai phụ không tên")."""
    return label[:1].lower() + label[1:] if label in ("Vai phụ không tên", "Người kể") else label


def _has_audio(row: Any, project_root: Path | None) -> bool:
    """Câu này nghe được không - đúng điều nút ▶ cần (`/media/books/ID/samples/N` trả 404 khi file không có). Hàng không có
    cột `wav_path` là chưa thu."""
    if "wav_path" not in row.keys() or not row["wav_path"]:
        return False
    return project_root is None or store.segment_audio(project_root, row["wav_path"]) is not None


def _example(row: Any, names: dict[int, dict[str, Any]], label: Callable[[str], str] = _speaker_label,
             project_root: Path | None = None) -> dict[str, Any]:
    chapter = names.get(int(row["chapter_id"]), {})
    return {
        "segmentId": int(row["id"]),
        "chapterId": int(row["chapter_id"]),
        "chapterTitle": chapter.get("full") or chapter.get("title") or "",
        "seq": int(row["seq"]),
        "text": str(row["text"]),
        "speaker": label(str(row["speaker"])),
        # Chỉ câu đã có bản thu (file còn nằm trong thư mục sách) mới nghe được; câu chưa thu vẫn là ví dụ ngữ cảnh.
        "hasAudio": _has_audio(row, project_root),
    }


def _cast_choices(spoken: list[Any], chapter_ids: set[int], leave_out: set[str],
                  label: Callable[[str], str] = _speaker_label) -> list[dict[str, str]]:
    """Người có tên nói nhiều nhất trong những chương ấy - ứng viên hợp lý nhất khi máy không có ý kiến riêng."""
    counts: dict[str, int] = defaultdict(int)
    for row in spoken:
        speaker = str(row["speaker"])
        if int(row["chapter_id"]) in chapter_ids and _is_named(speaker) and speaker.casefold() not in leave_out:
            counts[speaker] += 1
    ranked = sorted(counts, key=lambda speaker: (-counts[speaker], speaker.casefold()))[:4]
    return [{"label": label(speaker), "value": speaker} for speaker in ranked]


def _speaker_fix(rows: list[Any], choices: list[dict[str, str]], current: str,
                 wishes: dict[str, dict[str, str]], label: Callable[[str], str] = _speaker_label) -> dict[str, Any] | None:
    """Phần "sửa được" của một thẻ gán người nói cho một nhóm câu, hoặc None khi người nghe đã quyết GIỮ cả nhóm.

    Mỗi câu mang mã ổn định + băm chữ, để yêu cầu không bao giờ áp nhầm câu đã đổi chữ. Nhóm đang chờ áp một người thì
    thẻ nói "đang chờ"."""
    asked = [wishes.get(str(row["stable_id"])) for row in rows]
    if all(wish is not None and wish["speaker"].casefold() == current.casefold() for wish in asked):
        return None
    pending = {wish["speaker"] for wish in asked if wish is not None}
    return {
        "lines": [{"stableId": str(row["stable_id"]), "textSha256": str(row["text_sha256"] or "")} for row in rows],
        "choices": [choice for choice in {choice["value"]: choice for choice in choices}.values()
                    if choice["value"].casefold() != current.casefold()],
        "currentValue": current,
        "requested": label(next(iter(pending))) if len(pending) == 1 and None not in asked else None,
    }


def _undo_of(item: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any] | None:
    """Cách rút lại quyết định đã ghi của một thẻ ("Đã quyết, chờ áp dụng" có nút Hoàn tác cho TỪNG mục, không chỉ toast vài
    giây): đúng thân yêu cầu `withdraw` mà thông báo hoàn tác đã gửi - `endpoint` + từng `decisions[i]` kèm `requestedAt` của lần
    bấm ấy. Thẻ gộp tên / quy ước 『』 còn ghi ở cấp tên cho các phần sau - hoàn tác chỉ lùi được phần câu nên không mời."""
    if not item.get("requested") or item["kind"] in ("alias", "bracket"):
        return None
    if item["kind"] == "narrator":
        section = item["narratorSection"]
        return {"endpoint": "narrator-section", "decisions": [
            {"chapterIndex": section["chapterIndex"], "fromSeq": section["fromSeq"], "toSeq": section["toSeq"]}]}

    def stamp(section: str, key: str) -> float | None:
        entry = (overrides.get(section) or {}).get(key)
        try:
            return float(entry["requested_at"]) if isinstance(entry, dict) else None
        except (KeyError, TypeError, ValueError):
            return None

    if item["kind"] == "pronunciation" and item.get("surface"):
        at = stamp("pronunciations", surface_key(str(item["surface"])))
        keep = item["requested"] == item["current"]
        return {"endpoint": "pronunciation", "decisions": [
            {"surface": item["surface"], "requestedAt": at, "previous": item["current"], "keep": keep}]} if at else None
    if item.get("voiceChoices"):
        decisions = []
        for character in item.get("keepCharacters") or []:
            entry = (overrides.get("voices") or {}).get(character)
            at = stamp("voices", character)
            # Thẻ chung giọng: chỉ người đã bị đổi giọng (có `avoid`) là phần của quyết định này.
            if at and (item["kind"] == "gender" or (isinstance(entry, dict) and entry.get("avoid"))):
                decisions.append({"character": character, "requestedAt": at, "keep": False})
        return {"endpoint": "voice", "decisions": decisions} if decisions else None
    if item.get("lines"):
        clicks: dict[float, list[dict[str, str]]] = defaultdict(list)
        for line in item["lines"]:
            at = stamp("speakers", line["stableId"])
            if at:
                clicks[at].append(line)
        # Một lần bấm có thể ghi nhiều câu cùng mốc (thẻ vai phụ cả cuốn) - mỗi mốc một quyết định.
        return {"endpoint": "speaker", "decisions": [{"lines": lines, "requestedAt": at} for at, lines in clicks.items()]} if clicks else None
    return None


def _character_key(name: str) -> str:
    """Khoá tên chuẩn như `character_registry.canonical_key` - cùng khoá mục `voices` của overrides.json."""
    return " ".join(str(name).strip().casefold().split()).upper()


def _voice_gender(rows: list[Any], profiles: dict[int, Any]) -> str:
    """Giới của giọng mà các câu này đang được đọc bằng (giới của preset), hay "" khi không biết."""
    from ..voice_catalog import preset_by_name

    for row in rows:
        profile = profiles.get(int(row["voice_profile_id"])) if row["voice_profile_id"] is not None else None
        if profile is None or not profile["preset_name"]:
            continue
        try:
            return str(preset_by_name(str(profile["preset_name"]))["gender"])
        except ValueError:
            return ""
    return ""


def _tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[\s\-]+", name.upper()) if token]


# Ngoặc kép và ngoặc CJK; bỏ ngoặc đơn vì dấu ’ cuối câu có thể là dấu lược.
QUOTE_OPENERS = ("\"", "“", "『", "「", "«")
QUOTE_CLOSERS = ("\"", "”", "』", "」", "»")


def _folded_book(chapter_paths: list[str]) -> str:
    """Cả cuốn (mọi .txt cùng thư mục với các chương, như character_registry._source_text), bỏ dấu, hạ chữ - giữ lại giữa
    các lần mở hộp "Việc cần duyệt" (bỏ dấu cả cuốn mất vài giây)."""
    from ..character_registry import fold_for_source_search

    folders = sorted({Path(path).parent for path in chapter_paths if path and Path(path).parent.is_dir()})
    files = [path for folder in folders for path in sorted(folder.glob("*.txt"))]
    key = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files)
    if key not in _BOOK_TEXT:
        _BOOK_TEXT.clear()
        _BOOK_TEXT[key] = fold_for_source_search(
            "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files))
    return _BOOK_TEXT[key]


def _word_positions(needle: str, text: str) -> list[int]:
    """Chỗ bắt đầu của `needle` NGUYÊN CHỮ trong `text` (cả hai đã bỏ dấu, hạ chữ)."""
    found, start = [], 0
    while needle:
        index = text.find(needle, start)
        if index < 0:
            return found
        end = index + len(needle)
        if (index == 0 or not text[index - 1].isalnum()) and (end == len(text) or not text[end].isalnum()):
            found.append(index)
        start = index + 1
    return found


def epithet_links(labels: list[str], folded_book: str) -> dict[tuple[str, str], int]:
    """{(danh hiệu, tên): số lần sách viết chúng SÁT nhau}: "Thiên Biến Vạn Hóa Krai", "Krai Thiên Biến Vạn Hóa",
    "Krai được mệnh danh Thiên Biến Vạn Hóa". Tên được so cả chữ đầu và chữ cuối ("Krai" của "Krai Andrey"). Dấu phẩy KHÔNG
    tính: "Tino, Krai" hay "Lapis, Kris" là danh sách hai người (đo trên kho Nageki 29-09: cặp đúng 5 lần sát nhau, hai cặp
    sai 0 lần sát, 9 và 5 lần cách dấu phẩy). Nhãn này nằm trong nhãn kia thì bỏ - thẻ "một người hai tên" lo."""
    from ..character_registry import fold_for_source_search

    folded = {label: fold_for_source_search(label).strip() for label in labels}
    joins = [fold_for_source_search(link) for link in EPITHET_LINKS]  # cùng phép gấp với văn bản ("được" -> "đuoc")
    forms: dict[str, set[str]] = {}
    for label, text in folded.items():
        words = text.split()
        forms[label] = {text} | ({word for word in (words[0], words[-1]) if len(word) >= 3} if len(words) > 1 else set())
    words = {label: set(text.split()) for label, text in folded.items()}
    # Chỉ mục "dạng tên -> những nhãn có dạng ấy", và các độ dài dạng tên: mỗi chỗ danh hiệu xuất hiện chỉ cần thử vài
    # độ dài, không phải từng tên x từng dạng tên (soát UX 29-09: phép thử cũ chiếm ~90% thời gian mở hộp "Việc cần duyệt",
    # 3-5 giây với sách 43 chương). Cùng điều kiện như trước: sau danh hiệu là " <tên>" rồi ký tự không phải chữ/số; trước
    # danh hiệu là "<tên> " mà trước tên không phải chữ/số; hoặc "<tên> <từ nối> " (không xét ranh giới, như trước).
    owners: dict[str, set[str]] = defaultdict(set)
    for label, label_forms in forms.items():
        for form in label_forms:
            owners[form].add(label)
    lengths = sorted({len(form) for form in owners})
    links: dict[tuple[str, str], int] = {}
    for epithet, text in folded.items():
        if not text:
            continue
        positions = _word_positions(text, folded_book)
        if not positions:
            continue
        counts: Counter = Counter()
        for index in positions:
            before = folded_book[max(0, index - 40):index]
            after = folded_book[index + len(text):index + len(text) + 40]
            heads = [before[:-len(link) - 2] for link in joins if before.endswith(f" {link} ")]
            found: set[str] = set()
            for size in lengths:
                if after.startswith(" ") and len(after) > size and after[1:size + 1] in owners \
                        and not after[size + 1:size + 2].isalnum():
                    found |= owners[after[1:size + 1]]
                if before.endswith(" ") and len(before) > size and before[-size - 1:-1] in owners \
                        and not before[-size - 2:-size - 1].isalnum():
                    found |= owners[before[-size - 1:-1]]
                for head in heads:
                    if len(head) >= size and head[-size:] in owners:
                        found |= owners[head[-size:]]
            counts.update(found)
        for name, count in counts.items():
            other = folded[name]
            if name == epithet or not other or text in other or other in text or words[epithet] & words[name]:
                continue
            links[(epithet, name)] = count
    return links


def merged_turns(connection: Any, chapter_id: int | None = None) -> list[tuple[Any, Any]]:
    """Cặp câu thoại liền kề ở hai đoạn văn liền nhau - câu trước đóng ngoặc, câu sau mở ngoặc mới, đoạn sau chỉ có thoại
    (không lời dẫn riêng) - mà mang CÙNG một người có tên. Project cũ không có số đoạn văn thì không tìm."""
    if "paragraph_index" not in {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}:
        return []
    where, parameters = (" WHERE chapter_id = ?", (chapter_id,)) if chapter_id is not None else ("", ())
    rows = [
        row for row in connection.execute(
            "SELECT id, stable_id, chapter_id, seq, paragraph_index, text, text_sha256, speaker, kind FROM segments"
            + where + " ORDER BY chapter_id, seq",
            parameters,
        )
        if row["paragraph_index"] is not None
    ]
    # Đoạn văn có lời kể hay nội tâm thì câu thoại trong đó có lời dẫn riêng - máy có căn cứ, không nghi.
    narrated = {(int(row["chapter_id"]), int(row["paragraph_index"])) for row in rows if row["kind"] != "dialogue"}
    pairs = []
    for first, second in zip(rows, rows[1:]):
        if first["kind"] != "dialogue" or second["kind"] != "dialogue":
            continue
        if int(first["chapter_id"]) != int(second["chapter_id"]) or int(second["seq"]) != int(first["seq"]) + 1:
            continue
        if int(second["paragraph_index"]) != int(first["paragraph_index"]) + 1:
            continue
        if (int(second["chapter_id"]), int(second["paragraph_index"])) in narrated:
            continue
        if not str(first["text"]).rstrip().endswith(QUOTE_CLOSERS):
            continue
        if not str(second["text"]).lstrip().startswith(QUOTE_OPENERS):
            continue
        speaker = str(second["speaker"])
        if _is_named(speaker) and str(first["speaker"]).casefold() == speaker.casefold():
            pairs.append((first, second))
    return pairs


def confident_doubts(project_root: Path, by_stable: dict[str, Any]) -> list[tuple[Any, dict[str, Any], float]]:
    """(câu, ý kiến, độ chắc) cho mỗi câu mà bộ chấm ứng viên (doubt.json, scripts/model_eval/quote_scorer/doubt_for_book.py)
    CHẮC từ 0,5 trở lên là của một người KHÁC nhãn LLM đang dùng. Câu đổi nhãn sau lần chấm, hay bộ chấm đồng ý: bỏ."""
    path = project_root / "doubt.json"
    if not path.is_file():
        return []
    try:
        doubts = json.loads(path.read_text(encoding="utf-8")).get("segments", {})
    except (OSError, ValueError, AttributeError):
        return []
    found = []
    for stable_id, doubt in doubts.items():
        row = by_stable.get(stable_id)
        if row is None or str(row["speaker"]) != doubt.get("llm") or not doubt.get("disagree"):
            continue
        certainty = float(doubt.get("certainty") or 0)
        if certainty >= 0.5:
            found.append((row, doubt, certainty))
    return found


def role_key(speaker: str) -> str:
    """Nhãn vai của một vai phụ cục bộ ("NPC_LOCAL::c00006::r0b2…::Lính gác 1" -> "lính gác 1"), hạ chữ, gộp dấu cách;
    "" với mọi người nói khác."""
    if not speaker.startswith("NPC_LOCAL"):
        return ""
    return " ".join(speaker.rsplit("::", 1)[-1].casefold().split())


def minor_role_groups(lines_by_speaker: dict[str, list[Any]], decided: set[str]) -> dict[str, dict[str, list[Any]]]:
    """{nhãn vai: {vai cục bộ: các câu CHƯA quyết}} cho mỗi nhãn mà máy chia thành từ hai vai cục bộ trở lên trong cuốn.

    Máy đặt mỗi vai phụ không tên trong phạm vi một chương/cảnh, nên "lính gác 1" ở bốn chương là bốn vai, bốn giọng. Nhãn
    vai là thứ duy nhất sổ có chung giữa các chỗ ấy: không có cột người nghe ("nói với X"), còn "UNKNOWN" không mang nhãn
    nào. Câu đã có quyết định của người nghe (`decided`, mã câu) ra khỏi nhóm - thẻ của vai ấy nói chuyện đã quyết."""
    groups: dict[str, dict[str, list[Any]]] = defaultdict(dict)
    for speaker, rows in lines_by_speaker.items():
        key = role_key(speaker)
        open_rows = [row for row in rows if str(row["stable_id"]) not in decided]
        if key and open_rows:
            groups[key][speaker] = open_rows
    return {key: members for key, members in groups.items() if len(members) > 1}


def self_addressed(connection: Any, chapter_id: int | None = None) -> dict[int, list[str]]:
    """segments.id -> những người có tên nói quanh câu (gần nhất trước), cho câu thoại gán cho người mà chính câu ấy GỌI
    ("Lucien, ..." / "..., Satomi-san." / "Karin-nim"): không ai gọi tên chính mình - gần như chắc sai (100% theo đáp án,
    `first_person.addressed_names`). Luật tự sửa của dây chuyền (`_repair_dialogue_turns_by_address`) chỉ sửa khi chắc; câu
    nó để nguyên rơi vào đây, nên hộp việc hỏi đúng những câu ấy. Tính lúc xem từ SQLite - không có dấu nào lưu. Người
    nói KHÔNG bị đổi. `chapter_id`: chỉ xét câu của chương ấy (người có tên và cách gọi vẫn tính trên cả cuốn)."""
    from ..character_registry import self_addressed as registry_self_addressed  # nặng: chỉ nạp khi dựng hộp việc

    tables = store._table_names(connection)
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
    if "canonical_character_id" not in columns or "characters" not in tables:
        return {}
    rows = connection.execute(
        "SELECT id, chapter_id, seq, text, speaker, kind, canonical_character_id FROM segments"
        " WHERE kind != 'narration' ORDER BY chapter_id, seq"
    ).fetchall()
    found: dict[int, set[str]] = defaultdict(set)
    for row in connection.execute("SELECT id, display_name FROM characters"):
        found[int(row[0])].add(str(row[1] or ""))
    if "character_aliases" in tables:
        for row in connection.execute("SELECT character_id, alias FROM character_aliases"):
            found[int(row[0])].add(str(row[1] or ""))
    aliases = {
        str(row["speaker"]): found.get(int(row["canonical_character_id"] or 0), set()) - {""}
        for row in rows
    }
    return registry_self_addressed(rows, aliases, lambda row: chapter_id is None or int(row["chapter_id"]) == chapter_id)


def work_items(project_root: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    renamed = renames.load(project_root)

    def speaker_label(raw: str) -> str:
        """Tên người nói như Studio đang hiện: tên người nghe đã "Đổi tên" (tab Nhân vật) thay tên gốc. Khoá (`value`,
        `character`) giữ nguyên - chỉ chữ trên thẻ đổi."""
        return renamed.get(renames.name_key(str(raw))) or _speaker_label(raw)

    with closing(store.connect(project_root)) as connection:
        names = store.chapter_names(connection, project_root)
        # Văn bản sách cho thẻ biệt danh (3a); sổ tối thiểu của test không có cột này.
        chapter_paths = [
            str(row[0] or "") for row in connection.execute("SELECT input_path FROM chapters")
        ] if "input_path" in {row[1] for row in connection.execute("PRAGMA table_info(chapters)")} else []
        has_wav_path = "wav_path" in {row[1] for row in connection.execute("PRAGMA table_info(segments)")}
        spoken = connection.execute(
            "SELECT id, stable_id, chapter_id, seq, text, text_sha256, speaker, kind, voice_profile_id, canonical_character_id"
            + (", wav_path" if has_wav_path else "") + " FROM segments"
            " WHERE kind != 'narration' ORDER BY chapter_id, seq"
        ).fetchall()
        characters = {
            int(row["id"]): row
            for row in connection.execute("SELECT id, canonical_name, display_name, gender, locked FROM characters")
        }
        # Số chương trong sách (first_person_chapters của settings khoá theo nó) - cho thẻ xưng hô (0b).
        chapter_index = {int(row[0]): int(row[1] or 0) for row in connection.execute("SELECT id, chapter_index FROM chapters")}
        # Giọng đang dùng của mỗi hồ sơ: khoá (để tránh khi tách hai người chung giọng) và giới của preset (thẻ giới nói
        # máy đang đọc bằng giọng nam hay nữ). Sổ giọng tối thiểu của test không có bảng này.
        profiles = {
            int(row["id"]): row
            for row in connection.execute("SELECT id, voice_key, preset_name FROM voice_profiles")
        } if "voice_profiles" in store._table_names(connection) else {}
        turns = merged_turns(connection)
        self_addressed_ids = self_addressed(connection)
        pronunciations = connection.execute(
            "SELECT surface, spoken_form, confidence, locked FROM pronunciations WHERE confidence < 0.9"
        ).fetchall() if "pronunciations" in store._table_names(connection) else []
        # Cách đọc một tên sai là sai ở MỌI câu có tên ấy: đếm số câu một lượt (phiên âm lưu theo từng từ - AGENTS.md),
        # và giữ vài câu làm ví dụ - ưu tiên câu đã thu, để người nghe nghe máy đang đọc tên ấy thế nào.
        word_segments: dict[str, int] = defaultdict(int)
        word_examples: dict[str, list[Any]] = defaultdict(list)
        if pronunciations:
            surfaces = {str(row["surface"]) for row in pronunciations}
            for row in connection.execute(
                "SELECT id, chapter_id, seq, text, speaker, wav_path FROM segments ORDER BY wav_path IS NULL, chapter_id, seq"
            ):
                for word in set(re.findall(r"\w+", str(row["text"]))):
                    word_segments[word] += 1
                    if word in surfaces and len(word_examples[word]) < EXAMPLES:
                        word_examples[word].append(row)
    lines_by_speaker: dict[str, list[Any]] = defaultdict(list)
    for row in spoken:
        lines_by_speaker[str(row["speaker"])].append(row)

    # 0. Ai nói câu này: bộ chấm ứng viên (doubt.json, scripts/model_eval/quote_scorer/doubt_for_book.py) CHẮC về một người
    #    có tên khác nhãn LLM. Đây là tín hiệu xếp hạng tốt nhất đã đo (review_curve.py: duyệt 20% câu theo nó 74,8 -> 84,6%,
    #    theo tin cậy LLM tự báo chỉ 79,7% = ngẫu nhiên). Bộ chấm không đổi nhãn nào - chỉ chỉ chỗ cho người nghe lại.
    overrides = read_overrides(project_root)
    speaker_wishes = {entry["stable_id"]: entry for entry in speaker_requests(overrides)}
    for row, doubt, certainty in confident_doubts(project_root, {str(row["stable_id"]): row for row in spoken}):
        stable_id = str(row["stable_id"])
        choice = speaker_label(str(doubt.get("choice") or ""))
        options = [speaker_label(str(name)) for name, _ in doubt.get("top", []) if name] + ["Người kể", "Vai phụ không tên"]
        # Lựa chọn bấm được: giá trị là khoá tên chuẩn (như doubt.json và sổ nhân vật), NARRATOR hay UNNAMED. Người nghe
        # đã chọn thì thẻ nói "đang chờ" tới khi dây chuyền áp; chọn giữ nguyên thì thẻ biến mất (đã có người quyết).
        choices = [{"label": speaker_label(str(name)), "value": str(name)} for name, _ in doubt.get("top", []) if name]
        choices += [{"label": "Người kể", "value": NARRATOR}, {"label": "Vai phụ không tên", "value": UNNAMED}]
        fix = _speaker_fix([row], choices, str(row["speaker"]), speaker_wishes, speaker_label)
        if fix is None:
            continue
        items.append({
            "kind": "speaker",
            "key": f"speaker:{stable_id}",
            "title": f"Ai nói câu này - {speaker_label(str(row['speaker']))} hay {choice}?",
            "problem": f"Máy đọc (LLM) gán cho {speaker_label(str(row['speaker']))}; bộ chấm thứ hai chắc"
                       f" {round(certainty * 100)}% là {choice}.",
            "affected": 1,
            "doubt": round(certainty, 3),
            "options": list(dict.fromkeys(options)),
            "current": speaker_label(str(row["speaker"])),
            "examples": [_example(row, names, speaker_label, project_root)],
            **fix,
        })

    # 0b. Ai nói câu này - theo XƯNG HÔ (address_cues.py): truyện kể ngôi thứ nhất, câu dính người kể "tôi" mà cách xưng
    #     hô ("ta… ngươi", "tớ… cậu") hợp người khác trong chương hơn hẳn. Đo 29-09 trên bộ LN: câu bị hỏi sai thật 85-95%.
    #     Câu đã có thẻ của bộ chấm thứ hai thì thôi (một câu một thẻ).
    voices_settings = store.read_settings(project_root).get("voices")
    voices_settings = voices_settings if isinstance(voices_settings, dict) else {}
    book_narrator = str(voices_settings.get("first_person_identity") or "").strip()
    chapter_narrators = voices_settings.get("first_person_chapters") if isinstance(voices_settings.get("first_person_chapters"), dict) else {}

    def narrator_of(chapter_id: int) -> str:
        index = str(chapter_index.get(chapter_id, ""))
        return str(chapter_narrators[index]).strip() if index in chapter_narrators else book_narrator

    # Người kể theo ĐOẠN người dùng đã nhận (narrator_sections.json): câu trong đoạn theo người kể của đoạn, không của chương.
    accepted_sections = narrator_sections.accepted(narrator_sections.load(project_root)) if (book_narrator or chapter_narrators) else {}

    def row_narrator(row: Any) -> str:
        found = narrator_sections.narrator_at(accepted_sections, int(chapter_index.get(int(row["chapter_id"]), 0)), int(row["seq"]))
        return narrator_of(int(row["chapter_id"])) if found is None else found

    by_section = row_narrator if accepted_sections else None
    asked = {item["key"] for item in items}
    for row, suggested, cue in address_doubts(spoken, narrator_of, by_section) if (book_narrator or chapter_narrators) else []:
        stable_id = str(row["stable_id"])
        if f"speaker:{stable_id}" in asked:
            continue
        current = str(row["speaker"])
        choices = [{"label": speaker_label(suggested), "value": suggested}]
        choices += _cast_choices(spoken, {int(row["chapter_id"])}, {current.casefold(), suggested.casefold()}, speaker_label)
        choices += [{"label": "Người kể", "value": NARRATOR}, {"label": "Vai phụ không tên", "value": UNNAMED}]
        fix = _speaker_fix([row], choices, current, speaker_wishes, speaker_label)
        if fix is None:
            continue
        words = ", ".join(f"“{word}”" for word in cue)
        items.append({
            "kind": "speaker",
            "key": f"speaker:{stable_id}",
            "title": f"Ai nói câu này - {speaker_label(current)} hay {speaker_label(suggested)}?",
            "problem": f"Cách xưng hô trong câu ({words}) giống cách {speaker_label(suggested)} nói ở chương này hơn cách"
                       f" {speaker_label(current)} nói.",
            "affected": 1,
            "doubt": 0.85,
            "options": list(dict.fromkeys([speaker_label(suggested), speaker_label(current), "Người kể", "Vai phụ không tên"])),
            "current": speaker_label(current),
            "examples": [_example(row, names, speaker_label, project_root)],
            **fix,
        })

    # 0c. Hai người chung một tên (address_cues.split_doubts): chương kể ngôi thứ nhất, câu thoại của MỘT nhãn chia hai
    #     giọng xưng hô không bao giờ đi chung câu, và một giọng lệch khỏi cách người ấy nói ở các chương khác - máy đã
    #     nhập một người lạ vào nhân vật có tên (29-09: 8B-v5 đọc bà thầy bói bằng giọng Lucia, 21/25 câu; model nào cũng
    #     nhập 32-55% câu người vô danh). Một thẻ cho cả nhóm; "Người khác…" đặt tên người lạ để có giọng riêng.
    asked = {item["key"] for item in items}
    for label, odd_rows, odd_words, usual_words, usual_count in (
        split_doubts(spoken, narrator_of, _is_named, by_section) if (book_narrator or chapter_narrators) else []
    ):
        odd_rows = [row for row in odd_rows if f"speaker:{row['stable_id']}" not in asked]
        if len(odd_rows) < 2:
            continue
        chapter_id = int(odd_rows[0]["chapter_id"])
        choices = [{"label": "Vai phụ không tên", "value": UNNAMED}]
        choices += _cast_choices(spoken, {chapter_id}, {label.casefold()}, speaker_label)
        choices += [{"label": "Người kể", "value": NARRATOR}]
        fix = _speaker_fix(odd_rows, choices, label, speaker_wishes, speaker_label)
        if fix is None:
            continue
        who = speaker_label(label)
        odd_list = ", ".join(f"“{word}”" for word in odd_words[:4])
        usual_list = ", ".join(f"“{word}”" for word in usual_words[:4])
        items.append({
            "kind": "speaker",
            "key": f"split:{chapter_id}:{_character_key(label)}",
            "title": f"{len(odd_rows)} câu của {who} ở chương này là của một người khác?",
            "problem": f"{who} nói theo hai kiểu xưng hô ở chương này - {odd_list} ({len(odd_rows)} câu) và {usual_list}"
                       f" ({usual_count} câu), không câu nào dùng cả hai - và kiểu {odd_list} khác cách {who} nói ở các chương"
                       f" khác. Thường là máy đã gán lời một người không tên cho {who}. “Người khác…” để đặt tên và giới"
                       f" (vd “bà thầy bói”, nữ) - người ấy được giọng riêng.",
            "affected": len(odd_rows),
            "doubt": 0.8,
            "options": list(dict.fromkeys(["Vai phụ không tên"] + [choice["label"] for choice in choices] + [who])),
            "current": who,
            "examples": [_example(row, names, speaker_label, project_root) for row in odd_rows[:EXAMPLES]],
            **fix,
        })

    # 0c2. Ai nói câu này - theo ĐỘ TIN logprob của chính model (speaker_logprobs.py, cờ ABOOK_SPEAKER_LOGPROBS): câu mà token
    #      đầu của tên người nói có xác suất thấp. Đo sớm trên 3 chương: AUROC ~0,77, duyệt 10% câu p_first thấp nhất thì 63% câu
    #      duyệt là câu sai. Chỉ hỏi câu mà nhãn hiện tại CÒN là nhãn model sinh (khác = dây chuyền hay người nghe đã đổi, số đo
    #      không còn nói về nhãn ấy) và câu chưa có thẻ nào ở trên (một câu một thẻ). Không có số đo = không thẻ.
    confidences = speaker_logprobs.read_confidences(project_root)
    measured = [
        (row, confidences[str(row["stable_id"])]) for row in spoken
        if row["kind"] in speaker_logprobs.SPOKEN_KINDS and str(row["stable_id"]) in confidences
    ]
    if measured:
        budget = int(len(measured) * LOGPROB_SHARE + 1e-9)
        carded = {str(line["stableId"]) for item in items for line in item.get("lines", [])}
        unsure = sorted(
            ((row, found) for row, found in measured
             if found["p_first"] < LOGPROB_DOUBT and str(row["stable_id"]) not in carded
             and renames.name_key(str(row["speaker"])) == renames.name_key(found["speaker"])),
            key=lambda pair: (pair[1]["p_first"], int(pair[0]["chapter_id"]), int(pair[0]["seq"])),
        )
        for row, found in unsure:
            if budget <= 0:
                break
            stable_id = str(row["stable_id"])
            current = str(row["speaker"])
            choices = _cast_choices(spoken, {int(row["chapter_id"])}, {current.casefold()}, speaker_label)
            choices += [{"label": "Người kể", "value": NARRATOR}, {"label": "Vai phụ không tên", "value": UNNAMED}]
            fix = _speaker_fix([row], choices, current, speaker_wishes, speaker_label)
            if fix is None:
                continue
            budget -= 1
            items.append({
                "kind": "speaker",
                "key": f"speaker:{stable_id}",
                "title": f"Ai nói câu này - {speaker_label(current)}?",
                "problem": f"Máy gán cho {speaker_label(current)} nhưng chỉ chắc khoảng {round(float(found['p_first']) * 100)}%.",
                "suggested": False,  # không có ứng viên nào được đề xuất: nút đầu không được tô như "máy đề xuất"
                "affected": 1,
                "doubt": round(1 - float(found["p_first"]), 3),
                "options": list(dict.fromkeys([speaker_label(current)] + [choice["label"] for choice in choices])),
                "current": speaker_label(current),
                "examples": [_example(row, names, speaker_label, project_root)],
                **fix,
            })

    # 0d. Người kể của ĐOẠN khác người kể "tôi" của sách (narrator_sections.py, ngưỡng đã đo ở b14err/P_RULE.md): model vẫn được
    #     dặn "người kể là X" nên gán thừa lời người khác cho X. Đề xuất có ngay sau khi chia câu, người dùng nhận lúc nào cũng
    #     được; lô đã phân tích rồi thì lựa chọn chỉ áp khi làm lại sách - thẻ nói rõ điều đó. Chưa trả lời = không áp.
    decisions = narrator_sections.load(project_root)
    for proposal in narrator_cards.proposals(project_root):
        chapter_id, first, last = proposal["chapter_id"], proposal["from_seq"], proposal["to_seq"]
        who = speaker_label(proposal["narrator"])
        decision = narrator_cards.decision_of(decisions, proposal["chapter_index"], first, last)
        total, done = narrator_cards.progress(project_root, chapter_id, first, last)
        with closing(store.connect(project_root)) as connection:
            shown = connection.execute(
                "SELECT * FROM segments WHERE chapter_id=? AND seq BETWEEN ? AND ? ORDER BY seq LIMIT ?",
                (chapter_id, first, last, EXAMPLES)).fetchall()
            section_texts = [str(row[0]) for row in connection.execute(
                "SELECT text FROM segments WHERE chapter_id=? AND seq BETWEEN ? AND ? ORDER BY seq", (chapter_id, first, last))]
        # "Chọn người kể…" gợi sẵn: tên riêng có mặt trong đoạn (sổ nhân vật có thể chưa có - đang phân tích), rồi người hay
        # nói trong chương; người kể của sách thì không (đó là câu hỏi đang hỏi).
        narrator_choices = [{"label": name, "value": name}
                            for name in narrator_cards.section_names(section_texts, {proposal["narrator"], who})]
        narrator_choices += [choice for choice in _cast_choices(spoken, {chapter_id}, {proposal["narrator"].casefold()}, speaker_label)
                             if choice["label"].casefold() not in {item["label"].casefold() for item in narrator_choices}]
        if decision is None:
            requested = None
        elif not decision["accepted"]:
            requested = "Giữ nguyên"
        else:
            requested = f"Người kể: {speaker_label(decision['narrator'])}" if decision["narrator"] else "Đổi người kể"
        chapter_name = names.get(chapter_id, {}).get("name") or f"Chương {proposal['chapter_index']}"
        if proposal["r1"] is not None and proposal["r1"] < 1:
            why = "Lời kể ở đây hầu như không có “tôi”, khác với phần còn lại của chương."
        else:
            why = f"Lời kể gọi tên {who} như nói về một người khác, và ít “tôi” hơn hẳn phần còn lại."
        items.append({
            "kind": "narrator",
            "key": f"narrator:{proposal['chapter_index']}:{first}:{last}",
            "title": f"{chapter_name}, {'câu ' + str(first) if first == last else f'câu {first}–{last}'}: có vẻ không phải {who} kể",
            "problem": f"{why} Nếu người kể ở đây là người khác, máy sẽ thôi gán lời họ cho {who}. Chưa trả lời thì máy giữ nguyên.",
            "affected": total,
            "doubt": 0.5,
            "options": ["Đúng, đổi người kể", "Không, giữ nguyên", "Chọn người kể…"],
            "current": who,
            "examples": [_example(row, names, speaker_label, project_root) for row in shown],
            "requested": requested,
            "narratorSection": {
                "chapterIndex": proposal["chapter_index"], "fromSeq": first, "toSeq": last, "narrator": who,
                "appliesNote": narrator_cards.applies_note(total, done),
                "choices": narrator_choices,
            },
        })

    # 1. Chưa rõ nam hay nữ mà có lời: giọng sai giới là lỗi người nghe nhận ra ngay. Bấm "Nam"/"Nữ" -> overrides.json
    #    `voices`; dây chuyền ghim giới và, nếu giọng đang dùng khác giới, chọn giọng mới như bước phân vai (mọi người khác
    #    giữ giọng) rồi thu lại câu của người ấy (ProjectDB.apply_listener_voice). "Để máy quyết" thì thôi hỏi.
    voice_wishes = {entry["character"]: entry for entry in voice_requests(overrides)}
    # Tên hiển thị trùng nhau (vai phụ cục bộ "Người Dân" ở 727, 728, 731 là ba người): thẻ của họ ghi thêm tên chương.
    shown_names = Counter(speaker_label(str(character["canonical_name"])) for character in characters.values())
    for character_id, character in characters.items():
        if character["gender"] not in ("unknown", "") or character["locked"]:
            continue
        # "UNKNOWN" là nhãn "vai phụ không tên", không phải một nhân vật - không hỏi giới của nó.
        if not _is_named(str(character["canonical_name"])):
            continue
        rows = [row for row in spoken if row["canonical_character_id"] == character_id]
        if not rows:
            continue
        key = _character_key(str(character["canonical_name"]))
        wish = voice_wishes.get(key)
        if wish is not None and not (wish["gender"] or wish["preset"]):
            continue
        heard = _voice_gender(rows, profiles)
        chapters_of = sorted({int(row["chapter_id"]) for row in rows})
        choices = []
        for gender, label in (("male", "Nam"), ("female", "Nữ")):
            choices.append({"label": label, "character": key, "gender": gender,
                            "done": f"{speaker_label(character['canonical_name'])} là {label.lower()}",
                            "note": "giữ giọng đang đọc" if heard == gender else f"đổi giọng, thu lại {len(rows)} câu"})
        items.append({
            "kind": "gender",
            "key": f"gender:{character['canonical_name']}",
            # Vai phụ cục bộ cùng tên ở nhiều chương là những người khác nhau ("Người Dân" ở 727, 728, 731): tên chương
            # trong tiêu đề để ba thẻ không trông như một thẻ lặp (soát UX 29-09) - chỉ khi tên hiển thị thật sự trùng.
            "title": f"{speaker_label(character['canonical_name'])} là nam hay nữ?"
                     + (f" · {names.get(chapters_of[0], {}).get('name', '')}"
                        if len(chapters_of) == 1 and shown_names[speaker_label(str(character["canonical_name"]))] > 1 else ""),
            "problem": "Truyện chưa cho máy đủ dấu hiệu về giới của nhân vật này; máy đang đọc bằng "
                       + {"male": "giọng nam.", "female": "giọng nữ."}.get(heard, "một giọng chưa rõ nam nữ."),
            "affected": len(rows),
            "doubt": 0.5,
            "options": ["Nam", "Nữ", "Để máy quyết"],
            # Cùng điều câu trên nói: giọng ĐANG ĐỌC (không phải "Chưa rõ" cạnh "máy đang đọc bằng giọng nam").
            "current": {"male": "Giọng nam", "female": "Giọng nữ"}.get(heard, "Chưa rõ"),
            "examples": [_example(row, names, speaker_label, project_root) for row in rows[:EXAMPLES]],
            "voiceChoices": choices,
            "keepCharacters": [key],
            "keepLabel": "Để máy quyết",
            # Tên người được hỏi: câu "Hoàn tác" nói cụ thể ai trở lại thế nào (soát UX 30-09).
            "subject": speaker_label(character["canonical_name"]),
            "requested": {"male": "Nam", "female": "Nữ"}.get(wish["gender"]) if wish is not None else None,
        })

    # 2. Người nói lại chính là người được GỌI ("Lucien, ..." / "..., Satomi-san." mà nhãn là LUCIEN/SATOMI): không ai gọi tên
    #    chính mình - sai 100% theo đáp án (self_addressed). Ứng viên: người có tên nói trong 6 đoạn quanh đó (gần nhất trước),
    #    rồi người nói nhiều nhất chương; đây chính là những câu luật tự sửa của dây chuyền không chắc nên để nguyên.
    for row in spoken:
        if int(row["id"]) not in self_addressed_ids:
            continue
        speaker = str(row["speaker"])
        name = speaker_label(speaker)
        nearby = [{"label": speaker_label(person), "value": person} for person in self_addressed_ids[int(row["id"])]]
        choices = nearby[:NEARBY_CHOICES]
        choices += _cast_choices(spoken, {int(row["chapter_id"])}, {speaker.casefold()}, speaker_label)[:max(0, 4 - len(choices))]
        choices += [{"label": "Người kể", "value": NARRATOR}, {"label": "Vai phụ không tên", "value": UNNAMED}]
        fix = _speaker_fix([row], choices, speaker, speaker_wishes, speaker_label)
        if fix is None:
            continue
        items.append({
            "kind": "vocative",
            "key": f"vocative:{row['id']}",
            "title": f"Câu này gọi tên “{name}” nhưng lại gán cho chính {name}",
            "problem": f"Không ai gọi tên chính mình: câu có tên {name} thường là nói với {name} hay nói về {name}, không"
                       f" phải {name} nói.",
            "affected": 1,
            "doubt": 0.7,
            "options": ["Chọn người nói khác", "Giữ nguyên"],
            "current": name,
            "examples": [_example(row, names, speaker_label, project_root)],
            **fix,
        })

    # 2b. Hai đoạn thoại liền nhau - đoạn trước đóng ngoặc, đoạn sau mở ngoặc mới, không lời dẫn - mà cùng một người: gần
    #     như chắc máy bỏ lỡ một lượt đổi người. Đo 28-09 (ANALYSIS_RESEARCH.md, "Lượt đối đáp"): trên đáp án 7 truyện,
    #     91/95 cặp như thế là HAI người, và qwen3:8b gán cùng người cho 42 cặp - 38 cặp sai.
    # Truyện kể ngôi thứ nhất: người đối đáp thường là chính "tôi" - đứng đầu các lựa chọn.
    voices = store.read_settings(project_root).get("voices")
    partner = str((voices if isinstance(voices, dict) else {}).get("first_person_identity") or "")
    # Cặp nối nhau (câu 1-2, 2-3...) là MỘT chuỗi, một thẻ: mỗi cặp một thẻ thì sửa thẻ đầu (câu 2 là người kia) xong thẻ
    # sau vẫn hỏi "câu 3 cũng là của A?" như thể câu 2 vẫn là A (soát UX 29-09). Chuỗi đối đáp bị gán hết cho một người
    # thường là hai người xen kẽ: thẻ đổi các câu thứ 2, 4... sang người được chọn, các câu còn lại giữ nguyên.
    chains: list[list[Any]] = []
    for first, second in turns:
        if chains and chains[-1][-1]["stable_id"] == first["stable_id"]:
            chains[-1].append(second)
        else:
            chains.append([first, second])
    for chain in chains:
        for start in range(0, len(chain), TURN_CHAIN_MAX):
            lines = chain[start:start + TURN_CHAIN_MAX]
            changing = lines[1::2]
            if not changing:
                continue
            speaker = str(lines[-1]["speaker"])
            name = _mid(speaker_label(speaker))
            choices = []
            if partner and partner.casefold() != speaker.casefold():
                choices.append({"label": speaker_label(partner), "value": partner})
            choices += _cast_choices(spoken, {int(lines[0]["chapter_id"])}, {speaker.casefold()}, speaker_label)
            choices += [{"label": "Người kể", "value": NARRATOR}, {"label": "Vai phụ không tên", "value": UNNAMED}]
            fix = _speaker_fix(changing, choices, speaker, speaker_wishes, speaker_label)
            if fix is None:
                continue
            if len(lines) == 2:
                items.append({
                    "kind": "turn",
                    "key": f"turn:{lines[1]['stable_id']}",
                    "title": f"Hai câu liền nhau đều là của {name}?",
                    "problem": f"Câu sau là một đoạn riêng, không lời dẫn, nói ngay sau một câu của {name}. Hầu hết những"
                               " cặp như thế là hai người đối đáp - có thể câu sau là của người đang nói với " + name + ".",
                    "affected": 1,
                    "doubt": 0.9,
                    "options": ["Chọn người nói khác", "Giữ nguyên"],
                    "current": speaker_label(speaker),
                    "examples": [{**_example(lines[0], names, speaker_label, project_root), "changes": False},
                                 {**_example(lines[1], names, speaker_label, project_root), "changes": True}],
                    **fix,
                })
                continue
            items.append({
                "kind": "turn",
                "key": f"turns:{lines[0]['stable_id']}",
                "title": f"{len(lines)} câu liền nhau đều là của {name}?",
                "problem": f"{len(lines)} đoạn thoại liền nhau, không lời dẫn, đều gán cho {name}. Thường là hai người đối"
                           f" đáp: chọn người nói các câu xen kẽ (đánh dấu “sẽ đổi”), các câu còn lại vẫn của {name}. Cả"
                           " chuỗi là lời của MỘT người khác (độc thoại vắt nhiều đoạn) thì chọn “Cả chuỗi”.",
                "affected": len(changing),
                "doubt": 0.9,
                "options": ["Chọn người nói khác", "Giữ nguyên"],
                "current": speaker_label(speaker),
                "examples": [{**_example(row, names, speaker_label, project_root), "changes": index % 2 == 1} for index, row in enumerate(lines)],
                **fix,
                # Phạm vi "Cả chuỗi": độc thoại vắt nhiều đoạn của một người khác (lô 18: 3 đoạn gán Heit mà người nói
                # đang tính "nhắc nhở Heit") - xen kẽ sẽ sai cả ba.
                "allLines": [{"stableId": str(row["stable_id"]), "textSha256": str(row["text_sha256"] or "")}
                             for row in lines],
            })

    # 3. Nghi là MỘT người mang hai tên (bí danh): tên ngắn nằm trọn ở đầu hay cuối tên dài, không khác giới. Tên nào dài
    #    hơn KHÔNG nói ai nhiều câu hơn ("Lucien" 500 câu, "Lucien Evans" 3 câu là trường hợp thường gặp nhất). Gộp thì câu
    #    của người ÍT câu về người NHIỀU câu: người nghe đã quen giọng ấy, và ít câu phải thu lại nhất. Đi đúng đường ghi đè
    #    nhóm câu của vai phụ; "Hai người khác nhau" giữ nguyên cả nhóm và thẻ không hiện lại.
    named = {speaker: rows for speaker, rows in lines_by_speaker.items() if _is_named(speaker)}
    by_character = {str(character["canonical_name"]).upper(): character for character in characters.values()}
    speakers = sorted(named, key=lambda speaker: (-len(named[speaker]), speaker))
    for index, major in enumerate(speakers):
        for minor in speakers[index + 1:]:
            longer, shorter = (
                (major, minor) if len(_tokens(speaker_label(major))) > len(_tokens(speaker_label(minor))) else (minor, major)
            )
            long_tokens, short_tokens = _tokens(speaker_label(longer)), _tokens(speaker_label(shorter))
            if not short_tokens or len(short_tokens) >= len(long_tokens):
                continue
            if short_tokens != long_tokens[-len(short_tokens):] and short_tokens != long_tokens[:len(short_tokens)]:
                continue
            a, b = by_character.get(longer.upper()), by_character.get(shorter.upper())
            if a is not None and b is not None and "unknown" not in (a["gender"], b["gender"]) and a["gender"] != b["gender"]:
                continue
            into = speaker_label(major)
            fix = _speaker_fix(named[minor], [{"label": f"Gộp vào {into}", "value": major, "name": into}], minor,
                               speaker_wishes, speaker_label)
            if fix is None:
                continue
            items.append({
                "kind": "alias",
                "key": f"alias:{longer}|{shorter}",
                "title": f"“{speaker_label(shorter)}” và “{speaker_label(longer)}” là một người?",
                "problem": "Hai tên này đang là hai nhân vật với hai giọng khác nhau, nhưng tên ngắn nằm trọn trong tên dài."
                           f" Gộp thì {len(named[minor])} câu của {speaker_label(minor)} đọc bằng giọng của {into}"
                           f" - giọng đang đọc {len(named[major])} câu của {into}.",
                "affected": len(named[minor]),
                "doubt": 0.6,
                "options": [f"Gộp vào {into}", "Hai người khác nhau"],
                "current": "Hai người khác nhau",
                "keepLabel": "Hai người khác nhau",
                # Tên được hỏi (bí danh) để hiển thị - `current` là nhãn lựa chọn "Hai người khác nhau", không phải tên.
                "subject": speaker_label(minor),
                "examples": [_example(row, names, speaker_label, project_root) for row in (named[minor][:2] + named[major][:1])],
                **fix,
            })

    # 3a. Danh hiệu / biệt danh của một người: sách viết hai tên SÁT nhau ("Thiên Biến Vạn Hóa Krai") mà máy gán câu cho
    #     cả hai - hai giọng cho một người (Nageki 65: 3 câu của người kể thành "Thiên Biến Vạn Hoá"). Thẻ trên chỉ bắt
    #     tên ngắn nằm trong tên dài. Chỉ hỏi khi danh hiệu đứng sát ĐÚNG MỘT người (EPITHET_EVIDENCE lần trở lên) - sát
    #     nhiều người là chức vụ chung ("Giáo sư"). Gộp như thẻ trên: người ít câu về người nhiều câu.
    try:
        folded_book = _folded_book(chapter_paths) if len(named) > 1 else ""
    except OSError:
        folded_book = ""
    if folded_book:
        top = sorted(named, key=lambda speaker: (-len(named[speaker]), speaker))[:40]
        links = epithet_links(top, folded_book)
        partners: dict[str, set[str]] = defaultdict(set)
        for (epithet, name), count in links.items():
            partners[epithet].add(name)
            partners[name].add(epithet)
        asked: set[frozenset[str]] = set()
        for (epithet, name), count in sorted(links.items(), key=lambda item: -item[1]):
            pair = frozenset((epithet, name))
            # Một chỗ sát nhau được thấy từ CẢ HAI tên - lấy chiều thấy nhiều hơn, không cộng. Độc quyền cả hai phía: "Glast"
            # chỉ sát "Giáo sư" nhưng "Giáo sư" sát cả Krayd - chức danh chung, không phải biệt danh.
            both = max(links.get((epithet, name), 0), links.get((name, epithet), 0))
            if pair in asked or both < EPITHET_EVIDENCE or partners[epithet] != {name} or partners[name] != {epithet}:
                continue
            asked.add(pair)
            major, minor = sorted(pair, key=lambda speaker: (-len(named[speaker]), speaker))
            a, b = by_character.get(major.upper()), by_character.get(minor.upper())
            if a is not None and b is not None and "unknown" not in (a["gender"], b["gender"]) and a["gender"] != b["gender"]:
                continue
            into = speaker_label(major)
            fix = _speaker_fix(named[minor], [{"label": f"Gộp vào {into}", "value": major, "name": into}], minor,
                               speaker_wishes, speaker_label)
            if fix is None:
                continue
            first, second = sorted((speaker_label(epithet), speaker_label(name)), key=len)
            items.append({
                "kind": "alias",
                "key": f"alias:{major}|{minor}",
                "title": f"“{speaker_label(minor)}” là tên khác của {into}?",
                "problem": f"Sách viết hai tên này sát nhau {both} lần (như “{second} {first}”) - thường là danh hiệu hay"
                           f" biệt danh của một người. Máy đang cho {len(named[minor])} câu của {speaker_label(minor)} một"
                           f" giọng riêng; gộp thì đọc bằng giọng của {into} - giọng đang đọc {len(named[major])} câu của {into}.",
                "affected": len(named[minor]),
                "doubt": 0.7,
                "options": [f"Gộp vào {into}", "Hai người khác nhau"],
                "current": "Hai người khác nhau",
                "keepLabel": "Hai người khác nhau",
                # Tên được hỏi (bí danh) để hiển thị - `current` là nhãn lựa chọn "Hai người khác nhau", không phải tên.
                "subject": speaker_label(minor),
                "examples": [_example(row, names, speaker_label, project_root) for row in (named[minor][:2] + named[major][:1])],
                **fix,
            })

    # 3b. Lời trong ngoặc 『』 - thần giao, linh thể, giọng qua điện thoại, bình luận trên mạng - là một "kênh giọng" riêng
    #     mà máy yếu nhất: đo 28-09 trên bộ LN, câu 『』 sai người nói 56-67% (câu thường 34-41%) - máy gán mỗi câu cho
    #     người đứng gần (Yamiyo: linh thể luôn nói trong 『』 bị chia cho người kể, Hina, Yuusei, "người lạ"). Thường cả
    #     chương chỉ một người (hay người kể) nói trong 『』: một cú bấm gán cả nhóm. Nhiều người thật thì sửa từng câu ở
    #     tab Kịch bản - thẻ không có nút giữ nguyên vì nhóm đang mang nhiều nhãn.
    bracketed: dict[int, list[Any]] = defaultdict(list)
    for row in spoken:
        if str(row["text"]).lstrip().startswith("『"):
            bracketed[int(row["chapter_id"])].append(row)
    # Phạm vi "Cả cuốn" (bracket_rule.py): mọi câu 『』 của dự án về một người - và quy ước đi theo các phần sau.
    every_bracketed = [{"stableId": str(row["stable_id"]), "textSha256": str(row["text_sha256"] or "")}
                       for rows in bracketed.values() for row in rows]
    for chapter_id, rows in bracketed.items():
        counts = Counter(str(row["speaker"]) for row in rows)
        if len(rows) < 3 or len(counts) < 2:
            continue
        here = [speaker for speaker, _count in counts.most_common() if _is_named(speaker)]
        choices = [{"label": f"Tất cả là {speaker_label(speaker)}", "value": speaker, "name": speaker_label(speaker)}
                   for speaker in here]
        # Người đúng có thể chưa từng được máy gán câu nào trong chương này (linh thể Yamiyo: 0/43 câu) - thêm người nói
        # nhiều nhất của chương rồi của CẢ CUỐN.
        offered = {speaker.casefold() for speaker in here}
        for chapters in ({chapter_id}, {int(row["chapter_id"]) for row in spoken}):
            for choice in _cast_choices(spoken, chapters, offered, speaker_label):
                offered.add(choice["value"].casefold())
                choices.append({**choice, "label": f"Tất cả là {choice['label']}", "name": choice["label"]})
        choices.append({"label": "Người kể đọc tất cả", "value": NARRATOR, "name": "Người kể"})
        fix = _speaker_fix(rows, choices, "", speaker_wishes, speaker_label)
        if fix is None:
            continue
        chapter = names.get(chapter_id, {})
        split = ", ".join(f"{speaker_label(speaker)} {count}" for speaker, count in counts.most_common(4))
        items.append({
            "kind": "bracket",
            "key": f"bracket:{chapter_id}",
            "title": f"Lời trong 『』 ở {chapter.get('full') or chapter.get('title') or 'chương này'} là của một người?",
            "problem": f"{len(rows)} câu trong ngoặc 『』 - thường là thần giao, linh thể, giọng qua điện thoại hay bình"
                       f" luận - máy chia cho {len(counts)} người ({split}). Máy hay sai loại câu này nhất. Nếu thật là"
                       " nhiều người, sửa từng câu ở tab Kịch bản.",
            "affected": len(rows),
            "doubt": 0.8,
            "options": [choice["label"] for choice in choices],
            "current": f"{len(counts)} người",
            "examples": [_example(row, names, speaker_label, project_root) for row in rows[:EXAMPLES]],
            **fix,
            "allLines": every_bracketed,
            "scopeLabels": ["Chương này", "Cả cuốn"],
        })

    # 4. Hai nhân vật có tên dùng CHUNG một giọng và cùng nói trong một chương: người nghe không phân biệt được.
    voice_chapters: dict[tuple[int, int], set[str]] = defaultdict(set)
    for row in spoken:
        if _is_named(str(row["speaker"])) and row["voice_profile_id"] is not None:
            voice_chapters[(int(row["voice_profile_id"]), int(row["chapter_id"]))].add(str(row["speaker"]))
    clashes: dict[frozenset[str], set[int]] = defaultdict(set)
    shared_voice: dict[frozenset[str], int] = {}
    for (voice, chapter_id), people in voice_chapters.items():
        if len(people) > 1:
            clashes[frozenset(people)].add(chapter_id)
            shared_voice[frozenset(people)] = voice
    for people, chapter_ids in clashes.items():
        rows = [row for row in spoken if str(row["speaker"]) in people and int(row["chapter_id"]) in chapter_ids]
        ordered = sorted(people, key=lambda person: speaker_label(person).casefold())
        labels = [speaker_label(person) for person in ordered]
        keys = [_character_key(person) for person in ordered]
        wishes = [voice_wishes.get(key) for key in keys]
        if all(wish is not None and not (wish["gender"] or wish["preset"] or wish["avoid"]) for wish in wishes):
            continue  # người nghe bảo giữ nguyên
        profile = profiles.get(shared_voice[people])
        avoid = str(profile["voice_key"]) if profile is not None else ""
        # Người ÍT câu hơn đứng đầu: ít câu phải thu lại hơn, và người nghe đã quen giọng của người nói nhiều.
        lines = {person: sum(1 for row in rows if str(row["speaker"]) == person) for person in ordered}
        choices = [
            {"label": f"Đổi giọng {label}", "character": key, "avoid": avoid, "done": f"đổi giọng {label}",
             "note": f"thu lại {lines[person]} câu ở các chương chung", "recommended": index == 0}
            for index, (person, label, key) in enumerate(sorted(zip(ordered, labels, keys), key=lambda item: lines[item[0]]))
        ] if avoid else []
        moving = [label for label, wish in zip(labels, wishes) if wish is not None and wish["avoid"]]
        items.append({
            "kind": "shared-voice",
            "key": "shared-voice:" + "|".join(sorted(people)),
            "title": f"{', '.join(labels)} dùng chung một giọng trong cùng chương",
            "problem": f"Cùng nói trong {len(chapter_ids)} chương mà một giọng - nghe không biết ai đang nói.",
            "affected": len(rows),
            "doubt": 0.8,
            "options": [f"Đổi giọng {label}" for label in labels] + ["Giữ nguyên"],
            "current": "Chung giọng",
            "examples": [_example(row, names, speaker_label, project_root) for row in rows[:EXAMPLES]],
            **({"voiceChoices": choices, "keepCharacters": keys, "keepLabel": "Giữ nguyên"} if choices else {}),
            "requested": f"đổi giọng {', '.join(moving)}" if moving else None,
        })

    # 5. Một vai phụ không tên mang cùng nhãn ở nhiều chương/cảnh ("lính gác 1" ở bốn chương, "áo xanh" ở ba): một thẻ
    #    cho cả cuốn thay cho thẻ của từng chỗ - chọn người một lần, bỏ chọn câu nào không phải. Áp là đúng một yêu cầu
    #    "ai nói câu này" cho mỗi câu đã chọn, cùng một lần bấm (hoàn tác cả nhóm một lần). Giữ nguyên = mỗi vai giữ
    #    người của nó (`keepGroups`).
    grouped: set[str] = set()
    for role, members in sorted(minor_role_groups(lines_by_speaker, set(speaker_wishes)).items()):
        rows = sorted((row for member_rows in members.values() for row in member_rows),
                      key=lambda row: (chapter_index.get(int(row["chapter_id"]), 0), int(row["seq"])))
        chapter_ids = {int(row["chapter_id"]) for row in rows}
        grouped.update(members)
        # Nhãn hay gặp nhất trong nhóm (máy viết "Lính gác" chỗ này, "lính  gác" chỗ kia); hoà thì câu đến trước.
        label = Counter(" ".join(speaker_label(str(row["speaker"])).split()) for row in rows).most_common(1)[0][0]
        where = f"{len(chapter_ids)} chương" if len(chapter_ids) > 1 else f"{len(members)} cảnh"
        # "Người kể" chỉ là lựa chọn khi sách có người kể "tôi" (lời người kể thường lẫn vào vai phụ); truyện ngôi ba thì lính
        # gác không phải người kể. Thay vào đó: "là một người mới tên “…”" (`newPerson`) - cả nhóm thành MỘT người có giọng riêng.
        choices = _cast_choices(spoken, chapter_ids, set(), speaker_label)
        if book_narrator or chapter_narrators:
            choices += [{"label": "Người kể", "value": NARRATOR}]
        items.append({
            "kind": "unnamed",
            "newPerson": label[:1].upper() + label[1:],
            "key": f"unnamed-role:{role}",
            "title": f"{len(rows)} câu của vai phụ “{label}” ở {where} - một người?",
            "problem": f"Máy để “{label}” là vai phụ không tên riêng ở từng chỗ - {len(members)} giọng khác nhau. Nếu cả"
                       " cuốn là một người, chọn người ấy một lần cho mọi câu; câu nào không phải thì bỏ chọn trước.",
            "affected": len(rows),
            "doubt": 0.4,
            "options": [choice["label"] for choice in choices] + [f"Là một người mới tên “{label[:1].upper() + label[1:]}”", "Mỗi chỗ một người"],
            "current": f"{len(members)} vai phụ riêng",
            # Mọi câu của nhóm (không chỉ vài câu ví dụ): người nghe bỏ chọn từng câu ngay trên thẻ.
            "examples": [{**_example(row, names, speaker_label, project_root), "stableId": str(row["stable_id"])}
                         for row in rows],
            "lines": [{"stableId": str(row["stable_id"]), "textSha256": str(row["text_sha256"] or "")} for row in rows],
            "choices": choices,
            "requested": None,
            "pick": True,
            "keepGroups": [
                {"speaker": speaker, "lines": [{"stableId": str(row["stable_id"]), "textSha256": str(row["text_sha256"] or "")}
                                               for row in member_rows]}
                for speaker, member_rows in members.items()
            ],
            "keepLabel": "Mỗi chỗ một người",
        })

    # 5b. Người nói không tên (vai phụ cục bộ không nằm trong thẻ cả cuốn): có thể là một nhân vật có tên trong chương.
    for speaker, rows in lines_by_speaker.items():
        if not speaker.startswith("NPC_LOCAL") or speaker in grouped:
            continue
        # Câu đã có quyết định riêng (bỏ chọn ở thẻ cả cuốn rồi gán phần còn lại, sửa một câu ở Kịch bản): thẻ chỉ hỏi những
        # câu còn lại. Mọi câu đã quyết mà không cùng một người thì không còn gì để hỏi.
        open_rows = [row for row in rows if str(row["stable_id"]) not in speaker_wishes]
        if not open_rows and len({speaker_wishes[str(row["stable_id"])]["speaker"].casefold() for row in rows}) > 1:
            continue
        rows = open_rows or rows
        # Chọn một người có tên thì MỌI câu của vai này về người ấy (giọng của họ); "Đúng là vai phụ" giữ cả nhóm.
        choices = _cast_choices(spoken, {int(row["chapter_id"]) for row in rows}, set(), speaker_label)
        fix = _speaker_fix(rows, choices, speaker, speaker_wishes, speaker_label)
        if fix is None:
            continue
        items.append({
            "kind": "unnamed",
            "key": f"unnamed:{speaker}",
            "title": f"“{speaker_label(speaker)}” là ai?",
            "problem": "Máy để người này là vai phụ không tên (giọng riêng trong chương). Nếu thật ra là nhân vật có tên thì"
                       " nên dùng giọng của nhân vật ấy.",
            "affected": len(rows),
            "doubt": 0.4,
            "options": ["Là một nhân vật có tên", "Đúng là vai phụ"],
            "current": "Vai phụ không tên",
            "examples": [_example(row, names, speaker_label, project_root) for row in rows[:EXAMPLES]],
            **fix,
        })

    # 6. Cách đọc tên riêng máy chưa chắc. Người nghe sửa ngay trên thẻ; mong muốn chưa áp thì hiện "đang chờ", áp rồi thì
    #    dòng cách đọc thành của người nghe (tin cậy 1,0) và việc tự rơi khỏi danh sách.
    requested = {surface_key(entry["surface"]): entry["spoken_form"] for entry in pronunciation_requests(overrides)}
    for row in pronunciations:
        occurrences = word_segments.get(str(row["surface"]), 0)
        if occurrences == 0:
            continue
        items.append({
            "kind": "pronunciation",
            "key": f"pronunciation:{row['surface']}",
            "title": f"Đọc “{row['surface']}” là “{shown_reading(str(row['spoken_form']))}”?",
            # Không ghi "máy chắc 88%": gần như mọi tên máy tự đoán đều mang đúng con số ấy nên nó không nói gì (soát UX
            # 29-09: 50/51 thẻ); số câu đã có ở "Ảnh hưởng N câu".
            "problem": "Cách đọc do máy tự đoán - nghe một câu mẫu, sai thì sửa ngay trên thẻ."
                       if float(row["confidence"]) >= 0.8 else
                       "Máy không chắc cách đọc tên này - nghe một câu mẫu, sai thì sửa ngay trên thẻ.",
            "affected": occurrences,
            "doubt": round(1 - float(row["confidence"]), 2),
            "options": ["Đúng rồi", "Đọc cách khác"],
            "current": str(row["spoken_form"]),
            "surface": str(row["surface"]),
            "requested": requested.get(surface_key(str(row["surface"]))),
            # Người nói của câu ví dụ không liên quan tới cách đọc tên - bỏ "máy gán: ..." khỏi thẻ này.
            "examples": [{**_example(example, names, speaker_label, project_root), "speaker": ""} for example in word_examples.get(str(row["surface"]), [])],
        })

    # 7. Bản thu lỗi (hàng chờ "Cần nghe lại"), gom theo chương.
    audio_by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in review_items(project_root):
        if entry.get("kind") in ("failed", "unverified", "name-low"):
            audio_by_chapter[int(entry["chapterId"])].append(entry)
    for chapter_id, entries in audio_by_chapter.items():
        items.append({
            "kind": "audio",
            "key": f"audio:{chapter_id}",
            "title": f"{len(entries)} câu thu âm cần nghe lại - {entries[0].get('chapterTitle', '')}",
            "problem": "Khâu tự kiểm tra không chắc các câu này (xem tab Cần nghe lại).",
            "affected": len(entries),
            "doubt": 0.5,
            "options": ["Nghe và chấm ở tab Cần nghe lại"],
            "current": "Chưa nghe",
            "examples": [],
        })

    # Chương của các câu mỗi thẻ sẽ đổi (hay của câu ví dụ, với thẻ không đổi câu nào cụ thể): "Duyệt trước khi thu"
    # (precast.py) hỏi trước những thẻ ở các chương sắp thu.
    chapter_of = {str(row["stable_id"]): int(row["chapter_id"]) for row in spoken}
    for item in items:
        item["chapters"] = sorted({chapter_of[line["stableId"]] for line in item.get("lines") or ()
                                   if line["stableId"] in chapter_of}
                                  or {int(example["chapterId"]) for example in item["examples"]})
        item["score"] = round(item["affected"] * item["doubt"] * SEVERITY[item["kind"]], 3)
        undo = _undo_of(item, overrides)
        if undo is not None:
            item["undo"] = undo
    items.sort(key=lambda item: -item["score"])
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item["kind"]] += 1
    return {"items": items, "counts": dict(counts)}
