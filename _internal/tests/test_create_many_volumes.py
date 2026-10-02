"""Tạo nhiều tập cùng lúc (B7): ĐỀ XUẤT chỗ cắt tập từ thư mục / tiêu đề "Tập N", rồi tạo tập 1 như sách thường và các tập
sau như phần nối tiếp, xếp hàng đúng thứ tự, gieo từ tập trước lúc tới lượt chạy."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import continuation
from abook.database import ProjectDB
from abook.webui import actions, txt_split, volumes
from abook.webui.library import book_id
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung


def _chapters(folder: Path, firsts: list[str], *, start: int = 1) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for offset, first in enumerate(firsts):
        (folder / f"{start + offset:03d}.txt").write_text(f"{first}\n\nLucien đi tiếp.\n", encoding="utf-8")
    return folder


# ---- đề xuất chỗ cắt ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("line, expected", [
    ("Tập 2", ("Tập", 2)),
    ("TẬP 12 - Lời mở đầu", ("Tập", 12)),
    ("Quyển 3: Biển", ("Quyển", 3)),
    ("Quyển thứ hai", ("Quyển", 2)),
    ("Tập Một", ("Tập", 1)),
    ("Volume 2", ("Volume", 2)),
    ("Vol. II", ("Vol", 2)),
    ("# Book Two", ("Book", 2)),
    ("【Tập 4】", ("Tập", 4)),
    ("第二卷 海", ("Tập", 2)),
    ("第12巻", ("Tập", 12)),
    ("Tập tin đính kèm", None),
    ("Tập trung vào Lucien.", None),
    ("Chương 2", None),
    ("Book civil war", None),
    ("Tập", None),
])
def test_a_line_naming_a_volume_is_recognised_in_vietnamese_and_english(line: str, expected) -> None:
    assert volumes.volume_heading(line) == expected


def test_one_folder_per_volume_is_proposed_in_natural_order_with_the_boundaries_at_each_folder(tmp_path: Path) -> None:
    root = tmp_path / "Light novel"
    # Tên file giống nhau giữa các tập (001, 002…): quét theo tên thì chương hai tập xen nhau.
    ten = _chapters(root / "Tập 10", ["Chương 1", "Chương 2", "Chương 3"])
    two = _chapters(root / "Tập 2", ["Chương 1", "Chương 2"])
    one = _chapters(root / "Tập 1", ["Chương 1", "Chương 2"])

    scan = actions.scan_inputs([str(ten), str(one), str(two)])
    proposal = scan["volumes"]

    assert proposal["source"] == "folders"
    assert [(item["label"], item["start"], item["chapters"]) for item in proposal["volumes"]] == [
        ("Tập 1", 1, 2), ("Tập 2", 3, 2), ("Tập 10", 5, 3)], "Tập 2 đứng trước Tập 10"
    assert proposal["order"] is not None and [Path(path).parent.name for path in proposal["order"]] == [
        "Tập 1", "Tập 1", "Tập 2", "Tập 2", "Tập 10", "Tập 10", "Tập 10"]
    assert [item["startPath"] for item in proposal["volumes"]] == [proposal["order"][0], proposal["order"][2], proposal["order"][4]]
    assert scan["totals"]["chapters"] == 7, "đề xuất không đổi gì ở danh sách chương"


def test_epub_folders_are_labelled_by_the_epub_name_not_its_hash(tmp_path: Path) -> None:
    root = tmp_path / "Nguồn EPUB"
    a = _chapters(root / "Re Zero Vol 1 - 1a2b3c4d", ["Mở đầu", "Một"])
    b = _chapters(root / "Re Zero Vol 2 - 5e6f7a8b", ["Mở đầu", "Một"])
    proposal = actions.scan_inputs([str(b), str(a)])["volumes"]
    assert proposal["source"] == "epubs"
    assert [item["label"] for item in proposal["volumes"]] == ["Re Zero Vol 1", "Re Zero Vol 2"]


def test_headings_that_name_a_volume_are_proposed_inside_one_folder(tmp_path: Path) -> None:
    folder = _chapters(tmp_path / "truyen", [
        "Tập 1 - Chương 1", "Tập 1 - Chương 2", "Chương 3",
        "Tập 2 - Chương 1", "Chương 2", "Chương 3",
        "Quyển 3", "Chương 1",
    ])
    proposal = actions.scan_inputs([str(folder)])["volumes"]
    assert proposal["source"] == "headings" and proposal["order"] is None, "một thư mục: thứ tự quét giữ nguyên"
    assert [(item["label"], item["start"], item["chapters"]) for item in proposal["volumes"]] == [
        ("Tập 1", 1, 3), ("Tập 2", 4, 3), ("Quyển 3", 7, 2)]


def test_a_preface_before_volume_one_belongs_to_volume_one_but_before_volume_three_it_does_not(tmp_path: Path) -> None:
    one = _chapters(tmp_path / "a", ["Lời giới thiệu", "Tập 1", "Chương 1", "Tập 2", "Chương 1"])
    assert [item["start"] for item in actions.scan_inputs([str(one)])["volumes"]["volumes"]] == [1, 4]
    three = _chapters(tmp_path / "b", ["Chương 9", "Tập 3", "Chương 1"])
    assert [item["start"] for item in actions.scan_inputs([str(three)])["volumes"]["volumes"]] == [1, 2]


def test_a_single_volume_source_gets_no_proposal(tmp_path: Path) -> None:
    plain = _chapters(tmp_path / "plain", ["Chương 1", "Chương 2", "Chương 3"])
    assert actions.scan_inputs([str(plain)])["volumes"] is None
    # "Tập 1" lặp ở mọi chương, hay số tập không tăng: không phải chỗ cắt.
    repeated = _chapters(tmp_path / "repeated", ["Tập 1 - Chương 1", "Tập 1 - Chương 2", "Tập 1 - Chương 3"])
    assert actions.scan_inputs([str(repeated)])["volumes"] is None
    backwards = _chapters(tmp_path / "backwards", ["Tập 3", "Tập 2", "Tập 1"])
    assert actions.scan_inputs([str(backwards)])["volumes"] is None
    one = _chapters(tmp_path / "one", ["Tập 2 - Chương 1"])
    assert actions.scan_inputs([str(one)])["volumes"] is None


def test_a_whole_story_in_one_file_keeps_the_volume_line_with_the_chapter_it_opens(tmp_path: Path) -> None:
    source = tmp_path / "Bo truyen.txt"
    source.write_text(
        "Chương 1: Mở\n\nMột câu.\n\nChương 2: Tiếp\n\nHai câu.\n\nTập 2\n\nChương 3: Sang tập\n\nBa câu.\n", encoding="utf-8")
    assert txt_split.plan(source)["chapters"] == 3
    folder = txt_split.split(source, tmp_path / "lib")
    names = sorted(path.name for path in folder.glob("*.txt"))
    assert names == ["0001 Chương 1 Mở.txt", "0002 Chương 2 Tiếp.txt", "0003 Chương 3 Sang tập.txt"]
    assert "Tập 2" not in (folder / names[1]).read_text(encoding="utf-8"), "dòng Tập 2 không còn là đuôi của chương 2"
    assert (folder / names[2]).read_text(encoding="utf-8").startswith("Tập 2\n\nChương 3: Sang tập")
    # ...và nhờ thế bước chia tập thấy được chỗ cắt.
    proposal = actions.scan_inputs([str(folder)])["volumes"]
    assert [(item["start"], item["chapters"]) for item in proposal["volumes"]] == [(1, 2), (3, 1)]


def test_split_paths_cuts_by_chapter_number_and_rejects_bad_boundaries() -> None:
    paths = [f"{index}.txt" for index in range(1, 8)]
    assert volumes.split_paths(paths, None) == [paths] and volumes.split_paths(paths, [1]) == [paths]
    assert volumes.split_paths(paths, [1, 4, 7]) == [paths[:3], paths[3:6], paths[6:]]
    for bad in ([2, 4], [1, 4, 4], [1, 5, 3], [1, 8], ["x"]):
        with pytest.raises(ValueError):
            volumes.split_paths(paths, bad)


def test_first_person_chapters_follow_their_chapter_into_the_volume() -> None:
    chapters = {"2": "Lucien", "5": "Natasha", "7": "Lucien"}
    assert volumes.localize_chapters(chapters, 0, 3) == {"2": "Lucien"}
    assert volumes.localize_chapters(chapters, 3, 3) == {"2": "Natasha"}
    assert volumes.localize_chapters(chapters, 6, 3) == {"1": "Lucien"}
    assert volumes.localize_chapters(None, 0, 3) is None and volumes.localize_chapters({"9": "X"}, 0, 3) is None


# ---- tạo nhiều tập -----------------------------------------------------------------------------------------------------


def _titles(server) -> dict[str, str]:
    _status, data = _call(server, "GET", "/api/library")
    return {book["id"]: book["title"] for book in data["books"]}


def test_volumes_become_one_book_and_linked_parts_queued_in_order(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    files = sorted(str(path) for path in folder.glob("*.txt"))

    status, created = _call(server, "POST", "/api/books", {
        "paths": files, "title": "Ánh Trăng", "profile": "high_quality", "narrator": "", "firstPerson": "",
        "volumeStarts": [1, 3, 6], "start": True,
    })

    assert status == 201, created
    parts = created["parts"]
    assert [part["part"] for part in parts] == [1, 2, 3] and parts[0]["id"] == created["id"]
    roots = [app.library.resolve(part["id"]) for part in parts]
    assert continuation.chain_of(roots[2]) == [root.resolve() for root in roots], "chuỗi continues.json đúng thứ tự"
    assert [continuation.part_number(root) for root in roots] == [1, 2, 3]
    titles = _titles(server)
    assert [titles[part["id"]] for part in parts] == ["Ánh Trăng", "Ánh Trăng · Phần 2", "Ánh Trăng · Phần 3"], \
        "cùng quy ước đặt tên với 'Làm tiếp cuốn này'"
    assert [len(continuation._input_paths(root)) for root in roots] == [2, 3, 1]
    assert [[Path(path).name for path in continuation._input_paths(root)] for root in roots] == [
        ["001.txt", "002.txt"], ["003.txt", "004.txt", "005.txt"], ["006.txt"]]
    # Hàng đợi: tập 1 chạy (hay đang khởi động), tập 2 rồi tập 3 xếp sau - đúng thứ tự, không tranh GPU.
    assert app.queue == [parts[1]["id"], parts[2]["id"]]
    assert [part["queued"] for part in parts] == [0, 1, 2]
    # Chưa gieo gì: tập 1 chưa chạy nên chưa có gì để mang - cờ chờ gieo thay cho việc gieo một cái vỏ rỗng.
    assert [continuation.seed_pending(root) for root in roots] == [False, True, True]
    assert ProjectDB(roots[1] / "project.sqlite3").locked_character_voices() == {}
    link = json.loads((roots[1] / continuation.LINK_FILE).read_text(encoding="utf-8"))
    assert link["part"] == 2 and link["seedPending"] is True and "seededAt" not in link
    status, view = _call(server, "GET", f"/api/books/{parts[1]['id']}")
    assert view["book"]["seedPending"] is True and view["book"]["queuePosition"] == 1
    assert view["book"]["series"] == {"root": parts[0]["id"], "part": 2}


def test_without_start_the_volumes_are_made_but_nothing_is_queued(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 5)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3],
    })
    assert status == 201 and len(created["parts"]) == 2
    assert app.queue == [] and not app.jobs.starting(app.library.resolve(created["id"]))


def test_one_volume_is_an_ordinary_book(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 4)])
    files = sorted(str(path) for path in folder.glob("*.txt"))
    for starts in (None, [1]):
        body = {"paths": files, "title": "Một tập", "profile": "fast", "narrator": "", "firstPerson": ""}
        status, created = _call(server, "POST", "/api/books", {**body, **({"volumeStarts": starts} if starts else {})})
        assert status == 201 and "parts" not in created
        root = app.library.resolve(created["id"])
        assert not (root / continuation.LINK_FILE).exists() and not continuation.seed_pending(root)
        assert len(continuation._input_paths(root)) == 3


def test_bad_boundaries_create_nothing(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 4)])
    before = len(app.library.projects())
    for starts in ([2, 3], [1, 3, 3], [1, 9]):
        status, data = _call(server, "POST", "/api/books", {
            "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Hỏng", "profile": "fast",
            "narrator": "", "firstPerson": "", "volumeStarts": starts,
        })
        assert status == 400, (starts, data)
    assert len(app.library.projects()) == before


def test_first_person_chapters_are_numbered_inside_each_volume(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Tôi", "profile": "fast", "narrator": "",
        "firstPerson": "Lucien", "firstPersonChapters": {"2": "Natasha", "5": "Natasha"}, "volumeStarts": [1, 4],
    })
    assert status == 201, created
    from abook.webui import store

    settings = [store.read_settings(app.library.resolve(part["id"])) for part in created["parts"]]
    assert [item["voices"]["first_person_chapters"] for item in settings] == [{"2": "Natasha"}, {"2": "Natasha"}]


# ---- gieo đúng lúc -----------------------------------------------------------------------------------------------------


def _pending_part(paths, app, tmp_path: Path) -> Path:
    """Một tập sau đang chờ gieo, nối sau dự án của bài thử (đã phân vai xong, có giọng)."""
    folder = _chapters(tmp_path / "tap2", ["Chương 1"])
    root = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "T · Phần 2", None)
    continuation.link_pending(paths.root, root)
    return root


def test_a_pending_part_is_seeded_when_it_starts_after_the_previous_one_has_cast_its_voices(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    root = _pending_part(paths, app, tmp_path)
    assert ProjectDB(root / "project.sqlite3").locked_character_voices() == {}

    app.start(book_id(root), now=True)

    voices = ProjectDB(root / "project.sqlite3").locked_character_voices()
    assert {"LUCIEN", "NATASHA"} <= set(voices), "giọng người đã gặp được gieo trước khi chạy"
    assert not continuation.seed_pending(root)
    link = json.loads((root / continuation.LINK_FILE).read_text(encoding="utf-8"))
    assert link["part"] == 2 and "seededAt" in link and "seedPending" not in link


def test_a_part_whose_previous_has_not_cast_yet_does_not_start_and_stays_pending(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 5)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3],
    })
    assert status == 201
    second = created["parts"][1]["id"]

    status, data = _call(server, "POST", f"/api/books/{second}/start")  # tập 1 chưa chạy: chưa phân vai

    assert status == 409 and "chưa phân tích xong" in data["error"]
    root = app.library.resolve(second)
    assert continuation.seed_pending(root), "vẫn chờ gieo - không chạy ra giọng khác phần trước"
    assert not app.jobs.starting(root) and not app.runner.running(root)


def test_the_queue_reports_a_part_it_could_not_seed_and_keeps_draining(studio, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    from abook.webui import server as server_module

    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 5)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3], "start": True,
    })
    assert status == 201
    second = app.library.resolve(created["parts"][1]["id"])
    first = app.library.resolve(created["id"])
    # Tập 1 bị dừng giữa chừng: hàng đợi tới lượt tập 2, nhưng chưa có phân vai để gieo.
    app.jobs._starting.clear()
    app.runner._running.discard(str(first))
    ticks = iter([None])

    def one_round(_seconds: float) -> None:
        if next(ticks, "stop") == "stop":
            raise SystemExit

    monkeypatch.setattr(server_module.time, "sleep", one_round)
    with pytest.raises(SystemExit):
        app._drain_queue()
    # (vòng lặp chạy một lượt rồi bị cắt ở lần ngủ kế)

    assert app.queue == [] and app.jobs.error(second).startswith("Phần trước"), app.jobs.error(second)
    assert continuation.seed_pending(second)


def test_a_part_whose_previous_was_deleted_starts_as_a_plain_book(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    root = _pending_part(paths, app, tmp_path)
    link = json.loads((root / continuation.LINK_FILE).read_text(encoding="utf-8"))
    link["previous"] = "khong-con-nua"
    (root / continuation.LINK_FILE).write_text(json.dumps(link), encoding="utf-8")

    assert continuation.seed_when_ready(root) == {"from": None}
    assert not continuation.seed_pending(root)
    assert continuation.seed_when_ready(root) is None


def test_a_volume_spanning_two_folders_with_the_same_file_names_is_refused_before_anything_is_made(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    one = _chapters(tmp_path / "Tập 1", ["Chương 1", "Chương 2", "Chương 3"])
    two = _chapters(tmp_path / "Tập 2", ["Chương 1", "Chương 2", "Chương 3"])
    files = [str(path) for path in sorted(one.glob("*.txt"))] + [str(path) for path in sorted(two.glob("*.txt"))]
    before = len(app.library.projects())

    # Cắt giữa Tập 2: tập 1 có "001.txt" của hai thư mục - dây chuyền xếp theo tên file nên chúng sẽ xen nhau.
    status, data = _call(server, "POST", "/api/books", {
        "paths": files, "title": "Lệch", "profile": "fast", "narrator": "", "firstPerson": "", "volumeStarts": [1, 6]})
    assert status == 400 and "thứ tự đọc" in data["error"], data
    assert len(app.library.projects()) == before, "không tạo gì"

    # Cắt đúng ranh giới thư mục thì được.
    status, data = _call(server, "POST", "/api/books", {
        "paths": files, "title": "Đúng", "profile": "fast", "narrator": "", "firstPerson": "", "volumeStarts": [1, 4]})
    assert status == 201 and len(data["parts"]) == 2
    # Một tập trải hai thư mục mà tên file nối tiếp nhau (001-003 rồi 004-006) vẫn đúng thứ tự đọc.
    assert not volumes.reading_order_problem(["a/001.txt", "a/002.txt", "b/003.txt"])
    assert volumes.reading_order_problem(["a/001.txt", "b/001.txt"])


def test_starting_the_first_part_queues_the_pending_parts_after_it_in_order(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3, 5],
    })
    assert status == 201 and app.queue == []
    ids = [part["id"] for part in created["parts"]]

    status, _data = _call(server, "POST", f"/api/books/{ids[0]}/start")

    assert status == 202
    assert app.queue == ids[1:], "phần 2 rồi phần 3 xếp hàng sau phần 1, đúng thứ tự"
    # Bấm lại / chạy tiếp không xếp hàng đôi.
    app._queue_successors(app.library.resolve(ids[0]))
    assert app.queue == ids[1:]


def test_after_a_restart_starting_any_part_requeues_the_pending_ones_after_it(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    second = _pending_part(paths, app, tmp_path)
    folder = _chapters(tmp_path / "tap3", ["Chương 1"])
    third = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "T · Phần 3", None)
    continuation.link_pending(second, third)
    assert app.queue == [], "mở lại app: hàng đợi trống, không gì tự chạy"

    app.start(book_id(second), now=True)  # phần 1 (bài thử) đã phân vai xong nên gieo được

    assert not continuation.seed_pending(second) and continuation.seed_pending(third)
    assert app.queue == [book_id(third)]


def test_a_part_that_cannot_start_does_not_queue_its_successors(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3, 5],
    })
    status, _data = _call(server, "POST", f"/api/books/{created['parts'][1]['id']}/start")
    assert status == 409 and app.queue == [], "phần 1 chưa phân vai: phần 2 không chạy, phần 3 không vào hàng"


def test_sibling_folders_used_together_suggest_the_parent_folder_as_the_title(tmp_path: Path) -> None:
    parent = tmp_path / "Re Zero"
    one = _chapters(parent / "Tập 1", ["Chương 1", "Chương 2"])
    two = _chapters(parent / "Tập 2", ["Chương 1", "Chương 2"])
    assert actions.scan_inputs([str(one), str(two)])["suggestedTitle"] == "Re Zero", "không phải '001' của file đầu"
    # Một thư mục: như trước (tên thư mục chứa chương). Cha chung chung: giữ cách cũ.
    assert actions.scan_inputs([str(one)])["suggestedTitle"] == "Tập 1"
    downloads = tmp_path / "Downloads"
    a = _chapters(downloads / "A", ["Chương 1"])
    b = _chapters(downloads / "B", ["Chương 1"])
    assert actions.scan_inputs([str(a), str(b)])["suggestedTitle"] == "001"
