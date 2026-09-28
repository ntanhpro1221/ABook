"""Vòng học (docs/STUDIO_REVIEW.md bước 4): gom mọi quyết định của người nghe trong Studio thành một tập nhãn.

    python scripts/model_eval/listener_labels.py <thư viện hay dự án ...> --out labels.jsonl
    python scripts/model_eval/listener_labels.py            # thư viện của app (%LOCALAPPDATA%/ABook/preferences.json)

Mỗi dòng một quyết định, kèm đủ thứ để học hay đo từ nó:
- `speaker`: câu (mã ổn định, chương, thứ tự, chữ, loại đoạn), người MÁY đã gán, người NGƯỜI NGHE chọn, `confirmed` khi
  người nghe giữ nguyên nhãn máy (một nhãn đúng cũng là nhãn - chủ động xác nhận là dữ liệu quý), và ba câu trước/sau.
  Yêu cầu đã áp thì SQLite chỉ còn nhãn mới: nhãn máy lấy từ sự kiện áp đầu tiên (`SPEAKER_SET_BY_LISTENER`,
  `previous_speaker`).
- `delivery`: loại đoạn / cảm xúc / cường độ của một câu (`LINE_SET_BY_LISTENER`, `previous`).
- `voice`: giới / giọng của một nhân vật (`VOICE_SET_BY_LISTENER`).
- `pronunciation`: cách đọc một tên.
Yêu cầu cho câu đã đổi chữ (băm lệch) bị bỏ: nhãn ấy không còn gắn với chữ nào. Chỉ đọc - SQLite mở chế độ ro.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from ebook_reader.listener_overrides import (  # noqa: E402
    line_requests,
    pronunciation_requests,
    read_overrides,
    speaker_requests,
    voice_requests,
)

CONTEXT = 3


def _key(name: str) -> str:
    return " ".join(str(name or "").strip().casefold().split()).upper()


def projects(paths: list[Path]) -> Iterator[Path]:
    """Dự án có ít nhất một yêu cầu của người nghe, dưới các đường dẫn (thư viện: sâu hai tầng)."""
    seen: set[str] = set()
    for root in paths:
        candidates = [root] + ([child for child in root.iterdir() if child.is_dir()] if root.is_dir() else [])
        candidates += [grand for child in candidates[1:] for grand in child.iterdir() if grand.is_dir()]
        for path in candidates:
            if (path / "project.sqlite3").is_file() and (path / "overrides.json").is_file():
                resolved = str(path.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    yield path


def _first_previous(connection: sqlite3.Connection, code: str, key: str) -> dict[str, dict[str, Any]]:
    """Mã câu / nhân vật -> chi tiết của lần áp ĐẦU TIÊN (nhãn của máy trước khi người nghe đụng tới)."""
    found: dict[str, dict[str, Any]] = {}
    try:
        rows = connection.execute("SELECT details_json FROM runtime_events WHERE code=? ORDER BY id", (code,)).fetchall()
    except sqlite3.OperationalError:
        return found
    for (details,) in rows:
        try:
            data = json.loads(details or "{}")
        except ValueError:
            continue
        if isinstance(data, dict) and data.get(key) and str(data[key]) not in found:
            found[str(data[key])] = data
    return found


def labels(project: Path) -> Iterator[dict[str, Any]]:
    overrides = read_overrides(project)
    with closing(sqlite3.connect(f"file:{project / 'project.sqlite3'}?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        book = connection.execute("SELECT title FROM book WHERE id=1").fetchone()
        title = str(book["title"]) if book is not None else project.name
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(segments)")}
        delivery = [column for column in ("emotion", "intensity") if column in columns]
        rows = connection.execute(
            "SELECT s.stable_id, s.chapter_id, s.seq, s.text, s.text_sha256, s.kind, s.speaker"
            + "".join(f", s.{column}" for column in delivery)
            + ", c.chapter_index, c.title AS chapter_title FROM segments s JOIN chapters c ON c.id = s.chapter_id"
            " ORDER BY c.chapter_index, s.seq"
        ).fetchall()
        speakers_before = _first_previous(connection, "SPEAKER_SET_BY_LISTENER", "stable_id")
        lines_before = _first_previous(connection, "LINE_SET_BY_LISTENER", "stable_id")
        voices_before = _first_previous(connection, "VOICE_SET_BY_LISTENER", "character")
    by_stable = {str(row["stable_id"]): index for index, row in enumerate(rows)}
    base = {"book": title, "project": str(project)}

    def line_view(index: int) -> dict[str, Any]:
        row = rows[index]
        return {"stable_id": str(row["stable_id"]), "chapter": int(row["chapter_index"]), "seq": int(row["seq"]),
                "kind": str(row["kind"] or ""), "speaker": str(row["speaker"] or ""), "text": str(row["text"])}

    def context(index: int) -> dict[str, list[dict[str, Any]]]:
        chapter = rows[index]["chapter_id"]
        before = [line_view(i) for i in range(max(0, index - CONTEXT), index) if rows[i]["chapter_id"] == chapter]
        after = [line_view(i) for i in range(index + 1, min(len(rows), index + 1 + CONTEXT)) if rows[i]["chapter_id"] == chapter]
        return {"before": before, "after": after}

    for wish in speaker_requests(overrides):
        index = by_stable.get(wish["stable_id"])
        if index is None or str(rows[index]["text_sha256"] or "") != wish["text_sha256"]:
            continue
        row = rows[index]
        event = speakers_before.get(wish["stable_id"])
        machine = str(event["previous_speaker"]) if event else str(row["speaker"] or "")
        yield {**base, "type": "speaker", **line_view(index), "machine": machine, "listener": wish["speaker"],
               "confirmed": _key(machine) == _key(wish["speaker"]),
               "applied": event is not None or _key(str(row["speaker"])) == _key(wish["speaker"]),
               "context": context(index)}

    for wish in line_requests(overrides):
        index = by_stable.get(wish["stable_id"])
        if index is None or str(rows[index]["text_sha256"] or "") != wish["text_sha256"]:
            continue
        row = rows[index]
        event = lines_before.get(wish["stable_id"])
        machine = dict(event["previous"]) if event and isinstance(event.get("previous"), dict) else {
            "kind": str(row["kind"] or ""),
            **({"emotion": str(row["emotion"] or "neutral")} if "emotion" in delivery else {}),
            **({"intensity": int(row["intensity"] or 0)} if "intensity" in delivery else {}),
        }
        listener = {key: wish[key] for key in ("kind", "emotion", "intensity") if wish[key] not in ("", None)}
        yield {**base, "type": "delivery", **line_view(index), "machine": machine, "listener": listener,
               "applied": event is not None, "context": context(index)}

    for wish in voice_requests(overrides):
        event = voices_before.get(_key(wish["character"]))
        yield {**base, "type": "voice", "character": wish["character"], "listener": {
            key: wish[key] for key in ("gender", "preset", "avoid") if wish[key]},
            "keep": not (wish["gender"] or wish["preset"] or wish["avoid"]),
            "machine": {"voice_key": event["previous_voice_key"]} if event else None, "applied": event is not None}

    for wish in pronunciation_requests(overrides):
        yield {**base, "type": "pronunciation", "surface": wish["surface"], "listener": wish["spoken_form"]}


def default_library() -> list[Path]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return []
    try:
        preferences = json.loads((Path(local) / "ABook" / "preferences.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    root = preferences.get("libraryRoot")
    return [Path(root)] if root else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, help="thư viện hay thư mục dự án (mặc định: thư viện của app)")
    parser.add_argument("--out", type=Path, default=None, help="file JSONL (mặc định: in ra màn hình)")
    args = parser.parse_args(argv)
    roots = args.paths or default_library()
    records = [record for project in projects(roots) for record in labels(project)]
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    counts = Counter(record["type"] for record in records)
    confirmed = sum(1 for record in records if record.get("confirmed"))
    print(f"{len(records)} nhãn từ {len({record['project'] for record in records})} dự án: {dict(counts)};"
          f" {confirmed} câu người nghe xác nhận đúng nhãn máy", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
