"""Soát bảo mật máy chủ cục bộ a109: bìa mang url(...), junction trong "Nguồn tải lên", cổng audio Cast không trần."""
from __future__ import annotations

import base64
import http.client
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from abook.webui import actions, bookfile, covers, packages, remote_sources
from abook.webui.cast import CastMedia
from abook.webui.fingerprints import Fingerprints
from tests.test_remote_studio import studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import library  # noqa: F401
from tests.test_remote_studio_paths import _cookie_with_studio, _upload
from tests.test_webui_listen_and_sync import _sync_request

TRACKER = "url(https://tracker.invalid/a109-reader-unique)"

# ---- F1: màu bìa chỉ là #rrggbb ----------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [TRACKER, "red", "#abc", "#GGGGGG", "#aabbccdd", "#aabbcc;background:url(x)", "", None, 7, {"a": 1}])
def test_cover_colour_keeps_only_a_plain_hex_colour(bad) -> None:
    assert covers.clean_color(bad) == ""


def test_cover_colour_accepts_what_the_cover_editor_accepts() -> None:
    assert covers.clean_color("#a1b2c3") == "#a1b2c3" and covers.clean_color(" #A1B2C3 ") == "#a1b2c3"


def _book_with_cover_colour(tmp_path: Path, colour: str) -> Path:
    from PIL import Image

    book = {"title": "Sách giả kiểm riêng tư", "chaptersTotal": 1, "chaptersAvailable": 0, "duration": 0, "complete": True,
            "chapters": [{"id": 1, "index": 1, "title": "Một", "file": None, "text": "texts/1.txt", "duration": 0, "available": True}],
            "cover": {"file": "cover.jpg", "color": colour, "width": 1, "height": 1}, "samples": []}
    jpeg = io.BytesIO()
    Image.new("RGB", (1, 1), (10, 20, 30)).save(jpeg, format="JPEG")
    archive = bookfile.seal(book, {"texts/1.txt": "Truyện kiểm thử.".encode(), "cover.jpg": jpeg.getvalue()}, tmp_path / "tracking.abook",
                            producer="a109", version=5)
    with bookfile.BookFile(archive) as opened:
        opened.verify()
        folder, _how = packages.import_opened(opened, tmp_path / "library", [], Fingerprints(tmp_path / "fingerprints.json"))
    return folder


def test_an_imported_book_never_keeps_a_tracking_background_as_its_cover_colour(tmp_path: Path) -> None:
    folder = _book_with_cover_colour(tmp_path, TRACKER)
    assert TRACKER not in (folder / covers.META_FILE).read_text(encoding="utf-8")
    assert covers.cover_view(folder, "testbook")["color"] == ""


def test_an_imported_book_keeps_a_genuine_cover_colour(tmp_path: Path) -> None:
    folder = _book_with_cover_colour(tmp_path, "#0a141e")
    assert covers.cover_view(folder, "testbook")["color"] == "#0a141e"


def test_the_view_filters_a_colour_that_an_older_cover_file_already_carries(tmp_path: Path) -> None:
    (tmp_path / covers.COVER_FILE).write_bytes(b"x")
    (tmp_path / covers.META_FILE).write_text(json.dumps({"color": TRACKER, "width": 1, "height": 1}), encoding="utf-8")
    assert covers.cover_view(tmp_path, "b")["color"] == ""


# ---- F2: junction trong "Nguồn tải lên" -------------------------------------------------------------------------


def _junction(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


@pytest.fixture()
def linked(tmp_path: Path):
    """Thư viện có `Nguồn tải lên/linked` là junction tới một thư mục riêng NGOÀI thư viện."""
    library = tmp_path / "library"
    outside = tmp_path / "ngoai"
    (library / actions.UPLOAD_FOLDER).mkdir(parents=True)
    outside.mkdir()
    (outside / "private.txt").write_text("A109 PRIVATE OUTSIDE DATA", encoding="utf-8")
    _junction(library / actions.UPLOAD_FOLDER / "linked", outside)
    return library, outside


def test_an_upload_through_a_junction_is_refused_and_writes_nothing_outside(linked) -> None:
    library, outside = linked
    with pytest.raises(ValueError, match="ngoài thư viện"):
        actions.upload_source(library, "linked", "injected.txt", b"x")
    with pytest.raises(ValueError, match="ngoài thư viện"):
        actions.upload_source(library, "linked/sau/hon", "injected.txt", b"x")
    assert sorted(path.name for path in outside.iterdir()) == ["private.txt"], "không file, không thư mục con, không .part"


def test_an_upload_into_an_ordinary_folder_still_works(linked) -> None:
    library, _outside = linked
    target = actions.upload_source(library, "Truyện", "001.txt", b"Chuong 1")
    assert target.read_bytes() == b"Chuong 1" and target.parent.parent == library / actions.UPLOAD_FOLDER


def test_a_reference_through_a_junction_is_refused_before_any_read(linked) -> None:
    library, outside = linked
    uploads = library / actions.UPLOAD_FOLDER
    for relative in ("linked/private.txt", "linked", "linked/sau/hon.txt"):
        with pytest.raises(actions.UploadEscape, match="ngoài thư viện"):
            remote_sources.upload_path(relative, uploads)
    assert remote_sources.upload_path("Truyện/001.txt", uploads) == uploads.resolve() / "Truyện" / "001.txt"


def test_an_uploads_folder_that_is_itself_a_junction_out_of_the_library_is_refused(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    outside = tmp_path / "ngoai"
    outside.mkdir()
    _junction(library / actions.UPLOAD_FOLDER, outside)
    with pytest.raises(ValueError, match="ngoài thư viện"):
        actions.upload_source(library, "Truyện", "001.txt", b"x")
    assert list(outside.iterdir()) == []


def test_a_sibling_whose_name_starts_like_the_uploads_folder_is_not_inside_it(tmp_path: Path) -> None:
    """So theo thành phần, không theo tiền tố chuỗi: `Nguồn tải lên 2` không nằm trong `Nguồn tải lên`."""
    library = tmp_path / "library"
    uploads = library / actions.UPLOAD_FOLDER
    sibling = library / (actions.UPLOAD_FOLDER + " 2")
    uploads.mkdir(parents=True)
    sibling.mkdir()
    (sibling / "x.txt").write_text("x", encoding="utf-8")
    _junction(uploads / "gan", sibling)
    with pytest.raises(actions.UploadEscape):
        remote_sources.upload_path("gan/x.txt", uploads)


def test_http_upload_scan_and_create_refuse_a_junction_with_a_clear_reason(studio, linked) -> None:
    app, _project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    library, outside = linked
    app.preferences.update({"libraryRoot": str(library)})
    status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "linked", "name": "injected.txt", "data": base64.b64encode(b"x").decode()})
    assert status in (400, 403) and "ngoài thư viện" in json.loads(data)["error"]
    assert not (outside / "injected.txt").exists()
    for route, body in (("/api/scan", {"paths": ["up:linked/private.txt"]}), ("/api/scan", {"paths": ["up:linked"]}),
                        ("/api/books", {"paths": ["up:linked"], "title": "x"}),
                        ("/api/sources/split", {"path": "up:linked/private.txt", "title": "x"})):
        status, data, _ = _sync_request(port, "POST", route, headers=cookie, body=body)
        assert status == 403 and "ngoài thư viện" in json.loads(data)["error"], (route, status, data)
        assert "A109 PRIVATE" not in data.decode("utf-8")
    uploaded = _upload(port, cookie, "Truyện", "001.txt", "Chương 1\n\nTrời sáng.")
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [uploaded["folder"]]})
    assert status == 200 and len(json.loads(data)["files"]) == 1


def test_a_junction_among_the_files_of_a_scanned_upload_folder_is_refused(studio, linked) -> None:
    """Thư mục tải lên hợp lệ nhưng có một liên kết con trỏ ra ngoài: cả lần quét bị từ chối, không đọc file ngoài."""
    app, _project = studio
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    library, outside = linked
    app.preferences.update({"libraryRoot": str(library)})
    uploaded = _upload(port, cookie, "Truyện", "001.txt", "Chương 1\n\nTrời sáng.")
    _junction(library / actions.UPLOAD_FOLDER / "Truyện" / "kèm", outside)
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [uploaded["folder"]]})
    assert status == 403 and "ngoài thư viện" in json.loads(data)["error"], (status, data)


# ---- F3: cổng audio Cast ----------------------------------------------------------------------------------------


def _hang(port: int) -> socket.socket:
    client = socket.create_connection(("127.0.0.1", port), timeout=3)
    client.sendall(b"GET /c/no-token HTTP/1.1\r\nHost: x\r\nX-Hold: ")
    return client


def _closed(client: socket.socket, seconds: float) -> bool:
    """Máy chủ đã đóng socket này (đọc ra EOF / bị reset) trong `seconds`?"""
    client.settimeout(seconds)
    try:
        return client.recv(1) == b""
    except socket.timeout:
        return False
    except OSError:
        return True


def test_cast_budget_counts_and_releases(tmp_path: Path) -> None:
    from abook.webui.cast import ConnectionBudget

    budget = ConnectionBudget(total=3, per_ip=2)
    assert budget.take("a") and budget.take("a") and not budget.take("a"), "mỗi IP tối đa 2"
    assert budget.take("b") and not budget.take("c"), "cả cổng tối đa 3"
    budget.release("a")
    assert budget.take("c")
    for who in ("a", "b", "c", "a"):
        budget.release(who)
    assert budget.take("a") and budget.take("a"), "giải phóng hết thì đếm lại từ đầu"
    budget.release("a")
    budget.release("a")
    budget.release("a")  # thừa một lần: không âm


def test_cast_port_closes_hanging_sockets_over_the_cap_and_still_serves(tmp_path: Path) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3-a109")
    media = CastMedia(host="127.0.0.1")
    held: list[socket.socket] = []
    try:
        url = media.share(audio, "127.0.0.1")
        port = media._server.server_port
        cap = media._server.budget.per_ip
        for _ in range(cap):
            held.append(_hang(port))
        extra = _hang(port)
        held.append(extra)
        assert _closed(extra, 3), "kết nối thứ cap+1 từ cùng IP phải bị đóng ngay, không được giữ worker"
        time.sleep(0.2)
        assert not any(_closed(client, 0.05) for client in held[:cap]), "các kết nối trong trần chưa bị cắt trước deadline"
        # Vượt deadline: socket treo bị cắt, slot trả lại, request hợp lệ chạy.
        assert all(_closed(client, media._server.header_deadline + 3) for client in held[:cap])
        deadline = time.time() + 2  # worker vừa đóng socket cần một nhịp để trả slot
        while media._server.budget._held and time.time() < deadline:
            time.sleep(0.05)
        assert not media._server.budget._held, "mọi slot đã được trả sau khi socket treo bị cắt"
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        c.request("GET", urlsplit(url).path)
        r = c.getresponse()
        assert r.status == 200 and r.read() == b"ID3-a109"
        c.close()
    finally:
        for client in held:
            client.close()
        media.close()


def test_cast_slow_header_trickle_is_cut_at_the_total_deadline(tmp_path: Path) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3-a109")
    media = CastMedia(host="127.0.0.1")
    try:
        media.share(audio, "127.0.0.1")
        server = media._server
        server.header_deadline = 1.0
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
        started = time.time()
        cut = False
        while time.time() - started < 6:
            try:
                client.sendall(b"X")  # mỗi byte một lần, chưa bao giờ xong header
            except OSError:
                cut = True
                break
            if _closed(client, 0.2):
                cut = True
                break
        assert cut and time.time() - started < 4, "đọc từng byte chậm không giữ worker mãi: cắt theo deadline TỔNG, không theo từng lần đọc"
        client.close()
    finally:
        media.close()


def test_cast_good_token_streams_a_long_chapter_past_the_header_deadline(tmp_path: Path) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3" + b"\0" * (3 * 1024 * 1024))
    media = CastMedia(host="127.0.0.1")
    try:
        url = media.share(audio, "127.0.0.1")
        server = media._server
        server.header_deadline = 0.5
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=5)
        client.sendall(f"GET {urlsplit(url).path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
        time.sleep(1.0)  # đã qua deadline header; đã có token đúng thì stream không bị cắt
        total = b""
        while chunk := client.recv(1 << 20):
            total += chunk
        client.close()
        assert total.startswith(b"HTTP/1.") and len(total) > 3 * 1024 * 1024
    finally:
        media.close()


def test_threads_do_not_pile_up_for_hanging_sockets(tmp_path: Path) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3-a109")
    media = CastMedia(host="127.0.0.1")
    held: list[socket.socket] = []
    try:
        media.share(audio, "127.0.0.1")
        port = media._server.server_port
        before = threading.active_count()
        held = [_hang(port) for _ in range(40)]
        time.sleep(0.5)
        assert threading.active_count() - before <= media._server.budget.total + 2
    finally:
        for client in held:
            client.close()
        media.close()
