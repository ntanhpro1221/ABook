"""Đối chiếu toàn bộ chương nguồn với audio và chữ đọc theo trước khi xuất sách."""
from __future__ import annotations

import math
import hashlib
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

from ..io_utils import ffmpeg_executable, run_hidden, sha256_file
from . import store


def inspect_audio(path: Path) -> tuple[bool, str, float | None]:
    """Decode every audio frame and measure its duration without Studio dependencies."""
    try:
        if not path.is_file() or path.stat().st_size < 4096:
            return False, "MP3 missing or too small", None
        result = run_hidden(
            [ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
             "-map", "0:a:0", "-vn", "-progress", "pipe:1", "-nostats", "-f", "null", "-"],
            timeout=3600, check=False,
        )
        if result.returncode:
            return False, result.stderr[-3000:], None
        times = [int(value) for line in result.stdout.splitlines()
                 if line.startswith("out_time_us=") and (value := line.partition("=")[2]).lstrip("-").isdigit()]
        duration = times[-1] / 1_000_000 if times else 0.0
        if not math.isfinite(duration) or duration <= 0:
            return False, "Audio duration missing or invalid", None
        return True, "ok", duration
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return False, str(exc), None


def script_error(script: Any, expected: list[dict[str, Any]]) -> str:
    if not isinstance(script, dict) or not script.get("timed"):
        return "thiếu phụ đề có mốc"
    segments = script.get("segments")
    if not isinstance(segments, list) or len(segments) != len(expected) or not segments:
        return "phụ đề thiếu dòng"
    previous = 0.0
    for segment, source in zip(segments, expected):
        if not isinstance(segment, dict):
            return f"phụ đề sai dòng {source['id']}"
        if (segment.get("id") != source["id"]
                or hashlib.sha256(str(segment.get("text", "")).encode("utf-8")).hexdigest() != source["textSha256"]):
            return f"phụ đề sai dòng {source['id']}"
        try:
            start, end = float(segment["start"]), float(segment["end"])
        except (KeyError, TypeError, ValueError):
            return f"phụ đề thiếu mốc dòng {source['id']}"
        if not (math.isfinite(start) and math.isfinite(end) and previous <= start < end):
            return f"phụ đề sai mốc dòng {source['id']}"
        previous = end
    try:
        duration = float(script["duration"])
    except (KeyError, TypeError, ValueError):
        return "phụ đề thiếu thời lượng"
    return "phụ đề vượt audio" if not math.isfinite(duration) or previous > duration + 0.25 else ""


def summary(coverage: dict[str, Any]) -> str:
    expected, missing = coverage["expected"], coverage["missing"]
    names = "; ".join(f"{item['title']}: {item['reason']}" for item in missing)
    return f"{len(expected) - len(missing)}/{len(expected)} chương" + (f" · {names}" if names else "")


def expected_source(project_root: Path) -> list[dict[str, Any]]:
    with closing(store.connect(project_root)) as connection:
        chapters = connection.execute("SELECT id,title,chapter_index,status,last_error FROM chapters ORDER BY chapter_index").fetchall()
        artifacts = {str(r["artifact_key"]): r for r in connection.execute(
            "SELECT artifact_key,sha256,verified FROM artifacts WHERE kind='chapter_mp3'"
        )}
        expected = []
        for chapter in chapters:
            rows = connection.execute(
                "SELECT id,text,status FROM segments WHERE chapter_id=? ORDER BY seq",
                (chapter["id"],),
            ).fetchall()
            artifact = artifacts.get(f"chapter_mp3:{chapter['chapter_index']}")
            expected.append({"id": int(chapter["id"]), "title": str(chapter["title"]),
                             "qualityPassed": chapter['status'] == 'completed' and all(r['status'] != 'failed' for r in rows),
                             "qualityWarning": str(chapter['last_error'] or ''),
                             "audioSha256": str(artifact["sha256"]) if artifact and artifact["verified"] else None,
                             "segments": [{"id": int(r["id"]),
                                           "textSha256": hashlib.sha256(str(r["text"]).encode("utf-8")).hexdigest()} for r in rows],
                             "failedLines": [{"id": int(r["id"]), "reason": "failed"} for r in rows if r["status"] == "failed"]})
    return expected


def project(project_root: Path, book: dict[str, Any], files: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    expected = expected_source(project_root)
    indexed = {c["id"]: c for c in book["chapters"]}
    if len(indexed) != len(book["chapters"]) or set(indexed) - {c["id"] for c in expected}:
        raise ValueError("Danh sách chương không khớp nguồn.")
    missing = []
    inspected: dict[tuple[Path, int, int], tuple[bool, str, str, float | None]] = {}
    for chapter in expected:
        entry = indexed.get(chapter["id"])
        if entry is None:
            entry = {"id": chapter["id"], "title": chapter["title"], "file": None, "available": False}
            book["chapters"].append(entry)
        path = files.get(entry.get("file"))
        reason = (chapter['qualityWarning'] if chapter['qualityWarning'].startswith('Thiếu audio dòng:')
                  else "thiếu audio")
        if isinstance(path, Path) and path.is_file():
            stat = path.stat()
            key = (path, stat.st_size, stat.st_mtime_ns)
            if key not in inspected:
                valid, diagnostic, duration = inspect_audio(path)
                inspected[key] = (valid, diagnostic, sha256_file(path) if valid else "",
                                  duration)
            valid, reason, checksum, duration = inspected[key]
            if not valid:
                reason = 'không giải mã được audio'
            if valid and (entry.get("sha256") != checksum or chapter["audioSha256"] != checksum):
                reason = "sai mã băm audio"
            elif valid:
                import json
                raw = files.get(entry.get("script"))
                try:
                    script = json.loads(raw) if isinstance(raw, bytes) else None
                except (ValueError, UnicodeError):
                    script = None
                reason = script_error(script, chapter["segments"])
                if not reason and (duration is None or abs(float(script["duration"]) - duration) > .25):
                    reason = "thời lượng phụ đề không khớp audio"
        if reason:
            missing.append({"id": chapter["id"], "title": chapter["title"], "reason": reason})
            # Không mang một chương hỏng vào gói xuất một phần.
            if entry.get("file"):
                files.pop(entry["file"], None)
            entry.update(file=None, available=False, duration=0.0)
        entry["failedLines"] = chapter["failedLines"]
        entry["qualityPassed"] = chapter['qualityPassed']
        entry['qualityWarning'] = chapter['qualityWarning']
    coverage = {"expected": expected, "missing": missing, "partial": bool(partial)}
    if missing and not partial:
        raise ValueError("Thiếu chương: " + summary(coverage) + ". Dùng --partial để xuất một phần.")
    book["audioCoverage"] = coverage
    book["chaptersTotal"] = len(expected)
    book["chaptersAvailable"] = len(expected) - len(missing)
    book["duration"] = round(sum(float(c.get("duration") or 0) for c in book["chapters"] if c.get("file")), 3)
    book["complete"] = not missing
    return coverage


def verify(book: dict[str, Any], read: Callable[[str], bytes], decode: Callable[[str], bool],
           *, audio_hash: Callable[[str], str] | None = None,
           audio_duration: Callable[[str], float] | None = None) -> None:
    coverage = book.get("audioCoverage")
    if not isinstance(coverage, dict):
        raise ValueError("Thiếu danh sách chương nguồn để kiểm audio.")
    expected, missing = coverage["expected"], coverage["missing"]
    ids = [c["id"] for c in expected]
    missing_ids = [c["id"] for c in missing]
    chapters = book["chapters"]
    if (len(ids) != len(set(ids)) or set(ids) != {c["id"] for c in chapters}
            or len(chapters) != len(ids) or book["chaptersTotal"] != len(ids)
            or len(missing_ids) != len(set(missing_ids)) or not set(missing_ids) <= set(ids)
            or book["chaptersAvailable"] != len(ids) - len(missing_ids)
            or bool(book["complete"]) != (not missing)):
        raise ValueError("Danh sách chương không khớp nguồn.")
    if missing and not coverage.get("partial"):
        raise ValueError("Thiếu chương: " + summary(coverage))
    import json
    indexed = {c["id"]: c for c in expected}
    if any(c["title"] != indexed[c["id"]]["title"] for c in missing):
        raise ValueError("Tên chương thiếu không khớp nguồn.")
    for chapter in chapters:
        failed = indexed[chapter['id']].get('failedLines', [])
        if ((failed and chapter.get('failedLines') != failed)
                or ((failed or indexed[chapter['id']].get('qualityPassed') is False)
                    and chapter.get('qualityPassed') is not False)):
            raise ValueError(f"Chương {chapter['title']} che dòng chưa đạt QA.")
        if chapter["id"] in missing_ids:
            if chapter.get("file"):
                raise ValueError("Chương thiếu vẫn khai có audio.")
            continue
        name = chapter.get("file")
        if not name or not decode(name):
            raise ValueError(f"Không giải mã được chương {chapter['title']}.")
        checksum = audio_hash(name) if audio_hash else hashlib.sha256(read(name)).hexdigest()
        if checksum != chapter.get("sha256") or checksum != indexed[chapter["id"]].get("audioSha256"):
            raise ValueError(f"Sai mã băm chương {chapter['title']}.")
        script = json.loads(read(chapter["script"]))
        reason = script_error(script, indexed[chapter["id"]]["segments"])
        if not reason and audio_duration and abs(float(script["duration"]) - audio_duration(name)) > .25:
            reason = "thời lượng phụ đề không khớp audio"
        if reason:
            raise ValueError(f"{chapter['title']}: {reason}")
