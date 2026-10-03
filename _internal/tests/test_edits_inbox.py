"""Điện thoại gửi phần sửa của một cuốn về máy tính (webui/edits_inbox.py, sync.py `POST /sync/v1/books/<mã>/edits`, docs/EDITING.md P2b):
sửa "áp ngay" áp liền bằng đúng các hàm Studio dùng; ý muốn chờ Studio thành yêu cầu khi thiết bị được điều khiển sản xuất từ xa, không
thì nằm trong hộp thư chờ chủ máy duyệt; gói là dữ liệu của người lạ nên bị kiểm như file sách."""
from __future__ import annotations

import http.client
import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook import names as renames
from abook.webui import book_edits, covers, edits_inbox, music_plan, store, tls
from abook.webui.actions import FakeRunner
from abook.webui.library import Library, Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.remote_studio import StudioGate
from abook.webui.server import App
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests import book_edits_fixtures as shared
from tests.test_bookfile_music import _plan

HEAD = shared.HEAD
DEVICE = "a1b2c3d4e5f6"


def _zip(members: dict[str, bytes | str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return out.getvalue()


def package(tmp_path: Path, edits: dict[str, Any] | None = None, *, cover: bytes | None = None,
            tracks: dict[str, bytes] | None = None, raw_edits: bytes | None = None) -> Path:
    """Gói phần sửa như điện thoại đóng (edits.json, edits/cover.jpg, music/<sha1>.<đuôi>)."""
    members: dict[str, bytes | str] = {}
    if raw_edits is not None:
        members["edits.json"] = raw_edits
    elif edits is not None:
        members["edits.json"] = book_edits.dump(book_edits.validate({**HEAD, **edits}))
    if cover is not None:
        members["edits/cover.jpg"] = cover
    for name, data in (tracks or {}).items():
        members[name] = data
    path = tmp_path / f"goi_{len(list(tmp_path.glob('goi_*')))}.zip"
    path.write_bytes(_zip(members))
    return path


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    producer = tmp_path / "may_tinh"
    producer.mkdir()
    folder = shared.make_base_project(producer)
    _plan(folder)
    return folder


def _app(tmp_path: Path, project: Path) -> App:
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(project.parent)})
    return App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))


# Cơ sở dữ liệu của dự án thử (make_base_project) chỉ có vài cột: những ý muốn mà Studio kiểm bằng cột khác (người nói, cách đọc câu,
# giọng) chỉ vào hộp thư được, chưa "áp" được trong bài thử - ba loại dưới đây áp được.
FOLDABLE = {k: shared.WISHES[k] for k in ("pronunciations", "retakes", "aliases")}


def _overrides(project: Path) -> dict[str, Any]:
    from abook.listener_overrides import read_overrides

    return read_overrides(project)


# ---- sửa "áp ngay" -----------------------------------------------------------------------------------------------------


def test_layer_edits_fold_at_once_through_the_studio_writers(tmp_path: Path, project: Path) -> None:
    edits = {"title": "Tên từ điện thoại", "cover": {"color": "#aa5522", "width": 96, "height": 128, "version": 7},
             "characters": {"LUCIEN": "Lu-xi-en"}, "chapters": {"1": {"title": "Chương Một", "subtitle": "Mở"}},
             "music": {"enabled": False, "levelDb": -26, "silenced": ["1:60000"]}}
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, edits, cover=shared.tiny_cover()))
    assert (report["applied"], report["skipped"], report["music"], report["requests"], report["waiting"]) == (7, 0, True, 0, 0)
    assert report["conflicts"] == []
    assert store.display_title(project, "") == "Tên từ điện thoại"
    assert renames.shown(project, "LUCIEN") == "Lu-xi-en" and covers.cover_file(project) is not None
    assert store.chapter_title_overrides(project) == {1: {"title": "Chương Một", "subtitle": "Mở"}}
    music = music_plan.read_overrides(project)
    assert music["enabled"] is False and music["levelDb"] == -26.0 and music["silenced"] == ["1:9"]
    # Không để lại gì ngoài sổ: không có phần chờ như khi mở file sách, không có thư mục tạm.
    assert not (project / book_edits.INCOMING_FILE).exists()
    assert not [item for item in project.iterdir() if item.name.startswith(".edits_in_")]


def test_a_character_or_chapter_the_project_does_not_have_is_skipped_and_counted(tmp_path: Path, project: Path) -> None:
    edits = {"characters": {"KHONGCO": "Ai đó"}, "chapters": {"99": {"title": "Chương lạ"}}, "title": "Có tên"}
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, edits))
    assert (report["applied"], report["skipped"]) == (1, 2)
    assert store.display_title(project, "") == "Có tên"


def test_a_pinned_track_is_taken_into_the_computers_own_store(tmp_path: Path, project: Path) -> None:
    app = _app(tmp_path, project)
    name = f"music/{shared.TRACK_SHA}.wav"
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"music": shared.PINS}, tracks={name: shared.tone_wav()}),
                                 my_music=app.my_music)
    assert (report["applied"], report["skipped"], report["music"]) == (1, 0, True)
    assert music_plan.read_overrides(project)["pins"] == {"1:1": shared.TRACK_LINK, "1:5": shared.TRACK_LINK}
    assert app.my_music.file(shared.TRACK_LINK) is not None


# ---- ý muốn chờ Studio -------------------------------------------------------------------------------------------------


def test_wishes_wait_in_the_inbox_when_the_device_may_not_produce(tmp_path: Path, project: Path) -> None:
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": shared.WISHES}), now=1000.0)
    assert (report["applied"], report["requests"], report["waiting"], report["skippedWishes"]) == (0, 0, 6, 0)
    assert "wishes" not in _overrides(project) and not (_overrides(project).get("pronunciations"))
    assert _overrides(project).get("speakers") in (None, {}) and _overrides(project).get("retakes") in (None, {})
    view = edits_inbox.view(project)
    assert view["waiting"] == 6 and [device["name"] for device in view["devices"]] == ["Pixel"]
    labels = [item["label"] for item in view["devices"][0]["items"]]
    assert "“Hailkes” đọc là “Hên-khơ”" in labels
    assert any("là lời của" in label for label in labels) and any("Giọng của" in label for label in labels)
    assert edits_inbox.waiting(project, DEVICE) == 6 and edits_inbox.waiting(project, "khac") == 0


def test_applying_one_item_makes_a_real_request_and_leaves_the_rest(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": shared.WISHES}), now=1000.0)
    item = next(item for item in edits_inbox.view(project)["devices"][0]["items"] if item["kind"] == "pronunciation")
    done = edits_inbox.apply(project, DEVICE, [item["id"]], now=2000.0)
    assert (done["requests"], done["skipped"], done["left"]) == (1, 0, 5)
    requested = _overrides(project)["pronunciations"]
    assert [entry["spoken_form"] for entry in requested.values()] == ["Hên-khơ"]
    assert next(iter(requested.values()))["requested_at"] == 2000.0, "giờ đóng dấu lại theo máy tính (đồng hồ điện thoại có thể lệch)"
    assert edits_inbox.waiting(project) == 5


def test_applying_a_device_takes_everything_it_sent_and_empties_its_box(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), now=1000.0)
    done = edits_inbox.apply(project, DEVICE, None, now=2000.0)
    assert done["left"] == 0 and done["requests"] == 3, done
    assert set(_overrides(project)["retakes"]) == {shared.NARRATION[0], shared.SECOND_CHAPTER[0]}
    assert edits_inbox.view(project)["devices"] == []
    assert not (project / edits_inbox.INBOX_FILE).exists() or json.loads((project / edits_inbox.INBOX_FILE).read_text("utf-8"))["devices"] == {}


def test_skipping_an_item_or_a_device_changes_nothing_in_the_project(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": shared.WISHES}), now=1000.0)
    first = edits_inbox.view(project)["devices"][0]["items"][0]
    assert edits_inbox.skip(project, DEVICE, [first["id"]]) == {"removed": 1, "left": 5}
    assert edits_inbox.skip(project, DEVICE, None) == {"removed": 5, "left": 0}
    assert edits_inbox.skip(project, DEVICE, None) == {"removed": 0, "left": 0}
    assert not _overrides(project).get("pronunciations") and edits_inbox.view(project)["waiting"] == 0


def test_a_second_push_replaces_the_same_wish_and_adds_new_ones(tmp_path: Path, project: Path) -> None:
    again = {"pronunciations": {"hailkes": {"requested_at": 1759400099.0, "spoken_form": "Hai-ơ-kơ", "surface": "Hailkes"}}}
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": shared.WISHES}), now=1000.0)
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": again}), now=1500.0)
    wishes = json.loads((project / edits_inbox.INBOX_FILE).read_text("utf-8"))["devices"][DEVICE]["wishes"]
    assert wishes["pronunciations"]["hailkes"]["spoken_form"] == "Hai-ơ-kơ", "bản đến sau thắng"
    assert len(wishes["lines"]) == 1 and edits_inbox.waiting(project) == 6


def test_a_device_that_may_produce_turns_wishes_into_requests_at_once(tmp_path: Path, project: Path) -> None:
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), may_produce=True, now=3000.0)
    assert report["waiting"] == 0 and report["requests"] == 3
    assert [entry["spoken_form"] for entry in _overrides(project)["pronunciations"].values()] == ["Hên-khơ"]
    assert edits_inbox.view(project)["waiting"] == 0


def test_a_wish_that_no_longer_fits_the_project_is_skipped_when_applied(tmp_path: Path, project: Path) -> None:
    stale = {"retakes": {"c9_s0001_zzzzzz": {"requested_at": 1759400005.0, "text_sha256": "0" * 64}}}
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": stale}), now=1000.0)
    done = edits_inbox.apply(project, DEVICE, None, now=2000.0)
    assert (done["requests"], done["skipped"], done["left"]) == (0, 1, 0)


# ---- xung đột ----------------------------------------------------------------------------------------------------------


def test_a_key_the_owner_changed_since_the_last_push_is_a_conflict_and_the_phone_still_wins(tmp_path: Path, project: Path) -> None:
    store.set_display_title(project, "Tên của chủ máy")
    first = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"title": "Tên điện thoại 1"}))
    assert [item["kind"] for item in first["conflicts"]] == ["title"] and "Pixel" in first["conflicts"][0]["label"]
    assert store.display_title(project, "") == "Tên điện thoại 1", "đến sau thắng"
    again = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"title": "Tên điện thoại 2"}))
    assert again["conflicts"] == [], "giá trị đang có là chính cái điện thoại gửi lần trước: không ai đổi gì chen vào"
    store.set_display_title(project, "Chủ máy sửa lại")
    third = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"title": "Tên điện thoại 3"}))
    assert [item["kind"] for item in third["conflicts"]] == ["title"]
    assert [entry["conflicts"] for entry in edits_inbox.view(project)["recent"]][0] == [third["conflicts"][0]["label"]]


def test_the_same_value_on_both_sides_is_not_a_conflict(tmp_path: Path, project: Path) -> None:
    store.set_display_title(project, "Giống nhau")
    assert edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"title": "Giống nhau"}))["conflicts"] == []


def test_names_music_and_chapters_report_their_own_conflicts(tmp_path: Path, project: Path) -> None:
    renames.set_name(project, "LUCIEN", "Tên chủ máy", "Lucien")
    music_plan.write_overrides(project, {"levelDb": -30})
    store.set_chapter_title(project, 1, "Chương của chủ", None)
    edits = {"characters": {"LUCIEN": "Tên điện thoại"}, "music": {"levelDb": -22}, "chapters": {"1": {"title": "Chương khác"}}}
    report = edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, edits))
    assert sorted(item["kind"] for item in report["conflicts"]) == ["chapter", "character", "music"]


# ---- gói của người lạ --------------------------------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore:Duplicate name")
@pytest.mark.parametrize("case", ["not_zip", "stranger_member", "bad_json", "unknown_key", "unpinned_music", "missing_pinned_music",
                                  "cover_without_object", "cover_not_jpeg", "duplicate_member", "wishes_overlong"])
def test_a_bad_package_is_refused_whole_and_nothing_applies(tmp_path: Path, project: Path, case: str) -> None:
    title = {"title": "Sẽ không áp"}
    name = f"music/{shared.TRACK_SHA}.wav"
    if case == "not_zip":
        path = tmp_path / "x.zip"
        path.write_bytes(b"not a zip")
    elif case == "stranger_member":
        path = package(tmp_path, title, tracks={"scripts/1.json": b"{}"})
    elif case == "bad_json":
        path = package(tmp_path, raw_edits=b"{not json")
    elif case == "unknown_key":
        path = package(tmp_path, raw_edits=json.dumps({**HEAD, "pins": []}).encode())
    elif case == "unpinned_music":
        path = package(tmp_path, title, tracks={name: shared.tone_wav()})
    elif case == "missing_pinned_music":
        path = package(tmp_path, {"music": shared.PINS})
    elif case == "cover_without_object":
        path = package(tmp_path, title, cover=shared.tiny_cover())
    elif case == "cover_not_jpeg":
        path = package(tmp_path, {"cover": {"color": "#000000", "width": 1, "height": 1, "version": 1}}, cover=b"GIF89a....")
    elif case == "duplicate_member":
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("edits.json", book_edits.dump(book_edits.validate({**HEAD, **title})))
            archive.writestr("edits.json", book_edits.dump(book_edits.validate({**HEAD, "title": "Khác"})))
        path = tmp_path / "dup.zip"
        path.write_bytes(out.getvalue())
    else:
        long = {"pronunciations": {"x": {"requested_at": 1.0, "spoken_form": "y" * 500, "surface": "X"}}}
        path = package(tmp_path, raw_edits=json.dumps({**HEAD, "wishes": long}).encode())
    with pytest.raises(edits_inbox.InboundError):
        edits_inbox.receive(project, DEVICE, "Pixel", path)
    assert store.display_title(project, "") == "" and not (project / edits_inbox.INBOX_FILE).exists()


# ---- qua cổng đồng bộ (TLS, mã thiết bị) -------------------------------------------------------------------------------


@pytest.fixture()
def gate(tmp_path: Path, project: Path):
    library = Library(Preferences(tmp_path / "prefs" / "p.json"))
    library.preferences.update({"libraryRoot": str(project.parent)})
    listening = Listening(tmp_path / "prefs" / "listening.json")
    devices = Devices(tmp_path / "devices.json")
    switch = {"on": False}
    studio = StudioGate(allowed=lambda: switch["on"], port=lambda: 0, token=None, static_dir=tmp_path)
    app = _app(tmp_path, project)
    rebuilt: list[str] = []
    sync = SyncApp(library, listening, devices, "Máy thử", studio=studio, my_music=app.my_music,
                   after_edits=lambda value, _report: rebuilt.append(value))
    server = SyncServer(sync, host="127.0.0.1", port=0).start()
    code = devices.start_pairing()["code"]
    token = _call(server.port, "POST", "/sync/v1/pair", body=json.dumps({"code": code, "device": "Pixel"}).encode(),
                  content="application/json")[1]["token"]
    try:
        yield server, devices, token, switch, rebuilt, book_id(project)
    finally:
        server.stop()


def _call(port: int, method: str, path: str, token: str = "", body: bytes | None = None, content: str = "application/zip",
          headers: dict[str, str] | None = None) -> tuple[int, Any]:
    connection = tls.PinnedHTTPSConnection("127.0.0.1", port, expected=None, timeout=15)
    sent = {"Authorization": f"Bearer {token}"} if token else {}
    if body is not None:
        sent["Content-Type"] = content
    sent.update(headers or {})
    connection.request(method, path, body=body, headers=sent)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, json.loads(data) if data[:1] in (b"{", b"[") else data


def _zip_of(tmp_path: Path, edits: dict[str, Any], **extra: Any) -> bytes:
    return package(tmp_path, edits, **extra).read_bytes()


def test_a_paired_phone_pushes_edits_and_they_fold(tmp_path: Path, gate) -> None:
    server, _devices, token, _switch, rebuilt, identifier = gate
    project = Library(Preferences(tmp_path / "prefs" / "p.json")).resolve(identifier)
    body = _zip_of(tmp_path, {"title": "Từ điện thoại", "music": {"levelDb": -25}, "wishes": shared.WISHES})
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, body)
    assert status == 200, reply
    assert (reply["applied"], reply["requests"], reply["waiting"], reply["music"]) == (2, 0, 6, True)
    assert store.display_title(project, "") == "Từ điện thoại" and rebuilt == [identifier]
    status, reply = _call(server.port, "GET", f"/sync/v1/books/{identifier}/edits", token)
    assert (status, reply) == (200, {"waiting": 6})


def test_the_remote_studio_permission_turns_wishes_into_requests(tmp_path: Path, gate) -> None:
    server, devices, token, switch, _rebuilt, identifier = gate
    body = _zip_of(tmp_path, {"wishes": {"pronunciations": shared.WISHES["pronunciations"]}})
    switch["on"] = True  # công tắc chung bật nhưng thiết bị chưa được phép: vẫn vào hộp thư
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, body)
    assert (status, reply["requests"], reply["waiting"]) == (200, 0, 1)
    device = devices.list()[0]
    assert devices.set_studio(device["id"], True)
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, body)
    assert (status, reply["requests"]) == (200, 1)
    switch["on"] = False  # thiết bị được phép mà công tắc chung tắt: lại về hộp thư
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, body)
    assert (status, reply["requests"], reply["waiting"]) == (200, 0, 1)


def test_the_edits_route_refuses_strangers_unknown_books_and_bad_bodies(tmp_path: Path, gate) -> None:
    server, _devices, token, _switch, _rebuilt, identifier = gate
    body = _zip_of(tmp_path, {"title": "x"})
    assert _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", "", body)[0] == 401, "chưa ghép nối"
    assert _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", "ma-gia", body)[0] == 401
    assert _call(server.port, "POST", "/sync/v1/books/" + "0" * 24 + "/edits", token, body)[0] == 404, "sách không có trong thư viện"
    assert _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, body, content="application/json")[0] == 415
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, b"not a zip")
    assert status == 400 and "hỏng" in reply["error"]
    status, reply = _call(server.port, "POST", f"/sync/v1/books/{identifier}/edits", token, _zip({"scripts/1.json": b"{}"}))
    assert status == 400 and "mục lạ" in reply["error"]
    assert _call(server.port, "PUT", f"/sync/v1/books/{identifier}/edits", token, body)[0] == 405
    connection = tls.PinnedHTTPSConnection("127.0.0.1", server.port, expected=None, timeout=15)
    connection.putrequest("POST", f"/sync/v1/books/{identifier}/edits")
    connection.putheader("Authorization", f"Bearer {token}")
    connection.putheader("Content-Type", "application/zip")
    connection.putheader("Content-Length", str(10**10))
    connection.endheaders()
    assert connection.getresponse().status == 413, "cỡ gói vượt trần bị từ chối trước khi đọc thân"
    connection.close()
    assert not (Library(Preferences(tmp_path / "prefs" / "p.json")).resolve(identifier) / "studio_title.json").exists()


# ---- hộp thư trong giao diện máy tính ----------------------------------------------------------------------------------


def test_the_desktop_lists_and_decides_the_inbox_through_the_ui_routes(tmp_path: Path, project: Path) -> None:
    from abook.webui.server import Server
    from tests.test_webui_listen_and_sync import _request

    app = _app(tmp_path, project)
    server = Server(app, port=0).start()
    identifier = book_id(project)
    token = {"X-Ebook-Token": "t"}
    try:
        edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), now=1000.0)
        status, data, _ = _request(server.port, "GET", f"/api/books/{identifier}/edits-inbox", headers=token)
        view = json.loads(data)
        assert status == 200 and view["waiting"] == 3 and view["devices"][0]["id"] == DEVICE
        first = view["devices"][0]["items"][0]["id"]
        status, data, _ = _request(server.port, "POST", f"/api/books/{identifier}/edits-inbox/skip", headers=token,
                                   body={"device": DEVICE, "items": [first]})
        assert (status, json.loads(data)) == (200, {"removed": 1, "left": 2})
        status, data, _ = _request(server.port, "POST", f"/api/books/{identifier}/edits-inbox/apply", headers=token, body={"device": DEVICE})
        assert status == 200 and json.loads(data)["left"] == 0
        assert _request(server.port, "POST", f"/api/books/{identifier}/edits-inbox/apply", headers=token, body={})[0] == 400
        assert _request(server.port, "POST", f"/api/books/{identifier}/edits-inbox/apply", headers=token,
                        body={"device": DEVICE, "items": [3]})[0] == 400
        assert _request(server.port, "GET", "/api/books/" + "0" * 24 + "/edits-inbox", headers=token)[0] == 404
    finally:
        server.stop()
