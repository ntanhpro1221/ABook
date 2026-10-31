"""Máy dò luật chủ sách "không bao giờ cắt chữ của người dùng": báo lỗi khi QML có chỗ cắt chữ.

Cấm trên mọi phần tử:      elide khác Text.ElideNone, maximumLineCount, truncate
Cấm trên phần tử chữ:      clip: true  (Text / Label / TextEdit / TextInput - chữ tràn thì phải xuống dòng hay thu cỡ, không xén)
Chữ dài thì: wrapMode: Text.Wrap (hàng/ô cao theo chữ) hoặc fontSizeMode: Text.Fit + minimumPixelSize (bìa vẽ).
Ngoại lệ có chủ đích: dòng có chú thích  // text-cut-ok: <lý do>  (chỉ cho chữ KHÔNG phải của người dùng).

  python -X utf8 check_text_cut.py [thư mục qml]       thoát 1 nếu có vi phạm (build.bat chạy nó như gen_theme --check)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NL = chr(10)
TEXT_TYPES = {"Text", "Label", "TextEdit", "TextInput"}
BANNED_ANY = [
    (re.compile(r"^elide$"), lambda v: v.replace(" ", "") != "Text.ElideNone", "elide cắt chữ bằng dấu ..."),
    (re.compile(r"^maximumLineCount$"), lambda v: True, "maximumLineCount cắt bớt dòng"),
    (re.compile(r"^truncate$"), lambda v: True, "truncate cắt chữ"),
]


def strip_noise(src: str) -> str:
    """Thay chuỗi và chú thích bằng khoảng trắng (giữ nguyên độ dài và xuống dòng để số dòng không lệch)."""
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(c + "".join(ch if ch == "\n" else " " for ch in src[i + 1:j]) + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def scan(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    raw_lines = raw.split("\n")
    text = strip_noise(raw)
    text = re.sub(r"^[ \t]*(import|pragma)\b[^\n]*$", lambda m: " " * len(m.group()), text, flags=re.M)   # import / pragma không phải mệnh đề
    errors: list[str] = []
    # Duyệt ký tự, giữ ngăn xếp khối: ("type", Tên) phần tử, ("group", tên) thuộc tính nhóm (font { }), ("js", None) khối lệnh
    stack: list[tuple[str, str | None]] = []
    i, n = 0, len(text)
    token_start = 0          # đầu "mệnh đề" hiện tại (sau { ; hoặc xuống dòng ở mức phần tử)
    line = 1

    def clause_end_handler(clause: str, start: int) -> None:
        ln = text.count(NL, 0, start + len(clause) - len(clause.lstrip())) + 1     # dòng của chữ đầu mệnh đề
        m = re.match(r"^\s*([A-Za-z_][\w.]*)\s*:\s*(.*)$", clause, re.S)
        if not m or not stack or stack[-1][0] not in ("type", "group"):
            return
        name, value = m.group(1), m.group(2).strip()
        base = name.split(".")[-1]
        owner = next((t[1] for t in reversed(stack) if t[0] == "type"), None)
        marker = raw_lines[ln - 1] if 0 < ln <= len(raw_lines) else ""
        if "text-cut-ok" in marker:
            return
        for pattern, bad, why in BANNED_ANY:
            if pattern.match(base) and bad(value):
                errors.append(f"{path}:{ln}: {why} ({owner or '?'} {{ {name}: {value[:40]} }})")
        if base == "clip" and value == "true" and owner in TEXT_TYPES:
            errors.append(f"{path}:{ln}: clip: true trên {owner} xén chữ ({owner} {{ clip: true }})")

    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
        if c == "{":
            head = text[token_start:i]
            hm = re.search(r"([A-Za-z_][\w.]*)\s*$", head)
            before = head[:hm.start()] if hm else head
            if hm and re.search(r":\s*$", before) is None and re.match(r"^\s*$", before.rsplit(";", 1)[-1]) is not None and hm.group(1)[0].isupper():
                stack.append(("type", hm.group(1)))                 # "Text {"
            elif hm and re.search(r":\s*$", before) is not None and hm.group(1)[0].isupper():
                stack.append(("type", hm.group(1)))                 # "delegate: Item {"
            elif hm and hm.group(1)[0].islower() and re.search(r":\s*$", before) is None and re.match(r"^\s*$", before.rsplit(";", 1)[-1]):
                stack.append(("group", hm.group(1)))                # "font {"
            else:
                stack.append(("js", None))                          # "onClicked: {", "function f() {", literal object
            token_start = i + 1
        elif c == "}":
            if stack and stack[-1][0] in ("type", "group"):
                clause_end_handler(text[token_start:i], token_start)
            if stack:
                stack.pop()
            token_start = i + 1
        elif c == ";" and stack and stack[-1][0] in ("type", "group"):
            clause_end_handler(text[token_start:i], token_start)
            token_start = i + 1
        elif c == "\n" and stack and stack[-1][0] in ("type", "group"):
            # Xuống dòng kết thúc một mệnh đề nếu ngoặc () [] đã đóng và dòng kế không phải phần nối tiếp
            clause = text[token_start:i]
            if clause.strip() and clause.count("(") == clause.count(")") and clause.count("[") == clause.count("]") \
                    and not clause.rstrip().endswith((",", "+", "?", ":", "&&", "||", "=>")):
                nxt = text[i + 1:i + 200].lstrip()
                if not nxt.startswith((".", "?", ":", "+", "&&", "||", ")")):
                    clause_end_handler(clause, token_start)
                    token_start = i + 1
        i += 1
    return errors


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "qml"
    files = sorted(folder.glob("*.qml"))
    errors: list[str] = []
    for f in files:
        errors.extend(scan(f))
    if errors:
        print("Máy dò cắt chữ: có chỗ cắt chữ của người dùng (luật chủ sách: không bao giờ cắt).")
        for e in errors:
            print("  " + e)
        print("Sửa: wrapMode: Text.Wrap (ô cao theo chữ) hoặc fontSizeMode: Text.Fit + minimumPixelSize; bỏ elide / maximumLineCount / clip.")
        return 1
    print(f"Máy dò cắt chữ: {len(files)} file QML, không có chỗ cắt chữ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
