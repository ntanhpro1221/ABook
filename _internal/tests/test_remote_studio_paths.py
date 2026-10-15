"""Studio từ xa không bao giờ trả đường dẫn tuyệt đối của máy tính (có tên người dùng Windows), và làm được những việc cần file nguồn
(Sửa thiết lập / Làm lại phân tích, Làm tiếp cuốn này) mà thiết bị chỉ cầm tham chiếu `ref:...` (webui/remote_sources.py): soát UX a33."""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

import pytest

from abook import continuation
from abook.webui import remote_sources, remote_studio, store
from abook.webui.library import book_id
from abook.webui.server import is_local_path, without_local_paths
from tests.test_remote_studio import _pair_browser, studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import library  # noqa: F401
from tests.test_webui_listen_and_sync import _sync_request

ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
# Chỗ giữ cho từng nhóm ký tự của danh sách trắng khi dựng một đường thật để gọi (cùng bảng với test_every_allowed_route_exists_on_the_computer).
SAMPLES = (("r-[0-9a-f]{16}", "r-0123456789abcdef"), (r"[0-9a-f]{32}\.wav", "b" * 32 + ".wav"), (r"\d+", "1"), ("[0-9a-f]+", "ab12"),
           ("[^/]+", "Duc"))


def _strings(value: Any) -> Iterator[str]:
    """Mọi chuỗi trong một cây JSON, cả khoá lẫn giá trị."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def _leaks(data: bytes, private: list[str]) -> list[str]:
    """Chuỗi trong lời đáp JSON trông như đường dẫn Windows tuyệt đối, hay có chứa thư mục riêng của máy tính."""
    try:
        tree = json.loads(data)
    except ValueError:
        return []
    return [text for text in _strings(tree) if ABSOLUTE.match(text) or text.startswith("\\\\") or any(item in text for item in private)]


def _path_of(pattern: re.Pattern[str], book: str) -> str:
    path = pattern.pattern.replace("[A-Za-z0-9_-]+", book)
    for token, sample in SAMPLES:
        path = path.replace(token, sample)
    return path


def _remote_gets() -> list[re.Pattern[str]]:
    # Âm thanh, bìa là byte, không phải JSON. Nhạc nền và tìm bìa cần danh mục / mạng mà bài thử không có (chờ mạng tới hết thời gian):
    # lời đáp của chúng dựng từ danh mục nhạc đã ký, không từ thư mục của máy tính.
    return [pattern for method, pattern in remote_studio.ALLOWED if method == "GET" and not pattern.pattern.startswith("/media/")
            and "/music" not in pattern.pattern and "/cover/search" not in pattern.pattern]


def _cookie_with_studio(app) -> dict[str, str]:
    # Không hỏi Ollama thật (cổng 11434) trong bài thử: danh sách model là câu trả lời dựng sẵn.
    app.analysis_models = lambda: {"default": "", "models": [], "reachable": False}
    app.set_remote_studio(True)
    cookie = {"Cookie": _pair_browser(app)}
    short_id = next(device["id"] for device in app.sync_view()["devices"])
    assert app.devices.set_studio(short_id, True)
    return cookie


def _give_the_book_real_sources(project: Path, story: Path) -> None:
    story.mkdir()
    for number, name in enumerate(("645.txt", "646.txt", "647.txt"), start=1):
        (story / name).write_text(f"Chương {name[:3]}\nLucien đi tiếp.\n", encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET input_path=? WHERE id=1", (str(story / "645.txt"),))
    db.execute("UPDATE chapters SET input_path=? WHERE id=2", (str(story / "646.txt"),))
    db.commit()
    db.close()


def test_the_path_filter_keeps_what_a_device_must_send_back_and_drops_the_rest() -> None:
    assert is_local_path("C:\\Users\\ai-do\\Sach") and is_local_path("D:/Sach") and is_local_path("\\\\may\\share")
    assert not is_local_path("Sach.abook") and not is_local_path("/media/books/x")
    cleaned = without_local_paths({"libraryRoot": "C:\\a", "libraryRootSeen": "C:\\a", "folder": "C:\\a\\x", "file": "C:\\a\\x\\Sach.abook",
                                   "result": {"file": "C:\\a\\Sach.m4b", "folder": "C:\\a", "size": 3},
                                   "books": [{"id": "x", "path": "C:\\a\\x", "title": "Sách"}]})
    assert cleaned["libraryRootSeen"] == "" and "folder" not in cleaned and cleaned["file"] == "Sach.abook"
    assert cleaned["result"] == {"file": "Sach.m4b", "size": 3} and cleaned["books"] == [{"id": "x", "title": "Sách"}]


def test_no_remote_get_answers_with_an_absolute_path(studio, tmp_path: Path) -> None:
    """Đi qua MỌI đường GET trong danh sách trắng (không từng khoá một): lời đáp nào cũng không mang đường dẫn Windows tuyệt đối hay thư mục
    thư viện / dự án của máy tính - kể cả khi lời đáp là lỗi."""
    app, project = studio
    _give_the_book_real_sources(project, tmp_path / "truyen")
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    identifier = book_id(project)
    library = Path(app.preferences.get()["libraryRoot"])
    app.preferences.update({"libraryRootSeen": str(library)})
    private = [str(library), str(project), str(tmp_path)]
    # Một lượt xuất đã xong: kết quả của nó (file, folder) cũng là lời đáp GET.
    status, _data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/bookfile-job", headers=cookie, body={})
    assert status == 202
    deadline = time.time() + 20
    while time.time() < deadline:
        _status, data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/bookfile-job", headers=cookie)
        if json.loads(data)["state"] != "running":
            break
        time.sleep(0.2)
    assert json.loads(data)["state"] == "done", data
    assert json.loads(data)["result"]["file"].endswith(".abook") and "\\" not in json.loads(data)["result"]["file"]
    reached = 0
    for pattern in _remote_gets():
        path = _path_of(pattern, identifier)
        status, data, headers = _sync_request(port, "GET", path, headers=cookie)
        if "json" not in headers.get("Content-Type", ""):
            continue
        reached += 1
        assert _leaks(data, private) == [], (path, status, _leaks(data, private))
    assert reached >= 25, "đã đi qua hầu hết các đường GET có JSON"
    status, data, _ = _sync_request(port, "GET", "/api/preferences", headers=cookie)
    assert json.loads(data)["libraryRootSeen"] == "" and json.loads(data)["libraryRoot"] == ""
    assert app.preferences.get()["libraryRootSeen"] == str(library), "máy tính vẫn nhớ thư mục của nó"


def test_a_finished_export_tells_a_remote_device_only_the_file_name(studio) -> None:
    app, project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    identifier = book_id(project)
    status, data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/bookfile-job", headers=cookie, body={"target": str(project)})
    assert status == 202
    deadline = time.time() + 20
    while time.time() < deadline:
        _status, data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/bookfile-job", headers=cookie)
        if json.loads(data)["state"] != "running":
            break
        time.sleep(0.2)
    job = json.loads(data)
    assert job["state"] == "done" and Path(job["result"]["file"]).name == job["result"]["file"] and "folder" not in job["result"]
    assert job["result"]["file"].endswith(".abook")
    status, data, _ = _sync_request(port, "GET", "/api/export-jobs", headers=cookie)
    assert status == 200 and set(json.loads(data)) >= {"bookfile", "m4b"}, "tải lại trang vẫn hỏi lại được việc đang chạy"
    status, data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/music-export", headers=cookie)
    assert status == 200 and json.loads(data)["active"] is False
    status, data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/music-export/cancel", headers=cookie, body={})
    assert status == 200 and "cancelling" in json.loads(data)
    # Chỉ nghe thì không huỷ được việc của máy tính, và cũng không hỏi được trạng thái xuất.
    assert not remote_studio.permitted("POST", f"/api/books/{identifier}/music-export/cancel", producing=False)
    assert not remote_studio.permitted("GET", "/api/export-jobs", producing=False)


def test_a_remote_device_renames_the_book_and_decides_the_phone_inbox(studio) -> None:
    app, project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    identifier = book_id(project)
    status, data, _ = _sync_request(port, "PUT", f"/api/books/{identifier}/title", headers=cookie, body={"title": "Tên mới từ xa"})
    assert status == 200, data
    assert app.summary(app.library.resolve(identifier))["title"] == "Tên mới từ xa"
    status, data, _ = _sync_request(port, "PUT", f"/api/books/{identifier}/chapters/1/title", headers=cookie, body={"title": "Chương một"})
    assert status == 200, data
    status, data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/edits-inbox", headers=cookie)
    assert status == 200 and json.loads(data)["waiting"] == 0
    for verb in ("apply", "skip"):
        status, data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/edits-inbox/{verb}", headers=cookie, body={"device": "khong-co"})
        assert status == 200, (verb, data)
    # Chỉ nghe: không đổi tên, không quyết hộp thư.
    for method, path in (("PUT", f"/api/books/{identifier}/title"), ("PUT", f"/api/books/{identifier}/author"),
                         ("GET", f"/api/books/{identifier}/edits-inbox"), ("POST", f"/api/books/{identifier}/edits-inbox/apply"),
                         ("GET", f"/api/books/{identifier}/redo")):
        assert remote_studio.permitted(method, path) and not remote_studio.permitted(method, path, producing=False), (method, path)


def _redo_world(studio, tmp_path: Path) -> tuple[Any, Path, dict[str, str], Path]:
    app, project = studio
    story = tmp_path / "truyen"
    _give_the_book_real_sources(project, story)
    # Một cuốn mới tạo, chưa chạy gì: "Sửa thiết lập" làm lại được.
    created = app.create({"paths": [str(story / "645.txt"), str(story / "646.txt")], "title": "Cuốn chưa chạy", "profile": "high_quality",
                          "narrator": "", "firstPerson": ""})
    cookie = _cookie_with_studio(app)
    return app, app.library.resolve(created["id"]), cookie, story


def test_a_remote_redo_hands_out_no_path_and_recreates_the_same_book(studio, tmp_path: Path) -> None:
    app, old, cookie, story = _redo_world(studio, tmp_path)
    port = app.sync_server.port
    old_id = book_id(old)
    status, data, _ = _sync_request(port, "GET", f"/api/books/{old_id}/redo", headers=cookie)
    plan = json.loads(data)
    assert status == 200 and plan["started"] is False and len(plan["paths"]) == 2
    assert all(remote_sources.parse(item) for item in plan["paths"]) and str(story) not in data.decode("utf-8")
    assert _leaks(data, [str(story), str(tmp_path)]) == []
    local = app.redo(old_id)  # máy tính thì vẫn nhận đường thật
    assert [Path(path).name for path in local["paths"]] == ["645.txt", "646.txt"] and str(story) in local["paths"][0]

    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": plan["paths"]})
    scan = json.loads(data)
    assert status == 200 and [row["name"] for row in scan["files"]] == ["645.txt", "646.txt"]
    assert _leaks(data, [str(story), str(tmp_path)]) == [] and all(remote_sources.parse(row["path"]) for row in scan["files"])
    status, data, _ = _sync_request(port, "POST", "/api/first-person", headers=cookie, body={"paths": [row["path"] for row in scan["files"]]})
    assert status == 200 and _leaks(data, [str(tmp_path)]) == []

    body = {"paths": [row["path"] for row in scan["files"]], "title": "Cuốn chưa chạy", "profile": "fast", "narrator": "", "firstPerson": "",
            "redoOf": old_id}
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body=body)
    assert status == 201, data
    made = json.loads(data)
    assert _leaks(data, [str(tmp_path)]) == []
    new = app.library.resolve(made["id"])
    assert [path.name for path in continuation._input_paths(new)] == ["645.txt", "646.txt"]
    assert store.read_settings(new)["quality_profile"] == "fast"
    assert new != old and app.library.resolve(old_id) is None, "cuốn cũ vào Thùng rác"


def test_a_remote_redo_matches_the_desktop_redo(studio, tmp_path: Path) -> None:
    """Cùng cuốn, cùng thiết lập: làm lại từ xa và làm lại ở máy tính ra cùng chương nguồn và cùng thiết lập."""
    app, old, cookie, story = _redo_world(studio, tmp_path)
    port = app.sync_server.port
    old_id = book_id(old)
    local_plan = app.redo(old_id)
    desktop = app.create({"paths": local_plan["paths"], "title": "Bản làm lại ở máy tính", "profile": "fast", "narrator": "",
                          "firstPerson": "", "replaces": old_id})
    desktop_settings = store.read_settings(app.library.resolve(desktop["id"]))
    status, data, _ = _sync_request(port, "GET", f"/api/books/{desktop['id']}/redo", headers=cookie)
    remote_plan = json.loads(data)
    assert status == 200
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={
        "paths": remote_plan["paths"], "title": "Bản làm lại từ xa", "profile": "fast", "narrator": "", "firstPerson": "", "redoOf": desktop["id"]})
    assert status == 201, data
    remote = app.library.resolve(json.loads(data)["id"])
    assert [path.name for path in continuation._input_paths(remote)] == [Path(path).name for path in local_plan["paths"]]
    remote_settings = store.read_settings(remote)
    for key in ("quality_profile", "voices", "text", "analysis"):
        assert remote_settings.get(key) == desktop_settings.get(key), key


def test_a_remote_redo_refuses_a_reference_that_no_longer_matches_and_a_bare_replace(studio, tmp_path: Path) -> None:
    app, old, cookie, story = _redo_world(studio, tmp_path)
    port = app.sync_server.port
    old_id = book_id(old)
    ref = remote_sources.make("redo", old_id, 0, story / "646.txt")  # đúng chỗ 0 nhưng sai tên: thư mục đã đổi
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [ref]})
    assert status == 409 and "mở lại trang" in json.loads(data)["error"]
    out_of_range = remote_sources.make("redo", old_id, 9, story / "645.txt")
    status, _data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [out_of_range]})
    assert status == 409
    status, _data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": ["ref:redo:khong-co-sach:0:a.txt"]})
    assert status == 404
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={
        "paths": [remote_sources.make("redo", old_id, 0, story / "645.txt")], "title": "x", "replaces": old_id})
    assert status == 403, "thiết bị ở xa không thay cuốn tuỳ ý: chỉ qua redoOf"
    assert old.exists()


def test_an_uploaded_source_still_comes_back_with_its_folder(studio) -> None:
    """Nguồn do chính thiết bị gửi lên là thứ duy nhất thiết bị phải cầm đường dẫn: gửi lại để quét và tạo sách."""
    app, _project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "Truyện", "name": "001.txt", "data": base64.b64encode("Chương 1\n\nTrời sáng.".encode()).decode()})
    uploaded = json.loads(data)
    assert status == 200 and is_local_path(uploaded["folder"]) and is_local_path(uploaded["path"])
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [uploaded["folder"]]})
    assert status == 200 and len(json.loads(data)["files"]) == 1


def test_a_loose_uploaded_file_names_the_book_after_the_file_not_the_random_batch_folder(tmp_path: Path) -> None:
    from abook.webui import actions

    batch = tmp_path / actions.UPLOAD_FOLDER / "20261015-1030-tzli"
    batch.mkdir(parents=True)
    one = batch / "Mùa mưa.txt"
    one.write_text("x", encoding="utf-8")
    assert actions._loose_upload_title([one]) == "Mùa mưa"
    parts = [batch / "Mùa mưa 1.txt", batch / "Mùa mưa 2.txt"]
    for part in parts:
        part.write_text("x", encoding="utf-8")
    assert actions._loose_upload_title(parts) == "Mùa mưa", "phần chung của tên, bỏ số thứ tự ở đuôi"
    unrelated = [batch / "a.txt", batch / "b.txt"]
    for part in unrelated:
        part.write_text("x", encoding="utf-8")
    assert actions._loose_upload_title(unrelated) == "", "không có phần chung: để trống cho người dùng tự đặt, không lấy 'tzli'"
    elsewhere = tmp_path / "Truyện" / "001.txt"
    elsewhere.parent.mkdir()
    elsewhere.write_text("x", encoding="utf-8")
    assert actions._loose_upload_title([elsewhere]) is None, "nguồn không phải tải lên: infer_book_title lo như cũ"
    assert actions._loose_upload_title([]) is None
