"""Byte budgets shared by peer download paths (PeerTransfer.kt on Android)."""
MIB = 1024 * 1024
JSON_BYTES = 16 * MIB
ERROR_BYTES = 64 * 1024
COVER_BYTES = 8 * MIB
JOB_BYTES = 64 * 1024 * MIB
JOB_FILES = 20000
DISK_MARGIN = 64 * MIB


def check_json(data: bytes) -> None:
    """Bound nesting before json.loads (which otherwise hits recursion limits)."""
    import json
    depth, string, escape = 0, False, False
    for byte in data:
        if string:
            if escape:
                escape = False
            elif byte == 92:
                escape = True
            elif byte == 34:
                string = False
        elif byte == 34:
            string = True
        elif byte in (91, 123):
            depth += 1
            if depth > 64:
                raise ValueError("Dữ liệu máy gửi lồng quá sâu; bạn hãy kiểm tra lại máy gửi.")
        elif byte in (93, 125):
            depth -= 1
    try:
        parsed = json.loads(data)
    except (ValueError, RecursionError) as error:
        raise ValueError("Dữ liệu máy gửi không hợp lệ; bạn hãy thử lại.") from error
    if not isinstance(parsed, dict):
        raise ValueError("Dữ liệu máy gửi sai dạng; bạn hãy thử lại.")


def file_budget(name: str, size: int | None = None) -> int:
    kind = name.lower()
    cap = (2 * 1024 * MIB if kind.startswith("music/") else
           8 * 1024 * MIB if kind.endswith((".mp3", ".m4b")) else
           64 * MIB if kind.endswith(".wav") else
           COVER_BYTES if kind.endswith((".jpg", ".png", ".webp")) else JSON_BYTES)
    if size is not None and (size < 0 or size > cap):
        raise ValueError("File vượt giới hạn tải; bạn hãy kiểm tra lại máy gửi sách.")
    return size if size is not None else cap
