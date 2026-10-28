import QtQuick
import ABook

// Nút (Button của shared/ui.tsx; DESIGN.md mục 6): chính (nền hổ phách, chữ mực-trên-nhấn), chữ (`ghost`: chữ --accent-text, rê chuột nền
// --hover) và nguy hiểm (nền --danger-soft chữ --danger, rê chuột nền đỏ đậm lên). Cao 40 mọi cỡ;
// sm 13 px đệm 12, md 14 px đệm 14, lg 15 px đệm 20 bo góc bìa. `wrap`: chữ dài (đường dẫn, tên mục) xuống dòng, nút cao thêm thay vì rộng
// hơn khung (WRAP_LABEL). `busy`: đang chạy việc - vòng xoay thay icon, vẫn giữ tiêu điểm; `activated` không phát khi busy (busyClick),
// nên nút có `busy` nối việc vào onActivated thay vì onClicked.
// Mỗi màn chỉ một nút chính. `kind: "text"` = `ghost` (tên cũ của D1).
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property string kind: "primary"     // "primary" | "ghost" (= "text") | "danger"
    property string size: "md"          // "sm" | "md" | "lg"
    property bool wrap: false
    property bool busy: false
    readonly property bool primary: kind === "primary"
    readonly property bool danger: kind === "danger"
    readonly property int pad: size === "sm" ? 12 : size === "lg" ? 20 : 14
    readonly property bool showsIcon: icon !== "" || busy
    readonly property real iconBox: showsIcon ? 16 + (size === "sm" ? 6 : 8) : 0
    readonly property color ink: primary ? Theme.accentInk : danger ? Theme.danger : Theme.accentText
    signal activated()

    Accessible.role: Accessible.Button
    Accessible.name: text
    implicitHeight: Math.max(Theme.buttonHeight, label.implicitHeight + 8)
    implicitWidth: label.implicitWidth + iconBox + 2 * pad
    opacity: enabled && !busy ? 1 : 0.45
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    onClicked: if (!busy) root.activated()

    Rectangle {
        anchors.fill: parent
        radius: root.size === "lg" ? Theme.radiusCover : Theme.radiusControl
        color: root.primary ? Theme.accent : root.danger ? Theme.dangerSoft : "transparent"
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: root.primary ? "#000000" : root.danger ? Theme.danger : Theme.hover
            opacity: root.primary ? (root.pressed ? Theme.pressShade : root.hovered ? 0.04 : 0)
                                  : root.danger ? (root.hovered || root.pressed ? 0.16 : 0)
                                                : (root.hovered || root.pressed ? 1 : 0)
            Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
        }
    }
    Item {
        id: lead
        visible: root.showsIcon
        x: Math.max(root.pad, (root.width - root.implicitWidth) / 2 + root.pad)
        width: 16
        height: 16
        anchors.verticalCenter: parent.verticalCenter
        Icon {
            anchors.centerIn: parent
            visible: !root.busy
            name: root.icon
            size: 16
            color: root.ink
        }
        Icon {
            anchors.centerIn: parent
            visible: root.busy
            name: "loader-circle"
            size: 16
            color: root.ink
            RotationAnimator on rotation { running: root.busy && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
        }
    }
    Text {
        id: label
        x: root.showsIcon ? lead.x + root.iconBox : Math.max(root.pad, (root.width - implicitWidth) / 2)
        width: Math.min(implicitWidth, root.width - x - root.pad)
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.ink
        wrapMode: root.wrap ? Text.WrapAnywhere : Text.NoWrap
        horizontalAlignment: Text.AlignHCenter
        lineHeight: root.wrap ? 1.25 : 1
        font.pixelSize: root.size === "sm" ? 13 : root.size === "lg" ? 15 : Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
}
