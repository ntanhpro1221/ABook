"""Điện thoại gửi phần sửa của một cuốn về máy tính - docs/EDITING.md, P2b.

Cuốn điện thoại tải từ máy tính này (Store.computerBooks) sửa được ngay trên điện thoại (lớp sửa `edits.json`, cùng giao ước với
file `.abook` v4 - book_edits.py). Gói gửi về là một file zip nhỏ: `edits.json`, `edits/cover.jpg` (khi đổi bìa), `music/<sha1>.<đuôi>`
(các bài nhạc người nghe ghim) - đúng tên và đúng kiểm tra của lớp sửa trong file sách (`book_edits.read_layer`). Gói đến từ mạng
nên là dữ liệu của người lạ: từ chối cả gói khi sai, chỉ thiết bị đã ghép mới gửi được (sync.py), chỉ cuốn có trong thư viện.

Hai loại sửa đi hai ngả:
- Sửa "áp ngay" (tên sách, bìa, tên nhân vật, tên chương, nhạc): áp NGAY bằng đúng các hàm Studio dùng (`book_edits.fold_edits`,
  như khi chủ máy đồng ý áp phần sửa trong file sách). Hai nơi cùng sửa một khoá thì bản đến sau thắng; máy nhớ giá trị nó đã áp
  cho từng thiết bị (`edits_synced.json`) nên chỉ báo XUNG ĐỘT khi chủ máy (hay thiết bị khác) đã đổi khoá ấy kể từ lần trước.
- Ý muốn chờ Studio (`wishes`: cách đọc, người nói, giọng, thu lại): thiết bị được điều khiển sản xuất từ xa thì thành YÊU CẦU
  thật (`book_wishes.fold`, vào danh sách "Áp dụng N thay đổi"); thiết bị chỉ nghe thì vào HỘP THƯ (`edits_inbox.json` cạnh dự
  án), chờ chủ máy "Áp dụng" hay "Bỏ qua" từng mục / từng thiết bị. KHÔNG BAO GIỜ tự áp.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import tempfile
import threading
import time
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any

from .. import listener_overrides as overrides
from .. import names as renames
from ..io_utils import atomic_write_bytes
from . import book_edits, book_wishes, covers, music_plan, store

INBOX_FILE = "edits_inbox.json"
SYNCED_FILE = "edits_synced.json"
MAX_PACKAGE_BYTES = 160 * 1024 * 1024  # cả gói (bìa <= 8 MiB, nhạc ghim thường vài MiB mỗi bài)
MAX_TRACK_BYTES = 128 * 1024 * 1024  # một bài nhạc ghim; hơn thế không phải nhạc nền
MAX_RECENT = 10
_MEMBER = re.compile(r"edits\.json|edits/cover\.jpg|music/[0-9a-f]{40}\.(?:mp3|m4a|ogg|opus|flac|wav)")
_LOCK = threading.RLock()
_CHUNK = 256 * 1024


class InboundError(ValueError):
    """Gói điện thoại gửi không dùng được - câu chữ để hiện cho người dùng."""


# ---- gói gửi về -------------------------------------------------------------------------------------------------------


def read_package(path: Path) -> tuple[dict[str, Any], bytes | None, dict[str, str]]:
    """Mở và KIỂM gói zip điện thoại gửi: chỉ nhận đúng các mục của lớp sửa, không mục trùng hay mã hoá, không quá cỡ; phần sửa
    đúng giao ước (`book_edits.read_layer`: cùng cổng với file sách của người lạ) và mọi bài nhạc trong gói đều là bài đã ghim.
    Trả (phần sửa, byte bìa hay None, {tên mục nhạc: sha1}); sai: `InboundError`."""
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise InboundError("Gói thay đổi từ điện thoại bị hỏng.") from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(set(names)) != len(names) or any(not _MEMBER.fullmatch(name) for name in names):
            raise InboundError("Gói thay đổi từ điện thoại có mục lạ.")
        if any(info.flag_bits & 0x1 for info in infos) or sum(info.file_size for info in infos) > MAX_PACKAGE_BYTES:
            raise InboundError("Gói thay đổi từ điện thoại không dùng được hoặc quá lớn.")
        try:
            edits, cover = book_edits.read_layer(archive, set(names))
        except (book_edits.EditsError, KeyError, zipfile.BadZipFile) as exc:
            raise InboundError(str(exc)) from exc
        pinned = set(book_edits.pinned_files(edits))
        tracks = {name: name[len("music/"):].partition(".")[0] for name in names if name.startswith("music/")}
        if set(tracks) != pinned:
            raise InboundError("Gói có bài nhạc không ai ghim.")
        if any(archive.getinfo(name).file_size > MAX_TRACK_BYTES for name in tracks):
            raise InboundError("Một bài nhạc trong gói quá dài.")
    return edits, cover, tracks


def extract(path: Path, tracks: dict[str, str], target: Path) -> None:
    """Chép các bài nhạc ghim ra `target/<sha1>.<đuôi>` (nơi `fold_edits` tìm file)."""
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for name in tracks:
            with archive.open(name) as source, (target / name.rpartition("/")[2]).open("wb") as sink:
                shutil.copyfileobj(source, sink, _CHUNK)


# ---- sổ nhớ giá trị đã áp cho từng thiết bị (để biết khi nào là xung đột) -----------------------------------------------


def _read(project: Path, name: str, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads((Path(project) / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return value if isinstance(value, dict) else default


def _write(project: Path, name: str, data: dict[str, Any]) -> None:
    atomic_write_bytes(Path(project) / name, (json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _current(project: Path, layer: dict[str, Any], local: Any) -> dict[str, Any]:
    """Giá trị chủ máy đang đặt cho các khoá mà `layer` định đổi (chỉ khoá có đặt riêng): cùng dạng với sổ nhớ."""
    out: dict[str, Any] = {}
    title = store.display_title(project, "")
    if "title" in layer and title:
        out["title"] = title
    cover = covers.cover_file(project)
    if "cover" in layer and cover is not None:
        out["cover"] = _sha(cover.read_bytes())
    mine = renames.load(project)
    people = {renames.name_key(name): mine[renames.name_key(name)] for name in layer.get("characters") or {}
              if renames.name_key(name) in mine}
    if people:
        out["characters"] = people
    own = store.chapter_title_overrides(project)
    chapters: dict[str, dict[str, str]] = {}
    for key, theirs in (layer.get("chapters") or {}).items():
        target = local(key)
        if target in own:
            kept = {field: own[target][field] for field in theirs if field in own[target]}
            if kept:
                chapters[key] = kept
    if chapters:
        out["chapters"] = chapters
    music = music_plan.read_overrides(project)
    wanted = layer.get("music") or {}
    changes: dict[str, Any] = {}
    if "enabled" in wanted and music["enabled"] is not True:
        changes["enabled"] = music["enabled"]
    if "levelDb" in wanted and music["levelDb"] != music_plan.DEFAULT_LEVEL_DB:
        changes["levelDb"] = music["levelDb"]
    if changes:
        out["music"] = changes
    return out


def _theirs(layer: dict[str, Any], cover: bytes | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "title" in layer:
        out["title"] = layer["title"]
    if "cover" in layer:
        out["cover"] = _sha(cover) if layer["cover"] is not None and cover is not None else ""
    if layer.get("characters"):
        out["characters"] = {renames.name_key(name): shown for name, shown in layer["characters"].items()}
    if layer.get("chapters"):
        out["chapters"] = layer["chapters"]
    music = {key: layer["music"][key] for key in ("enabled", "levelDb") if key in (layer.get("music") or {})}
    if music:
        out["music"] = music
    return out


_WHAT = {"title": "Tên sách", "cover": "Ảnh bìa", "characters": "Tên nhân vật", "chapters": "Tên chương", "music": "Nhạc nền"}
HOST = "máy kia"  # `sender_label` nói theo góc nhìn NGƯỜI GỬI, nơi lời báo hiện ra: máy giữ sách là "máy kia" (bên gửi thêm tên máy)


def _quoted(value: Any) -> str:
    text = " ".join(str(value).split()) if isinstance(value, str) else ""
    return f"“{text[:40]}{'…' if len(text) > 40 else ''}”" if text else ""


def conflict(kind: str, key: str, what: str, label: str, lost: Any = None, kept: Any = None) -> dict[str, Any]:
    """Một khoá hai bên đặt khác nhau. `label`: câu cho CHỦ MÁY giữ sách (hộp thư, lịch sử nhận); `what`/`lost`/`kept` (thứ gì, giá trị
    ở máy giữ sách, giá trị người gửi vừa gửi) để máy gửi tự viết lại câu cho mình (`sender_label`)."""
    return {"kind": kind, "key": key, "label": label, "what": what, "lost": _quoted(lost), "kept": _quoted(kept)}


def sender_label(item: dict[str, Any], host: str) -> str:
    """Câu báo xung đột cho người GỬI: thứ gì đã đổi ở máy giữ sách `host` sau lần gửi trước, và bản vừa gửi đã thay vào."""
    where = f"{HOST} ({host})" if host else HOST
    if item.get("lost") and item.get("kept"):
        return f"{item['what']}: {where} đã đổi thành {item['lost']} trước đó, bản của bạn {item['kept']} đã thay vào"
    if item.get("what"):
        return f"{item['what']}: {where} đã đổi khác trước đó, bản của bạn đã thay vào"
    return str(item.get("label") or "")  # máy kia cũ không gửi các khoá trên: giữ câu của nó


def _conflicts(project: Path, device: str, name: str, layer: dict[str, Any], cover: bytes | None, local: Any) -> list[dict[str, Any]]:
    """Khoá mà chủ máy (hay thiết bị khác) đã đặt khác, KỂ TỪ lần trước thiết bị này gửi: bản của điện thoại vẫn thắng (đến
    sau thắng) nhưng người dùng được báo. Khoá chưa có giá trị riêng ở máy tính, hay đang đúng giá trị điện thoại gửi lần trước,
    hay đúng giá trị điện thoại gửi lần này: không phải xung đột."""
    mine, theirs = _current(project, layer, local), _theirs(layer, cover)
    last = _read(project, SYNCED_FILE, {}).get(device) or {}
    found: list[dict[str, str]] = []

    def differs(section: str, key: str | None = None) -> bool:
        now = mine.get(section) if key is None else (mine.get(section) or {}).get(key)
        wanted = theirs.get(section) if key is None else (theirs.get(section) or {}).get(key)
        before = last.get(section) if key is None else (last.get(section) or {}).get(key)
        return now is not None and now != wanted and now != before

    for section in ("title", "cover"):
        if section in mine and differs(section):
            found.append(conflict(section, "", _WHAT[section], f"{_WHAT[section]}: máy tính đã có bản riêng, đã thay bằng bản từ {name}",
                                  mine.get(section) if section == "title" else None, theirs.get(section) if section == "title" else None))
    for key in (mine.get("characters") or {}):
        if differs("characters", key):
            found.append(conflict("character", key, _WHAT["characters"],
                                  f"{_WHAT['characters']}: máy tính đã đặt “{mine['characters'][key]}”, đã thay bằng bản từ {name}",
                                  mine["characters"][key], (theirs.get("characters") or {}).get(key)))
    for key in (mine.get("chapters") or {}):
        if differs("chapters", key):
            found.append(conflict("chapter", key, f"{_WHAT['chapters']} (mã {key})",
                                  f"{_WHAT['chapters']} (mã {key}): máy tính đã đặt lại, đã thay bằng bản từ {name}"))
    for key in (mine.get("music") or {}):
        if differs("music", key):
            what = f"{_WHAT['music']} ({'bật/tắt' if key == 'enabled' else 'mức to'})"
            found.append(conflict("music", key, what, f"{what}: máy tính đã chọn khác, đã thay bằng bản từ {name}"))
    return found


def _remember(project: Path, device: str, layer: dict[str, Any], cover: bytes | None) -> None:
    memory = _read(project, SYNCED_FILE, {})
    mine = memory.get(device) or {}
    for section, value in _theirs(layer, cover).items():
        if isinstance(value, dict):
            mine[section] = {**(mine.get(section) or {}), **value}
        else:
            mine[section] = value
    memory[device] = mine
    _write(project, SYNCED_FILE, memory)


# ---- hộp thư ý muốn chờ duyệt -----------------------------------------------------------------------------------------


def _load(project: Path) -> dict[str, Any]:
    data = _read(project, INBOX_FILE, {})
    devices = data.get("devices") if isinstance(data.get("devices"), dict) else {}
    recent = data.get("recent") if isinstance(data.get("recent"), list) else []
    return {"devices": devices, "recent": recent}


def _save(project: Path, data: dict[str, Any]) -> None:
    if not data["devices"] and not data["recent"]:
        (Path(project) / INBOX_FILE).unlink(missing_ok=True)
        return
    _write(project, INBOX_FILE, {"version": 1, **data})


def _groups(wishes: dict[str, Any]) -> list[dict[str, Any]]:
    """Các MỤC của ý muốn (một lần bấm = một mục, như `book_wishes.count`): {id, kind, section, keys, requestedAt}."""
    items: list[dict[str, Any]] = []

    def add(kind: str, section: str, keys: list[str], at: float) -> None:
        items.append({"id": f"{section}:{keys[0]}", "kind": kind, "section": section, "keys": keys, "requestedAt": at})

    for key in sorted(wishes.get("pronunciations") or {}):
        add("pronunciation", "pronunciations", [key], float(wishes["pronunciations"][key]["requested_at"]))
    for section, kind in (("speakers", "speaker"), ("lines", "line"), ("voices", "voice"), ("retakes", "retake")):
        entries = wishes.get(section) or {}
        if section in book_wishes.BY_CLICK:
            clicks: dict[float, list[str]] = {}
            for key in sorted(entries):
                clicks.setdefault(float(entries[key]["requested_at"]), []).append(key)
            for at, keys in clicks.items():
                add(kind, section, keys, at)
        else:
            for key in sorted(entries):
                add(kind, section, [key], float(entries[key]["requested_at"]))
    for item in wishes.get(book_wishes.ALIASES) or []:
        add("alias", book_wishes.ALIASES, [item["alias"]], float(item["at"]))
    return items


def _subset(wishes: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        section, keys = item["section"], set(item["keys"])
        if section == book_wishes.ALIASES:
            out.setdefault(section, []).extend(copy.deepcopy(entry) for entry in wishes.get(section) or [] if entry["alias"] in keys)
        else:
            out.setdefault(section, {}).update({key: copy.deepcopy(wishes[section][key]) for key in keys if key in (wishes.get(section) or {})})
    return out


def _without(wishes: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    gone = {(item["section"], key) for item in items for key in item["keys"]}
    out: dict[str, Any] = {}
    for section, entries in wishes.items():
        if section == book_wishes.ALIASES:
            kept = [entry for entry in entries if (section, entry["alias"]) not in gone]
            if kept:
                out[section] = kept
        else:
            kept_entries = {key: value for key, value in entries.items() if (section, key) not in gone}
            if kept_entries:
                out[section] = kept_entries
    return out


def _labelled(project: Path, wishes: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Thêm câu nói bằng lời cho từng mục (nội dung câu, người nói, chương) - đọc sổ dự án chỉ đọc."""
    wanted = {key for item in items if item["section"] in ("speakers", "lines", "retakes") for key in item["keys"]}
    rows: dict[str, Any] = {}
    speakers: dict[str, str] = {}
    titles: dict[int, str] = {}
    try:
        with closing(store.connect(project)) as connection:
            rows = {str(row["stable_id"]): row for row in connection.execute("SELECT stable_id, chapter_id, text FROM segments")
                    if str(row["stable_id"]) in wanted}
            if any(item["section"] == "voices" for item in items):
                speakers = {overrides.character_key(str(row[0] or "")): str(row[0]) for row in connection.execute("SELECT DISTINCT speaker FROM segments")}
        titles = {chapter["id"]: chapter["displayTitle"] for chapter in store.chapters(project)}
    except Exception:  # noqa: BLE001 - không đọc được sổ thì vẫn liệt kê được (nhãn gọn hơn), không làm hỏng hộp thư
        pass
    out = []
    for item in items:
        section, keys = item["section"], item["keys"]
        first = rows.get(keys[0])
        chapter = titles.get(int(first["chapter_id"]), "") if first is not None else ""
        text = str(first["text"]) if first is not None else ""
        entry = (wishes.get(section) or {}).get(keys[0]) if section != book_wishes.ALIASES else None
        if section == "pronunciations":
            label = store.label_pronunciation(entry["surface"], entry["spoken_form"])
        elif section == "speakers":
            label = store.label_speaker(text if len(keys) == 1 else "", store.person_label(project, entry["speaker"]), len(keys))
        elif section == "lines":
            label = store.label_line(text, entry)
        elif section == "voices":
            label = store.label_voice(store.person_label(project, speakers.get(keys[0], keys[0])), entry)
        elif section == "retakes":
            label = store.label_retake(text if len(keys) == 1 else "", len(keys))
        else:
            person = next((value["person"] for value in wishes.get(section) or [] if value["alias"] == keys[0]), "")
            label = f"“{keys[0]}” là cách gọi khác của {store.person_label(project, person)}"
        out.append({**item, "label": label, **({"chapter": chapter} if chapter else {}), "lines": len(keys)})
    return out


def waiting(project: Path, device: str | None = None) -> int:
    """Số mục đang chờ chủ máy duyệt (của một thiết bị, hay của mọi thiết bị)."""
    with _LOCK:
        devices = _load(project)["devices"]
    return sum(len(_groups(entry.get("wishes") or {})) for key, entry in devices.items() if device in (None, key))


def view(project: Path) -> dict[str, Any]:
    """Hộp thư của một dự án cho giao diện: từng thiết bị với các mục chờ (nói bằng lời), cộng vài lần nhận gần đây."""
    with _LOCK:
        data = _load(project)
        devices = []
        for key, entry in sorted(data["devices"].items(), key=lambda pair: -float(pair[1].get("at") or 0)):
            wishes = entry.get("wishes") or {}
            items = _labelled(project, wishes, _groups(wishes))
            if items:
                devices.append({"id": key, "name": str(entry.get("name") or "Điện thoại"), "at": float(entry.get("at") or 0), "items": items})
        return {"devices": devices, "waiting": sum(len(device["items"]) for device in devices), "recent": data["recent"]}


def apply(project: Path, device: str, item_ids: list[str] | None, *, now: float | None = None) -> dict[str, int]:
    """Chủ máy bấm "Áp dụng": các mục (hay mọi mục của thiết bị) thành YÊU CẦU của dự án bằng `book_wishes.fold` - như người dùng
    vừa bấm trong Studio, vào danh sách "Áp dụng N thay đổi", chưa chạy gì. Mục Studio sẽ từ chối ngay (câu đã đổi chữ...) bị bỏ
    qua và đếm. Xong thì rút khỏi hộp thư. Trả {"requests", "skipped", "left"}."""
    with _LOCK:
        data = _load(project)
        entry = data["devices"].get(device)
        if entry is None:
            return {"requests": 0, "skipped": 0, "left": 0}
        wishes = entry.get("wishes") or {}
        chosen = [item for item in _groups(wishes) if item_ids is None or item["id"] in item_ids]
        folded = book_wishes.fold(project, _subset(wishes, chosen), now=time.time() if now is None else now) if chosen else {"requests": 0, "skipped": 0}
        left = _without(wishes, chosen)
        _store(data, device, entry, left)
        _save(project, data)
        return {**folded, "left": len(_groups(left))}


def skip(project: Path, device: str, item_ids: list[str] | None) -> dict[str, int]:
    """Chủ máy bấm "Bỏ qua": các mục (hay mọi mục của thiết bị) bị bỏ khỏi hộp thư, không làm gì cả. Trả {"removed", "left"}."""
    with _LOCK:
        data = _load(project)
        entry = data["devices"].get(device)
        if entry is None:
            return {"removed": 0, "left": 0}
        wishes = entry.get("wishes") or {}
        chosen = [item for item in _groups(wishes) if item_ids is None or item["id"] in item_ids]
        left = _without(wishes, chosen)
        _store(data, device, entry, left)
        _save(project, data)
        return {"removed": len(chosen), "left": len(_groups(left))}


def _store(data: dict[str, Any], device: str, entry: dict[str, Any], wishes: dict[str, Any]) -> None:
    if wishes:
        data["devices"][device] = {**entry, "wishes": wishes}
    else:
        data["devices"].pop(device, None)


# ---- nhận một gói ------------------------------------------------------------------------------------------------------


def receive(project: Path, device: str, name: str, package: Path, *, my_music: Any = None, may_produce: bool = False,
            now: float | None = None) -> dict[str, Any]:
    """Nhận gói phần sửa điện thoại `device` (mã thiết bị đã ghép, `name`: tên nó) gửi về dự án `project`. `may_produce`: thiết bị
    được điều khiển sản xuất từ xa (công tắc chung VÀ quyền của thiết bị) - ý muốn của nó thành yêu cầu thật; không thì vào hộp
    thư chờ duyệt. Trả {"applied", "skipped", "music": có đổi lựa chọn nhạc không, "requests", "waiting": số mục của thiết bị này
    đang chờ duyệt, "skippedWishes", "conflicts": [{kind, key, label}], "reasons"?}. Gói sai: `InboundError` (không áp gì)."""
    project = Path(project)
    now = time.time() if now is None else now
    edits, cover, tracks = read_package(package)
    layer = {key: value for key, value in edits.items() if key != "wishes"}
    wishes = edits.get("wishes") or {}
    with _LOCK:
        local = book_edits.chapter_resolver(project)
        conflicts = _conflicts(project, device, name, layer, cover, local)
        scratch = Path(tempfile.mkdtemp(prefix=".edits_in_", dir=project))
        try:
            if tracks:
                extract(package, tracks, scratch)
            report = book_edits.fold_edits(project, layer, cover=cover, music_dir=scratch, my_music=my_music)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        _remember(project, device, layer, cover)
        requests = skipped_wishes = 0
        held = 0
        if wishes and may_produce:
            folded = book_wishes.fold(project, wishes, now=now)
            requests, skipped_wishes = folded["requests"], folded["skipped"]
        data = _load(project)
        if wishes and not may_produce:
            previous = (data["devices"].get(device) or {}).get("wishes") or {}
            merged, _ = book_wishes.merge(wishes, previous)  # bản đến sau thắng từng khoá
            data["devices"][device] = {"name": name, "at": now, "wishes": merged}
        held = len(_groups((data["devices"].get(device) or {}).get("wishes") or {}))
        entry = {"at": now, "device": device, "name": name, "applied": report["applied"], "skipped": report["skipped"] + skipped_wishes,
                 "requests": requests, "waiting": held, "conflicts": [item["label"] for item in conflicts]}
        if report["applied"] or report["skipped"] or requests or skipped_wishes or wishes or conflicts:
            data["recent"] = ([entry] + data["recent"])[:MAX_RECENT]
        _save(project, data)
    return {"applied": report["applied"], "skipped": report["skipped"], "music": report["music"], "requests": requests,
            "waiting": held, "skippedWishes": skipped_wishes, "conflicts": conflicts,
            **({"reasons": report["reasons"]} if report.get("reasons") else {})}
