r"""Python 3.13 dọn thụt lề docstring ngay lúc biên dịch và từ chối một docstring chứa nửa cặp surrogate: `import` nổ
`UnicodeEncodeError ... surrogates not allowed`. Colab chạy 3.13 nên bộ đo không nạp nổi `analysis.py` (28-09) - docstring
của `strip_lone_surrogates` trích nguyên thông báo lỗi có `'\ud83d'` trong một chuỗi thường. Viết `\\ud83d` (hay dùng
docstring r"...") khi cần nhắc tới một surrogate trong docstring.
"""
from __future__ import annotations

import ast
from pathlib import Path


def test_no_docstring_holds_a_lone_surrogate() -> None:
    root = Path(__file__).resolve().parents[1] / "abook"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and any(0xD800 <= ord(char) <= 0xDFFF for char in doc):
                    offenders.append(f"{path.relative_to(root)}:{getattr(node, 'name', '<module>')}")
    assert not offenders, offenders
