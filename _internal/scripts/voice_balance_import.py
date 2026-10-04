"""Thả số đo thật vào bảng cân bằng giọng (`abook/assets/voice_balance.json`).

    python scripts/voice_balance_import.py <rates.json> <gains.json> [--create] [--dry-run]

Chạy từ thư mục `_internal`. Định dạng vào (GIẢ ĐỊNH - đổi ở đây nếu máy đo ghi khác):

rates.json - tốc độ đo ở tốc độ gốc của giọng (chưa áp tempo), trên câu trung tính:

    {"median_syll_per_s": 4.56,
     "voices": {"vieneu@3.8.1/Đức Trí/f100": {"syll_per_s": 4.15},
                "vieneu@3.8.1/Mỹ Duyên/f100": {"r": 1.0}}}

  `r = median_syll_per_s / syll_per_s`. Giọng có sẵn `r` thì dùng thẳng `r` (để ghim hằng số chủ sách
  đã chọn bằng tai, không cho số đo ghi đè). `median_syll_per_s` là trung vị của các giọng trên một
  trục, chỉ cần khi có giọng khai `syll_per_s`.

gains.json - độ to đo trên bản thô SAU cao độ và tempo (WORLD kéo tốc độ làm đổi độ to):

    {"voices": {"vieneu@3.8.1/Đức Trí/f100": {"lufs": -19.4, "o_db": 0.0}}}

  `lufs` -> `ref_lufs` (LUFS trung bình của bản thô, bắt buộc); `o_db` là độ lệch riêng thêm vào, tuỳ
  chọn (không ghi thì giữ giá trị hiện có).

Khoá là `voice_balance.voice_key(...)`. Một khoá chưa có trong bảng là LỖI, trừ khi có `--create`
(giọng mới: khi đó `pitch_st` lấy 0 cho tới khi ai đó đặt). `pitch_st` không bao giờ được đo hay đề xuất
ở đây. Các núm chung `x`, `L_lufs`, `pace_floor_scale`, `engine_pace_floor` và trường `engine_speed` của máy tự đọc theo tốc độ
(Supertonic) sửa tay trong file json; script giữ nguyên chúng.

Sau khi ghi, bảng được nạp lại và kiểm (`voice_balance.load_table`) - số hỏng thì file không bị đổi. Hash
chất lượng (`quality_implementation_hash`) đổi: chỉ thả số khi không có lượt sản xuất nào đang chạy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abook import voice_balance  # noqa: E402


def _read(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("voices"), dict):
        raise SystemExit(f"{path}: cần object có khoá 'voices'")
    return data


def merge(
    table: dict[str, Any],
    rates: dict[str, Any],
    gains: dict[str, Any],
    *,
    create: bool = False,
) -> list[str]:
    """Ghi số đo vào `table` (sửa tại chỗ). Trả danh sách khoá đã đổi."""
    voices = table["voices"]
    median = rates.get("median_syll_per_s")
    touched: list[str] = []

    def record(key: str) -> dict[str, Any]:
        if key in voices:
            return voices[key]
        if not create:
            raise SystemExit(f"{key}: chưa có trong bảng (thêm --create nếu đây là giọng mới)")
        voices[key] = {"r": 1.0, "o_db": 0.0, "ref_lufs": -19.8, "pitch_st": 0}
        return voices[key]

    for key, item in rates["voices"].items():
        entry = record(key)
        if "r" in item:
            entry["r"] = round(float(item["r"]), 4)
        elif "syll_per_s" in item:
            if not median:
                raise SystemExit("rates.json: giọng khai syll_per_s nhưng thiếu median_syll_per_s")
            entry["r"] = round(float(median) / float(item["syll_per_s"]), 4)
        else:
            raise SystemExit(f"{key}: cần 'r' hoặc 'syll_per_s'")
        touched.append(key)
    for key, item in gains["voices"].items():
        entry = record(key)
        if "lufs" not in item:
            raise SystemExit(f"{key}: cần 'lufs'")
        entry["ref_lufs"] = round(float(item["lufs"]), 2)
        if "o_db" in item:
            entry["o_db"] = round(float(item["o_db"]), 2)
        touched.append(key)
    return touched


def render(table: dict[str, Any]) -> bytes:
    """Cùng dạng với file gốc: núm chung ở đầu, mỗi giọng một dòng, khoá xếp theo thứ tự."""
    head = [
        f'  "version": {json.dumps(table["version"])}',
        f'  "engine_versions": {json.dumps(table["engine_versions"], ensure_ascii=False)}',
        f'  "x": {json.dumps(table["x"])}',
        f'  "L_lufs": {json.dumps(table["L_lufs"])}',
        f'  "pace_floor_scale": {json.dumps(table["pace_floor_scale"])}',
    ]
    if "engine_pace_floor" in table:
        head.append(f'  "engine_pace_floor": {json.dumps(table["engine_pace_floor"], ensure_ascii=False)}')
    lines = [
        f"    {json.dumps(key, ensure_ascii=False)}: "
        + json.dumps(table["voices"][key], ensure_ascii=False)
        for key in sorted(table["voices"])
    ]
    text = "{\n" + ",\n".join(head) + ',\n  "voices": {\n' + ",\n".join(lines) + "\n  }\n}\n"
    return text.encode("utf-8")  # LF, không đi qua write_text (Windows ghi CRLF)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("rates")
    parser.add_argument("gains")
    parser.add_argument("--create", action="store_true", help="cho phép thêm giọng chưa có trong bảng")
    parser.add_argument("--dry-run", action="store_true", help="kiểm và in số khoá đổi, không ghi file")
    args = parser.parse_args(argv)

    table = json.loads(voice_balance.TABLE_PATH.read_text(encoding="utf-8"))
    touched = merge(table, _read(args.rates), _read(args.gains), create=args.create)
    data = render(table)
    voice_balance._validate(json.loads(data.decode("utf-8")))  # báo lỗi trước khi ghi
    if not args.dry_run:
        voice_balance.TABLE_PATH.write_bytes(data)
        voice_balance.reload_table()
    print(f"{len(set(touched))} giọng {'sẽ đổi' if args.dry_run else 'đã đổi'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
