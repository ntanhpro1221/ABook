"""Chạy host Python của ABook trên một thư viện thử, in địa chỉ + mã phiên + mã các cuốn nghe được ra file JSON rồi đứng đó tới khi bị dừng.
  python -X utf8 hostserve.py <fixture dir> <info.json>
Dùng cho các phép đo ngoài app (audiobench)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from make_fixture import Host  # noqa: E402

fixture = Path(sys.argv[1])
host = Host(fixture / "prefs.json")
books = json.loads((fixture / "audio_books.json").read_text(encoding="utf-8")) if (fixture / "audio_books.json").exists() else {}
Path(sys.argv[2]).write_bytes(json.dumps({"base": host.base, "token": host.token, "books": books}).encode("utf-8"))
try:
    while True:
        time.sleep(5)
finally:
    host.stop()
