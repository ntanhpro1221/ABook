"""Lexical checks for untrusted package names, before filesystem access."""
import re
from typing import Any

_DEVICE = re.compile(r"(?i)(CON|PRN|AUX|NUL|CONIN[$]|CONOUT[$]|COM[0-9¹²³]|LPT[0-9¹²³])\Z")


def safe_relative(name: Any) -> bool:
    if not isinstance(name, str) or not name or len(name) > 1024:
        return False
    if any(ord(c) < 32 or c in '\\:<>"|?*' for c in name):
        return False
    return all(part not in ("", ".", "..") and not part.endswith((".", " "))
               and not _DEVICE.fullmatch(part.split(".", 1)[0].rstrip(" ")) for part in name.split("/"))


def check_manifest(book: dict) -> None:
    from .bookfile import BookFileError, check_shape
    try:
        check_shape(book)
    except BookFileError as error:
        raise ValueError("Dữ liệu sách sai dạng; bạn hãy kiểm tra lại máy gửi sách.") from error
    names = [book.get("cast")]
    for chapter in book.get("chapters") or []:
        names.extend(chapter.get(key) for key in ("file", "script", "text"))
    names.extend(book.get("samples") or [])
    cover = book.get("cover")
    if isinstance(cover, dict):
        names.append(cover.get("file"))
    music = book.get("music")
    if isinstance(music, dict):
        tracks = music.get("tracks") or {}
        if not isinstance(tracks, dict):
            raise ValueError("Dữ liệu nhạc sai dạng; bạn hãy kiểm tra lại máy gửi sách.")
        names.extend(tracks.keys())
    if any(name is not None and name != "" and not safe_relative(name) for name in names):
        raise ValueError("Đường dẫn trong sách không hợp lệ; bạn hãy kiểm tra lại máy gửi sách.")
