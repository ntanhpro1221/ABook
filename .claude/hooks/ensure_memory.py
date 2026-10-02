"""SessionStart: nối bộ nhớ tự động của Claude Code với bản trong repo riêng tư, để clone về máy mới không phải cài gì.

Bộ nhớ của dự án nằm ở `<repo>/Corpus/claude/memory` (repo RIÊNG TƯ ABook-Private, clone vào thư mục Corpus/ - đã bị
.gitignore của repo công khai). Claude Code đọc bộ nhớ ở `~/.claude/projects/<tên suy từ đường dẫn repo>/memory`, và
không nhận `autoMemoryDirectory` từ settings.json của dự án. Nên lần đầu mở phiên: thư mục ấy chưa có -> tạo junction
(Windows) / symlink trỏ sang bản trong Corpus. Đã có (thư mục thật hay liên kết) thì không đụng tới.
Không bao giờ chặn phiên; thiếu Corpus thì chỉ nhắc.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    source = root / "Corpus" / "claude" / "memory"
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(root))
    target = Path.home() / ".claude" / "projects" / slug / "memory"
    note = ""
    if os.path.lexists(target):
        return 0
    if not source.is_dir():
        note = (f"Bộ nhớ dự án chưa có: clone repo riêng tư ABook-Private vào {root / 'Corpus'} rồi mở lại phiên "
                "(hook ensure_memory sẽ tự nối).")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(source)], capture_output=True)
        else:
            target.symlink_to(source, target_is_directory=True)
        note = f"Đã nối bộ nhớ dự án: {target} -> {source}." if os.path.lexists(target) else \
            f"Không nối được bộ nhớ {target} -> {source}; làm tay theo Corpus/claude/README.md."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": note}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
