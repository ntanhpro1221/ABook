"""Acceptance gate of the hidden-window CPU stage (desktop_qt/tools/idle2_stage.py): an empty audio endpoint counts only
before the bench's `done` event; the drain while the app exits is not a gap in the hidden window."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop_qt/tools"))
import idle2_stage  # noqa: E402


def test_selftest():
    idle2_stage.selftest()


def test_exit_drain_after_done_is_ignored():
    trace = "mix_wakes epoch_ms=900 count=1\ngraphics_idle_release epoch_ms=1014 x\nmix_device_empty written=6462240\n"
    got = {"d": {"events": [[100.0, "hide_begin"], [1000.0, "done"]], "epoch_offset_ms": 0.0}}
    assert idle2_stage.done_ms(got) == 1000.0
    assert idle2_stage.device_empty(trace, idle2_stage.done_ms(got)) == 0
    assert idle2_stage.device_empty(trace.replace("1014", "999"), idle2_stage.done_ms(got)) == 1
