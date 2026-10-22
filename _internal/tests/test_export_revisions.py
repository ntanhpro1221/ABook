from pathlib import Path

from abook.webui import export, export_jobs, store
from tests.test_webui_listen_and_sync import make_project


def test_export_history_survives_restart_and_retake_same_size(tmp_path):
    project = make_project(tmp_path)
    snapshot = export_jobs.audio_snapshot(project)
    export_jobs.remember_export(project, "m4b", "D:/out/book.m4b", snapshot)
    assert export_jobs.export_history(project)[0]["changed"] == []
    audio = store.chapter_audio_paths(project)[1]
    data = audio.read_bytes()
    audio.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    history = export_jobs.export_history(project)
    assert history[0]["changed"] == [1]
    assert history[0]["kind"] == "m4b"
    assert history[0]["target"] == "D:/out/book.m4b"
    # Một bản mới không làm mất cảnh báo của file cũ bạn đã chép/gửi.
    export_jobs.remember_export(project, "m4b", "D:/out/new.m4b", export_jobs.audio_snapshot(project))
    assert [item["changed"] for item in export_jobs.export_history(project)] == [[1], []]


def test_mp3_only_selected_chapters_keep_their_original_number(tmp_path, monkeypatch):
    import sqlite3
    project = make_project(tmp_path)
    audio = project / "output/chapters/00002_646.mp3"
    audio.write_bytes(b"audio-two")
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE chapters SET status='completed',output_mp3=? WHERE id=2", (str(audio),))
        db.execute("UPDATE segments SET status='verified',wav_duration=2 WHERE chapter_id=2")
    calls = []
    def write(_ffmpeg, source, final, _cover, **kwargs):
        calls.append((source, final.name, kwargs["number"], kwargs["total"]))
        final.write_bytes(source.read_bytes())
    monkeypatch.setattr(export, "write_chapter", write)
    monkeypatch.setattr(export, "ffmpeg_executable", lambda: "unused")
    monkeypatch.setattr(export.mp3, "duration_ms", lambda _: 1000)
    result = export.export_book(project, tmp_path / "out", chapter_ids=[2])
    assert result["files"] == 1
    assert calls[0][0] == audio
    assert calls[0][2:] == (2, 2)
    assert export_jobs.export_history(project)[0]["changed"] == []
    assert set(export_jobs.export_history(project)[0]["chapters"]) == {"2"}
