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


def test_loose_uploads_next_to_an_uploaded_folder_do_not_show_the_internal_batch_folder_as_a_volume(tmp_path: Path) -> None:
    """Soát a35: gửi lẫn file lẻ và một thư mục -> gợi ý "nhiều tập" gọi thư mục lô "Tải lên dd-mm-yyyy hhmm xxxx" là một tập."""
    batch = tmp_path / actions.UPLOAD_FOLDER / "Tải lên 05-10-2026 18h22 ab12"
    loose = _chapters(batch, ["Chương 1", "Chương 2"])
    folder = _chapters(batch / "Truyện hay", ["Chương 3", "Chương 4"], start=3)
    scan = actions.scan_inputs([str(loose / "001.txt"), str(loose / "002.txt"), str(folder)])
    proposal = scan["volumes"]
    assert proposal is None or all("Tải lên" not in item["label"] for item in proposal["volumes"]), proposal
    assert scan["totals"]["chapters"] == 4
    # Hai thư mục người dùng chọn (không có file lẻ) vẫn là hai tập, tên tập là tên thư mục của họ.
    other = _chapters(batch / "Tập 2", ["Chương 1"])
    two = actions.scan_inputs([str(batch / "Truyện hay"), str(other)])["volumes"]
    assert two is not None and two["source"] == "folders" and {item["label"] for item in two["volumes"]} == {"Tập 2", "Truyện hay"}


def test_uploads_mixing_loose_files_and_a_folder_suggest_the_folder_name_never_a_chapter_title(tmp_path: Path) -> None:
    """Soát a36: lẫn file lẻ + thư mục -> tên sách gợi ý là "Chương 1" (tên chương đầu)."""
    batch = tmp_path / actions.UPLOAD_FOLDER / "Tải lên 05-10-2026 18h22 ab12"
    loose = _chapters(batch, ["Chương 1", "Chương 2"])
    folder = _chapters(batch / "Truyện hay", ["Chương 3", "Chương 4"], start=3)
    mixed = actions.scan_inputs([str(loose / "001.txt"), str(loose / "002.txt"), str(folder)])
    assert mixed["suggestedTitle"] == "Truyện hay"
    # Cùng thư mục nhưng thứ tự chọn khác: vẫn tên thư mục.
    assert actions.scan_inputs([str(folder), str(loose / "001.txt")])["suggestedTitle"] == "Truyện hay"
    # Chỉ thư mục (như trước), và thư mục có thư mục con (tên thư mục ngoài cùng).
    assert actions.scan_inputs([str(folder)])["suggestedTitle"] == "Truyện hay"
    nested = _chapters(batch / "Re Zero" / "Tập 1", ["Chương 1"])
    _chapters(batch / "Re Zero" / "Tập 2", ["Chương 1"])
    assert actions.scan_inputs([str(nested), str(batch / "Re Zero" / "Tập 2")])["suggestedTitle"] == "Re Zero"
    # Hai thư mục người dùng: không bao giờ lấy tên lần gửi ("Tải lên ...") làm tên sách.
    other = _chapters(batch / "Truyện hay 2", ["Chương 1"])
    assert "Tải lên" not in actions.scan_inputs([str(folder), str(other)])["suggestedTitle"]
    assert not actions.scan_inputs([str(loose / "001.txt"), str(folder)])["suggestedTitle"].startswith("Chương")


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


# ---- tạo nhiều tập -----------------------------------------------------------------------------------------------------


def _volumes(app, book: str) -> list[tuple[str, list[str]]]:
    from abook import book_volumes

    root = app.library.resolve(book)
    chapters = [dict(row) for row in ProjectDB(root / "project.sqlite3").list_chapters()]
    return [(volume["title"], [Path(chapter["input_path"]).name for chapter in volume["chapters"]])
            for volume in book_volumes.project(root, chapters)]


def test_volumes_become_one_book_with_ordered_volumes_and_one_queue_entry(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    files = sorted(str(path) for path in folder.glob("*.txt"))
    before = len(app.library.projects())

    status, created = _call(server, "POST", "/api/books", {
        "paths": files, "title": "Ánh Trăng", "profile": "high_quality", "narrator": "", "firstPerson": "",
        "volumeStarts": [1, 3, 6], "volumeLabels": ["Tập 1", "Tập 2", "Tập 3"], "start": True,
    })

    assert status == 201, created
    assert "parts" not in created and len(app.library.projects()) == before + 1, "một sách, không phải chuỗi phần"
    root = app.library.resolve(created["id"])
    assert not (root / continuation.LINK_FILE).exists()
    assert _volumes(app, created["id"]) == [("Tập 1", ["001.txt", "002.txt"]), ("Tập 2", ["003.txt", "004.txt", "005.txt"]),
                                            ("Tập 3", ["006.txt"])]
    assert app.queue == [], "chỉ một sách chạy, không có phần nối tiếp xếp hàng"
    status, view = _call(server, "GET", f"/api/listen/books/{created['id']}")
    assert [v["title"] for v in view["volumes"]] == ["Tập 1", "Tập 2", "Tập 3"]
    assert [len(v["chapters"]) for v in view["volumes"]] == [2, 3, 1]


def test_without_start_the_volumes_are_made_but_nothing_is_queued(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 5)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Bộ", "profile": "fast", "narrator": "",
        "firstPerson": "", "volumeStarts": [1, 3],
    })
    assert status == 201 and [title for title, _ in _volumes(app, created["id"])] == ["Quyển 1", "Quyển 2"]
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
        assert [title for title, _ in _volumes(app, created["id"])] == ["Quyển 1"]


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


def test_first_person_chapters_keep_their_whole_book_numbers(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    folder = _chapters(tmp_path / "truyen", [f"Chương {n}" for n in range(1, 7)])
    status, created = _call(server, "POST", "/api/books", {
        "paths": sorted(str(path) for path in folder.glob("*.txt")), "title": "Tôi", "profile": "fast", "narrator": "",
        "firstPerson": "Lucien", "firstPersonChapters": {"2": "Natasha", "5": "Natasha"}, "volumeStarts": [1, 4],
    })
    assert status == 201, created
    from abook.webui import store

    settings = store.read_settings(app.library.resolve(created["id"]))
    assert settings["voices"]["first_person_chapters"] == {"2": "Natasha", "5": "Natasha"}, "số chương toàn sách"


def test_volumes_across_two_folders_with_the_same_file_names_follow_the_book_order(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    one = _chapters(tmp_path / "Tập 1", ["Chương 1", "Chương 2", "Chương 3"])
    two = _chapters(tmp_path / "Tập 2", ["Chương 1", "Chương 2", "Chương 3"])
    files = [str(path) for path in sorted(one.glob("*.txt"))] + [str(path) for path in sorted(two.glob("*.txt"))]
    status, data = _call(server, "POST", "/api/books", {
        "paths": files, "title": "Hai thư mục", "profile": "fast", "narrator": "", "firstPerson": "", "volumeStarts": [1, 4]})
    assert status == 201, data
    assert [len(files) for _title, files in _volumes(app, data["id"])] == [3, 3]


# ---- phần nối tiếp chờ gieo ("Làm tiếp cuốn này") ----------------------------------------------------------------------


def _pending_part(paths, app, tmp_path: Path) -> Path:
    """Một phần sau đang chờ gieo, nối sau dự án của bài thử (đã phân vai xong, có giọng)."""
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


def test_a_part_whose_previous_was_deleted_starts_as_a_plain_book(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    root = _pending_part(paths, app, tmp_path)
    link = json.loads((root / continuation.LINK_FILE).read_text(encoding="utf-8"))
    link["previous"] = "khong-con-nua"
    (root / continuation.LINK_FILE).write_text(json.dumps(link), encoding="utf-8")

    assert continuation.seed_when_ready(root) == {"from": None}
    assert not continuation.seed_pending(root)
    assert continuation.seed_when_ready(root) is None


def test_after_a_restart_starting_any_part_requeues_the_pending_ones_after_it(studio, tmp_path: Path) -> None:  # noqa: F811
    paths, app, _server, _runner = studio
    second = _pending_part(paths, app, tmp_path)
    folder = _chapters(tmp_path / "tap3", ["Chương 1"])
    third = app._create_book({"profile": "fast"}, [str(next(folder.glob("*.txt")))], "T · Phần 3", None)
    continuation.link_pending(second, third)
    assert app.queue == []

    app.start(book_id(second), now=True)

    assert not continuation.seed_pending(second) and continuation.seed_pending(third)
    assert app.queue == [book_id(third)]


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
