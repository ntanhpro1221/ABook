import QtQuick
import ABook
import "RecordLogic.js" as Logic

// Danh sách của nút "Hồ sơ nghe:" (menu của RecordPicker, listen/BookScreen.tsx): một dòng giải thích, mỗi hồ sơ (dấu tích ở hồ sơ đang dùng, chỗ nghe cuối và
// lần nghe gần nhất), vạch ngăn, rồi "Hồ sơ mới", "Đổi tên hồ sơ này…", "Chuyển sang cuốn khác…", "Xoá hồ sơ này…". Việc chọn / làm do trang sách xử lý.
Column {
    id: root
    property var book: ({})
    property real now: 0                    // mili giây; 0 = giờ máy (để thử)
    signal activate(var record)
    signal action(var dialog)

    Text {
        width: parent.width
        topPadding: 4
        leftPadding: Theme.s8
        rightPadding: Theme.s8
        bottomPadding: 6
        text: Logic.PICKER_NOTE
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
    }
    Repeater {
        model: root.book.records || []
        Interactive {
            id: row
            required property var modelData
            objectName: "recordChoice"
            width: root.width
            implicitHeight: Math.max(Theme.buttonHeight, texts.height + 12)
            height: implicitHeight
            pressScaling: false
            Accessible.role: Accessible.MenuItem
            Accessible.name: modelData.name
            Accessible.checkable: true
            Accessible.checked: modelData.active
            readonly property bool selected: modelData.active
            onClicked: root.activate(modelData)
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusControl
                color: Theme.text
                opacity: row.pressed ? 0.10 : (row.hovered ? 0.06 : 0)
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            }
            Icon {
                x: Theme.s8
                y: 6 + 2
                name: "check"
                size: 16
                color: Theme.accentText
                opacity: row.selected ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            }
            Column {
                id: texts
                x: Theme.s8 + 16 + Theme.s12
                y: 6
                width: parent.width - x - Theme.s8
                Text {
                    objectName: "recordChoiceName"
                    width: parent.width
                    text: row.modelData.name
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                }
                ClockLabel {
                    objectName: "recordChoiceLine"
                    width: parent.width
                    text: Logic.recordLine(root.book, row.modelData, root.now > 0 ? root.now : undefined)
                    color: Theme.text3
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeCaption
                }
            }
        }
    }
    Item { width: 1; height: 9; Rectangle { y: 4; width: parent.width; height: 1; color: Theme.line } }
    Repeater {
        model: Logic.pickerActions(root.book)
        MenuRow {
            required property var modelData
            objectName: "recordAction." + modelData.key
            width: root.width
            icon: modelData.icon
            text: modelData.label
            danger: Boolean(modelData.danger)
            onClicked: root.action(modelData.dialog)
        }
    }
}
