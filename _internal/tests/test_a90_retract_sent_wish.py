"""a90 V2: Hoàn tác một thay đổi ĐÃ GỬI (máy giữ sách nhận rồi, điện thoại/máy khách đã gỡ nó khỏi lớp sửa của mình).

Hợp đồng chung Python / Kotlin: gửi xong thì giữ BIÊN NHẬN của từng ý muốn (`sent_marks`: {phần: {khoá: requested_at}}); hoàn tác sau đó không còn
ý muốn nào ở máy này để rút, nên ghi một yêu cầu RÚT vào sổ (`retract_sent`), lần gửi kế mang nó trong `edits_removed.json` (`wishes`); máy giữ sách
rút đúng thao tác ấy nếu còn chờ hay chưa vào sách, không thì nói thật rằng đã áp.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from abook.webui import book_edits, edits_inbox
from tests import book_edits_fixtures as shared
from tests.test_edits_inbox import DEVICE, FOLDABLE, HEAD, _overrides, package, project  # noqa: F401 - fixture `project`
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401 - fixture `library`

SPEAKER = {"speakers": {shared.LUCIEN_LINE[0]: {"requested_at": 1759400002.0, "speaker": "HEIDI", "text_sha256": shared.LUCIEN_LINE[1]}}}
RECEIPT = {"speakers": {shared.LUCIEN_LINE[0]: 1759400002.0}}


def _sent(wishes: dict[str, Any]) -> dict[str, Any]:
    return book_edits.validate({**HEAD, "wishes": wishes})


# ---- sổ biên nhận (hợp đồng chung, ca trong tests/fixtures/book_edits/sent) -----------------------------------------------------


def test_sending_a_wish_leaves_a_receipt_in_the_marks_and_nothing_to_resend() -> None:
    marks = book_edits.sent_marks(_sent(SPEAKER))
    assert marks == {"wishes": RECEIPT}
    assert book_edits.removed_marks({}, marks) == {} and book_edits.count_removed({}) == 0
    again = book_edits.sent_marks(_sent({"retakes": shared.WISHES["retakes"]}), marks)
    assert set(again["wishes"]) == {"speakers", "retakes"} and len(again["wishes"]["retakes"]) == 2


def test_retracting_a_sent_wish_moves_its_receipt_to_the_waiting_list_once() -> None:
    marks = book_edits.sent_marks(_sent(SPEAKER))
    after, done = book_edits.retract_sent(marks, "speakers", [shared.LUCIEN_LINE[0]], 1759400002.0)
    assert done == [shared.LUCIEN_LINE[0]]
    assert after == {"retract": RECEIPT}
    waiting = book_edits.removed_marks({}, after)
    assert waiting == {"wishes": RECEIPT} and book_edits.count_removed(waiting) == 1
    # Cùng một lần bấm bấm lại, hay lần bấm khác (mốc khác): không có biên nhận nào để rút.
    assert book_edits.retract_sent(after, "speakers", [shared.LUCIEN_LINE[0]], 1759400002.0)[1] == []
    assert book_edits.retract_sent(marks, "speakers", [shared.LUCIEN_LINE[0]], 1759400003.0)[1] == []
    # Gửi xong thì sổ không còn nhắc tới biên nhận lẫn yêu cầu rút.
    assert book_edits.sent_marks({}, book_edits.forget_marks(after, waiting)) == {}


def test_the_removed_member_carries_wishes_and_a_stranger_cannot_smuggle_other_things_in() -> None:
    waiting = {"wishes": {"speakers": {"c1_s1": 1759400002.0, "c1_s2": 1759400002.0}, "retakes": {"c1_s1": 1759400009.5}}}
    assert book_edits.count_removed(waiting) == 3
    assert book_edits.parse_removed(book_edits.dump_removed(waiting)) == waiting
    for bad in ({"wishes": []}, {"wishes": {"nope": {"a": 1.0}}}, {"wishes": {"speakers": {"a": "x"}}},
                {"wishes": {"speakers": {"a": -1.0}}}, {"wishes": {"speakers": {}}}, {"wishes": {"speakers": {"": 1.0}}}):
        with pytest.raises(book_edits.EditsError):
            book_edits.validate_removed(bad)


def test_the_receipts_stay_bounded() -> None:
    entries = {f"c1_s{index}": 1759400000.0 + index for index in range(book_edits.MAX_RECEIPTS + 50)}
    marks = book_edits.sent_marks({"wishes": {"speakers": {key: {"requested_at": at} for key, at in entries.items()}}})
    kept = marks["wishes"]["speakers"]
    assert len(kept) == book_edits.MAX_RECEIPTS and max(entries) in kept and min(entries) not in kept, "giữ biên nhận mới nhất"


# ---- máy giữ sách rút đúng thao tác ----------------------------------------------------------------------------------------------


def _retract_package(tmp_path: Path, wishes: dict[str, Any], edits: dict[str, Any] | None = None) -> Path:
    """Gói điện thoại gửi khi người nghe hoàn tác thao tác đã gửi: chỉ có `edits_removed.json` ({wishes: {phần: {khoá: requested_at}}})."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as archive:
        if edits is not None:
            archive.writestr("edits.json", book_edits.dump(book_edits.validate({**HEAD, **edits})))
        archive.writestr("edits_removed.json", book_edits.dump_removed({"wishes": wishes}))
    path = tmp_path / f"rut_{len(list(tmp_path.glob('rut_*')))}.zip"
    path.write_bytes(out.getvalue())
    return path


def test_a_wish_still_waiting_in_the_inbox_is_taken_out(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": shared.WISHES}), now=1000.0)
    assert edits_inbox.waiting(project) == 6
    report = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"pronunciations": {"hailkes": 1759400001.5}}), now=1100.0)
    assert report["withdrawn"] == 1 and report["conflicts"] == [] and report["waiting"] == 5
    assert edits_inbox.waiting(project) == 5
    labels = [item["label"] for item in edits_inbox.view(project)["devices"][0]["items"]]
    assert not any("Hailkes" in label for label in labels)


def test_a_wish_the_owner_already_folded_into_a_request_is_withdrawn_by_the_stamp_the_computer_gave_it(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), may_produce=True, now=3000.0)
    assert [entry["spoken_form"] for entry in _overrides(project)["pronunciations"].values()] == ["Hên-khơ"]
    # Mốc điện thoại (1759400001.5) khác mốc máy tính đóng dấu lại (3000.x): máy giữ sách nhớ cặp này.
    report = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"pronunciations": {"hailkes": 1759400001.5}}), may_produce=True, now=3100.0)
    assert report["withdrawn"] == 1 and report["conflicts"] == []
    assert not _overrides(project).get("pronunciations")
    # Rút lần nữa, hay rút thao tác máy này chưa từng nhận: không lỗi, không rút gì, không lời báo thừa.
    again = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"pronunciations": {"hailkes": 1759400001.5}}), now=3200.0)
    assert again["withdrawn"] == 0 and again["conflicts"] == []


def test_one_line_of_a_click_is_withdrawn_without_touching_the_others(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), may_produce=True, now=3000.0)
    assert set(_overrides(project)["retakes"]) == {shared.NARRATION[0], shared.SECOND_CHAPTER[0]}
    report = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"retakes": {shared.NARRATION[0]: 1759400005.0}}), now=3100.0)
    assert report["withdrawn"] == 1
    assert set(_overrides(project)["retakes"]) == {shared.SECOND_CHAPTER[0]}


def test_a_request_the_pipeline_already_applied_is_not_withdrawn_and_the_sender_is_told_so(tmp_path: Path, project: Path, monkeypatch) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), may_produce=True, now=3000.0)
    monkeypatch.setattr(edits_inbox.store, "already_applied", lambda *_args, **_kw: True)
    report = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"pronunciations": {"hailkes": 1759400001.5}}), now=3100.0)
    assert report["withdrawn"] == 0
    (conflict,) = report["conflicts"]
    assert "vào sách" in conflict["label"] and "không rút được" in conflict["label"]
    assert edits_inbox.sender_label(conflict, "Máy A") == conflict["label"], "câu cho người gửi giữ nguyên, không lẫn góc nhìn chủ máy"
    assert [entry["spoken_form"] for entry in _overrides(project)["pronunciations"].values()] == ["Hên-khơ"], "yêu cầu còn nguyên"


def test_a_retraction_of_an_old_click_sent_together_with_a_newer_click_of_the_same_key_leaves_the_newer_one(tmp_path: Path, project: Path) -> None:
    edits_inbox.receive(project, DEVICE, "Pixel", package(tmp_path, {"wishes": FOLDABLE}), may_produce=True, now=3000.0)
    newer = {"pronunciations": {"hailkes": {"requested_at": 1759400099.0, "spoken_form": "Hên-khớ", "surface": "Hailkes"}}}
    report = edits_inbox.receive(project, DEVICE, "Pixel", _retract_package(tmp_path, {"pronunciations": {"hailkes": 1759400001.5}}, {"wishes": newer}),
                                 may_produce=True, now=3100.0)
    assert report["withdrawn"] == 1 and report["requests"] == 1
    assert [entry["spoken_form"] for entry in _overrides(project)["pronunciations"].values()] == ["Hên-khớ"], "lần bấm mới đứng, cái cũ đã rút"


def test_a_book_imported_from_a_file_drops_the_retracted_wish_from_its_own_layer(tmp_path: Path) -> None:
    from tests.test_package_share import _holder

    _lib, sync, folder, _mirror = _holder(tmp_path)
    device = {"id": DEVICE, "name": "Pixel"}
    sync.receive_edits(folder, device, package(tmp_path, {"wishes": {**SPEAKER, "retakes": shared.WISHES["retakes"]}}))
    assert book_edits.load(folder)["wishes"]["speakers"] and len(book_edits.load(folder)["wishes"]["retakes"]) == 2
    report = sync.receive_edits(folder, device, _retract_package(tmp_path, {"speakers": {shared.LUCIEN_LINE[0]: 1759400002.0},
                                                                          "retakes": {shared.NARRATION[0]: 1759400005.0}}))
    assert report["withdrawn"] == 2
    wishes = book_edits.load(folder)["wishes"]
    assert "speakers" not in wishes and set(wishes["retakes"]) == {shared.SECOND_CHAPTER[0]}
    # Lần bấm khác (mốc khác) của cùng khoá thì không bị rút nhầm.
    again = sync.receive_edits(folder, device, _retract_package(tmp_path, {"retakes": {shared.SECOND_CHAPTER[0]: 1759400999.0}}))
    assert again["withdrawn"] == 0 and set(book_edits.load(folder)["wishes"]["retakes"]) == {shared.SECOND_CHAPTER[0]}


# ---- hai máy tính thật: gửi, hoàn tác sau khi đã gửi, gửi lần nữa -------------------------------------------------------------


def test_undoing_a_reading_after_it_was_sent_asks_the_other_computer_to_withdraw_it(library, tmp_path: Path) -> None:  # noqa: F811
    from abook.webui import book_wishes, edits_inbox as inbox
    from abook.webui.library import book_id  # noqa: F401
    from abook.webui.server import Server
    from tests.test_remote_download_and_edits import _two_computers
    from tests.test_webui_listen_and_sync import _request

    app, other, _sync, project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{value}/{endpoint}", headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        status, made = post("pronunciation", {"surface": "Lucien", "spokenForm": "Lu-xi-en"})
        assert status == 200, made
        app.send_remote_edits(value)
        assert not book_wishes.made_at(path, "pronunciations", ["lucien"], made["requestedAt"]), "gửi xong đã gỡ khỏi lớp sửa của máy này"
        (device,) = inbox.view(project)["devices"]
        assert [item["kind"] for item in device["items"]] == ["pronunciation"]

        status, undone = post("pronunciation", {"surface": "Lucien", "withdraw": True, "requestedAt": made["requestedAt"]})
        assert status == 200 and undone["sent"] is True and undone["undone"] == 1, undone
        assert app.listen_book(value)["editsSync"]["pending"] == 1, "lời nhờ rút là một thay đổi chưa tới máy kia"
        state = app.send_remote_edits(value)
        assert state["pending"] == 0 and state["last"]["withdrawn"] == 1 and state["last"]["conflicts"] == []
        assert not inbox.view(project)["devices"] or not inbox.view(project)["devices"][0]["items"], "máy kia đã rút đúng thao tác ấy"

        # Bấm hoàn tác lần nữa: biên nhận đã dùng, không còn gì để rút - nói thật.
        status, again = post("pronunciation", {"surface": "Lucien", "withdraw": True, "requestedAt": made["requestedAt"]})
        assert status == 409, again
    finally:
        server.stop()
        other.stop()


def test_a_newer_click_of_the_same_key_is_not_undone_by_the_older_clicks_receipt(library, tmp_path: Path) -> None:  # noqa: F811
    from abook.webui import book_wishes
    from abook.webui.server import Server
    from tests.test_remote_download_and_edits import _two_computers
    from tests.test_webui_listen_and_sync import _request

    app, other, _sync, _project, _devices, _computer, value, path = _two_computers(library, tmp_path)
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{value}/{endpoint}", headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        _s, first = post("pronunciation", {"surface": "Lucien", "spokenForm": "Lu-xi-en"})
        app.send_remote_edits(value)
        _s, second = post("pronunciation", {"surface": "Lucien", "spokenForm": "Lu-xiên"})
        status, answer = post("pronunciation", {"surface": "Lucien", "withdraw": True, "requestedAt": first["requestedAt"]})
        assert status == 409, answer
        assert book_wishes.made_at(path, "pronunciations", ["lucien"], second["requestedAt"]), "lần bấm mới còn nguyên"
        assert app.listen_book(value)["editsSync"]["pending"] == 1
    finally:
        server.stop()
        other.stop()
