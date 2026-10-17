"""Xuất sách nói "Kèm nhạc nền" (webui/music_export.py + export.py + listen_export.py): nhạc trộn thẳng vào MP3 / M4B theo đúng mốc của trình
phát (music_mix.music_timeline), bộ chặn đỉnh chỉ trên bus nhạc (music_render), tắt thì ra đúng như trước.

Bài thử là sóng sin có tần số riêng: đo biên độ từng tần số theo cửa sổ thời gian (chiếu lên sin/cos) cho biết bài nào đang kêu, to bao nhiêu."""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile

from abook.io_utils import ffmpeg_available, ffmpeg_executable
from abook.webui import export, export_jobs, listen_export, music_export, music_plan, music_render
from abook.webui.music_export import ChapterMusic, Mixer
from abook.webui.music_mix import MIX
from tests.test_export_series import _get, _part, _post, _studio

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="cần ffmpeg")
RATE = 48000
QUIET = 10 ** (-12 / 20)


def _tone(seconds: float, freq: float, amp: float, rate: int = RATE) -> np.ndarray:
    return amp * np.sin(2 * np.pi * freq * np.arange(round(seconds * rate)) / rate)


def _wav(path: Path, samples: np.ndarray, rate: int = RATE) -> Path:
    soundfile.write(path, samples.astype(np.float32), rate, subtype="PCM_16", format="WAV")
    return path


def _amp(x: np.ndarray, freq: float, t0: float, t1: float, rate: int = RATE) -> float:
    """Biên độ thành phần `freq` của `x` trong [t0, t1) giây."""
    seg = x[round(t0 * rate):round(t1 * rate)]
    t = np.arange(len(seg)) / rate
    return float(2 * abs(np.sum(seg * np.exp(-2j * np.pi * freq * t))) / len(seg))


def _mix(tmp_path: Path, voice: np.ndarray, cues: list[dict[str, Any]], tracks: dict[str, np.ndarray],
         seconds: float | None = None) -> tuple[np.ndarray, Mixer]:
    """Chương giọng `voice` + nhạc `cues` qua đúng đường xuất (giải mã ffmpeg, `export.pump_mixed`); trả (PCM ra [-1, 1), bộ trộn)."""
    files = {name: _wav(tmp_path / f"{name}.wav", data) for name, data in tracks.items()}
    voice_file = _wav(tmp_path / "voice.wav", voice)
    mixer = Mixer(ffmpeg_executable(), {1: ChapterMusic(cues, {cue["track"]: files[cue["track"]] for cue in cues if cue["track"] in files})})
    sink = io.BytesIO()
    size = export.pump_mixed(ffmpeg_executable(), mixer, 1, voice_file, RATE, 1, sink, seconds)
    assert size == len(sink.getvalue()) == 2 * len(voice), "ra đúng bằng số mẫu giọng"
    return np.frombuffer(sink.getvalue(), dtype="<i2") / 32768.0, mixer


def test_the_music_follows_the_cues_fades_sibling_crossfade_and_volume_step(tmp_path: Path) -> None:
    a, b = _tone(60, 1000, 0.5), _tone(60, 2500, 0.5)
    cues = [{"start": 2.0, "end": 20.0, "track": "a", "gainDb": -12.0, "steps": [{"at": 10.0, "db": 6.0}]},
            {"start": 20.0, "end": 35.0, "track": "b", "gainDb": -12.0, "sibling": True}]
    out, mixer = _mix(tmp_path, np.zeros(45 * RATE), cues, {"a": a, "b": b})
    assert mixer.note([1]) == {}
    level, louder = 0.5 * QUIET, 0.5 * 10 ** (-6 / 20)
    fade, sibling, ramp = MIX["fadeSeconds"], MIX["siblingFadeSeconds"], MIX["stepRampSeconds"]

    def near(value: float, want: float, tol: float = 0.03) -> bool:
        return abs(value - want) <= tol * max(want, 0.1)

    # im trước mốc đầu và sau khi mốc cuối mờ hết
    assert _amp(out, 1000, 0, 1.9) < 1e-3 and _amp(out, 2500, 0, 1.9) < 1e-3
    assert _amp(out, 1000, 35 + fade + 0.2, 45) < 1e-3 and _amp(out, 2500, 35 + fade + 0.2, 45) < 1e-3
    # mờ vào FADE giây rồi đứng ở gainDb
    assert near(_amp(out, 1000, 2 + fade / 2 - 0.1, 2 + fade / 2 + 0.1), level / 2)
    assert near(_amp(out, 1000, 2 + fade + 0.5, 9.5), level) and _amp(out, 2500, 2, 19.5) < 1e-3
    # bước +6 dB ở giây 10, trượt STEP_RAMP giây
    assert near(_amp(out, 1000, 10 + ramp / 2 - 0.1, 10 + ramp / 2 + 0.1), (level + louder) / 2)
    assert near(_amp(out, 1000, 10 + ramp + 0.5, 19.5), louder)
    # bài anh em: mờ chéo SIBLING_FADE giây (bài cũ còn xa E nên mờ đủ)
    mid = 20 + sibling / 2
    assert near(_amp(out, 1000, mid - 0.1, mid + 0.1), louder / 2) and near(_amp(out, 2500, mid - 0.1, mid + 0.1), level / 2)
    assert near(_amp(out, 2500, 20 + sibling + 0.5, 34.5), level) and _amp(out, 1000, 20 + sibling + 0.2, 34.5) < 1e-3
    # mốc cuối mờ ra FADE giây
    assert near(_amp(out, 2500, 35 + fade / 2 - 0.1, 35 + fade / 2 + 0.1), level / 2)


def test_after_a_tail_cue_the_track_ends_at_its_end_and_never_comes_back_to_its_intro(tmp_path: Path) -> None:
    track = np.concatenate([_tone(3, 4000, 0.5), _tone(27, 1000, 0.5)])  # 3 s dạo đầu 4 kHz rồi 1 kHz, hết ở 30 s
    cue = {"start": 0.0, "end": 40.0, "track": "t", "gainDb": -6.0, "audibleStart": 0.0, "audibleEnd": 30.0}
    with_tail, _ = _mix(tmp_path, np.zeros(45 * RATE), [{**cue, "tail": True}], {"t": track})
    looping, _ = _mix(tmp_path, np.zeros(45 * RATE), [cue], {"t": track})
    assert _amp(with_tail, 4000, 2.1, 2.9) > 0.1, "dạo đầu kêu lúc vào bài"
    assert _amp(with_tail, 4000, 27, 40) < 1e-3, "vòng cuối: không quay lại dạo đầu"
    assert _amp(with_tail, 1000, 31, 40) < 1e-3, "bài chơi tới E là hết"
    assert _amp(looping, 4000, 29.5, 30.5) > 0.1, "không có tail thì lặp mờ chéo về A như trình phát"


def test_a_track_with_loop_points_loops_inside_them_and_its_tail_plays_the_composed_ending(tmp_path: Path) -> None:
    # PLAN_loop §10: dạo đầu 4 kHz (0-3 s), thân 1 kHz (3-25 s), đoạn kết soạn sẵn 2,5 kHz (25-30 s); điểm vòng 3 / 25 -> phần tử lặp
    # mở ở 23 từ 3, P = 20. Mốc thường không bao giờ nghe lại dạo đầu hay đoạn kết; mốc tail dài 50 = E của vòng thứ hai kết bằng đoạn kết.
    track = np.concatenate([_tone(3, 4000, 0.5), _tone(22, 1000, 0.5), _tone(5, 2500, 0.5)])
    cue = {"start": 0.0, "end": 60.0, "track": "t", "gainDb": -6.0, "audibleStart": 0.0, "audibleEnd": 30.0,
           "loopStart": 3.0, "loopEnd": 25.0}
    looping, _ = _mix(tmp_path, np.zeros(65 * RATE), [cue], {"t": track})
    with_tail, _ = _mix(tmp_path, np.zeros(65 * RATE), [{**cue, "end": 50.0, "tail": True}], {"t": track})
    assert _amp(looping, 1000, 30, 58) > 0.1, "lặp trong thân bài"
    assert _amp(looping, 4000, 4, 62) < 1e-3 and _amp(looping, 2500, 0, 62) < 1e-3, "không quay về dạo đầu, không nghe đoạn kết"
    assert _amp(with_tail, 2500, 46, 49.5) > 0.1, "vòng cuối chơi qua loopEnd tới E: đoạn kết là cái kết"
    assert _amp(with_tail, 4000, 4, 55) < 1e-3 and _amp(with_tail, 2500, 51, 55) < 1e-3


def test_where_no_cue_plays_the_voice_comes_out_sample_for_sample(tmp_path: Path) -> None:
    voice = _tone(12, 220, 0.3)
    out, _ = _mix(tmp_path, voice, [{"start": 4.0, "end": 8.0, "track": "a", "gainDb": -12.0}], {"a": _tone(20, 1000, 0.5)})
    alone = io.BytesIO()  # giọng giải mã y như bản xuất không nhạc
    export.pump_pcm(ffmpeg_executable(), tmp_path / "voice.wav", RATE, 1, alone)
    want = np.frombuffer(alone.getvalue(), dtype="<i2") / 32768.0
    plain = np.concatenate([np.arange(0, 4 * RATE), np.arange((8 + round(MIX["fadeSeconds"])) * RATE + 1, len(voice))])
    assert np.array_equal(out[plain], want[plain])
    assert _amp(out, 1000, 5, 7.5) > 0.1 and _amp(out, 1000, 10.5, 12) < 1e-4


def test_the_true_peak_stays_under_the_ceiling_and_only_the_music_is_lowered(tmp_path: Path) -> None:
    voice = _tone(6, 1000, 0.8)  # -1,9 dBFS: nhạc to cộng vào thì vượt trần
    music = _tone(10, 2500, 0.9)
    raw = voice + 0.9 * 10 ** (-3 / 20) * np.sin(2 * np.pi * 2500 * np.arange(len(voice)) / RATE)
    assert music_render.true_peak_db(raw[:, None], MIX["truePeakFir"]) > -1.0, "không chặn thì vỡ tiếng"
    out, _ = _mix(tmp_path, voice, [{"start": 0.0, "end": 6.0, "track": "m", "gainDb": -3.0}], {"m": music})
    ceiling = MIX["exportCeilingDbtp"] - MIX["exportGuardHeadroomDb"]
    peak = music_render.true_peak_db(out[:, None], MIX["truePeakFir"])
    assert peak <= ceiling + 0.05 and peak <= -1.0
    assert _amp(out, 1000, 2, 4) == pytest.approx(_amp(np.rint(voice * 32767) / 32768, 1000, 2, 4), rel=1e-3), "giọng giữ nguyên"
    assert _amp(out, 2500, 2, 4) < 0.9 * 10 ** (-3 / 20) * 0.9, "nhạc bị hạ"


def test_a_track_that_cannot_be_read_leaves_that_part_silent_and_is_counted(tmp_path: Path) -> None:
    broken = tmp_path / "hong.mp3"
    broken.write_bytes(b"not audio at all")
    files = {"a": _wav(tmp_path / "a.wav", _tone(20, 1000, 0.5)), "x": broken}
    cues = [{"start": 1.0, "end": 5.0, "track": "x", "gainDb": -12.0}, {"start": 6.0, "end": 9.0, "track": "a", "gainDb": -12.0}]
    mixer = Mixer(ffmpeg_executable(), {1: ChapterMusic(cues, files, dropped=2), 2: ChapterMusic([], {}, dropped=1)})
    sink = io.BytesIO()
    export.pump_mixed(ffmpeg_executable(), mixer, 1, _wav(tmp_path / "v.wav", np.zeros(12 * RATE)), RATE, 1, sink)
    out = np.frombuffer(sink.getvalue(), dtype="<i2") / 32768.0
    assert _amp(out, 1000, 7.5, 8.9) > 0.1, "đoạn kia vẫn có nhạc"
    assert mixer.note([1, 2]) == {"musicMissing": 1 + 2 + 1}, "bài hỏng + bài không tải được, kể cả chương chẳng còn mốc nào"


# ---- Studio: export_book (MP3) / export_m4b ---------------------------------------------------------------------------------

LINK_A, LINK_B = "https://x/a.mp3", "https://x/b.mp3"


def _ffmpeg(*args: str) -> None:
    subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _studio_book(tmp_path: Path, *, enabled: bool = True) -> tuple[Path, dict[str, Path]]:
    """Dự án 2 chương MP3 thật (giọng sin 220 Hz, 48 kHz mono), kế hoạch nhạc: chương 1 có bài A (1 kHz) rồi bài B (2,5 kHz), chương 2
    không có nhạc. Trả (dự án, {link: file bài trong "bộ đệm"})."""
    library = tmp_path / "thu_vien"
    library.mkdir()
    project = _part(tmp_path, library, "p1", "Truyện X")
    chapters = project / "output" / "chapters"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000", "-af", "volume=0.5", "-t", "20", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "96k", str(chapters / "00001_645.mp3"))
    second = chapters / "00002_646.mp3"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-t", "6", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", str(second))
    with sqlite3.connect(project / "project.sqlite3") as db:
        db.execute("UPDATE chapters SET status='completed', output_mp3=? WHERE id=2", (str(second),))
        db.execute("UPDATE segments SET status='verified', wav_duration=1.0 WHERE chapter_id=2")
    cache = tmp_path / "bo_dem"
    cache.mkdir()
    tracks = {LINK_A: _wav(cache / "a.wav", _tone(30, 1000, 0.5)), LINK_B: _wav(cache / "b.wav", _tone(30, 2500, 0.5))}
    scenes = [{"chapterId": 1, "start": 1.0, "end": 8.0, "link": LINK_A, "key": "1:1"},
              {"chapterId": 1, "start": 9.0, "end": 16.0, "link": LINK_B, "key": "1:9"}]
    (project / music_plan.PLAN_FILE).write_text(json.dumps({"version": music_plan.PLAN_VERSION, "enabled": enabled, "levelDb": -20.0,
                                                             "scenes": scenes, "tracks": {}}), encoding="utf-8")
    return project, tracks


def _decode(path: Path) -> np.ndarray:
    raw = subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE),
                          "pipe:1"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2") / 32768.0


def _sha(folder: Path) -> dict[str, str]:
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(folder.iterdir()) if file.is_file()}


def test_off_the_mp3_and_m4b_exports_are_byte_for_byte_what_they_were(tmp_path: Path) -> None:
    project, _tracks = _studio_book(tmp_path)
    before_mp3 = _sha(Path(export.export_book(project, tmp_path / "xuat1")["folder"]))
    before_m4b = hashlib.sha256(Path(export.export_m4b(project, tmp_path / "m4b1")["file"]).read_bytes()).hexdigest()
    (project / music_plan.PLAN_FILE).unlink()  # cuốn không có nhạc: đường cũ
    assert _sha(Path(export.export_book(project, tmp_path / "xuat2")["folder"])) == before_mp3
    assert hashlib.sha256(Path(export.export_m4b(project, tmp_path / "m4b2")["file"]).read_bytes()).hexdigest() == before_m4b


def test_on_the_mp3_chapter_with_music_is_mixed_and_the_one_without_is_copied_as_it_was(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path, enabled=False)  # rãnh nhạc đang tắt mà người dùng tích "Kèm nhạc nền": vẫn trộn
    plain = Path(export.export_book(project, tmp_path / "khong")["folder"])
    result = export.export_book(project, tmp_path / "co", music=tracks.get)
    folder = Path(result["folder"])
    assert "musicMissing" not in result and result["files"] == 2
    assert sorted(path.name for path in (tmp_path / "co").iterdir()) == ["Truyện X"], "không để lại thư mục tạm"
    names = sorted(file.name for file in folder.glob("*.mp3"))
    assert _sha(folder)[names[1]] == _sha(plain)[names[1]], "chương không có nhạc: chép nguyên như cũ"
    out = _decode(folder / names[0])
    assert abs(len(out) - 20 * RATE) <= RATE // 10
    assert _amp(out, 1000, 4, 7.5) > 3e-3 and _amp(out, 2500, 4, 7.5) < 1e-3
    assert _amp(out, 2500, 12, 15.5) > 3e-3 and _amp(out, 1000, 12, 15.5) < 1e-3
    assert _amp(out, 1000, 19, 19.9) < 1e-3 and _amp(out, 2500, 19, 19.9) < 1e-3
    # giọng như cũ, trừ mất mát của lần mã hoá MP3 thứ hai (LAME 96k làm sin 220 Hz nhỏ đi ~0,45 dB; trước mã hoá thì từng mẫu như cũ -
    # test_where_no_cue_plays_the_voice_comes_out_sample_for_sample)
    assert _amp(out, 220, 4, 7.5) == pytest.approx(_amp(_decode(plain / names[0]), 220, 4, 7.5), rel=0.07)
    probe = subprocess.run([ffmpeg_executable(), "-hide_banner", "-i", str(folder / names[0])], capture_output=True, encoding="utf-8", errors="replace", check=False).stderr
    assert re.search(r"Audio: mp3.*96 kb/s", probe), "mã hoá lại cùng bitrate với MP3 của chương"


def test_on_a_track_that_cannot_be_fetched_leaves_its_part_silent_and_the_export_still_finishes(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    result = export.export_book(project, tmp_path / "xuat", music=lambda link: tracks[LINK_A] if link == LINK_A else None)
    assert result["musicMissing"] == 1 and result["files"] == 2
    out = _decode(min(Path(result["folder"]).glob("*.mp3")))
    assert _amp(out, 1000, 4, 7.5) > 3e-3 and _amp(out, 2500, 12, 15.5) < 1e-3


def test_on_the_m4b_mixes_before_the_aac_encoder_reports_the_music_phase_and_peaks_under_minus_one(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path)
    loud = {"version": 1, "enabled": True, "levelDb": 0.0, "tracks": {}, "scenes": [
        {"chapterId": 1, "start": 1.0, "end": 16.0, "link": LINK_A, "key": "1:1"}]}
    (project / music_plan.PLAN_FILE).write_text(json.dumps(loud), encoding="utf-8")
    # giọng sát trần (sin 1/8 x 6,4 = 0,8: -1,9 dBFS) để bộ chặn phải làm việc
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000", "-af", "volume=6.4", "-t", "20", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "96k", str(project / "output" / "chapters" / "00001_645.mp3"))
    seen: list[tuple[int, int]] = []
    result = export.export_m4b(project, tmp_path / "xuat", music=tracks.get, progress=lambda chapter, chapters: seen.append((chapter, chapters)))
    assert seen == [(1, 2)], "chỉ chương có nhạc báo pha trộn nhạc"
    out = _decode(Path(result["file"]))
    assert _amp(out, 1000, 4, 15) > 0.01
    measured = subprocess.run([ffmpeg_executable(), "-hide_banner", "-nostats", "-i", result["file"], "-af", "ebur128=peak=true", "-f", "null", "-"],
                              capture_output=True, encoding="utf-8", errors="replace", check=False).stderr
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", measured)[-1])
    assert peak <= -1.0, measured[-400:]


def _spy_aac(monkeypatch: pytest.MonkeyPatch, over: Callable[[int, int], float]) -> tuple[list[str], list[tuple[int, float]]]:
    """Ghi bitrate mỗi lần mã hoá AAC; đo đỉnh chương trả `over(lượt đo, chương từ 1)` dB so với trần (giả lập bộ aac vọt đỉnh)."""
    bitrates: list[str] = []
    measured: list[tuple[int, float]] = []
    real = export.encode_stream

    def encode(ffmpeg: str, rate: int, channels: int, codec_args: list[str], destination: Path, feed: Any, what: str = "âm thanh") -> int:
        if "aac" in codec_args:
            bitrates.append(codec_args[codec_args.index("-b:a") + 1])
        return real(ffmpeg, rate, channels, codec_args, destination, feed, what)

    def peak(_ffmpeg: str, _path: Path, start: float = 0.0, seconds: float | None = None) -> float:
        measured.append((len(bitrates), start))
        chapter = sum(1 for done, at in measured if done == len(bitrates))
        return MIX["exportCeilingDbtp"] + over(len(bitrates), chapter)

    monkeypatch.setattr(export, "encode_stream", encode)
    monkeypatch.setattr(export, "true_peak_dbtp", peak)
    return bitrates, measured


def _chapter_count(m4b: str) -> int:
    probe = subprocess.run([ffmpeg_executable(), "-hide_banner", "-i", m4b], capture_output=True, encoding="utf-8", errors="replace", check=False).stderr
    return len(re.findall(r"Chapter #", probe))


@pytest.mark.parametrize("music", [False, True])
def test_a_chapter_whose_aac_peaks_over_the_ceiling_is_lowered_by_the_excess_and_encoded_again_at_64k(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, music: bool) -> None:
    project, tracks = _studio_book(tmp_path)
    options: dict[str, Any] = {"music": tracks.get} if music else {}
    bitrates, measured = _spy_aac(monkeypatch, lambda _round, _chapter: -0.5)
    plain = _decode(Path(export.export_m4b(project, tmp_path / "duoi_tran", **options)["file"]))
    assert bitrates == ["64k"] and len(measured) == 2, "không chương nào vượt: một lần mã hoá, đo từng chương"
    # lượt đo 1: chương 1 vượt 0,4 dB -> hạ 0,5 dB, chương 2 dưới trần; lượt 2: hết vượt
    bitrates, measured = _spy_aac(monkeypatch, lambda round_, chapter: 0.4 if round_ == 1 and chapter == 1 else -0.5)
    result = export.export_m4b(project, tmp_path / "vuot", **options)
    assert bitrates == ["64k", "64k"] and len(measured) == 4, "mã hoá lại MỘT lần, vẫn 64k, rồi đo lại"
    assert _chapter_count(result["file"]) == 2, "mục lục không nhân đôi"
    lowered = _decode(Path(result["file"]))
    assert _amp(lowered, 220, 2, 7) / _amp(plain, 220, 2, 7) == pytest.approx(10 ** (-0.5 / 20), rel=0.01), "chương 1 hạ đúng phần vượt + 0,1 dB"
    assert _amp(lowered, 330, 21, 25) / _amp(plain, 330, 21, 25) == pytest.approx(1.0, rel=0.01), "chương 2 không vượt thì giữ mức"
    if music:
        assert _amp(lowered, 1000, 4, 7.5) / _amp(plain, 1000, 4, 7.5) == pytest.approx(10 ** (-0.5 / 20), rel=0.03)


def test_the_peak_retry_stops_after_four_more_encodes_with_the_cuts_added_up_and_still_finishes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    project, _tracks = _studio_book(tmp_path)
    bitrates, _measured = _spy_aac(monkeypatch, lambda _round, _chapter: -0.5)
    plain = _decode(Path(export.export_m4b(project, tmp_path / "duoi_tran")["file"]))
    bitrates, measured = _spy_aac(monkeypatch, lambda _round, chapter: 0.4 if chapter == 1 else -0.5)
    result = export.export_m4b(project, tmp_path / "vuot")
    assert bitrates == ["64k"] * 5 and len(measured) == 10, "tối đa 4 lần mã hoá lại"
    assert _amp(_decode(Path(result["file"])), 220, 2, 7) / _amp(plain, 220, 2, 7) == pytest.approx(10 ** (-2.0 / 20), rel=0.01)
    assert "vẫn còn đỉnh AAC vượt" in caplog.text, "còn vượt sau 4 lượt: xuất vẫn xong, ghi số đỉnh"


def test_a_spike_that_jumps_to_another_chapter_keeps_the_earlier_cut_and_converges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, tracks = _studio_book(tmp_path)
    bitrates, _measured = _spy_aac(monkeypatch, lambda _round, _chapter: -0.5)
    plain = _decode(Path(export.export_m4b(project, tmp_path / "duoi_tran", music=tracks.get)["file"]))
    # như M4B thật: lượt 1 gai ở chương 1; mã hoá lại thì gai nhảy sang chương 2, rồi về lại chương 1; lượt 4 hết hẳn
    jumps = {(1, 1): 0.4, (2, 2): 0.2, (3, 1): 0.4}
    bitrates, measured = _spy_aac(monkeypatch, lambda round_, chapter: jumps.get((round_, chapter), -0.5))
    result = export.export_m4b(project, tmp_path / "vuot", music=tracks.get)
    assert bitrates == ["64k"] * 4 and len(measured) == 8
    out = _decode(Path(result["file"]))
    assert _amp(out, 220, 2, 7) / _amp(plain, 220, 2, 7) == pytest.approx(10 ** (-1.0 / 20), rel=0.01), "chương 1: hạ lượt 1 + lượt 3"
    assert _amp(out, 330, 21, 25) / _amp(plain, 330, 21, 25) == pytest.approx(10 ** (-0.3 / 20), rel=0.01), "chương 2 hạ ở lượt 2"


@pytest.mark.parametrize("music", [False, True])
def test_the_peak_check_and_each_re_encode_show_in_the_m4b_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, music: bool) -> None:
    project, tracks = _studio_book(tmp_path)
    _spy_aac(monkeypatch, lambda round_, chapter: 0.4 if round_ == 1 and chapter == 1 else -0.5)
    steps: list[tuple[int, int]] = []
    export.export_m4b(project, tmp_path / "xuat", peaks=lambda round_, over: steps.append((round_, over)), **({"music": tracks.get} if music else {}))
    assert steps == [(0, 0), (1, 1), (1, 0)], "kiểm đỉnh -> mã hoá lại lượt 1 vì 1 chương -> kiểm lại"
    _spy_aac(monkeypatch, lambda _round, _chapter: -0.5)
    steps.clear()
    export.export_m4b(project, tmp_path / "xuat2", peaks=lambda round_, over: steps.append((round_, over)), **({"music": tracks.get} if music else {}))
    assert steps == [(0, 0)]


def test_the_text_book_m4b_job_reports_the_peak_check_and_the_re_encode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_listen_export import _library, _run

    app, book_id, path, _fake = _library(tmp_path)
    _spy_aac(monkeypatch, lambda round_, chapter: 1.0 if round_ == 1 and chapter == 2 else -0.5)
    steps: list[dict[str, Any]] = []
    _run(app, book_id, path, tmp_path / "xuat", "m4b", progress=lambda **fields: steps.append(fields))
    peaks = [(step["phase"], step.get("peakRound"), step.get("peakOver")) for step in steps if step["phase"] in ("peaks", "reencode")]
    assert peaks == [("peaks", 0, 0), ("reencode", 1, 1), ("peaks", 1, 0)]
    after = steps.index(next(step for step in steps if step["phase"] == "reencode"))
    assert any(step["phase"] == "encode" for step in steps[after:]), "lượt mã hoá lại vẫn báo từng chương"


def _fold_offset(folder: Path) -> tuple[str, float]:
    """(khoá đoạn phát, dB bù) duy nhất trong `<bài>.mono.json`."""
    spans = json.loads((folder / "t.mono.json").read_text(encoding="utf-8"))["spans"]
    assert len(spans) == 1
    key = next(iter(spans))
    return key, spans[key]["offsetDb"]


def test_a_stereo_track_folded_into_a_mono_chapter_is_raised_by_its_own_measured_loss(tmp_path: Path) -> None:
    voice = np.zeros(10 * RATE)
    cues = [{"start": 0.0, "end": 10.0, "track": "t", "gainDb": -12.0}]
    same = np.stack([_tone(12, 1000, 0.3), _tone(12, 1000, 0.3)], axis=1)
    wide = np.stack([_tone(12, 1000, 0.3), _tone(12, 1500, 0.3)], axis=1)  # hai kênh khác nhau: gộp (L+R)/2 nhỏ đi 3 dB
    for name in ("same", "wide", "flip"):
        (tmp_path / name).mkdir()
    out_same, _ = _mix(tmp_path / "same", voice, cues, {"t": same})
    out_wide, _ = _mix(tmp_path / "wide", voice, cues, {"t": wide})
    assert _fold_offset(tmp_path / "same")[1] == pytest.approx(0.0, abs=0.1)
    key, offset = _fold_offset(tmp_path / "wide")
    assert offset == pytest.approx(3.0, abs=0.3), "bù đúng phần mất khi gộp, đo bằng BS.1770 của chính bài"
    # bù xong: mỗi tông của bản gộp = 0,15 x 10^(bù/20) ~ 0,212, bằng tông chung của bài hai kênh giống nhau (0,3) hạ 3 dB
    assert _amp(out_wide, 1000, 3, 7.5) == pytest.approx(0.15 * 10 ** (offset / 20) * 10 ** (-12 / 20), rel=0.03)
    assert _amp(out_same, 1000, 3, 7.5) == pytest.approx(0.3 * 10 ** (-12 / 20), rel=0.03)

    flip = np.stack([_tone(12, 1000, 0.3), -0.9 * _tone(12, 1000, 0.3)], axis=1)  # gần triệt tiêu khi gộp: trần +4 dB
    _mix(tmp_path / "flip", voice, cues, {"t": flip})
    assert _fold_offset(tmp_path / "flip")[1] == music_export.MONO_MAX_DB
    sidecar = tmp_path / "wide" / "t.mono.json"
    sidecar.write_text(json.dumps({"spans": {key: {"offsetDb": 1.0}}}), encoding="utf-8")
    again, _ = _mix(tmp_path / "wide", voice, cues, {"t": wide})
    assert _amp(again, 1000, 3, 7.5) == pytest.approx(0.15 * 10 ** (1.0 / 20) * 10 ** (-12 / 20), rel=0.03), "đo một lần, đọc lại số cạnh bài"


def test_the_fold_offset_is_measured_on_the_stretch_the_chapter_plays_not_the_whole_track(tmp_path: Path) -> None:
    # bài 60 s: 12 s đầu hai kênh khác nhau (gộp mất ~3 dB), phần còn lại hai kênh giống nhau (gộp không mất gì) - cả bài chỉ mất ~0,5 dB
    left = _tone(60, 1000, 0.3)
    right = np.concatenate([_tone(12, 1500, 0.3), _tone(60, 1000, 0.3)[12 * RATE:]])
    track = np.stack([left, right], axis=1)
    cues = [{"start": 0.0, "end": 8.0, "track": "t", "gainDb": -12.0}]
    out, _ = _mix(tmp_path, np.zeros(10 * RATE), cues, {"t": track}, seconds=10.0)
    key, offset = _fold_offset(tmp_path)
    start, end = map(int, key.split("-"))
    assert start == 0 and 8 <= end <= 12, "khoảng phát = phần đầu bài chương này phát (giây nguyên)"
    assert offset == pytest.approx(3.0, abs=0.3), "đo trên đoạn phát (rộng stereo), không trên cả bài"
    assert _amp(out, 1000, 3, 7) == pytest.approx(0.15 * 10 ** (offset / 20) * 10 ** (-12 / 20), rel=0.03)
    whole = music_export.played_span([{"track": "t", "position": 0.0, "from": 0.0, "to": 5.0, "loop": True}], 60.0)
    assert whole == (0, 60), "phần tử lặp phát cả bài"


def test_the_text_book_m4b_shares_the_peak_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_listen_export import _library, _run

    app, book_id, path, _fake = _library(tmp_path)
    chapters = listen_export.load_chapters(path)
    bitrates, measured = _spy_aac(monkeypatch, lambda round_, chapter: 1.5 if round_ == 1 and chapter == 2 else -0.5)
    result = _run(app, book_id, path, tmp_path / "xuat", "m4b")
    assert bitrates == ["64k", "64k"] and len(measured) == 2 * len(chapters)
    assert _chapter_count(result["file"]) == len(chapters)


def test_the_server_says_whether_the_book_has_music_and_exports_with_it_when_asked(tmp_path: Path) -> None:
    project, tracks = _studio_book(tmp_path, enabled=False)
    app, server = _studio(tmp_path, project.parent)
    cache = app.music_dir / "files"
    cache.mkdir(parents=True)
    for link, file in tracks.items():
        shutil.copyfile(file, cache / (hashlib.sha1(link.encode("utf-8")).hexdigest() + ".mp3"))
    try:
        state = _get(server, project, "export-music")
        status, result = _post(server, project, "export", {"target": str(tmp_path / "xuat"), "music": True})
    finally:
        server.stop()
    assert state == (200, {"available": True, "enabled": False})
    assert status == 200 and "musicMissing" not in result
    out = _decode(min(Path(result["folder"]).glob("*.mp3")))
    assert _amp(out, 1000, 4, 7.5) > 3e-3
    (project / music_plan.PLAN_FILE).unlink()
    assert music_export.studio_state(project) == {"available": False, "enabled": False}


# ---- sách Nghe ngay (listen_export) ---------------------------------------------------------------------------------------


def test_a_text_book_chapter_is_mixed_into_its_own_temp_file_and_changing_the_music_redoes_only_the_mix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_listen_export import VOICE, _library, _run

    app, book_id, path, fake = _library(tmp_path)
    chapters = listen_export.load_chapters(path)
    track = _wav(tmp_path / "nhac.wav", _tone(10, 1000, 0.5, 24000), 24000)
    first = {chapters[0].id: ChapterMusic([{"start": 0.0, "end": 1.5, "track": "n", "gainDb": -12.0}], {"n": track})}
    stop = threading.Event()
    steps: list[dict[str, Any]] = []
    with pytest.raises(export_jobs.Cancelled):
        _run(app, book_id, path, tmp_path / "xuat", "mp3", music=first, cancelled=stop.is_set,
             progress=lambda **fields: (steps.append(fields), stop.set() if fields["chapter"] == 2 else None))
    assert ("music", 1) in {(step["phase"], step["chapter"]) for step in steps}
    work = listen_export.work_folder(tmp_path / "export_work", book_id)
    reading = listen_export.Reading(VOICE, None, {})
    assert listen_export.chapter_ready(work, chapters[0], reading) is not None, "bản giọng giữ nguyên"
    assert listen_export.chapter_ready(work, chapters[0], reading, first[chapters[0].id]) is not None
    changed = {chapters[0].id: ChapterMusic([{"start": 0.0, "end": 1.5, "track": "n", "gainDb": -18.0}], {"n": track})}
    assert listen_export.chapter_ready(work, chapters[0], reading, changed[chapters[0].id]) is None, "đổi nhạc: bản trộn cũ không dùng"

    pumped: list[str] = []
    real = export.pump_pcm
    monkeypatch.setattr(export, "pump_pcm", lambda ffmpeg, source, rate, channels, sink: (pumped.append(source.name), real(ffmpeg, source, rate, channels, sink))[1])
    fake.calls.clear()
    result = _run(app, book_id, path, tmp_path / "xuat", "mp3", music=changed)
    assert not any(text in fake.calls for text in ("Một hai ba.", "Bốn năm.")), "giọng chương 1 không đọc lại"
    assert f"{chapters[0].id}.flac" in pumped, "chương 1 trộn lại từ bản giọng"
    out = _decode(min(Path(result["folder"]).glob("*.mp3")))
    # chương 2,9 s: mốc kẹp ở 2,9 - chapterEndFadeSeconds = 0,4 s, đang mờ vào (tới 0,2 mức) thì mờ ra - đo đỉnh ấy, ở mức MỚI (-18)
    assert 0.15 * 0.5 * 10 ** (-18 / 20) < _amp(out, 1000, 0.3, 0.5) < 0.2 * 0.5 * 10 ** (-18 / 20) * 1.15
    assert "musicMissing" not in result


def test_the_player_only_install_starts_and_lowers_m4b_peaks_without_numpy(tmp_path: Path) -> None:
    # Bản cài chỉ để nghe không có numpy (tải theo mô-đun Phân tích nhạc): server phải nạp được, và lần mã hoá lại M4B của chương
    # không nhạc hạ mức trong ffmpeg (không qua numpy). Chặn numpy trong một tiến trình riêng.
    if not ffmpeg_available():
        pytest.skip("cần ffmpeg")
    wav = tmp_path / "tone.wav"
    soundfile.write(wav, (0.5 * np.sin(2 * np.pi * 220 * np.arange(24000) / 24000)).astype("float32"), 24000, subtype="PCM_16")
    script = (
        "import io, sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] == 'numpy': raise ImportError('numpy bị chặn')\n"
        "sys.meta_path.insert(0, Block())\n"
        "from abook.webui import server, export\n"
        "from abook.io_utils import ffmpeg_executable\n"
        "from pathlib import Path\n"
        "plain, low = io.BytesIO(), io.BytesIO()\n"
        "export.pump_pcm(ffmpeg_executable(), Path(sys.argv[1]), 24000, 1, plain)\n"
        "export.pump_pcm(ffmpeg_executable(), Path(sys.argv[1]), 24000, 1, low, lower_db=6.0)\n"
        "peak = lambda data: max(abs(int.from_bytes(data[i:i + 2], 'little', signed=True)) for i in range(0, len(data), 2))\n"
        "print(len(plain.getvalue()) == len(low.getvalue()), round(peak(low.getvalue()) / peak(plain.getvalue()), 3))\n")
    run = subprocess.run([sys.executable, "-c", script, str(wav)], capture_output=True, encoding="utf-8", check=False,
                         cwd=Path(export.__file__).parents[2])
    assert run.returncode == 0, run.stderr
    same_length, ratio = run.stdout.split()
    assert same_length == "True" and float(ratio) == pytest.approx(10 ** (-6 / 20), rel=0.01)
