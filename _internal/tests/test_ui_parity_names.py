"""Device and listening-profile names cannot be clipped, including by a generic exemption."""
import importlib.util
from pathlib import Path

import pytest


QT = Path(__file__).resolve().parents[1] / "desktop_qt"
SPEC = importlib.util.spec_from_file_location("name_text_cut", QT / "tools" / "check_text_cut.py")
TEXT_CUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TEXT_CUT)


def test_qt_device_and_profile_sources_do_not_clip():
    errors = [error for path in sorted((QT / "qml").glob("*.qml")) for error in TEXT_CUT.scan(path)]
    assert errors == [], "\n".join(errors)


@pytest.mark.parametrize("expression", [
    "device.name", "root.device.name", "computer.name", "peer.name", "target.name",
    "profile.name", "record.name", "modelData.name", "root.name", "computerName", "shownName",
])
@pytest.mark.parametrize("cut", ["elide: Text.ElideRight", "maximumLineCount: 1", "clip: true"])
def test_qt_detector_rejects_planted_names_even_with_exemption(tmp_path, expression, cut):
    fixture = tmp_path / "Device.qml"
    fixture.write_text(
        f"Text {{\n    text: {expression}\n    {cut} // text-cut-ok: compact row\n}}\n",
        encoding="utf-8", newline="\n",
    )
    assert len(TEXT_CUT.scan(fixture)) == 1


def test_qt_detector_accepts_full_name_fit(tmp_path):
    fixture = tmp_path / "Device.qml"
    fixture.write_text("OneLineFit { room: parent.width; text: device.name }\n", encoding="utf-8", newline="\n")
    assert TEXT_CUT.scan(fixture) == []


def test_qt_detector_keeps_unrelated_approved_exception(tmp_path):
    fixture = tmp_path / "Cover.qml"
    fixture.write_text(
        "Text {\n    text: book.title\n    elide: Text.ElideRight // text-cut-ok: cover grid\n}\n",
        encoding="utf-8", newline="\n",
    )
    assert TEXT_CUT.scan(fixture) == []
