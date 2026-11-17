"""Ghi danh sách bộ tách (demuxer) và bộ giải âm thanh (audio decoder) của exe ffmpeg đang ghim trong `abook/webui/ffmpeg_setup.py`
vào `tests/fixtures/ffmpeg_pinned_codecs.json`, kèm SHA-256 của exe và dòng phiên bản.

`tests/test_music_local.py::test_the_pinned_ffmpeg_decodes_every_extension_the_app_accepts` đọc fixture này (luôn chạy, không cần exe),
kiểm fixture thuộc đúng `ffmpeg_setup.EXE_SHA256` và mỗi đuôi nhạc app nhận có đủ bộ tách + bộ giải. Đổi pin ffmpeg thì chạy lại:

    python scripts/ffmpeg_pinned_codecs.py <đường tới ffmpeg.exe đã ghim>

Script từ chối exe có SHA-256 khác `EXE_SHA256`. Đặt ABOOK_TEST_FFMPEG=<exe> khi chạy pytest thì test còn so fixture với exe thật.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ffmpeg_pinned_codecs.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(exe: Path, kind: str) -> list[tuple[str, str]]:
    """(cờ, tên) cho mỗi dòng sau vạch `---`/`------` của `ffmpeg -demuxers` / `-decoders`. Cột cờ rộng đúng bằng vạch và có thể chứa
    khoảng trắng (`D d dshow`: bộ tách là thiết bị), nên cắt theo cột chứ không tách theo khoảng trắng."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    lines = subprocess.run([str(exe), "-hide_banner", f"-{kind}"], capture_output=True, text=True, check=True, creationflags=flags).stdout.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() and set(line.strip()) == {"-"})
    width = len(lines[start].strip())
    return [(line[1:1 + width], line[1 + width:].split()[0]) for line in lines[start + 1:] if line[1 + width:].strip()]


def listing(exe: Path) -> dict[str, object]:
    """Cái test cần biết về một exe: phiên bản, mọi bộ tách (ffmpeg ghi nhiều tên chung một dòng như `mov,mp4,m4a,3gp,3g2,mj2`), bộ giải âm thanh."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    version = subprocess.run([str(exe), "-hide_banner", "-version"], capture_output=True, text=True, check=True, creationflags=flags).stdout.splitlines()[0]
    demuxers = sorted({name for flag, name in _rows(exe, "demuxers") if flag.startswith("D")})
    decoders = sorted({name for flag, name in _rows(exe, "decoders") if flag.startswith("A")})
    return {"version": version, "demuxers": demuxers, "audio_decoders": decoders}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    sys.path.insert(0, str(ROOT))
    from abook.webui import ffmpeg_setup

    exe = Path(argv[0])
    digest = sha256(exe)
    if digest != ffmpeg_setup.EXE_SHA256:
        print(f"{exe}: SHA-256 {digest} khác EXE_SHA256 đang ghim {ffmpeg_setup.EXE_SHA256}", file=sys.stderr)
        return 1
    record = {"exe_sha256": digest, "member": ffmpeg_setup.MEMBER, **listing(exe)}
    FIXTURE.write_bytes((json.dumps(record, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print(f"{FIXTURE}: {len(record['demuxers'])} demuxer, {len(record['audio_decoders'])} audio decoder; {record['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
