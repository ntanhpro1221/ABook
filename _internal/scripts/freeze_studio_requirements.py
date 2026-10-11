"""Sinh `shell/python/studio-requirements.txt`: thư viện của Studio trong app Windows đóng gói (docs/PACKAGING.md).

Lấy từ runtime dev ĐANG CHẠY TỐT (`pip freeze` của runtime/.venv - chính môi trường đã làm ra các lô sách), bỏ những
gì Studio đóng gói không cần: bản thân `abook` (mã đi theo bộ cài), PySide6 (giao diện là Tauri), công cụ dev.
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
PYPROJECT = INTERNAL / "pyproject.toml"
# Giao diện Qt và công cụ dev: Studio đóng gói không chạy giao diện Qt (vỏ Tauri) và không chạy test.
# Từ PySide6 6.12, WebEngine và Pdf là wheel riêng.
EXCLUDED = {
    "pyside6", "pyside6-addons", "pyside6-essentials", "pyside6-webengine", "pyside6-pdf", "shiboken6",
    "pytest", "ruff", "iniconfig", "pluggy",
}
PIN_PATTERN = re.compile(r'"([A-Za-z0-9_.\-]+)==([^"]+)"')
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"


def _name(line: str) -> str:
    return re.split(r"[=@<>~! ]", line, maxsplit=1)[0].strip().lower().replace("_", "-")


def kept_lines(frozen: str) -> list[str]:
    """Các dòng `pip freeze` Studio cần cài."""
    kept: list[str] = []
    for line in frozen.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-e ")) or "@ file:" in line:
            continue  # bản thân abook (cài editable) và wheel cài tay từ thư mục tạm
        if _name(line) in EXCLUDED:
            continue
        kept.append(line)
    return kept


def drift_from_pins(kept: list[str], pyproject: str) -> list[str]:
    """Gói ghim `==` trong pyproject mà runtime cài bản khác (hay không cài); bỏ qua đuôi bản dựng (+cu128).

    Vì sao: runtime dev từng trôi khỏi ghim (11-10: huggingface-hub 1.29 dù ghim 1.33). Đóng băng lúc ấy thì bộ cài
    Studio lùi bản trong khi pyproject vẫn nói bản mới - không ai thấy.
    """
    installed = {_name(line): line.split("==", 1)[1].split("+", 1)[0] for line in kept if "==" in line}
    drift = []
    for name, pinned in PIN_PATTERN.findall(pyproject):
        key = name.lower().replace("_", "-")
        if key in EXCLUDED or installed.get(key) == pinned:
            continue
        drift.append(f"{key}: runtime {installed.get(key) or 'không có'}, pyproject {pinned}")
    return drift


def main() -> int:
    python = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNTIME_PYTHON
    frozen = subprocess.run([str(python), "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True).stdout
    kept = kept_lines(frozen)
    drift = drift_from_pins(kept, PYPROJECT.read_text(encoding="utf-8"))
    if drift:
        raise SystemExit("runtime lệch ghim của pyproject - đồng bộ runtime trước khi đóng băng:\n  " + "\n  ".join(drift))
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
