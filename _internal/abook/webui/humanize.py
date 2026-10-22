"""Chữ cho người đọc: trạng thái, giai đoạn, sự kiện của dây chuyền nói bằng tiếng Việt thường ngày.

Nguyên tắc: nói điều người dùng nhận ra được (một chương đã nghe được, một câu nên nghe lại), không nói cách hệ
thống làm (lease, critic, candidate). Sự kiện nào không có nghĩa với người nghe thì không có mặt ở đây - nó vẫn
nằm nguyên trong "Chi tiết kỹ thuật".
"""
from __future__ import annotations

import ast
import errno
import json
import re
from pathlib import Path

from ..voice_catalog import ENGINE_VOICES

WORKING_PHASES = frozenset({"analysis", "casting", "synthesis"})

PROFILE_LABELS = {
    "fast": "Nhanh",
    "balanced": "Cân bằng",
    "high_quality": "Chất lượng cao",
}

CHAPTER_STATUS_LABELS = {
    "pending": "Chờ",
    "synthesizing": "Đang thu",
    "verifying": "Đang kiểm tra",
    "completed": "Nghe được",
    "failed": "Lỗi",
    "warning": "Cần xem lại",
}

# Trạng thái chương ngoài bảng trên (dữ liệu lạ, bản dây chuyền mới hơn): nhãn chung, không đưa mã thô như "done" ra trang.
UNKNOWN_CHAPTER_STATUS = "Chưa rõ trạng thái"


def chapter_status_label(status: str) -> str:
    return CHAPTER_STATUS_LABELS.get(status, UNKNOWN_CHAPTER_STATUS)


GENDER_LABELS = {"male": "Nam", "female": "Nữ"}

# Tên giọng VieNeu là tên hiện hành của VieNeu (3.8.3) và cũng là khoá - không đổi qua lại. Chỉ giọng của máy đọc khác
# (voice_catalog.ENGINE_VOICES) có nhãn riêng: khoá là tên giọng của máy ("baotrang"), người nghe thấy "Bảo Trang" -
# đổi sang nhãn khi đưa ra giao diện (`voice_label`), đổi ngược khi nhận về (`voice_key`).
_ENGINE_VOICE_LABELS = {str(voice["name"]): str(voice["label"]) for voice in ENGINE_VOICES}
_VOICE_KEYS = {label: key for key, label in _ENGINE_VOICE_LABELS.items()}


def voice_label(name: str) -> str:
    return _ENGINE_VOICE_LABELS.get(name, name)


def voice_key(name: str) -> str:
    return _VOICE_KEYS.get(name, name)
AGE_LABELS = {
    "child": "Trẻ em",
    "teen": "Thiếu niên",
    "young": "Thanh niên",
    "adult": "Trưởng thành",
    "elderly": "Cao tuổi",
}

_STABLE_ID = re.compile(r"\bc(\d{5})_s(\d{7})_[0-9a-f]+")
_NUMERIC_TITLE = re.compile(r"^\s*0*(\d+)\s*$")
# Số thứ tự đệm số 0 đầu tên file ("0000 Mở đầu", "001 - Chương 1"): chỉ khi bắt đầu bằng 0, để không cắt "100 ngày" hay "1984".
_FILE_ORDER_PREFIX = re.compile(r"^\s*0\d*(?:\s*[-_.:]+\s*|\s+)(\S.*)$")


def phase_of(status: str, stage: str) -> str:
    if status == "completed" or stage in ("completed", "completed_with_errors"):
        return "done"
    if status == "error" or stage in ("unrecoverable_error", "critical_stop"):
        return "error"
    if status in ("stopped", "paused"):
        return "stopped"
    return {
        "analyzing": "analysis",
        "casting": "casting",
        "synthesizing": "synthesis",
    }.get(status, "idle")


def status_label(phase: str, stage: str, *, active: bool) -> str:
    if phase == "done":
        return "Xong, còn chương lỗi" if stage == "completed_with_errors" else "Hoàn tất"
    if phase == "error":
        return "Dừng khẩn cấp" if stage == "critical_stop" else "Gặp lỗi"
    if phase == "stopped":
        return "Đã dừng"
    if phase == "idle":
        # Worker đã chạy nhưng chưa làm câu nào (đang nạp model): "Chưa bắt đầu" cạnh nút Dừng là mâu thuẫn.
        return "Đang khởi động" if active else "Chưa bắt đầu"
    doing = {"analysis": "phân tích truyện", "casting": "phân vai", "synthesis": "thu âm"}[phase]
    if phase == "analysis" and stage == "speaker_pass":
        doing = "xác định người nói từng câu"  # lượt speaker_pass.py, sau khi cả truyện đã phân tích
    return f"Đang {doing}" if active else f"Tạm ngưng lúc {doing}"


# Đã bấm "Dừng": worker còn chạy tới checkpoint sạch kế, chưa dừng hẳn.
STOPPING_LABEL = "Đang dừng…"


def pause_label(reason: str, *, reached: bool) -> str:
    """Nhãn trạng thái khi cuốn đang tạm dừng (power_source). Chưa tới checkpoint thì dây chuyền còn làm nốt việc dở."""
    if not reached:
        return "Đang tạm dừng…"
    return "Tạm dừng · máy đang chạy pin" if reason == "battery" else "Đã tạm dừng"


def chapter_title(title: str) -> str:
    """Tên file chương là số ("645") thì đọc thành "Chương 645"; số thứ tự đánh đầu file ("0000 Mở đầu") là để xếp thứ tự,
    không phải tên - bỏ đi; còn lại giữ nguyên."""
    match = _NUMERIC_TITLE.match(title)
    if match:
        return f"Chương {match.group(1)}"
    prefixed = _FILE_ORDER_PREFIX.match(title)
    return prefixed.group(1).strip() if prefixed else title.strip()


_HEADING = re.compile(
    r"^\s*((?:chương|chapter|hồi|quyển|phần|tiết)\s*[\dIVXLC]+)\s*(?:[-:–—.·|]+\s*(.*?))?\s*$", re.IGNORECASE
)


def is_heading(text: str) -> bool:
    return len(text) <= 160 and _HEADING.match(text) is not None


def chapter_names(file_title: str, heading: str | None) -> tuple[str, str]:
    """(tên, phụ đề) của một chương cho người đọc.

    Tên file không phải tên chương: nguồn của cuốn 2 đánh số file lệch một so với truyện - file `645.txt` mở đầu
    bằng "Chương 646 - Trở về (1)". Người nghe thấy "Chương 645" trên danh sách rồi nghe đọc "Chương 646" là hai con
    số vênh nhau. Nên dòng tiêu đề trong văn bản thắng; tên file chỉ là đường lui khi chương không có tiêu đề.
    """
    if heading and len(heading) <= 160:
        match = _HEADING.match(heading)
        if match:
            name = match.group(1).strip()
            return name[:1].upper() + name[1:], (match.group(2) or "").strip()
    return chapter_title(file_title), ""


def person_name(name: str) -> str:
    """Tên chuẩn hoá của sổ nhân vật viết HOA HẾT ("VIỄN CỔ MỘC NÃI Y"); người đọc thấy "Viễn Cổ Mộc Nãi Y".
    Tên đã có chữ thường thì để nguyên - người viết sách đã chọn cách viết ấy. Vai phụ cục bộ mang nhãn nội bộ
    "NPC_LOCAL::c00006::r0b2…::người lùn": người đọc chỉ thấy "người lùn"; gạch dưới thành dấu cách."""
    if "::" in name:
        name = name.rsplit("::", 1)[-1]
    name = name.replace("_", " ").strip()
    if name != name.upper():
        # "LOUise": model gõ vài chữ đầu HOA rồi thường - không tên nào viết thế (soát UX 29-09); "McDonald", "LeBlanc" giữ.
        return " ".join(word[:1] + word[1:].lower() if _caps_glitch(word) else word for word in name.split(" "))
    words = []
    for word in name.split():
        if word in _ROMAN_NUMERALS:
            words.append(word)
        else:
            words.append("-".join(part[:1] + part[1:].lower() for part in word.split("-")))
    return " ".join(words)


_ROMAN_NUMERALS = frozenset({"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"})


def shown_reading(spoken: str) -> str:
    """Cách đọc một tên để HIỆN: chữ đầu mỗi từ viết hoa ("rên-ta-rô" -> "Rên-ta-rô", như ui/src/shared/format.shownReading).
    Chỉ cho chữ hiện ra - giá trị lưu và giá trị để sửa giữ nguyên."""
    return re.sub(r"(^|\s)([^\W\d_])", lambda match: match.group(1) + match.group(2).upper(), spoken)


def _caps_glitch(word: str) -> bool:
    """Từ mở bằng từ HAI chữ hoa trở lên rồi toàn chữ thường ("LOUise")."""
    letters = [ch for ch in word if ch.isalpha()]
    run = next((index for index, ch in enumerate(letters) if not ch.isupper()), len(letters))
    return 2 <= run < len(letters) and all(ch.islower() for ch in letters[run:])


def voice_tone(formant: float, pitch: float) -> str:
    """Một chữ mô tả biến thể của giọng gốc, như người nghe nhận ra nó."""
    if formant <= 0.9 or pitch <= -2.5:
        return "trầm hẳn"
    if formant <= 0.96 or pitch <= -1.5:
        return "hơi trầm"
    if formant >= 1.1 or pitch >= 2.5:
        return "sáng hẳn"
    if formant >= 1.04 or pitch >= 1.5:
        return "hơi sáng"
    return ""


def error_text(error: str) -> str:
    text = error.strip().splitlines()[0] if error.strip() else ""
    return text[:240]


def is_write_problem(error: BaseException) -> bool:
    """Lỗi ghi người dùng tự gỡ được: thư mục chỉ đọc / không có quyền, ổ đầy."""
    return isinstance(error, PermissionError) or (isinstance(error, OSError) and error.errno in (errno.EACCES, errno.EPERM, errno.EROFS, errno.ENOSPC))


def write_error(error: OSError) -> str:
    """Lỗi ghi file bằng lời người dùng (soát a28 lỗi 10): tên THƯ MỤC (không cả đường dẫn - có tên tài khoản Windows) và việc nên làm,
    thay vì "PermissionError: [Errno 13] Permission denied: '...names.json.part'" hay "[WinError 5] Access is denied"."""
    where = "thư mục này"
    if error.filename:
        path = Path(str(error.filename))
        folder = path if path.is_dir() else path.parent
        if folder.name:
            where = f"thư mục “{folder.name}”"
    if error.errno == errno.ENOSPC:
        return f"Ổ đĩa chứa {where} đã đầy - dọn bớt rồi thử lại."
    if is_write_problem(error):
        return f"Không ghi được vào {where}: thư mục chỉ đọc hoặc app không có quyền ghi - chọn thư mục khác trong Cài đặt."
    return f"Không ghi được vào {where} ({error.strerror or error})."


def _where(message: str, chapters: dict[int, str]) -> str:
    match = _STABLE_ID.search(message)
    if not match:
        return ""
    return chapters.get(int(match.group(1)), f"chương thứ {int(match.group(1))}")


def _pronunciations(message: str) -> str:
    match = re.search(r"\{.*\}", message)
    if not match:
        return ""
    try:
        mapping = ast.literal_eval(match.group(0))
    except (ValueError, SyntaxError):
        return ""
    return ", ".join(f"{source} → {spoken}" for source, spoken in mapping.items())


def _listed_names(message: str) -> str:
    match = re.search(r"\[(.*?)\]", message)
    if not match:
        return ""
    try:
        return ", ".join(str(name) for name in ast.literal_eval(match.group(0)))
    except (ValueError, SyntaxError):
        return ""


def _mismatch(message: str, chapters: dict[int, str]) -> str:
    where = _where(message, chapters)
    return (f"Một câu ở {where} vẫn đọc lệch chữ sau khi thử lại hết lượt; đã giữ bản tốt nhất - nên nghe lại"
            if where else "")


def _short(message: str, chapters: dict[int, str]) -> str:
    where = _where(message, chapters)
    return f"Một câu rất ngắn ở {where} không tự kiểm được bằng nhận dạng giọng nói" if where else ""


def _dictionary(message: str, _chapters: dict[int, str]) -> str:
    pairs = _pronunciations(message)
    return f"Cách đọc tên lấy theo từ điển: {pairs}" if pairs else ""


def _uncertain(message: str, _chapters: dict[int, str]) -> str:
    names = _listed_names(message)
    return f"Chưa chắc cách đọc nên giữ nguyên chữ: {names}" if names else ""


def _protest(message: str, _chapters: dict[int, str]) -> str:
    match = re.search(r"(\d+) segment", message)
    count = match.group(1) if match else "Vài"
    return f"{count} câu được đọc dù AI đạo diễn chưa đồng ý cách thể hiện - nên nghe lại"


def _reconciled(message: str, _chapters: dict[int, str]) -> str:
    match = re.match(r"Hợp nhất NPC (.+?) → (.+?) \((\d+) segment\) ở chương (\d+)", message)
    if not match:
        return ""
    return f"Nhận ra “{match.group(1)}” chính là {person_name(match.group(2))} (chương thứ {match.group(4)})"


_SNAPPED = re.compile(r"chapter (\d+): (\d+) lines labelled (.+) -> (.+) \(the only close name")


def _snapped(message: str, chapters: dict[int, str]) -> str:
    """character_registry.snap_labels_to_chapter_names: nhãn model viết mà chương không viết, về tên chương viết."""
    match = _SNAPPED.match(message)
    if not match:
        return ""
    try:
        label, name = (str(ast.literal_eval(match.group(group))) for group in (3, 4))
    except (ValueError, SyntaxError):
        return ""
    index = int(match.group(1))
    return (f"{chapters.get(index, f'Chương {index}')}: máy viết “{person_name(label)}”, sách chỉ viết “{person_name(name)}”"
            f" - {match.group(2)} câu về {person_name(name)}")


# ---- người kể "tôi" (teller_voice.py): máy tự đổi giọng, nói như người nghe nhận ra ------------------------------------

_TELLER_THOUGHTS = re.compile(r"^(\d+) inner thoughts")
_TELLER_ALIGNED = re.compile(r"^narration voice (.+?) -> (.+?) to match")
_TELLER_MOVED = re.compile(r"^(\d+) narration lines are (?:read in|back in)[^(]*\((\d+) (?:re-recorded|to re-record)\)")


def _teller_thoughts(message: str, _chapters: dict[int, str]) -> str:
    match = _TELLER_THOUGHTS.match(message)
    return f"Máy chuyển {match.group(1)} câu nghĩ thầm của người kể “tôi” sang giọng dẫn" if match else ""


def _teller_aligned(message: str, _chapters: dict[int, str]) -> str:
    match = _TELLER_ALIGNED.match(message)
    return f"Máy đổi giọng dẫn từ {match.group(1)} sang {match.group(2)} cho hợp giới của người kể “tôi”" if match else ""


def _teller_to_teller(message: str, _chapters: dict[int, str]) -> str:
    match = _TELLER_MOVED.match(message)
    if not match:
        return ""
    redo = int(match.group(2))
    return (f"Người kể “tôi” tự đọc {match.group(1)} câu lời kể của mình"
            + (f" - {redo} câu đã thu phải thu lại" if redo else ""))


def _teller_to_narrator(message: str, _chapters: dict[int, str]) -> str:
    match = _TELLER_MOVED.match(message)
    if not match:
        return ""
    redo = int(match.group(2))
    return (f"Trả {match.group(1)} câu lời kể về giọng dẫn" + (f" - {redo} câu đã thu phải thu lại" if redo else ""))


def _resumed(_message: str, _chapters: dict[int, str]) -> str:
    return "Bắt đầu chạy - đã kiểm tra lại dữ liệu cũ"


EVENT_TEXT = {
    "ASR_MISMATCH_UNRESOLVED": _mismatch,
    "NAME_PRONUNCIATION_FROM_DICTIONARY": _dictionary,
    "NAME_PRONUNCIATION_UNCERTAIN_SKIPPED": _uncertain,
    "ANALYSIS_DIRECTOR_CRITIC_PROTESTED": _protest,
    "LOCAL_IDENTITY_RECONCILED": _reconciled,
    "RECOVERY_SCAN": _resumed,
    "SPEAKER_LABEL_SNAPPED_TO_TEXT": _snapped,
    "TELLER_THOUGHTS_TO_NARRATOR": _teller_thoughts,
    "NARRATOR_ALIGNED_TO_TELLER": _teller_aligned,
    "TELLER_NARRATION_TO_TELLER": _teller_to_teller,
    "TELLER_NARRATION_TO_NARRATOR": _teller_to_narrator,
}

_EVENT_LEVEL = {
    "ASR_MISMATCH_UNRESOLVED": "warning",
    "ANALYSIS_DIRECTOR_CRITIC_PROTESTED": "warning",
    "ASR_UNVERIFIABLE_SHORT_TEXT": "info",
    "NAME_PRONUNCIATION_FROM_DICTIONARY": "info",
    "NAME_PRONUNCIATION_UNCERTAIN_SKIPPED": "info",
    "LOCAL_IDENTITY_RECONCILED": "info",
    "RECOVERY_SCAN": "info",
    "SPEAKER_LABEL_SNAPPED_TO_TEXT": "info",
}


# Máy đổi người nói của từng câu bằng đúng đường người nghe dùng (`apply_listener_speaker`), nên mỗi câu ghi một sự kiện "Người nghe gán
# câu …" dù người làm là máy. Ngay sau lô ấy máy ghi MỘT sự kiện tổng kết có đếm: lô gộp thành một dòng và nói máy làm.
_SET_BY_LISTENER = "SPEAKER_SET_BY_LISTENER"
_MACHINE_BATCH = {"TELLER_THOUGHTS_TO_NARRATOR": "lines", "TELLER_NARRATION_TO_TELLER": "thoughts_back",
                  "TELLER_NARRATION_TO_NARRATOR": "thoughts"}
_TELLER_EVENT_TEXT = {"TELLER_THOUGHTS_TO_NARRATOR": _teller_thoughts, "TELLER_NARRATION_TO_TELLER": _teller_to_teller,
                      "TELLER_NARRATION_TO_NARRATOR": _teller_to_narrator}


def _json(raw: object) -> dict:
    try:
        value = json.loads(str(raw or "{}"))
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def technical_events(rows: list) -> list[dict]:
    """"Chi tiết kỹ thuật" của Nhật ký: các sự kiện gần nhất (`rows` mới nhất trước: id, timestamp, level, code, message, details_json),
    nguyên văn - trừ việc máy tự đổi giọng người kể "tôi": lô "Người nghe gán câu …" do máy làm gộp thành một dòng ("Máy chuyển N câu
    nghĩ thầm của <tên> sang giọng dẫn"), sự kiện tổng kết của nó nói bằng lời thường."""
    kept: list[tuple[dict, dict]] = []  # (dòng, chi tiết), cũ trước: sự kiện tổng kết nuốt lô đứng ngay trước nó
    for row in reversed(rows):
        code, message = str(row["code"]), str(row["message"])
        item = {"id": f"e{row['id']}", "at": float(row["timestamp"] or 0), "level": str(row["level"]), "code": code, "text": message}
        details = _json(row["details_json"])
        field = _MACHINE_BATCH.get(code)
        if field is not None:
            batch: list[dict] = []
            for _ in range(int(details.get(field) or 0)):
                if not kept or kept[-1][0]["code"] != _SET_BY_LISTENER:
                    break
                batch.append(kept.pop()[1])
            text = _TELLER_EVENT_TEXT[code](message, {})
            who = ", ".join(sorted({person_name(str(entry.get("previous_speaker") or "")) for entry in batch} - {""})) or "người kể “tôi”"
            if code == "TELLER_THOUGHTS_TO_NARRATOR" and batch:
                text = f"Máy chuyển {len(batch)} câu nghĩ thầm của {who} sang giọng dẫn"
            elif batch and text:
                text += f"; máy cũng đưa {len(batch)} câu nghĩ thầm của {who} về giọng cũ"
            item["text"] = text or message
        elif code == "NARRATOR_ALIGNED_TO_TELLER":
            item["text"] = _teller_aligned(message, {}) or message
        kept.append((item, details))
    return [item for item, _details in reversed(kept)]


def event_text(code: str, message: str, chapters: dict[int, str]) -> str:
    handler = EVENT_TEXT.get(code)
    return handler(message, chapters) if handler else ""


def event_level(code: str, raw_level: str) -> str:
    return _EVENT_LEVEL.get(code, "error" if raw_level == "error" else "info")
