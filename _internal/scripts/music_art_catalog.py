"""Prepare unsigned artwork assets in a COPY of the music catalog; never publish or sign.

Public landing pages only, one request per second, resumable page/image cache.
Run: python -X utf8 scripts/music_art_catalog.py --catalog ... --out ...
The existing Worker static-asset store serves art/ alongside tracks/ after Lead review.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import json
import re
from pathlib import Path
import shutil
import time
from urllib.parse import urljoin

import requests
from PIL import Image, ImageOps

BASE = "https://abook-music.ngdtuanh.workers.dev"
SUPPORTED = {"jamendo", "fma", "scottbuckley", "silverman", "maoudamashii", "opengameart"}


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.images: list[str] = []
        self.assets: list[str] = []
        self.download_depth = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            if self.download_depth:
                self.download_depth += 1
            elif "field-name-field-art-files" in a.get("class", ""):
                self.download_depth = 1
        if tag == "a" and self.download_depth and re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", a.get("href", ""), re.I):
            self.assets.append(a["href"])
        if tag == "meta" and a.get("property", a.get("name")) in ("og:image", "twitter:image"):
            self.images.insert(0, a.get("content", ""))
        if tag == "img" and any(kind in unescape(a.get("src", "")) for kind in ("type=album", "type=track")):
            self.images.append(a["src"])

    def handle_endtag(self, tag):
        if tag == "div" and self.download_depth:
            self.download_depth -= 1


class PublicReader:
    def __init__(self, cache: Path):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers["User-Agent"] = "ABook-artwork/1.0 (public music library artwork; 1 request/second)"
        self.last = 0.0

    def get(self, url: str) -> bytes:
        key = self.cache / hashlib.sha256(url.encode()).hexdigest()
        if key.exists():
            return key.read_bytes()
        time.sleep(max(0, 1.0 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        with self.session.get(url, timeout=(10, 25), stream=True) as r:
            if r.status_code == 429:
                # Stop instead of hammering a throttled host; rerun resumes the cache.
                raise RuntimeError("rate limited; retry after " + r.headers.get("Retry-After", "later"))
            r.raise_for_status()
            raw = bytearray()
            for part in r.iter_content(65536):
                raw.extend(part)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("image/page exceeds 8 MiB")
        key.write_bytes(raw)
        return bytes(raw)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    src, out = args.catalog.resolve(), args.out.resolve()
    if src == out or src in out.parents or out in src.parents or any((p / ".git").exists() for p in (out, *out.parents)):
        ap.error("output must be an independent catalog copy outside Git")
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json.sig").unlink(missing_ok=True)
    # Do not copy stale signatures: this catalog is intentionally unsigned.
    for folder in ("tracks", "cells"):
        shutil.copytree(src / folder, out / folder, dirs_exist_ok=True)
    reader = PublicReader(out / ".." / "public-art-cache")
    assets = out / "art"
    assets.mkdir(exist_ok=True)
    records = []
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    # Confirm the local copy is the current public generation without downloading 256 identical shards.
    live = json.loads(reader.get(BASE + "/manifest.json"))
    if live["revision"] != manifest["revision"]:
        raise ValueError("public catalog changed; obtain that exact generation first")
    for relative, digest in manifest["files"].items():
        if hashlib.sha256((src / relative).read_bytes()).hexdigest() != digest:
            raise ValueError("catalog checksum mismatch: " + relative)
    failures = Counter()
    for shard in sorted((out / "tracks").glob("*.json")):
        tracks = json.loads(shard.read_text(encoding="utf-8"))
        for link, track in tracks.items():
            source, landing = track["source"], track.get("landing", "")
            record = {"link": link, "source": source, "landing": landing}
            reason = "source has no track-specific cover"
            if source == "opengameart":
                reason = "preview image rights not included automatically; OpenGameArt FAQ #preview"
            if source in SUPPORTED and failures[source] < 4:
                try:
                    page = reader.get(landing).decode("utf-8", errors="replace")
                    parsed = Page(page)
                    # OGA previews are not automatically licensed. Only submitted image assets qualify.
                    candidates = parsed.assets if source == "opengameart" else parsed.images
                    candidates = [urljoin(landing, unescape(u)) for u in candidates if u]
                    candidates = [u for u in candidates if not any(w in u.lower() for w in ("logo", "default", "favicon", "avatar", "twitter_card", "/wp-content/themes/"))]
                    if not candidates:
                        reason = ("no submitted cover image asset; preview rights are separate (OpenGameArt FAQ)"
                                  if source == "opengameart" else "no track/album image in public landing page")
                    else:
                        image_url = candidates[0]
                        if source == "jamendo":
                            image_url = image_url.replace("width=300", "width=600")
                        raw = reader.get(image_url)
                        with Image.open(io.BytesIO(raw)) as im:
                            im = ImageOps.exif_transpose(im)
                            if im.width < 80 or im.height < 80:
                                raise ValueError("image too small / placeholder")
                            rgba = im.convert("RGBA")
                            bg = Image.new("RGB", rgba.size, (239, 234, 224))
                            bg.paste(rgba, mask=rgba.getchannel("A"))
                            image = ImageOps.pad(bg, (512, 512), method=Image.Resampling.LANCZOS, color=(239, 234, 224))
                            data = io.BytesIO()
                            image.save(data, "JPEG", quality=88, optimize=True)
                        encoded = data.getvalue()
                        sha = hashlib.sha1(encoded).hexdigest()
                        (assets / (sha + ".jpg")).write_bytes(encoded)
                        art = {"url": BASE + "/art/" + sha + ".jpg", "sha1": sha, "w": 512, "h": 512,
                               "source": image_url, "landing": landing,
                               "credit": f"Artwork via {source} — {landing}",
                               "rights": "Source artwork; see original album/track page (music license is separate)"}
                        track["art"] = art
                        record["art"] = art
                        reason = "prepared"
                except requests.HTTPError as exc:
                    code = exc.response.status_code
                    reason = f"public source HTTP {code}"
                    if code in (403, 406, 429):
                        failures[source] += 1
                except (requests.RequestException, ValueError, OSError) as exc:
                    reason = type(exc).__name__ + ": " + str(exc)[:150]
            elif source in SUPPORTED:
                reason = "host blocked public requests; stopped after 4 failures"
            record["result"] = reason
            records.append(record)
        shard.write_text(json.dumps(tracks, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        (out.parent / "art-discovery.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        print(shard.name, len(records), sum("art" in r for r in records), flush=True)
    manifest["files"] = {rel: hashlib.sha256((out / rel).read_bytes()).hexdigest() for rel in manifest["files"]}
    manifest["revision"] = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True).encode()).hexdigest()[:12]
    manifest["issued"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["built"] = manifest["issued"]
    manifest["artwork"] = {"version": 1, "size": 512, "fit": "letterbox", "prepared": sum("art" in r for r in records)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "_headers").write_text("/art/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf-8")
    (assets / "ATTRIBUTION.json").write_text(json.dumps([r for r in records if "art" in r], ensure_ascii=False, indent=1), encoding="utf-8")
    referenced = {r["art"]["sha1"] for r in records if "art" in r}
    for path in assets.glob("*.jpg"):
        if path.stem not in referenced:
            path.unlink()
    for source in sorted({r["source"] for r in records}):
        subset = [r for r in records if r["source"] == source]
        print(source, sum("art" in r for r in subset), "/", len(subset))


if __name__ == "__main__":
    main()
