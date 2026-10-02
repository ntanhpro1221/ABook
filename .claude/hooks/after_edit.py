"""PostToolUse (Edit/Write): sau mỗi lần sửa file trong repo ABook (mọi worktree):

- file có CRLF -> báo (repo dùng LF; Python write_text trên Windows ghi CRLF, mà CRLF cũng đổi hash file khoá);
- file nằm dưới _internal/ebook_reader/ -> tính quality_implementation_hash của worktree ấy, báo khi nó ĐỔI so với lần
  trước (đổi = bản sửa phải ở nhánh dev, chờ hết các lượt sách đang dở - AGENTS.md).
Kết quả trả cho Claude qua additionalContext; không bao giờ chặn.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def worktree_of(path: Path) -> Path | None:
    for parent in path.parents:
        if (parent / "_internal" / "ebook_reader").is_dir():
            return parent
    return None


def quality_hash(root: Path) -> str | None:
    python = root / "_internal" / "runtime" / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = Path("D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe")
    code = ("import sys; sys.path.insert(0, '.'); from ebook_reader.quality_policy import quality_implementation_hash; "
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
    root = worktree_of(path)
    if root is not None and "ebook_reader" in path.parts:
        value = quality_hash(root)
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
