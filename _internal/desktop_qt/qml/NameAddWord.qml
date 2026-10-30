import QtQuick
import ABook
import "NameLogic.js" as N

// "Thêm cách đọc" (AddAnyWord của NameReadings.tsx): tên nhân vật đã có dòng sẵn, còn chữ khác máy đọc sai ("TP.HCM", "Mr.", một chữ viết tắt) thì gõ vào đây - cách đọc ghi cho cả cuốn,
// đi đúng đường của cách đọc tên. Gõ xong thấy ngay chữ ấy có bao nhiêu câu và bao nhiêu câu đã thu phải thu lại. Nút mở ô; ô mở / đóng tại chỗ.
Column {
    id: root
    objectName: "nameAddWord"
    property var work: null
    property bool open: false
    property string word: ""
    readonly property string typed: word.trim()
    readonly property bool single: N.single(typed)
    property string heldWord: ""
    onTypedChanged: if (typed !== "" && N.single(typed)) heldWord = typed

    function openBox() { open = true; Later.call(root, function() { field.forceActiveFocus() }) }
    function closeBox() { word = ""; field.text = ""; open = false }

    Collapse {
        width: parent.width
        open: !root.open
        Item {
            width: parent.width
            height: 8 + add.height
            Button {
                id: add
                objectName: "addWordOpen"
                y: 8
                size: "sm"
                kind: "ghost"
                icon: "plus"
                text: "Thêm cách đọc"
                onClicked: root.openBox()
            }
        }
    }
    Collapse {
        width: parent.width
        open: root.open
        Column {
            width: Math.min(parent.width, 576)
            Item { width: 1; height: 12 }
            Item {
                width: parent.width
                height: Math.max(heading.height, close.height)
                Text { id: heading; anchors.verticalCenter: parent.verticalCenter; text: "Chữ đọc sai"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                IconButton {
                    id: close
                    objectName: "addWordClose"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    implicitWidth: 32
                    implicitHeight: 32
                    icon: "x"
                    iconSize: 16
                    ink: Theme.text3
                    hoverInk: Theme.text
                    tip: "Đóng"
                    Accessible.name: "Đóng"
                    onClicked: root.closeBox()
                }
            }
            Item { width: 1; height: 6 }
            FormField {
                id: field
                objectName: "addWordField"
                width: parent.width
                label: "Chữ đọc sai"
                placeholderText: "vd TP.HCM"
                escapeLocal: true
                topPadding: 8
                bottomPadding: 8
                implicitHeight: Math.max(36, contentHeight + 16)
                onTextChanged: root.word = text
                onEscaped: root.closeBox()
            }
            Text { width: parent.width; topPadding: 6; text: "Nhập một từ liền để đổi cách đọc cả cuốn, giữ chữ gốc."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
            Collapse {
                width: parent.width
                open: root.typed !== "" && !root.single
                Text { width: parent.width; topPadding: 6; text: "Gõ một chữ liền nhau, không có khoảng trắng."; color: Theme.warning; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
            }
            Collapse {
                width: parent.width
                open: root.single
                NameRow {
                    objectName: "addWordRow"
                    work: root.work
                    fresh: true
                    item: N.freshItem(root.heldWord)
                }
            }
        }
    }
}
