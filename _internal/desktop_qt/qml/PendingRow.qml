import QtQuick
import ABook
import "ExportLogic.js" as Logic
import "CastLogic.js" as Cast

// Một dòng thay đổi chờ áp (hàng của PendingList trong studio/ApplyChanges.tsx): biểu tượng theo loại, lời nói rõ đổi gì (+ chương, + "từ <máy>"), số câu sẽ thu lại,
// nút "Nghe thử" nếu là đổi giọng, và nút bỏ mang đúng tên việc nó bỏ ("Bỏ cách đọc “Lucien”") để trình đọc màn hình phân biệt được các dòng.
// Hàng mới mở ra từ chiều cao 0, hàng đã bỏ khép lại rồi mới gỡ (DevicesRows). Chữ dài xuống dòng, không cắt.
Collapse {
    id: root
    objectName: "pendingRow"
    property var rows: null
    property string rowId: ""
    property string json: "{}"
    property bool present: true
    property bool fresh: false
    property bool first: true
    property string dropping: ""
    property bool showLines: true
    property var voiceTry: null
    readonly property var item: JSON.parse(json)
    readonly property string tag: Logic.pendingKey(item)
    readonly property string key: voiceTry && item.voice ? voiceTry.key(item.voice) : ""
    readonly property var heard: voiceTry ? voiceTry.tried[tag] : undefined
    readonly property bool playing: heard !== undefined && Clip.current === Cast.tryId(heard)
    readonly property var icons: ({pronunciation: "book-open-check", speaker: "user-round", line: "audio-lines", voice: "mic-vocal", retake: "refresh-cw"})
    property bool entered: !fresh
    signal dropRequested(var item)
    signal tryRequested(var item)

    open: present && entered
    Component.onCompleted: entered = true
    Timer {
        running: !root.present
        interval: (Theme.reduceMotion ? Theme.motionFast : Theme.motionMediumOut) + 80
        onTriggered: if (root.rows) root.rows.drop(root.rowId)
    }

    Item {
        id: line
        width: parent.width
        implicitHeight: (root.first ? 0 : 1) + Math.max(40, Math.max(label.height, actions.height) + 16)
        height: implicitHeight
        Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.first }
        Icon { x: 0; y: (root.first ? 0 : 1) + 8 + 2; name: root.icons[root.item.kind] || "refresh-cw"; size: 16; color: Theme.text3 }
        Text {
            id: label
            objectName: "pendingLabel"
            x: 28
            y: (root.first ? 0 : 1) + 8
            width: line.width - 28 - actions.width - 12
            text: root.item.label + (root.item.chapter ? " · " + root.item.chapter : "") + (root.item.from ? " · từ " + root.item.from : "")
            color: Theme.text
            textFormat: Text.PlainText
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
        }
        Row {
            id: actions
            anchors.right: parent.right
            y: (root.first ? 0 : 1) + (line.height - (root.first ? 0 : 1) - height) / 2
            spacing: 8
            Text {
                objectName: "pendingLines"
                visible: root.showLines
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, 120)
                text: Logic.pendingLines(root.item)
                color: Theme.text3
                horizontalAlignment: Text.AlignRight
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
            Button {
                objectName: "pendingTry"
                visible: root.voiceTry !== null && Boolean(root.item.voice)
                anchors.verticalCenter: parent.verticalCenter
                size: "sm"
                kind: "ghost"
                icon: root.playing ? "pause" : "book-open-text"
                text: root.playing ? "Dừng" : "Nghe thử"
                busy: root.voiceTry !== null && root.voiceTry.asking === root.key && root.key !== ""
                enabled: root.voiceTry !== null && (root.voiceTry.asking === "" || root.voiceTry.asking === root.key)
                Accessible.name: Cast.tryLabel(root.item.voiceLabel || "mới", root.playing)
                onActivated: root.tryRequested(root.item)
            }
            IconButton {
                objectName: "pendingDrop"
                anchors.verticalCenter: parent.verticalCenter
                width: 36
                height: 36
                icon: "x"
                iconSize: 16
                ink: Theme.text3
                hoverInk: Theme.text
                tip: Logic.dropLabel(root.item)
                Accessible.name: Logic.dropLabel(root.item)
                enabled: root.dropping === ""
                onClicked: root.dropRequested(root.item)
            }
        }
    }
}
