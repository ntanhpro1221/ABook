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
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Any

COVER_FILE = "cover.jpg"
META_FILE = "cover.json"
MAX_SIDE = 1400
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
DATA_URL = re.compile(r"data:image/(png|jpe?g|webp|gif|bmp);base64,([A-Za-z0-9+/=\s]+)", re.IGNORECASE)


class CoverError(ValueError):
    """Ảnh không dùng được làm bìa - thông điệp đọc được cho người dùng."""


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
    return {
        "version": int(path.stat().st_mtime),
        "color": str(meta.get("color") or ""),
        "width": int(meta.get("width") or 0),
        "height": int(meta.get("height") or 0),
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
        image = Image.open(io.BytesIO(raw))
        image.seek(0)
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise CoverError("Không đọc được ảnh này") from exc
    if min(image.size) < 64:
        raise CoverError("Ảnh quá nhỏ để làm bìa (cần ít nhất 64 điểm ảnh mỗi cạnh)")
    if image.mode in ("RGBA", "LA", "P"):
        backdrop = Image.new("RGB", image.size, (255, 255, 255))
        backdrop.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        image = backdrop
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
    (project_root / META_FILE).write_text(json.dumps({**meta, "savedAt": time.time()}, ensure_ascii=False), encoding="utf-8")
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
