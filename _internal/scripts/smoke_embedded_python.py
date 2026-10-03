"""Thử Python nhúng của bộ cài app Windows SAU KHI đã cắt phần không dùng (build_windows_app.ps1 > Remove-UnusedFromPython).

Chạy bằng chính `resources\\python\\python.exe` với thư mục làm việc là `resources\\app` (không phải pytest - gói thử không
nằm trong bộ cài):

    resources\\python\\python.exe scripts\\smoke_embedded_python.py

Kiểm những thứ phía NGHE cần mà việc cắt có thể làm hỏng: nạp được mọi mô-đun của `abook.webui`, bìa đủ năm định dạng
nhận vào (PNG / JPEG / WebP / GIF / BMP -> JPEG, đúng giới hạn của covers.render_cover), bộ nhập sách (importers + abook/vendor),
ssl + sqlite3 + requests + psutil; numpy / onnxruntime KHÔNG có (thuộc mô-đun Phân tích nhạc). Và: dữ liệu chỉ Studio dùng KHÔNG có trong bộ cài mà máy vẫn trả lời gọn gàng.
"""
from __future__ import annotations

import importlib
import importlib.util
import io
import pkgutil
import sys
from pathlib import Path


# Mô-đun chỉ chạy được khi đã có mô-đun "Phân tích nhạc" (numpy, onnxruntime, librosa: webui/music_module.py tải khi cần) hay
# Studio: bộ cài chỉ-nghe không nạp được chúng. Mọi mô-đun khác của webui PHẢI nạp được.
NEEDS_OPTIONAL_LIBRARIES = {"abook.webui.music_acoustic", "abook.webui.music_mel"}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr] - console cp1252 của Windows
    app = Path.cwd()
    assert (app / "abook").is_dir(), f"chạy trong thư mục app của bộ cài, không phải {app}"

    import abook.webui as webui

    names = sorted(module.name for module in pkgutil.iter_modules(webui.__path__, "abook.webui.") if module.name != "abook.webui.host")
    loaded = 0
    for name in names:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as error:
            if name not in NEEDS_OPTIONAL_LIBRARIES:
                raise
            print(f"  bỏ qua {name}: cần {error.name} (mô-đun Phân tích nhạc / Studio)")
        else:
            loaded += 1
    print(f"nạp {loaded}/{len(names)} mô-đun abook.webui")

    from PIL import Image

    from abook.webui import covers

    for fmt in ("PNG", "JPEG", "WEBP", "GIF", "BMP"):
        buffer = io.BytesIO()
        Image.new("RGB", (300, 450), (40, 90, 160)).save(buffer, fmt)
        jpeg, meta = covers.render_cover(buffer.getvalue())
        assert jpeg[:3] == b"\xff\xd8\xff" and meta["width"] == 300 and meta["height"] == 450 and meta["color"].startswith("#"), fmt
    big = io.BytesIO()
    Image.new("RGBA", (3000, 2000), (200, 30, 30, 128)).save(big, "PNG")
    jpeg, meta = covers.render_cover(big.getvalue())
    assert max(meta["width"], meta["height"]) == covers.MAX_SIDE, meta
    print("bìa: 5 định dạng + giới hạn", covers.MAX_SIDE)

    for optional in ("numpy", "onnxruntime"):
        assert importlib.util.find_spec(optional) is None, f"{optional} thuộc mô-đun Phân tích nhạc, không thuộc bộ cài"
    from abook import importers  # noqa: F401 - bộ nhập sách
    from abook.vendor.tinytag import TinyTag  # chép vào gói (abook/vendor), không cài từ PyPI

    pypdf = importers._vendored_pypdf()
    pdf = io.BytesIO()
    writer = pypdf.PdfWriter()
    writer.add_blank_page(100, 100)
    writer.write(pdf)
    assert len(pypdf.PdfReader(io.BytesIO(pdf.getvalue())).pages) == 1 and TinyTag
    print("bộ nhập sách: importers, vendor.tinytag, vendor.pypdf; không có numpy / onnxruntime")

    import psutil
    import requests
    import sqlite3
    import ssl

    ssl.create_default_context()
    sqlite3.connect(":memory:").close()
    assert psutil.cpu_count() and requests.__version__
    print("ssl, sqlite3, requests, psutil")

    from abook.voice_catalog import VOICE_PREVIEW_FILENAMES
    from abook.webui.voice_picker import preview_file

    assets = app / "abook" / "assets"
    for name in ("cmudict.dict", "voice_previews"):
        assert not (assets / name).exists(), f"{name} là dữ liệu của Studio, không thuộc bộ cài"
    assert VOICE_PREVIEW_FILENAMES and all(preview_file(name) is None for name in VOICE_PREVIEW_FILENAMES)
    print("không có dữ liệu Studio -> không có nút nghe thử")
    print("Python", sys.version.split()[0], "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
