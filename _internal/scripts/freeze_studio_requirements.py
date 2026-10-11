"""Sinh `shell/python/studio-requirements.txt`: thư viện của Studio trong app Windows đóng gói (docs/PACKAGING.md).

Lấy từ runtime dev ĐANG CHẠY TỐT (`pip freeze` của runtime/.venv - chính môi trường đã làm ra các lô sách), chỉ giữ
bao đóng phụ thuộc của app theo `uv.lock` (không extra dev), bỏ PySide6 (giao diện là Tauri). Từ 11-10 lock và danh
sách này phải khớp từng gói (tests/test_lock_matches_studio_requirements.py): trước đó freeze cuốn theo mọi thứ cài tay
vào runtime cho thí nghiệm (voxcpm, funasr, modelscope, datasets... 64 gói, 258 MiB) mà app không nạp.
Studio cài danh sách này bằng `uv pip install --no-deps` rồi `uv pip check`: đúng từng phiên bản, không để bộ giải phụ
thuộc chọn bản khác - môi trường nào làm ra sách thì cài lại đúng môi trường ấy.

    runtime/.venv/Scripts/python.exe scripts/freeze_studio_requirements.py

Chạy lại sau mỗi lần nâng thư viện của runtime (pyproject.toml đổi = một sự kiện phiên bản, AGENTS.md).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

INTERNAL = Path(__file__).resolve().parents[1]
TARGET = INTERNAL / "shell" / "python" / "studio-requirements.txt"
RUNTIME_PYTHON = INTERNAL / "runtime" / ".venv" / "Scripts" / "python.exe"
PYPROJECT = INTERNAL / "pyproject.toml"
LOCK = INTERNAL / "uv.lock"
# Giao diện Qt và công cụ dev: Studio đóng gói không chạy giao diện Qt (vỏ Tauri) và không chạy test.
# Từ PySide6 6.12, WebEngine và Pdf là wheel riêng.
EXCLUDED = {
    "pyside6", "pyside6-addons", "pyside6-essentials", "pyside6-webengine", "pyside6-pdf", "shiboken6",
    "pytest", "ruff", "iniconfig", "pluggy",
}
PIN_PATTERN = re.compile(r'"([A-Za-z0-9_.\-]+)==([^"]+)"')
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"


def normalize(name: str) -> str:
    """Tên gói dạng PEP 503 (như uv.lock ghi)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _name(line: str) -> str:
    return normalize(re.split(r"[=@<>~! ]", line, maxsplit=1)[0].strip())


def _version(line: str) -> str:
    """Bản của một dòng `pip freeze`; gói cài từ git thì là commit."""
    return line.rsplit("@", 1)[1] if " @ git+" in line else line.split("==", 1)[1]


def lock_closure(lock: dict[str, Any]) -> dict[str, str]:
    """Gói Studio cần theo uv.lock: bao đóng phụ thuộc của dự án (không extra như dev), trừ EXCLUDED.

    Tên -> bản như lock ghi (torch: `2.11.0+cu128`); gói git -> commit.
    """
    packages = {normalize(p["name"]): p for p in lock["package"]}
    project = next(p for p in lock["package"] if "editable" in p.get("source", {}))
    found: dict[str, str] = {}
    seen: set[tuple[str, tuple[str, ...]]] = set()
    stack = list(project.get("dependencies", []))
    while stack:
        dependency = stack.pop()
        name, extras = normalize(dependency["name"]), tuple(dependency.get("extra", []))
        if name in EXCLUDED or (name, extras) in seen:
            continue
        seen.add((name, extras))
        package = packages[name]
        git = package.get("source", {}).get("git")
        found[name] = git.rsplit("#", 1)[1] if git else package["version"]
        stack += package.get("dependencies", [])
        for extra in extras:
            stack += package.get("optional-dependencies", {}).get(extra, [])
    return found


def kept_lines(frozen: str, wanted: set[str] | None = None) -> list[str]:
    """Các dòng `pip freeze` Studio cần cài: chỉ gói trong `wanted` (None = mọi gói trừ EXCLUDED)."""
    kept: list[str] = []
    for line in frozen.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-e ")) or "@ file:" in line:
            continue  # bản thân abook (cài editable) và wheel cài tay từ thư mục tạm
        if _name(line) in EXCLUDED or (wanted is not None and _name(line) not in wanted):
            continue
        kept.append(line)
    return kept


def drift_from_lock(kept: list[str], locked: dict[str, str]) -> list[str]:
    """Gói lock khoá mà runtime cài bản khác (hay không cài)."""
    installed = {_name(line): _version(line) for line in kept}
    return [
        f"{name}: runtime {installed.get(name) or 'không có'}, uv.lock {version}"
        for name, version in sorted(locked.items())
        if installed.get(name) != version
    ]


def drift_from_pins(kept: list[str], pyproject: str, wanted: set[str] | None = None) -> list[str]:
    """Gói ghim `==` trong pyproject mà runtime cài bản khác (hay không cài); bỏ qua đuôi bản dựng (+cu128).

    Vì sao: runtime dev từng trôi khỏi ghim (11-10: huggingface-hub 1.29 dù ghim 1.33). Đóng băng lúc ấy thì bộ cài
    Studio lùi bản trong khi pyproject vẫn nói bản mới - không ai thấy.
    """
    installed = {_name(line): line.split("==", 1)[1].split("+", 1)[0] for line in kept if "==" in line}
    drift = []
    for name, pinned in PIN_PATTERN.findall(pyproject):
        key = normalize(name)
        if key in EXCLUDED or (wanted is not None and key not in wanted) or installed.get(key) == pinned:
            continue
        drift.append(f"{key}: runtime {installed.get(key) or 'không có'}, pyproject {pinned}")
    return drift


def main() -> int:
    python = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNTIME_PYTHON
    frozen = subprocess.run([str(python), "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True).stdout
    locked = lock_closure(tomllib.loads(LOCK.read_text(encoding="utf-8")))
    kept = kept_lines(frozen, set(locked))
    drift = drift_from_pins(kept, PYPROJECT.read_text(encoding="utf-8"), set(locked)) + drift_from_lock(kept, locked)
    if drift:
        raise SystemExit("runtime lệch ghim/uv.lock - đồng bộ runtime trước khi đóng băng:\n  " + "\n  ".join(drift))
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
