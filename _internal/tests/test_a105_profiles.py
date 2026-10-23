"""Hồ sơ người nghe (soát a105): mọi thao tác ghi dữ liệu nghe mang MÃ HỒ SƠ chốt lúc việc bắt đầu, không lấy "hồ sơ đang chọn"
lúc ghi. Hợp đồng đồng bộ theo mã hồ sơ nằm trong tests/fixtures/sync/records_host.json - test JVM (A105ProfilesTest.kt) đọc
cùng tệp, nên hai bên nói cùng một thứ."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import remote_books, server, sync
from abook.webui.listening import Listening, RecordGone
from abook.webui.listening_revision import meta_items, observe

BOOK = "sach"
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sync" / "records_host.json").read_text(encoding="utf-8"))
IDS = FIXTURE["ids"]


def state_of(store: Listening, record: str) -> dict:
    return json.loads(json.dumps(store._data["records"][record]["state"]))


def host_from(spec: dict, path: Path) -> Listening:
    """Máy giữ sách dựng từ phía `host` của một ca trong bộ ví dụ dùng chung."""
    store = Listening(path)
    for key, item in spec["records"].items():
        record = {"name": item["name"], "createdAt": 0.0, "nameAt": item["nameAt"], "state": item["state"] | {"chapters": {}}}
        record["state"].setdefault("bookmarks", [])
        if item.get("movedAt"):
            record["movedAt"] = item["movedAt"]
        store._data["records"][IDS[key]] = record
    store._data["links"] = {book: {"records": [IDS[r] for r in link["records"]], "active": IDS[link["active"]], "activeAt": link["activeAt"]}
                            for book, link in spec["links"].items()}
    store._data["deleted"] = {IDS[key]: at for key, at in spec["deleted"].items()}
    store._save()
    return store


def ident(body: dict) -> dict:
    """Thân yêu cầu của bộ ví dụ: mã viết tắt a/b/c -> mã thật."""
    out = dict(body)
    out["record"] = IDS[body["record"]]
    out["deletedRecords"] = {IDS.get(key, key): at for key, at in body.get("deletedRecords", {}).items()}
    return out


def route(store: Listening, book: str, body: dict, monkeypatch: pytest.MonkeyPatch) -> dict:
    result: list = []
    monkeypatch.setattr(sync, "book_id", lambda path: book)
    handler = SimpleNamespace(
        path=f"/sync/v1/books/{book}/state", _device=lambda: {"id": "pc", "name": "PC"}, _body=lambda: body,
        _json=lambda code, payload: result.append((int(code), payload)),
        app=SimpleNamespace(book=lambda value: "fixture-book", listening=store, chapter_lengths=lambda path: {1: 1000}))
    sync.SyncHandler._route(handler, "POST")
    assert result[0][0] == 200, result
    return result[0][1]


def check_after(store: Listening, expect: dict) -> None:
    for book, link in expect["links"].items():
        assert [r["id"] for r in store.records(book)] == [IDS[r] for r in link["records"]], book
        assert store.active_record(book) == IDS[link["active"]], book
    for key, name in expect["names"].items():
        assert store._data["records"][IDS[key]]["name"] == name
    assert sorted(store._data["deleted"]) == sorted(IDS[key] for key in expect["deleted"])
    for key, seconds in expect.get("lastSeconds", {}).items():
        assert state_of(store, IDS[key])["last"]["seconds"] == seconds
    for key, notes in expect.get("bookmarkNotes", {}).items():
        assert [mark["note"] for mark in state_of(store, IDS[key])["bookmarks"]] == notes


def check_reply(reply: dict, expect: dict) -> None:
    assert reply["record"] == IDS[expect["record"]]
    if "book" in expect:
        assert reply["book"] == expect["book"]
    if "deleted" in expect:
        assert reply["deleted"] is expect["deleted"]
    if "lastSeconds" in expect:
        assert reply["last"]["seconds"] == expect["lastSeconds"]
    if "bookmarkNotes" in expect:
        assert [mark["note"] for mark in reply["bookmarks"]] == expect["bookmarkNotes"]
    if "recordName" in expect:
        assert reply["recordName"] == expect["recordName"]
    if "movedAt" in expect:
        assert reply["movedAt"] == expect["movedAt"]
    if "activeRecord" in expect:
        assert reply["active"]["record"] == IDS[expect["activeRecord"]]
    if "activeStateLastSeconds" in expect:
        assert reply["activeState"]["last"]["seconds"] == expect["activeStateLastSeconds"]
    if "recordIds" in expect:
        assert sorted(item["id"] for item in reply["records"]) == sorted(IDS[key] for key in expect["recordIds"])
    for key in expect.get("tombstones", []):
        assert IDS[key] in reply["deletedRecords"]


@pytest.mark.parametrize("case", sorted(FIXTURE["cases"]))
def test_host_follows_the_shared_record_contract(case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Máy giữ sách (Python) theo đúng bộ ví dụ dùng chung với máy giữ sách Android."""
    spec = FIXTURE["cases"][case]
    store = host_from(spec["host"], tmp_path / "host.json")
    reply = route(store, spec["request"]["book"], ident(spec["request"]["body"]), monkeypatch)
    check_reply(reply, spec["expect"]["reply"])
    check_after(store, spec["expect"]["after"])


# ---- F1: máy tính <-> máy tính gửi MÃ HỒ SƠ chốt lúc gửi -------------------------------------------------------------


def paired_computer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sender: Listening, send) -> SimpleNamespace:
    """App của máy gửi: cuốn `sach` là cuốn ảo của một máy tính khác đã ghép; `send(body)` thay đường mạng."""
    manifest = {"package": {"remote": {"computer": "paired-pc", "book": BOOK}}}
    monkeypatch.setattr(server.packages, "is_package", lambda path: True)
    monkeypatch.setattr(server.packages, "manifest", lambda path: manifest)
    monkeypatch.setattr(remote_books, "_COMPUTERS", SimpleNamespace(get=lambda key: {"token": "fake"}))
    monkeypatch.setattr(remote_books, "_base", lambda entry: "http://localhost")
    monkeypatch.setattr(remote_books, "_request",
                        lambda base, method, url, token, body, **kw: json.dumps(send(body)).encode())
    return SimpleNamespace(library=SimpleNamespace(resolve_listenable=lambda value: tmp_path, root=tmp_path),
                           listening=sender, _state_synced={})


def test_computer_sync_keeps_two_people_apart_and_brings_back_only_ones_own_bookmarks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = Listening(tmp_path / "sender.json")
    receiver = Listening(tmp_path / "receiver.json")
    other = receiver.create_record(BOOK, "B")["id"]
    receiver.progress(BOOK, 1, 100, 1000, record=other)
    receiver.add_bookmark(BOOK, 1, 90, "Ghi chu rieng cua B")
    mine = sender.create_record(BOOK, "A")["id"]
    sender.progress(BOOK, 1, 600, 1000, record=mine)
    # Hợp đồng phiên bản (Lamport): hai lần chọn đồng thời xếp theo (counter, node) ngẫu nhiên, không theo giờ tường. "Người chọn sau" là người
    # đã THẤY lựa chọn của B rồi mới chọn: máy gửi nhận phiên bản chọn của máy giữ sách (như khi gộp lời đáp), rồi A chọn lại hồ sơ của mình.
    with sender._changing():
        observe(sender._data, receiver._data["links"][BOOK]["activeRev"], meta_items)
        sender._save()
    sender.activate(BOOK, mine)
    sent: list = []

    def send(body: dict) -> dict:
        sent.append(body)
        return route(receiver, BOOK, body, monkeypatch)

    app = paired_computer(monkeypatch, tmp_path, sender, send)
    server.App.sync_remote_state(app, BOOK, wait=True)

    assert sent[0]["record"] == mine and sent[0]["recordName"] == "A"
    assert {"nameAt", "activeAt", "movedAt", "deletedRecords"} <= set(sent[0])
    assert state_of(receiver, other)["last"]["seconds"] == 100, "hồ sơ của người kia ở máy giữ sách không bị đè"
    assert receiver.active_record(BOOK) == mine, "người chọn sau (phiên bản cao hơn) thắng, như điện thoại"
    assert state_of(receiver, mine)["last"]["seconds"] == 600
    assert state_of(receiver, other)["bookmarks"][0]["note"] == "Ghi chu rieng cua B"
    assert state_of(sender, mine)["bookmarks"] == [], "dấu trang của B không chảy sang A"
    assert state_of(sender, mine)["last"]["seconds"] == 600


def test_computer_reply_after_profile_switch_stays_with_the_profile_it_was_sent_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = Listening(tmp_path / "sender.json")
    a = sender.create_record(BOOK, "A")["id"]
    sender.progress(BOOK, 1, 20, 1000, record=a)
    b = sender.create_record(BOOK, "B")["id"]
    sender.progress(BOOK, 1, 80, 1000, record=b)
    sender.activate(BOOK, a)

    def send(body: dict) -> dict:
        sender.activate(BOOK, b)  # người dùng đổi sang B trong lúc chờ mạng
        return {"record": body["record"], "book": BOOK, "last": {"chapterId": 1, "seconds": 700, "at": time.time() + 10,
                "rev": {"counter": body["last"]["rev"]["counter"] + 1, "node": "holder"}}}

    server.App.sync_remote_state(paired_computer(monkeypatch, tmp_path, sender, send), BOOK, wait=True)

    assert state_of(sender, a)["last"]["seconds"] == 700
    assert state_of(sender, b)["last"]["seconds"] == 80


def test_a_reply_for_a_deleted_record_does_not_create_or_fall_to_another(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = Listening(tmp_path / "sender.json")
    a = sender.create_record(BOOK, "A")["id"]
    sender.progress(BOOK, 1, 20, 1000, record=a)
    b = sender.create_record(BOOK, "B")["id"]
    sender.progress(BOOK, 1, 80, 1000, record=b)

    def send(body: dict) -> dict:
        sender.delete_record(body["record"])  # hồ sơ vừa gửi bị xoá trong lúc chờ mạng
        return {"record": body["record"], "book": BOOK, "last": {"chapterId": 1, "seconds": 999, "at": time.time() + 10,
                "rev": {"counter": body["last"]["rev"]["counter"] + 1, "node": "holder"}}}

    server.App.sync_remote_state(paired_computer(monkeypatch, tmp_path, sender, send), BOOK, wait=True, record=b)

    assert b not in sender._data["records"] and b in sender._data["deleted"]
    assert state_of(sender, a)["last"]["seconds"] == 20
    assert len(sender.records(BOOK)) == 1


def test_rename_and_tombstone_travel_both_ways_over_computer_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sender = Listening(tmp_path / "sender.json")
    host = Listening(tmp_path / "host.json")
    keep = sender.create_record(BOOK, "A")["id"]
    gone = sender.create_record(BOOK, "Con")["id"]
    sender.activate(BOOK, keep)
    app = paired_computer(monkeypatch, tmp_path, sender, lambda body: route(host, BOOK, body, monkeypatch))
    server.App.sync_remote_state(app, BOOK, wait=True)
    server.App.sync_remote_state(app, BOOK, wait=True, record=gone)
    assert {keep, gone} <= set(host._data["records"])
    sender.rename_record(keep, "Bố")
    sender.delete_record(gone)
    app._state_synced.clear()
    server.App.sync_remote_state(app, BOOK, wait=True)
    assert host._data["records"][keep]["name"] == "Bố"
    assert gone not in host._data["records"] and gone in host._data["deleted"]
    # máy giữ sách đổi tên: về máy gửi theo lời đáp
    host.rename_record(keep, "Bố ơi")
    app._state_synced.clear()
    server.App.sync_remote_state(app, BOOK, wait=True)
    assert sender._data["records"][keep]["name"] == "Bố ơi"


# ---- F7: tốc độ / giọng riêng đi đúng hồ sơ của phiên phát ------------------------------------------------------------


def rate_voice_handler(store: Listening, body: dict) -> SimpleNamespace:
    synced: list = []
    app = SimpleNamespace(listening=store, _listenable=lambda _: None,
                          sync_remote_state=lambda *args, **kwargs: synced.append(kwargs))
    return SimpleNamespace(app=app, _body=lambda: body, _send_json=lambda *args: None, synced=synced)


def test_rate_and_voice_go_to_the_profile_the_player_holds_not_the_active_one(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    a = store.create_record(BOOK, "A")["id"]
    b = store.create_record(BOOK, "B")["id"]  # cửa sổ khác đã chuyển cuốn sang B
    handler = rate_voice_handler(store, {"rate": 1.75, "voice": "device:nam", "record": a})
    server.Handler.post_rate(handler, {}, BOOK)
    server.Handler.post_listen_voice(handler, {}, BOOK)
    assert state_of(store, a)["rate"] == 1.75 and state_of(store, a)["voice"] == "device:nam"
    assert "rate" not in state_of(store, b) and "voice" not in state_of(store, b)
    assert handler.synced[-1].get("record") == a


def test_rate_and_voice_for_a_deleted_or_moved_profile_are_refused_clearly(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    a = store.create_record(BOOK, "A")["id"]
    b = store.create_record(BOOK, "B")["id"]
    store.delete_record(a)
    handler = rate_voice_handler(store, {"rate": 1.75, "voice": "device:nam", "record": a})
    for call in (server.Handler.post_rate, server.Handler.post_listen_voice):
        with pytest.raises(server.ApiError) as error:
            call(handler, {}, BOOK)
        assert error.value.status == 409 and "hồ sơ" in error.value.message.lower()
    assert "rate" not in state_of(store, b) and "voice" not in state_of(store, b)
    moved = store.create_record(BOOK, "C")["id"]
    store.move_record(moved, "sach-khac")
    handler = rate_voice_handler(store, {"rate": 1.5, "record": moved})
    with pytest.raises(server.ApiError):
        server.Handler.post_rate(handler, {}, BOOK)
    assert "rate" not in state_of(store, moved)


def test_rate_and_voice_without_a_record_still_use_the_active_profile(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    store.create_record(BOOK, "A")
    b = store.create_record(BOOK, "B")["id"]
    handler = rate_voice_handler(store, {"rate": 1.25, "voice": "device:x"})
    server.Handler.post_rate(handler, {}, BOOK)
    server.Handler.post_listen_voice(handler, {}, BOOK)
    assert state_of(store, b)["rate"] == 1.25 and state_of(store, b)["voice"] == "device:x"


# ---- F5: nhật ký đêm theo hồ sơ -----------------------------------------------------------------------------------------


def night_of(identifier: str = "abc123abc123") -> dict:
    now = time.time()
    return {"id": identifier, "startedAt": now, "endedAt": now, "events": [{"type": "timer", "at": now}], "timeline": []}


def test_a_delayed_night_save_goes_to_the_profile_it_was_recorded_for(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    a = store.create_record(BOOK, "A")["id"]
    b = store.create_record(BOOK, "B")["id"]  # đổi hồ sơ trước khi lượt lưu cuối của A tới
    store.save_night(BOOK, night_of(), record=a)
    assert state_of(store, a)["night"]["id"] == "abc123abc123"
    assert "night" not in state_of(store, b)


def test_night_save_for_a_deleted_profile_is_refused_not_put_in_another(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    a = store.create_record(BOOK, "A")["id"]
    b = store.create_record(BOOK, "B")["id"]
    store.delete_record(a)
    with pytest.raises(RecordGone):
        store.save_night(BOOK, night_of(), record=a)
    assert "night" not in state_of(store, b)


def test_night_endpoint_passes_the_record_and_the_morning_card_follows_the_active_profile(tmp_path: Path) -> None:
    store = Listening(tmp_path / "listen.json")
    a = store.create_record(BOOK, "A")["id"]
    b = store.create_record(BOOK, "B")["id"]
    body = {**night_of(), "record": a}
    handler = SimpleNamespace(app=SimpleNamespace(listening=store, _listenable=lambda _: None), _body=lambda: body, _send_json=lambda *args: None)
    server.Handler.post_night(handler, {}, BOOK)
    assert state_of(store, a)["night"]["id"] == "abc123abc123" and "night" not in state_of(store, b)
    assert store.latest_night() is None, "hồ sơ đang dùng là B: không có đêm của B thì thẻ buổi sáng không mời về chỗ của A"
    store.activate(BOOK, a)
    assert store.latest_night()["night"]["id"] == "abc123abc123"
