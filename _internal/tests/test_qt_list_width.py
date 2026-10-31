"""Danh sách chữ của bản Qt lấy bề ngang qua MỘT hàm chung Theme.listWidth (soát UI nhạc 01-11 mục 4, Lead duyệt).

Cài đặt > Nghe > Nhạc của tôi từng cắt danh sách bài ở 640 px (Theme.listMeasure) trong khi mọi công tắc / mũi tên của cả trang thẳng ở mép cột
888 px: mép phải lởm chởm. Luật (DESIGN.md "Danh sách chữ"): trang tự do giữ hàng tối đa 640 px; trong cột Cài đặt (`wholeRows: true`) danh sách
chạy hết cột như các hàng quanh nó. Một danh sách mới tự cắt `Math.min(..., Theme.listMeasure)` sẽ lại lởm chởm khi nằm trong Cài đặt - test đỏ.
"""
from __future__ import annotations

import re
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "desktop_qt" / "qml"

# Chỗ dùng thẳng listMeasure có lý do riêng, không phải một danh sách nằm giữa các hàng chạy hết cột.
DIRECT = {
    "Theme.qml": "định nghĩa listMeasure và listWidth",
    "BookPage.qml": "trang sách: cột bìa + danh sách chương tính khổ cả khối (tối đa 1360)",
    "LibraryContinue.qml": "hàng 'Nghe tiếp' trên lưới bìa của Thư viện, trang tự do",
    "PhoneSync.qml": "hai cột Máy này / Máy đã ghép tự chia khổ theo độ rộng (wideT)",
}


def test_lists_take_their_width_from_the_shared_rule():
    direct = sorted(p.name for p in QML.glob("*.qml") if "Theme.listMeasure" in p.read_text(encoding="utf-8") or p.name == "Theme.qml")
    assert direct == sorted(DIRECT)


def test_the_settings_column_lets_lists_run_its_whole_width():
    theme = (QML / "Theme.qml").read_text(encoding="utf-8")
    assert re.search(r"function listWidth\(column, available\).*wholeRows === true\) return available; return Math\.min\(available, listMeasure\)", theme)
    settings = (QML / "SettingsScreen.qml").read_text(encoding="utf-8")
    assert re.search(r'objectName: "settingsContent"\s*\n\s*property bool wholeRows: true', settings)
    assert "Theme.listWidth(parent, parent.width)" in (QML / "MyMusicSettings.qml").read_text(encoding="utf-8")
