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
    signal clicked()
    signal rightClicked()

    activeFocusOnTab: true
    scale: pressed && pressScaling && !Theme.reduceMotion ? Theme.pressScale : 1
    Behavior on scale {
        NumberAnimation {
            duration: root.pressed ? Theme.motionFastOut : Theme.motionFast
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
        onHoveredChanged: {
            if (hovered && root.tip) tipTimer.restart()
            else { tipTimer.stop(); Nav.hideTip(root) }
        }
    }
    // Bấm bắt đầu dưới một bảng nổi / hộp thoại đang mở (Nav.coveredFor): không phải bấm vào nút này
    property bool _covered: false
    TapHandler {
        id: tap
        onTapped: { if (root._covered) return; root.forceActiveFocus(Qt.MouseFocusReason); root.clicked() }
        onPressedChanged: if (pressed) { Nav.hideTip(root); root._covered = Nav.coveredFor(root) }
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onPressedChanged: if (pressed) root._covered = Nav.coveredFor(root)
        onTapped: { if (root._covered) return; root.forceActiveFocus(Qt.MouseFocusReason); root.rightClicked() }
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
        visible: (root.activeFocus || root.externalFocus) && Platform.keyboardNav
    }
}
