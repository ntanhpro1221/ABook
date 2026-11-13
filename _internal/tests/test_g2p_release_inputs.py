"""Release verification must fail closed when native parity inputs are absent."""
from pathlib import Path

import pytest
from scripts import release_gate as gate


def test_release_always_requires_parity_and_uses_runtime_dictionary(monkeypatch):
    for key in ("ABOOK_REQUIRE_G2P_PARITY", "ABOOK_SEA_G2P_DICT", "ABOOK_SEA_G2P_LIB"):
        monkeypatch.delenv(key, raising=False)
    inputs = gate.safe_env()
    assert inputs["ABOOK_REQUIRE_G2P_PARITY"] == "1"
    assert Path(inputs["ABOOK_SEA_G2P_DICT"]).is_file()
    assert Path(inputs["ABOOK_SEA_G2P_LIB"]).is_absolute()


def test_android_gate_fails_before_gradle_when_native_inputs_are_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ABOOK_SEA_G2P_LIB", str(tmp_path / "absent.dll"))
    monkeypatch.setattr(gate, "run_process", lambda *_: pytest.fail("Gradle must not run without parity inputs"))
    with pytest.raises(ValueError, match="Required G2P parity input absent: ABOOK_SEA_G2P_LIB"):
        gate.worker("android-unit")
