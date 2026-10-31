import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Lỗi ngay ở vùng bị ảnh hưởng (InlineError của shared/ui.tsx) - MỌI lỗi tải của app dùng thành phần này: tam giác cảnh báo đỏ 16, câu 14
// mực phụ, nút ghost nhỏ "Thử lại" (icon xoay lại) đứng ngay sau câu; hẹp thì nút xuống dòng, chữ thẳng mép với câu (-ml-3 của web).
// Dòng đầu của câu đứng giữa chiều cao nút và icon đứng giữa dòng ấy, kể cả khi câu gãy dòng (máy dò IconText). Nội dung đã có vẫn dùng được.
// `open` mặc định theo `message`; mở / khép tại chỗ (Collapse), khép thì giữ câu cũ tới khi thu xong.
Collapse {
    id: root
    property string message: ""
    property string shownMessage: ""
    signal retry()
    onMessageChanged: if (message !== "") shownMessage = message
    Component.onCompleted: if (message !== "") shownMessage = message
    open: message !== ""

    readonly property real line: 20
    Item {
        width: root.width
        height: Math.max(row.height, again.implicitHeight) + 24
        Icon {
            objectName: "inlineErrorIcon"
            x: 0
            y: 12 + (again.implicitHeight - size) / 2
            name: "triangle-alert"
            size: 16
            color: Theme.danger
        }
        Flow {
            id: row
            x: 16 + 12
            y: 12
            width: parent.width - x
            spacing: 4
            Text {
                objectName: "inlineErrorText"
                width: Math.min(implicitWidth, row.width)
                topPadding: (again.implicitHeight - root.line) / 2
                bottomPadding: topPadding
                text: TextWrap.pretty(root.shownMessage)
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                lineHeight: root.line
                lineHeightMode: Text.FixedHeight
                textFormat: Text.PlainText
                Accessible.role: Accessible.AlertMessage
            }
            Item {
                width: again.implicitWidth - 12
                height: again.implicitHeight
                Button {
                    id: again
                    objectName: "inlineErrorRetry"
                    x: -12
                    text: "Thử lại"
                    icon: "rotate-cw"
                    kind: "ghost"
                    size: "sm"
                    enabled: root.open
                    onClicked: root.retry()
                }
            }
        }
    }
}
