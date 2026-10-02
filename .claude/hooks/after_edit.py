"""PostToolUse (Edit/Write): sau mỗi lần sửa file trong repo ABook (mọi worktree):

- file có CRLF -> báo (repo dùng LF; Python write_text trên Windows ghi CRLF, mà CRLF cũng đổi hash file khoá);
- file nằm dưới gói Python của worktree (_internal/abook/, hay _internal/ebook_reader/ ở checkout trước 0.4.17) -> tính
  quality_implementation_hash của worktree ấy, báo khi nó ĐỔI so với lần trước (đổi = bản sửa phải ở nhánh dev, chờ hết
  các lượt sách đang dở - AGENTS.md).
Kết quả trả cho Claude qua additionalContext; không bao giờ chặn.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGES = ("abook", "ebook_reader")  # tên gói từ 0.4.17, và tên cũ ở checkout D:/Novels/ABook cố ý giữ cũ


def worktree_of(path: Path) -> tuple[Path, str] | None:
    for parent in path.parents:
        for package in PACKAGES:
            if (parent / "_internal" / package / "quality_policy.py").is_file():
                return parent, package
    return None


def quality_hash(root: Path, package: str) -> str | None:
    python = root / "_internal" / "runtime" / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = Path("D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe")
    code = (f"import sys; sys.path.insert(0, '.'); from {package}.quality_policy import quality_implementation_hash; "
            "print(quality_implementation_hash())")
    try:
        out = subprocess.run([str(python), "-c", code], cwd=root / "_internal", capture_output=True, text=True,
                             timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = out.stdout.strip().splitlines()
    return lines[-1][:8] if out.returncode == 0 and lines else None


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    path = Path(str((event.get("tool_input") or {}).get("file_path") or ""))
    if not path.is_file():
        return 0
    notes = []
    try:
        if b"\r\n" in path.read_bytes():
            notes.append(f"{path.name} có CRLF - repo dùng LF; đổi lại trước khi commit.")
    except OSError:
        pass
    found = worktree_of(path)
    if found is not None and found[1] in path.parts:
        root, package = found
        value = quality_hash(root, package)
        state = Path(tempfile.gettempdir()) / f"abook_quality_hash_{hashlib.sha1(str(root).encode()).hexdigest()[:8]}"
        before = state.read_text().strip() if state.is_file() else None
        if value:
            state.write_text(value)
            if before and before != value:
                notes.append(f"quality_implementation_hash ĐỔI {before} -> {value} ở {root.name}: sửa file khoá - phải ở "
                             "nhánh dev và chờ hết các lượt sách đang dở (AGENTS.md).")
            elif not before:
                notes.append(f"quality_implementation_hash ở {root.name} = {value}.")
    if notes:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": " ".join(notes)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
