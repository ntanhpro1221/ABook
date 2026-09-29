"""Cuối lượt v6b: 4 chương "nhắm lỗi" (LU 03, Nageki 53, TCF 107, Yamiyo 009) có hại không - quyết thành phần dữ liệu cho
v7, v8, q35 (các lượt sau đọc composition.txt lúc bắt đầu).

Luật đặt TRƯỚC khi có số (29-09 07:3x): F1 giọng GỘP 12 chương LN (6 gốc + 6 mở rộng) của v6b cao hơn v6 từ 1,0 điểm trở lên
-> bỏ 4 chương (hậu tố "b": data_v7b/data_v8b); ngược lại giữ (hậu tố ""). Thiếu số (lượt hỏng, thiếu chương) -> giữ.
Căn cứ: trên 6 chương gốc v6 thua v3 1,7 F1 và câu 『』 tụt 43,6% -> 23,1% (TCF 042: 『』 là lời kể, v6 gán cho KUCHINASHI
sau khi học TCF 107 nơi 『』 là "ký sinh trùng" nói).
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PY = "D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe"
THRESHOLD = 1.0


def pooled() -> dict[str, tuple[float, int]]:
    out = subprocess.run([PY, str(HERE / "lnx_table.py"), "v6=29-09-ln-lora6,29-09-lnx-lora6",
                          "v6b=29-09-ln-lora6b,29-09-lnx-lora6b"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=str(HERE), env={"PYTHONIOENCODING": "utf-8", "SYSTEMROOT": "C:\\Windows"}).stdout
    found = {}
    for line in out.splitlines():
        match = re.match(r"\| (v6b?) \|.*\| ([0-9.]+)% \((\d+) câu, (\d+) chương\)", line)
        if match:
            found[match.group(1)] = (float(match.group(2)), int(match.group(4)))
    print(out[-1500:])
    return found


def main() -> int:
    found = pooled()
    choice = ""
    if "v6" in found and "v6b" in found and found["v6"][1] == found["v6b"][1] == 12:
        gain = found["v6b"][0] - found["v6"][0]
        choice = "b" if gain >= THRESHOLD else ""
        verdict = f"v6b {found['v6b'][0]:.1f} - v6 {found['v6'][0]:.1f} = {gain:+.1f} F1"
    else:
        verdict = f"thiếu số ({found}) - giữ nguyên thành phần"
    (HERE / "composition.txt").write_text(choice, encoding="utf-8")
    print(f"THÀNH PHẦN: {'bỏ 4 chương (b)' if choice else 'giữ 4 chương'} - {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
