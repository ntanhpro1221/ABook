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
from tests.test_webui_listen_and_sync import _request, _sync_request

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


def _upload(port: int, cookie: dict[str, str], folder: str, name: str, text: str) -> dict[str, str]:
    status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": folder, "name": name, "data": base64.b64encode(text.encode()).decode()})
    assert status == 200, data
    return {"raw": data, **json.loads(data)}


def test_an_uploaded_source_comes_back_as_a_reference_that_scans_and_creates(studio) -> None:
    """Nguồn do chính thiết bị gửi lên: nó cầm `up:...` (không đường dẫn nào của máy tính) và gửi lại đúng chuỗi ấy để quét, tạo sách."""
    app, _project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    uploaded = _upload(port, cookie, "Truyện", "001.txt", "Chương 1\n\nTrời sáng.")
    assert uploaded["folder"] == "up:Truyện" and uploaded["path"] == "up:Truyện/001.txt"
    assert not is_local_path(uploaded["folder"]) and not is_local_path(uploaded["path"])
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [uploaded["folder"]]})
    assert status == 200 and len(json.loads(data)["files"]) == 1
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={"paths": [uploaded["folder"]], "title": "Từ tải lên"})
    assert status == 201, data
    assert [path.name for path in continuation._input_paths(app.library.resolve(json.loads(data)["id"]))] == ["001.txt"]
    # Cửa sổ app trên chính máy tính vẫn nhận đường thật, y như trước.
    local = {"X-Ebook-Token": "phien", "Host": f"127.0.0.1:{app.local_port}"}
    status, data, _ = _request(app.local_port, "POST", "/api/sources/upload", headers=local, body={
        "folder": "Lần gửi d5", "name": "1.txt", "data": base64.b64encode(b"Chuong 1").decode()})
    assert status == 200 and is_local_path(json.loads(data)["folder"]) and is_local_path(json.loads(data)["path"])


def test_an_upload_reference_round_trips_and_one_parser_refuses_every_escape(tmp_path: Path) -> None:
    uploads = tmp_path / "Nguồn tải lên"
    token = remote_sources.make_upload(uploads / "Lần gửi" / "Tập 1" / "01 Mở đầu.txt", uploads)
    assert token == "up:Lần gửi/Tập 1/01 Mở đầu.txt"
    assert remote_sources.parse(token) == ("up", "", 0, "Lần gửi/Tập 1/01 Mở đầu.txt")
    assert remote_sources.upload_path("Lần gửi/Tập 1", uploads) == uploads / "Lần gửi" / "Tập 1"
    assert remote_sources.make_upload(tmp_path / "ngoai.txt", uploads) is None and remote_sources.make_upload(uploads, uploads) is None
    assert remote_sources.parse("ref:redo:abc:0:a.txt")[0] == "redo", "một bộ phân tích cho cả hai kiểu tham chiếu"
    for bad in ("up:", "up:..", "up:../x", "up:a/../x", "up:/x", "up:C:/x", "up:a\\b", "up:\\\\may\\share", "up://may/share", "up:a//b", "up:a/CON",
                "up:a/nul.txt", "up:a/b.", "up:a/b ", "up:a/b:c", "up:a/b*", "up:a/\x00", "C:\\x", "up"):
        assert remote_sources.parse(bad) is None, bad


def test_no_remote_post_answers_with_an_absolute_path(studio, tmp_path: Path) -> None:
    """Đi qua cả chuỗi upload -> quét (thư mục có thư mục con, nhiều tập, file cả truyện) -> tách chương -> hỏi ngôi kể -> tạo sách:
    lời đáp nào cũng không mang đường dẫn Windows tuyệt đối hay thư mục thư viện / dự án / thư mục tạm của máy tính (soát a34)."""
    app, project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    library = Path(app.preferences.get()["libraryRoot"])
    private = [str(library), str(project), str(tmp_path), "Users", "AppData"]
    seen: list[str] = []

    def post(route: str, body: dict[str, Any], expect: int = 200) -> Any:
        status, data, _ = _sync_request(port, "POST", route, headers=cookie, body=body)
        assert status == expect, (route, status, data)
        assert _leaks(data, private) == [], (route, _leaks(data, private))
        seen.append(route)
        return json.loads(data)

    for volume in ("Tập 1", "Tập 2"):
        for number in (1, 2):
            sent = _upload(port, cookie, f"Lần gửi a1/Bộ truyện/{volume}", f"{number:02d}.txt", f"Chương {number}\n\nTôi đi tiếp.")
            assert _leaks(sent["raw"], private) == []
    whole = _upload(port, cookie, "Cả truyện", "tron bo.txt", "Chương 1\n\nTrời sáng.\n\nChương 2\n\nTrời tối.\n")
    assert _leaks(whole["raw"], private) == []

    # Thư mục chỉ có thư mục con: gợi ý các thư mục con (mỗi cái một tham chiếu), không có file nào.
    parent = post("/api/scan", {"paths": ["up:Lần gửi a1/Bộ truyện"]})
    assert parent["files"] == [] and parent["subfolders"] == ["up:Lần gửi a1/Bộ truyện/Tập 1", "up:Lần gửi a1/Bộ truyện/Tập 2"]
    # "Dùng cả các thư mục": hai tập -> đề xuất chia tập mang thứ tự và điểm bắt đầu cũng là tham chiếu.
    both = post("/api/scan", {"paths": parent["subfolders"]})
    assert len(both["files"]) == 4 and all(remote_sources.parse(row["path"]) for row in both["files"])
    proposal = both["volumes"]
    assert proposal and all(remote_sources.parse(item) for item in proposal["order"])
    assert all(remote_sources.parse(volume["startPath"]) for volume in proposal["volumes"])
    # Mọi tham chiếu trong lời đáp đều là chính chuỗi quét lại được.
    post("/api/scan", {"paths": [row["path"] for row in both["files"]]})
    post("/api/first-person", {"paths": [row["path"] for row in both["files"]]})
    # File ghi nhầm / không có: nói tên tham chiếu thiết bị đã gửi, không phải đường thật.
    gone = post("/api/scan", {"paths": ["up:Lần gửi a1/khong-co"]})
    assert gone["files"] == [] and gone["missing"] == ["up:Lần gửi a1/khong-co"]
    # File cả truyện: đề xuất tách rồi quét thư mục chương.
    scan = post("/api/scan", {"paths": [whole["path"]]})
    assert scan["files"][0]["path"] == whole["path"] and scan["files"][0]["split"]["chapters"] == 2
    split = post("/api/sources/split", {"path": whole["path"]})
    assert remote_sources.parse(split["folder"]) and len(post("/api/scan", {"paths": [split["folder"]]})["files"]) == 2
    made = post("/api/books", {"paths": [row["path"] for row in both["files"]], "title": "Bộ truyện", "profile": "fast", "narrator": "",
                               "firstPerson": ""}, expect=201)
    assert sorted(path.name for path in continuation._input_paths(app.library.resolve(made["id"]))) == ["01.txt", "01.txt", "02.txt", "02.txt"]
    assert len(seen) >= 8


def test_a_remote_epub_is_unpacked_inside_the_upload_folder_so_its_chapters_can_be_sent_back(studio, tmp_path: Path) -> None:
    from tests.test_epub_import import _epub

    app, _project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    epub = _epub(tmp_path / "truyen.epub")
    sent = _upload(port, cookie, "Lần gửi e1", "truyen.epub", "")
    assert sent["path"] == "up:Lần gửi e1/truyen.epub"
    (Path(app.preferences.get()["libraryRoot"]) / "Nguồn tải lên" / "Lần gửi e1" / "truyen.epub").write_bytes(epub.read_bytes())
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [sent["path"]]})
    scan = json.loads(data)
    assert status == 200 and len(scan["files"]) == 2 and scan["errors"] == [], data
    assert _leaks(data, [str(tmp_path), str(Path(app.preferences.get()["libraryRoot"]))]) == []
    assert all(remote_sources.parse(row["path"]) for row in scan["files"])
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={"paths": [row["path"] for row in scan["files"]], "title": "EPUB từ xa"})
    assert status == 201, data


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
