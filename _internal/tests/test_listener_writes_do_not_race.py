"""Ghi đồng thời không mất câu (soát UX a32, lỗi 9): ba lần POST /speaker cách nhau chưa tới 20 ms từng làm mất 2-3 câu mà vẫn
trả 200, vì `overrides.json` và `aliases.json` được đọc-sửa-ghi không khoá trong một máy chủ nhiều luồng. Mỗi dự án có một khoá
ghi (`io_utils.project_write_lock`), giữ quanh cả lần đọc-sửa-ghi của mọi đường ghi yêu cầu của người nghe."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from abook import aliases
from abook.listener_overrides import overrides_path, read_overrides, speaker_requests
from tests.test_minor_speaker_groups import make_book

LINES = ["b", "d", "e", "g", "h"]  # năm câu thoại khác nhau của cùng một sách
ROUNDS = 6


@pytest.fixture
def studio(tmp_path: Path):
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(project: Path, body: dict) -> int:
        from abook.webui.library import book_id

        status, _data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/speaker",
                                    headers={"X-Ebook-Token": "t"}, body=body)
        return status

    try:
        yield post
    finally:
        server.stop()


def _together(actions: list) -> None:
    """Chạy các việc cùng một lúc (rào chắn), đợi xong hết."""
    barrier = threading.Barrier(len(actions))
    errors: list[BaseException] = []

    def run(action) -> None:
        try:
            barrier.wait()
            action()
        except BaseException as error:  # noqa: BLE001 - đưa về luồng chính
            errors.append(error)

    threads = [threading.Thread(target=run, args=(action,)) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors


def test_simultaneous_answers_all_land(tmp_path: Path, studio) -> None:
    project = make_book(tmp_path)
    for _round in range(ROUNDS):
        if overrides_path(project).exists():
            os.remove(overrides_path(project))
        statuses: dict[str, int] = {}

        def answer(stable_id: str, into: dict[str, int] = statuses) -> None:
            into[stable_id] = studio(project, {"lines": [{"stableId": stable_id, "textSha256": f"sha-{stable_id}"}], "speaker": "RHINE"})

        _together([lambda stable_id=stable_id: answer(stable_id) for stable_id in LINES])
        assert set(statuses.values()) == {200}
        assert sorted(entry["stable_id"] for entry in speaker_requests(read_overrides(project))) == sorted(LINES), \
            "câu nào được trả 200 thì phải còn trong overrides.json"


def test_simultaneous_name_cards_keep_every_alias(tmp_path: Path, studio) -> None:
    project = make_book(tmp_path)
    names = ["Tên một", "Tên hai", "Tên ba", "Tên bốn", "Tên năm"]
    for _round in range(ROUNDS):
        for path in (overrides_path(project), project / aliases.FILE_NAME):
            if path.exists():
                os.remove(path)

        def merge(stable_id: str, name: str) -> None:
            assert studio(project, {"lines": [{"stableId": stable_id, "textSha256": f"sha-{stable_id}"}], "speaker": "RHINE",
                                    "alias": name}) == 200

        _together([lambda stable_id=stable_id, name=name: merge(stable_id, name) for stable_id, name in zip(LINES, names)])
        saved = json.loads((project / aliases.FILE_NAME).read_text(encoding="utf-8"))["aliases"]
        assert sorted(entry["alias"] for entry in saved) == sorted(names)
        assert len(speaker_requests(read_overrides(project))) == len(LINES)


def test_a_waiting_merge_can_be_taken_back_from_the_cast_line(tmp_path: Path) -> None:
    """"Bỏ gộp" ở dòng "Chờ áp dụng: gộp vào X": tìm lần gộp theo `mergedAt` trong danh sách thay đổi chờ rồi rút bằng đường hoàn tác
    của "Ai nói câu này" - rút cả câu lẫn bí danh, và dùng được cả lúc sách đang chạy / giữ chờ duyệt."""
    from abook import aliases
    from abook.config import build_settings, save_settings
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from abook.webui.store import cast
    from tests.test_a_project_can_be_renamed_or_deleted import _call
    from tests.test_listener_speakers import _book
    from tests.test_webui_listen_and_sync import FakeRunner

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    project = paths.root
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    runner = FakeRunner()
    app = App(preferences=preferences, runner=runner, token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    base = f"/api/books/{book_id(project)}"
    try:
        status, merged = _call(server, "POST", base + "/characters/merge", {"from": "NATASHA", "into": "LUCIEN"})
        assert status == 200, merged
        person = next(item for item in cast(project)["characters"] if item["name"] == "NATASHA")
        assert person["mergedInto"] == "Lucien" and person["mergedAt"] == merged["requestedAt"]

        status, details = _call(server, "GET", base + "/pending-changes")
        item = next(entry for entry in details["items"] if entry["section"] == "speakers" and abs(entry["requestedAt"] - person["mergedAt"]) < 1e-6)
        status, undone = _call(server, "POST", base + "/speaker", {
            "lines": [{"stableId": stable_id} for stable_id in item.get("keys") or [item["key"]]], "withdraw": True,
            "requestedAt": item["requestedAt"]})
        assert status == 200 and undone["undone"] >= 1, undone
    finally:
        server.stop()
    assert speaker_requests(read_overrides(project)) == [] and aliases.load(project) == {}
    assert next(item for item in cast(project)["characters"] if item["name"] == "NATASHA")["mergedInto"] is None
