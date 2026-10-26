import QtQuick
import ABook
import "PeerStudio.js" as Peer

// Thanh trên cùng khi đang mở Studio của máy tính đã ghép (desktop/PeerBar.tsx): máy nào, máy ấy có trả lời không, và đường về máy này. Nền tràn
// cả bề ngang (báo tin; máy im hay chỉ được nghe thì nền cảnh báo, màu nền đổi êm), nội dung thẳng lề trang bên dưới. Mở / khép theo chiều cao.
Collapse {
    id: root
    property string name: ""
    property string silent: ""
    property bool listenOnly: false
    property real contentX: Theme.margin
    property real contentWidth: width - 2 * Theme.margin
    signal home()
    Item {
        width: root.width
        height: Math.max(row.height, 32) + 16 + 1
        Rectangle {
            anchors.fill: parent
            color: root.silent !== "" || root.listenOnly ? Theme.warningSoft : Theme.infoSoft
            Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        Item {
            id: row
            x: root.contentX
            y: 8
            width: root.contentWidth
            height: Math.max(line.height, back.height)
            Icon { x: 0; y: (row.height - 16) / 2; name: "laptop"; size: 16; color: Theme.text2 }
            Text {
                id: line
                objectName: "peerLine"
                x: 28
                y: (row.height - height) / 2
                width: row.width - x - 12 - back.width
                text: Peer.peerBarLine(root.name, root.silent, root.listenOnly)
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Button {
                id: back
                objectName: "peerHome"
                x: row.width - width
                y: (row.height - height) / 2
                text: "Về máy này"
                kind: "ghost"
                size: "sm"
                onClicked: root.home()
            }
        }
    }
}
