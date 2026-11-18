import QtQuick

// Lớp nổi đè lên nội dung (Đang nghe, bảng nổi, hộp thoại, thanh nghe thử, lời báo, thanh bên mở tạm, đầu trang dính...): đặt làm con ĐẦU TIÊN của
// lớp, dưới mọi nút. Ba việc:
//  - giữ riêng cú bấm trái / phải / giữa rơi vào lớp (chỗ trống, phần đệm, chữ) để nó không tới thứ nằm dưới. Nút Back / Forward của chuột thì để
//    đi tiếp: TapHandler Back ở Main.qml đóng Đang nghe / lùi trang ở bất cứ đâu, kể cả trên lớp nổi. Không dùng MouseArea: đo 17-11, MouseArea
//    (kể cả chỉ nhận trái) cộng HoverHandler cùng chỗ thì nuốt luôn nút Back; và MouseArea nhận cú bấm vẫn để TapHandler thụ động của thứ nằm dưới
//    lớp thấy nó khi nút của lớp đã giữ cú bấm thụ động (tests/qml/tst_tapthrough.qml). TapHandler giữ riêng thì chặn được cả hai;
//  - giữ con trỏ trên lớp: dòng nằm dưới không sáng hover, không hiện chú thích, không đổi con trỏ thành bàn tay (HoverHandler của chính lớp và
//    tổ tiên vẫn thấy con trỏ, như panel của Sidebar);
//  - đánh dấu lớp: mọi Interactive là con cháu của cha nó tự giữ riêng cú bấm (Interactive.holdsTap).
// Cú kéo không bị giữ: Flickable trong lớp vẫn cuộn. Lăn chuột mặc định đi qua (thanh nghe thử, đầu trang dính, lời báo: trang dưới vẫn lăn được);
// lớp che trang [holdsWheel] (Đang nghe, bảng nổi, hộp thoại) giữ cả lăn chuột - soát 18-11: lăn trên bìa Đang nghe làm thư viện khuất cuộn đi,
// lăn trên bảng làm trang dưới trôi khỏi neo. Flickable TRONG lớp nhận lăn trước khiên (nằm trên nó), nên danh sách trong lớp vẫn lăn; hết đà thì
// cú lăn dừng ở khiên. Máy dò: scripts/ui_parity_rules.py (L12) - khiên phải là con đầu tiên.
Item {
    id: root
    property bool holdsWheel: false
    objectName: "tapShield"
    anchors.fill: parent
    TapHandler {
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        gesturePolicy: TapHandler.ReleaseWithinBounds
    }
    HoverHandler { cursorShape: Qt.ArrowCursor }
    // Không nhận nút nào (Back vẫn đi tiếp), không hover: chỉ giữ cú lăn.
    MouseArea { anchors.fill: parent; enabled: root.holdsWheel; acceptedButtons: Qt.NoButton; onWheel: wheel => wheel.accepted = true }
}
