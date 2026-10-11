"""Lô 2 mix-loop (Corpus/research/music/MIX_QA.md 3.2, 3.4, 3.5, 7.1, 9): một nguồn hằng số trộn nhạc (music_mix.json), số đo
mỗi bài (độ to ngắn hạn p95, đoạn nghe được), chặn gain theo đoạn to nhất, mốc mang A/E cho trình phát, và dòng thời gian thuần
`music_timeline` chạy cùng các fixture với trình phát web (musicBed.test.ts) và Android (MusicCuesTest.kt)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import soundfile

from abook.config import DEFAULT_SETTINGS
from abook.webui import book_edits, music_mix, music_plan, music_select
from tests.test_webui_listen_and_sync import make_project

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "music_timeline"
RATE = 48000


def _tone(seconds: float, amplitude: float = 0.1, frequency: float = 1000.0) -> np.ndarray:
    t = np.arange(round(seconds * RATE)) / RATE
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def test_the_mix_constants_are_read_from_the_one_file_the_players_bundle() -> None:
    values = json.loads((Path(music_plan.__file__).parent / "assets" / "music_mix.json").read_text(encoding="utf-8"))
    assert music_mix.MIX_FILE == Path(music_plan.__file__).resolve().parent / "assets" / "music_mix.json"
    assert music_mix.MIX == {key: [[float(x) for x in row] for row in value] if isinstance(value, list) else float(value)
                             for key, value in values.items()}
    assert all(isinstance(value, float) for key, value in music_mix.MIX.items() if key != "truePeakFir")
    assert [len(row) for row in music_mix.MIX["truePeakFir"]] == [12] * 4, "bảng nội suy x4 của bộ chặn đỉnh (music_render)"
    assert music_plan.CHAPTER_END_FADE_SECONDS == values["chapterEndFadeSeconds"]
    assert music_plan.VOICE_PLAYED_LUFS == values["voicePlayedLufs"]
    assert music_plan.SHORT_TERM_FLOOR_LU == values["shortTermFloorLu"] == 10
    assert music_plan.AUDIBLE_THRESHOLD_DBFS == values["audibleThresholdDbfs"] == -60
    assert music_select.CUE_MERGE_GAP_SECONDS == values["cueMergeGapSeconds"]
    assert music_select.TAIL_MIN_SECONDS == values["tailMinSeconds"]
    assert music_mix.LOOP_CROSSFADE_SECONDS == values["loopCrossfadeSeconds"]
    # Giọng phát hai loa = mức chuẩn hoá giọng của cài đặt + 10 log10 2: file ghi đúng số ấy (không lệch khi đổi cài đặt).
    assert math.isclose(values["voicePlayedLufs"], DEFAULT_SETTINGS["audio"]["loudness_lufs"] + 10 * math.log10(2), abs_tol=1e-9)


def test_the_short_term_p95_follows_the_loud_part_of_a_track_not_its_average() -> None:
    steady = _tone(10.0)
    integrated = music_plan.stereo_lufs(steady, RATE)
    assert math.isclose(music_plan.short_term_p95(steady, RATE), integrated, abs_tol=0.1), "tiếng đều: p95 = tích hợp"
    burst = np.concatenate([_tone(30.0, 0.1), _tone(6.0, 0.2)])  # cao trào 6 s to hơn 6 dB
    s95 = music_plan.short_term_p95(np.stack([burst, burst], axis=1), RATE)
    assert s95 - music_plan.stereo_lufs(np.stack([burst, burst], axis=1), RATE) > 3.0, "p95 nằm ở đoạn to"
    assert math.isclose(s95, music_plan.stereo_lufs(_tone(6.0, 0.2), RATE), abs_tol=0.5)
    assert music_plan.short_term_p95(_tone(2.0), RATE) is None, "ngắn hơn một cửa sổ 3 s"
    assert music_plan.short_term_p95(np.zeros(RATE * 5, dtype=np.float32), RATE) is None, "im hẳn"
    assert music_plan.short_term_p95(_tone(10.0), 44100) is None, "chỉ đo ở 48 kHz như lúc giải mã"


def test_the_audible_part_skips_the_silence_at_both_ends() -> None:
    signal = np.concatenate([np.zeros(RATE, dtype=np.float32), _tone(3.0), np.zeros(2 * RATE, dtype=np.float32)])
    assert music_plan.audible_bounds(signal, RATE) == (1.0, 4.0)
    quiet = np.stack([signal * 0.01, np.zeros_like(signal)], axis=1)  # đỉnh -66 dBFS sau khi trộn mono: dưới ngưỡng -60
    assert music_plan.audible_bounds(quiet, RATE) is None
    one_side = np.stack([signal, np.zeros_like(signal)], axis=1)
    assert music_plan.audible_bounds(one_side, RATE) == (1.0, 4.0), "trộn mono: một kênh kêu là kêu"
    assert music_plan.audible_bounds(signal, RATE, -10.0) is None, "ngưỡng cao hơn đỉnh bài"


def test_a_track_file_is_measured_once_with_loudness_peaks_length_and_audible_bounds(tmp_path: Path) -> None:
    signal = np.concatenate([np.zeros(RATE // 2, dtype=np.float32), _tone(8.0), np.zeros(RATE, dtype=np.float32)])
    cached = tmp_path / "a.mp3"
    soundfile.write(cached, np.stack([signal, signal], axis=1), RATE, format="WAV")
    measured = music_plan.measured_track(cached)
    assert set(measured) == {"lufs", "s95", "seconds", "audibleStart", "audibleEnd"}
    assert (measured["audibleStart"], measured["audibleEnd"], measured["seconds"]) == (0.5, 8.5, 9.5)
    assert math.isclose(measured["s95"], measured["lufs"], abs_tol=0.5)
    sidecar = cached.with_suffix(".measure.json")
    assert json.loads(sidecar.read_text(encoding="utf-8")) == measured, "ghi cạnh file cho lần sau"
    cached.write_bytes(b"not audio")  # giải mã thì hỏng: lần sau chỉ đọc số đã ghi
    assert music_plan.measured_track(cached) == measured
    assert music_plan.measured_lufs(cached) == measured["lufs"]


def test_an_old_loudness_sidecar_still_counts_until_the_file_is_measured_again(tmp_path: Path) -> None:
    cached = tmp_path / "b.mp3"
    cached.write_bytes(b"not audio")
    cached.with_suffix(".lufs2").write_text("-18.50\n", encoding="utf-8")
    assert music_plan.measured_track(cached, measure=False) == {"lufs": -18.5}, "đường nóng: không giải mã"
    assert music_plan.measured_track(cached) == {"lufs": -18.5}, "đo lại hỏng: vẫn giữ số cũ"
    info = {"lufs": -26.0, "s95": -20.0, "audibleStart": 1.0, "audibleEnd": 180.0}
    assert music_plan.track_measure(info, cached, measure=False) == {**info, "lufs": -18.5}, "số đo từ file thắng danh mục"


def test_the_gain_keeps_the_loudest_part_of_a_track_ten_lu_under_the_voice() -> None:
    voice = music_plan.VOICE_PLAYED_LUFS
    # Mức "To" (-14): bài -20 LUFS có p95 -12 -> theo LUFS tích hợp chỉ hạ 10,99 dB, đoạn to nhất còn cách giọng 6 LU.
    assert music_plan.cue_gain_db(-14.0, -20.0, 0.30) == -10.99
    assert music_plan.cue_gain_db(-14.0, -20.0, 0.30, -12.0) == round(voice - 10 - (-12.0), 2) == -14.99
    assert music_plan.cue_gain_db(-20.0, -20.0, 0.30, -18.0) == -16.99, "mức mặc định: sàn không chặn"
    assert music_plan.cue_gain_db(-20.0, -20.0, 0.30, None) == -16.99, "chưa đo p95: như cũ"


def test_cues_for_the_player_carry_the_audible_bounds_and_the_held_gain(tmp_path: Path) -> None:
    cached = tmp_path / "b.mp3"
    cached.write_bytes(b"not audio")
    cached.with_suffix(".measure.json").write_text(json.dumps(
        {"lufs": -20.0, "s95": -12.0, "seconds": 200.0, "audibleStart": 1.5, "audibleEnd": 190.25}), encoding="utf-8")
    cues = [{"link": "https://x/a.mp3", "key": "a"}, {"link": "https://x/b.mp3", "key": "b"},
            {"link": "https://x/c.mp3", "key": "c"}]
    tracks = {"https://x/a.mp3": {"lufs": -20.0, "speechBand": 0.3, "s95": -12.0, "audibleStart": 0.2, "audibleEnd": 99.0},
              "https://x/b.mp3": {"lufs": -26.0, "audibleStart": 0.0, "audibleEnd": 150.0}, "https://x/c.mp3": {}}
    music_plan.apply_gain(cues, -14.0, tracks, lambda link: cached if link.endswith("b.mp3") else None)
    assert cues[0]["gainDb"] == -14.99 and (cues[0]["audibleStart"], cues[0]["audibleEnd"]) == (0.2, 99.0), "số danh mục"
    assert cues[1]["gainDb"] == -14.99 and (cues[1]["audibleStart"], cues[1]["audibleEnd"]) == (1.5, 190.25), "số đo từ file thắng"
    assert "audibleStart" not in cues[2] and "audibleEnd" not in cues[2], "không biết: trình phát dùng 0 và độ dài thật"


def test_the_book_package_carries_the_audible_bounds_and_the_loud_part_of_each_track(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    plan = {"version": music_plan.PLAN_VERSION, "enabled": True, "levelDb": -14.0,
            "tracks": {"https://x/a.mp3": {"lufs": -20.0, "speechBand": 0.3}}, "scenes": [
                {"chapterId": 1, "key": "1:1", "start": 0.0, "end": 300.0, "link": "https://x/a.mp3"}]}
    (project / music_plan.PLAN_FILE).write_bytes(json.dumps(plan).encode("utf-8"))
    folder = tmp_path / "cache"
    folder.mkdir()

    def file(link: str) -> Path:
        path = folder / music_plan.track_name(link).split("/")[1]
        path.write_bytes(b"ID3")
        path.with_suffix(".measure.json").write_text(json.dumps(
            {"lufs": -20.0, "s95": -12.0, "seconds": 200.0, "audibleStart": 1.5, "audibleEnd": 190.25}), encoding="utf-8")
        return path

    music, _files = music_plan.package(project, [1], file)
    [cue] = music["chapters"]["1"]
    [track] = music["tracks"].values()
    assert (cue["audibleStart"], cue["audibleEnd"], cue["gainDb"]) == (1.5, 190.25, -14.99)
    assert track["s95"] == -12.0, "đổi mức trên máy nghe tính lại gain cũng chặn theo p95"
    [back] = music_plan.packaged_cues(json.loads(json.dumps(music)), 1)
    assert (back["audibleStart"], back["audibleEnd"]) == (1.5, 190.25)
    louder = book_edits.apply_music(music, {"music": {"levelDb": -10.0}})
    assert louder["chapters"]["1"][0]["gainDb"] == -14.99, "sách đóng gói: đổi mức vẫn chặn theo p95"
    old = {**music, "chapters": {"1": [{k: v for k, v in cue.items() if not k.startswith("audible")}]}}
    assert "audibleStart" not in music_plan.packaged_cues(old, 1)[0], "sách đóng gói cũ: trình phát dùng 0 và độ dài thật"


def test_the_loop_bounds_follow_the_audible_part_and_fall_back_to_the_whole_file() -> None:
    assert music_mix.loop_bounds(200.0, 1.5, 190.0) == (1.5, 190.0, 186.5, True)
    assert music_mix.loop_bounds(200.0) == (0.0, 200.0, 198.0, True), "thiếu A/E: 0 và độ dài thật"
    assert music_mix.loop_bounds(200.0, 1.5, 250.0) == (1.5, 200.0, 196.5, True), "E không vượt độ dài thật"
    assert music_mix.loop_bounds(10.0, 2.0, 7.0) == (0.0, 10.0, 10.0, False), "quá ngắn (E - A < 3X): lặp thường cả file"
    assert music_mix.loop_bounds(None) == (0.0, math.inf, math.inf, False)


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda path: path.stem)
def test_the_timeline_of_each_fixture(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    assert music_mix.music_timeline(case["cues"], case["chapterSeconds"], case["tracks"]) == case["timeline"]


def test_the_fixtures_cover_every_case_the_three_sides_check() -> None:
    names = {path.stem for path in FIXTURES.glob("*.json")}
    assert {"loop_crossfade", "sibling_tail", "stop_at", "chapter_end", "short_track"} <= names


ORIGINAL, SUBSTITUTE = "https://x/original.mp3", "https://x/substitute.mp3"


def test_a_substitute_track_in_the_book_package_drops_the_tail_and_carries_its_own_audible_part(tmp_path: Path) -> None:
    # Cờ `tail` chỉ đúng cho bài đã lập lịch (kết đúng ở `stopAt`): bài thay dài ngắn khác thì không được thôi lặp / vào sớm theo nó.
    project = make_project(tmp_path)
    plan = {"version": music_plan.PLAN_VERSION, "enabled": True, "levelDb": -20.0,
            "tracks": {ORIGINAL: {"lufs": -20.0}}, "scenes": [
                {"chapterId": 1, "key": "1:1", "start": 0.0, "end": 300.0, "stopAt": 200.0, "link": ORIGINAL}]}
    (project / music_plan.PLAN_FILE).write_bytes(json.dumps(plan).encode("utf-8"))
    folder = tmp_path / "cache"
    folder.mkdir()
    bounds = {ORIGINAL: (1.0, 150.0), SUBSTITUTE: (2.5, 120.0)}

    def file(link: str) -> Path:
        path = folder / music_plan.track_name(link).split("/")[1]
        path.write_bytes(b"ID3")
        start, end = bounds[link]
        path.with_suffix(".measure.json").write_text(json.dumps(
            {"lufs": -20.0, "s95": -15.0, "seconds": 160.0, "audibleStart": start, "audibleEnd": end}), encoding="utf-8")
        return path

    music, _files = music_plan.package(project, [1], file)
    [cue] = music["chapters"]["1"]
    assert cue.get("tail") is True and (cue["audibleStart"], cue["audibleEnd"]) == (1.0, 150.0), "bài gốc giữ cờ"

    def gone(link: str) -> Path | None:
        return None if link == ORIGINAL else file(link)

    source = music_plan.TrackSource(gone, lambda root, key, exclude: [{"link": SUBSTITUTE, "lufs": -20.0}])
    music, _files = music_plan.package(project, [1], source)
    [cue] = music["chapters"]["1"]
    assert cue["track"] == music_plan.track_name(SUBSTITUTE)
    assert "tail" not in cue, "bài thay không kết đúng ở stopAt"
    assert (cue["audibleStart"], cue["audibleEnd"]) == (2.5, 120.0), "đoạn nghe được của bài thay"


def test_a_substitute_track_on_the_player_drops_the_tail_and_what_was_measured_on_the_original() -> None:
    from abook.webui.server import App

    class Machine:
        def music_track_available(self, link: str) -> bool:
            return link != ORIGINAL

        def _music_alternatives(self, path: Path, key: str, exclude: list[str], limit: int | None = None,
                                available=None) -> list[dict]:
            return [{"link": SUBSTITUTE, "lufs": -20.0, "audibleStart": 2.5, "audibleEnd": 120.0}]

    planned = {"start": 0.0, "end": 200.0, "link": ORIGINAL, "key": "1:1", "tail": True,
               "gainDb": -9.0, "audibleStart": 1.0, "audibleEnd": 150.0}
    kept = {"start": 200.0, "end": 260.0, "link": SUBSTITUTE, "key": "1:2", "tail": True}
    tracks: dict = {}
    swapped, same = App._music_playable(Machine(), Path("."), [planned, kept], tracks)
    assert swapped["link"] == SUBSTITUTE and swapped["start"] == 0.0 and swapped["end"] == 200.0
    assert not {"tail", "gainDb", "audibleStart", "audibleEnd"} & set(swapped), "chỉ đúng cho bài gốc"
    assert same == kept, "bài dùng được: mốc giữ nguyên"
    music_plan.apply_gain([swapped], -20.0, tracks)
    assert (swapped["audibleStart"], swapped["audibleEnd"]) == (2.5, 120.0)
