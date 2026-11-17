import QtQuick

// Lớp nổi đè lên nội dung cuộn (thanh nghe thử, lời báo, thanh bên mở tạm, đầu trang dính...): đặt làm con ĐẦU TIÊN của lớp, dưới mọi nút.
// Nó nhận mọi cú bấm rơi vào chỗ trống / phần đệm của lớp để cú bấm không lọt xuống dòng nằm bên dưới. Lăn chuột không bị giữ lại: danh
// sách bên dưới vẫn cuộn được. Nút trong lớp phải đặt `exclusiveTap: true` (Interactive): TapHandler thụ động mặc định để cú bấm đi tiếp tới
// TapHandler của thứ nằm dưới lớp dù TapShield đã nhận (đo bằng tests/qml/tst_tapthrough.qml). Máy dò: scripts/ui_parity_rules.py (L12).
MouseArea {
    objectName: "tapShield"
    anchors.fill: parent
    acceptedButtons: Qt.AllButtons
}
