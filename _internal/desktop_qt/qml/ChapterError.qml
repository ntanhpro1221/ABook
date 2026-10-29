import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Khung nổi "Lỗi chương" (ChapterError của studio/ChapterError.tsx): bấm "Chi tiết" ở dòng lỗi của một chương thì hiện việc nên làm và nguyên văn lỗi kỹ thuật
// (cùng `friendlyError` với khối lỗi của cả cuốn). Hàng chương cao theo chữ nên lỗi mở ở khung nổi, không đẩy hàng dưới. Chữ dài xuống dòng, nguyên văn chọn chép được.
Popover {
    id: root
    objectName: "chapterError"
    property string raw: ""
    property bool studio: false
    readonly property var shown: Logic.friendlyError(raw, studio, false, false)
    panelWidth: 512
    maxHeight: 360
    Accessible.name: "Lỗi chương"
    function openFor(anchor, message, bundled) {
        raw = message
        studio = bundled
        anchorItem = anchor
        show()
    }
    Column {
        width: parent.width
        spacing: 8
        Text {
            objectName: "chapterErrorHint"
            width: parent.width
            text: root.shown.hint
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        TextEdit {
            objectName: "chapterErrorDetail"
            visible: root.shown.detail !== ""
            width: parent.width
            readOnly: true
            selectByMouse: true
            text: root.shown.detail
            color: Theme.text2
            wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
            font.family: "monospace"
            font.pixelSize: 11
        }
    }
}
