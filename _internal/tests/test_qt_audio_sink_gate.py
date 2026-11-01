"""desktop_qt/tools/audio_sink.py as the release gate: build.bat package / installer plays the packaged app and listens.

01-11 on 0.4.152 the ear was red on every run for two things the listener never hears: the reported position lags the
truth by 0..10 ms (the mixer's cursor follows the device padding, one 10 ms engine period at a time) and a consonant pop
of the recording that Sonic copies intact at x3, 22 ms (listener) from where the app says it is. A third came on run 5:
a slope bend Sonic's own crossfade makes (offline Sonic built from the same sonic.c makes them too). These tests keep
all three silent and keep real faults red, on a synthetic run shaped like the bench scenario.

The same day it heard a fault the listener does hear: at the end of chapter 1 the music stopped with the voice (-30 -> -91 dB
in 6 ms). The sudden-silence detector ("cut") came in with the fix, red on 0.4.152.

When the voice stalls (network gone mid-chapter) the music must hold for voiceStallFadeAfterSeconds, then fade out the
chapter-end way, and come back when the voice moves again. The bench seeks into a range tools/stall_host makes the app's
host hold for 25 s; the synthetic stall run below has the same shape.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "desktop_qt"
spec = importlib.util.spec_from_file_location("audio_sink", ROOT / "tools/audio_sink.py")
sink = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sink)


def kinds(data):
    return {f["kind"] for f in sink.check(data)["findings"]}


def test_build_bat_gates_package_and_installer_on_the_ear():
    bat = (ROOT / "build.bat").read_text(encoding="ascii")
    gate = bat.index('tools\\audio_sink.py" gate "%HERE%dist\\ABookDesk.exe"')
    assert bat.index('if /i "%1"=="package" set AUDIO_GATE=1') < gate
    assert bat.index('if /i "%1"=="installer" set AUDIO_GATE=1') < gate
    # after the packaged smoke start, before the installer is built
    assert bat.index("smoke_dist.py") < gate < bat.index('-File "%HERE%..\\scripts\\build_windows_qt.ps1"')
    assert bat[gate:].index("if errorlevel 1 (") < bat[gate:].index("exit /b 1") < bat[gate:].index("rem build.bat package:")


@pytest.mark.parametrize("speed", [1.0, 3.0])
def test_cursor_sawtooth_is_not_drift(speed):
    assert kinds(sink.synthetic_run(speed, saw_ms=10.0)) == set()


@pytest.mark.parametrize("frac", [0.003, -0.005])
def test_real_drift_from_mid_segment_is_red(frac):
    assert "drift" in kinds(sink.synthetic_run(3.0, drift=frac))


def test_source_pop_counts_in_listener_time():
    report = sink.check(sink.synthetic_run(3.0, lead_ms=22, source_step_at=60.0))
    assert "click" not in {f["kind"] for f in report["findings"]}
    # the pop is heard and forgiven by name, so the gate summary shows it per run
    assert any(abs(e["source"] - 60.0) < 0.05 for e in report["excused"])
    assert "click" in kinds(sink.synthetic_run(1.0, lead_ms=66, source_step_at=15.0))


def test_strength_goes_red_with_a_deaf_drift_detector(monkeypatch):
    data = sink.synthetic_run(3.0)
    ok, results = sink.strength(data, stall=False)
    assert ok, [r for r in results if not r["ok"]]
    monkeypatch.setattr(sink, "DRIFT_MS", 1e9)
    ok, results = sink.strength(data, stall=False)
    assert not ok
    assert all(r["ok"] for r in results if not r["case"].startswith("trôi"))


@pytest.mark.parametrize("bump, red", [(0.01, True), (0.03, False)])
def test_source_must_be_half_as_sharp_to_excuse_a_click(bump, red):
    # Sonic copies the source's own transients (and a splice may sharpen one), so a sink click is the source's when the
    # source holds a transient at least half as sharp in the window; a faint source feature excuses nothing.
    data = sink.synthetic_run(1.0)
    rate = data["rate"]
    ticks = [m for m in data["marks"] if m["tag"] == "tick" and 10 * rate < m["frame"] < 20 * rate]
    a, b = ticks[0], ticks[1]
    f = (a["frame"] + b["frame"]) // 2
    p = int((a["position"] + (f - a["frame"]) / rate) * rate)
    source, mono = data["source"].copy(), data["mono"].copy()
    source[p:] += bump
    mono[f:f + rate // 100] += 0.05
    report = sink.check(dict(data, source=source, mono=mono))
    assert any(x["kind"] == "click" and abs(x["t"] * rate - f) < rate // 1000 for x in report["findings"]) == red


@pytest.mark.parametrize("speed, size, red", [(3.0, 0.025, False), (3.0, 0.04, True), (1.0, 0.025, True)])
def test_sonic_segments_carry_their_own_floor(speed, size, red):
    # Sonic's crossfaded splices bend the slope by up to 0.0205 where the source is smooth (01-11 run 5 at x3), so a
    # segment where Sonic runs needs 0.03; speed 1 copies the source and keeps 0.02.
    data = sink.synthetic_run(speed)
    rate = data["rate"]
    lo, hi = (30, 45) if speed != 1.0 else (10, 20)
    ticks = [m for m in data["marks"] if m["tag"] == "tick" and lo * rate < m["frame"] < hi * rate]
    f = (ticks[0]["frame"] + ticks[1]["frame"]) // 2
    mono = data["mono"].copy()
    mono[f:f + rate // 100] += size
    report = sink.check(dict(data, mono=mono))
    assert any(x["kind"] == "click" and abs(x["t"] * rate - f) < rate // 1000 for x in report["findings"]) == red


def test_music_stopping_with_the_voice_is_a_cut():
    data = sink.synthetic_run(1.0)
    rate = data["rate"]
    mono = data["mono"].copy()
    mono[10 * rate: 10 * rate + rate * 3 // 10] = 0
    report = sink.check(dict(data, mono=mono))
    assert any(f["kind"] == "cut" and abs(f["t"] - 10) < 0.02 for f in report["findings"])


def test_a_voice_that_goes_silent_by_itself_is_not_a_cut():
    # TTS hard-cut at a sentence end with no music under it: the sink copies the source, so the silence is the recording's
    assert "cut" not in kinds(sink.synthetic_run(1.0, source_quiet_at=12.0))


@pytest.mark.parametrize("tag", ["pause", "stop"])
def test_silence_right_after_a_listener_action_is_not_a_cut(tag):
    # synthetic_run goes silent exactly at pause and stop; the frame before the fall may sit up to 20 ms before the action
    data = sink.synthetic_run(1.0)
    at = next(m["frame"] for m in data["marks"] if m["tag"] == tag) / data["rate"]
    assert not any(f["kind"] == "cut" and abs(f["t"] - at) < 0.1 for f in sink.check(data)["findings"])


def test_strength_goes_red_with_a_deaf_cut_detector(monkeypatch):
    data = sink.synthetic_run(3.0)
    monkeypatch.setattr(sink, "CUT_TO_DB", -1e9)
    ok, results = sink.strength(data, stall=False)
    assert not ok
    assert [r["case"] for r in results if not r["ok"]] == [next(r["case"] for r in results if r["case"].startswith("đột im"))]


def test_a_stalled_voice_holds_then_fades_the_music_then_brings_it_back():
    report = sink.check(sink.synthetic_stall_run())
    assert report["findings"] == []
    stall = report["stall"]
    assert stall["resumed"] and stall["early_db"] > sink.STALL_MUSIC_DB > stall["return_db"] - 20
    assert stall["late_peak_db"] < sink.STALL_QUIET_DB


@pytest.mark.parametrize("fault, kind", [("keep", "stall_music"), ("early", "stall_early"), ("abrupt", "cut"), ("noreturn", "stall_return")])
def test_each_wrong_stall_shape_is_red(fault, kind):
    assert kind in kinds(sink.synthetic_stall_run(fault))


def test_a_run_without_a_stall_window_fails_the_gate_strength():
    ok, results = sink.strength(sink.synthetic_run(3.0))
    assert not ok and [r["case"] for r in results if not r["ok"]] == ["khựng"]


def test_stall_strength_goes_red_with_a_deaf_fade_detector(monkeypatch):
    data = sink.synthetic_stall_run()
    assert all(r["ok"] for r in sink.stall_strength(data, sink.check(data)))
    monkeypatch.setattr(sink, "STALL_QUIET_DB", 1e9)
    results = sink.stall_strength(data, sink.check(data))
    assert [r["case"] for r in results if not r["ok"]] == ["khựng: nhạc không mờ"]


def test_stall_hook_is_inert_without_its_variable():
    hook = (ROOT / "tools/stall_host/sitecustomize.py").read_text(encoding="utf-8")
    assert 'SPEC = os.environ.get("ABOOK_TEST_VOICE_STALL", "")' in hook and hook.rstrip().endswith("if SPEC:\n    sys.meta_path.insert(0, _After())")
    assert "stall_host" not in (ROOT / "build.bat").read_text(encoding="ascii")  # never shipped
