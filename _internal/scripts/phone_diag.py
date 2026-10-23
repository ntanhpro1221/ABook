"""Đọc nhật ký + trạng thái của điện thoại đã ghép, qua mạng bất kỳ (LAN, Tailscale, 4G), KHÔNG cần adb.

    runtime/.venv/Scripts/python.exe scripts/phone_diag.py                       # liệt kê máy đã ghép
    runtime/.venv/Scripts/python.exe scripts/phone_diag.py --device Pixel        # tóm tắt + 40 dòng nhật ký cuối
    runtime/.venv/Scripts/python.exe scripts/phone_diag.py --device a1b2c3d4e5f6 --lines 5000 --out nhat-ky.json

Dùng đúng thư viện máy đã ghép của app máy tính (`computers.json` cạnh tuỳ chọn của app; `ABOOK_PREFERENCES` đổi chỗ) và đúng đường
`remote_books.diagnostics` (TLS ghim vân tay, cùng mã thiết bị) nên đi được nơi app đi được. Điện thoại phải mở ABook và bật
"Cho máy khác nghe thư viện này" (cổng đồng bộ); bản ABook trên điện thoại phải có đường chẩn đoán. Chỉ đọc: không ghi gì lên điện thoại.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from abook.webui import remote_books  # noqa: E402
from abook.webui.library import preferences_path  # noqa: E402

TAIL_PRINTED = 40


def find(computers: remote_books.Computers, wanted: str) -> dict[str, Any] | None:
    """Máy đã ghép theo mã 12 ký tự (hay đầu mã), hoặc theo tên (không phân biệt hoa thường, khớp đầu tên hay một phần)."""
    listed = computers.list()
    wanted = wanted.strip().casefold()
    for test in (lambda item: str(item["id"]).casefold() == wanted,
                 lambda item: str(item["id"]).casefold().startswith(wanted),
                 lambda item: str(item.get("name") or "").casefold() == wanted,
                 lambda item: wanted in str(item.get("name") or "").casefold()):
        hits = [item for item in listed if test(item)]
        if len(hits) == 1:
            return hits[0]
    return None


def summary(report: dict[str, Any], tail: int = TAIL_PRINTED) -> list[str]:
    """Các dòng tóm tắt (mỗi mục có thì in, thiếu thì bỏ) rồi `tail` dòng nhật ký cuối."""
    lines: list[str] = []
    for key, value in report.items():
        if key in {"log", "logcat", "crashes", "fetchedAt"}:
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    for key in ("crashes",):
        if report.get(key):
            lines.append(f"{key}: {len(report[key])} file")
    log = report.get("log")
    log = log if isinstance(log, list) else str(log or "").splitlines()
    lines.append(f"--- {len(log)} dòng nhật ký (in {min(tail, len(log))} dòng cuối) ---")
    lines.extend(str(line) for line in log[-tail:])
    return lines


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")  # bảng mã Windows (cp1252) không in được tiếng Việt
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--device", help="tên (hay một phần tên) hoặc mã 12 ký tự của máy đã ghép")
    parser.add_argument("--lines", type=int, default=remote_books.DIAGNOSTICS_LINES, help="số dòng nhật ký cuối cần lấy")
    parser.add_argument("--out", type=Path, help="ghi nguyên bản JSON vào file này")
    args = parser.parse_args(argv)
    computers = remote_books.Computers(preferences_path().with_name("computers.json"))
    remote_books.configure(computers)
    if not args.device:
        for item in computers.list():
            print(f"{item['id']}  {item.get('kind') or '?':8}  {item.get('name')}")
        return 0
    entry = find(computers, args.device)
    if entry is None:
        print(f"Không thấy máy đã ghép nào khớp “{args.device}” (chạy không kèm --device để xem danh sách)")
        return 2
    started = time.time()
    try:
        report = remote_books.diagnostics(str(entry["id"]), args.lines)
    except remote_books.RemoteError as error:
        print(f"Không đọc được chẩn đoán của {entry.get('name')}: {error}")
        return 1
    print(f"{entry.get('name')} trả lời sau {time.time() - started:.1f} giây")
    print("\n".join(summary(report)))
    if args.out:
        args.out.write_bytes(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))  # LF, không CRLF của Windows
        print(f"Đã ghi {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
