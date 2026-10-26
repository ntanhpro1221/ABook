"""Dựng một thư viện thử CÓ THẬT để đo lưới bìa: N cuốn chỉ-có-chữ (nhập qua chính API của host) + ảnh bìa JPEG 600x900 cho phần lớn.

Không đụng thư viện của người dùng: dữ liệu nằm trọn trong <out>, host chạy với ABOOK_PREFERENCES riêng.
Chữ truyện là văn bản giả (lặp một đoạn vô nghĩa), không lấy từ truyện nào.

  python -X utf8 make_fixture.py <out> [--books 200] [--covers 0.8] [--long]
Sau đó chạy app với:  ABOOK_PREFERENCES=<out>/prefs.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from PIL import Image, ImageDraw, ImageFont

INTERNAL = Path(__file__).resolve().parents[2]          # _internal của worktree
PYTHON = os.environ.get("ABOOK_HOST_PYTHON", str(Path("D:/Novels/ABook/_internal/runtime/.venv/Scripts/pythonw.exe")))

WORDS = "gió mưa núi sông trăng nắng thuyền bến đèn phố chợ mùa lúa mây đường quán sách thư hạc kiếm đồi suối".split()
SERIES = ["Bộ Mây Núi", "Chuyện Bến Sông", "Nhật Ký Phố Cổ", "Hạc Và Kiếm"]


def title_for(i: int, rng: random.Random, long_titles: bool = False) -> str:
    if long_titles and i % 5 == 0:     # tên dài: kiểm xuống dòng đủ ở lưới, bìa vẽ, tiêu đề trang
        return " ".join(rng.choice(WORDS) for _ in range(rng.choice([14, 22, 34]))).capitalize() + f" {i:03d}"
    if long_titles and i % 11 == 0:    # một chữ dài không có chỗ ngắt
        return "Vôcùngdàiliềnmạchkhôngchỗngắtchữnàocả" * 2 + f"{i:03d}"
    if i % 7 == 0:
        return f"{SERIES[i % len(SERIES)]} · Tập {i // 7 + 1}"
    n = rng.choice([2, 3, 3, 4, 5, 7])
    return " ".join(rng.choice(WORDS).capitalize() if k == 0 else rng.choice(WORDS) for k in range(n)) + f" {i:03d}"


def cover_jpeg(i: int, title: str, rng: random.Random) -> bytes:
    w, h = 600, 900
    a = tuple(rng.randrange(30, 200) for _ in range(3))
    b = tuple(rng.randrange(10, 120) for _ in range(3))
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(a[k] * (1 - t) + b[k] * t) for k in range(3)))
    d = ImageDraw.Draw(img)
    for _ in range(14):  # nhiễu hình học để JPEG có kích thước thật (vài chục KB)
        x0, y0 = rng.randrange(w), rng.randrange(h)
        r = rng.randrange(20, 260)
        d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], outline=tuple(min(255, c + 70) for c in a), width=rng.randrange(1, 5))
    try:
        font = ImageFont.truetype("arial.ttf", 54)
    except OSError:
        font = ImageFont.load_default()
    d.text((40, 60), f"#{i}", fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=84)
    return buf.getvalue()


class Host:
    def __init__(self, prefs: Path) -> None:
        env = dict(os.environ, ABOOK_PREFERENCES=str(prefs), PYTHONIOENCODING="utf-8")
        self.proc = subprocess.Popen([PYTHON, "-m", "abook.webui.host", "--version", "fixture"], cwd=INTERNAL, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        line = self.proc.stdout.readline()
        ready = json.loads(line)["ready"]
        url = urlparse(ready)
        self.base = f"http://127.0.0.1:{url.port}"
        self.token = parse_qs(url.query)["t"][0]

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"X-Ebook-Token": self.token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")

    def stop(self) -> None:
        try:
            self.proc.stdin.write('{"quit": true}\n')
            self.proc.stdin.flush()
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--books", type=int, default=200)
    ap.add_argument("--covers", type=float, default=0.8)
    ap.add_argument("--long", action="store_true", help="xen tên rất dài vào thư viện thử")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    (out / "library").mkdir(parents=True, exist_ok=True)
    (out / "src").mkdir(exist_ok=True)
    prefs = out / "prefs.json"
    prefs.write_bytes(json.dumps({"libraryRoot": str(out / "library")}).encode("utf-8"))
    rng = random.Random(20261026)
    host = Host(prefs)
    try:
        for i in range(1, args.books + 1):
            title = title_for(i, rng, args.long)
            src = out / "src" / f"{i:03d}.txt"
            para = " ".join(rng.choice(WORDS) for _ in range(40)) + "."
            src.write_bytes(("\n\n".join([para] * 6) + "\n").encode("utf-8"))  # LF
            added = host.call("POST", "/api/listen/import", {"path": str(src), "title": title, "separate": True, "splitChapters": False})
            if rng.random() < args.covers:
                raw = cover_jpeg(i, title, rng)
                host.call("PUT", f"/api/books/{added['id']}/cover", {"image": "data:image/jpeg;base64," + base64.b64encode(raw).decode()})
            if i % 25 == 0:
                print(f"{i}/{args.books}", flush=True)
        library = host.call("GET", "/api/listen/library")
        print(f"thư viện: {len(library)} cuốn, {sum(1 for b in library if b.get('cover'))} có bìa ảnh")
    finally:
        host.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
