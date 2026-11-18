import QtQuick
import ABook

// Nền chung cho mọi thứ bấm được: rê chuột (con trỏ bàn tay + chú thích), nhấn (thu 0,97 theo DESIGN 5.2), bàn phím (Tab, Enter / Space)
// và vòng tiêu điểm - chỉ vẽ khi đang dùng bàn phím (Platform.keyboardNav), bấm chuột thì không hiện.
Item {
    id: root
    property alias hovered: hover.hovered
    readonly property bool pressed: tap.pressed
    property string tip: ""
    property real ringRadius: Theme.radiusControl
    property real ringMargin: 2
    property real ringHeight: -1          // >= 0: vòng chỉ bao phần cao này (ô có chữ dưới bìa chỉ bao bìa)
    property bool pressScaling: true
    property bool externalFocus: false     // ô trong lưới / danh sách: danh sách giữ tiêu điểm, ô chỉ được tô vòng
    // Giữ riêng cú bấm từ lúc nhấn (TapHandler.ReleaseWithinBounds), không để nó đi tiếp xuống thứ bấm được nằm dưới. Đo 17-11
    // (tests/qml/tst_tapthrough.qml): TapHandler thụ động mặc định để cú bấm tới cả TapHandler của Interactive nằm DƯỚI (bìa / dòng thư viện dưới
    // Đang nghe). Vì vậy mọi Interactive nằm trong một lớp có TapShield (con đầu tiên của một tổ tiên: Đang nghe, bảng nổi, hộp thoại, lời báo,
    // thanh bên mở tạm...) TỰ giữ riêng - kể cả hàng của ListView, nội dung của Loader nằm trong lớp - không nút nào phải tự nhớ đặt cờ.
    // `exclusiveTap` chỉ cần cho thứ nổi không có TapShield. Máy dò: scripts/ui_parity_rules.py (L12). Flickable vẫn giành được cú kéo
    // (TapHandler chấp nhận nhường), nên cuộn vẫn chạy (tests/width/tst_nowplaying_tapthrough.qml).
    property bool exclusiveTap: false
    readonly property bool holdsTap: exclusiveTap || layer.shielded
    signal clicked()
    signal rightClicked()

    activeFocusOnTab: true
    scale: pressed && pressScaling && Nav.uiVisible && !Theme.reduceMotion ? Theme.pressScale : 1
    Behavior on scale {
        NumberAnimation {
            duration: root.pressed ? Theme.motionFastOut : Theme.motionFast
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }

    // Dò một lần khi dựng xong và mỗi khi đổi cha (không ràng buộc: đọc `children` trong binding sẽ chạy lại cho mọi hàng mỗi lần ListView thêm hàng).
    // O(độ sâu): chỉ nhìn con đầu tiên của mỗi tổ tiên - TapShield luôn là con đầu (L12 kiểm).
    QtObject {
        id: layer
        property bool shielded: false
        function scan() {
            for (let p = root.parent; p; p = p.parent) {
                const first = p.children.length ? p.children[0] : null
                if (first instanceof TapShield) return true
            }
            return false
        }
    }
    Component.onCompleted: layer.shielded = layer.scan()
    onParentChanged: layer.shielded = layer.scan()

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
        onHoveredChanged: {
            if (hovered && root.tip) tipTimer.restart()
            else { tipTimer.stop(); Nav.hideTip(root) }
        }
    }
    TapHandler {
        id: tap
        gesturePolicy: root.holdsTap ? TapHandler.ReleaseWithinBounds : TapHandler.DragThreshold
        onTapped: { root.forceActiveFocus(Qt.MouseFocusReason); root.clicked() }
        onPressedChanged: if (pressed) Nav.hideTip(root)
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: { root.forceActiveFocus(Qt.MouseFocusReason); root.rightClicked() }
    }
    Timer { id: tipTimer; interval: 600; onTriggered: Nav.showTip(root, root.tip) }

    Keys.onReturnPressed: root.clicked()
    Keys.onEnterPressed: root.clicked()
    Keys.onSpacePressed: root.clicked()

    Rectangle {
        x: -root.ringMargin
        y: -root.ringMargin
        width: root.width + 2 * root.ringMargin
        height: (root.ringHeight >= 0 ? root.ringHeight : root.height) + 2 * root.ringMargin
        radius: root.ringRadius + root.ringMargin
        color: "transparent"
        border.width: 2
        border.color: Theme.accent
        Reveal { shown: (root.activeFocus || root.externalFocus) && Platform.keyboardNav }
    }
}
