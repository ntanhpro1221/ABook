"""Xuất MP3 / M4B "Kèm nhạc nền" mang ghi công nhạc (FINDINGS_music A3, A4): nhạc CC BY đã trộn vào file thì người nhận file phải thấy tên bài, tác giả,
giấy phép và lời "đã chỉnh sửa" - trong thẻ comment và trong file `.txt` đi kèm; bài cc0 không tác giả không bao giờ in "by" rỗng."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from abook.io_utils import ffmpeg_available, ffmpeg_executable
from abook.webui import export, music_plan
from abook.webui.music_export import MODIFIED_NOTE, credit_line, credit_text
from tests.test_export_music import LINK_A, LINK_B, _studio_book

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="cần ffmpeg")

BY = {"title": "Bài A", "creator": "Kevin", "license": "by", "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
      "attribution": '"Bài A" Kevin (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License'}
CC0 = {"title": "The Hope", "creator": "", "license": "cc0", "licenseUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
       "attribution": '"The Hope" by  licensed CC0: https://opengameart.org/content/the-hope'}


def _credited(project: Path, tracks: dict[str, dict]) -> None:
    plan_file = project / music_plan.PLAN_FILE
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["tracks"] = tracks
    plan_file.write_bytes(json.dumps(plan).encode("utf-8"))


def _tags(path: Path) -> str:
    return subprocess.run([ffmpeg_executable(), "-hide_banner", "-i", str(path)], capture_output=True, encoding="utf-8", errors="replace",
                          check=False).stderr


def test_a_credit_line_uses_the_catalog_attribution_but_never_prints_an_empty_by() -> None:
    assert credit_line(BY) == BY["attribution"]
    line = credit_line(CC0)
    assert "by " not in line and "The Hope" in line and "CC0" in line
    mine = credit_line({"title": "Của tôi", "creator": "Tôi", "source": "local"})
    assert mine == "“Của tôi” - Tôi"
    assert credit_line({}) == ""


def test_the_modified_note_is_only_for_music_that_asks_for_credit() -> None:
    assert MODIFIED_NOTE in credit_text([BY, CC0]) and BY["attribution"] in credit_text([BY, CC0])
    assert MODIFIED_NOTE not in credit_text([CC0]), "bài cc0 không đòi ghi công, cũng không đòi nói đã sửa"
    assert credit_text([BY, BY]).count(BY["attribution"]) == 1, "một bài dùng nhiều đoạn chỉ một dòng"
    assert credit_text([{}]) == ""


def test_the_mp3_export_with_music_carries_the_credits_in_the_chapter_tag_and_a_text_file(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    _credited(project, {LINK_A: BY, LINK_B: CC0})
    folder = Path(export.export_book(project, tmp_path / "co", music=tracks.get)["folder"])
    credits = (folder / export.CREDITS_FILE).read_bytes()
    assert b"\r" not in credits
    text = credits.decode("utf-8")
    assert BY["attribution"] in text and "The Hope" in text and MODIFIED_NOTE in text and "by  licensed" not in text
    first, second = sorted(folder.glob("*.mp3"))
    assert BY["attribution"] in _tags(first) and "The Hope" in _tags(first), "chương có nhạc mang ghi công của chính nó"
    assert "Nhạc nền" not in _tags(second), "chương không nhạc không có ghi công"


def test_the_m4b_export_with_music_carries_the_credits_in_the_tag_and_beside_the_file(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    _credited(project, {LINK_A: BY, LINK_B: CC0})
    result = export.export_m4b(project, tmp_path / "co", music=tracks.get)
    file = Path(result["file"])
    sidecar = file.with_name(f"{file.stem} - {export.CREDITS_FILE}")
    assert BY["attribution"] in sidecar.read_text(encoding="utf-8") and MODIFIED_NOTE in sidecar.read_text(encoding="utf-8")
    assert BY["attribution"] in _tags(file) and MODIFIED_NOTE in _tags(file)


def test_an_export_without_music_has_no_credits_file(tmp_path: Path) -> None:
    project, _tracks = _studio_book(tmp_path)
    _credited(project, {LINK_A: BY, LINK_B: CC0})
    folder = Path(export.export_book(project, tmp_path / "khong")["folder"])
    assert not (folder / export.CREDITS_FILE).exists() and "Nhạc nền" not in _tags(min(folder.glob("*.mp3")))
    result = export.export_m4b(project, tmp_path / "khong_m4b")
    assert not list(Path(result["folder"]).glob("*Ghi công*"))


def test_a_packaged_book_hands_its_track_credits_to_the_mixer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sách Nghe ngay (listen_export): ghi công nằm trong mục `music.tracks` của gói, đi theo từng mốc."""
    from abook.webui import music_export

    music = {"levelDb": -20.0, "tracks": {"music/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mp3": BY, "music/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.mp3": CC0},
             "chapters": {"1": [{"start": 0.0, "end": 5.0, "track": "music/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mp3", "gainDb": -20.0}], "2": []}}
    monkeypatch.setattr(music_export, "_book_music", lambda path, include_disabled: music)
    monkeypatch.setattr(music_export.packages, "music_file", lambda path, name: tmp_path / "a.mp3")
    chapters = music_export.packaged_music(tmp_path, [1, 2])
    assert chapters[1].tracks == {"music/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mp3": BY}, "chỉ bài chương này dùng"
    mixer = music_export.Mixer("ffmpeg", chapters)
    assert BY["attribution"] in mixer.credits([1, 2]) and "The Hope" not in mixer.credits([1, 2])
