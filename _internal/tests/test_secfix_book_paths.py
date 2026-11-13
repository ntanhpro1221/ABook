"""Soát bảo mật 12-11 (lỗi 1): đường dẫn trong sổ dự án là dữ liệu - file `.abookproj` người khác gửi mang sổ do họ viết.

Lớp một: `ProjectFile.open_into` từ chối cả file khi còn đường trỏ ra ngoài thư mục dự án mới (không mở dở).
Lớp hai: mọi chỗ đọc/ghi theo cột đường dẫn đi qua `book_paths` - kiểm theo chữ TRƯỚC mọi I/O, chặn hẳn UNC.
"""
from __future__ import annotations

import builtins
import hashlib
import json
import os
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from abook import book_paths
from abook.webui import projectfile, store
from abook.webui.projectfile import ProjectFile, ProjectFileError
from tests.test_project_file import _project

UNC = r"\\attacker.example\s\1.txt"
BAD_INPUTS = [
    UNC,
    "//attacker.example/s/1.txt",
    r"\\?\UNC\attacker.example\s\1.txt",
    r"\\.\pipe\x",
    r"C:\Windows\win.ini",
    r"C:\ngoai_du_an\1.txt",
    r"..\ngoai_du_an\1.txt",
    "chuong.txt",  # tương đối
]


class _Touched(AssertionError):
    pass


@pytest.fixture
def no_network_io(monkeypatch: pytest.MonkeyPatch):
    """Bất kỳ open / stat / lstat / scandir nào vào đường của kẻ gửi (UNC hay ngoài thư mục dự án) đều làm test hỏng."""
    touched: list[str] = []
    forbidden = ("attacker", "win.ini", "ngoai_du_an")

    def guard(real):
        def wrapper(path, *args, **kwargs):
            text = os.fspath(path) if isinstance(path, (str, bytes, os.PathLike)) else ""
            text = text.decode() if isinstance(text, bytes) else text
            if any(word in text.lower() for word in forbidden):
                touched.append(text)
                raise _Touched(text)
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(builtins, "open", guard(builtins.open))
    monkeypatch.setattr(os, "stat", guard(os.stat))
    monkeypatch.setattr(os, "lstat", guard(os.lstat))
    monkeypatch.setattr(os, "scandir", guard(os.scandir))
    return touched


# ---- book_paths ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", BAD_INPUTS + [r"{root}\..\ngoai_du_an\x.mp3", r"{root}\output\..\..\ngoai_du_an\x.mp3",
                                                r"D:\ngoai_du_an\x.mp3", "", None])
def test_a_book_file_outside_the_book_folder_is_refused_before_any_io(tmp_path: Path, value, no_network_io) -> None:
    value = value.format(root=tmp_path) if isinstance(value, str) else value
    with pytest.raises(book_paths.UnsafeBookPath):
        book_paths.inside(tmp_path, value)
    assert book_paths.safe_inside(tmp_path, value) is None
    assert no_network_io == []


@pytest.mark.parametrize("value", [UNC, "//attacker.example/s/1.txt", r"\\?\C:\ngoai_du_an\a.txt", r"C:\Windows\win.ini",
                                   r"C:\ngoai_du_an\khoa_ssh", "chuong.txt", r"{root}\..\ngoai_du_an\khoa"])
def test_a_chapter_source_that_is_not_allowed_is_refused_before_any_io(tmp_path: Path, value: str, no_network_io) -> None:
    with pytest.raises(book_paths.UnsafeBookPath):
        book_paths.chapter_source(tmp_path, value.format(root=tmp_path))
    assert no_network_io == []


def test_allowed_paths_pass(tmp_path: Path) -> None:
    (tmp_path / "output").mkdir()
    assert book_paths.inside(tmp_path, tmp_path / "output" / "1.mp3") == (tmp_path / "output" / "1.mp3").resolve()
    # Dự án làm trên máy này đọc thẳng file TXT người dùng chọn, nằm đâu cũng được.
    elsewhere = tmp_path.parent / "nguon_cua_toi" / "1.TXT"
    with pytest.raises(book_paths.UnsafeBookPath):
        book_paths.chapter_source(tmp_path / "sach", elsewhere)
    with pytest.raises(book_paths.UnsafeBookPath):
        book_paths.chapter_source(None, elsewhere)
    assert book_paths.chapter_source(tmp_path, tmp_path / "sources" / "1.md") == (tmp_path / "sources" / "1.md").resolve()


def test_a_link_inside_the_book_folder_that_points_outside_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "ngoai"
    outside.mkdir()
    root = tmp_path / "sach"
    root.mkdir()
    try:
        os.symlink(outside, root / "lien_ket", target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        import subprocess
        subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(root / "lien_ket"), str(outside)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    with pytest.raises(book_paths.UnsafeBookPath):
        book_paths.inside(root, root / "lien_ket" / "x.mp3")


# ---- lớp một: mở file dự án ---------------------------------------------------------------------------------------


def _tampered(tmp_path: Path, sql: str, *params) -> Path:
    """File dự án hợp lệ mà sổ bị kẻ gửi sửa - mã băm trong project.json tính lại cho khớp (kẻ gửi tự làm được)."""
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    member = f"project/{store.DB_NAME}"
    scratch = tmp_path / "scratch.sqlite3"
    with zipfile.ZipFile(packed) as archive:
        scratch.write_bytes(archive.read(member))
        infos = [(info, archive.read(info.filename)) for info in archive.infolist()]
    with sqlite3.connect(scratch) as db:
        db.execute(sql, params)
    data = scratch.read_bytes()
    out = tmp_path / "doc.abookproj"
    with zipfile.ZipFile(out, "w") as sink:
        for info, payload in infos:
            if info.filename == member:
                payload = data
            elif info.filename == projectfile.MANIFEST:
                manifest = json.loads(payload)
                manifest["files"][member] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                payload = json.dumps(manifest).encode("utf-8")
            sink.writestr(info, payload)
    return out


@pytest.mark.parametrize("sql,value", [
    ("UPDATE chapters SET input_path = ? WHERE id = 2", UNC),
    ("UPDATE chapters SET input_path = ? WHERE id = 2", r"C:\Windows\win.ini"),
    ("UPDATE chapters SET input_path = ? WHERE id = 2", r"..\..\ngoai_du_an\1.txt"),
    ("UPDATE chapters SET output_mp3 = ? WHERE id = 1", r"C:\Public\Documents\ngoai_du_an.mp3"),
    ("UPDATE chapters SET output_mp3 = ? WHERE id = 1", "//attacker.example/s/x.mp3"),
    ("UPDATE segments SET wav_path = ? WHERE id = 3", r"\\attacker.example\s\x.wav"),
])
def test_a_project_file_with_a_path_outside_the_project_is_refused_whole(tmp_path: Path, sql: str, value: str,
                                                                       no_network_io) -> None:
    bad = _tampered(tmp_path, sql, value)
    library = tmp_path / "thu_vien"
    with ProjectFile(bad) as opened, pytest.raises(ProjectFileError, match="trỏ ra ngoài"):
        opened.open_into(library)
    assert list(library.iterdir()) == []  # không mở dở: không thư mục dự án, không thư mục tạm
    assert no_network_io == []


def test_a_path_under_the_old_root_that_climbs_out_is_refused(tmp_path: Path) -> None:
    root = str((tmp_path / "may_cu" / "sach_thu").resolve())
    bad = _tampered(tmp_path, "UPDATE chapters SET output_mp3 = ? WHERE id = 1", root + r"\output\..\..\..\ngoai.mp3")
    with ProjectFile(bad) as opened, pytest.raises(ProjectFileError, match="trỏ ra ngoài"):
        opened.open_into(tmp_path / "thu_vien")


def test_the_studio_reports_the_refusal_and_opens_nothing(tmp_path: Path) -> None:
    from abook.webui.server import ApiError
    from tests.test_project_file import _app

    bad = _tampered(tmp_path, "UPDATE chapters SET input_path = ? WHERE id = 2", UNC)
    library = tmp_path / "thu_vien"
    library.mkdir()
    app = _app(tmp_path, library)
    with pytest.raises(ApiError, match="trỏ ra ngoài"):
        app.open_book_file(str(bad))
    assert app.library.projects() == []


def test_listening_only_import_also_refuses_the_workbook_before_writing_a_book(tmp_path, no_network_io):
    bad = _tampered(tmp_path, "UPDATE chapters SET input_path=? WHERE id=2", UNC)
    library = tmp_path / "listen_only"
    with ProjectFile(bad) as opened, pytest.raises(ProjectFileError, match="trỏ ra ngoài"):
        opened.extract(library)
    assert not library.exists()
    assert no_network_io == []


@pytest.mark.parametrize("value", [UNC, r"C:\ngoai_du_an\1.txt", r"..\ngoai_du_an\1.txt"])
def test_containment_is_required_even_if_source_change_detection_is_disabled(tmp_path, value, no_network_io):
    fake, pipeline = _pipeline(tmp_path)
    fake.settings["safety"]["stop_book_on_source_change"] = False
    with pytest.raises(RuntimeError, match="not allowed"):
        pipeline._validate_chapter_source(fake, {"input_path": value})
    assert no_network_io == []


# ---- lớp hai: chỗ đọc / ghi theo sổ --------------------------------------------------------------------------------


def _book(tmp_path: Path, input_path: str) -> Path:
    from tests.test_webui_listen_and_sync import make_project

    project = make_project(tmp_path / "lib")
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("DELETE FROM segments WHERE chapter_id = 2")  # chương chưa tách câu: tên lấy từ dòng đầu file nguồn
        db.execute("UPDATE chapters SET input_path = ? WHERE id = 2", (input_path,))
    return project


@pytest.mark.parametrize("value", BAD_INPUTS)
def test_the_chapter_list_never_reads_a_source_it_may_not(tmp_path: Path, value: str, no_network_io) -> None:
    project = _book(tmp_path, value)
    store.listing_cache.forget(("chapter_names", str(project)))
    with store.closing(store.connect(project)) as connection:
        names = store.chapter_names(connection, project)
    assert names[2]["subtitle"] in (None, "")
    assert store.chapter_source_text(project, 2) is None
    assert no_network_io == []


def test_the_chapter_list_still_reads_a_local_source(tmp_path: Path) -> None:
    source = tmp_path / "nguon" / "646.txt"
    source.parent.mkdir()
    source.write_text("Chương 646 - Trở về (2)\n\nChưa thu.\n", encoding="utf-8")
    project = _book(tmp_path, str(source))
    source2 = project / "sources" / "646.txt"
    source2.parent.mkdir(exist_ok=True)
    source2.write_bytes(source.read_bytes())
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("UPDATE chapters SET input_path=? WHERE id=2", (str(source2),))
    assert store.chapter_source_text(project, 2).startswith("Chương 646")


def test_the_audio_locator_never_probes_a_network_path(tmp_path: Path, no_network_io) -> None:
    project = tmp_path / "sach"
    (project / "work").mkdir(parents=True)
    assert store.segment_audio(project, r"\\attacker.example\s\work\x.wav") is None
    assert store.segment_audio(project, r"C:\ngoai_du_an\x.wav") is None
    assert no_network_io == []


def _pipeline(root: Path):
    from abook.pipeline import BookPipeline

    fake = SimpleNamespace(paths=SimpleNamespace(root=root), settings={"safety": {"stop_book_on_source_change": True}})
    fake._book_file = BookPipeline._book_file.__get__(fake)
    return fake, BookPipeline


@pytest.mark.parametrize("value", [UNC, r"C:\Public\ngoai_du_an.mp3", r"{root}\..\ngoai_du_an.mp3", "x.mp3"])
def test_the_pipeline_never_writes_a_chapter_outside_the_book(tmp_path: Path, value: str, no_network_io) -> None:
    fake, _ = _pipeline(tmp_path)
    with pytest.raises(RuntimeError, match="ngoài thư mục sách"):
        fake._book_file(value.format(root=tmp_path))
    assert fake._book_file(str(tmp_path / "output" / "chapters" / "1.mp3")) == tmp_path / "output" / "chapters" / "1.mp3"
    assert no_network_io == []


@pytest.mark.parametrize("value", BAD_INPUTS)
def test_the_pipeline_never_reads_a_source_it_may_not(tmp_path: Path, value: str, no_network_io) -> None:
    fake, pipeline = _pipeline(tmp_path)
    with pytest.raises(RuntimeError, match="not allowed"):
        pipeline._validate_chapter_source(fake, {"input_path": value, "input_size": 1, "input_sha256": "0"})
    assert no_network_io == []


def test_the_pipeline_has_real_audio_is_false_for_a_network_wav(tmp_path: Path, no_network_io) -> None:
    fake, pipeline = _pipeline(tmp_path)
    assert pipeline._has_real_audio(fake, {"wav_path": UNC, "wav_sha256": "0"}) is False
    assert no_network_io == []


@pytest.mark.parametrize("column,value", [("output_mp3", UNC), ("input_path", UNC), ("input_path", r"C:\Windows\win.ini")])
def test_the_worker_refuses_a_project_with_a_path_it_may_not_touch(tmp_path: Path, column: str, value: str,
                                                                  no_network_io) -> None:
    from abook import worker
    from abook.models import ProjectPaths

    paths = ProjectPaths.build(tmp_path / "sach")
    chapter = {"output_mp3": str(paths.chapters / "1.mp3"), "input_path": str(tmp_path / "1.txt"),
               "input_size": 1, "input_sha256": "0", column: value}
    db = SimpleNamespace(list_chapters=lambda: [chapter])
    with pytest.raises(RuntimeError):
        worker._validate_project_inputs(paths, db, {"safety": {"stop_book_on_source_change": True}})
    assert no_network_io == []
