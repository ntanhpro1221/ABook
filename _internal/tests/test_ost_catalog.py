"""The public OST reference catalog (music/ost_catalog.json) stays metadata only and matches its schema.

It lists copyrighted soundtrack pieces kept for private books, so the file must never point at audio we host or at review
pages: the only URL allowed is the original upload in ``audio_source.url``. Every entry explains itself in its own words
(``description``) instead of linking to what others wrote."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from abook.webui.music_scenes import EMOTION_CLASSES

MUSIC = Path(__file__).resolve().parents[1] / "music"
CATALOG = json.loads((MUSIC / "ost_catalog.json").read_text("utf-8"))
SCHEMA = json.loads((MUSIC / "ost_catalog.schema.json").read_text("utf-8"))
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict, "array": list, "null": type(None)}


def check(value, schema, where="$"):
    """The subset of JSON Schema the catalog schema uses."""
    errors = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        ok = any(isinstance(value, TYPES[k]) and not (k in ("integer", "number") and isinstance(value, bool)) for k in kinds)
        if not ok:
            return [f"{where}: {type(value).__name__} is not {kinds}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: {value!r} != {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} not in enum")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: {value} > {schema['maximum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors += [f"{where}: missing {k}" for k in schema.get("required", []) if k not in value]
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in props:
                errors += check(item, props[key], f"{where}.{key}")
            elif extra is False:
                errors.append(f"{where}: unexpected {key}")
            elif isinstance(extra, dict):
                errors += check(item, extra, f"{where}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{where}: {len(value)} items")
        errors += [e for i, item in enumerate(value) for e in check(item, schema.get("items", {}), f"{where}[{i}]")]
    return errors


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def test_catalog_matches_schema():
    assert check(CATALOG, SCHEMA) == []
    assert all(key == track["id"] for key, track in CATALOG["tracks"].items())


def test_schema_labels_are_the_selector_classes():
    labels = SCHEMA["properties"]["tracks"]["additionalProperties"]["properties"]["labels"]["items"]["enum"]
    assert sorted(labels) == sorted(EMOTION_CLASSES)


def test_no_url_outside_the_original_upload():
    for track in CATALOG["tracks"].values():
        rest = {k: v for k, v in track.items() if k != "audio_source"}
        text = json.dumps(rest, ensure_ascii=False)
        assert not re.search(r"https?://|www\.|tvtropes|reddit|myanimelist|vndb|blog", text, re.I), track["id"]
        assert "evidence" not in track and "file" not in track and "link" not in track


def test_no_private_store_named():
    text = (MUSIC / "ost_catalog.json").read_text("utf-8")
    assert "huggingface" not in text.lower() and "Music_Private" not in text and "abook-music" not in text


def test_every_track_is_described_in_its_own_words():
    descriptions = [t["description"] for t in CATALOG["tracks"].values()]
    assert all(2 <= len(sentences(d)) <= 6 for d in descriptions)
    assert len(set(descriptions)) == len(descriptions)
    repeats = Counter(s for d in descriptions for s in sentences(d))
    assert max(repeats.values()) <= 5, repeats.most_common(3)
    assert all(t["quality_note"].strip() for t in CATALOG["tracks"].values())


def test_tracks_kept_for_narration_have_no_vocals():
    for track in CATALOG["tracks"].values():
        if "excluded_reason" not in track:
            assert track["vocals"] is False, track["id"]


def test_superseded_uploads_point_at_a_kept_official_release():
    tracks = CATALOG["tracks"]
    for track in tracks.values():
        new_id = track.get("superseded_by")
        if new_id is None:
            continue
        assert "excluded_reason" in track, track["id"]
        new = tracks[new_id]
        assert "excluded_reason" not in new and new["audio_source"]["version"] == "official", track["id"]
        assert new["labels"] == track["labels"], track["id"]
