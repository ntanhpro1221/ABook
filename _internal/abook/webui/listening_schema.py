"""Repair known profile fields only; the caller must preserve original bytes before writing."""
from __future__ import annotations

import copy
import math
from .listening_revision import revision, MAX_COUNTER, valid_epoch
from typing import Any


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def fields(value: dict, numbers=(), strings=(), booleans=()) -> dict:
    result = dict(value)
    for keys, valid in ((numbers, number), (strings, lambda v: isinstance(v, str)),
                        (booleans, lambda v: isinstance(v, bool))):
        for key in keys:
            if key in result and not valid(result[key]):
                del result[key]
    return result


def revisions(item: dict) -> dict:
    if "rev" in item and revision(item)[0] == 0:
        item.pop("rev")
    return item


def clean_state(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {"chapters": {}, "bookmarks": []}
    state = fields(raw, ("updatedAt", "rate", "rateAt", "finishedAt", "voiceAt", "_clock"), ("voice",), ("finished",))
    if "_clock" in state and (type(state["_clock"]) is not int or not 0 <= state["_clock"] <= MAX_COUNTER):
        state.pop("_clock")
    if "_epoch" in state and not valid_epoch(state["_epoch"]):
        state.pop("_epoch")
    for key in ("_fieldRevs", "_deletedRevs"):
        if key in state:
            rows = state[key]
            state[key] = {k: v for k, v in rows.items() if revision({"rev": v})[0]} if isinstance(rows, dict) else {}
    for key, required in (("last", ("chapterId", "seconds")), ("reading", ("chapterId", "index"))):
        if key in state:
            item = state[key]
            if not isinstance(item, dict) or not all(number(item.get(k)) for k in required):
                del state[key]
            else:
                state[key] = revisions(fields(item, (*required, "at")))
    chapters = state.get("chapters", {})
    state["chapters"] = {key: revisions(fields(item, ("heard", "duration", "at"), booleans=("done",)))
                         for key, item in (chapters.items() if isinstance(chapters, dict) else [])
                         if isinstance(item, dict)}
    marks = state.get("bookmarks", [])
    state["bookmarks"] = [revisions(fields(item, ("seconds", "at", "createdAt", "index"), ("note", "quote")))
                          for item in (marks if isinstance(marks, list) else [])
                          if isinstance(item, dict) and isinstance(item.get("id"), str)
                          and number(item.get("chapterId")) and number(item.get("seconds"))]
    for key in ("chapters", "bookmarks"):
        if key not in raw:
            state.pop(key, None)
    for key in ("deleted",):
        if key in state:
            state[key] = {k: v for k, v in state[key].items() if number(v)} if isinstance(state[key], dict) else {}
    if "sessions" in state:
        state["sessions"] = [fields(v, ("startedAt", "endedAt", "listened"))
                             for v in (state["sessions"] if isinstance(state["sessions"], list) else [])
                             if isinstance(v, dict) and isinstance(v.get("id"), str)]
    if "night" in state:
        night = state["night"]
        if not isinstance(night, dict):
            del state["night"]
        else:
            night = fields(night, ("startedAt",), ("id", "device", "bookTitle"), ("dismissed",))
            if night.get("endedAt") is not None and not number(night["endedAt"]):
                night.pop("endedAt")
            for key in ("events", "timeline"):
                if key in night:
                    night[key] = [v for v in night[key] if isinstance(v, dict)] if isinstance(night[key], list) else []
            state["night"] = night
    return state


def clean_profiles(raw: dict) -> dict:
    data = copy.deepcopy(raw)
    if data.get("version") != 2:
        return {key: clean_state(value) for key, value in data.items() if isinstance(value, dict)}
    records = data.get("records", {})
    data["records"] = {}
    for key, row in (records.items() if isinstance(records, dict) else []):
        if isinstance(row, dict):
            row = fields(row, ("createdAt", "nameAt", "movedAt"), ("name",))
            if "state" in row:
                row["state"] = clean_state(row["state"])
            data["records"][key] = row
    links = data.get("links", {})
    data["links"] = {}
    for key, link in (links.items() if isinstance(links, dict) else []):
        if not isinstance(link, dict):
            continue
        link = fields(link, ("activeAt",))
        ids = link.get("records", [])
        link["records"] = list(dict.fromkeys(v for v in (ids if isinstance(ids, list) else [])
                                             if isinstance(v, str) and v in data["records"]))
        if not isinstance(link.get("active"), str) or link["active"] not in link["records"]:
            link["active"] = next(iter(link["records"]), "")
        data["links"][key] = link
    if "deleted" in data:
        gone = data["deleted"]
        data["deleted"] = {k: v for k, v in gone.items() if number(v)} if isinstance(gone, dict) else {}
    return data
