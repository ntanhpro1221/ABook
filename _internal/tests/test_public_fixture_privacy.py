"""Prevent private sentence fixtures from entering the public repository."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/public_fixture_guard.py"
spec = importlib.util.spec_from_file_location("public_fixture_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_public_fixture_privacy():
    failures = guard.audit()
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("field", ["sentence", "source_text", "words", "vietnamese_names", "source_sha256", "sent_sha256"])
def test_rejects_context_fields_even_for_short_values(field):
    assert guard.violations({field: ["private"]})


def test_rejects_eight_phonetic_syllables_and_accepts_tokens():
    assert guard.violations({"phonemes": " ".join(["kˈaː"] * 8)})
    assert guard.violations({"syllables": ["ka"] * 8})
    assert not guard.violations({"token": "Katou", "phones": ["kˈaː t̪ˈə1w"]})


def test_old_leaked_calibration_is_rejected():
    # Local audit only: the unsafe commit is deliberately NOT a new-branch ancestor.
    proc = subprocess.run(["git", "show", "9062518d4:_internal/tests/data/g2pgate/calibration.json"],
                          cwd=guard.REPO, capture_output=True)
    if proc.returncode:
        pytest.skip("Unsafe historical blob absent from this clone; synthetic leak tests still run")
    findings = guard.violations(json.loads(proc.stdout))
    assert any("8 consecutive" in item for item in findings)
    assert any("context field" in item for item in findings)
    print(f"Historical unsafe calibration rejected: {len(findings)} findings (no values logged)")
