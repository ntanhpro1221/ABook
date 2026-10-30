import QtQuick
import ABook

// Bảng nổi nhỏ trên chip trạng thái: chi tiết (bản, lời nhắn khi lỗi) + hai hành động "Khởi động lại" / "Mở thư mục nhật ký".
// Là một lớp của ngăn xếp Back: Esc, Alt+Left, nút Back của chuột hay bấm ra ngoài đều đóng; Back không lùi màn khi lớp còn mở.
WindowLayer {
    id: root
    property bool open: false
    property Item anchorItem: null
    property real shown: open ? 1 : 0
    visible: shown > 0
    z: 50

    Behavior on shown {
        NumberAnimation {
            duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : (root.open ? Theme.motionFast : Theme.motionFastOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }

    function show() { open = true; Nav.openLayer(root) }
    function close() { open = false; Nav.closedLayer(root) }

    // Bấm ra ngoài thì đóng
    MouseArea {
        anchors.fill: parent
        enabled: root.open
        onPressed: root.close()
    }

    Item {
        id: panel
        width: 300
        height: content.implicitHeight + Theme.s12 + Theme.s8
        x: root.anchorItem ? root.anchorItem.mapToItem(root, 0, 0).x : 0
        y: (root.anchorItem ? root.anchorItem.mapToItem(root, 0, 0).y : 0) - height - Theme.s8 + (1 - root.shown) * 8
        opacity: root.shown
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.shown
        transformOrigin: Item.BottomLeft

        // Bóng nhẹ cho lớp nổi (DESIGN.md 5.5: bóng chỉ cho lớp nổi)
        Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
        Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: Theme.panel
            border.width: Theme.dark ? 1 : 0
            border.color: Theme.line
        }
        MouseArea { anchors.fill: parent }   // bấm trong bảng không đóng

        // Chip bên dưới đã nói trạng thái ("Sẵn sàng"...), bảng chỉ thêm phần chi tiết và hai việc có thể làm.
        Column {
            id: content
            x: Theme.s16
            y: Theme.s12
            width: parent.width - 2 * Theme.s16
            spacing: Theme.s4

            Text {
                width: parent.width
                topPadding: Theme.s4
                text: Backend.state === Backend.Failed ? Backend.message
                    : (Backend.state === Backend.Starting ? "ABook đang chuẩn bị, bạn chờ một chút." : "Mọi thứ đang chạy trên máy này.")
                color: Backend.state === Backend.Failed ? Theme.danger : Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Text {
                topPadding: 0
                bottomPadding: Theme.s8
                text: "Bản " + Backend.version
                color: Theme.text3
                font.pixelSize: Theme.sizeCaption
            }
            Item {
                width: parent.width + 2 * Theme.s8
                x: -Theme.s8
                height: restart.height + log.height
                MenuRow {
                    id: restart
                    width: parent.width
                    icon: "refresh-cw"
                    text: "Khởi động lại"
                    onClicked: { root.close(); Backend.restart() }
                }
                MenuRow {
                    id: log
                    y: restart.height
                    width: parent.width
                    icon: "folder-open"
                    text: "Mở thư mục nhật ký"
                    onClicked: { root.close(); Platform.revealFile(Backend.logPath) }
                }
            }
        }
    }
}
