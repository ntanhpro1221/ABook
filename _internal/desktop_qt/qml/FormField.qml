import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Ô nhập chữ (input của bản web: cao 40, bo 8, viền điều khiển --control-line, tiêu điểm viền --focus, nền --bg, đệm 12, chữ 14). Chữ của
// người dùng không bao giờ bị cắt: tên dài xuống dòng, ô cao thêm. Enter = `accepted` (Shift+Enter xuống dòng khi `multiline`); Esc trong
// ô đang sửa phát `escaped` để chỗ dùng huỷ việc gõ (data-escape-local) thay vì đóng cả hộp. `invalid`: viền đỏ.
C.TextArea {
    id: root
    property string label: ""
    property bool multiline: false
    property bool invalid: false
    property color fill: Theme.bg
    signal accepted()
    signal escaped()
    Accessible.name: label
    color: Theme.text
    placeholderTextColor: Theme.text3
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentInk
    font.family: Theme.family
    font.pixelSize: Theme.sizeBodySmall
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    activeFocusOnTab: true
    topPadding: 10
    bottomPadding: 10
    leftPadding: 12
    rightPadding: 12
    implicitHeight: Math.max(40, contentHeight + topPadding + bottomPadding)
    opacity: enabled ? 1 : 0.5
    background: Rectangle {
        color: root.fill
        radius: Theme.radiusControl
        border.width: 1
        border.color: root.invalid ? Theme.danger : root.activeFocus ? Theme.focus : Theme.controlLine
        Behavior on border.color { ColorAnimation { duration: Theme.motionFast } }
    }
    Keys.onPressed: event => {
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(root.multiline && (event.modifiers & Qt.ShiftModifier))) {
            root.accepted(); event.accepted = true
        } else if (event.key === Qt.Key_Escape && root.escapeLocal) {
            root.escaped(); event.accepted = true
        }
    }
    property bool escapeLocal: false
    // Dán chữ nhiều dòng vào ô một dòng: gộp thành một dòng (input của web bỏ xuống dòng).
    onTextChanged: if (!multiline && /[\r\n]/.test(text)) { const at = cursorPosition; text = text.replace(/[\r\n]+/g, " "); cursorPosition = Math.min(at, text.length) }
}
