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


def revisions(item: dict) -> dict | None:
    """Phiên bản hỏng thì bỏ cả hàng: hàng còn lại mà thiếu phiên bản thì máy kia từ chối mãi (thiếu phiên bản), bỏ đi thì máy kia gửi lại bản đủ."""
    return None if "rev" in item and revision(item)[0] == 0 else item


def meta_revisions(row: dict, *keys: str) -> dict:
    """Phiên bản tên / lần chuyển / hồ sơ đang chọn hỏng thì bỏ: còn mốc giờ để gộp như máy chưa có phiên bản."""
    for key in keys:
        if key in row and revision({"rev": row[key]})[0] == 0:
            row.pop(key)
    return row


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
    for field, stamp in (("rate", "rateAt"), ("finished", "finishedAt"), ("voice", "voiceAt")):
        # Giá trị + mốc giờ + phiên bản là một bộ: một phần hỏng thì bỏ cả bộ (máy kia gửi lại bản đủ) - trước đây giữ giá trị và phiên
        # bản mà mất mốc, máy kia gộp văng lỗi ở mọi lần đồng bộ (soát a118 lỗi 3).
        # Một luật: trường còn giá trị mà bảng phiên bản đã lọc không có phiên bản cho nó là hỏng - gồm cả khi chính `_fieldRevs` sai kiểu (bị thay bằng {}).
        revs = state.get("_fieldRevs", {})
        broken_rev = (isinstance(raw.get("_fieldRevs"), dict) and field in raw["_fieldRevs"] and field not in revs) or (field in state and field not in revs)
        if (field in raw and field not in state) or (stamp in raw and stamp not in state) or broken_rev:
            state.pop(field, None)
            state.pop(stamp, None)
            if isinstance(state.get("_fieldRevs"), dict):
                state["_fieldRevs"].pop(field, None)
    for key, required in (("last", ("chapterId", "seconds")), ("reading", ("chapterId", "index"))):
        if key in state:
            item = state[key]
            if not isinstance(item, dict) or not all(number(item.get(k)) for k in required):
                del state[key]
            elif (kept := revisions(fields(item, (*required, "at")))) is None:
                del state[key]
            else:
                state[key] = kept
    chapters = state.get("chapters", {})
    state["chapters"] = {key: kept for key, item in (chapters.items() if isinstance(chapters, dict) else [])
                         if isinstance(item, dict)
                         and (kept := revisions(fields(item, ("heard", "duration", "at"), booleans=("done",)))) is not None}
    marks = state.get("bookmarks", [])
    state["bookmarks"] = [kept for item in (marks if isinstance(marks, list) else [])
                          if isinstance(item, dict) and isinstance(item.get("id"), str)
                          and number(item.get("chapterId")) and number(item.get("seconds"))
                          and (kept := revisions(fields(item, ("seconds", "at", "createdAt", "index"), ("note", "quote")))) is not None]
    for key in ("chapters", "bookmarks"):
        if key not in raw:
            state.pop(key, None)
    for key in ("deleted",):
        if key in state:
            state[key] = {k: v for k, v in state[key].items() if number(v)} if isinstance(state[key], dict) else {}
            # Dấu xoá không còn phiên bản trong bảng đã lọc (phiên bản hỏng, hay chính `_deletedRevs` sai kiểu) cũng bỏ, cùng lý do như hàng.
            state[key] = {k: v for k, v in state[key].items() if k in state.get("_deletedRevs", {})}
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
    if "_clock" in data and (type(data["_clock"]) is not int or not 0 <= data["_clock"] <= MAX_COUNTER):
        data.pop("_clock")
    if "_epoch" in data and not valid_epoch(data["_epoch"]):
        data.pop("_epoch")
    records = data.get("records", {})
    data["records"] = {}
    for key, row in (records.items() if isinstance(records, dict) else []):
        if isinstance(row, dict):
            row = meta_revisions(fields(row, ("createdAt", "nameAt", "movedAt"), ("name",)), "nameRev", "movedRev")
            if "state" in row:
                row["state"] = clean_state(row["state"])
            data["records"][key] = row
    links = data.get("links", {})
    data["links"] = {}
    for key, link in (links.items() if isinstance(links, dict) else []):
        if not isinstance(link, dict):
            continue
        link = meta_revisions(fields(link, ("activeAt",)), "activeRev")
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
