"""Hộp "Việc cần duyệt" trên cuốn lớn (400 chương, 60.000 câu) từng mất ba phút (soát a21): mỗi thẻ "Ai nói câu này" hỏi
`speaker_target` về từng chip (mỗi lần quét cả bảng câu), mỗi thẻ hỏi lại người nói nhiều nhất chương bằng cách quét cả sách,
mỗi câu ví dụ `resolve` lại thư mục sách. Các phép nhanh phải cho CÙNG kết quả với phép chậm."""
from __future__ import annotations

import os
import random
import sqlite3
from pathlib import Path

from abook.webui import store
from abook.webui import work_items as module
from abook.webui.work_items import _cast_choices, _is_named, _Spoken, work_items
from tests.test_work_items import make_book, unsure_line


def test_speaker_target_is_only_asked_about_people_who_may_lack_a_voice(tmp_path: Path, monkeypatch) -> None:
    project = make_book(tmp_path)
    unsure_line(project, "c")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, status, text_sha256)"
               " VALUES (9, 'z', 1, 8, '“Tôi đây.”', 'dialogue', 'BAN LE', 'verified', 'sha-z')")
    db.commit()
    db.close()
    asked: list[str] = []
    real = module.speaker_target

    def spy(connection, **kwargs):
        asked.append(kwargs["speaker"])
        return real(connection, **kwargs)

    monkeypatch.setattr(module, "speaker_target", spy)
    card = next(item for item in work_items(project)["items"] if item["kind"] == "speaker")
    assert asked and set(asked) == {"BAN LE"}, "người đã có giọng thì khỏi hỏi"
    assert all(choice["value"] != "BAN LE" for choice in card["choices"]), "người chưa có giọng vẫn bị bỏ khỏi chip"
    assert {choice["value"] for choice in card["choices"]} & {"RHINE", "HEIDI", "ÁO CHOÀNG ĐEN"}


def _naive_cast_choices(spoken, chapter_ids, leave_out):
    counts: dict[str, int] = {}
    for row in spoken:
        speaker = str(row["speaker"])
        if int(row["chapter_id"]) in chapter_ids and _is_named(speaker) and speaker.casefold() not in leave_out:
            counts[speaker] = counts.get(speaker, 0) + 1
    ranked = sorted(counts, key=lambda speaker: (-counts[speaker], speaker.casefold()))[:4]
    return [{"label": speaker, "value": speaker} for speaker in ranked]


def test_cast_choices_from_the_per_chapter_index_equal_a_scan_of_every_line() -> None:
    rng = random.Random(7)
    people = ["Lucien", "LUCIEN", "Heidi", "Rhine", "Áo choàng đen", "NARRATOR", "UNKNOWN", "NPC_LOCAL::c1::người gác", "ANONYMOUS_MALE", "Mira"]
    spoken = _Spoken({"chapter_id": chapter, "seq": seq, "speaker": rng.choice(people)}
                     for chapter in range(1, 13) for seq in range(rng.randint(0, 30)))
    for _ in range(200):
        chapters = set(rng.sample(range(14), rng.randint(0, 6)))
        leave_out = {name.casefold() for name in rng.sample(people, rng.randint(0, 3))}
        assert _cast_choices(spoken, chapters, leave_out, lambda raw: raw) == _naive_cast_choices(spoken, chapters, leave_out)
    plain = list(spoken)  # danh sách thường cũng được (dựng chỉ mục tại chỗ)
    assert _cast_choices(plain, {1, 2}, set(), lambda raw: raw) == _naive_cast_choices(spoken, {1, 2}, set())


def _reference_segment_audio(project_root: Path, recorded_path):
    """Bản cũ của store.segment_audio (trước AudioLocator): chuẩn để so."""
    if not recorded_path:
        return None
    root = project_root.resolve()
    path = Path(str(recorded_path))
    try:
        resolved = (path if path.is_absolute() else project_root / path).resolve()
        resolved.relative_to(root)
        return resolved if resolved.is_file() else None
    except (OSError, ValueError):
        pass
    parts = Path(str(recorded_path).replace("\\", "/")).parts
    for index, part in enumerate(parts):
        if part not in ("work", "output") or ".." in parts[index:]:
            continue
        candidate = project_root.joinpath(*parts[index:])
        if not candidate.is_file():
            continue
        try:
            found = candidate.resolve()
            found.relative_to(root)
        except (OSError, ValueError):
            return None
        return found
    return None


def test_the_batch_audio_locator_answers_exactly_like_one_lookup_at_a_time(tmp_path: Path) -> None:
    book = tmp_path / "sach"
    (book / "chunks").mkdir(parents=True)
    (book / "work" / "chunks").mkdir(parents=True)
    (book / "sub").mkdir()
    outside = tmp_path / "ngoai"
    outside.mkdir()
    for name in ("chunks/a.wav", "work/chunks/b.wav", "sub/c.wav"):
        (book / name).write_bytes(b"x")
    (outside / "secret.wav").write_bytes(b"x")
    (outside / "work").mkdir()
    (outside / "work" / "d.wav").write_bytes(b"x")
    (book / "work" / "d.wav").write_bytes(b"x")
    cases = [None, "", "chunks/a.wav", "chunks/missing.wav", "CHUNKS/A.WAV", "sub", "sub/c.wav", "./sub/c.wav", "sub/../sub/c.wav",
             "../ngoai/secret.wav", str(book / "chunks" / "a.wav"), str(book / "chunks" / "missing.wav"), str(outside / "secret.wav"),
             str(outside / "work" / "d.wav"), "D:/elsewhere/work/chunks/b.wav", r"D:\elsewhere\work\chunks\b.wav", "D:/elsewhere/x.wav",
             "work/../../ngoai/secret.wav", "chunks/\0a.wav"]
    try:
        os.symlink(outside / "secret.wav", book / "chunks" / "link.wav")
        cases.append("chunks/link.wav")
    except (OSError, NotImplementedError):
        pass
    one_by_one = store.AudioLocator(book)
    many = store.AudioLocator(book, many=True)
    for case in cases:
        expected = _reference_segment_audio(book, case)
        assert store.segment_audio(book, case) == expected, case
        assert one_by_one.find(case) == expected, case
        assert many.find(case) == expected, case
        assert store.segment_audio(book, case, many) == expected, case


def test_the_word_index_never_misses_a_line_the_regex_would_match() -> None:
    """"Áp dụng N thay đổi" tìm câu chứa tên bằng chỉ mục từ rồi thử lại regex; chỉ mục không được bỏ sót câu nào mà regex cũ khớp."""
    import re

    rng = random.Random(11)
    pool = ["sáng", "SÁNG", "Sáng", "sáng", "Lucien", "LUCIEN", "İstanbul", "istanbul", "ıstanbul", "Straße", "STRASSE", "ẞ", "σοφος", "ΣΟΦΟΣ",
            "σοφοσ", "K", "k", "Å", "å", "Deck", "deck-1", "x_y", "ǰ", "người", "NGƯỜI", "ngươi\u0300", "Xờ-mon"]
    texts = [" ".join(rng.choice(pool + [",", ".", "“", "”"]) for _ in range(rng.randint(0, 8))) for _ in range(400)]
    index = store._WordIndex(texts)
    for surface in [word for word in pool if re.fullmatch(r"\w+", word)]:
        pattern = re.compile(rf"(?<![\w]){re.escape(surface)}(?![\w])", re.IGNORECASE)
        wanted = [position for position, text in enumerate(texts) if pattern.search(text)]
        found = [position for position in index.positions(surface) if pattern.search(texts[position])]
        assert found == wanted, surface
        assert set(wanted) <= set(index.positions(surface)), surface


def test_pending_pronunciations_and_voices_are_found_without_scanning_every_line_per_change(tmp_path: Path) -> None:
    import time

    from abook import listener_overrides
    from tests.test_pending_changes_preview import _project

    project = _project(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET wav_path = 'y.wav' WHERE wav_path IS NULL OR wav_path = ''")
    db.execute("UPDATE segments SET text = 'Mr. Sáng đến, SÁNG ngời, Trời sáng.' WHERE id = 1")
    db.commit()
    db.close()
    since = time.time() - 1
    for surface in ("sáng", "Mr.", "Trời"):
        listener_overrides.request_pronunciation(project, surface, "một hai", now=time.time())
    listener_overrides.request_voice(project, "LUCIEN", preset="Thanh Bình", now=time.time())
    items = {item["label"]: item for item in store.pending_details(project, since)["items"]}
    by_surface = {key: item["lines"] for key, item in items.items() if item["kind"] == "pronunciation"}
    expected = {}
    import re
    with sqlite3.connect(project / "project.sqlite3") as db:
        texts = [str(row[0]) for row in db.execute("SELECT text FROM segments WHERE wav_path IS NOT NULL AND wav_path != ''")]
        lucien = db.execute("SELECT COUNT(*) FROM segments WHERE UPPER(speaker) = 'LUCIEN' AND wav_path != ''").fetchone()[0]
    for label in by_surface:
        surface = label.split("“")[1].split("”")[0]
        expected[label] = sum(1 for text in texts if re.search(rf"(?<![\w]){re.escape(surface)}(?![\w])", text, re.IGNORECASE))
    assert by_surface == expected and all(count > 0 for count in by_surface.values())
    assert next(item for item in items.values() if item["kind"] == "voice")["lines"] == lucien


def test_the_tab_label_asks_for_the_count_only_and_gets_the_same_number_as_the_list(tmp_path: Path) -> None:
    import json

    from abook import listener_overrides
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(project)}/work"
    try:
        def count() -> tuple[int, int]:
            status, data, _ = _request(server.port, "GET", path + "?count=1", headers=headers)
            assert status == 200
            return json.loads(data)["count"], len(json.loads(data))

        status, data, _ = _request(server.port, "GET", path, headers=headers)
        items = json.loads(data)["items"]
        assert status == 200 and items
        assert count() == (sum(1 for item in items if not item.get("requested")), 1), "chỉ một trường"
        listener_overrides.request_pronunciation(project, "Hailkes", "Hain-keo", now=1.0)
        status, data, _ = _request(server.port, "GET", path, headers=headers)
        items = json.loads(data)["items"]
        assert any(item.get("requested") for item in items)
        assert count()[0] == sum(1 for item in items if not item.get("requested")), "việc đã quyết không còn được đếm"
    finally:
        server.stop()


def test_many_deletes_share_one_sweep_timer_and_the_earliest_deadline_wins() -> None:
    """Mỗi lần xoá từng một Timer (31 giây ngủ); giờ một bộ hẹn chung: không quá một luồng chờ, dọn đúng hạn, đóng thì bỏ hết."""
    import threading
    import time

    from abook.webui.trash_pending import SweepTimer

    swept: list[Path] = []
    done = threading.Event()

    def sweep(root: Path) -> None:
        swept.append(root)
        if len(swept) >= 2:
            done.set()

    before = threading.active_count()
    timer = SweepTimer(sweep)
    first, second = Path("a"), Path("b")
    for _ in range(20):
        timer.schedule(first, 30)
    assert timer.pending() == 20 and threading.active_count() <= before + 1, "20 lần xoá vẫn chỉ một luồng chờ"
    timer.schedule(second, 0.05)  # hạn sớm hơn: hẹn lại sớm hơn
    assert done.wait(0) is False
    time.sleep(0.4)
    assert swept == [second] and timer.pending() == 20
    timer.cancel()
    assert timer.pending() == 0
    timer.schedule(first, 0.01)  # đã đóng: không hẹn nữa
    time.sleep(0.1)
    assert swept == [second] and timer.pending() == 0

    swept.clear()
    done.clear()
    again = SweepTimer(sweep)
    for root in (first, first, second):
        again.schedule(root, 0.05)
    assert done.wait(2), "hai thư viện khác nhau, mỗi cái dọn một lần dù xoá nhiều lần"
    time.sleep(0.1)
    assert sorted(swept) == [first, second] and again.pending() == 0


def test_the_library_listing_cache_follows_adds_removes_and_renames(tmp_path: Path) -> None:
    """Danh sách thư viện / sách nhập được đệm theo chữ ký thư mục (listing_cache): thêm, đổi tên, xoá cuốn, hay file nhận thêm sau khi thư mục
    đã có, đều phải thấy ngay ở lần hỏi kế - không đợi hết tuổi đệm."""
    import json
    import shutil

    from abook.webui import packages
    from abook.webui.library import Library, Preferences, book_id

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    library_root = tmp_path / "thuvien"
    library_root.mkdir()
    preferences.update({"libraryRoot": str(library_root)})
    library = Library(preferences)

    def project(name: str) -> Path:
        folder = library_root / name
        folder.mkdir()
        (folder / "book_settings.json").write_text("{}", encoding="utf-8")
        (folder / "project.sqlite3").write_bytes(b"")
        return folder

    def names(paths: list[Path]) -> list[str]:
        return sorted(path.name for path in paths)

    assert library.projects() == []
    first = project("mot")
    assert names(library.projects()) == ["mot"]
    second = project("hai")
    assert names(library.projects()) == ["hai", "mot"]
    assert library.resolve(book_id(second)) == second.resolve()
    second.rename(library_root / "ba")
    assert names(library.projects()) == ["ba", "mot"]
    assert library.resolve(book_id(second)) is None, "mã của tên cũ không còn trỏ vào đâu"
    shutil.rmtree(library_root / "ba")
    assert names(library.projects()) == ["mot"]
    # thư mục có trước, file đánh dấu dự án đến sau
    late = library_root / "muon"
    late.mkdir()
    assert names(library.projects()) == ["mot"]
    (late / "book_settings.json").write_text("{}", encoding="utf-8")
    (late / "project.sqlite3").write_bytes(b"")
    assert names(library.projects()) == ["mot", "muon"]
    assert first.exists()

    imported = library_root / packages.IMPORTED_FOLDER
    assert packages.local_folders(library_root) == [] and packages.folders(library_root) == []

    def package(folder: Path) -> None:
        folder.mkdir(parents=True)
        (folder / packages.MANIFEST).write_text(json.dumps({"package": {"format": 1}, "chapters": []}), encoding="utf-8")

    package(imported / "sach_a")
    assert names(packages.local_folders(library_root)) == ["sach_a"]
    package(imported / "sach_b")
    assert names(packages.folders(library_root)) == ["sach_a", "sach_b"]
    (imported / "sach_b").rename(imported / "sach_c")
    assert names(packages.local_folders(library_root)) == ["sach_a", "sach_c"]
    shutil.rmtree(imported / "sach_a")
    assert names(packages.folders(library_root)) == ["sach_c"]
    # cuốn ảo của máy khác dưới hai tầng
    from abook.webui.remote_books import REMOTE_FOLDER
    package(library_root / REMOTE_FOLDER / "may-x" / "sach_d")
    assert names(packages.folders(library_root)) == ["sach_c", "sach_d"]
    assert names(packages.local_folders(library_root)) == ["sach_c"], "cuốn ảo không tính vào phần chia sẻ"
    shutil.rmtree(library_root / REMOTE_FOLDER / "may-x" / "sach_d")
    assert names(packages.folders(library_root)) == ["sach_c"]


def test_a_directory_changed_a_moment_ago_is_never_served_from_the_cache(tmp_path: Path) -> None:
    """Mốc sửa chỉ nhích theo nhịp đồng hồ: file thêm vào ngay sau lần liệt kê có thể để nguyên chữ ký. Thư mục mới sửa thì khỏi nhớ."""
    import time

    from abook.webui import listing_cache

    folder = tmp_path / "thuvien"
    (folder / "a").mkdir(parents=True)
    built = []

    def build() -> list[str]:
        built.append(1)
        return sorted(child.name for child in folder.iterdir())

    for _ in range(3):
        listing_cache.cached(("racy", str(folder)), listing_cache.signature(folder), build)
    assert len(built) == 3, "vừa sửa: lần nào cũng liệt kê lại"
    old = time.time() - 600
    for path in (folder, folder / "a"):
        os.utime(path, (old, old))
    for _ in range(3):
        assert listing_cache.cached(("racy", str(folder)), listing_cache.signature(folder), build) == ["a"]
    assert len(built) == 4, "đã cũ: chỉ liệt kê một lần"
    (folder / "b").mkdir()
    assert listing_cache.cached(("racy", str(folder)), listing_cache.signature(folder), build) == ["a", "b"]
