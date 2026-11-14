"""Book organization, independent of analysis, casting and generation identity."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from . import book_paths
from .database import ProjectDB

MAX_VOLUMES = 99
COVER_FILE = re.compile(r"covers/[1-9][0-9]{0,8}\.jpg")
TREE_VERSION = 6  # first `.abook` version whose book.json may carry `volumes` (bookfile.FORMAT_VERSION)
DEFAULT_TITLE = "Quyển 1"


def volumes_of(book: dict[str, Any]) -> list[dict[str, Any]]:
    """The book's volumes; a book.json without `volumes` is one volume holding every chapter (the book cover stands for it)."""
    volumes = book.get("volumes")
    if volumes:
        return volumes
    return [{"id": 1, "number": 1, "title": DEFAULT_TITLE, "cover": None, "chapters": list(book.get("chapters") or [])}]


def needs_tree(book: dict[str, Any]) -> bool:
    """Only several volumes, or a volume with its own cover, are written as a tree; one plain volume stays a flat chapter list."""
    volumes = book.get("volumes") or []
    return len(volumes) > 1 or any(volume.get("cover") for volume in volumes)


def group(chapters: list[dict[str, Any]], volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach chapter objects without copying or changing the global sequence."""
    result = [{**volume, "chapters": []} for volume in volumes]
    by_id = {volume["id"]: volume for volume in result}
    if not result:
        raise ValueError("A book requires a volume")
    for chapter in chapters:
        identifier = chapter.get("volumeId") or result[0]["id"]
        if identifier not in by_id:
            raise ValueError("Chapter refers to an unknown volume")
        by_id[identifier]["chapters"].append(chapter)
    if [c["id"] for v in result for c in v["chapters"]] != [c["id"] for c in chapters]:
        raise ValueError("Volume boundaries must preserve global chapter order")
    return result


VOLUMES_FILE = "volumes.json"  # in the project folder; travels inside `.abookproj` with every other project file


def _meta(volume: dict[str, Any]) -> dict[str, Any]:
    return {"id": volume["id"], "number": volume["number"], "title": volume["title"], "cover": volume.get("cover")}


def _check(volume: Any, ids: set[int]) -> None:
    if not isinstance(volume, dict):
        raise ValueError("Invalid volume")
    identifier, number, title = volume.get("id"), volume.get("number"), volume.get("title")
    if (type(identifier) is not int or not 1 <= identifier <= 999999999 or identifier in ids
            or type(number) is not int or not 1 <= number <= 9999
            or not isinstance(title, str) or not title.strip() or len(title) > 240):
        raise ValueError("Volumes require a unique id, number and title")
    cover = volume.get("cover")
    if cover is not None and (not isinstance(cover, dict) or not isinstance(cover.get("file"), str)
                              or not COVER_FILE.fullmatch(cover["file"])):
        raise ValueError("Invalid volume cover")
    ids.add(identifier)


def stored(root: Path) -> list[dict[str, Any]]:
    """The project's volumes as saved: [{id, number, title, cover, start}], `start` = id of the volume's first chapter (None for
    the first volume). No file means one volume holding every chapter."""
    path = Path(root) / VOLUMES_FILE
    if not path.is_file():
        return [{"id": 1, "number": 1, "title": DEFAULT_TITLE, "cover": None, "start": None}]
    data = json.loads(path.read_text(encoding="utf-8"))
    volumes = data.get("volumes") if isinstance(data, dict) else None
    if not isinstance(volumes, list) or not 1 <= len(volumes) <= MAX_VOLUMES:
        raise ValueError("volumes.json is invalid")
    ids: set[int] = set()
    for volume in volumes:
        _check(volume, ids)
        if volume.get("start") is not None and type(volume["start"]) is not int:
            raise ValueError("volumes.json is invalid")
    return volumes


def project(root: Path, chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group the project's chapters (global order, unchanged) into volumes and label each chapter with `volumeId`. A volume whose
    first chapter is gone (chapters redone) folds into the one before; the order of chapters always wins."""
    volumes = stored(root)
    starts = {volume["start"]: volume for volume in volumes[1:] if volume.get("start") is not None}
    current, result, used = volumes[0], [], set()
    for chapter in chapters:
        begins = starts.get(chapter.get("id"))
        if begins is not None and begins["id"] not in used:
            current = begins
        if not result or result[-1]["id"] != current["id"]:
            used.add(current["id"])
            result.append({**_meta(current), "chapters": []})
        chapter["volumeId"] = current["id"]
        result[-1]["chapters"].append(chapter)
    return result or [{**_meta(volumes[0]), "chapters": []}]


def _write(root: Path, volumes: list[dict[str, Any]]) -> None:
    from .io_utils import atomic_write_json

    atomic_write_json(Path(root) / VOLUMES_FILE, {"volumes": volumes})


def organize(root: Path, definitions: list[dict[str, Any]]) -> None:
    """Save the volume boundaries in one atomic write. Never touches the database: sources, segments, settings, voices and seeds
    stay exactly as they are."""
    if not isinstance(definitions, list) or not 1 <= len(definitions) <= MAX_VOLUMES:
        raise ValueError("Choose between 1 and 99 volumes")
    db = ProjectDB(Path(root) / "project.sqlite3")
    chapters = [chapter["id"] for chapter in db.list_chapters()]
    covers = {volume["id"]: volume.get("cover") for volume in stored(root)}
    ids: set[int] = set()
    assigned: list[int] = []
    result = []
    for volume in definitions:
        _check({**volume, "cover": None}, ids)
        selected = volume.get("chapters")
        if not isinstance(selected, list) or not selected or any(type(c) is not int for c in selected):
            raise ValueError("Every volume needs its chapters")
        assigned.extend(selected)
        result.append({"id": volume["id"], "number": volume["number"], "title": volume["title"].strip(),
                       "cover": covers.get(volume["id"]), "start": selected[0] if result else None})
    if assigned != chapters:
        raise ValueError("Every chapter must occur once, in its existing global order")
    _write(root, result)


def save_cover(root: Path, identifier: int, data: bytes | None) -> None:
    from .io_utils import atomic_write_bytes
    from .webui import covers

    volumes = stored(root)
    volume = next((volume for volume in volumes if volume["id"] == identifier), None)
    if volume is None:
        raise ValueError("Unknown volume")
    meta = None
    if data is not None:
        jpeg, details = covers.render_cover(data)
        relative = f"covers/{identifier}.jpg"
        target = book_paths.inside(Path(root), str((Path(root) / relative).resolve()))
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, jpeg)
        meta = {**details, "version": covers.content_version(jpeg), "file": relative}
    volume["cover"] = meta
    _write(root, volumes)


def cover_files(root: Path, volumes: list[dict[str, Any]]) -> dict[str, Path]:
    files = {}
    for volume in volumes:
        cover = volume.get("cover")
        if cover is None:
            continue
        name = cover.get("file") if isinstance(cover, dict) else None
        if not isinstance(name, str) or not COVER_FILE.fullmatch(name):
            raise ValueError("Invalid volume cover path")
        files[name] = book_paths.inside(root, str((root / name).resolve()))
    return files


def flatten(book: dict[str, Any]) -> dict[str, Any]:
    """Validate the on-disk tree and add the in-memory playback projection. Without `volumes` the book is one volume."""
    if "volumes" not in book:
        return book
    volumes = book.get("volumes")
    if not isinstance(volumes, list) or not 1 <= len(volumes) <= MAX_VOLUMES:
        raise ValueError("Book volumes are missing or invalid")
    ids, chapters = set(), []
    for volume in volumes:
        if not isinstance(volume, dict):
            raise ValueError("Invalid volume")
        identifier, number, title = volume.get("id"), volume.get("number"), volume.get("title")
        rows = volume.get("chapters")
        if (type(identifier) is not int or not 1 <= identifier <= 999999999 or identifier in ids
                or type(number) is not int or not 1 <= number <= 9999
                or not isinstance(title, str) or not title.strip() or len(title) > 240
                or not isinstance(rows, list) or not rows):
            raise ValueError("Invalid volume metadata or empty volume")
        ids.add(identifier)
        cover = volume.get("cover")
        if cover is not None and (not isinstance(cover, dict) or not isinstance(cover.get("file"), str)
                                  or not COVER_FILE.fullmatch(cover["file"])):
            raise ValueError("Invalid volume cover")
        indices = []
        for chapter in rows:
            if (not isinstance(chapter, dict) or type(chapter.get("id")) is not int
                    or ("index" in chapter and type(chapter["index"]) is not int)):
                raise ValueError("Invalid chapter identity")
            chapter["volumeId"] = identifier
            chapters.append(chapter)
            if "index" in chapter:
                indices.append(chapter["index"])
        # A series file numbers chapters inside each part; within one volume the order is always ascending.
        if indices != sorted(set(indices)):
            raise ValueError("Duplicate or unordered chapters")
    if len({c["id"] for c in chapters}) != len(chapters):
        raise ValueError("Duplicate or unordered chapters")
    if "chapters" in book and [c["id"] for c in book["chapters"]] != [c["id"] for c in chapters]:
        raise ValueError("Chapter projection differs from volumes")
    book["chapters"] = chapters
    return book


def nested(book: dict[str, Any]) -> dict[str, Any]:
    """Serialize one authoritative tree, using the current chapter projection."""
    result = copy.deepcopy(book)
    chapters = result.pop("chapters", [])
    metadata = result.get("volumes") or [{"id": 1, "number": 1, "title": DEFAULT_TITLE, "cover": None}]
    result["volumes"] = group(chapters, metadata)
    if not needs_tree(result):
        # Same keys in the same order as before volumes existed: a one-volume book.json is byte-identical.
        flat = copy.deepcopy({key: value for key, value in book.items() if key != "volumes"})
        if "chapters" in flat:
            flat["chapters"] = [{key: value for key, value in chapter.items() if key != "volumeId"} for chapter in flat["chapters"]]
        return flat
    flatten(result)
    result.pop("chapters")
    return result
