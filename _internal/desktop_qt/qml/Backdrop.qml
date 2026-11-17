import QtQuick

// Nền "bấm ra ngoài thì đóng" của lớp nổi (Popover / menu "…", ConnectionPopover, Modal): phủ cả cửa sổ dưới bảng. Cú bấm trái / phải / giữa ra ngoài
// bảng chỉ ĐÓNG lớp, không tới thứ nằm dưới - như DropdownMenu / Dialog của web (Radix chặn cú bấm ra ngoài). Soát 18-11: nền cũ là MouseArea; nó nhận
// cú bấm nhưng TapHandler thụ động của nút nằm dưới (Interactive) vẫn thấy cú bấm ấy, nên bấm ra ngoài vừa đóng menu vừa mở cuốn sách / dòng dưới.
// TapHandler giữ riêng cú bấm thì chặn được (cùng lý do TapShield chặn được). Nút Back / Forward của chuột đi tiếp tới Main.qml (đóng lớp qua Nav).
// [holdsWheel]: lăn chuột trên nền không cuộn trang dưới (bảng không trôi khỏi neo, trang sau hộp thoại đứng yên).
Item {
    id: root
    signal dismissed()
    property bool holdsWheel: true
    objectName: "backdrop"
    anchors.fill: parent
    TapHandler {
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        gesturePolicy: TapHandler.ReleaseWithinBounds
        onPressedChanged: if (pressed) root.dismissed()
    }
    MouseArea { anchors.fill: parent; enabled: root.holdsWheel; acceptedButtons: Qt.NoButton; onWheel: wheel => wheel.accepted = true }
}
