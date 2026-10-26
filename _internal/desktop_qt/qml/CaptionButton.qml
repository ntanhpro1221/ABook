import QtQuick
import ABook

// Nút cửa sổ 46 x (cao dải): nền rê chuột / nhấn là cùng token với nút phụ (0,06 / 0,10 của màu chữ); riêng Đóng nền đỏ chuẩn Windows,
// chữ trắng, nhấn đậm hơn. Cửa sổ không còn là cửa sổ đang dùng thì nét chữ nhạt đi như mọi app Windows.
// Cho Windows biết vùng của nút (WindowChrome): rê vào nút phóng to thì Snap Layouts của Windows 11 hiện ra.
Item {
    id: root
    property bool danger: false
    property bool active: true
    property var chrome: null              // WindowChrome: để giữ nền rê chuột khi Windows mở Snap Layouts (Qt thôi nhận tin rê chuột lúc đó)
    property bool latched: false
    default property alias glyphs: holder.data
    readonly property bool hovered: hover.hovered || latched
    readonly property bool pressed: tap.pressed
    readonly property color ink: danger && (hovered || pressed) ? "#ffffff" : (active ? Theme.text : Theme.faint)
    signal clicked()

    implicitWidth: 46
    implicitHeight: Theme.buttonHeight

    Rectangle {
        anchors.fill: parent
        color: root.danger ? (root.pressed ? "#a82419" : "#c42b1c") : Theme.text
        opacity: root.danger ? (root.hovered || root.pressed ? 1 : 0) : (root.pressed ? 0.10 : (root.hovered ? 0.06 : 0))
        Behavior on color { ColorAnimation { duration: Theme.motionFastOut } }
        Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
    }
    Item {
        id: holder
        anchors.centerIn: parent
        width: 10
        height: 10
    }
    HoverHandler { id: hover }
    Connections {
        target: hover
        function onHoveredChanged() {
            if (hover.hovered) { root.latched = false; latchTimer.stop() }
            else if (root.chrome && root.chrome.cursorInside(root)) { root.latched = true; latchTimer.start() }
        }
    }
    Timer {
        id: latchTimer
        interval: 80
        repeat: true
        onTriggered: if (!root.chrome.cursorInside(root)) { root.latched = false; stop() }
    }
    TapHandler { id: tap; onTapped: root.clicked() }
}
