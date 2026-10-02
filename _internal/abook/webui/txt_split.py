"""Một file TXT chứa CẢ truyện (soát UX a5 01-10: truyện tải trên mạng phần lớn là một file như vậy; trình tạo sách đọc
ra MỘT chương 3 tiếng, không một lời nhắc). Trình tạo sách ĐỀ XUẤT tách theo các dòng tiêu đề "Chương N" - mặc định không
tách, người dùng bấm mới tách (không bao giờ tự sửa nguồn của người dùng). Tách thì ghi các chương ra một thư mục MỚI trong
thư viện, file gốc giữ nguyên, rồi trình tạo sách quét thư mục ấy như mọi thư mục chương."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ..io_utils import decode_text_bytes

# Số của chương: chữ số, số La Mã, hay số viết bằng chữ ("Chương Một", "Hồi thứ hai").
_NUMBER_WORDS = (
    "một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mốt|trăm|nghìn|ngàn|linh|lẻ|"
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
)
HEADING = re.compile(
    r"^\s*(?:"
    r"(?:chương|chuong|hồi|hoi|chapter|tiết)\s+(?:thứ\s+)?(?:\d+|[ivxlcdm]+|(?:(?:" + _NUMBER_WORDS + r")\s*)+)(?![\w])"
    r"|第\s*[\d一二三四五六七八九十百千零〇两]+\s*[章回]"
    r")",
    re.IGNORECASE,
)
MAX_HEADING = 120  # dòng dài hơn là một câu văn mở đầu bằng "Chương…", không phải tiêu đề
PREAMBLE = "Mở đầu"
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _lines(path: Path) -> list[str]:
    return decode_text_bytes(path.read_bytes()).replace("\r\n", "\n").replace("\r", "\n").split("\n")


def headings(lines: list[str]) -> list[int]:
    """Chỉ số các dòng là tiêu đề chương."""
    return [index for index, line in enumerate(lines) if len(line.strip()) <= MAX_HEADING and HEADING.match(line)]


def plan(path: Path) -> dict[str, Any] | None:
    """Đề xuất tách một file: số chương sẽ ra và vài tiêu đề đầu, hay None khi file chỉ là một chương (ít hơn hai tiêu đề)."""
    try:
        lines = _lines(path)
    except OSError:
        return None
    found = headings(lines)
    if len(found) < 2:
        return None
    preamble = any(line.strip() for line in lines[: found[0]])
    return {
        "chapters": len(found) + (1 if preamble else 0),
        "titles": [lines[index].strip() for index in found[:3]],
        # Chữ trước tiêu đề đầu tiên (tên truyện, lời giới thiệu, ghi công) thành một chương riêng "Mở đầu" - không bỏ đi.
        "preamble": preamble,
    }


def split(path: Path, root: Path) -> Path:
    """Ghi các chương của `path` thành từng file TXT (UTF-8) trong một thư mục mới dưới `root`, trả thư mục ấy:
    `<root>/<băm nội dung>/<tên file>` - tách lại cùng file thì dùng lại thư mục, file khác cùng tên không đè lên nhau, và
    tên thư mục chương vẫn là tên truyện (trình tạo sách gợi ý tên sách theo nó). Chữ giữ nguyên từng dòng - chỉ cắt ở
    đầu các dòng tiêu đề."""
    raw = path.read_bytes()
    lines = _lines(path)
    found = headings(lines)
    if len(found) < 2:
        raise ValueError("File này không có đủ tiêu đề chương để tách")
    stem = " ".join(_UNSAFE_NAME.sub(" ", path.stem).split()).strip(" .")[:80] or "truyen"
    folder = root / hashlib.sha256(raw).hexdigest()[:8] / stem
    if folder.is_dir() and any(folder.glob("*.txt")):
        return folder
    width = max(4, len(str(len(found))))
    parts: list[tuple[str, list[str]]] = []
    if any(line.strip() for line in lines[: found[0]]):
        parts.append((PREAMBLE, lines[: found[0]]))
    for position, start in enumerate(found):
        end = found[position + 1] if position + 1 < len(found) else len(lines)
        parts.append((lines[start].strip(), lines[start:end]))
    folder.mkdir(parents=True, exist_ok=True)
    first = 0 if parts[0][0] == PREAMBLE else 1
    for index, (title, body) in enumerate(parts, start=first):
        label = " ".join(_UNSAFE_NAME.sub(" ", title).split())[:50].strip(" .")
        text = "\n".join(body).strip("\n") + "\n"
        (folder / f"{index:0{width}d}{' ' + label if label else ''}.txt").write_bytes(text.encode("utf-8"))
    return folder
