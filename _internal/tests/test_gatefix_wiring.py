"""Source-only checks for gates that must not build or launch apps on battery."""
from pathlib import Path
import json
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_every_quicktest_directory_has_a_cmake_source_and_a_bat_invocation():
    cmake = (ROOT / "desktop_qt/CMakeLists.txt").read_text(encoding="utf-8")
    batch = (ROOT / "desktop_qt/build.bat").read_bytes()
    assert b"\n" not in batch.replace(b"\r\n", b"")
    for directory in (ROOT / "desktop_qt/tests").iterdir():
        if list(directory.glob("tst_*.qml")):
            assert f'/tests/{directory.name}"' in cmake, directory.name
    assert 'add_test(NAME HitlTests COMMAND HitlTests)' in cmake
    assert b'call :test "%HERE%build\\hitl_tests\\HitlTests.exe"' in batch


def test_external_unit_tests_are_discovered_and_browser_has_a_separate_marker():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert "scripts/tap_audit" in config["testpaths"]
    assert "mobile/android/scripts/test_phone_frames.py" in config["testpaths"]
    assert config["xfail_strict"] and config["empty_parameter_set_mark"] == "fail_at_collect"
    assert "pytestmark = pytest.mark.browser" in (ROOT / "scripts/tap_audit/test_sheetgeo.py").read_text(encoding="utf-8")


def test_all_four_host_frontend_classes_use_the_required_input_contract():
    directory = ROOT / "mobile/android/app/src/test/java/vn/abook/player/vieneu"
    helper = (directory / "G2pTestInputs.kt").read_text(encoding="utf-8")
    assert 'System.getenv("ABOOK_REQUIRE_G2P_PARITY") == "1"' in helper
    assert 'assertTrue(message, available)' in helper
    for name in ("SeaG2pParityTest", "PhonemePolicyTest", "RealNamesTest", "EnglishDirectFrontendTest"):
        source = (directory / (name + ".kt")).read_text(encoding="utf-8")
        assert "G2pTestInputs.requireOrSkip(" in source and "assumeTrue(" not in source


def test_snapshot_proof_is_written_only_after_a_successful_verify():
    source = (ROOT / "mobile/android/app/src/test/java/vn/abook/player/ui/snapshot/UiTreeCapture.kt").read_text(encoding="utf-8")
    assert source.index("roborazziCapture(filePath, roborazziOptions)") < source.index('System.getenv("ABOOK_SNAPSHOT_PROOFS")')
    assert "roborazziOptions.taskType == RoborazziTaskType.Verify" in source
    properties = (ROOT / "mobile/android/gradle.properties").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*roborazzi\.test\.record\s*=\s*true", properties)
