"""Học sinh q06 của "Nghe ngay" chạy ở Python của Studio (webui/music_scene_student.py `serve` + `StudioChapterStudent`, webui/server.py
`_scene_student_mode`): bản cài không có torch nên mô hình nằm ở một tiến trình con giữ qua các chương. Không cần torch: tiến trình con GIẢ là
một gói `abook/webui/music_scene_student.py` nhỏ dựng trong thư mục mã, trả lời đúng giao thức (một dòng JSON mỗi chương) theo `script["mode"]`.
Bằng chứng tương đương với học sinh thật nằm ở scripts/music_nnstudio_check.py (cần gói model)."""
from __future__ import annotations

import io
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from abook.webui import music_scene_student as student
from tests.test_music_nnscene import _cues_when_ready, _scene_server

# Tiến trình con giả: `python -m abook.webui.music_scene_student --serve --package P [--cache C] --threads N`, cwd = thư mục mã giả.
FAKE_CHILD = '''
import json, os, sys, time
args = sys.argv[1:]
if args[args.index("--package") + 1].endswith("broken"):
    print(json.dumps({"error": "thieu torch"}), flush=True)
    raise SystemExit(2)
for line in sys.stdin:
    request = json.loads(line)
    mode = request["script"].get("mode", "ok")
    scenes = request["scenes"]
    if mode == "crash":
        os._exit(3)
    if mode == "garbage":
        print("khong phai json", flush=True)
        continue
    if mode == "hang":
        time.sleep(600)
    if mode == "error":
        print(json.dumps({"items": None, "error": "ValueError: hong"}), flush=True)
        continue
    if mode == "unusable":
        print(json.dumps({"items": None}), flush=True)
        continue
    items = [{"chapterId": s["chapterId"], "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "dV": 0.1, "dE": 0.3, "dT": 0.2,
              "chapterV": 0.3, "pid": os.getpid(), "argv": args} for s in scenes]
    print(json.dumps({"items": items}), flush=True)
'''


@pytest.fixture
def code_root(tmp_path: Path) -> Path:
    root = tmp_path / "code"
    package = root / "abook" / "webui"
    package.mkdir(parents=True)
    (root / "abook" / "__init__.py").write_bytes(b"")
    (package / "__init__.py").write_bytes(b"")
    (package / "music_scene_student.py").write_bytes(FAKE_CHILD.encode("utf-8"))
    return root


def make(code_root: Path, tmp_path: Path, package: str = "pkg") -> student.StudioChapterStudent:
    worker = student.StudioChapterStudent(sys.executable, code_root, {"PYTHONPATH": str(code_root)}, tmp_path / package, tmp_path / "e.npz", threads=2)
    worker.POLL_SECONDS = 0.05
    worker.KILL_AFTER_SECONDS = 2.0
    worker.CLOSE_WAIT_SECONDS = 5.0
    return worker


def request(mode: str = "ok") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return {"chapterId": 1, "mode": mode, "segments": []}, [{"chapterId": 1, "firstSegment": 1, "lastSegment": 4},
                                                          {"chapterId": 1, "firstSegment": 5, "lastSegment": 9}]


def test_a_reply_becomes_the_items_and_the_one_process_serves_every_chapter(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    try:
        script, scenes = request()
        first = worker.chapter(script, scenes)
        second = worker.chapter(script, scenes)
        assert first is not None and [item["firstSegment"] for item in first] == [1, 5] and first[0]["dV"] == 0.1
        assert second is not None and second[0]["pid"] == first[0]["pid"], "model giữ nguyên qua các chương: không sinh lại tiến trình"
        argv = first[0]["argv"]
        assert argv[argv.index("--threads") + 1] == "2" and argv[argv.index("--cache") + 1] == str(tmp_path / "e.npz")
        assert argv[argv.index("--package") + 1] == str(tmp_path / "pkg") and "--serve" in argv
        assert worker.stopped is False
        worker.save()  # tiến trình con đã ghi đệm: không làm gì, không ném
    finally:
        worker.close()


def test_an_error_reply_or_an_unusable_chapter_gives_none_and_the_process_keeps_serving(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    try:
        good = worker.chapter(*request())
        assert good is not None
        assert worker.chapter(*request("error")) is None
        assert worker.chapter(*request("unusable")) is None
        again = worker.chapter(*request())
        assert again is not None and again[0]["pid"] == good[0]["pid"], "lỗi một chương không giết tiến trình"
        assert worker.broken is False
    finally:
        worker.close()


def test_a_crash_gives_none_for_that_chapter_and_the_next_chapter_respawns(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    try:
        first = worker.chapter(*request())
        assert first is not None
        assert worker.chapter(*request("crash")) is None
        after = worker.chapter(*request())
        assert after is not None and after[0]["pid"] != first[0]["pid"]
    finally:
        worker.close()


def test_a_stdout_line_that_is_not_json_gives_none_and_the_process_is_not_trusted_again(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    try:
        first = worker.chapter(*request())
        assert first is not None
        process = worker._process
        assert worker.chapter(*request("garbage")) is None
        assert process is not None and process.poll() is not None, "giao thức lệch: tiến trình bị giết"
        after = worker.chapter(*request())
        assert after is not None and after[0]["pid"] != first[0]["pid"]
    finally:
        worker.close()


def test_stopping_in_the_middle_of_a_request_kills_the_process_and_flags_stopped(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    flag = threading.Event()
    try:
        warm = worker.chapter(*request())
        assert warm is not None
        process = worker._process
        threading.Timer(0.6, flag.set).start()
        started = time.time()
        assert worker.chapter(*request("hang"), stop_requested=flag.is_set) is None
        assert time.time() - started < 8, "dừng không chờ tiến trình con xong"
        assert worker.stopped is True
        assert process is not None and process.poll() is not None, "tiến trình đã mất"
        worker.stopped = False
        after = worker.chapter(*request())
        assert after is not None and after[0]["pid"] != warm[0]["pid"], "chương kế sinh lại"
    finally:
        worker.close()


def test_asking_to_stop_before_sending_never_starts_a_process(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    assert worker.chapter(*request(), stop_requested=lambda: True) is None
    assert worker.stopped is True and worker._process is None


def test_close_lets_the_process_finish_on_end_of_input(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path)
    assert worker.chapter(*request()) is not None
    process = worker._process
    worker.close()
    assert process is not None and process.poll() == 0 and worker._process is None
    worker.close()  # lần hai: không ném


def test_a_child_that_reports_an_error_at_start_up_is_not_respawned(code_root: Path, tmp_path: Path) -> None:
    worker = make(code_root, tmp_path, package="broken")
    try:
        assert worker.chapter(*request()) is None
        assert worker.broken is True and worker._process is None
        assert worker.chapter(*request()) is None and worker._process is None, "không sinh lại tiến trình đã báo thiếu torch / gói"
    finally:
        worker.close()


def test_a_missing_python_is_none_not_an_exception(code_root: Path, tmp_path: Path) -> None:
    worker = student.StudioChapterStudent(tmp_path / "khong_co" / "python.exe", code_root, {}, tmp_path / "pkg", None)
    assert worker.chapter(*request()) is None and worker.stopped is False
    worker.close()


# ---- `serve`: phía tiến trình con thật (không cần torch: học sinh thay bằng đối tượng giả) -------------------------------------


class FakeStudent:
    instances: list["FakeStudent"] = []

    def __init__(self, directory: Path, cache_path: Path | None, *, log: Any = None, threads: int = 0) -> None:
        self.calls, self.saved, self.closed, self.threads, self.cache_path = 0, 0, False, threads, cache_path
        FakeStudent.instances.append(self)

    def chapter(self, script: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        self.calls += 1
        if script.get("explode"):
            raise RuntimeError("nổ")
        return None if script.get("unusable") else [{"firstSegment": scene["firstSegment"], "dV": 0.5} for scene in scenes]

    def save(self) -> None:
        self.saved += 1

    def close(self) -> None:
        self.closed = True


def run_serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, lines: list[dict[str, Any]], *, available: bool = True) -> tuple[int, list[dict[str, Any]]]:
    FakeStudent.instances.clear()
    monkeypatch.setattr(student, "available", lambda: available)
    monkeypatch.setattr(student, "ChapterStudent", FakeStudent)
    monkeypatch.setattr(student, "_directory", None)
    monkeypatch.setattr(sys, "stdout", sys.stdout)  # `serve` đổi sys.stdout sang stderr: monkeypatch trả lại
    source = io.StringIO("".join(json.dumps(line) + "\n" for line in lines) + "\n")
    sink = io.StringIO()
    code = student.serve(tmp_path / "pkg", tmp_path / "e.npz", 2, stdin=source, stdout=sink)
    return code, [json.loads(line) for line in sink.getvalue().splitlines()]


def test_serve_answers_one_json_line_per_chapter_saves_after_each_and_closes_at_end_of_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenes = [{"chapterId": 1, "firstSegment": 1, "lastSegment": 2}]
    code, replies = run_serve(monkeypatch, tmp_path, [{"script": {"a": 1}, "scenes": scenes}, {"script": {"unusable": 1}, "scenes": scenes},
                                                       {"script": {"explode": 1}, "scenes": scenes}, {"script": {"a": 2}, "scenes": scenes}])
    assert code == 0
    assert replies[0] == {"items": [{"firstSegment": 1, "dV": 0.5}]} and replies[1] == {"items": None}
    assert replies[2]["items"] is None and "RuntimeError" in replies[2]["error"], "chương lỗi: một dòng báo lỗi, vẫn phục vụ"
    assert replies[3] == {"items": [{"firstSegment": 1, "dV": 0.5}]} and len(replies) == 4
    (worker,) = FakeStudent.instances
    assert worker.threads == 2 and worker.cache_path == tmp_path / "e.npz"
    assert worker.saved >= 3 and worker.closed, "ghi đệm sau mỗi chương và lúc đóng"


def test_serve_with_no_package_or_no_torch_says_so_on_the_first_line_and_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, replies = run_serve(monkeypatch, tmp_path, [{"script": {}, "scenes": []}], available=False)
    assert code == 2 and len(replies) == 1 and "error" in replies[0] and "items" not in replies[0]
    assert not FakeStudent.instances


def test_the_main_entry_point_still_needs_a_project_unless_it_serves(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        student.main([])
    assert error.value.code == 2
    with pytest.raises(SystemExit):
        student.main(["--serve"])  # thiếu --package
    served: list[tuple[Any, ...]] = []
    monkeypatch.setattr(student, "serve", lambda *a: served.append(a) or 0)
    assert student.main(["--serve", "--package", "p", "--cache", "c.npz", "--threads", "3"]) == 0
    assert served == [(Path("p"), Path("c.npz"), 3)]


# ---- máy chủ: chọn đường học sinh -----------------------------------------------------------------------------------------------


class FakeStudio:
    def __init__(self, python: Path | str, root: Path, installed: bool = True) -> None:
        self.python, self.app_root, self._installed = python, root, installed

    def installed(self) -> bool:
        return self._installed

    def environment(self, code: Path | None = None) -> dict[str, str]:
        return {"PYTHONPATH": str(code or self.app_root)}


@pytest.mark.parametrize(("available", "present", "studio", "expected"), [
    (True, True, None, "local"),
    (True, False, "installed", "local"),  # torch + gói tại chỗ thắng Studio
    (False, True, "installed", "studio"),
    (False, True, "not installed", "none"),
    (False, True, None, "none"),
    (False, False, "installed", "none"),
])
def test_the_scene_student_runs_here_in_the_studio_or_not_at_all(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code_root: Path,
                                                                 available: bool, present: bool, studio: str | None, expected: str) -> None:
    app, _book, server = _scene_server(tmp_path)
    try:
        monkeypatch.setattr(student, "available", lambda: available)
        monkeypatch.setattr(student, "present", lambda: present)
        app.studio = None if studio is None else FakeStudio(sys.executable, code_root, installed=studio == "installed")
        assert app._scene_student_mode() == expected
        assert app.music_playlists()["scene"] == {"student": expected != "none"}
    finally:
        server.stop()


def test_in_studio_mode_the_builder_uses_the_studio_child_and_the_plan_has_student_scenes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                                                         code_root: Path) -> None:
    app, book, server = _scene_server(tmp_path)
    try:
        monkeypatch.setattr(student, "available", lambda: False)
        monkeypatch.setattr(student, "present", lambda: True)
        monkeypatch.setattr(student, "package_dir", lambda: tmp_path / "pkg")
        monkeypatch.setattr(student, "package_sha", lambda directory=None: "sha-q06")
        app.studio = FakeStudio(sys.executable, code_root)
        monkeypatch.setattr(student.StudioChapterStudent, "POLL_SECONDS", 0.05)
        reply = _cues_when_ready(server, book)
        assert reply["scene"] is True and reply["cues"]
        records = list((app.music_dir / "scene").glob("*/*/1.json"))
        assert records, "plan của chương đã ghi"
        scenes = json.loads(records[0].read_text(encoding="utf-8"))["scenes"]
        assert scenes and all(scene.get("moodSource") == "student" for scene in scenes), "mọi cảnh có học sinh (tiến trình con giả đã trả mục)"
        deadline = time.time() + 10
        while app._scene_student is not None and time.time() < deadline:  # hàng cạn -> `_close_scene_student` đóng tiến trình con
            time.sleep(0.1)
        assert app._scene_student is None
    finally:
        server.stop()
