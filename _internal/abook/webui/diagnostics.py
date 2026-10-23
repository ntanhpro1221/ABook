"""Chẩn đoán của chính máy tính: một gói .zip để người dùng TỰ gửi cho người sửa lỗi ("Gửi nhật ký", Cài đặt).

Gói gồm `thong-tin.json` (phiên bản app, hệ điều hành, giờ máy, ổ đĩa, cổng đồng bộ bật hay tắt, tên các máy đã ghép) và đuôi các file nhật ký
app ghi ở `%LOCALAPPDATA%\\ABook\\logs` (host.log: stderr của host kèm logging của Python). Không có mã thiết bị, vân tay chứng chỉ, khoá giọng
online, địa chỉ máy đã ghép hay chữ của truyện; mỗi file nhật ký chỉ lấy đuôi có trần dung lượng và qua `redact` (mã trong dòng log nếu lỡ có).
App không gửi gói đi đâu - nó chỉ được ghi vào thư mục người dùng chọn.
"""
from __future__ import annotations

import io
import ipaddress
import json
import platform
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

TAIL_BYTES = 256 * 1024  # trần mỗi file nhật ký
MAX_LOG_FILES = 8
TOTAL_LOG_BYTES = 1024 * 1024  # trần cả phần nhật ký trong gói
LOG_SUFFIXES = {".log", ".txt"}
FILE_PREFIX = "abook-nhat-ky-may-tinh"

# Chuỗi trông như bí mật: "Authorization: Bearer ...", `token=...`, mã 64 hex (băm mã thiết bị, vân tay chứng chỉ), khoá API kiểu sk-.
_SECRETS = (
    (re.compile(r"(/c/)(?:[A-Za-z0-9_-]{22}|[0-9a-fA-F]{32})(?=\.[A-Za-z0-9]{1,5}\b|[^A-Za-z0-9_-]|$)"), r"\1***"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer ***"),
    (re.compile(r'''(?i)\b((?:key|api[_-]?key|token|secret|password|code|mật khẩu|mã ghép)["']?\s*[:=]\s*)(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"',;&}\]]+)'''), r"\1***"),
    (re.compile(r"(?i)(\b(?:pair(?:ing)?|code|mã ghép)\b[^\r\n\d]{0,32})\d{6}\b"), r"\1***"),
    (re.compile(r"\b[0-9a-fA-F]{24,}\b"), "***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-***"),
)
_PATHS = re.compile(r'''(?i)(?:\b[a-z]:[\\/]+|\\\\[^\\/\r\n"'<>|]+[\\/]+|(?<!:)//[^/\r\n"'<>|]+/|/(?:home|Users|storage|sdcard|data)/|content://)[^\r\n"'<>|]*''')
_SOURCE_FILE = re.compile(r'''(?i)[\\/]([^\\/\r\n"'<>|]*?\.(?:py|kt))(:\d+(?::\d+)?)?(?=$|[,\s:)])''')
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?:%[\w.-]+)?(?![\w:])")
_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
_SECRET_FIELD = re.compile(r"(?i)^(?:key|api[_-]?key|token|secret|password|code|mật khẩu|mã ghép)$")


def redact(text: str) -> str:
    """Che những chuỗi trông như mã / khoá trong một đoạn nhật ký (phòng khi một dòng log lỡ in ra)."""
    for pattern, replacement in _SECRETS:
        text = pattern.sub(replacement, text)
    def hide_path(match: re.Match) -> str:
        source = _SOURCE_FILE.search(match.group())
        if source:
            closing = re.match(r"\)*", match.group()[source.end():]).group()
            return "<đường>/" + source[1] + (source[2] or "") + closing
        return "<đường>"
    text = _PATHS.sub(hide_path, text)
    def hide_ip(match: re.Match) -> str:
        address = match.group().rstrip('.')
        try:
            ipaddress.ip_address(address)
        except ValueError:
            return match.group()
        return "<ip>" + match.group()[len(address):]
    text = _IPV6.sub(hide_ip, text)
    text = _IPV4.sub(hide_ip, text)
    return text


def redact_report(value: Any) -> Any:
    """Same scrubber at every JSON boundary, including nested error metadata."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {redact(str(key)): "***" if isinstance(item, str) and _SECRET_FIELD.fullmatch(str(key)) else redact_report(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_report(item) for item in value]
    return value


def tail_text(path: Path, cap: int = TAIL_BYTES) -> str:
    """Đuôi tối đa `cap` byte của file chữ (bỏ dòng đầu nếu bị cắt giữa chừng); không đọc được thì chuỗi rỗng."""
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, 2)
            handle.seek(max(0, size - cap))
            data = handle.read(cap)
            cut = size > cap
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    if cut and "\n" in text:
        text = text.split("\n", 1)[1]
    return text


def log_files(log_dir: Path | None) -> list[Path]:
    """Các file nhật ký của app, mới ghi nhất trước, host.log đứng đầu."""
    if log_dir is None or not log_dir.is_dir():
        return []
    found = [path for path in log_dir.iterdir() if path.is_file() and path.suffix.lower() in LOG_SUFFIXES]
    found.sort(key=lambda path: (path.name != "host.log", -path.stat().st_mtime))
    return found[:MAX_LOG_FILES]


def machine_info(version: str, library_root: Path | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Thông tin máy cho `thong-tin.json`: không có tên người dùng Windows, đường dẫn, địa chỉ mạng."""
    from .notices import NOTICES
    disk: dict[str, Any] = {}
    if library_root is not None:
        try:
            usage = shutil.disk_usage(library_root if library_root.exists() else library_root.anchor or ".")
            disk = {"freeBytes": usage.free, "totalBytes": usage.total}
        except OSError:
            pass
    now = time.time()
    return {
        "app": "ABook (máy tính)",
        "version": version,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "timezone": time.tzname[1 if time.localtime(now).tm_isdst > 0 else 0],
        "system": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "disk": disk,
        "dataRecovery": NOTICES.diagnostics(),
        **(extra or {}),
    }


def bundle(info: dict[str, Any], log_dir: Path | None) -> bytes:
    """Gói .zip: `thong-tin.json` + đuôi các nhật ký (`nhat-ky/<tên>`), tổng phần nhật ký không quá `TOTAL_LOG_BYTES`."""
    out = io.BytesIO()
    budget = TOTAL_LOG_BYTES
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("thong-tin.json", json.dumps(redact_report(info), ensure_ascii=False, indent=2))
        listed: list[str] = []
        for path in log_files(log_dir):
            if budget <= 0:
                break
            text = redact(tail_text(path, min(TAIL_BYTES, budget)))
            if not text:
                continue
            budget -= len(text.encode("utf-8"))
            archive.writestr(f"nhat-ky/{path.name}", text)
            listed.append(path.name)
        if not listed:
            archive.writestr("nhat-ky/trong.txt", "Chưa có file nhật ký nào trên máy này.\n")
    return out.getvalue()


def file_name(now: float | None = None) -> str:
    return f"{FILE_PREFIX}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}.zip"
