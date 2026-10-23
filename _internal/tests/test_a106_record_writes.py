"""Bốn việc ghi còn lại của người nghe (a106): đánh dấu chương đã nghe, đánh dấu cả cuốn, sửa ghi chú, xoá dấu trang ghi vào HỒ SƠ ĐÃ
CHỐT lúc việc bắt đầu (`record`), không phải hồ sơ đang dùng lúc yêu cầu tới - cửa sổ khác vừa đổi hồ sơ thì không ghi nhầm người.
Ca dùng chung với test JVM (A106RecordWritesTest.kt) ở tests/fixtures/records/writes.json."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook.webui import server
from abook.webui.listening import Listening, RecordGone

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "records" / "writes.json").read_text(encoding="utf-8"))
IDS = FIXTURE["ids"]
BOOK = FIXTURE["book"]


def build(path: Path) -> Listening:
    store = Listening(path)
    setup = FIXTURE["setup"]
    for key, item in setup["records"].items():
        store._data["records"][IDS[key]] = {"name": key, "createdAt": 0.0, "nameAt": 0.0, "state": json.loads(json.dumps(item["state"]))}
        link = store._data["links"].setdefault(item["book"], {"records": []})
        link["records"].append(IDS[key])
        link.setdefault("active", IDS[key])
    store._data["links"][BOOK]["active"] = IDS[setup["active"]]
    store._save()
    return store


def projection(store: Listening, key: str) -> dict:
    state = store._data["records"][IDS[key]]["state"]
    return json.loads(json.dumps({name: state.get(name) for name in ("chapters", "bookmarks", "finished", "deleted")}))


def snapshot(store: Listening) -> dict:
    return {key: projection(store, key) for key in FIXTURE["setup"]["records"]}


def apply_op(store: Listening, op: dict) -> None:
    record = IDS[op["record"]] if "record" in op else None
    kind = op["kind"]
    if kind == "chapterDone":
        store.set_chapter_done(BOOK, op["chapterId"], op["done"], record)
    elif kind == "finished":
        store.set_finished(BOOK, op["finished"], record)
    elif kind == "updateBookmark":
        store.update_bookmark(BOOK, op["markId"], op["note"], record)
    else:
        store.delete_bookmark(BOOK, op["markId"], record)


def check_applied(before: dict, after: dict, op: dict) -> None:
    """Hồ sơ nhận lần ghi: đúng điều việc ấy nói, không gì khác."""
    kind = op["kind"]
    if kind == "chapterDone":
        chapter = after["chapters"][str(op["chapterId"])]
        assert chapter["done"] is op["done"]
        assert chapter["heard"] == (before["chapters"][str(op["chapterId"])]["heard"] if op["done"] else 0.0)
    elif kind == "finished":
        assert after["finished"] is op["finished"]
    elif kind == "updateBookmark":
        for was, now in zip(before["bookmarks"], after["bookmarks"], strict=True):
            assert now["note"] == (op["note"] if was["id"] == op["markId"] else was["note"])
    else:
        assert [mark["id"] for mark in after["bookmarks"]] == [mark["id"] for mark in before["bookmarks"] if mark["id"] != op["markId"]]
        assert op["markId"] in (after.get("deleted") or {})


@pytest.mark.parametrize("case", sorted(FIXTURE["cases"]))
def test_shared_cases(case: str, tmp_path: Path) -> None:
    spec = FIXTURE["cases"][case]
    store = build(tmp_path / "listen.json")
    before = snapshot(store)
    if spec["applied"] is None:
        with pytest.raises(RecordGone):
            apply_op(store, spec["op"])
        assert snapshot(store) == before
        return
    apply_op(store, spec["op"])
    after = snapshot(store)
    for key in before:
        if key == spec["applied"]:
            check_applied(before[key], after[key], spec["op"])
        else:
            assert after[key] == before[key], f"hồ sơ {key} không được đổi"


def handler(store: Listening, body: dict, query: dict | None = None) -> SimpleNamespace:
    synced: list = []
    app = SimpleNamespace(listening=store, _listenable=lambda _: None, sync_remote_state=lambda *args, **kwargs: synced.append(kwargs))
    return SimpleNamespace(app=app, _body=lambda: body, _send_json=lambda *args: None, synced=synced, _query=query or {})


def test_endpoints_pass_the_record_the_window_holds(tmp_path: Path) -> None:
    store = build(tmp_path / "listen.json")
    a = IDS["a"]
    server.Handler.post_chapter_done(handler(store, {"done": True, "record": a}), {}, BOOK, "3")
    server.Handler.post_finished(handler(store, {"finished": True, "record": a}), {}, BOOK)
    server.Handler.put_bookmark(handler(store, {"note": "sửa", "record": a}), {}, BOOK, "aaaaaaaaaaaa")
    state = store._data["records"][a]["state"]
    assert state["chapters"]["3"]["done"] is True and state["finished"] is True and state["bookmarks"][0]["note"] == "sửa"
    b = store._data["records"][IDS["b"]]["state"]
    assert b["chapters"]["3"]["done"] is False and "finished" not in b and b["bookmarks"][0]["note"] == "của B"
    delete = handler(store, {"record": a})
    server.Handler.delete_bookmark(delete, {}, BOOK, "aaaaaaaaaaaa")
    assert store._data["records"][a]["state"]["bookmarks"] == [] and len(b["bookmarks"]) == 1
    assert delete.synced[-1].get("record") == a


def test_delete_bookmark_takes_the_record_from_the_query_when_the_body_is_empty(tmp_path: Path) -> None:
    """DELETE thường không có thân: lời gọi mang hồ sơ ở `?record=`."""
    store = build(tmp_path / "listen.json")
    window = handler(store, {}, {"record": [IDS["a"]]})
    server.Handler.delete_bookmark(window, {"record": [IDS["a"]]}, BOOK, "aaaaaaaaaaaa")
    assert store._data["records"][IDS["a"]]["state"]["bookmarks"] == []
    assert len(store._data["records"][IDS["b"]]["state"]["bookmarks"]) == 1


@pytest.mark.parametrize("call,body,args", [
    (server.Handler.post_chapter_done, {"done": True}, ("3",)),
    (server.Handler.post_finished, {"finished": True}, ()),
    (server.Handler.put_bookmark, {"note": "x"}, ("aaaaaaaaaaaa",)),
    (server.Handler.delete_bookmark, {}, ("aaaaaaaaaaaa",)),
])
def test_endpoints_refuse_a_gone_record_with_409_and_write_nothing(call, body, args, tmp_path: Path) -> None:
    store = build(tmp_path / "listen.json")
    before = snapshot(store)
    window = handler(store, {**body, "record": IDS["d"]}, {"record": [IDS["d"]]})
    with pytest.raises(server.ApiError) as error:
        call(window, {"record": [IDS["d"]]}, BOOK, *args)
    assert error.value.status == 409 and "hồ sơ" in error.value.message.lower()
    assert snapshot(store) == before
