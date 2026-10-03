"""Dựng từ điển phát âm GỌN cho `abook/english_vi.py` (Việt hoá từ tiếng Anh): `abook/assets/english_phones.txt.gz`.

Nguồn: `abook/assets/cmudict.dict` (CMU Pronouncing Dictionary, BSD - `CMUDICT_LICENSE.txt`), đọc bằng `analysis._cmudict_entries` (cách
đọc đầu tiên của mỗi từ). Chỉ giữ từ toàn chữ a-z; mỗi dòng "từ PHONES" (ARPAbet, số nhấn ở nguyên âm), xếp theo từ, gzip mức 9 với
mtime 0 nên dựng lại ra đúng từng byte. Bản máy tính đóng kèm file này (cmudict.dict là dữ liệu của Studio, tải riêng); điện thoại tải
theo yêu cầu (`EnglishVi.loadPhones`).

    runtime/.venv/Scripts/python.exe scripts/build_english_phones.py
"""
from __future__ import annotations

import gzip
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from abook.analysis import CMUDICT_PATH, _cmudict_entries
from abook.english_vi import PHONES_PATH


def phones_bytes() -> bytes:
    entries = _cmudict_entries()
    lines = [f"{word} {phones}\n" for word, phones in sorted(entries.items()) if word.isascii() and word.isalpha()]
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as handle:
        handle.write("".join(lines).encode("utf-8"))
    return buffer.getvalue()


def main() -> None:
    data = phones_bytes()
    PHONES_PATH.write_bytes(data)
    raw = len(gzip.decompress(data))
    print(f"{CMUDICT_PATH.stat().st_size:,} B cmudict.dict -> {raw:,} B gọn -> {len(data):,} B gzip: {PHONES_PATH}")


if __name__ == "__main__":
    main()
