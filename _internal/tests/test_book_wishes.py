"""Ý muốn chờ Studio của người nghe trên cuốn không có xưởng (webui/book_wishes.py, docs/EDITING.md, P2a).

Cách đọc tên, người nói, cách đọc câu, giọng/giới, thu lại: ghi vào `edits.json` (mục `wishes`, hình dạng mục của
`overrides.json`), liệt kê và rút được, đi theo file `.abook` phiên bản 4, hợp lại khi nhập lại file, và chủ máy sản xuất đọc lại
thành yêu cầu thật bằng các hàm Studio dùng - KHÔNG BAO GIỜ áp vào chữ hay audio người nghe thấy.

Phần so với bộ ví dụ dùng chung với app Android (hợp đồng, kiểm, hợp) nằm ở test_book_edits.py; ở đây là hành vi quanh chúng.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

from abook import aliases, listener_overrides
from abook.webui import book_edits, book_wishes, bookfile, packages, store
from abook.webui.bookfile import BookFile
from abook.webui.library import book_id
from tests import book_edits_fixtures as shared
from tests.book_edits_fixtures import HEIDI_LINE, LUCIEN_LINE, NARRATION, SECOND_CHAPTER
from tests.test_book_edits import _app, _edited_library, _read, imported  # noqa: F401 - `imported` là fixture

SECTIONS = book_wishes.SECTIONS


def _post(call, path: str, body: dict[str, Any] | None = None):
    return call("POST", "/api/books/{id}" + path, body)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---- không bao giờ áp ------------------------------------------------------------------------------------------------


def test_a_wish_never_changes_what_the_listener_hears_or_reads(imported) -> None:
    app, folder, identifier, call = imported
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    script_before = packages.script(folder, 1)
    manifest_before = packages.edited_manifest(folder)
    assert _post(call, "/pronunciation", {"surface": "Hailkes", "spokenForm": "Hên-khơ"})[0] == 200
    assert _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1], "speaker": "HEIDI"})[0] == 200
    assert _post(call, "/line", {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1], "emotion": "sad", "spoken": "Chào."})[0] == 200
    assert _post(call, "/voice", {"character": "HEIDI", "gender": "male"})[0] == 200
    assert _post(call, "/chapters/1/retake")[0] == 200
    assert _post(call, "/characters/merge", {"from": "HEIDI", "into": "LUCIEN"})[0] == 200
    after = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    changed = {path.relative_to(folder).as_posix() for path in after if before.get(path) != after[path]}
    assert changed == {"edits.json"}, "chỉ lớp sửa đổi; lớp sách, audio, bìa nguyên"
    assert packages.script(folder, 1) == script_before, "chữ đọc theo và người nói giữ nguyên - ý muốn không được áp"
    assert packages.edited_manifest(folder) == manifest_before
    view = app.listen_book(identifier)
    assert view["edits"] == view["wishes"] and view["wishes"] >= 5, "mọi ý muốn là thay đổi chờ Studio, không áp ngay"
    assert call("GET", "/api/books/{id}/edits")[1]["applied"] == 0


def test_a_waiting_voice_is_only_a_mark_on_the_cast(imported) -> None:
    _app_, folder, _identifier, call = imported
    _post(call, "/voice", {"character": "HEIDI", "gender": "male"})
    cast = call("GET", "/api/books/{id}/cast")[1]
    heidi = next(person for person in cast["characters"] if person["name"] == "HEIDI")
    assert heidi["pendingVoice"] == {"preset": "", "gender": "Nam"}
    assert heidi["gender"] == "Nữ" and heidi["voice"]["preset"] == "Thanh Bình", "giọng và giới đang đọc không đổi"
    assert next(person for person in cast["characters"] if person["name"] == "LUCIEN")["pendingVoice"] is None
    assert packages.raw_cast(folder)["characters"][0]["pendingVoice"] is None, "cast.json của người làm sách nguyên"


def test_the_pending_list_names_each_wish_and_withdrawing_brings_back_the_one_it_replaced(imported) -> None:
    _app_, folder, _identifier, call = imported
    first = _post(call, "/voice", {"character": "HEIDI", "gender": "female"})[1]
    second = _post(call, "/voice", {"character": "HEIDI", "gender": "male"})[1]
    assert book_edits.load(folder)["wishes"]["voices"]["HEIDI"]["replaced"]["gender"] == "female"
    listing = call("GET", "/api/books/{id}/pending-changes")[1]
    assert [item["label"] for item in listing["items"]] == ["Giọng của Hây-đi: giọng nam"] and listing["lines"] == 0
    undone = _post(call, "/voice", {"character": "HEIDI", "withdraw": True, "requestedAt": second["requestedAt"]})
    assert undone == (200, {"undone": 1, "restored": False})
    assert call("GET", "/api/books/{id}/pending-changes")[1]["items"][0]["label"] == "Giọng của Hây-đi: giọng nữ"
    assert _post(call, "/voice", {"character": "HEIDI", "withdraw": True, "requestedAt": second["requestedAt"]})[0] == 409
    assert _post(call, "/voice", {"character": "HEIDI", "withdraw": True, "requestedAt": first["requestedAt"]})[0] == 200
    assert not (folder / book_edits.EDITS_FILE).exists(), "rút hết thì không còn gì để lưu"


def test_one_click_on_many_lines_is_one_change_and_a_merge_carries_its_alias(imported) -> None:
    _app_, folder, _identifier, call = imported
    merged = _post(call, "/characters/merge", {"from": "HEIDI", "into": "LUCIEN"})[1]
    retaken = _post(call, "/chapters/1/retake")[1]
    wishes = book_edits.load(folder)["wishes"]
    assert wishes["aliases"] == [{"alias": "HEIDI", "at": merged["requestedAt"], "person": "LUCIEN"}]
    assert len(wishes["retakes"]) == retaken["lines"] == 4
    assert book_wishes.count(wishes) == 2, "gộp tên: một thay đổi; thu lại cả chương: một thay đổi"
    items = call("GET", "/api/books/{id}/pending-changes")[1]["items"]
    assert [(item["kind"], item.get("keys") and len(item["keys"])) for item in items] == [("speaker", None), ("retake", 4)]
    assert _post(call, "/pending-changes/withdraw", {"section": "speakers", "key": HEIDI_LINE[0], "keys": [HEIDI_LINE[0]],
                                                     "requestedAt": merged["requestedAt"]})[1] == {"withdrawn": 1}
    assert "aliases" not in book_edits.load(folder)["wishes"], "rút lần gộp là rút luôn bí danh"


def test_a_wish_on_a_line_that_changed_or_a_person_with_no_voice_is_refused_on_the_spot(imported) -> None:
    _app_, folder, _identifier, call = imported
    assert _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": HEIDI_LINE[1], "speaker": "HEIDI"})[0] == 400
    assert _post(call, "/speaker", {"stableId": NARRATION[0], "textSha256": NARRATION[1], "speaker": "HEIDI"})[0] == 400
    assert _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1], "speaker": "Ai đó"})[0] == 400
    assert _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1], "speaker": "Ai đó",
                                    "newGender": "female"})[0] == 200, "người nghe tạo người mới: cần tên và giới"
    assert _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1], "speaker": "ANONYMOUS_X",
                                    "newGender": "female"})[0] == 400
    assert _post(call, "/line", {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1], "emotion": "bored"})[0] == 400
    assert _post(call, "/voice", {"character": "NARRATOR", "gender": "male"})[0] == 400
    assert _post(call, "/pronunciation", {"surface": "Hai kes", "spokenForm": "Hên-khơ"})[0] == 400
    assert _post(call, "/pronunciation", {"surface": "Mở/đóng", "spokenForm": "mở hoặc đóng"})[0] == 400, "không bao giờ được dùng"
    assert list(book_edits.load(folder)["wishes"]) == ["speakers"], "chỉ ý muốn hợp lệ được ghi"


def test_a_wish_is_found_in_the_second_chapter_whatever_its_id_says(imported) -> None:
    _app_, folder, _identifier, call = imported
    assert _post(call, "/review", {"verdict": "redo", "stableId": SECOND_CHAPTER[0], "chapterId": 2})[0] == 200
    assert list(book_edits.load(folder)["wishes"]["retakes"]) == [SECOND_CHAPTER[0]]


def test_linked_books_and_unknown_books_take_no_wishes(imported, tmp_path: Path) -> None:
    from abook.webui import remote_books

    _app_, _folder, _identifier, call = imported
    remote = tmp_path / "thu_vien" / remote_books.REMOTE_FOLDER / "m1" / "b1"
    shutil.copytree(shared.BASE, remote)
    data = _read(remote / "book.json")
    data["package"]["remote"] = {"computer": "m1", "book": "b1"}
    (remote / "book.json").write_bytes(json.dumps(data).encode("utf-8"))
    for path, body in (("pronunciation", {"surface": "A", "spokenForm": "Ây"}), ("speaker", {}), ("line", {}), ("voice", {}),
                       ("review", {}), ("characters/merge", {}), ("chapters/1/retake", None), ("pending-changes/withdraw", {})):
        status, answer = call("POST", f"/api/books/{book_id(remote)}/{path}", body)
        assert status == 409 and "máy tính khác" in answer["error"], path
        assert call("POST", f"/api/books/nope/{path}", body)[0] == 404, path
    assert call("GET", f"/api/books/{book_id(remote)}/pending-changes")[0] == 409


# ---- kiểm dữ liệu của người lạ ----------------------------------------------------------------------------------------


def test_too_many_wishes_in_a_file_refuse_the_whole_file() -> None:
    def many(section: str, count: int, entry: dict[str, Any], key: str = "c1_s{:04d}") -> dict[str, Any]:
        return {**shared.HEAD, "wishes": {section: {key.format(i): dict(entry) for i in range(count)}}}

    ok = many("retakes", book_wishes.MAX_ENTRIES["retakes"], {"requested_at": 1.5, "text_sha256": NARRATION[1]})
    book_edits.validate(ok)
    ok["wishes"]["retakes"]["c1_s99999"] = {"requested_at": 1.5, "text_sha256": NARRATION[1]}
    with pytest.raises(book_edits.EditsError, match="quá dài"):
        book_edits.validate(ok)
    pronunciations = {**shared.HEAD, "wishes": {"pronunciations": {
        f"w{i}": {"requested_at": 1.5, "spoken_form": "Ây", "surface": f"W{i}"} for i in range(book_wishes.MAX_ENTRIES["pronunciations"] + 1)}}}
    with pytest.raises(book_edits.EditsError, match="quá dài"):
        book_edits.validate(pronunciations)


def test_the_writer_never_leaves_a_file_it_could_not_read_back(imported, monkeypatch) -> None:
    _app_, folder, _identifier, call = imported
    assert _post(call, "/voice", {"character": "HEIDI", "gender": "male"})[0] == 200
    monkeypatch.setattr(book_edits, "MAX_EDITS_BYTES", (folder / book_edits.EDITS_FILE).stat().st_size + 10)
    status, answer = _post(call, "/voice", {"character": "LUCIEN", "gender": "female"})
    assert status == 400 and "Quá nhiều" in answer["error"]
    assert list(book_edits.load(folder)["wishes"]["voices"]) == ["HEIDI"], "file cũ nguyên"


def test_an_entry_must_agree_with_its_key_and_carry_no_device_or_path() -> None:
    for entry in ({"requested_at": 1.5, "text_sha256": NARRATION[1], "device": "Pixel"},
                  {"requested_at": 1.5, "text_sha256": NARRATION[1], "path": "/sdcard/x"}):
        with pytest.raises(book_edits.EditsError):
            book_edits.validate({**shared.HEAD, "wishes": {"retakes": {NARRATION[0]: entry}}})
    kept = book_edits.validate({**shared.HEAD, "wishes": {"retakes": {NARRATION[0]: {"requested_at": 7, "text_sha256": NARRATION[1]}}}})
    assert kept["wishes"]["retakes"][NARRATION[0]]["requested_at"] == 7.0 and isinstance(
        kept["wishes"]["retakes"][NARRATION[0]]["requested_at"], float)


def test_a_wish_dumps_in_a_fixed_order_and_survives_the_round_trip() -> None:
    edits = book_edits.validate({**shared.HEAD, **shared.CASES["wishes"]})
    data = book_edits.dump(edits)
    assert book_edits.parse(data) == edits and book_edits.dump(book_edits.parse(data)) == data
    assert data.decode("utf-8").index('"pronunciations"') < data.decode("utf-8").index('"speakers"') < data.decode("utf-8").index('"aliases"')
    assert b"\r" not in data and data.endswith(b"\n")


def test_counting_follows_the_pending_list(imported) -> None:
    _app_, folder, _identifier, call = imported
    _post(call, "/pronunciation", {"surface": "Hailkes", "spokenForm": "Hên-khơ"})
    _post(call, "/speaker", {"lines": [{"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1]},
                                       {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1]}], "speaker": "UNNAMED"})
    _post(call, "/chapters/1/retake")
    _post(call, "/line", {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1], "emotion": "sad"})
    wishes = book_edits.load(folder)["wishes"]
    assert book_wishes.count(wishes) == 4 == len(call("GET", "/api/books/{id}/pending-changes")[1]["items"])
    assert call("GET", "/api/books/{id}/edits")[1] == {"applied": 0, "waiting": 0, "wishes": 4}


def test_the_reader_asks_which_lines_are_waiting_and_a_workshop_book_has_none(imported) -> None:
    app, folder, identifier, call = imported
    assert call("GET", "/api/books/{id}/wishes")[1] == {"pronunciations": [], "lines": {}}
    _post(call, "/speaker", {"stableId": LUCIEN_LINE[0], "textSha256": LUCIEN_LINE[1], "speaker": "HEIDI"})
    _post(call, "/line", {"stableId": HEIDI_LINE[0], "textSha256": HEIDI_LINE[1], "emotion": "sad", "spoken": "Chào."})
    _post(call, "/review", {"verdict": "redo", "stableId": NARRATION[0], "chapterId": 1})
    _post(call, "/pronunciation", {"surface": "Hailkes", "spokenForm": "Hên-khơ"})
    status, view = call("GET", "/api/books/{id}/wishes")
    assert status == 200
    assert view["pronunciations"][0]["key"] == "hailkes" and view["pronunciations"][0]["spokenForm"] == "Hên-khơ"
    assert set(view["lines"]) == {LUCIEN_LINE[0], HEIDI_LINE[0], NARRATION[0]}
    assert view["lines"][LUCIEN_LINE[0]]["speaker"]["shown"] == "Hây-đi", "tên người nghe thấy, không phải tên chuẩn"
    assert view["lines"][HEIDI_LINE[0]]["delivery"]["spoken"] == "Chào."
    assert set(view["lines"][NARRATION[0]]) == {"retake"}
    assert book_wishes.by_line(folder, None) == {"pronunciations": [], "lines": {}}


# ---- lưu, mở lại, nhập lại ------------------------------------------------------------------------------------------


def test_saving_carries_the_wishes_and_another_computer_sees_them_waiting(tmp_path: Path) -> None:
    app, folder, _identifier = _edited_library(tmp_path)
    book_edits.set_title(folder, "Sách của tôi")
    book_wishes.request_voice(folder, "HEIDI", gender="male", now=1759400004.0)
    book_wishes.request_retakes(folder, [NARRATION, SECOND_CHAPTER], now=1759400005.0)
    saved = bookfile.repack(folder, tmp_path / "ra.abook")
    with BookFile(saved) as opened:
        opened.verify()
        assert opened.book["package"]["version"] == 4 and book_edits.count(opened.edits) == 3
        assert book_wishes.count(opened.edits["wishes"]) == 2
    other, other_folder, _ = _edited_library(tmp_path, "may_b")
    shutil.rmtree(other_folder)
    result = other.open_book_file(str(saved))
    assert result["how"] == "new"
    view = other.listen_book(result["id"])
    assert (view["edits"], view["wishes"]) == (3, 2)
    imported_folder = other.library.resolve_listenable(result["id"])
    heidi = next(person for person in packages.cast(imported_folder)["characters"] if person["name"] == "HEIDI")
    assert heidi["pendingVoice"]["gender"] == "Nam"


def test_opening_the_file_again_unions_wishes_local_wins_and_a_withdrawal_stays_local(tmp_path: Path) -> None:
    app, folder, identifier = _edited_library(tmp_path)
    book_wishes.request_voice(folder, "HEIDI", gender="male", now=1759400004.0)
    book_wishes.request_retakes(folder, [NARRATION], now=1759400005.0)
    carried = bookfile.repack(folder, tmp_path / "mang_theo.abook")
    # trên máy này, sau khi lưu: đổi ý về giọng, thêm một ý muốn khác, rút lần thu lại
    book_wishes.request_voice(folder, "HEIDI", gender="female", now=1759400010.0)
    book_wishes.request_pronunciation(folder, "Hailkes", "Hên-khơ", now=1759400011.0)
    book_wishes.withdraw(folder, "retakes", [NARRATION[0]], 1759400005.0)
    result = app.open_book_file(str(carried))
    assert result["how"] == "existing" and result["id"] == identifier
    wishes = book_edits.load(folder)["wishes"]
    assert wishes["voices"]["HEIDI"]["gender"] == "female", "khoá cả hai cùng có: bên máy này thắng"
    assert wishes["voices"]["HEIDI"]["requested_at"] == 1759400010.0
    assert list(wishes["pronunciations"]) == ["hailkes"], "ý muốn chỉ có trên máy này được giữ"
    assert list(wishes["retakes"]) == [NARRATION[0]], "rút chỉ ở máy này: file còn mang nó thì nhập lại mang nó về"
    assert result["merge"]["conflicts"] == 1 and result["merge"]["kept"] == 2


def test_a_merge_that_would_overflow_keeps_this_machines_wishes_whole() -> None:
    entry = {"requested_at": 1.5, "text_sha256": NARRATION[1]}
    cap = book_wishes.MAX_ENTRIES["retakes"]
    local = {"retakes": {f"c1_s{i:05d}": dict(entry) for i in range(cap - 1)}}
    incoming = {"retakes": {f"c2_s{i:05d}": dict(entry) for i in range(5)}}
    merged, conflicts = book_wishes.merge(local, incoming)
    assert merged == local and conflicts == 0, "quá trần: giữ của máy này, không nhận thêm (file mới sẽ bị từ chối cả)"
    assert book_edits.merge({**shared.HEAD, "wishes": local}, {**shared.HEAD, "wishes": incoming})[0]["wishes"] == local


# ---- chủ máy sản xuất ----------------------------------------------------------------------------------------------------


def _producer(tmp_path: Path):
    """Một dự án thật (ProjectDB) có người kể, Lucien, Natasha và vài câu đã thu - mã băm chữ là băm thật."""
    from tests.test_listener_speakers import _book

    paths, db = _book(tmp_path)
    with db.connect() as conn:
        for row_id, text in conn.execute("SELECT id, text FROM segments").fetchall():
            conn.execute("UPDATE segments SET text_sha256=? WHERE id=?", (_sha(text), row_id))
    return paths.root, db


def _line(db, stable_id: str) -> tuple[str, str]:
    with db.connect() as conn:
        return stable_id, str(conn.execute("SELECT text_sha256 FROM segments WHERE stable_id=?", (stable_id,)).fetchone()[0])


def _dump_segments(db) -> list[tuple]:
    with db.connect() as conn:
        return [tuple(row) for row in conn.execute("SELECT * FROM segments ORDER BY id").fetchall()]


def test_the_producer_turns_wishes_into_requests_with_fresh_stamps_and_applies_nothing(tmp_path: Path) -> None:
    project, db = _producer(tmp_path)
    one, two, three = (_line(db, f"c1s{i}") for i in (1, 2, 3))
    wishes = {
        "pronunciations": {"lucien": {"requested_at": 5.0, "spoken_form": "Lu-xi-en", "surface": "Lucien"}},
        "speakers": {
            one[0]: {"requested_at": 10.0, "speaker": "NATASHA", "text_sha256": one[1]},
            two[0]: {"requested_at": 10.0, "speaker": "NATASHA", "text_sha256": two[1]},
            three[0]: {"requested_at": 20.0, "speaker": "LUCIEN", "text_sha256": three[1]},
        },
        "lines": {two[0]: {"emotion": "sad", "intensity": 1, "kind": "", "requested_at": 30.0, "text_sha256": two[1]}},
        "voices": {"LUCIEN": {"avoid": "", "gender": "male", "preset": "", "requested_at": 40.0}},
        "retakes": {three[0]: {"requested_at": 50.0, "text_sha256": three[1]}},
        "aliases": [{"alias": "Người lạ", "at": 10.0, "person": "NATASHA"}],
    }
    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "wishes": wishes}), None)
    before = _dump_segments(db)
    started = time.time()
    report = book_edits.fold(project)
    assert report == {"applied": 0, "skipped": 0, "music": False, "requests": 7}
    assert _dump_segments(db) == before, "yêu cầu chỉ được ghi, không áp vào sổ"
    data = listener_overrides.read_overrides(project)
    stamps = {name: {key: entry["requested_at"] for key, entry in data[name].items()} for name in SECTIONS}
    assert all(stamp >= started for section in stamps.values() for stamp in section.values()), "đóng dấu lại giờ"
    assert stamps["speakers"][one[0]] == stamps["speakers"][two[0]] != stamps["speakers"][three[0]], "một lần bấm vẫn là một lần bấm"
    assert stamps["pronunciations"]["lucien"] < stamps["speakers"][one[0]] < stamps["speakers"][three[0]] < stamps["lines"][two[0]], "giữ thứ tự"
    assert data["lines"][two[0]]["emotion"] == "sad" and data["voices"]["LUCIEN"]["gender"] == "male"
    assert aliases.load(project) == {aliases.key("Người lạ"): "NATASHA"}
    assert not (project / book_edits.INCOMING_FILE).exists()
    assert store.pending_changes(project, 0.0) == 6 and store.pending_details(project, 0.0)["items"], "vào danh sách Áp dụng"


def test_the_producer_skips_wishes_the_studio_would_refuse(tmp_path: Path) -> None:
    project, db = _producer(tmp_path)
    one = _line(db, "c1s1")
    wishes = {
        "pronunciations": {"x": {"requested_at": 5.0, "spoken_form": "Xă-mon", "surface": "Xamon"}},
        "speakers": {one[0]: {"requested_at": 10.0, "speaker": "NATASHA", "text_sha256": _sha("chữ khác")},
                     "c9s9": {"requested_at": 10.0, "speaker": "NATASHA", "text_sha256": one[1]}},
        "lines": {one[0]: {"emotion": "sad", "intensity": None, "kind": "", "requested_at": 30.0, "text_sha256": _sha("chữ khác")}},
        "voices": {"NOBODY": {"avoid": "", "gender": "male", "preset": "", "requested_at": 40.0}},
        "retakes": {one[0]: {"requested_at": 50.0, "text_sha256": _sha("chữ khác")}},
    }
    # `validate` giữ cả ý muốn mà Studio sẽ từ chối (chúng hợp lệ về hình dạng): fold phải bỏ qua chúng, không ghi gì
    book_edits.stash_incoming(project, book_edits.validate({**shared.HEAD, "wishes": wishes}), None)
    report = book_edits.fold(project)
    assert (report["requests"], report["skipped"]) == (0, 6)
    assert listener_overrides.read_overrides(project) == {}, "không có yêu cầu nào bị ghi"


def test_a_file_of_wishes_is_offered_to_the_producer_and_the_fold_route_reports_the_requests(tmp_path: Path) -> None:
    """Đường thật: file `.abook` mang ý muốn mở ra đúng dự án của chính máy này -> chờ người dùng đồng ý."""
    producer = tmp_path / "may_san_xuat"
    producer.mkdir()
    project = shared.make_base_project(producer)
    packed = bookfile.pack(project, tmp_path / "v1.abook")
    listener = tmp_path / "nguoi_nghe"
    listener.mkdir()
    folder = BookFile(packed).extract(listener / "thu_vien", "b")
    book_wishes.request_voice(folder, "LUCIEN", gender="male", now=1759400004.0)
    book_wishes.request_retakes(folder, [NARRATION], now=1759400005.0)
    edited = bookfile.repack(folder, tmp_path / "da_sua.abook")
    app = _app(tmp_path, project.parent)
    opened = app.open_book_file(str(edited))
    assert (opened["how"], opened["edits"]) == ("project", 2)
    assert listener_overrides.read_overrides(project) == {}, "chưa áp cho tới khi người dùng đồng ý"
    assert book_edits.incoming(project)["wishes"]["voices"]["LUCIEN"]["gender"] == "male"
