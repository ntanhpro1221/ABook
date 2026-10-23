"""Soát a118: sáu lỗi đồng bộ dữ liệu nghe có phiên bản, mỗi test dựng lại đúng script tái hiện (a118/repro/rXX_*.py).

Mỗi máy một thư mục (listening.json + listening-node.json qua ABOOK_PREFERENCES) và một đồng hồ tường riêng. Đồng bộ đi đúng đường
sync.py POST .../state: khách `sync_request` -> JSON -> máy giữ sách `merge_record` -> JSON -> khách `merge_reply`.
Bản Kotlin: A118SyncRulesTest.kt (cùng fixture boundary.json / a118_meta.json).
"""
import json
import time as real_time
from pathlib import Path

import pytest

from abook.webui import listening, notices
from abook.webui.listening import SYNC_KEYS, Listening, default_record_id, merge_states
from abook.webui.listening_revision import JUMP_NOTICE, MAX_JUMP, SAFE_COUNTER, checked_peer, meta_newer
from abook.webui.listening_schema import clean_state

HOLDER = "B"
META = Path(__file__).parent / "fixtures/listening_revision/a118_meta.json"


class Clock:
    def __init__(self) -> None:
        self.now = 1_800_000_000.0
        self.offset = 0.0

    def time(self) -> float:
        return self.now + self.offset

    def __getattr__(self, name):
        return getattr(real_time, name)


class Machine:
    def __init__(self, root: Path, name: str, book: str, clock: Clock, monkeypatch) -> None:
        self.dir = root / name
        self.dir.mkdir(parents=True)
        self.book, self.clock, self.monkeypatch = book, clock, monkeypatch
        self.offset = 0.0
        self.restart()

    def enter(self) -> "Machine":
        self.monkeypatch.setenv("ABOOK_PREFERENCES", str(self.dir / "preferences.json"))
        self.clock.offset = self.offset
        return self

    def restart(self) -> None:
        self.enter()
        self.L = Listening(self.dir / "listening.json")
        self.L.sync_request(self.book, "" if self.book == HOLDER else HOLDER, None)

    @property
    def path(self) -> Path:
        return self.dir / "listening.json"

    def state(self) -> dict:
        return self.L._data["records"][default_record_id(HOLDER)]["state"]

    def node(self) -> str:
        return json.loads((self.dir / "listening-node.json").read_text("utf-8"))["node"]


def roundtrip(value):
    return json.loads(json.dumps(value, ensure_ascii=False))


def sync(client: Machine, holder: Machine) -> bool:
    body = roundtrip(client.enter().L.sync_request(client.book, HOLDER, None))
    holder.enter()
    state = {k: v for k, v in body.items() if k not in SYNC_KEYS or (k == "deleted" and isinstance(v, dict))}
    deleted = body.get("deletedRecords")
    reply = roundtrip(holder.L.merge_record(  # tham số như sync.py
        holder.book, body["record"], state, name=str(body.get("recordName") or ""),
        name_at=float(body.get("nameAt") or 0), active_at=float(body.get("activeAt") or 0),
        moved_at=float(body.get("movedAt") or 0), deleted=deleted if isinstance(deleted, dict) else None,
        name_rev=body.get("nameRev"), active_rev=body.get("activeRev"), moved_rev=body.get("movedRev")))
    return client.enter().L.merge_reply(client.book, body["record"], reply, remote_book=HOLDER, resolve=lambda _book: None)


@pytest.fixture
def world(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(listening, "time", clock)
    notes: list[str] = []
    monkeypatch.setattr(notices.NOTICES, "add", lambda text, **_kw: notes.append(text))

    def make():
        holder = Machine(tmp_path, "H", HOLDER, clock, monkeypatch)
        client = Machine(tmp_path, "C", "V1", clock, monkeypatch)
        return holder, client, clock, notes
    return make


def test_1_new_device_takes_a_profile_with_more_than_a_million_saves(world):
    holder, client, clock, notes = world()
    with holder.enter().L._changing():  # ~1,2 triệu lần lưu chỗ nghe (đúng dạng _clock app tự ghi)
        holder.state()["_clock"] = 1_200_000
        holder.L._save()
    holder.L.progress(HOLDER, 3, 300.0, 600.0)
    holder.L.set_rate(HOLDER, 1.25)
    mark = holder.L.add_bookmark(HOLDER, 3, 120.0, note="quan trọng")
    assert sync(client, holder)
    mine = client.state()
    assert mine["rate"] == 1.25 and mine["last"]["chapterId"] == 3 and [m["id"] for m in mine["bookmarks"]] == [mark["id"]]
    assert JUMP_NOTICE not in notes
    client.enter().L.progress(client.book, 4, 50.0, 600.0)
    sync(client, holder)
    assert holder.state()["last"]["chapterId"] == 4, "chỗ nghe của máy mới tới được máy kia"


def test_1_a_leap_in_the_upper_half_is_still_ignored():
    ours = {"reading": {"chapterId": 1, "index": 1, "at": 1, "rev": {"counter": SAFE_COUNTER + 5, "node": "a"}}, "chapters": {}, "bookmarks": []}
    forged = {"listeningRevision": 1, "reading": {"chapterId": 9, "index": 9, "at": 9,
                                                  "rev": {"counter": SAFE_COUNTER + 5 + MAX_JUMP + 1, "node": "z"}}}
    seen = []
    assert "reading" not in checked_peer(ours, forged, seen.append) and seen == [JUMP_NOTICE]
    seen.clear()
    assert "reading" not in checked_peer({}, {**forged, "reading": {**forged["reading"], "rev": {"counter": SAFE_COUNTER + 1, "node": "z"}}},
                                         seen.append), "hồ sơ trống cũng không bị đẩy vào nửa trên"
    assert checked_peer({}, {**forged, "reading": {**forged["reading"], "rev": {"counter": SAFE_COUNTER, "node": "z"}}}, seen.append)["reading"]


def test_2_a_recovered_profile_never_reuses_a_revision(world):
    holder, client, clock, _ = world()
    holder.enter().L.set_rate(HOLDER, 1.5)
    first = dict(holder.state()["_fieldRevs"]["rate"])
    node = holder.node()
    sync(client, holder)
    holder.path.write_bytes(holder.path.read_bytes()[:20])  # mất điện / ổ lỗi: app giữ bản hỏng, bắt đầu hồ sơ trống
    holder.restart()
    assert holder.node() != node, "hồ sơ dựng lại từ bản hỏng thì máy lấy mã mới"
    holder.enter().L.set_rate(HOLDER, 2.0)
    assert holder.state()["_fieldRevs"]["rate"] != first
    for _ in range(3):
        sync(client, holder)
    assert holder.state()["rate"] == client.state()["rate"]
    assert holder.state()["_fieldRevs"]["rate"] == client.state()["_fieldRevs"]["rate"]


def test_2_a_partially_read_profile_also_takes_a_new_node(world):
    holder, _, _, _ = world()
    holder.enter().L.set_chapter_done(HOLDER, 3, True)
    node = holder.node()
    raw = json.loads(holder.path.read_text("utf-8"))
    raw["records"][default_record_id(HOLDER)]["state"]["_clock"] = "hỏng"
    holder.path.write_text(json.dumps(raw), encoding="utf-8")
    holder.restart()
    assert holder.node() != node
    assert holder.enter().L.set_chapter_done(HOLDER, 4, True)["chapters"]["4"]["rev"]["node"] == holder.node()


def test_3_a_missing_field_stamp_never_breaks_a_merge(world):
    theirs = {"listeningRevision": 1, "rate": 1.5, "_fieldRevs": {"rate": {"counter": 3, "node": "peer"}}}
    merged = merge_states({"chapters": {}, "bookmarks": []}, theirs)
    assert merged["rate"] == 1.5 and "rateAt" not in merged
    merged = merge_states({"chapters": {}, "bookmarks": [], "rateAt": 5}, {**theirs, "rateAt": None})
    assert merged["rate"] == 1.5 and "rateAt" not in merged
    for field, stamp in (("rate", "rateAt"), ("voice", "voiceAt"), ("finished", "finishedAt")):
        broken = {"chapters": {}, "bookmarks": [], field: {"rate": 1.5, "voice": "edge:x", "finished": True}[field], stamp: None,
                  "_fieldRevs": {field: {"counter": 1, "node": "n"}}}
        clean = clean_state(broken)
        assert field not in clean and stamp not in clean and field not in clean["_fieldRevs"], "bỏ cả bộ ba"
    holder, client, _, _ = world()
    holder.enter().L.set_rate(HOLDER, 1.5)
    raw = json.loads(holder.path.read_text("utf-8"))
    raw["records"][default_record_id(HOLDER)]["state"]["rateAt"] = None
    holder.path.write_text(json.dumps(raw), encoding="utf-8")
    holder.restart()
    for _ in range(3):
        assert sync(client, holder)


def test_4_self_repaired_entries_get_new_revisions_and_still_sync(world):
    holder, client, clock, _ = world()
    holder.enter().L.progress(HOLDER, 1, 100.0, 600.0)
    assert sync(client, holder)
    holder.enter().L.set_chapter_done(HOLDER, 3, True)  # chỉ có ở máy giữ sách
    mark = holder.L.add_bookmark(HOLDER, 2, 30.0)
    holder.L.delete_bookmark(HOLDER, mark["id"])
    raw = json.loads(holder.path.read_text("utf-8"))
    state = raw["records"][default_record_id(HOLDER)]["state"]
    state["chapters"]["3"]["rev"]["counter"] = "1"
    state["_deletedRevs"][mark["id"]] = {"counter": -4, "node": "x"}
    holder.path.write_text(json.dumps(raw), encoding="utf-8")
    holder.restart()
    repaired = holder.state()
    assert repaired["chapters"]["3"]["rev"]["counter"] > 0 and repaired["_deletedRevs"][mark["id"]]["counter"] > 0
    holder.enter().L.set_rate(HOLDER, 1.75)
    for _ in range(2):
        assert sync(client, holder)
    mine = client.state()
    assert mine["rate"] == 1.75 and mine["chapters"]["3"]["done"] and mark["id"] in mine["deleted"]


def test_5_record_metadata_follows_causality_not_the_wall_clock(world):
    holder, client, clock, _ = world()
    record = default_record_id(HOLDER)
    holder.enter().L.rename_record(record, "Lần nghe đầu")
    clock.now += 10
    sync(client, holder)
    assert client.L._data["records"][record]["name"] == "Lần nghe đầu"
    client.offset = -3600  # đồng hồ máy khách chậm 1 giờ
    client.enter().L.rename_record(record, "Nghe lại cùng con")
    clock.now += 10
    holder.enter().L.create_record(HOLDER, "Hồ sơ phụ")
    clock.now += 10
    sync(client, holder)
    clock.now += 10
    client.enter().L.activate(client.book, record)  # chọn lại hồ sơ chính SAU khi đã thấy lựa chọn của máy kia
    for _ in range(2):
        clock.now += 10
        sync(client, holder)
    assert (holder.L._data["records"][record]["name"], client.L._data["records"][record]["name"]) == ("Nghe lại cùng con",) * 2
    assert (holder.L._data["links"][HOLDER]["active"], client.L._data["links"][client.book]["active"]) == (record, record)


@pytest.mark.parametrize("case", json.loads(META.read_text("utf-8")), ids=lambda c: c["name"])
def test_5_shared_metadata_order_fixture(case):
    seen = []
    assert meta_newer(case["data"], case["theirs"].get("rev"), case["theirs"]["at"], case["ours"].get("rev"), case["ours"]["at"],
                      seen.append) is case["newer"]
    assert bool(seen) is case.get("notice", False)


def test_6_undoing_a_bookmark_delete_keeps_the_tombstone_and_converges(world):
    holder, client, _, _ = world()
    mark = holder.enter().L.add_bookmark(HOLDER, 1, 30.0)
    holder.L.delete_bookmark(HOLDER, mark["id"])
    sync(client, holder)
    holder.enter().L.restore_bookmark(HOLDER, mark)
    for _ in range(3):
        sync(client, holder)
    for machine in (holder, client):
        state = machine.state()
        assert [m["id"] for m in state["bookmarks"]] == [mark["id"]]
        assert set(state["deleted"]) == {mark["id"]} and set(state["_deletedRevs"]) == {mark["id"]}
    assert holder.state()["_deletedRevs"] == client.state()["_deletedRevs"]
    assert merge_states(holder.state(), client.state())["bookmarks"] == merge_states(client.state(), holder.state())["bookmarks"]
