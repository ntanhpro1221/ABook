"""Read-only review ordering. Counts are observations; effort and urgency are estimates.

No error probability is inferred from a detector's doubt or severity. The tuple is
public and deterministic: applicable, upcoming, lines/action, tentative, key.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any


def expected_actions(item: dict[str, Any]) -> int:
    """Shortest offered decision, excluding optional listening and exceptions."""
    return 2 if item.get("kind") == "audio" else 1


def _ids(item: dict[str, Any], speakers: dict[str, set[str]], words: dict[str, set[str]]) -> set[str] | None:
    if item.get("lines") is not None:
        return {str(line["stableId"]) for line in item["lines"]}
    if item.get("surface"):
        return set(words.get(str(item["surface"]), ()))
    people = set(item.get("keepCharacters") or ())
    people.update(option["character"] for option in item.get("voiceChoices") or () if option.get("character"))
    if item.get("pickVoice"):
        people.add(item["pickVoice"]["name"])
    if people:
        return set().union(*(speakers.get(person, set()) for person in people))
    # Examples can include narration or only the first page; they are never a census.
    return None


def _decision(item: dict[str, Any]) -> str:
    """Deduplicate equivalent proposals, never pending/refused/undo or different scopes."""
    if item.get("kind") in {"speaker", "caller", "collective", "vocative", "unnamed", "snap"} and item.get("lines") and item.get("choices") is not None and not any(
        item.get(key) for key in ("requested", "undo", "refused", "allLines", "keepGroups", "narratorSection")
    ):
        return json.dumps(["speaker", sorted({(line["stableId"], line["textSha256"]) for line in item["lines"]}),
                           item.get("currentValue"), bool(item.get("pick"))], ensure_ascii=False)
    return "key:" + item["key"]


def rank(items: list[dict[str, Any]], rows: dict[str, dict], upcoming: set[int]) -> list[dict[str, Any]]:
    """Return new cards without changing the cached/input snapshot or request bodies.

    `recordedLines` counts stored recordings in the default scope, an upper bound
    on retakes, not a promise to replace them. Same-voice assignments can cost zero.
    Missing IDs/audio columns make that measurement unknown, not zero.
    """
    unique: dict[str, dict] = {}
    for item in sorted(items, key=lambda card: (not bool(card.get("pickVoice")), not bool(card.get("suggestedName")),
                                               bool(card.get("askLast")), str(card["key"]),
                                               json.dumps(card, sort_keys=True, ensure_ascii=False))):
        decision = _decision(item)
        if decision not in unique:
            unique[decision] = dict(item)
        elif decision.startswith("["):
            kept = unique[decision]
            choices = {choice["value"]: choice for choice in kept["choices"]}
            for choice in item["choices"]:
                choices.setdefault(choice["value"], choice)
            kept["choices"] = list(choices.values())
            for key in ("contextLines", "contextExamples", "suggestedName", "pickVoice"):
                if not kept.get(key) and item.get(key):
                    kept[key] = item[key]
            if item["problem"] != kept["problem"]:
                kept["problem"] += " " + item["problem"]
            # Multiple cues nominate alternatives, not a stronger recommendation.
            kept["suggested"] = False
    cards = list(unique.values())
    speakers: dict[str, set[str]] = defaultdict(set)
    words: dict[str, set[str]] = defaultdict(set)
    surfaces = {str(item["surface"]) for item in cards if item.get("surface")}
    for key, row in rows.items():
        speakers[row["speaker"]].add(key)
        if surfaces:
            for word in set(re.findall(r"\w+", row["text"])) & surfaces:
                words[word].add(key)
    scopes = [_ids(item, speakers, words) for item in cards]
    membership = Counter(key for scope in scopes if scope is not None for key in scope)
    result = []
    for index, original in enumerate(cards):
        item = dict(original)
        if item.get("lines") is not None:
            item["lines"] = list({(line["stableId"], line["textSha256"]): line for line in item["lines"]}.values())
        ids = scopes[index]
        known = ids is not None and ids <= rows.keys()
        selected = [rows[key] for key in sorted(ids or ()) if key in rows]
        chapters = {row["chapterId"] for row in selected} if known else set(item.get("chapters") or ())
        affected = len(ids) if ids is not None else int(item["affected"])
        item["affected"] = affected
        recorded = [row for row in selected if row.get("recorded") is True]
        measured = known and all(row.get("recorded") is not None for row in selected)
        actions = expected_actions(item)
        urgent = bool(chapters & upcoming) and not item.get("redoOnly") and not item.get("requested")
        reason = ("redo" if item.get("redoOnly") else "refused" if item.get("refused") else
                  "upcoming" if urgent else "tentative" if item.get("askLast") else "impact")
        item["priority"] = {
            "reason": reason, "lines": affected, "recordedLines": len(recorded) if measured else None,
            "recordedChapters": len({row["chapterId"] for row in recorded}) if measured else None,
            "estimatedActions": actions, "upcoming": urgent,
            "overlapLines": sum(membership[key] > 1 for key in ids or ()),
            "tentative": bool(item.get("askLast")),
        }
        # Compatibility field, now lines per estimated action, never probability.
        item["score"] = affected / actions
        result.append(item)
    result.sort(key=lambda item: (bool(item.get("redoOnly")), not item["priority"]["upcoming"],
                                 -Fraction(item["priority"]["lines"], item["priority"]["estimatedActions"]),
                                 item["priority"]["tentative"], str(item["key"])))
    return result


def read_snapshot(connection: Any) -> tuple[dict[str, dict], set[int]]:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(segments)")}
    audio = "wav_path" if "wav_path" in columns else "NULL AS wav_path"
    rows = {str(row["stable_id"]): {"chapterId": int(row["chapter_id"]), "text": str(row["text"]),
                                   "speaker": str(row["speaker"]),
                                   "recorded": bool(row["wav_path"]) if "wav_path" in columns else None}
            for row in connection.execute(f"SELECT stable_id, chapter_id, text, speaker, {audio} FROM segments")
            if row["stable_id"]}
    chapters = {row[1] for row in connection.execute("PRAGMA table_info(chapters)")}
    upcoming = set()
    if "status" in chapters:
        upcoming = {int(row[0]) for row in connection.execute(
            "SELECT id FROM chapters WHERE status != 'completed' ORDER BY chapter_index, id LIMIT 3")}
    return rows, upcoming
