"""Độ không chắc của người nói từ logprob TOKEN của model phân tích (Ollama) - chỉ ghi lại, chưa ai đọc lúc chạy.

Độ tin cậy model TỰ BÁO bằng chữ (`confidence`) vô dụng (docs/ANALYSIS_RESEARCH.md: trung bình 0,91 cho cả câu đúng lẫn sai).
Logprob của chính các token sinh ra tên người nói thì chưa ai đo: bật `ABOOK_SPEAKER_LOGPROBS=1` thì `OllamaBookAnalyzer` xin
Ollama `logprobs` + `top_logprobs`, và với MỖI đoạn thoại/nội tâm của lô ghi một dòng vào `analysis_logprobs/<chương>.jsonl` cạnh
sổ dự án. File ấy không phải đầu vào của bước nào (không vào sổ phản hồi, không vào resume, không đổi schema DB); tắt cờ thì
request và mọi đầu ra y hệt trước.

Hai điều đã đo (Ollama 0.33.2, qwen3.5, 2026-10-09): (1) bật logprobs KHÔNG đổi chữ sinh ra (cùng seed/temperature: từng byte);
(2) logprob là phân phối THÔ của model, trước ngữ pháp `format` - token bị schema ép (`{`, `":`) có p thấp dù là lựa chọn duy
nhất. Chỉ giá trị chuỗi tự do (tên người nói) mới có nghĩa, và đó là thứ ở đây.

Ánh xạ giá trị -> token không đoán bằng regex: `locate_string_values` đi cây JSON bằng bộ quét nhỏ (cùng văn phạm với
`json.loads`) để lấy khoảng byte của từng giá trị chuỗi, rồi chọn các token có khoảng byte chồng lên khoảng ấy. Token có thể
gộp ký tự JSON (` "`, `":`, `",`) hay cắt giữa một chữ có dấu, nên khoảng byte của token dựng từ trường `bytes`, không từ `token`.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ENV_FLAG = "ABOOK_SPEAKER_LOGPROBS"
DIRNAME = "analysis_logprobs"
TOP_LOGPROBS = 5
# Đoạn có người nói thật; lời dẫn luôn là người kể nên không cần độ tin cậy.
SPOKEN_KINDS = ("dialogue", "thought")


def enabled() -> bool:
    """Bật mặc định từ 09-10 (A/B cùng cây: không tốn giây đo được, nhãn trùng từng byte; LLM_Train/spkconf/lpab.txt).
    `ABOOK_SPEAKER_LOGPROBS=0` tắt."""
    return os.environ.get(ENV_FLAG, "").strip() != "0"


def request_options() -> dict[str, Any]:
    """Phần thêm vào body gửi Ollama (SAU khi băm khoá sổ, để khoá không đổi)."""
    return {"logprobs": True, "top_logprobs": TOP_LOGPROBS}


def _token_bytes(entry: Mapping[str, Any]) -> bytes:
    raw = entry.get("bytes")
    if isinstance(raw, list) and raw:
        try:
            return bytes(raw)
        except (TypeError, ValueError):
            pass
    return str(entry.get("token", "")).encode("utf-8")


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _scan_string_end(text: str, i: int) -> int:
    """`i` ở dấu `"` mở; trả vị trí NGAY SAU dấu `"` đóng."""
    i += 1
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
        elif char == '"':
            return i + 1
        else:
            i += 1
    raise ValueError("unterminated string")


def _scan_value(text: str, i: int) -> tuple[Any, int]:
    """Nút = ("str", start, end) | ("obj", {key: nút}) | ("arr", [nút]) | ("lit", start, end); trả (nút, vị trí sau)."""
    i = _skip_ws(text, i)
    if i >= len(text):
        raise ValueError("unexpected end")
    char = text[i]
    if char == '"':
        end = _scan_string_end(text, i)
        return ("str", i, end), end
    if char == "{":
        members: dict[str, Any] = {}
        i = _skip_ws(text, i + 1)
        if text[i : i + 1] == "}":
            return ("obj", members), i + 1
        while True:
            i = _skip_ws(text, i)
            if text[i : i + 1] != '"':
                raise ValueError("object key expected")
            key_end = _scan_string_end(text, i)
            key = json.loads(text[i:key_end])
            i = _skip_ws(text, key_end)
            if text[i : i + 1] != ":":
                raise ValueError("colon expected")
            node, i = _scan_value(text, i + 1)
            members.setdefault(key, node)
            i = _skip_ws(text, i)
            if text[i : i + 1] == ",":
                i += 1
                continue
            if text[i : i + 1] == "}":
                return ("obj", members), i + 1
            raise ValueError("object end expected")
    if char == "[":
        items: list[Any] = []
        i = _skip_ws(text, i + 1)
        if text[i : i + 1] == "]":
            return ("arr", items), i + 1
        while True:
            node, i = _scan_value(text, i)
            items.append(node)
            i = _skip_ws(text, i)
            if text[i : i + 1] == ",":
                i += 1
                continue
            if text[i : i + 1] == "]":
                return ("arr", items), i + 1
            raise ValueError("array end expected")
    start = i
    while i < len(text) and text[i] not in ",]} \t\r\n":
        i += 1
    if i == start:
        raise ValueError("value expected")
    return ("lit", start, i), i


def locate_string_values(raw_text: str, array_key: str, fields: Sequence[str]) -> list[dict[str, tuple[int, int, str]]] | None:
    """Với `raw_text` = JSON thô của model, cho mỗi phần tử của `raw_text[array_key]` (mảng object):
    {field: (byte_start, byte_end, giá trị)} - khoảng byte NỘI DUNG chuỗi (không gồm dấu `"`), chỉ các field là chuỗi.
    None nếu JSON thô không đọc được hay không có mảng ấy (câu trả lời hỏng thì không ghi gì)."""
    try:
        root, end = _scan_value(raw_text, 0)
        if raw_text[end:].strip() or root[0] != "obj" or array_key not in root[1]:
            return None
        array = root[1][array_key]
        if array[0] != "arr":
            return None
    except (ValueError, IndexError):
        return None
    # Đổi vị trí ký tự -> byte một lần: bảng cộng dồn chỉ cho các vị trí cần tra.
    needed: set[int] = set()
    for member in array[1]:
        if member[0] != "obj":
            continue
        for field in fields:
            node = member[1].get(field)
            if node is not None and node[0] == "str":
                needed.update((node[1], node[2]))
    byte_at: dict[int, int] = {}
    total = 0
    for position, char in enumerate(raw_text):
        if position in needed:
            byte_at[position] = total
        total += len(char.encode("utf-8", "surrogatepass"))
    if len(raw_text) in needed:
        byte_at[len(raw_text)] = total
    located: list[dict[str, tuple[int, int, str]]] = []
    for member in array[1]:
        entry: dict[str, tuple[int, int, str]] = {}
        if member[0] == "obj":
            for field in fields:
                node = member[1].get(field)
                if node is None or node[0] != "str":
                    continue
                try:
                    value = json.loads(raw_text[node[1] : node[2]])
                except ValueError:
                    continue
                entry[field] = (byte_at[node[1]] + 1, byte_at[node[2]] - 1, value)
        located.append(entry)
    return located


def _token_spans(tokens: Sequence[Mapping[str, Any]]) -> tuple[list[tuple[int, int]], int]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for entry in tokens:
        size = len(_token_bytes(entry))
        spans.append((cursor, cursor + size))
        cursor += size
    return spans, cursor


def _p(logprob: Any) -> float | None:
    try:
        return math.exp(float(logprob))
    except (TypeError, ValueError, OverflowError):
        return None


def _text_of(entry: Mapping[str, Any]) -> str:
    return _token_bytes(entry).decode("utf-8", "replace")


def _value_stats(
    tokens: Sequence[Mapping[str, Any]], spans: Sequence[tuple[int, int]], start: int, end: int
) -> dict[str, Any] | None:
    """Số đo của các token sinh ra khoảng byte [start, end) của một giá trị chuỗi."""
    covering = [
        index for index, (low, high) in enumerate(spans)
        if low < end and high > start
    ] if end > start else []
    if not covering:
        return None
    first = tokens[covering[0]]
    first_logprob = first.get("logprob")
    p_first = _p(first_logprob)
    if p_first is None:
        return None
    p_seq = 1.0
    for index in covering:
        p_token = _p(tokens[index].get("logprob"))
        if p_token is None:
            return None
        p_seq *= p_token
    chosen = _token_bytes(first)
    ranked = sorted(
        (alt for alt in first.get("top_logprobs") or [] if _p(alt.get("logprob")) is not None),
        key=lambda alt: -float(alt["logprob"]),
    )
    # Hiệu xác suất top1 - top2 ở token đầu: ~1 khi model chắc, ~0 khi hai ứng viên ngang nhau.
    margin = (_p(ranked[0]["logprob"]) - _p(ranked[1]["logprob"])) if len(ranked) >= 2 else None
    alternatives = [
        {"token": _text_of(alt), "p": round(_p(alt["logprob"]), 6)}
        for alt in ranked
        if _token_bytes(alt) != chosen
    ]
    # Token đứng ngay chỗ dấu `"` đóng: model có định kéo dài tên ("Minh" hay "Minh Anh") không.
    closing = next((i for i, (low, _high) in enumerate(spans) if low == end), None)
    p_end = _p(tokens[closing].get("logprob")) if closing is not None else None
    return {
        "p_first": round(p_first, 6),
        "p_seq": round(p_seq, 6),
        "p_end": None if p_end is None else round(p_end, 6),
        "margin": None if margin is None else round(margin, 6),
        "alts": alternatives,
        "ntok": len(covering),
    }


def speaker_records(raw_text: str, tokens: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """{id đoạn như model viết -> số đo của giá trị `speaker`} cho mọi đoạn thoại/nội tâm của câu trả lời `raw_text`.

    Rỗng khi token không ghép lại đúng `raw_text` (câu trả lời lấy từ sổ, hay cắt) - thà thiếu còn hơn lệch."""
    spans, total = _token_spans(tokens)
    if not tokens or total != len(raw_text.encode("utf-8", "surrogatepass")):
        return {}
    located = locate_string_values(raw_text, "segments", ("id", "speaker"))
    segments = payload.get("segments")
    if located is None or not isinstance(segments, list) or len(located) != len(segments):
        return {}
    records: dict[str, dict[str, Any]] = {}
    for item, where in zip(segments, located):
        if not isinstance(item, Mapping) or "id" not in where or "speaker" not in where:
            continue
        if item.get("kind") not in SPOKEN_KINDS or item.get("id") != where["id"][2] or item.get("speaker") != where["speaker"][2]:
            continue
        stats = _value_stats(tokens, spans, where["speaker"][0], where["speaker"][1])
        if stats is None:
            continue
        records[str(item["id"])] = {"kind": item["kind"], "speaker": item["speaker"], **stats}
    return records


def path_for(project_root: Path, chapter: int) -> Path:
    return Path(project_root) / DIRNAME / f"{int(chapter):05d}.jsonl"


def write_chapter_records(project_root: Path, chapter: int, records: Iterable[Mapping[str, Any]]) -> None:
    """Gộp `records` vào file của chương; cùng `stable_id` thì dòng mới thắng (request cuối cùng của một lô thử lại).
    Ghi cả file qua tệp tạm + os.replace, LF, nên không bao giờ để nửa dòng."""
    path = path_for(project_root, chapter)
    merged: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_bytes().decode("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and "stable_id" in row:
                merged[str(row["stable_id"])] = row
    for record in records:
        merged[str(record["stable_id"])] = dict(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in sorted(merged.values(), key=lambda row: (int(row.get("seq", 0)), str(row["stable_id"])))
    )
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_bytes(body.encode("utf-8"))
    os.replace(temporary, path)


def read_confidences(project_root: Path) -> dict[str, dict[str, Any]]:
    """{stable_id -> dòng đo} của mọi chương trong `analysis_logprobs/`: hộp "Việc cần duyệt" đọc để hỏi lại những câu model
    kém chắc nhất. Thiếu thư mục/file, dòng hỏng hay thiếu `p_first` thì bỏ qua (không bao giờ làm sập người gọi)."""
    found: dict[str, dict[str, Any]] = {}
    folder = Path(project_root) / DIRNAME
    try:
        paths = sorted(folder.glob("*.jsonl"))
    except OSError:
        return found
    for path in paths:
        try:
            text = path.read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or not isinstance(row.get("stable_id"), str) or not isinstance(row.get("speaker"), str):
                continue
            p_first = row.get("p_first")
            if isinstance(p_first, bool) or not isinstance(p_first, (int, float)) or not 0 <= p_first <= 1:
                continue
            found[row["stable_id"]] = row
    return found
