"""The phone parity snapshot must describe the desktop frontend as it is now.

G2pGateParityTest.kt compares the phone against desktop_parity.json, so a stale
snapshot would let both platforms drift together unnoticed. CPU only, no models.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/g2pgate/desktop_parity.json"


def _generator():
    spec = importlib.util.spec_from_file_location("generate_g2p_parity", ROOT / "scripts/generate_g2p_parity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_desktop_parity_snapshot_matches_current_desktop_output():
    generator = _generator()
    stored = json.loads(FIXTURE.read_text("utf8"))
    current = generator.payload(generator.public_cases())
    stale = [
        c["id"] for c, n in zip(stored["cases"], current["cases"]) if c != n
    ]
    assert len(stored["cases"]) == len(current["cases"]), "token count changed; regenerate the snapshot"
    assert not stale, f"{len(stale)} stale cases, first {stale[:10]}: run scripts/generate_g2p_parity.py"
    assert stored == current


def test_snapshot_carries_no_stale_build_identity():
    # A frozen quality hash cannot be kept true; it is checked dynamically instead.
    assert "quality_hash" not in json.loads(FIXTURE.read_text("utf8"))
