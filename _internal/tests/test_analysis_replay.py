"""Stop the analysis anywhere, resume it, and get the book an unstopped run gets.

AUDIT resume_determinism (2026-10-06) split "a resume gives a different book" in two: the
model answering the same request differently after a cold start (an Ollama matter, not
tested here - it needs the GPU), and the app rebuilding a different request or a different
attempt after a stop. This file pins the second half on the CPU.

A fake Ollama answers from the request alone, so it is a pure function of what was asked.
The baseline runs the whole book without stopping and records every request hash. Each
resumed run stops somewhere - after k batches, inside a director critic call, between two
generator attempts - and continues in a fresh analyzer whose fake *fails on any request the
baseline never sent*. If the app rebuilt one byte of state differently (the known-characters
list, carried feedback, an attempt number, a critic seed), the request hash would differ and
the fake would say so.

All text is synthetic: the repository is public.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

import pytest

from abook.analysis import (
    DIRECTOR_CRITIC_SYSTEM_PROMPT,
    LOW_CONFIDENCE_ISSUE_CODE,
    SYSTEM_PROMPT,
    AnalysisRequestStopped,
    OllamaBookAnalyzer,
    analysis_request_hash,
)
from abook.config import build_settings
from abook.database import ProjectDB, canonical_analysis_critic_source_anchors
from abook.io_utils import sha256_text

DIGEST = "sha256:replay-test-digest"

# Rows whose answer the fake makes interesting, chosen by their text:
#   INCOMPLETE - attempt 1 of its batch drops one id, so the batch needs attempt 2;
#   DISPUTED   - the critic wants pace "fast"; the generator only says so once the critic's
#                feedback is in its prompt, so attempt 1 is rejected and attempt 2 accepted;
#   GARBLED    - the first critic attempt on its batch answers for the wrong candidate, a
#                retryable invalid verdict, so critic attempt 2 (another seed) decides;
#   SPLIT      - attempt 1 is under the confidence floor, attempt 2 (now carrying that
#                feedback) runs out of output budget, so the batch is split in two and the
#                half holding SPLIT carries the feedback with it - across a stop, too.
INCOMPLETE = "Ngọn đèn bàn vẫn sáng."
DISPUTED = "Anh bước nhanh qua hành lang dài."
GARBLED = "Cánh cửa sổ khép lại."
SPLIT = "Gió lùa qua khe cửa."
SPLIT_INDEX = 6
NAMES = ("Lam", "Mai", "Tùng")
# Carried in from an earlier part of the series (port_casting): the counts a resume used to
# lose (AUDIT R4), and a tie between two carried characters that only `id` can order.
CARRIED = (("Mai", "female", 7), ("Hà", "female", 3), ("Tùng", "male", 3))


def _book_rows(chapter: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paragraph = 0
    for index in range(10):
        name = NAMES[(index + chapter) % len(NAMES)]
        texts: list[tuple[str, str]] = [
            ("narration", f"{name} mở cuốn sổ ghi chép số {chapter}{index}."),
            ("dialogue", f"“Trang {index} của chương {chapter} đã xong rồi,” {name} nói."),
        ]
        if chapter == 1 and index == 2:
            texts[0] = ("narration", INCOMPLETE)
        if chapter == 1 and index == 5:
            texts[0] = ("narration", DISPUTED)
        if chapter == 2 and index == 3:
            texts[0] = ("narration", GARBLED)
        if chapter == 2 and index == SPLIT_INDEX:
            texts[0] = ("narration", SPLIT)
        for kind, text in texts:
            rows.append(
                {
                    "stable_id": f"c{chapter}s{len(rows):03d}",
                    "seq": len(rows),
                    "paragraph_index": paragraph,
                    "text": text,
                    "text_sha256": sha256_text(text),
                    "kind_hint": kind,
                }
            )
            paragraph += 1
    return rows


def _project(path: Path) -> ProjectDB:
    db = ProjectDB(path / "project.sqlite3")
    db.initialize_book(
        title="Sổ tay",
        project_root=path,
        settings={},
        settings_hash="settings",
        input_manifest_hash="manifest",
    )
    chapter_ids = db.ensure_chapters(
        [
            {
                "chapter_index": index,
                "title": f"Chương {index}",
                "input_path": path / f"{index}.txt",
                "input_sha256": f"source{index}",
                "input_size": 1,
                "output_mp3": path / f"{index}.mp3",
            }
            for index in (1, 2)
        ]
    )
    for chapter, chapter_id in zip((1, 2), chapter_ids):
        db.replace_chapter_segments(chapter_id, _book_rows(chapter))
    with db.connect() as conn:
        for name, gender, mentions in CARRIED:
            conn.execute(
                "INSERT INTO characters(canonical_name,display_name,gender,age,personality,"
                "importance,mention_count,confidence,locked,created_at,updated_at) "
                "VALUES(?,?,?,'adult','','main',?,1,0,0,0)",
                (name, name, gender, mentions),
            )
    return db


def _json_after(text: str, marker: str) -> Any:
    start = text.index(marker) + len(marker)
    value, _end = json.JSONDecoder().raw_decode(text[start:])
    return value


def _generator_answer(body: dict[str, Any]) -> tuple[dict[str, Any], str]:
    prompt = str(body["prompt"])
    rows = _json_after(prompt, "Các đoạn liên tiếp:\n")
    told_fast = "DIRECTOR_FIELD_MISMATCH" in prompt
    told_floor = LOW_CONFIDENCE_ISSUE_CODE in prompt
    segments = []
    for row in rows:
        text = str(row["text"])
        dialogue = row["hint"] == "dialogue"
        speaker = next((name for name in NAMES if text.startswith(name) or f" {name} " in text), "")
        segments.append(
            {
                "id": row["id"],
                "kind": "dialogue" if dialogue else "narration",
                "speaker": speaker if dialogue and speaker else "NARRATOR",
                "gender": ("female" if speaker == "Mai" else "male") if dialogue else "unknown",
                "age": "adult" if dialogue else "unknown",
                "emotion": "neutral",
                "intensity": 1,
                "pace": "fast" if text == DISPUTED and told_fast else "normal",
                "volume": "normal",
                "confidence": 0.5 if text == SPLIT and not told_floor else 0.9,
                "personality_hint": "",
                "notes": "Ngữ cảnh phù hợp với cách thể hiện.",
            }
        )
    if any(row["text"] == INCOMPLETE for row in rows) and body["options"]["temperature"] == 0.1:
        segments = segments[:-1]
    if any(row["text"] == SPLIT for row in rows) and told_floor and len(rows) > 2:
        return {"segments": segments[:1]}, "length"
    return {"segments": segments, "pronunciations": []}, "stop"


def _critic_answer(body: dict[str, Any], *, garble: bool) -> dict[str, Any]:
    prompt = str(body["prompt"])
    candidate_hash = prompt.split("\n", 1)[0].removeprefix("candidate_hash=")
    rows = _json_after(
        prompt,
        "Hãy phản biện từng candidate sau mà không suy đoán notes/confidence của lượt trước:\n",
    )
    verdicts = []
    for row in rows:
        verdict = dict(row["candidate"])
        if row["text"] == DISPUTED:
            verdict["pace"] = "fast"
        verdicts.append(
            {
                "id": row["id"],
                **verdict,
                "rationale": "Chức năng câu và delivery được đối chiếu với ngữ cảnh.",
                "evidence_quote": canonical_analysis_critic_source_anchors(str(row["text"]))[0],
                "critic_confidence": 0.9,
            }
        )
    if garble and any(row["text"] == GARBLED for row in rows):
        candidate_hash = "0" * 64
    return {"candidate_hash": candidate_hash, "verdicts": verdicts}


class _Stream:
    def __init__(
        self,
        text: str,
        done_reason: str,
        on_first_line: Callable[[], None] | None = None,
    ) -> None:
        self.text = text
        self.done_reason = done_reason
        self.on_first_line = on_first_line
        self.encoding = None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        if self.on_first_line is not None:
            self.on_first_line()
        line = json.dumps(
            {
                "response": self.text,
                "done": True,
                "done_reason": self.done_reason,
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
            ensure_ascii=False,
        )
        yield line if decode_unicode else line.encode("utf-8")

    def close(self) -> None:
        return None


class UnseenRequest(BaseException):
    """BaseException, so no retry handler in the analysis loop can swallow it."""


class FakeOllama:
    """The baseline's Ollama answers from the request; a resumed run's replays its script.

    `script` maps request hash -> the exact text the baseline got. A resumed run must send
    only requests the baseline sent, so any other hash fails the test on the spot.
    """

    def __init__(self, *, script: dict[str, tuple[str, str]] | None = None) -> None:
        self.script = script
        self.answers: dict[str, tuple[str, str]] = {}
        self.completed: list[str] = []
        self.roles: dict[str, str] = {}
        self.garbled_prompts: set[str] = set()
        self.stop_on: str | None = None
        self.stop_flag = False

    def get(self, _url: str, timeout: float):
        class Tags:
            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict[str, Any]:
                return {"models": [{"name": str(build_settings()["analysis"]["model"]), "digest": DIGEST}]}

        return Tags()

    def _answer(self, body: dict[str, Any], request_hash: str) -> tuple[str, str]:
        if self.script is not None:
            if request_hash not in self.script:
                raise UnseenRequest(
                    f"request {request_hash[:12]} was never sent by the unstopped run"
                )
            return self.script[request_hash]
        if body["system"] == SYSTEM_PROMPT:
            self.roles[request_hash] = "generator"
            answer, done_reason = _generator_answer(body)
        elif body["system"] == DIRECTOR_CRITIC_SYSTEM_PROMPT:
            self.roles[request_hash] = "director_critic"
            prompt_key = sha256_text(str(body["prompt"]))
            garble = prompt_key not in self.garbled_prompts
            self.garbled_prompts.add(prompt_key)
            answer, done_reason = _critic_answer(body, garble=garble), "stop"
        else:
            raise AssertionError("unexpected request role")
        return json.dumps(answer, ensure_ascii=False), done_reason

    def post(self, _url: str, *, json: dict[str, Any], timeout: Any, stream: bool):
        body = json
        request_hash = analysis_request_hash(body)
        text, done_reason = self._answer(body, request_hash)
        if request_hash == self.stop_on:
            def stop_now() -> None:
                self.stop_flag = True

            return _Stream(text, done_reason, stop_now)
        self.answers[request_hash] = (text, done_reason)
        self.completed.append(request_hash)
        return _Stream(text, done_reason)


def _analyzer(db: ProjectDB, settings: dict[str, Any], ollama: FakeOllama, log: list[str]) -> OllamaBookAnalyzer:
    analyzer = OllamaBookAnalyzer(settings, db, log.append)
    analyzer.session = ollama

    def ready() -> bool:
        analyzer._model_digest = DIGEST
        return True

    analyzer.ensure_available = ready  # type: ignore[method-assign]
    return analyzer


def _labels(db: ProjectDB) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db.path) as conn:
        return list(
            conn.execute(
                "SELECT stable_id,status,kind,speaker,gender,age,emotion,intensity,pace,volume,"
                "confidence,analysis_notes FROM segments ORDER BY id"
            )
        )


def _critic_seeds(db: ProjectDB) -> list[tuple[Any, ...]]:
    with sqlite3.connect(db.path) as conn:
        rows = conn.execute(
            "SELECT candidates.group_fingerprint,candidates.candidate_hash,candidates.state,"
            "attempts.attempt_number,attempts.state,attempts.contract_json "
            "FROM analysis_critic_attempts AS attempts "
            "JOIN analysis_candidates AS candidates ON candidates.id=attempts.analysis_candidate_id "
            "ORDER BY candidates.id,attempts.attempt_number"
        )
        return [(*row[:5], json.loads(row[5])["seed"]) for row in rows]


def _codes(db: ProjectDB) -> list[str]:
    return [str(row["code"]) for row in db.list_events()]


def _checkpoints(log: list[str]) -> int:
    return sum(1 for line in log if line.startswith("Đã checkpoint phân tích"))


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("abook.analysis.time.sleep", lambda _seconds: None)


def _baseline(tmp_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    db = _project(tmp_path / "baseline")
    ollama = FakeOllama()
    log: list[str] = []
    _analyzer(db, settings, ollama, log).analyze_all(lambda: False)
    assert all(row[1] in {"analyzed", "warning"} for row in _labels(db))
    return {
        "completed": ollama.completed,
        "answers": ollama.answers,
        "roles": ollama.roles,
        "labels": _labels(db),
        "state": db.analysis_state(),
        "critic": _critic_seeds(db),
        "batches": _checkpoints(log),
        "codes": _codes(db),
    }


def _resume_and_compare(
    tmp_path: Path,
    settings: dict[str, Any],
    baseline: dict[str, Any],
    *,
    stop_after_batches: int | None = None,
    stop_on_request: str | None = None,
) -> ProjectDB:
    db = _project(tmp_path)
    first = FakeOllama(script=baseline["answers"])
    first.stop_on = stop_on_request
    log: list[str] = []
    analyzer = _analyzer(db, settings, first, log)

    def stop() -> bool:
        if first.stop_flag:
            return True
        return stop_after_batches is not None and _checkpoints(log) >= stop_after_batches

    if stop_on_request is None:
        analyzer.analyze_all(stop)
    else:
        with pytest.raises(AnalysisRequestStopped):
            analyzer.analyze_all(stop)
    assert any(row[1] == "pending" for row in _labels(db)), "the stop came too late to test anything"

    # A new process: new database handle, new analyzer, an Ollama that refuses anything new.
    reopened = ProjectDB(db.path)
    second = FakeOllama(script=baseline["answers"])
    second_log: list[str] = []
    _analyzer(reopened, settings, second, second_log).analyze_all(lambda: False)

    assert first.completed + second.completed == baseline["completed"]
    assert _labels(reopened) == baseline["labels"]
    assert reopened.analysis_state() == baseline["state"]
    assert _critic_seeds(reopened) == baseline["critic"]
    assert "ANALYSIS_STATE_REDERIVE_MISMATCH" not in _codes(reopened)
    assert "ANALYSIS_STATE_UNUSABLE" not in _codes(reopened)
    return reopened


def test_the_baseline_exercises_every_path_it_claims_to(tmp_path: Path) -> None:
    baseline = _baseline(tmp_path, build_settings())
    roles = [baseline["roles"][request_hash] for request_hash in baseline["completed"]]
    assert roles.count("director_critic") > baseline["batches"], "a critic retry or rejection happened"
    assert roles.count("generator") > baseline["batches"], "a generator retry happened"
    assert "ANALYSIS_DIRECTOR_CRITIC_REJECTED" in baseline["codes"]
    assert any(row[3] == 2 for row in baseline["critic"]), "a second critic attempt happened"
    assert baseline["state"]["queue"] == []
    assert baseline["state"]["committed_batches"] == baseline["batches"]


def test_a_stop_after_every_batch_resumes_into_the_same_book(tmp_path: Path) -> None:
    settings = build_settings()
    baseline = _baseline(tmp_path, settings)
    for stop_after in range(1, baseline["batches"]):
        _resume_and_compare(
            tmp_path / f"after{stop_after}", settings, baseline, stop_after_batches=stop_after
        )


def _nth_request_of(baseline: dict[str, Any], role: str, predicate: Callable[[int], bool]) -> list[str]:
    hashes = [h for h in baseline["completed"] if baseline["roles"][h] == role]
    return [h for index, h in enumerate(hashes) if predicate(index)]


@pytest.mark.parametrize("which", [0, 3])
def test_a_stop_inside_a_critic_call_reuses_the_same_attempt_and_seed(tmp_path: Path, which: int) -> None:
    settings = build_settings()
    baseline = _baseline(tmp_path, settings)
    target = _nth_request_of(baseline, "director_critic", lambda index: index == which)[0]
    reopened = _resume_and_compare(tmp_path / "resumed", settings, baseline, stop_on_request=target)
    with sqlite3.connect(reopened.path) as conn:
        abandoned = conn.execute(
            "SELECT COUNT(*) FROM analysis_critic_attempts WHERE state='abandoned'"
        ).fetchone()[0]
    assert abandoned == 0


def test_a_stop_inside_every_critic_call_of_the_book(tmp_path: Path) -> None:
    """Including the one that gets rejected and the one whose first verdict is garbled."""
    settings = build_settings()
    baseline = _baseline(tmp_path, settings)
    critics = _nth_request_of(baseline, "director_critic", lambda _index: True)
    for index, target in enumerate(critics):
        _resume_and_compare(tmp_path / f"critic{index}", settings, baseline, stop_on_request=target)


def test_a_stop_between_generator_attempts_rewalks_them_from_the_ledger(tmp_path: Path) -> None:
    settings = build_settings()
    baseline = _baseline(tmp_path, settings)
    generators = [h for h in baseline["completed"] if baseline["roles"][h] == "generator"]
    # Every generator request that is not its batch's first attempt is a mid-batch stop point.
    for index, target in enumerate(generators[1:], 1):
        reopened = _resume_and_compare(
            tmp_path / f"generator{index}", settings, baseline, stop_on_request=target
        )
        del reopened


def test_the_balanced_profile_resumes_into_the_same_book_too(tmp_path: Path) -> None:
    """No director critic: the batch commit is the row update plus the checkpoint, atomically."""
    settings = build_settings("balanced")
    baseline = _baseline(tmp_path, settings)
    assert baseline["batches"] >= 2
    _resume_and_compare(tmp_path / "resumed", settings, baseline, stop_after_batches=1)


def test_a_replayed_answer_is_announced_and_never_asks_the_model(tmp_path: Path) -> None:
    settings = build_settings()
    baseline = _baseline(tmp_path, settings)
    generators = [h for h in baseline["completed"] if baseline["roles"][h] == "generator"]
    target = next(
        h for index, h in enumerate(generators) if index and generators[index - 1] in baseline["completed"]
    )
    reopened = _resume_and_compare(tmp_path / "resumed", settings, baseline, stop_on_request=target)
    assert "ANALYSIS_RESPONSE_REPLAYED" in _codes(reopened)
