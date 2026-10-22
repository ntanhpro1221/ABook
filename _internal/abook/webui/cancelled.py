"""Bia mộ của yêu cầu đã rút (soát a89 V6): `cancelled.json` cạnh `overrides.json` nhớ "yêu cầu này đã bị bỏ", để mở file `.abookproj`
của máy khác (workshop_merge) không làm yêu cầu ấy sống lại.

Chuyện xảy ra nếu không có: máy A bấm "Thu lại" rồi đổi ý (`cancel_retake`) hay hoàn tác một sửa (`withdraw_requests`) - mục biến khỏi
overrides.json. Máy B vẫn giữ file cũ còn mục ấy; trộn hai bên thì mục "chỉ có ở một bên" được lấy về, người dùng thấy lại việc mình đã bỏ.

Mỗi bia = `{"requested_at": mốc của CHÍNH yêu cầu bị rút, "cancelled_at": lúc rút}` (thêm `"exact": true` khi rút một yêu cầu đã thay
yêu cầu cũ - cũ ấy trở lại, nên chỉ luật 1 áp), khoá `"<phần>:<khoá>"` (`retakes:c1s1`).
Luật so (cùng ở WorkshopMerge.kt; ca chung tests/fixtures/book_edits/workshop_merge/cancelled_requests.json), KHÔNG tin đồng hồ máy kia mù quáng:
  1. Cùng một yêu cầu (`requested_at` bằng đúng mốc trong bia) thì luôn chết - so bằng nhau chứ không so hơn kém, nên đồng hồ lệch bao nhiêu
     cũng không sai.
  2. Mục CŨ HƠN yêu cầu đã rút (`requested_at` nhỏ hơn) cũng chết, NHƯNG chỉ khi bia không `exact` và hợp lý: `requested_at <= cancelled_at` (rút sau khi
     tạo, theo cùng đồng hồ) và `cancelled_at` không vượt giờ máy này quá SKEW_SECONDS (máy kia đặt đồng hồ tương lai không chôn được việc
     của máy này). Bia không hợp lý thì chỉ còn luật 1.
  3. Mục MỚI HƠN (đặt lại sau khi rút) luôn sống: bia chỉ nói về yêu cầu nó nêu và các yêu cầu cũ hơn.
Bia của hai máy hợp lại, mỗi khoá giữ bia của yêu cầu mới hơn (rồi lần rút muộn hơn). Quá MAX_ENTRIES thì bỏ bia rút lâu nhất."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import listener_overrides
from ..io_utils import atomic_write_json

FILE_NAME = "cancelled.json"
SKEW_SECONDS = 86400.0
MAX_ENTRIES = 5000
SECTIONS = ("pronunciations", "speakers", "lines", "voices", "retakes")


def key(section: str, entry_key: str) -> str:
    return f"{section}:{entry_key}"


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def entries_of(content: Any) -> dict[str, dict[str, Any]]:
    """Nội dung file -> {khoá bia: {requested_at, cancelled_at}}; mục sai hình bị bỏ."""
    rows = content.get("cancelled") if isinstance(content, dict) else None
    out: dict[str, dict[str, Any]] = {}
    for name, row in (rows.items() if isinstance(rows, dict) else ()):
        requested, cancelled = (_number(row.get("requested_at")), _number(row.get("cancelled_at"))) if isinstance(row, dict) else (None, None)
        if requested is not None and cancelled is not None and ":" in str(name):
            out[str(name)] = {"requested_at": requested, "cancelled_at": cancelled, **({"exact": True} if row.get("exact") is True else {})}
    return out


def content_of(entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"version": 1, "cancelled": {name: entries[name] for name in sorted(entries)}}


def union(mine: dict[str, dict[str, Any]], theirs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Hợp bia của hai máy: mỗi khoá giữ bia của yêu cầu mới hơn, bằng nhau thì lần rút muộn hơn."""
    merged = dict(mine)
    for name, row in theirs.items():
        local = merged.get(name)
        if local is None or (row["requested_at"], row["cancelled_at"]) > (local["requested_at"], local["cancelled_at"]):
            merged[name] = dict(row)
    return merged


def is_dead(section: str, entry_key: str, entry: Any, tombstones: dict[str, dict[str, Any]], now: float) -> bool:
    """Mục `entry` của overrides.json có bị bia nào chôn không (luật ở đầu file)."""
    tomb = tombstones.get(key(section, entry_key))
    stamp = _number(entry.get("requested_at")) if isinstance(entry, dict) else None
    if tomb is None or stamp is None:
        return False
    if stamp == tomb["requested_at"]:
        return True
    return (not tomb.get("exact") and stamp < tomb["requested_at"] and tomb["requested_at"] <= tomb["cancelled_at"]
            and tomb["cancelled_at"] <= now + SKEW_SECONDS)


def bury(overrides: dict[str, Any], tombstones: dict[str, dict[str, Any]], now: float) -> tuple[dict[str, Any], int]:
    """`overrides` bỏ những mục đã bị bia chôn -> (bản mới, số mục bỏ). Không sửa đầu vào."""
    out = dict(overrides)
    removed = 0
    for section in SECTIONS:
        entries = out.get(section)
        if not isinstance(entries, dict):
            continue
        keep = {name: entry for name, entry in entries.items() if not is_dead(section, name, entry, tombstones, now)}
        if len(keep) != len(entries):
            removed += len(entries) - len(keep)
            out[section] = keep
    return out, removed


def read(project_root: Path) -> dict[str, dict[str, Any]]:
    try:
        return entries_of(json.loads((Path(project_root) / FILE_NAME).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def write(project_root: Path, entries: dict[str, dict[str, Any]]) -> None:
    if len(entries) > MAX_ENTRIES:
        newest = sorted(entries, key=lambda name: entries[name]["cancelled_at"], reverse=True)[:MAX_ENTRIES]
        entries = {name: entries[name] for name in newest}
    atomic_write_json(Path(project_root) / FILE_NAME, content_of(entries))


def record(project_root: Path, section: str, requested: dict[str, tuple[float, bool]], *, now: float) -> None:
    """Ghi bia cho các yêu cầu sắp bị rút: {khoá: (`requested_at` của yêu cầu, có yêu cầu cũ trở lại không)}. Gọi TRƯỚC khi gỡ khỏi overrides.json, dưới khoá ghi của
    dự án (nút Studio đã giữ): chết giữa chừng thì còn bia mà yêu cầu chưa gỡ - đúng ý người dùng (đã bấm bỏ), lần trộn sau chôn nốt."""
    if not requested:
        return
    entries = read(project_root)
    entries = union(entries, {key(section, name): {"requested_at": float(at), "cancelled_at": float(now), **({"exact": True} if restored else {})}
                              for name, (at, restored) in requested.items()})
    write(project_root, entries)


def cancel_retake(project_root: Path, stable_id: str, *, now: float) -> None:
    """`listener_overrides.cancel_retake` kèm bia (nếu yêu cầu còn đó)."""
    here = (listener_overrides.read_overrides(project_root).get("retakes") or {}).get(str(stable_id))
    stamp = _number(here.get("requested_at")) if isinstance(here, dict) else None
    if stamp is not None:
        record(project_root, "retakes", {str(stable_id): (stamp, False)}, now=now)
    listener_overrides.cancel_retake(project_root, stable_id)


def withdraw_requests(project_root: Path, section: str, keys: list[str], requested_at: float, *, now: float) -> list[str]:
    """`listener_overrides.withdraw_requests` kèm bia cho từng yêu cầu của đúng lần bấm ấy."""
    mine = listener_overrides.requests_made_at(listener_overrides.read_overrides(project_root), section, keys, requested_at)
    record(project_root, section, {name: (float(entry["requested_at"]), isinstance(entry.get("replaced"), dict))
                                   for name, entry in mine.items()}, now=now)
    return listener_overrides.withdraw_requests(project_root, section, keys, requested_at)


def withdraw_folded(project_root: Path, section: str, keys: list[str], requested_at: float, *, now: float) -> list[str]:
    """Rút yêu cầu của đúng lần bấm `requested_at` (hộp "Áp dụng", thông báo "Hoàn tác" và gói điện thoại nhờ rút - edits_inbox.receive) ra khỏi
    overrides.json kèm bia, và mọi thứ cùng mốc ấy ghi theo: yêu cầu "người nói" đi kèm cách đọc câu (lời kể -> lời thoại), bí danh của lần
    "Gộp vào…" (chỉ khi không còn câu nào của lần bấm ấy). "Thu lại" rút từng câu. Chưa kiểm yêu cầu đã vào sách chưa - người gọi hỏi
    `store.already_applied` trước. Trả các khoá đã rút."""
    from .. import aliases

    mine = listener_overrides.requests_made_at(listener_overrides.read_overrides(project_root), section, keys, requested_at)
    if section == "retakes":
        for stable_id in mine:
            cancel_retake(project_root, stable_id, now=now)
        return list(mine)
    removed = withdraw_requests(project_root, section, list(mine), requested_at, now=now)
    if section == "lines" and removed:
        withdraw_requests(project_root, "speakers", removed, requested_at, now=now)
    if section == "speakers" and removed:
        left = listener_overrides.requests_made_at(listener_overrides.read_overrides(project_root), "speakers",
                                                   list(listener_overrides.read_overrides(project_root).get("speakers") or {}), requested_at)
        if not left:
            aliases.remove_added_at(project_root, requested_at)
    return removed
