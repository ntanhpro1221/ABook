"""Soát a68 (hai máy): chỗ nghe máy kia gửi mà vượt độ dài chương bị bỏ (lỗi 2), giọng riêng của cuốn đi theo hồ sơ nghe - bên chọn sau thắng
(lỗi 8), chỗ nghe mới hơn thắng khi điện thoại nối lại (lỗi 9), cỡ + "đang làm" trong danh sách sách (lỗi 7, 13), đổi tên thiết bị (lỗi 16)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from abook.webui import export
from abook.webui.listening import Listening, merge_states
from abook.webui.sync import Devices, SyncApp, SyncServer, trusted_state
from tests.test_webui_listen_and_sync import _sync_request, library  # noqa: F401 - fixture dùng chung


def test_a_place_beyond_the_chapter_is_dropped_but_text_chapters_are_not_judged() -> None:
    state = {"last": {"chapterId": 1, "seconds": 812.4, "at": 5.0},
             "chapters": {"1": {"heard": 812.4, "at": 5.0}, "2": {"heard": 3.0, "at": 5.0}, "7": {"heard": 900.0, "at": 5.0}},
             "rate": 1.25}
    kept = trusted_state(state, {1: 9.7, 2: 30.0})
    assert "last" not in kept, "đồng hồ của cuốn khác không thành chỗ nghe của cuốn này"
    assert set(kept["chapters"]) == {"2", "7"}, "chương không có độ dài thật (chỉ chữ) không xét"
    assert kept["rate"] == 1.25
    assert trusted_state({"last": {"chapterId": 1, "seconds": 11.0, "at": 5.0}}, {1: 9.7})["last"]["seconds"] == 11.0, "lệch vài giây vẫn nhận"


def test_the_book_voice_travels_with_the_listening_record_and_the_later_choice_wins(tmp_path: Path) -> None:
    listening = Listening(tmp_path / "listening.json")
    listening.set_voice("b", "vieneu:Ái Hân")
    listening.set_voice("b", "edge:vi-VN-NamMinhNeural")
    computer = listening.get("b")
    assert computer["voice"] == "edge:vi-VN-NamMinhNeural" and computer["voiceAt"] > 0
    revision = computer["_fieldRevs"]["voice"]
    older = {"chapters": {}, "bookmarks": [], "voice": "vieneu:Ái Hân", "voiceAt": computer["voiceAt"] - 60,
             "_fieldRevs": {"voice": {**revision, "counter": revision["counter"] - 1}}}
    newer = {**older, "voiceAt": computer["voiceAt"] + 60,
             "_fieldRevs": {"voice": {**revision, "counter": revision["counter"] + 1}}}
    assert merge_states(computer, older)["voice"] == "edge:vi-VN-NamMinhNeural"
    assert merge_states(computer, newer)["voice"] == "vieneu:Ái Hân"


def test_a_place_heard_offline_wins_when_the_phone_comes_back(tmp_path: Path) -> None:
    now = time.time()
    computer = {"last": {"chapterId": 726, "seconds": 691.0, "at": now - 600, "rev": {"counter": 1, "node": "computer"}}, "chapters": {}, "bookmarks": []}
    phone = {"last": {"chapterId": 727, "seconds": 17.0, "at": now - 60, "rev": {"counter": 2, "node": "phone"}}, "chapters": {}, "bookmarks": []}
    assert merge_states(computer, phone)["last"]["chapterId"] == 727
    assert merge_states(phone, computer)["last"]["chapterId"] == 727, "máy tính không kéo điện thoại về chỗ cũ"


def test_the_size_before_download_counts_the_background_music_too() -> None:
    """Soát lại uxfix75: lo18 ghi "63 MB" cạnh nút Tải mà thanh tiến độ chạy tới 119 MB - nhạc nền đi kèm cũng là phần tải về."""
    from abook.webui.package_share import download_bytes

    book = {"chapters": [{"available": True, "size": 1000}, {"available": False, "size": 500}, {"available": True, "size": 24}],
            "music": {"tracks": {"music/a.mp3": {"size": 300}, "music/b.mp3": {"size": 7}}}}
    assert download_bytes(book) == 1331, "cùng phép tính DownloadSpace.bookBytes của điện thoại"
    assert download_bytes({"chapters": []}) == 0


def test_renaming_a_paired_device(tmp_path: Path) -> None:
    devices = Devices(tmp_path / "devices.json")
    code = devices.start_pairing()["code"]
    devices.pair(code, "Google sdk_gphone64_x86_64")
    device = devices.list()[0]
    assert devices.rename(device["id"], "  Điện thoại   của Mai ")
    assert devices.list()[0]["name"] == "Điện thoại của Mai"
    assert not devices.rename(device["id"], "   "), "tên rỗng bị từ chối"
    assert Devices(tmp_path / "devices.json").list()[0]["name"] == "Điện thoại của Mai", "tên mới lưu ra đĩa"


def test_over_the_wire_the_phone_renames_itself_and_a_foreign_place_is_refused(library, tmp_path: Path) -> None:  # noqa: F811
    lib, project, listening = library
    devices = Devices(tmp_path / "devices.json")
    server = SyncServer(SyncApp(lib, listening, devices, "Máy thử"), host="127.0.0.1", port=0).start()
    try:
        code = devices.start_pairing()["code"]
        _status, data, _ = _sync_request(server.port, "POST", "/sync/v1/pair", body={"code": code, "device": "Google sdk_gphone64_x86_64"})
        token = json.loads(data)["token"]
        status, _data, _ = _sync_request(server.port, "POST", "/sync/v1/name", token, body={"name": "Điện thoại Google (máy ảo)"})
        assert status == 200 and devices.list()[0]["name"] == "Điện thoại Google (máy ảo)"

        _status, data, _ = _sync_request(server.port, "GET", "/sync/v1/library", token)
        book = json.loads(data)["books"][0]
        # Điện thoại tải cả kịch bản, dàn nhân vật, câu mẫu, bìa (manifest) - cỡ báo trước là audio + phần ấy (soát a99 T1).
        extras = export.packed_extras_bytes(project, [chapter["id"] for chapter in export._listenable(project)])
        assert extras > 0 and book["bytes"] == 3 + 256 * 40 + extras, "cỡ khi tải về, trước khi bấm Tải"
        assert book["producing"] is False, "không chạy Studio thì không phải đang làm, dù cuốn chưa xong"

        identifier = book["id"]
        foreign = {"last": {"chapterId": 1, "seconds": 812.4, "at": time.time(), "rev": {"counter": 1, "node": "phone"}}, "chapters": {}, "bookmarks": []}
        status, _data, _ = _sync_request(server.port, "POST", f"/sync/v1/books/{identifier}/state", token, body=foreign)
        assert status == 200 and "last" not in listening.get(identifier), "chỗ nghe vượt độ dài chương không vào hồ sơ"
        good = {"last": {"chapterId": 1, "seconds": 5.0, "at": time.time(), "rev": {"counter": 2, "node": "phone"}}, "chapters": {}, "bookmarks": []}
        _sync_request(server.port, "POST", f"/sync/v1/books/{identifier}/state", token, body=good)
        assert listening.get(identifier)["last"]["seconds"] == 5.0
    finally:
        server.stop()


def test_a_refused_body_does_not_spill_into_the_next_request(library, tmp_path: Path) -> None:  # noqa: F811
    """Soát lại uxfix75: máy tính đã thôi ghép, điện thoại gửi chỗ nghe (có thân) rồi hỏi danh sách trên CÙNG kết nối giữ sống - thân chưa
    đọc bị hiểu là dòng lệnh, lời đáp 501 làm điện thoại báo "máy tính đang tắt" thay vì "đã thôi ghép"."""
    import socket
    import ssl

    lib, _project, listening = library
    server = SyncServer(SyncApp(lib, listening, Devices(tmp_path / "devices.json"), "Máy thử"), host="127.0.0.1", port=0).start()
    try:
        body = json.dumps({"last": {"chapterId": 1, "seconds": 3.0, "at": time.time()}}).encode()
        requests = (b"POST /sync/v1/books/x/state HTTP/1.1\r\nHost: a\r\nAuthorization: Bearer cu\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode() + body
                    + b"GET /sync/v1/library HTTP/1.1\r\nHost: a\r\nAuthorization: Bearer cu\r\n\r\n")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as raw, context.wrap_socket(raw) as sock:
            sock.sendall(requests)
            answer = b""
            while chunk := sock.recv(65536):
                answer += chunk
        assert answer.startswith(b"HTTP/1.1 401"), answer[:80]
        # Không có lời đáp thứ hai: thân chưa đọc không bị hiểu thành một yêu cầu (lời đáp 400/501); kết nối đóng, điện thoại nối kết nối mới.
        assert answer.count(b"HTTP/1.1 ") == 1, answer.decode("utf-8", "replace")
    finally:
        server.stop()


def test_the_computer_knows_a_book_it_imported_from_a_file_that_the_phone_is_playing(tmp_path: Path) -> None:
    """Soát a68 lỗi 6: cuốn nhập từ file trên máy tính, điện thoại đang nghe thẳng - thanh điện thoại ở máy tính phải biết cuốn ấy ("Nghe trên
    máy này", bìa), không chỉ dự án Studio."""
    import shutil

    from abook.webui import packages
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App
    from tests import book_edits_fixtures as shared

    root = tmp_path / "thu_vien"
    folder = root / packages.IMPORTED_FOLDER / "base"
    shutil.copytree(shared.BASE, folder)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "listening.json"))
    app.sync_host, app.sync_port = "127.0.0.1", 0
    app.set_sync(True)
    try:
        code = app.devices.start_pairing()["code"]
        _status, data, _ = _sync_request(app.sync_server.port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
        token = json.loads(data)["token"]
        identifier = book_id(folder.resolve())
        report = {"state": {"bookId": identifier, "bookTitle": "Sách thử", "chapterId": 1, "chapterTitle": "Chương 1", "position": 3.0,
                            "duration": 9.0, "playing": False, "rate": 1.0}, "books": [], "wait": 0}
        status, _data, _ = _sync_request(app.sync_server.port, "POST", "/sync/v1/remote", token, body=report)
        assert status == 200
        (phone,) = app.remote_view()["phones"]
        assert phone["known"], "cuốn nhập từ file cũng là cuốn của máy này"
    finally:
        app.close()
