"""Optional portrait decoration. Never writes analysis, casting, audio settings or RNG state."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sqlite3
import time
import unicodedata
import urllib.request
import urllib.parse
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from . import book_paths
from .io_utils import file_lock, sqlite_read_only_uri

DB = "avatars.sqlite3"
CONFIG = "avatar_service.json"
IMAGE_NAME = re.compile(r"avatars/[0-9a-f]{64}\.webp")
MAX_IMAGE_BYTES = 4 * 1024 * 1024
STYLE = ("Minimal flat editorial portrait illustration, head and shoulders, one person, centered face, "
         "warm ivory background, muted brass and brown palette, elegant clean shapes, subtle facial detail, "
         "consistent vector illustration style, fully clothed, square avatar, no text, no letters, no watermark.")
PALETTE = ("#805c38", "#675f48", "#73594c", "#4c6963", "#66607a", "#80565e")
_APPEARANCE = re.compile(r"tóc|mắt|khuôn mặt|làn da|râu|kính|cao|gầy|béo|sẹo|hair|eyes|beard|glasses|scar|skin", re.I)


def hash32(text: str) -> int:
    """FNV-1a over UTF-8 of NFC text; shared with TypeScript, Kotlin and QML."""
    value = 2166136261
    for byte in unicodedata.normalize("NFC", text).encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return value


def fallback(name: str) -> dict[str, Any]:
    key = unicodedata.normalize("NFC", name)
    words = re.sub(r"_", " ", key).split()
    initials = "".join(word[0] for word in words if not re.fullmatch("[IVXLCDM]+", word))[:2].upper()
    number = hash32(key)
    return {"kind": "pattern", "key": key, "initials": initials, "color": PALETTE[number % len(PALETTE)],
            "bits": number & 32767}


def voice_file(name: str) -> str:
    return f"voice-{hash32(name):08x}.webp"


def voice_avatar(name: str) -> dict[str, Any]:
    path = Path(__file__).parent / "assets" / "voice_avatars" / voice_file(name)
    return {"kind": "voice", "file": path.name, "key": name} if path.is_file() else fallback(name)


def portrait_key(name: str) -> str:
    """The one portrait key, for every write and every read: the cast shows a speaker as written ("Lucien"), the character
    book keys "LUCIEN" - both must land on the same row (soát 0.4.173 B3). Same rule as store.speaker_key."""
    return " ".join(str(name).strip().casefold().split()).upper()


def portrait(saved: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    """The saved portrait of a speaker, written any way the cast writes it, or its pattern."""
    return saved.get(portrait_key(name)) or fallback(name)


def _connect(root: Path) -> sqlite3.Connection:
    path = book_paths.inside(root, str((root / DB).absolute()))
    connection = sqlite3.connect(path, timeout=15)
    connection.execute("CREATE TABLE IF NOT EXISTS portraits (name TEXT PRIMARY KEY, revision INTEGER NOT NULL, "
                       "chosen INTEGER NOT NULL, payload TEXT NOT NULL, provenance TEXT NOT NULL)")
    return connection


def entries(root: Path) -> dict[str, dict[str, Any]]:
    path = book_paths.inside(root, str((root / DB).absolute()))
    if not path.is_file():
        return {}
    with closing(sqlite3.connect(sqlite_read_only_uri(path), uri=True)) as connection:
        return {portrait_key(name): json.loads(payload) for name, payload in connection.execute("SELECT name,payload FROM portraits")}


def decorate(root: Path, cast: dict[str, Any]) -> dict[str, Any]:
    """Fresh projection; do not mutate the cast cache or include private prompts in cast.json."""
    saved = entries(root)
    result = dict(cast)
    for group in ("characters", "extras", "carried"):
        result[group] = [{**person, "avatar": portrait(saved, person["name"])}
                         for person in cast.get(group, [])]
    result["narrator"] = {**cast.get("narrator", {}), "avatar": voice_avatar(str(cast.get("narrator", {}).get("voice") or "NARRATOR"))}
    return result


def cast(root: Path) -> dict[str, Any]:
    """Studio / listening cast with portraits; the analysis-owned store stays untouched."""
    from .webui import store
    return decorate(root, store.cast(root))


def recorded_cast(root: Path) -> dict[str, Any]:
    from .webui import store
    return decorate(root, store.recorded_cast(root))


def script(chapter: dict[str, Any] | None, people: dict[str, Any]) -> dict[str, Any] | None:
    """Speaker images on read-along lines, matched by the shown name so a line and the cast row share one picture.

    Pattern portraits are not added: every client derives the same pattern from the speaker name itself.
    """
    if not chapter:
        return chapter
    shown = {}
    for group in ("characters", "extras", "carried"):
        for person in people.get(group) or []:
            avatar = person.get("avatar") if isinstance(person, dict) else None
            if isinstance(avatar, dict) and avatar.get("kind") != "pattern":
                shown.setdefault(str(person.get("displayName") or person.get("name") or ""), avatar)
    if not shown:
        return chapter
    segments = [{**segment, "avatar": shown[segment["speaker"]]}
                if isinstance(segment, dict) and segment.get("speaker") in shown else segment
                for segment in chapter.get("segments") or []]
    return {**chapter, "segments": segments}


def image_file(root: Path, relative: str) -> Path | None:
    if not IMAGE_NAME.fullmatch(relative):
        return None
    file = book_paths.inside(root, str((root / relative).absolute()))
    return file if file.is_file() else None


def image_files(root: Path, cast: dict[str, Any]) -> dict[str, Path]:
    out = {}
    for group in ("characters", "extras", "carried"):
        for person in cast.get(group, []):
            avatar = person.get("avatar") or {}
            file = image_file(root, str(avatar.get("file") or ""))
            if file is not None:
                out[avatar["file"]] = file
    return out


def normalize_image(data: bytes) -> bytes:
    """Decode bounded raster input, strip metadata, crop a square and encode 256px WebP."""
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Ảnh quá lớn. Bạn chọn ảnh dưới 4 MB.")
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data), formats=("PNG", "JPEG", "WEBP")) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError("Ảnh quá lớn. Bạn chọn ảnh nhỏ hơn.")
        image.load()
        square = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (256, 256), method=Image.Resampling.LANCZOS)
        out = io.BytesIO()
        square.save(out, format="WEBP", quality=85, method=6)
        return out.getvalue()


def _store_image(root: Path, data: bytes) -> dict[str, Any]:
    data = normalize_image(data)
    digest = hashlib.sha256(data).hexdigest()
    relative = f"avatars/{digest}.webp"
    path = book_paths.inside(root, str((root / relative).absolute()))
    path.parent.mkdir(parents=True, exist_ok=True)
    from .io_utils import atomic_write_bytes
    atomic_write_bytes(path, data)
    return {"kind": "image", "file": relative, "sha256": digest}


def choose(root: Path, name: str, data: bytes | None) -> dict[str, Any]:
    payload = _store_image(root, data) if data is not None else fallback(name)
    with closing(_connect(root)) as connection, connection:
        connection.execute("INSERT INTO portraits VALUES (?,1,1,?,?) ON CONFLICT(name) DO UPDATE SET "
                           "revision=revision+1,chosen=1,payload=excluded.payload,provenance=excluded.provenance",
                           (portrait_key(name), json.dumps(payload), json.dumps({"source": "user"})))
    return payload


def appearance(name: str, text: str, names: list[str]) -> list[str]:
    """Conservative extractive evidence: direct subject, appearance cue, no other named person or quotation.

    Ambiguous pronouns and indirect mentions are omitted rather than inventing an appearance.
    """
    subject = re.compile(r"^" + re.escape(name) + r"(?:\s+(?:có|là|mang|đeo|cao|gầy|mặc|has|is|wears)\b|\s*,)", re.I)
    found = []
    for sentence in re.split(r"(?<=[.!?。])\s+|[\r\n]+", text):
        sentence = sentence.strip()
        if (len(sentence) > 500 or not subject.search(sentence) or not _APPEARANCE.search(sentence)
                or any(char in sentence for char in '“”"「」')
                or any(other.casefold() != name.casefold() and re.search(r"\b" + re.escape(other) + r"\b", sentence, re.I) for other in names)):
            continue
        if sentence not in found:
            found.append(sentence)
        if len(found) == 4:
            break
    return found


def prompt_for(person: dict[str, Any], quotes: list[str]) -> str:
    gender = {"male": "male", "female": "female"}.get(person.get("gender"), "person")
    age = {"child": "child", "teen": "teenager", "young": "young adult", "adult": "adult",
           "middle_aged": "middle-aged", "elderly": "elderly"}.get(person.get("age"), "age unspecified")
    # Metadata is an illustration brief, not additional source evidence.
    return f"{STYLE} Fictional {gender}, {age}. Appearance evidence from the book: " + (" ".join(quotes) if quotes else "unspecified; neutral illustrative interpretation.")


def service_config(root: Path) -> dict[str, Any] | None:
    path = book_paths.inside(root, str((root / CONFIG).absolute()))
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    if not config.get("enabled"):
        return None
    url = str(config.get("url") or "")
    if not url.startswith("https://") or urllib.parse.urlsplit(url).username:
        raise ValueError("Dịch vụ ảnh cần địa chỉ HTTPS.")
    return config


def remote_image(config: dict[str, Any], prompt: str, seed: int) -> bytes:
    headers = {"Content-Type": "application/json"}
    # Credentials stay in an existing configured environment variable, never project/export metadata.
    if variable := config.get("tokenEnv"):
        import os
        headers["Authorization"] = "Bearer " + os.environ[str(variable)]
    request = urllib.request.Request(config["url"], json.dumps({"prompt": prompt, "seed": seed}).encode(), headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read(MAX_IMAGE_BYTES * 2 + 1)
    if len(body) > MAX_IMAGE_BYTES * 2:
        raise ValueError("Dịch vụ trả ảnh quá lớn.")
    return base64.b64decode(json.loads(body)["image"], validate=True)


def generate(root: Path, person: dict[str, Any], quotes: list[str], *, force: bool = False,
             renderer: Callable[[str, int], bytes] | None = None) -> dict[str, Any]:
    name = portrait_key(person["canonical_name"])
    config = service_config(root) if renderer is None else None
    if renderer is None and config is None:
        # Nothing is stored, so a service configured later still runs; a read never creates the database.
        return entries(root).get(name) or fallback(name)
    with closing(_connect(root)) as connection:
        row = connection.execute("SELECT revision,chosen,payload FROM portraits WHERE name=?", (name,)).fetchone()
        if row and not force:
            payload = json.loads(row[2])
            # The user's choice is final; a missing generated file is regenerated.
            if row[1] or (payload.get("kind") == "image" and image_file(root, payload.get("file", ""))):
                return payload
        revision = row[0] if row else 0
    seed = (hash32(name) + (revision if force else 0)) & 0xFFFFFFFF
    prompt = prompt_for(person, quotes)
    started = time.perf_counter()
    payload = (_store_image(root, renderer(prompt, seed) if renderer else remote_image(config, prompt, seed))
               if renderer or config else fallback(name))
    provenance = {"prompt": prompt, "seed": seed, "evidence": quotes, "seconds": time.perf_counter() - started,
                  "model": (config or {}).get("model", "injected" if renderer else "pattern-v1")}
    with closing(_connect(root)) as connection, connection:
        if revision:
            changed = connection.execute("UPDATE portraits SET revision=revision+1,chosen=?,payload=?,provenance=? "
                "WHERE name=? AND revision=?", (int(force), json.dumps(payload), json.dumps(provenance), name, revision)).rowcount
        else:
            changed = connection.execute("INSERT OR IGNORE INTO portraits VALUES (?,1,?,?,?)",
                (name, int(force), json.dumps(payload), json.dumps(provenance))).rowcount
    # A user's selection during the request always wins.
    return payload if changed else entries(root)[name]


def run_after_analysis(root: Path, stop: Callable[[], bool], log: Callable[[str], None], *,
                       paused: Callable[[], bool] = lambda: False,
                       renderer: Callable[[str, int], bytes] | None = None) -> None:
    from .pipeline import PipelineStopped
    from .webui import store
    if renderer is None and service_config(root) is None:
        return  # deterministic pattern portraits need no step and no stored state
    with closing(store.connect(root)) as connection:
        if connection.execute("SELECT COUNT(*) FROM segments WHERE status='pending'").fetchone()[0]:
            return
        people = [dict(row) for row in connection.execute("SELECT canonical_name,display_name,gender,age FROM characters ORDER BY id")]
        chapters = [dict(row) for row in connection.execute("SELECT id FROM chapters ORDER BY id")]
    named = [p for p in people if p["canonical_name"] != "NARRATOR" and not p["canonical_name"].startswith(("NPC", "EXTRA"))]
    names = [p["display_name"] for p in named]
    with file_lock(root / "avatar_generation", timeout=0.1):
        saved = entries(root)
        todo = [p for p in named if (saved.get(portrait_key(p["canonical_name"])) or {}).get("kind") != "image"]
        # Text is read only when needed and is never committed to the repository.
        for person in todo:
            while paused() and not stop():
                time.sleep(0.1)
            if stop():
                raise PipelineStopped("Stop requested during avatar preparation")
            evidence = []
            if renderer or service_config(root):
                for chapter in chapters:
                    text = store.chapter_source_text(root, chapter["id"]) or ""
                    evidence.extend(appearance(person["display_name"], text, names))
                    if len(evidence) >= 4:
                        break
            try:
                generate(root, person, evidence[:4], renderer=renderer)
            except Exception as exc:
                # Optional decoration cannot fail or change the audio pipeline. Leave absent for a safe retry.
                log(f"Chưa sinh được ảnh nhân vật; giữ hoạ tiết: {type(exc).__name__}")
            if stop():
                raise PipelineStopped("Stop requested during avatar preparation")
