import QtQuick
import ABook

// Bảng nổi nhỏ cạnh chip trạng thái: chi tiết bộ máy (cổng, thời gian mở, bản) + "Khởi động lại" / "Mở nhật ký".
// Là một lớp của ngăn xếp Back: Esc, Alt+Left, nút Back của chuột hay bấm ra ngoài đều đóng; Back không lùi màn khi lớp còn mở.
Item {
    id: root
    anchors.fill: parent
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
        height: content.implicitHeight + 2 * Theme.s16
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

        Column {
            id: content
            x: Theme.s16
            y: Theme.s16
            width: parent.width - 2 * Theme.s16
            spacing: Theme.s12

            Row {
                spacing: Theme.s8
                Rectangle {
                    width: 8; height: 8; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: Backend.state === Backend.Failed ? Theme.danger : (Backend.state === Backend.Starting ? Theme.accent : Theme.success)
                }
                Text {
                    text: Backend.state === Backend.Failed ? "Gặp lỗi" : (Backend.state === Backend.Starting ? "Đang mở…" : "Sẵn sàng")
                    color: Theme.text
                    font.pixelSize: Theme.sizeBody
                    font.weight: Theme.weightMedium
                }
            }
            Text {
                visible: Backend.state === Backend.Failed
                width: parent.width
                text: Backend.message
                color: Theme.danger
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Column {
                visible: Backend.state === Backend.Ready
                spacing: 2
                Text { text: "Mọi thứ đang chạy trên máy này."; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                Text { text: "Bản " + Backend.version; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            }
            Row {
                spacing: Theme.s4
                x: -Theme.s12      // nút chữ đầu hàng: mực thẳng mép cột chữ
                Button { kind: "text"; text: "Khởi động lại"; onClicked: { root.close(); Backend.restart() } }
                Button { kind: "text"; text: "Mở nhật ký"; onClicked: { root.close(); Platform.revealFile(Backend.logPath) } }
            }
        }
    }
}
