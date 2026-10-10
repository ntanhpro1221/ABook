from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Iterator


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def discover_txt_files(directory: Path) -> list[Path]:
    """Return direct child TXT files in deterministic natural order.

    Folder import is intentionally non-recursive so selecting a book folder cannot
    silently pull unrelated TXT files from nested metadata, backup, or output folders.
    """
    directory = directory.expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(directory)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    # Tên bằng nhau theo thứ tự tự nhiên ("1.txt" và "01.txt") xếp theo tên gốc - không theo thứ tự hệ thống tệp liệt kê, vốn
    # khác nhau giữa các máy (app điện thoại cũng xếp như vậy: BookImport.naturalOrder).
    return sorted(
        (path.resolve() for path in directory.iterdir() if path.is_file() and path.suffix.casefold() == ".txt"),
        key=lambda path: (natural_key(path.name), path.name),
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


LONE_SURROGATE_PATTERN = re.compile("[\ud800-\udfff]")


def strip_lone_surrogates(text: str) -> str:
    """Bỏ những code point là **một nửa** của cặp surrogate.

    Đặt ở đây chứ không ở `analysis.py` vì đã có **hai** nguồn cần nó: phản hồi Ollama và
    transcript của Whisper. Cả hai là văn bản do model sinh ra, và cả hai đều tạo ra được một
    `str` hợp lệ trong bộ nhớ mà **không mã hoá UTF-8 được** - thứ giết lô 1 ngày 2026-09-08
    ngay dưới đây ở `sha256_text`, và cũng bị chính sqlite từ chối lúc `INSERT`.

    Xoá đúng khoảng D800-DFFF: mọi cặp hợp lệ đã được bộ giải mã ghép thành ký tự thật, nên
    thứ còn sót trong khoảng ấy chắc chắn là nửa lạc.
    """
    return LONE_SURROGATE_PATTERN.sub("", text)


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def stable_int(text: str, low: int = 1, high: int = 2_147_483_000) -> int:
    if high <= low:
        return low
    value = int(hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16], 16)
    return low + (value % (high - low))


def slugify(text: str, max_length: int = 90) -> str:
    import unicodedata

    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return (text[:max_length] or "item").lower()


def decode_text_bytes(raw: bytes) -> str:
    return decode_text(raw)[0]


# Chữ Việt có dấu (NFC, hoa lẫn thường); chữ CHỈ tiếng Việt có (ạ ả ấ…, ư, đ, ĩ, ũ) - Bồ Đào Nha đọc nhầm qua cp1258 chỉ ra ă / ơ.
VIET_LETTERS = frozenset(
    unicodedata.normalize("NFC", base + tone)
    for vowel in "aăâeêioôơuưy"
    for base in (vowel, vowel.upper())
    for tone in ("", "̀", "́", "̉", "̃", "̣")
) | {"đ", "Đ"}
VIET_ONLY = frozenset(char for char in VIET_LETTERS if ord(char) >= 0x1EA0) | set("đĐưƯĩĨũŨ")
VIET_WORD_MAX = 7  # âm tiết dài nhất: "nghiêng"
VIET_PLAUSIBLE = 0.9  # từ có dấu là âm tiết Việt được
VIET_ONLY_SHARE = 0.2  # từ có dấu mang chữ chỉ tiếng Việt có
LATIN_RUN_MAX = 3  # chữ Tây Âu: dấu nằm rải rác giữa chữ ASCII ("ação"); chữ Trung đọc nhầm qua cp1252 ra cả chuỗi dài "ÄãºÃ"
LATIN_MARKS = frozenset("“”‘’–—…«»°·€©®™§¡¿")
CJK = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))
CJK_MARKS = ((0x3000, 0x303F), (0xFF00, 0xFFEF))


def _letter_runs(text: str) -> Iterator[str]:
    word: list[str] = []
    for char in text:
        if char.isalpha() or unicodedata.category(char) == "Mn":
            word.append(char)
        elif word:
            yield "".join(word)
            word = []
    if word:
        yield "".join(word)


def looks_vietnamese(text: str) -> bool:
    """cp1258 nhận gần như mọi byte, nên chỉ tin nó khi chữ ra trông như tiếng Việt: gần hết từ có dấu là âm tiết Việt được (chỉ chữ
    Việt, không dấu rời, <= 7 chữ) và đủ từ mang chữ chỉ tiếng Việt có."""
    accented = plausible = only = 0
    for word in _letter_runs(text):
        if word.isascii():
            continue
        accented += 1
        plausible += len(word) <= VIET_WORD_MAX and all(char.isascii() or char in VIET_LETTERS for char in word)
        only += any(char in VIET_ONLY for char in word)
    return accented == 0 or (plausible >= VIET_PLAUSIBLE * accented and only >= VIET_ONLY_SHARE * accented)


def _in(code: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(low <= code <= high for low, high in ranges)


def encoding_score(text: str, encoding: str) -> int:
    """Chữ ra trông thật đến đâu (chữ đúng trừ hai lần chữ lạ). gb18030: chữ Hán / dấu câu Hán, không dính chữ ASCII ("n中o" là chữ Tây
    đọc nhầm). cp1252: chuỗi ký tự ngoài ASCII ngắn, toàn chữ cái / dấu câu Tây Âu."""
    good = bad = 0
    if encoding == "gb18030":
        for index, char in enumerate(text):
            code = ord(char)
            if code < 0x80:
                continue
            near = text[index - 1:index] if index else ""
            near += text[index + 1:index + 2]
            if _in(code, CJK) and not any(other.isascii() and other.isalpha() for other in near) or _in(code, CJK_MARKS):
                good += 1
            else:
                bad += 1
        return good - 2 * bad
    run: list[str] = []
    for char in text + "\n":
        if ord(char) >= 0x80:
            run.append(char)
            continue
        if run:
            if len(run) <= LATIN_RUN_MAX and all(other.isalpha() or other in LATIN_MARKS for other in run):
                good += len(run)
            else:
                bad += len(run)
            run = []
    return good - 2 * bad


def decode_text(raw: bytes) -> tuple[str, str]:
    """(chữ NFC, bảng mã). UTF-16 (BOM, hay nhiều byte 0), UTF-8 (có / không BOM); không thì cp1258 khi chữ ra trông như tiếng Việt
    (`looks_vietnamese`), còn lại cp1252 hay gb18030 theo `encoding_score` - không im lặng ra chữ rác vì cp1258 nhận mọi byte."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return unicodedata.normalize("NFC", raw.decode("utf-16")), "utf-16"

    encodings = ["utf-8-sig", "utf-8"]
    if raw:
        even_nuls = raw[0::2].count(0)
        odd_nuls = raw[1::2].count(0)
        nul_ratio = (even_nuls + odd_nuls) / len(raw)
        if nul_ratio >= 0.2:
            utf16_encoding = "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"
            encodings.insert(0, utf16_encoding)

    for encoding in encodings:
        text = _strict(raw, encoding)
        if text is not None:
            return text, encoding
    guesses = {encoding: text for encoding in ("cp1258", "windows-1252", "gb18030") if (text := _strict(raw, encoding)) is not None}
    if "cp1258" in guesses and looks_vietnamese(guesses["cp1258"]):
        return guesses["cp1258"], "cp1258"
    scored = [(encoding_score(guesses[encoding], encoding), encoding) for encoding in ("windows-1252", "gb18030") if encoding in guesses]
    if scored:
        encoding = max(scored, key=lambda pair: pair[0])[1]  # hoà điểm: cp1252 (đứng trước)
        return guesses[encoding], encoding
    if "cp1258" in guesses:
        return guesses["cp1258"], "cp1258"
    return unicodedata.normalize("NFC", raw.decode("utf-8", errors="replace")), "utf-8"


def _strict(raw: bytes, encoding: str) -> str | None:
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        return None
    return None if "�" in text else unicodedata.normalize("NFC", text)


REPLACE_RETRY_ATTEMPTS = 12
REPLACE_RETRY_DELAY_SECONDS = 0.05


def _replace_with_retry(temp: Path, path: Path) -> None:
    """os.replace, but survive a reader holding the destination open.

    On Windows a rename onto an open file fails with PermissionError (WinError 5), and
    every reader of these files opens them the ordinary way - so *reading* a state file can
    break the process writing it. It is not hypothetical: alpha.50 died 44 minutes into its
    analysis on

        PermissionError: [WinError 5] Access is denied:
        'runtime/background/state.json.part' -> 'runtime/background/state.json'

    because a script was polling that state file every 15 seconds. `cli status` reads the
    same file, so a person checking on their own run could have done it just as easily.

    The window is microseconds wide, so retrying briefly closes it: twelve attempts across
    about 0.6s. If it still fails the error is raised unchanged, because a rename that is
    blocked for that long is not this race.
    """
    for attempt in range(REPLACE_RETRY_ATTEMPTS):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == REPLACE_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_RETRY_DELAY_SECONDS)


def atomic_write_bytes(path: Path, data: bytes, *, fsync: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        if fsync:
            os.fsync(handle.fileno())
    _replace_with_retry(temp, path)


def atomic_write_json(path: Path, data: Any, *, fsync: bool = True) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write_bytes(path, payload, fsync=fsync)


def atomic_write_text(path: Path, text: str, *, fsync: bool = True) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), fsync=fsync)


def remove_part_files(
    root: Path,
    *,
    excluded_roots: Iterable[Path] = (),
) -> list[Path]:
    removed: list[Path] = []
    if not root.exists():
        return removed
    excluded = tuple(path.resolve() for path in excluded_roots)

    def is_excluded(path: Path) -> bool:
        resolved = path.resolve()
        return any(resolved == item or resolved.is_relative_to(item) for item in excluded)

    for path in root.rglob("*.part"):
        if is_excluded(path):
            continue
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    for path in root.rglob("*.part.*"):
        if is_excluded(path):
            continue
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed


_downloaded_ffmpeg: Path | None = None


def use_downloaded_ffmpeg(path: Path | str | None) -> None:
    """Đăng ký ffmpeg tải về lúc chạy (webui/ffmpeg_setup.py: bản app chỉ-nghe không mang ffmpeg); None = gỡ."""
    global _downloaded_ffmpeg
    _downloaded_ffmpeg = Path(path) if path is not None else None


def ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if _downloaded_ffmpeg is not None and _downloaded_ffmpeg.is_file():
        return str(_downloaded_ffmpeg)
    found = shutil.which("ffmpeg")
    if found:
        return found
    return "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def ffmpeg_available() -> bool:
    """Có ffmpeg dùng được ngay không (imageio_ffmpeg, bản đã tải, hay trong PATH). Rẻ: không chạy tiến trình nào."""
    return Path(ffmpeg_executable()).is_file()


def run_hidden(command: Iterable[str], *, timeout: float | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
