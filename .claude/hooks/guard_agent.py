"""PreToolUse (Agent/Task): mỗi agent phải ghi rõ `model` - máy giữ luật thay cho trí nhớ.

Không ghi `model` thì agent lấy model của phiên chính (Opus): 03-10 Lead quên, thả agent soát UX bằng Opus, chủ sách nhắc.
Luật (bộ nhớ work-efficiency): việc có đặc tả rõ -> "sonnet"; "opus" chỉ khi có lý do (thiết kế khó, hay đợt đốt hạn mức sắp
mất). Agent tự định nghĩa có `model:` trong frontmatter (vd abook-dev) cũng phải ghi lại ở lệnh gọi cho rõ.
Thoát 2 = chặn, lý do in ra stderr cho Claude đọc.
"""
import json
import sys


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if str((event.get("tool_input") or {}).get("model") or "").strip():
        return 0
    print('Chặn: agent phải ghi rõ `model` - "sonnet" cho việc có đặc tả rõ, "opus" chỉ khi có lý do '
          "(thiết kế khó / đốt hạn mức sắp mất), nói lý do với chủ sách (bộ nhớ work-efficiency).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
