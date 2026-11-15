"""Trusted speaker labels installed by an answer replay adapter, never by model JSON.

Labels are bound to source hashes and survive reopening the project. Repairs may
only change their spelling using identity links supplied with the answers.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_bytes

FILE = "speaker_labels.json"
MARKER = "_authoritative_speaker"


def name_key(name: str) -> str:
    name = unicodedata.normalize("NFC", name).strip()
    if name.startswith("NPC_LOCAL::"):
        return name.casefold()
    # Tiền tố NPC là một phần danh tính ("NPC X" và "X" là hai người): chỉ chuẩn cách viết nó, không bỏ.
    name = re.sub(r"^npc(?:[\s:_-]+)", "npc ", name, flags=re.IGNORECASE)
    words = [re.sub(r"-(?:san|sama|kun|chan|sensei|senpai|dono)$", "", word, flags=re.IGNORECASE)
             for word in name.replace("_", " ").split()]
    return " ".join(sorted(word.casefold() for word in words))


class SpeakerLabels:
    def __init__(self, labels: dict[str, dict[str, Any]] | None = None,
                 identities: dict[str, str] | None = None):
        self.labels = labels or {}
        self.identities = identities or {}

    def label(self, row: Any) -> dict[str, Any] | None:
        if not self.labels:
            return None
        label = self.labels.get(str(row["stable_id"]))
        if label is not None and label["text_sha256"] != str(row["text_sha256"]):
            raise ValueError("Authoritative speaker label source hash differs")
        return label

    def person(self, name: str) -> str:
        key = name_key(name)
        return self.identities.get(key, key)

    def allows(self, row: Any, speaker: str) -> bool:
        label = self.label(row)
        return label is None or self.person(label["speaker"]) == self.person(speaker)

    def require(self, row: Any, data: dict[str, Any]) -> None:
        speaker = str(data.get("speaker", "NARRATOR"))
        effective = "NARRATOR" if data.get("kind") == "narration" else speaker
        if not self.allows(row, speaker) or not self.allows(row, effective):
            raise ValueError("Host analysis conflicts with an authoritative speaker label")


def load(db: Any) -> SpeakerLabels:
    path = getattr(db, "path", None)
    if path is None:
        return SpeakerLabels()
    path = Path(path).parent / FILE
    try:
        stamp = path.stat().st_mtime_ns
    except FileNotFoundError:
        return SpeakerLabels()
    cached = getattr(db, "_speaker_labels_cache", None)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["version"] != 1 or not isinstance(data["labels"], dict) or not isinstance(data["identities"], dict):
        raise ValueError("Invalid authoritative speaker labels")
    labels = SpeakerLabels(data["labels"], data["identities"])
    db._speaker_labels_cache = (stamp, labels)
    return labels


def install(db: Any, labels: dict[str, dict[str, Any]], identities: dict[str, str]) -> None:
    """Called explicitly by the trusted replay adapter before analysis, after segmentation."""
    rows = {str(row["stable_id"]): row for row in db.list_segments()}
    bound = {}
    from .analysis import _canonical_speaker, _scope_local_speaker

    for stable_id, label in labels.items():
        row = rows[stable_id]
        if label["kind"] not in {"dialogue", "thought", "narration"} or not label["speaker"].strip():
            raise ValueError("Invalid authoritative speaker label")
        bound[stable_id] = {"kind": label["kind"], "speaker": _scope_local_speaker(_canonical_speaker(label["speaker"]), row),
                            "text_sha256": str(row["text_sha256"])}
    normalized = {name_key(alias): name_key(person) for alias, person in identities.items()}
    data = {"version": 1, "labels": bound, "identities": normalized}
    atomic_write_bytes(Path(db.path).parent / FILE, json.dumps(data, ensure_ascii=False).encode("utf-8"))


def protected(data: dict[str, Any]) -> bool:
    return data.get(MARKER) is True
