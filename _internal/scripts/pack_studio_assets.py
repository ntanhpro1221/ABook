"""Đóng gói dữ liệu chỉ Studio dùng (từ điển phát âm + giọng nghe thử) thành MỘT gói zip để đăng và ghim.

    runtime/.venv/Scripts/python.exe scripts/pack_studio_assets.py [--out thư_mục]

Bộ cài chỉ-nghe không mang chúng (docs/PACKAGING.md): Studio tải gói này ở bước "Từ điển phát âm và giọng nghe thử"
(webui/studio_setup.py, STUDIO_ASSETS). Gói đúng các `ASSET_PATHS` của `abook/assets`, byte y hệt - nên hash chính sách
chất lượng (`voice_previews_sha256`) của máy có Studio không đổi so với chạy từ mã nguồn. Đóng gói xác định (thứ tự, giờ
file, mức nén cố định): cùng nguồn thì cùng băm.

In tên file, cỡ, SHA-256 và dòng `STUDIO_ASSETS` để dán vào studio_setup.py sau khi đăng (URL ghim theo commit). Không đăng gì.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abook.webui.studio_setup import ASSET_PATHS  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "abook" / "assets"
ARCHIVE_NAME = "studio-assets-2.zip"  # 2: thêm giọng nghe thử ZeroTTS (5) và Supertonic (4), 04-10
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def pack(assets: Path, target: Path) -> Path:
    files = sorted(path for name in ASSET_PATHS for path in ([assets / name] if (assets / name).is_file()
                                                              else (assets / name).rglob("*")) if path.is_file())
    if not files:
        raise SystemExit(f"Không có file nào của {', '.join(ASSET_PATHS)} trong {assets}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(assets).as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, path.read_bytes(), compresslevel=9)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path.cwd(), help="thư mục ghi gói (mặc định: thư mục hiện tại)")
    args = parser.parse_args(argv)
    archive = pack(ASSETS, args.out / ARCHIVE_NAME)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"{archive}  {archive.stat().st_size:,} byte  sha256 {digest}")
    print(f'STUDIO_ASSETS = Download("studio-assets", "<URL ghim theo commit>/{ARCHIVE_NAME}", "{digest}", '
          f"{archive.stat().st_size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
