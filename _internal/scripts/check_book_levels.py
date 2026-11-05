"""Đo gói sách ở chế độ chỉ đọc; JSON ra stdout không mang chữ/audio."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from abook.book_levels import measure_package

if __name__ == "__main__":
    print(json.dumps(measure_package(Path(sys.argv[1])), ensure_ascii=False, indent=2))
