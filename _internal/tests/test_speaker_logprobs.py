"""Logprob token của người nói (ABOOK_SPEAKER_LOGPROBS): tắt thì request y hệt; bật thì xin logprobs SAU khi băm khoá sổ và ghi
`analysis_logprobs/<chương>.jsonl`; ánh xạ giá trị `speaker` -> token đúng cả khi tên nhiều token, có dấu, token cắt giữa chữ
(byte) hay gộp ký tự JSON (` "`, `":`, `",`, `"}`). Không gọi Ollama thật."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from abook import speaker_logprobs as SL
from abook.analysis import OllamaBookAnalyzer
from abook.config import build_settings
from test_analysis_required import FakeDB
from tests.fresh_slot_fakes import PrimeResponse, is_fresh_slot_prime


def tok(raw: bytes, logprob: float, alts: dict[bytes, float] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "token": raw.decode("utf-8", "replace"),
        "logprob": logprob,
        "bytes": list(raw),
        "top_logprobs": [{"token": raw.decode("utf-8", "replace"), "logprob": logprob, "bytes": list(raw)}],
    }
    for other, other_logprob in (alts or {}).items():
        entry["top_logprobs"].append(
            {"token": other.decode("utf-8", "replace"), "logprob": other_logprob, "bytes": list(other)}
        )
    return entry


def tokenize(text: str) -> list[dict[str, Any]]:
    """Cắt `text` thành token giả như Ollama: ký tự JSON gộp (` "`, `":`, `",`, `"}`), phần còn lại thành mảnh 1,2,3,2 byte
    lần lượt (nên có chỗ cắt giữa một chữ có dấu); mọi token logprob -0,01."""
    data = text.encode("utf-8")
    pieces: list[bytes] = []
    glued = (b'":', b'",', b'"}', b' "', b'"]')
    sizes = [1, 2, 3, 2]
    i = n = 0
    while i < len(data):
        for glue in glued:
            if data.startswith(glue, i):
                pieces.append(glue)
                i += len(glue)
                break
        else:
            j = i + 1
            while j < len(data) and j - i < sizes[n % 4] and not any(data.startswith(g, j) for g in glued):
                j += 1
            pieces.append(data[i:j])
            i = j
            n += 1
    return [tok(piece, -0.01) for piece in pieces]


def set_token_covering(tokens: list[dict[str, Any]], text: str, needle: str, logprob: float, alts: dict[bytes, float]) -> int:
    """Đặt logprob/ứng viên cho token đầu tiên phủ byte đầu của `needle` trong `text`; trả chỉ số token."""
    position = text.encode("utf-8").index(needle.encode("utf-8"))
    cursor = 0
    for index, entry in enumerate(tokens):
        size = len(entry["bytes"])
        if cursor <= position < cursor + size:
            raw = bytes(entry["bytes"])
            tokens[index] = tok(raw, logprob, alts)
            return index
        cursor += size
    raise AssertionError("needle not found")


def raw_json(*speakers: str, kinds: tuple[str, ...] | None = None) -> str:
    kinds = kinds or ("dialogue",) * len(speakers)
    items = [
        {"id": f"S{index + 1:03d}", "kind": kind, "speaker": speaker}
        for index, (speaker, kind) in enumerate(zip(speakers, kinds))
    ]
    return json.dumps({"segments": items}, ensure_ascii=False, indent=2)


def test_locate_string_values_gives_byte_spans_of_the_value_content() -> None:
    text = raw_json("Trần Quân Đức", "Lan")
    located = SL.locate_string_values(text, "segments", ("id", "speaker"))
    assert located is not None and len(located) == 2
    data = text.encode("utf-8")
    start, end, value = located[0]["speaker"]
    assert value == "Trần Quân Đức" and data[start:end].decode("utf-8") == "Trần Quân Đức"
    start, end, value = located[1]["id"]
    assert data[start:end] == b"S002"


def test_locate_string_values_survives_escapes_and_refuses_broken_json() -> None:
    text = '{"segments":[{"id":"S1","kind":"dialogue","speaker":"A \\"B\\" \\u1ea7"}]}'
    located = SL.locate_string_values(text, "segments", ("speaker",))
    assert located is not None
    start, end, value = located[0]["speaker"]
    assert value == 'A "B" ầ' and text.encode("utf-8")[start:end] == b'A \\"B\\" \\u1ea7'
    assert SL.locate_string_values('{"segments":[{"id":"S1"', "segments", ("id",)) is None
    assert SL.locate_string_values('{"other":[]}', "segments", ("id",)) is None


def test_speaker_records_maps_a_multi_token_accented_name_to_exactly_its_tokens() -> None:
    text = raw_json("Trần Quân Đức", "Lan", "NARRATOR", kinds=("dialogue", "thought", "narration"))
    tokens = tokenize(text)
    set_token_covering(tokens, text, "Trần Quân Đức", math.log(0.6), {b"Ph": math.log(0.3)})
    assert b"".join(bytes(t["bytes"]) for t in tokens) == text.encode()
    # có token cắt giữa một chữ nhiều byte (không tự giải mã được thành chữ)
    assert any("�" in t["token"] for t in tokens)

    records = SL.speaker_records(text, tokens, json.loads(text))

    assert set(records) == {"S001", "S002"}  # lời dẫn không có
    first = records["S001"]
    assert first["speaker"] == "Trần Quân Đức" and first["kind"] == "dialogue"
    assert first["p_first"] == pytest.approx(0.6, abs=1e-5)
    # token đầu của tên bắt đầu ở chữ T (khoảng byte nội dung); p_seq = tích mọi token chồng lên giá trị
    covering = first["ntok"]
    assert covering >= 3
    assert first["p_seq"] == pytest.approx(0.6 * math.exp(-0.01) ** (covering - 1), abs=1e-4)
    assert first["margin"] == pytest.approx(0.6 - 0.3, abs=1e-5)
    assert first["alts"] == [{"token": "Ph", "p": pytest.approx(0.3, abs=1e-5)}]
    assert records["S002"]["speaker"] == "Lan"


def test_a_token_gluing_the_closing_quote_and_the_next_key_still_counts_only_value_tokens() -> None:
    text = '{"segments":[{"id":"S001","kind":"dialogue","speaker":"Minh","gender":"male"}]}'
    tokens = [tok(b'{"', -5.0), tok(b'segments', -0.2), tok(b'":[{"', -3.0), tok(b'id', -0.1), tok(b'":"', -0.1),
              tok(b'S001', -0.1), tok(b'","', -0.2), tok(b'kind', -0.1), tok(b'":"', -0.1), tok(b'dialogue', -0.1),
              tok(b'","', -0.1), tok(b'speaker', -0.1), tok(b'":"', -0.3), tok(b'Minh', math.log(0.8), {b"Lan": math.log(0.1)}),
              tok(b'","', math.log(0.5)), tok(b'gender', -0.1), tok(b'":"', -0.1), tok(b'male', -0.1), tok(b'"}]}', -0.1)]
    assert b"".join(bytes(t["bytes"]) for t in tokens) == text.encode()

    record = SL.speaker_records(text, tokens, json.loads(text))["S001"]

    # `":"` đứng trước giá trị chứa dấu mở nhưng không chứa chữ nào của giá trị -> không tính; `","` sau giá trị cũng không
    assert record["ntok"] == 1 and record["p_first"] == pytest.approx(0.8, abs=1e-5)
    assert record["p_seq"] == pytest.approx(0.8, abs=1e-5)
    assert record["p_end"] == pytest.approx(0.5, abs=1e-5)
    assert record["margin"] == pytest.approx(0.8 - 0.1, abs=1e-5)


def test_tokens_that_do_not_rebuild_the_raw_text_give_no_records() -> None:
    text = raw_json("Lan")
    tokens = tokenize(text)[:-1]  # thiếu token cuối
    assert SL.speaker_records(text, tokens, json.loads(text)) == {}
    assert SL.speaker_records(text, [], json.loads(text)) == {}
    # tên trong JSON khác tên model đã giải mã (payload bị sửa) -> bỏ đoạn đó, không đoán
    altered = json.loads(text)
    altered["segments"][0]["speaker"] = "Khác"
    assert SL.speaker_records(text, tokenize(text), altered) == {}


def test_write_chapter_records_last_write_wins_and_uses_lf(tmp_path: Path) -> None:
    SL.write_chapter_records(tmp_path, 3, [{"chapter": 3, "seq": 2, "stable_id": "b", "p_first": 0.5},
                                          {"chapter": 3, "seq": 1, "stable_id": "a", "p_first": 0.9}])
    SL.write_chapter_records(tmp_path, 3, [{"chapter": 3, "seq": 2, "stable_id": "b", "p_first": 0.7}])
    path = tmp_path / "analysis_logprobs" / "00003.jsonl"
    data = path.read_bytes()
    assert b"\r" not in data
    rows = [json.loads(line) for line in data.decode().splitlines()]
    assert [(row["stable_id"], row["p_first"]) for row in rows] == [("a", 0.9), ("b", 0.7)]
    assert not (tmp_path / "analysis_logprobs" / "00003.jsonl.tmp").exists()


# ---------------------------------------------------------------- đường nối vào OllamaBookAnalyzer


class StreamResponse:
    def __init__(self, raw_text: str, tokens: list[dict[str, Any]], with_logprobs: bool) -> None:
        self.raw_text, self.tokens, self.with_logprobs = raw_text, tokens, with_logprobs
        self.encoding = None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        pieces = [bytes(t["bytes"]) for t in self.tokens]
        text_so_far = b""
        decoder_buffer = b""
        for index, piece in enumerate(pieces):
            decoder_buffer += piece
            try:
                chunk = decoder_buffer.decode("utf-8")
                decoder_buffer = b""
            except UnicodeDecodeError:
                chunk = ""  # token cắt giữa chữ: chữ ra ở mảnh sau, như Ollama
            envelope: dict[str, Any] = {"response": chunk, "done": False}
            if self.with_logprobs:
                envelope["logprobs"] = [self.tokens[index]]
            text_so_far += piece
            yield json.dumps(envelope, ensure_ascii=False)
        yield json.dumps({"response": "", "done": True, "done_reason": "stop", "eval_count": len(pieces)})

    def close(self) -> None:
        pass


class LogprobSession:
    def __init__(self, raw_text: str, tokens: list[dict[str, Any]]) -> None:
        self.raw_text, self.tokens = raw_text, tokens
        self.reals: list[dict[str, Any]] = []

    def post(self, _url: str, **kwargs: Any) -> Any:
        body = kwargs["json"]
        if is_fresh_slot_prime(body):
            return PrimeResponse()
        self.reals.append(body)
        return StreamResponse(self.raw_text, self.tokens, "logprobs" in body)


class PathDB(FakeDB):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.path = root / "project.db"
        self.chapters = [{"id": 1, "title": "Chương 1", "chapter_index": 7}]
        self.rows = [
            {"id": 1, "stable_id": "c1s1", "chapter_id": 1, "seq": 4, "paragraph_index": 0, "text": "\"Anh đi đâu?\" Lan hỏi.",
             "kind_hint": "dialogue", "status": "pending", "speaker": None},
            {"id": 2, "stable_id": "c1s2", "chapter_id": 1, "seq": 5, "paragraph_index": 1, "text": "Ngoài trời mưa.",
             "kind_hint": "narration", "status": "pending", "speaker": None},
        ]


def _analyzer(session: LogprobSession, db: PathDB) -> OllamaBookAnalyzer:
    analyzer = OllamaBookAnalyzer(build_settings(), db, lambda _message: None)
    analyzer.session = session
    analyzer._model_digest = "sha256:test"
    analyzer._verify_locked_model_digest = lambda _phase: None  # type: ignore[method-assign]
    return analyzer


def _answer() -> tuple[str, list[dict[str, Any]]]:
    segments = [
        {"id": "S001", "kind": "dialogue", "speaker": "Lan", "gender": "female", "age": "adult", "emotion": "neutral",
         "intensity": 0, "pace": "normal", "volume": "normal", "confidence": 0.9},
        {"id": "S002", "kind": "narration", "speaker": "NARRATOR", "gender": "unknown", "age": "unknown",
         "emotion": "neutral", "intensity": 0, "pace": "normal", "volume": "normal", "confidence": 0.9},
    ]
    text = json.dumps({"segments": segments}, ensure_ascii=False)
    tokens = tokenize(text)
    set_token_covering(tokens, text, 'Lan', math.log(0.55), {b"Minh": math.log(0.35)})
    return text, tokens


def test_the_flag_is_on_unless_set_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SL.ENV_FLAG, raising=False)
    assert SL.enabled()
    monkeypatch.setenv(SL.ENV_FLAG, "0")
    assert not SL.enabled()


def test_flag_off_sends_no_logprobs_and_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SL.ENV_FLAG, "0")
    text, tokens = _answer()
    session, db = LogprobSession(text, tokens), PathDB(tmp_path)
    analyzer = _analyzer(session, db)

    payload = analyzer._request(db.rows)

    assert [segment["id"] for segment in payload["segments"]] == ["c1s1", "c1s2"]
    assert len(session.reals) == 1 and "logprobs" not in session.reals[0] and "top_logprobs" not in session.reals[0]
    assert not (tmp_path / SL.DIRNAME).exists()


def test_flag_on_asks_for_logprobs_and_writes_one_line_per_spoken_segment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text, tokens = _answer()
    monkeypatch.setenv(SL.ENV_FLAG, "0")
    off_session, off_db = LogprobSession(text, tokens), PathDB(tmp_path / "off")
    (tmp_path / "off").mkdir()
    off_payload = _analyzer(off_session, off_db)._request(off_db.rows)

    monkeypatch.setenv(SL.ENV_FLAG, "1")
    session, db = LogprobSession(text, tokens), PathDB(tmp_path)
    payload = _analyzer(session, db)._request(db.rows)

    assert payload == off_payload  # bật cờ không đổi đầu ra của lô
    body = session.reals[0]
    assert body["logprobs"] is True and body["top_logprobs"] == 5
    # trừ hai trường thêm, body y hệt lúc tắt (khoá sổ băm trên body KHÔNG có logprobs)
    assert {k: v for k, v in body.items() if k not in ("logprobs", "top_logprobs")} == off_session.reals[0]
    lines = (tmp_path / SL.DIRNAME / "00007.jsonl").read_bytes().decode().splitlines()
    assert len(lines) == 1  # chỉ câu thoại; lời dẫn không có
    row = json.loads(lines[0])
    assert (row["chapter"], row["seq"], row["stable_id"], row["speaker"], row["kind"]) == (7, 4, "c1s1", "Lan", "dialogue")
    assert row["p_first"] == pytest.approx(0.55, abs=1e-5)
    assert row["alts"] == [{"token": "Minh", "p": pytest.approx(0.35, abs=1e-5)}]

    # lô thử lại cho cùng đoạn: dòng mới thay dòng cũ
    session2 = LogprobSession(*_answer())
    _analyzer(session2, db)._request(db.rows)
    assert len((tmp_path / SL.DIRNAME / "00007.jsonl").read_bytes().decode().splitlines()) == 1


def test_ledger_key_ignores_the_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from abook.analysis import analysis_request_hash

    text, tokens = _answer()
    recorded: list[str] = []

    class Ledger(PathDB):
        def analysis_response(self, request_hash: str) -> None:
            recorded.append(request_hash)
            return None

    keys = []
    for flag in ("0", "1"):
        monkeypatch.setenv(SL.ENV_FLAG, flag)
        recorded.clear()
        db = Ledger(tmp_path)
        _analyzer(LogprobSession(text, tokens), db)._request(db.rows)
        keys.append(tuple(recorded))
    assert keys[0] == keys[1] and len(keys[0]) == 1
    assert analysis_request_hash  # băm là hàm của body gốc, không của body kèm logprobs


def test_a_logprob_failure_never_breaks_the_batch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SL.ENV_FLAG, "1")
    text, tokens = _answer()
    messages: list[str] = []
    db = PathDB(tmp_path)
    analyzer = _analyzer(LogprobSession(text, tokens), db)
    analyzer.log = messages.append
    monkeypatch.setattr(SL, "write_chapter_records", lambda *a, **k: (_ for _ in ()).throw(OSError("đĩa đầy")))

    payload = analyzer._request(db.rows)

    assert [segment["id"] for segment in payload["segments"]] == ["c1s1", "c1s2"]
    assert any("logprob" in message for message in messages)
