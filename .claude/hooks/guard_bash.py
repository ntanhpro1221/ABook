"""PreToolUse (Bash/PowerShell): chặn các lệnh git từng làm hỏng việc ở repo này - máy giữ luật thay cho trí nhớ.

- `git add -A` / `git add .` / `git add --all`: phải stage đúng đường dẫn (thư mục còn file rời của việc đang chạy).
- `git checkout` / `switch` / `reset --hard` / `restore` / `stash` trong bản checkout chính D:/Novels/ABook: bản ấy cố ý
  để cũ; viết lại file (kể cả chỉ đổi CRLF/LF) đổi hash file khoá và sách đang dở không resume được nữa.
Thoát 2 = chặn, lý do in ra stderr cho Claude đọc.
"""
import json
import re
import sys

MAIN_CHECKOUT = re.compile(r"^[A-Za-z]:[\\/]+Novels[\\/]+ABook[\\/]*$|^/[a-z]/Novels/ABook/?$", re.IGNORECASE)
ADD_ALL = re.compile(r"\bgit\s+(-C\s+\S+\s+)?add\s+(.*\s)?(-A|--all|\.)(\s|$)")
REWRITE = re.compile(r"\bgit\s+(checkout|switch|restore|stash)\b|\bgit\s+reset\s+.*--hard")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    command = str((event.get("tool_input") or {}).get("command") or "")
    cwd = str(event.get("cwd") or "")
    if ADD_ALL.search(command):
        print("Chặn: `git add -A`/`git add .` - stage đúng từng đường dẫn (luật repo ABook).", file=sys.stderr)
        return 2
    in_main = MAIN_CHECKOUT.match(cwd.rstrip()) and not re.search(r"\bcd\s+\S*ABook_", command)
    if in_main and REWRITE.search(command) and "-C" not in command:
        print("Chặn: không checkout/reset/restore/stash trong D:/Novels/ABook (bản chính cố ý để cũ - đổi file là đổi "
              "hash file khoá, sách dở không resume được). Làm trong một worktree ABook_*.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
