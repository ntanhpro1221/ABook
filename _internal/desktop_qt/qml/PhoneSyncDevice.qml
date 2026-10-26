import QtQuick
import ABook
import "DevicesLogic.js" as Logic

// Một thiết bị đã ghép trong "Máy đã ghép" (hàng <li> của desktop/PhoneSync.tsx): khối gập (tên + "Lần cuối ..."), thân có icon điện thoại,
// tên + "Kết nối lần cuối ... · ghép ngày ...", công tắc "Điều khiển sản xuất" (khi Studio từ xa bật), "Đổi tên", "Thôi ghép". Hàng mới
// mở ra từ chiều cao 0, hàng đã thôi ghép khép lại rồi mới gỡ khỏi danh sách (DevicesRows). Tên máy dài xuống dòng, không cắt.
Collapse {
    id: root
    property var rows: null
    property string rowId: ""
    property string json: "{}"
    property bool present: true
    property bool fresh: false
    property bool first: true
    property bool remoteStudio: false
    property bool studioBusy: false
    property real clock: Date.now() / 1000
    readonly property var device: JSON.parse(json)
    property bool entered: !fresh
    signal rename(string id, string name)
    signal remove(string id, string name)
    signal studioToggled(string id, bool enabled)

    open: present && entered
    width: parent ? parent.width : 0
    Component.onCompleted: entered = true
    Timer {
        running: !root.present
        interval: (Theme.reduceMotion ? Theme.motionFast : Theme.motionMediumOut) + 80
        onTriggered: if (root.rows) root.rows.drop(root.rowId)
    }

    Item {
        width: parent.width
        implicitHeight: (root.first ? 0 : 1) + fold.height
        height: implicitHeight
        Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.first }
        DevicesFold {
            id: fold
            y: root.first ? 0 : 1
            width: parent.width
            storageKey: "phone-sync.device." + root.rowId
            title: root.device.name || ""
            summary: "Lần cuối " + Logic.formatRelative(root.device.lastSeen, root.clock)
            Item {
                id: body
                width: parent.width
                readonly property real restWidth: rest.width
                readonly property bool inline: 20 + 12 + 176 + 12 + restWidth <= width
                readonly property real lineHeight: Math.max(40, infoColumn.height)
                height: inline ? lineHeight : lineHeight + 12 + rest.height
                Icon { x: 0; y: body.lineHeight / 2 - 10; name: "smartphone"; size: 20; color: Theme.text3 }
                Column {
                    id: infoColumn
                    x: 32
                    y: (body.lineHeight - height) / 2
                    width: body.inline ? body.width - 32 - 12 - body.restWidth : body.width - 32
                    Text { width: parent.width; text: root.device.name || ""; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                    Text {
                        width: parent.width
                        text: "Kết nối lần cuối " + Logic.formatRelative(root.device.lastSeen, root.clock) + " · ghép ngày " + Logic.formatDate(root.device.pairedAt)
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                }
                Row {
                    id: rest
                    spacing: 12
                    x: body.inline ? body.width - width : 0
                    y: body.inline ? (body.lineHeight - height) / 2 : body.lineHeight + 12
                    Row {
                        visible: root.remoteStudio
                        spacing: 8
                        height: 40
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Điều khiển sản xuất"
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                            TapHandler { enabled: !root.studioBusy; onTapped: root.studioToggled(root.rowId, !root.device.studio) }
                        }
                        Switch {
                            anchors.verticalCenter: parent.verticalCenter
                            label: "Điều khiển sản xuất từ " + (root.device.name || "")
                            checked: Boolean(root.device.studio)
                            enabled: !root.studioBusy
                            onToggled: value => root.studioToggled(root.rowId, value)
                        }
                    }
                    Button { size: "sm"; kind: "ghost"; text: "Đổi tên"; onClicked: root.rename(root.rowId, root.device.name || "") }
                    Button { size: "sm"; kind: "ghost"; text: "Thôi ghép"; onClicked: root.remove(root.rowId, root.device.name || "") }
                }
            }
        }
    }
}
