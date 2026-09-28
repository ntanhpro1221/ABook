"""Sinh `shell/python/studio-requirements.txt`: thư viện của Studio trong app Windows đóng gói (docs/PACKAGING.md).

Lấy từ runtime dev ĐANG CHẠY TỐT (`pip freeze` của runtime/.venv - chính môi trường đã làm ra các lô sách), bỏ những
gì Studio đóng gói không cần: bản thân `ebook_reader` (mã đi theo bộ cài), PySide6 (giao diện là Tauri), công cụ dev.
Studio cài danh sách này bằng `uv pip install --no-deps` rồi `uv pip check`: đúng từng phiên bản, không để bộ giải phụ
thuộc chọn bản khác - môi trường nào làm ra sách thì cài lại đúng môi trường ấy.

    runtime/.venv/Scripts/python.exe scripts/freeze_studio_requirements.py

Chạy lại sau mỗi lần nâng thư viện của runtime (pyproject.toml đổi = một sự kiện phiên bản, AGENTS.md).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

INTERNAL = Path(__file__).resolve().parents[1]
TARGET = INTERNAL / "shell" / "python" / "studio-requirements.txt"
RUNTIME_PYTHON = INTERNAL / "runtime" / ".venv" / "Scripts" / "python.exe"
# Giao diện Qt và công cụ dev: Studio đóng gói không chạy giao diện Qt (vỏ Tauri) và không chạy test.
EXCLUDED = {"pyside6", "pyside6-addons", "pyside6-essentials", "shiboken6", "pytest", "ruff", "iniconfig", "pluggy"}
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"


def _name(line: str) -> str:
    return re.split(r"[=@<>~! ]", line, maxsplit=1)[0].strip().lower().replace("_", "-")


def main() -> int:
    python = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNTIME_PYTHON
    frozen = subprocess.run([str(python), "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True).stdout
    kept: list[str] = []
    for line in frozen.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-e ")) or "@ file:" in line:
            continue  # bản thân ebook_reader (cài editable) và wheel cài tay từ thư mục tạm
        if _name(line) in EXCLUDED:
            continue
        kept.append(line)
    if not any(line.startswith("torch==") and "+cu" in line for line in kept):
        raise SystemExit("runtime không có torch bản CUDA - không sinh danh sách từ một môi trường chạy CPU")
    header = [
        "# Sinh bởi scripts/freeze_studio_requirements.py từ runtime dev đang chạy tốt - đừng sửa tay.",
        "# Cài: uv pip install --no-deps --index-strategy unsafe-best-match -r <file>, rồi uv pip check.",
        f"--extra-index-url {TORCH_INDEX}",
    ]
    TARGET.write_text("\n".join(header + sorted(kept, key=str.lower)) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(kept)} gói -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
