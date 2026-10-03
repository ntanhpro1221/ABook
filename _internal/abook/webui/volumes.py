"""Tạo nhiều tập cùng lúc (B7): ĐỀ XUẤT chỗ cắt một truyện dài thành các tập (light novel ra từng "Tập 1, Tập 2…").

Chỉ ĐỀ XUẤT - người dùng bấm "Chia thành nhiều tập" mới áp, và sửa được từng chỗ cắt theo số chương (không bao giờ tự chia
nguồn của người dùng). Ba nguồn gợi ý, theo thứ tự tin cậy:

- mỗi thư mục (hay mỗi file EPUB - `scan_inputs` tách EPUB thành một thư mục chương riêng) là một tập;
- tiêu đề chương gọi tên tập: "Tập 2", "Quyển 2", "Volume 2", "Vol. II", "Book 2", "第二卷"... - đoán từ dòng đầu của chương,
  rồi tên file (EPUB: tiêu đề mục lục là dòng đầu - txt_split.py gắn dòng "Tập N" vào chương đứng sau nó khi tách file TXT).

Hàm ở đây thuần (không đọc đĩa): chạy trên các dòng của `scan_inputs`. Cắt thật là `split_paths` - mỗi tập một danh sách
file, rồi `App.create` làm tập 1 như sách thường và các tập sau thành phần nối tiếp (server.py, continuation.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..io_utils import natural_key

MAX_VOLUME_LINE = 120  # dòng dài hơn là câu văn mở đầu bằng "Tập…", không phải tiêu đề tập
MAX_VOLUMES = 99

_WORDS = {
    "một": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_CJK_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# Dấu đầu dòng hay gặp quanh tiêu đề: "# Tập 2", "【Tập 2】", "*** Volume 2 ***", "[Quyển 2]".
_LEAD = r"^[\s#*_>=~·\-–—\[\]()（）【】〖〗『』「」《》<]*"
_NAMES = r"(?P<name>tập|tap|quyển|quyen|volume|vol|book|juan)"
_ROMAN = r"(?=[ivx])(?:x{0,3})(?:ix|iv|v?i{0,3})"
_NUMBER = (r"(?:(?P<digits>\d{1,3})|(?P<word>" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")|(?P<roman>" + _ROMAN + r"))")
VOLUME = re.compile(_LEAD + _NAMES + r"\b\.?\s*(?:thứ\s+)?[:.\-–—]?\s*" + _NUMBER + r"(?![\w])", re.IGNORECASE)
# 第二卷 (Hán), 第2巻 (Nhật): `卷`/`巻` là "tập"; 册/冊/集 cũng gặp ở truyện Trung.
VOLUME_CJK = re.compile(_LEAD + r"第\s*(?P<number>[\d零〇一二两三四五六七八九十百]+)\s*[卷巻册冊集]")
# Thư mục chương tách từ EPUB: "<tên file> - <8 ký tự băm>" (importers.extract).
_EPUB_FOLDER = re.compile(r"\s+-\s+[0-9a-f]{8}$")


def _roman(text: str) -> int:
    values = {"i": 1, "v": 5, "x": 10}
    total = 0
    for index, letter in enumerate(text.casefold()):
        value = values[letter]
        total += -value if index + 1 < len(text) and values[text[index + 1].casefold()] > value else value
    return total


def _cjk_number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        tens, _, ones = text.partition("十")
        try:
            return (_CJK_DIGITS[tens] if tens else 1) * 10 + (_CJK_DIGITS[ones] if ones else 0)
        except KeyError:
            return None
    return _CJK_DIGITS.get(text)


def volume_heading(line: str) -> tuple[str, int] | None:
    """(tên gọi, số tập) nếu dòng là tiêu đề một tập ("Tập 2 - Lời mở đầu" -> ("Tập", 2)); không thì None."""
    if len(line.strip()) > MAX_VOLUME_LINE:
        return None
    found = VOLUME.match(line)
    if found:
        if found["digits"]:
            number = int(found["digits"])
        elif found["word"]:
            number = _WORDS[found["word"].casefold()]
        else:
            number = _roman(found["roman"])
        name = found["name"].casefold()
        return ("Tập" if name == "tap" else "Quyển" if name == "quyen" else name.capitalize()), number
    found = VOLUME_CJK.match(line)
    if found:
        number = _cjk_number(found["number"])
        return ("Tập", number) if number else None
    return None


def is_volume_heading(line: str) -> bool:
    return volume_heading(line) is not None


def _volume_of(row: dict[str, Any]) -> tuple[str, int] | None:
    """Dòng đầu của chương nói nó mở một tập, hay không có thì tên file."""
    return volume_heading(str(row.get("firstLine") or "")) or volume_heading(str(row.get("name") or ""))


def _origin(row: dict[str, Any]) -> str:
    return str(Path(str(row["path"])).parent)


def _proposal(source: str, ordered: list[dict[str, Any]], starts: list[int], labels: list[str], original: list[dict[str, Any]]) -> dict[str, Any]:
    """`starts`: chỉ số 0 của chương đầu mỗi tập trong `ordered`; số chương trả về tính từ 1 (như cột số ở bước 1)."""
    ends = [*starts[1:], len(ordered)]
    reordered = [row["path"] for row in ordered] != [row["path"] for row in original]
    return {
        "source": source,
        # Thứ tự các chương khi chia (thư mục xếp theo tên tự nhiên); chỉ có khi khác thứ tự quét - nguồn nhiều thư mục bị
        # `scan_inputs` xếp xen theo tên file.
        "order": [row["path"] for row in ordered] if reordered else None,
        "volumes": [
            {
                "label": label,
                "start": start + 1,
                "startPath": ordered[start]["path"],
                "chapters": end - start,
                "firstTitle": str(ordered[start].get("firstLine") or ordered[start].get("title") or ""),
            }
            for label, start, end in zip(labels, starts, ends)
        ],
    }


def propose(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Đề xuất chia các chương đã quét (`scan_inputs()["files"]`) thành nhiều tập, hay None khi nguồn trông như MỘT tập.

    Mỗi thư mục / mỗi EPUB một tập (xếp theo tên tự nhiên: "Tập 2" trước "Tập 10"); không thì theo tiêu đề chương gọi tên
    tập - tập mới khi số tập TĂNG so với tập đang đọc ("Tập 1 - Chương 5" lặp ở mọi chương thì không thành chỗ cắt).
    """
    if len(rows) < 2:
        return None
    origins: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        origins.setdefault(_origin(row), []).append(row)
    if 2 <= len(origins) <= MAX_VOLUMES:
        folders = sorted(origins, key=lambda folder: natural_key(Path(folder).name))
        ordered = [row for folder in folders for row in origins[folder]]
        starts, position = [], 0
        for folder in folders:
            starts.append(position)
            position += len(origins[folder])
        names = [Path(folder).name for folder in folders]
        epubs = all(_EPUB_FOLDER.search(name) for name in names)
        labels = [(_EPUB_FOLDER.sub("", name).strip() or name) for name in names]
        return _proposal("epubs" if epubs else "folders", ordered, starts, labels, rows)

    starts = [0]
    word = ""
    current: int | None = None
    for index, row in enumerate(rows):
        found = _volume_of(row)
        if found is None:
            continue
        name, number = found
        word = word or name
        if current is None:
            current = number
            # Chữ đứng trước tiêu đề "Tập 1" (lời giới thiệu) thuộc tập 1; trước "Tập 3" thì là tập khác.
            if index and number > 1:
                starts.append(index)
        elif number > current:
            current = number
            starts.append(index)
    if len(starts) < 2 or len(starts) > MAX_VOLUMES:
        return None
    return _proposal("headings", rows, starts, _heading_labels(rows, starts, word), rows)


def _heading_labels(rows: list[dict[str, Any]], starts: list[int], word: str) -> list[str]:
    labels: list[str] = []
    for position, start in enumerate(starts):
        found = _volume_of(rows[start])
        labels.append(f"{found[0]} {found[1]}" if found else f"{word} {position + 1}")
    return labels


def split_paths(paths: list[str], starts: list[Any] | None) -> list[list[str]]:
    """Các tập từ danh sách `paths` và số chương đầu của mỗi tập (từ 1: [1, 121, 300]). Không có `starts` thì một tập."""
    if not starts:
        return [list(paths)]
    try:
        cuts = [int(start) for start in starts]
    except (TypeError, ValueError) as error:
        raise ValueError("Chỗ cắt tập phải là số chương") from error
    if cuts[0] != 1:
        raise ValueError("Tập đầu phải bắt đầu từ chương 1")
    if any(later <= earlier for earlier, later in zip(cuts, cuts[1:])):
        raise ValueError("Chỗ cắt các tập phải tăng dần, mỗi tập có ít nhất một chương")
    if cuts[-1] > len(paths):
        raise ValueError(f"Chỗ cắt chương {cuts[-1]} vượt quá số chương ({len(paths)})")
    if len(cuts) > MAX_VOLUMES:
        raise ValueError(f"Tối đa {MAX_VOLUMES} tập")
    return [list(paths[start - 1:end - 1]) for start, end in zip(cuts, [*cuts[1:], len(paths) + 1])]


def reading_order_problem(volume: list[str]) -> bool:
    """Thứ tự đọc của một tập không giữ được: dây chuyền xếp chương theo TÊN file (text_processing.build_chapter_manifest), nên
    một tập gồm file của nhiều thư mục chỉ đúng khi xếp theo tên vẫn ra đúng thứ tự đã cho - "001.txt" của hai thư mục thì
    không."""
    names = [tuple(natural_key(Path(path).name)) for path in volume]
    return names != sorted(names) or len(set(names)) != len(names)


def localize_chapters(chapters: dict[str, str] | None, offset: int, size: int) -> dict[str, str] | None:
    """Người xưng "tôi" theo chương (`firstPersonChapters`, số chương tính cả truyện) -> số chương trong một tập: tập bắt
    đầu sau `offset` chương và có `size` chương."""
    if not chapters:
        return None
    local: dict[str, str] = {}
    for key, name in chapters.items():
        if not str(key).strip().isdigit():
            local[str(key)] = name  # không phải số chương: để `create_book` từ chối như với sách một tập
        elif 1 <= int(key) - offset <= size:
            local[str(int(key) - offset)] = name
    return local or None
