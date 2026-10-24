from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_connection_notes_state_the_eight_address_cap():
    section = (DOCS / "CHANGELOG.md").read_text(encoding="utf-8").split("## [0.4.134]", 1)[1].split("\n## [", 1)[0]
    connection = section.split("### Kết nối", 1)[1].split("\n### ", 1)[0]
    assert "nhớ tối đa 8 địa chỉ" in connection


def test_android_tink_notice_identifies_version_license_and_signature_role():
    text = (DOCS / "THIRD_PARTY.md").read_text(encoding="utf-8")
    android = text.split("## App điện thoại (Android)", 1)[1].split("## Nhạc nền", 1)[0]
    assert "Tink Android 1.24.0" in android
    assert "com.google.crypto.tink:tink-android:1.24.0" in android
    line = next(line for line in android.splitlines() if "Tink Android 1.24.0" in line)
    assert "Apache-2.0" in line and "kiểm chữ ký" in line
