"""Bộ dựng nhạc nền ngoại tuyến của bản xuất "Kèm nhạc nền" (webui/music_render.py): qua đủ 7 fixture `music_render` của Music (cùng bộ
fixture bản Kotlin phải qua), chạy theo khối ra từng bit như chạy một lần, giọng không bao giờ bị nhân, trần đỉnh giữ.

Fixture chỉ có tham số (repo công khai): tín hiệu dựng lại theo đúng công thức của bộ sinh (LLM_Train/music/mixqa/make_render_fixtures.py):
x[k] = tổng amp * sin(2 pi freq k / rate + phase) trên [round(from*rate), round(to*rate)); bài im `lead` giây đầu, `trail` giây cuối."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from abook.webui import music_render as R
from abook.webui.music_mix import MIX

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "music_render"
CASES = sorted(FIXTURES.glob("*.json"))
EXPORT_KEYS = ("exportCeilingDbtp", "exportGuardHeadroomDb", "exportGuardAttackMs", "exportGuardReleaseMs", "truePeakFir")


def _signal(components: list[dict[str, Any]], n: int, rate: int) -> np.ndarray:
    x = np.zeros(n, dtype=np.float64)
    k = np.arange(n, dtype=np.float64)
    for c in components:
        a = round(float(c.get("from", 0.0)) * rate)
        b = n if c.get("to") is None else min(n, round(float(c["to"]) * rate))
        x[a:b] += float(c["amp"]) * np.sin(2 * np.pi * float(c["freq"]) * k[a:b] / rate + float(c.get("phase", 0.0)))
    return x


def _track(spec: dict[str, Any], rate: int) -> np.ndarray:
    n = round(float(spec["seconds"]) * rate)
    x = _signal(spec["components"], n, rate)
    x[: round(float(spec.get("lead", 0.0)) * rate)] = 0.0
    tail = round(float(spec.get("trail", 0.0)) * rate)
    if tail:
        x[n - tail:] = 0.0
    return x[:, None]


def _expected(case: dict[str, Any]) -> dict[str, Any]:
    """Đúng phép tính kỳ vọng của bộ sinh fixture: điểm dò, g ở điểm dò, RMS 100 ms, thống kê bộ chặn, bài thiếu, sha256 int16."""
    rate, n = case["rate"], round(case["seconds"] * case["rate"])
    voice = _signal(case["voice"], n, rate)[:, None]
    tracks = {name: _track(spec, rate) for name, spec in case["tracks"].items()}
    bus, missing = R.render_bus(case["timeline"], n, rate, 1, tracks.get)
    out, g = R.guard(voice, bus, rate, case["mix"])
    pcm = R.to_int16(out)[:, 0]
    idx = set(np.linspace(0, n - 1, 32).astype(int).tolist())
    for element in case["timeline"]:
        for t, _db in element["gain"]:
            k = round(float(t) * rate)
            idx |= {min(n - 1, max(0, k + d)) for d in (-3, 0, 3)}
    if g.min() < 1.0:
        k = int(np.argmin(g))
        idx |= {min(n - 1, max(0, k + d)) for d in (-40, -5, 0, 5, 40)}
    idx = sorted(idx)
    win = rate // 10
    rms = []
    for a in range(0, n - win + 1, win):
        r = float(np.sqrt(np.mean(out[a:a + win, 0] ** 2)))
        rms.append(round(20 * math.log10(r), 2) if r > 0 else None)
    return {"probes": [[k, int(pcm[k])] for k in idx], "gainProbes": [[k, round(float(g[k]), 12)] for k in idx],
            "rmsDb": rms, "guard": R.guard_stats(g, rate), "missing": missing,
            "sha256": hashlib.sha256(pcm.astype("<i2").tobytes()).hexdigest()}


def test_all_seven_render_fixtures_are_here() -> None:
    assert [path.stem for path in CASES] == ["fade_in_out", "guard_hot", "loop_crossfade", "missing_track", "short_loop",
                                             "sibling_step", "voice_over_ceiling"]


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_the_fixture_uses_the_shared_constants(path: Path) -> None:
    """Fixture tự đủ (mang `mix`), nhưng phải được sinh bằng đúng hằng số app đang đọc - kể cả đệm 0,75 dB."""
    mix = json.loads(path.read_text(encoding="utf-8"))["mix"]
    assert {key: mix[key] for key in EXPORT_KEYS} == {key: MIX[key] for key in EXPORT_KEYS}
    assert MIX["exportGuardHeadroomDb"] == 0.75


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_the_fixture_reproduces(path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    assert _expected(case) == case["expected"]


def _signals(seed: int, n: int, channels: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    k = np.arange(n)[:, None]
    voice = 0.55 * np.sin(2 * np.pi * 900 * k / 48000 + rng.uniform(0, 6, channels)) * (np.sin(2 * np.pi * 3 * k / 48000) > 0)
    voice += 0.25 * rng.standard_normal((n, channels)) * 0.3
    bus = 0.45 * np.sin(2 * np.pi * 330 * k / 48000 + rng.uniform(0, 6, channels))
    return voice, bus


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("block", [4096, 1000, 257, 7])
def test_any_block_size_gives_the_same_bits_as_one_pass(channels: int, block: int) -> None:
    voice, bus = _signals(channels, 48000 * 2 + 123, channels)
    out_whole, g_whole = R.guard(voice, bus, 48000)
    out_blocks, g_blocks = R.guard(voice, bus, 48000, block=block)
    assert (g_whole < 1).any(), "tín hiệu thử phải làm bộ chặn chạy"
    assert np.array_equal(g_whole, g_blocks)
    assert np.array_equal(out_whole, out_blocks)


def test_the_voice_is_never_scaled_and_the_ceiling_holds() -> None:
    voice, bus = _signals(3, 48000, 1)
    out, g = R.guard(voice, bus, 48000)
    assert np.abs(out - g[:, None] * bus - voice).max() < 1e-12
    ceiling = MIX["exportCeilingDbtp"] - MIX["exportGuardHeadroomDb"]
    # đỉnh theo đúng nội suy của bộ chặn: không vượt max(trần, đỉnh của giọng một mình) quá 0,05 dB (g đổi trong chân lọc)
    assert R.true_peak_db(out, MIX["truePeakFir"]) <= max(ceiling, R.true_peak_db(voice, MIX["truePeakFir"])) + 0.05


def test_the_bus_rendered_in_blocks_equals_one_pass() -> None:
    case = json.loads((FIXTURES / "sibling_step.json").read_text(encoding="utf-8"))
    rate, n = case["rate"], round(case["seconds"] * case["rate"])
    tracks = {name: _track(spec, rate) for name, spec in case["tracks"].items()}
    whole, _ = R.render_bus(case["timeline"], n, rate, 1, tracks.get)
    parts = [R.render_bus(case["timeline"], min(999, n - a), rate, 1, tracks.get, start=a)[0] for a in range(0, n, 999)]
    assert np.array_equal(np.concatenate(parts), whole)
