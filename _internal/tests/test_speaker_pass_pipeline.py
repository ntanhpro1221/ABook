"""Lượt "người nói từng câu" trong dây chuyền (speaker_pass.SpeakerPass + ProjectDB + pipeline): không model thật.

Ollama được thay bằng bản giả đọc đúng đề (JSON sau dòng tiêu đề khối, câu có "dich": true) rồi trả nhãn đã định theo CHỮ của câu.
Bộ đếm token được thay bằng bộ đếm ký tự (tests/test_speaker_pass_prompts.py đã kiểm tokenizer thật trùng từng byte).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import requests

import abook.pipeline as pipeline_module
from abook import speaker_pass as sp
from abook.analysis import AnalysisModelDigestError, AnalysisRequestStopped, OllamaBookAnalyzer
from abook.config import build_settings, validate_settings
from abook.database import ProjectDB
from abook.quality_policy import (
    ANALYSIS_CASTING_IMPLEMENTATION_FILES,
    QUALITY_IMPLEMENTATION_FILES,
    build_quality_policy,
)

ANALYZER = "abook-analyzer:v5"


class CharCounter:
    kind = "chars/3"

    @staticmethod
    def count(system: str, user: str) -> int:
        return math.ceil(len(sp._template(system, user)) / 3)


class Crash(BaseException):
    """Tiến trình chết giữa lượt (BaseException để không ai nuốt)."""


class FakeOllama:
    """Phiên HTTP giả: /api/tags (digest), /api/chat (đọc đề, trả nhãn theo chữ câu đích), /api/generate (nhả model)."""

    def __init__(self, labels: dict[str, str], digest: str = "sha256:speaker-v1") -> None:
        self.labels, self.digest = labels, digest
        self.prompts: list[str] = []
        self.payloads: list[dict] = []
        self.unloaded: list[str] = []
        self.fail_after: int | None = None       # sau chừng này lời gọi /api/chat thì "chết"
        self.transport_faults = 0                # số lần /api/chat đầu rớt kết nối
        self.digest_after_chat: str | None = None  # digest đổi sau lời gọi chat đầu

    def get(self, url: str, timeout: float = 0) -> Any:
        assert url.endswith("/api/tags")
        body = {"models": [{"name": sp.SPEAKER_MODEL, "digest": self.digest}, {"name": ANALYZER, "digest": "sha256:analysis"}]}
        return SimpleNamespace(ok=True, raise_for_status=lambda: None, json=lambda: body)

    def post(self, url: str, json: dict | None = None, timeout: Any = None, **_kw: Any) -> Any:  # noqa: A002
        if url.endswith("/api/generate"):
            self.unloaded.append(json["model"])
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {})
        assert url.endswith("/api/chat")
        if self.transport_faults:
            self.transport_faults -= 1
            raise requests.ConnectionError("rớt")
        if self.fail_after is not None and len(self.prompts) >= self.fail_after:
            raise Crash()
        self.payloads.append(json)
        user = json["messages"][1]["content"]
        self.prompts.append(user)
        rows = __import__("json").loads(user.split(sp.HEADER_PQ + "\n", 1)[1])
        target = next(row for row in rows if row.get("dich"))
        label = self.labels.get(target["text"], "UNKNOWN")
        if self.digest_after_chat is not None:
            self.digest = self.digest_after_chat
        body = {"message": {"content": __import__("json").dumps({"speaker": label}, ensure_ascii=False)}}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)


# Hai chương. Chữ câu là khoá để fake trả nhãn; nhãn gốc của "model phân tích" (cột speaker) cố tình KHÁC nhãn lượt này.
CHAPTERS = [
    ("Chương 1", [
        ("narration", "Trời sáng.", "NARRATOR"),
        ("dialogue", "“Chào buổi sáng.”", "SAI_1"),
        ("narration", "Lan cười.", "NARRATOR"),
        ("dialogue", "“Dậy đi nào.”", "SAI_2"),
        ("thought", "‘Hôm nay mình sẽ ổn.’", "SAI_3"),
        ("dialogue", "“Ai đó?”", "NPC_LOCAL::gốc"),
    ]),
    ("Chương 2", [
        ("narration", "Mưa rơi.", "NARRATOR"),
        ("dialogue", "“Mưa to quá.”", "SAI_4"),
        ("dialogue", "“Ừ.”", "SAI_5"),
    ]),
    ("Chương 3", [("narration", "Không ai nói gì cả.", "NARRATOR")]),
]
LABELS = {
    "“Chào buổi sáng.”": "Minh", "“Dậy đi nào.”": "Lan", "‘Hôm nay mình sẽ ổn.’": "Lan", "“Ai đó?”": "NPC_LOCAL:người gác",
    "“Mưa to quá.”": "Minh", "“Ừ.”": "Lan",
}


def make_project(root: Path, *, settings: dict | None = None) -> ProjectDB:
    root.mkdir(parents=True, exist_ok=True)
    db = ProjectDB(root / "project.sqlite3")
    if db.speaker_pass_lock() is None and not db.list_chapters():
        db.initialize_book(title="Thử", project_root=root, settings=settings or {}, settings_hash="s", input_manifest_hash="m")
        for index, (title, lines) in enumerate(CHAPTERS, 1):
            source = root / f"{index:03d}.txt"
            source.write_bytes(b"x")
            chapter = db.ensure_chapters([{"chapter_index": index, "title": title, "input_path": source, "input_sha256": "x",
                                           "input_size": 1, "output_mp3": root / f"{index:03d}.mp3"}])[0]
            db.replace_chapter_segments(chapter, [
                {"stable_id": f"c{index}s{seq}", "seq": seq, "paragraph_index": seq, "text": text, "text_sha256": f"t{index}{seq}",
                 "kind_hint": kind} for seq, (kind, text, _speaker) in enumerate(lines)])
            with db.transaction() as conn:
                for seq, (kind, _text, speaker) in enumerate(lines):
                    conn.execute("UPDATE segments SET kind=?, speaker=?, status='analyzed' WHERE stable_id=?",
                                 (kind, speaker, f"c{index}s{seq}"))
    return db


def pass_settings(**overrides: Any) -> dict:
    return build_settings("high_quality", {"analysis": {"model": ANALYZER}, **overrides})


def make_pass(db: ProjectDB, ollama: FakeOllama, monkeypatch: pytest.MonkeyPatch, settings: dict | None = None,
              log: list[str] | None = None) -> sp.SpeakerPass:
    settings = settings or pass_settings()
    monkeypatch.setattr(sp, "find_tokenizer", lambda _root: Path("tokenizer.json"))
    monkeypatch.setattr(sp, "TokenCounter", lambda _path: CharCounter())
    messages = log if log is not None else []
    analyzer = OllamaBookAnalyzer(settings, db, messages.append)
    analyzer.session = ollama
    monkeypatch.setattr(sp.SpeakerPass, "_sleep", staticmethod(lambda _seconds: None))
    return sp.SpeakerPass(analyzer, db, settings, messages.append, runtime_root=Path("runtime"))


def speakers(db: ProjectDB) -> list[list[str]]:
    return [[str(row["speaker"]) for row in db.list_segments(chapter_id=int(chapter["id"]))] for chapter in db.list_chapters()]


# ---- bản chất của lượt ------------------------------------------------------------------------------------------------

def test_the_pass_replaces_speakers_chapter_by_chapter_and_keeps_the_analysis_labels(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    progress: list[tuple[int, int, int, int]] = []
    speaker_pass = make_pass(db, ollama, monkeypatch)
    assert speaker_pass.enabled and speaker_pass.pending()

    made = speaker_pass.run(lambda: False, progress=lambda *args: progress.append(args))

    assert made == 3 and not speaker_pass.pending()
    assert speakers(db) == [
        ["NARRATOR", "Minh", "NARRATOR", "Lan", "Lan", "NPC_LOCAL::người gác"],   # nhãn cục bộ về dạng lưu `NPC_LOCAL::x`
        ["NARRATOR", "Minh", "Lan"],
        ["NARRATOR"],
    ]
    kinds = [str(row["kind"]) for row in db.list_segments()]
    assert kinds.count("thought") == 1 and kinds.count("dialogue") == 5, "kind giữ nguyên"
    with db.connect() as conn:
        saved = {str(r["analysis_speaker"]): str(r["pass_speaker"]) for r in conn.execute("SELECT * FROM speaker_pass_labels")}
        chapters = [dict(r) for r in conn.execute("SELECT * FROM speaker_pass_chapters ORDER BY chapter_id")]
    assert saved == {"SAI_1": "Minh", "SAI_2": "Lan", "SAI_3": "Lan", "NPC_LOCAL::gốc": "NPC_LOCAL::người gác", "SAI_4": "Minh",
                     "SAI_5": "Lan"}, "nhãn gốc giữ để so"
    assert [c["spoken_lines"] for c in chapters] == [4, 2, 0] and [c["changed_lines"] for c in chapters] == [4, 2, 0]
    assert progress[0] == (0, 3, 0, 0) and progress[-1] == (3, 3, 0, 0)
    assert sorted({p[0] for p in progress}) == [0, 1, 2, 3], "tiến độ theo chương đã xong"
    lock = db.speaker_pass_lock()
    assert lock is not None and (lock["model_name"], lock["model_digest"]) == (sp.SPEAKER_MODEL, "sha256:speaker-v1")
    assert lock["analysis_model"] == ANALYZER and lock["tokenizer_sha256"] == sp.TOKENIZER_SHA256


def test_the_request_is_the_measured_one_and_the_history_is_the_pass_labels(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    make_pass(db, ollama, monkeypatch).run(lambda: False)
    payload = ollama.payloads[0]
    assert payload == sp.chat_payload(sp.SPEAKER_MODEL, ollama.prompts[0])
    assert payload["options"] == {"temperature": 0, "seed": 0, "num_ctx": 16384, "num_predict": 512}
    assert payload["think"] is False and payload["stream"] is False and payload["format"] == sp.PQ_SCHEMA
    assert payload["messages"][0] == {"role": "system", "content": sp.SYSTEM_PQ}
    assert not any("SAI_" in prompt for prompt in ollama.prompts), "nhãn của model phân tích không bao giờ vào đề"
    assert "Các chương hiện tại: Chương 1" in ollama.prompts[0] and "Các chương hiện tại: Chương 2" in ollama.prompts[-1]
    assert any("- [thoại · Minh] “Chào buổi sáng.”" in prompt for prompt in ollama.prompts[1:]) or "Minh" in ollama.prompts[1]


def test_a_chapter_narrator_from_the_book_settings_heads_its_prompts(tmp_path: Path, monkeypatch) -> None:
    settings = pass_settings()
    settings["voices"]["first_person_identity"] = "Lan"
    settings["voices"]["first_person_chapters"] = {"2": ""}      # chương 2 kể ngôi ba
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    make_pass(db, ollama, monkeypatch, settings).run(lambda: False)
    first, second = ollama.prompts[0], ollama.prompts[-1]
    assert "Truyện kể ở ngôi thứ nhất" in first and "speaker=Lan" in first
    assert "Truyện kể ở ngôi thứ nhất" not in second and second.startswith("Các chương hiện tại: Chương 2\n\nNhân vật")


def test_a_book_without_a_paired_model_has_no_pass(tmp_path: Path, monkeypatch) -> None:
    assert build_settings("high_quality", {"analysis": {"model": ANALYZER}})["analysis"]["speaker_model"] == sp.SPEAKER_MODEL
    for model in ("qwen3:8b", "abook-analyzer:v4", "abook-analyzer:v3"):
        assert build_settings("high_quality", {"analysis": {"model": model}})["analysis"]["speaker_model"] == ""
    assert build_settings("fast")["analysis"]["speaker_model"] == sp.SPEAKER_MODEL  # cùng model phân tích mặc định -> cùng lượt
    assert build_settings("high_quality", {"analysis": {"model": ANALYZER, "speaker_model": ""}})["analysis"]["speaker_model"] == ""
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    off = make_pass(db, ollama, monkeypatch, build_settings("high_quality", {"analysis": {"model": "qwen3:8b"}}))
    assert not off.enabled and not off.pending() and off.run(lambda: False) == 0
    assert not ollama.prompts and speakers(db)[0][1] == "SAI_1"


def test_settings_only_accept_the_paired_speaker_model() -> None:
    settings = pass_settings()
    validate_settings(settings)
    for bad in ("abook-speaker:v9", "qwen3:8b", 7):
        settings["analysis"]["speaker_model"] = bad
        with pytest.raises(ValueError):
            validate_settings(settings)
    unpaired = build_settings("high_quality", {"analysis": {"model": "qwen3:8b"}})
    unpaired["analysis"]["speaker_model"] = sp.SPEAKER_MODEL
    with pytest.raises(ValueError):
        validate_settings(unpaired)


# ---- bền: crash / reopen / khoá --------------------------------------------------------------------------------------

def test_a_crash_inside_a_chapter_resumes_that_chapter_from_its_start(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "p"
    db = make_project(root)
    first = FakeOllama(LABELS)
    first.fail_after = 4 + 1                    # chương 1 xong (4 câu), chương 2 chết ở câu thứ hai
    with pytest.raises(Crash):
        make_pass(db, first, monkeypatch).run(lambda: False)
    assert db.speaker_pass_done_chapters() == {int(db.list_chapters()[0]["id"])}, "chương dở không có dòng kết quả"
    assert speakers(db)[0] == ["NARRATOR", "Minh", "NARRATOR", "Lan", "Lan", "NPC_LOCAL::người gác"]
    assert speakers(db)[1] == ["NARRATOR", "SAI_4", "SAI_5"], "chương dở còn nguyên nhãn gốc: không ghi nửa chương"

    reopened = make_project(root)               # mở lại sổ như tiến trình mới
    second = FakeOllama(LABELS)
    SpeakerResumed = make_pass(reopened, second, monkeypatch)
    assert SpeakerResumed.pending()
    assert SpeakerResumed.run(lambda: False) == 2
    assert len(second.prompts) == 2, "chỉ hỏi lại chương 2 (2 câu); chương 1 đã xong không hỏi lại"
    assert second.prompts[0] == first.prompts[4], "chương dở làm lại từ đầu, đề y hệt lượt trước"
    assert speakers(reopened)[1] == ["NARRATOR", "Minh", "Lan"]
    assert not SpeakerResumed.pending()
    again = FakeOllama(LABELS)
    assert make_pass(reopened, again, monkeypatch).run(lambda: False) == 0 and not again.prompts, "xong rồi thì không hỏi gì nữa"


def test_a_failed_commit_leaves_the_chapter_untouched(tmp_path: Path) -> None:
    db = make_project(tmp_path / "p")
    chapter = db.list_chapters()[0]
    rows = db.list_segments(chapter_id=int(chapter["id"]))
    good = (int(rows[1]["id"]), "SAI_1", "Minh")
    stale = (int(rows[3]["id"]), "KHÔNG PHẢI NHÃN HIỆN TẠI", "Lan")
    with pytest.raises(RuntimeError, match="CAS"):
        db.commit_speaker_pass_chapter(int(chapter["id"]), [good, stale], {"calls": 2}, seconds=1.0)
    assert speakers(db)[0][1] == "SAI_1", "giao dịch hoàn tác cả câu đã đúng"
    assert db.speaker_pass_done_chapters() == set()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM speaker_pass_labels").fetchone()[0] == 0
    # Narration không phải câu được hỏi: CAS từ chối đổi người nói của nó.
    with pytest.raises(RuntimeError, match="CAS"):
        db.commit_speaker_pass_chapter(int(chapter["id"]), [(int(rows[0]["id"]), "NARRATOR", "Minh")], {}, seconds=0.0)
    assert db.commit_speaker_pass_chapter(int(chapter["id"]), [good], {"calls": 1}, seconds=1.0) == 1
    with pytest.raises(RuntimeError, match="already committed"):
        db.commit_speaker_pass_chapter(int(chapter["id"]), [], {}, seconds=0.0)


def test_the_model_digest_is_locked_for_the_book(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "p"
    db = make_project(root)
    first = FakeOllama(LABELS)
    first.fail_after = 1
    with pytest.raises(Crash):
        make_pass(db, first, monkeypatch).run(lambda: False)
    assert db.speaker_pass_lock()["model_digest"] == "sha256:speaker-v1"
    swapped = FakeOllama(LABELS, digest="sha256:another-build")        # resume với model cùng tên nhưng nội dung khác
    with pytest.raises(RuntimeError, match="differs from what is locked"):
        make_pass(make_project(root), swapped, monkeypatch).run(lambda: False)
    assert not swapped.prompts, "fail-closed TRƯỚC khi hỏi câu nào"
    other = make_project(tmp_path / "q")
    odd = FakeOllama(LABELS)
    pass_ = make_pass(other, odd, monkeypatch)
    pass_.run(lambda: False)
    with pytest.raises(RuntimeError, match="differs"):
        other.lock_speaker_pass(model_name=sp.SPEAKER_MODEL, model_digest="sha256:speaker-v1", analysis_model="qwen3:8b",
                                tokenizer_sha256=sp.TOKENIZER_SHA256, algorithm=sp.ALGORITHM)


def test_a_digest_that_changes_between_requests_stops_the_pass(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    ollama.digest_after_chat = "sha256:swapped-mid-run"
    with pytest.raises(AnalysisModelDigestError, match="changed after speaker request"):
        make_pass(db, ollama, monkeypatch).run(lambda: False)
    assert db.speaker_pass_done_chapters() == set() and speakers(db)[0][1] == "SAI_1"


def test_stop_ends_the_pass_at_a_line_boundary_without_a_partial_chapter(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    asked = {"n": 0}

    def stop() -> bool:
        asked["n"] += 1
        return asked["n"] > 2

    with pytest.raises(AnalysisRequestStopped):
        make_pass(db, ollama, monkeypatch).run(stop)
    assert speakers(db)[0][1] == "SAI_1" and db.speaker_pass_done_chapters() == set()


def test_the_pass_never_runs_after_casting_is_locked(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    db.finalize_casting()
    ollama = FakeOllama(LABELS)
    log: list[str] = []
    assert make_pass(db, ollama, monkeypatch, log=log).run(lambda: False) == 0
    assert not ollama.prompts and any("casting đã khóa" in line for line in log)


def test_the_pass_refuses_to_run_while_segments_are_still_pending(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    with db.transaction() as conn:
        conn.execute("UPDATE segments SET status='pending' WHERE stable_id='c1s3'")
    with pytest.raises(sp.SpeakerPassError, match="phân tích xong"):
        make_pass(db, FakeOllama(LABELS), monkeypatch).run(lambda: False)


# ---- Ollama: quy ước transport -----------------------------------------------------------------------------------------

def test_a_dropped_connection_is_replayed_not_fatal(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    ollama.transport_faults = 2                      # đúng OLLAMA_TRANSPORT_RECONNECT_ATTEMPTS lần rớt
    log: list[str] = []
    assert make_pass(db, ollama, monkeypatch, log=log).run(lambda: False) == 3
    assert sum("Ollama rớt" in line for line in log) == 2 and speakers(db)[0][1] == "Minh"


def test_a_dead_server_is_revived_a_few_times_then_the_pass_stops_at_the_checkpoint(tmp_path: Path, monkeypatch) -> None:
    db = make_project(tmp_path / "p")
    ollama = FakeOllama(LABELS)
    ollama.transport_faults = 10_000
    revived = {"n": 0}
    speaker_pass = make_pass(db, ollama, monkeypatch)
    speaker_pass.analyzer.ensure_server = lambda: revived.__setitem__("n", revived["n"] + 1) or True
    with pytest.raises(sp.SpeakerPassError, match="không trả lời"):
        speaker_pass.run(lambda: False)
    assert revived["n"] >= sp.SERVER_REVIVALS and db.speaker_pass_done_chapters() == set()
    ollama.transport_faults = 0                     # Ollama sống lại: chạy tiếp bình thường
    assert speaker_pass.run(lambda: False) == 3


# ---- hỏi lại khi đáp hỏng -----------------------------------------------------------------------------------------------

def test_an_empty_answer_is_asked_twice_then_unknown() -> None:
    replies = iter(["không phải JSON", '{"speaker": "  "}'])
    asker = sp.Asker(lambda _user: next(replies))
    assert asker.ask_pq("đề") == ("UNKNOWN", 1)
    assert (asker.calls, asker.retries, asker.failed) == (2, 1, 1)
    replies = iter(['{"speaker": "  Lan   Anh "}'])
    ok = sp.Asker(lambda _user: next(replies))
    assert ok.ask_pq("đề") == ("Lan Anh", 0) and ok.calls == 1
    replies = iter(["{", '{"speaker": "Minh"}'])
    again = sp.Asker(lambda _user: next(replies))
    assert again.ask_pq("đề") == ("Minh", 0) and (again.calls, again.retries, again.failed) == (2, 1, 0)


def test_local_labels_are_stored_in_the_books_form() -> None:
    assert sp.db_label("NPC_LOCAL:lính gác 1") == "NPC_LOCAL::lính gác 1"
    assert sp.db_label("NPC_LOCAL::đã đúng dạng") == "NPC_LOCAL::đã đúng dạng"
    assert sp.db_label("Lan") == "Lan" and sp.db_label("UNKNOWN") == "UNKNOWN"


# ---- móc trong dây chuyền ----------------------------------------------------------------------------------------------

def test_the_pass_is_part_of_the_locked_implementation() -> None:
    assert "speaker_pass.py" in QUALITY_IMPLEMENTATION_FILES and "speaker_pass.py" in ANALYSIS_CASTING_IMPLEMENTATION_FILES
    assert build_quality_policy(build_settings())["algorithms"]["speaker_pass"] == sp.ALGORITHM


class _Analyzer:
    base_url = "http://ollama"

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.order: list[str] = []
        _Analyzer.instance = self

    def analyze_all(self, *_args: Any, **_kwargs: Any) -> None:
        _Order.events.append("analyze_all")

    def reconcile_local_speaker_identities(self, **_kw: Any) -> None:
        _Order.events.append("reconcile_local_speaker_identities")

    def reconcile_name_pronunciations(self, **_kw: Any) -> None:
        _Order.events.append("reconcile_name_pronunciations")

    def release_model(self) -> None:
        _Order.events.append("release_analysis_model")

    def unload(self) -> None:
        _Order.events.append("unload")


class _Order:
    events: list[str] = []


class _Stop(Exception):
    pass


def _pipeline(monkeypatch: pytest.MonkeyPatch, *, finalized: bool, pending: bool) -> Any:
    _Order.events = []
    monkeypatch.setattr(pipeline_module, "OllamaBookAnalyzer", _Analyzer)

    class FakePass:
        def __init__(self, analyzer: Any, db: Any, settings: dict, log: Any) -> None:
            _Order.events.append("speaker_pass_built")

        def pending(self) -> bool:
            return pending

        def run(self, stop_requested: Any, *, progress: Any, before_chapter: Any) -> int:
            _Order.events.append("speaker_pass")
            progress(1, 2, 3, 4)
            before_chapter(1)
            return 1

        def release_model(self) -> None:
            _Order.events.append("release_speaker_model")

    monkeypatch.setattr(pipeline_module, "SpeakerPass", FakePass)
    monkeypatch.setattr(pipeline_module, "build_registry_and_cast", lambda *_a, **_k: _Order.events.append("build_registry_and_cast"))
    book_updates: list[dict] = []
    db = SimpleNamespace(begin_run_generation=lambda: None, update_book=lambda **kw: book_updates.append(kw),
                         casting_is_finalized=lambda: finalized, finalize_casting=lambda: _Order.events.append("finalize_casting"),
                         list_segments=lambda: [{"status": "pending" if pending else "analyzed"}])
    pipeline = object.__new__(pipeline_module.BookPipeline)
    pipeline.db, pipeline.settings, pipeline.quality_policy_hash = db, {}, "x"
    pipeline.stop_requested = lambda: False
    emitted: list[tuple[str, dict]] = []
    pipeline.emit = lambda kind, payload: emitted.append((kind, payload))
    pipeline.after_analysis = None
    pipeline._completed_noop = False
    pipeline.log = lambda _message: None
    pipeline._recover = lambda: None
    pipeline._ensure_segments = lambda: None
    pipeline._state = lambda *_args: None
    pipeline._wait_pause_or_stop = lambda: None
    pipeline._resource_gate = lambda checkpoint, **kw: _Order.events.append(f"gate:{checkpoint}")
    pipeline._safe_export_reports = lambda **_kw: None

    def done(*_args: Any, **_kwargs: Any) -> None:
        raise _Stop

    pipeline.tts = SimpleNamespace(prepare_voice_presets=done)
    pipeline._book_updates, pipeline._emitted = book_updates, emitted
    return pipeline


def test_the_pass_sits_between_the_analysis_and_the_casting(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = _pipeline(monkeypatch, finalized=False, pending=True)
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    order = _Order.events
    assert order.index("analyze_all") < order.index("speaker_pass") < order.index("reconcile_local_speaker_identities")
    assert order.index("speaker_pass") < order.index("reconcile_name_pronunciations") < order.index("build_registry_and_cast")
    assert order.index("release_analysis_model") < order.index("speaker_pass"), "dỡ model phân tích trước khi nạp model người nói"
    assert order.index("speaker_pass") < order.index("release_speaker_model"), "nhả model người nói khi xong lượt"
    assert "gate:speaker pass chapter 1" in order
    assert ("speaker_pass_progress", {"done": 1, "total": 2, "lines_done": 3, "lines": 4}) in pipeline._emitted
    assert ("work_progress", {"label": "Xác định người nói từng câu", "done": 1, "total": 2}) in pipeline._emitted
    assert {"status": "analyzing", "stage": "speaker_pass"} in [{k: v for k, v in u.items() if k in {"status", "stage"}}
                                                                 for u in pipeline._book_updates]


def test_a_book_with_nothing_left_for_the_pass_goes_straight_to_the_casting(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = _pipeline(monkeypatch, finalized=False, pending=False)
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert "speaker_pass" not in _Order.events and "build_registry_and_cast" in _Order.events


def test_a_book_with_casting_already_locked_never_builds_the_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = _pipeline(monkeypatch, finalized=True, pending=True)
    with pytest.raises(_Stop):
        pipeline.run(recovery_already_run=True)
    assert "speaker_pass_built" not in _Order.events and "build_registry_and_cast" not in _Order.events
