"""Ảnh bìa thật của một cuốn: `cover.jpg` trong thư mục sách, kèm `cover.json` (màu chủ đạo, cỡ, phiên bản).

Sách làm từ TXT không có bìa, nên mặc định giao diện tự vẽ bìa từ tên sách (shared/cover.ts, Artwork.kt). Người dùng
có thể đặt ảnh bìa thật; khi ấy mọi nơi hiện bìa đều dùng ảnh này: thư viện, trình phát, màn hình khoá điện thoại, bảng
điều khiển media của Windows, file MP3 xuất ra.

Ảnh được chuẩn hoá một lần lúc lưu: xoay theo EXIF, bỏ kênh trong suốt, thu về cạnh dài tối đa `MAX_SIDE`, ghi JPEG. Nhờ
vậy file đồng bộ sang điện thoại luôn nhỏ (vài trăm KB) dù người dùng thả vào một ảnh chụp 12 MB. Màu chủ đạo tính sẵn
ở đây để máy tính và điện thoại nhuộm màn hình đang nghe cùng một màu, không mỗi bên tự đoán.
"""

from __future__ import annotations

import base64
import binascii
import colorsys
import hashlib
import io
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from ..io_utils import atomic_write_bytes

COVER_FILE = "cover.jpg"
META_FILE = "cover.json"
# Màu bìa chỉ là #rrggbb (đúng dạng `dominant_color` ghi và lớp sửa bìa nhận). Trường này đi theo file sách / manifest của người khác rồi thành
# CSS ở giao diện: để nguyên chuỗi thì `url(https://…)` làm trình duyệt tự gọi máy lạ mỗi lần hiện bìa (soát a109 F1).
COLOR = re.compile(r"#[0-9a-f]{6}")


def clean_color(value: Any) -> str:
    """`value` nếu là màu #rrggbb (chữ thường, bỏ khoảng trắng hai đầu), không thì ''."""
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if COLOR.fullmatch(text) else ""


def stored_meta(cover: dict[str, Any]) -> dict[str, Any]:
    """Phần `cover` của một book.json / manifest từ nơi khác -> nội dung `cover.json` (màu chỉ khi hợp lệ; cỡ khi có)."""
    meta = {key: cover[key] for key in ("width", "height")
            if type(cover.get(key)) is int and 0 < cover[key] <= 20_000}
    color = clean_color(cover.get("color"))
    if color:
        meta["color"] = color
    return meta
MAX_SIDE = 1400
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
# Ảnh nén nhỏ nhưng nhiều điểm ảnh (PNG 8000x8000 chỉ vài MB) giải nén ra hàng trăm MB mỗi bản; vài lượt cùng lúc là chạm 1 GB.
# JPEG được giải mã thẳng ở cỡ nhỏ (`draft`) nên ảnh chụp điện thoại 100 triệu điểm ảnh vẫn dùng được.
MAX_PIXELS = 40_000_000
DATA_URL = re.compile(r"data:image/(png|jpe?g|webp|gif|bmp);base64,([A-Za-z0-9+/=\s]+)", re.IGNORECASE)


class CoverError(ValueError):
    """Ảnh không dùng được làm bìa - thông điệp đọc được cho người dùng."""


VERSION_MODULUS = 10**10  # book_edits._clean_cover nhận phiên bản tới 10**10; điện thoại (Store.kt) tính cùng công thức


def content_version(data: bytes) -> int:
    """Phiên bản bìa THEO NỘI DUNG (8 byte đầu của SHA-256, chia dư 10**10): hai ảnh khác nhau không bao giờ chung `?v=` dù đặt cùng một giây,
    cùng một ảnh thì cùng phiên bản ở mọi máy. Địa chỉ ảnh phát với `immutable` nên chỉ được trùng khi nội dung trùng (soát a97 T2)."""
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big") % VERSION_MODULUS


_FILE_VERSIONS: dict[str, tuple[int, int, int]] = {}  # đường dẫn -> (mốc sửa ns, cỡ, phiên bản): không băm lại bìa chưa đổi mỗi lần liệt kê thư viện
_FILE_VERSIONS_LOCK = threading.Lock()


def file_version(path: Path) -> int:
    """`content_version` của một file bìa, nhớ theo (mốc sửa, cỡ)."""
    stat = path.stat()
    key = os.path.abspath(path)
    with _FILE_VERSIONS_LOCK:
        known = _FILE_VERSIONS.get(key)
    if known is not None and known[:2] == (stat.st_mtime_ns, stat.st_size):
        return known[2]
    version = content_version(path.read_bytes())
    with _FILE_VERSIONS_LOCK:
        if len(_FILE_VERSIONS) > 4096:
            _FILE_VERSIONS.clear()
        _FILE_VERSIONS[key] = (stat.st_mtime_ns, stat.st_size, version)
    return version


def cover_file(project_root: Path) -> Path | None:
    path = project_root / COVER_FILE
    return path if path.is_file() else None


def cover_meta(project_root: Path) -> dict[str, Any] | None:
    """Màu, cỡ và phiên bản của bìa; None khi sách chưa có ảnh bìa."""
    path = cover_file(project_root)
    if path is None:
        return None
    try:
        meta = json.loads((project_root / META_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    meta = stored_meta(meta) if isinstance(meta, dict) else {}
    return {
        "version": file_version(path),
        "color": clean_color(meta.get("color")),
        "width": meta.get("width", 0),
        "height": meta.get("height", 0),
    }


def cover_view(project_root: Path, book_id: str) -> dict[str, Any] | None:
    """Phần `cover` trong JSON sách của giao diện máy tính: đường dẫn kèm phiên bản để trình duyệt không giữ ảnh cũ."""
    meta = cover_meta(project_root)
    if meta is None:
        return None
    return {**meta, "url": f"/media/books/{book_id}/cover?v={meta['version']}"}


def _decode(data_url: str) -> bytes:
    match = DATA_URL.fullmatch((data_url or "").strip())
    if not match:
        raise CoverError("Chỉ nhận ảnh PNG, JPEG, WebP, GIF hoặc BMP")
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CoverError("Dữ liệu ảnh bị hỏng") from exc
    if len(raw) > MAX_UPLOAD_BYTES:
        raise CoverError(f"Ảnh quá lớn (tối đa {MAX_UPLOAD_BYTES // 2**20} MB)")
    return raw


def dominant_color(image: Any) -> str:
    """Màu đại diện dùng để nhuộm nền: màu của vùng có nhiều điểm ảnh nhất, ưu tiên màu có sắc (không lấy xám/đen/trắng).

    Trung bình cộng mọi điểm ảnh thường ra một màu nâu xám không có trong ảnh; nên lượng tử hoá về 8 màu rồi chấm theo
    số điểm ảnh nhân độ bão hoà, và nâng độ sáng về một dải đọc được trên cả nền sáng lẫn tối.
    """
    small = image.convert("RGB").resize((64, 64))
    palette = small.quantize(colors=8, method=0)
    counts = sorted(palette.getcolors() or [], reverse=True)
    colors = palette.getpalette() or []
    best, best_score = (120, 120, 120), -1.0
    for count, index in counts:
        r, g, b = colors[index * 3: index * 3 + 3]
        hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        score = count * (0.25 + saturation) * (1.0 if 0.12 < lightness < 0.88 else 0.35)
        if score > best_score:
            best, best_score = (r, g, b), score
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in best))
    r, g, b = colorsys.hls_to_rgb(hue, min(max(lightness, 0.32), 0.62), min(saturation, 0.75))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def save_cover(project_root: Path, data_url: str) -> dict[str, Any]:
    return save_cover_bytes(project_root, _decode(data_url))


def render_cover(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Chuẩn hoá một ảnh bìa từ byte thô: JPEG đã xoay theo EXIF, bỏ kênh trong suốt, cạnh dài tối đa `MAX_SIDE`, kèm
    {"color", "width", "height"}. Dùng chung cho bìa của dự án (`save_cover_bytes`) và bìa người nghe đặt cho sách
    không có xưởng (book_edits.py)."""
    from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: PLC0415 - Pillow chỉ cần khi có người đặt bìa

    if len(raw) > MAX_UPLOAD_BYTES:
        raise CoverError(f"Ảnh quá lớn (tối đa {MAX_UPLOAD_BYTES // 2**20} MB)")
    try:
        image = Image.open(io.BytesIO(raw), formats=("JPEG", "PNG", "WEBP", "GIF", "BMP"))
        image.seek(0)
        image.draft("RGB", (MAX_SIDE, MAX_SIDE))  # JPEG: giải mã ở 1/2, 1/4, 1/8 cỡ nếu vẫn đủ cho bìa; định dạng khác: không làm gì
        if image.width * image.height > MAX_PIXELS:
            raise CoverError(f"Ảnh có quá nhiều điểm ảnh (tối đa {MAX_PIXELS // 1_000_000} triệu) - bạn thu nhỏ ảnh rồi thử lại")
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise CoverError("Không đọc được ảnh này") from exc
    if min(image.size) < 64:
        raise CoverError("Ảnh quá nhỏ để làm bìa (cần ít nhất 64 điểm ảnh mỗi cạnh)")
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")  # một bản thôi: cỡ nguyên ảnh lớn rất tốn RAM
        backdrop = Image.new("RGB", image.size, (255, 255, 255))
        backdrop.paste(rgba, mask=rgba.getchannel("A"))
        image = backdrop
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue(), {"color": dominant_color(image), "width": image.width, "height": image.height}


def save_cover_bytes(project_root: Path, raw: bytes) -> dict[str, Any]:
    """Chuẩn hoá và lưu một ảnh bìa từ byte thô (ảnh người dùng gửi lên, hay ảnh tải về từ cover_search)."""
    jpeg, meta = render_cover(raw)
    target = project_root / COVER_FILE
    partial = target.with_suffix(".jpg.part")
    partial.write_bytes(jpeg)
    os.replace(partial, target)
    atomic_write_bytes(project_root / META_FILE, json.dumps({**meta, "savedAt": time.time()}, ensure_ascii=False).encode("utf-8"))
    return cover_meta(project_root) or {}


def decode_data_url(data_url: str) -> bytes:
    """Byte của ảnh trong một data URL do giao diện gửi (PNG, JPEG, WebP, GIF, BMP); lỗi thì `CoverError`."""
    return _decode(data_url)


def remove_cover(project_root: Path) -> None:
    for name in (COVER_FILE, META_FILE):
        try:
            (project_root / name).unlink()
        except FileNotFoundError:
            pass
