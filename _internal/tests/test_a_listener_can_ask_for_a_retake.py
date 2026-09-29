"""Tab "Cần nghe lại": "Cần thu lại" thu lại THẬT một câu (soát 29-09: phán quyết chỉ nằm ở reviews.json, không gì đọc nó).

Giao diện ghi overrides.json `retakes`; dây chuyền áp ở ranh giới như mọi yêu cầu khác - đúng MỘT lần mỗi yêu cầu (mốc
`listener_retake_at`), đặt lại câu đã thu, và thu bằng hạt giống MỚI (`listener_retakes` trong tts.generation_seed): cùng
hạt giống thì bản thu lại y hệt bản bị chê. Câu chưa ai yêu cầu giữ đúng hạt giống cũ."""
from __future__ import annotations

import json
from pathlib import Path

from ebook_reader.listener_overrides import (
    SOURCE_CHANGED,
    UNKNOWN_LINE,
    cancel_retake,
    read_overrides,
    request_retake,
    retake_requests,
)
from tests.test_listener_lines import _line
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_speakers import _book


def test_a_retake_request_is_written_listed_and_can_be_withdrawn(tmp_path: Path) -> None:
    request_retake(tmp_path, "c1s2", "sha-c1s2", now=200.0)
    request_retake(tmp_path, "c1s1", "sha-c1s1", now=100.0)
    assert retake_requests(read_overrides(tmp_path)) == [
        {"stable_id": "c1s1", "text_sha256": "sha-c1s1", "requested_at": 100.0},
        {"stable_id": "c1s2", "text_sha256": "sha-c1s2", "requested_at": 200.0},
    ]
    cancel_retake(tmp_path, "c1s1")
    cancel_retake(tmp_path, "khong-co")
    assert [request["stable_id"] for request in retake_requests(read_overrides(tmp_path))] == ["c1s2"]


def test_a_retake_resets_the_line_once_per_request_and_counts(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)
    result = db.apply_listener_retake(stable_id="c1s1", text_sha256="sha-c1s1", requested_at=500.0)
    assert result == {"stable_id": "c1s1", "chapter_id": 1, "retakes": 1, "reset": True}
    line = _line(db, "c1s1")
    assert (line["status"], line["wav_path"], line["listener_retakes"], line["listener_retake_at"]) == ("analyzed", None, 1, 500.0)
    assert db.apply_listener_retake(stable_id="c1s1", text_sha256="sha-c1s1", requested_at=500.0) is None, \
        "overrides.json đọc lại ở mọi ranh giới: một yêu cầu thu lại đúng một lần"
    again = db.apply_listener_retake(stable_id="c1s1", text_sha256="sha-c1s1", requested_at=900.0)
    assert again is not None and again["retakes"] == 2, "chê lần nữa: lượt mới, hạt giống mới"
    assert db.apply_listener_retake(stable_id="c1s2", text_sha256="khac", requested_at=1.0) == {"problem": SOURCE_CHANGED}
    assert db.apply_listener_retake(stable_id="khong-co", text_sha256="x", requested_at=1.0) == {"problem": UNKNOWN_LINE}
    assert _line(db, "c1s2")["status"] == "verified", "câu đã đổi chữ không bị đụng"


def test_a_retaken_line_gets_a_new_seed_and_an_untouched_line_keeps_the_old_one(tmp_path: Path) -> None:
    from ebook_reader.config import build_settings
    from ebook_reader.tts import TTSCoordinator

    _paths, db = _book(tmp_path)
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    before = coordinator.generation_seed(_line(db, "c1s1"), "primary")
    legacy = dict(_line(db, "c1s1"))
    legacy.pop("listener_retakes")
    assert coordinator.generation_seed(legacy, "primary") == before, "sổ cũ chưa có cột: hạt giống như trước"
    db.apply_listener_retake(stable_id="c1s1", text_sha256="sha-c1s1", requested_at=500.0)
    first = coordinator.generation_seed(_line(db, "c1s1"), "primary")
    db.apply_listener_retake(stable_id="c1s1", text_sha256="sha-c1s1", requested_at=900.0)
    second = coordinator.generation_seed(_line(db, "c1s1"), "primary")
    assert len({before, first, second}) == 3


def test_the_pipeline_applies_a_retake_at_the_boundary(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    request_retake(paths.root, "c1s3", "sha-c1s3", now=700.0)
    pipeline = _Pipeline(paths, db)
    assert pipeline._apply_listener_overrides() == {1}
    assert _line(db, "c1s3")["listener_retakes"] == 1
    assert any("thu lại câu c1s3" in message for message in pipeline.logs)
    assert pipeline._apply_listener_overrides() == set(), "ranh giới sau: không thu lại lần nữa"


def test_the_review_verdict_writes_and_withdraws_the_request(tmp_path: Path) -> None:
    from ebook_reader.config import build_settings, save_settings
    from ebook_reader.webui.actions import FakeRunner
    from ebook_reader.webui.library import Preferences, book_id
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.server import App, Server
    from ebook_reader.webui.store import changes_since, pending_changes
    from tests.test_webui_listen_and_sync import _request

    paths, _db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    path = f"/api/books/{book_id(paths.root)}/review"
    headers = {"X-Ebook-Token": "t"}
    try:
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c1s2", "chapterId": 1, "verdict": "redo"})
        assert status == 200
        retakes = read_overrides(paths.root)["retakes"]
        assert list(retakes) == ["c1s2"] and retakes["c1s2"]["text_sha256"] == "sha-c1s2"
        assert pending_changes(paths.root, changes_since(paths.root, 0.0)) == 1, "sách xong: nút Áp dụng đếm cả thu lại"
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c1s2", "chapterId": 1, "verdict": "ok"})
        assert status == 200 and read_overrides(paths.root)["retakes"] == {}
    finally:
        server.stop()
    assert json.loads((tmp_path / "prefs" / "reviews.json").read_text(encoding="utf-8"))
