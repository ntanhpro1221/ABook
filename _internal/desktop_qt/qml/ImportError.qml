import QtQuick
import ABook

// Lỗi ngay vùng bị ảnh hưởng (InlineError của shared/ui.tsx): icon cảnh báo đỏ 16, câu báo 14 mực phụ, nút "Thử lại" (sm, chữ, icon xoay lại) đứng ngay sau câu,
// màn hẹp thì xuống dòng. Hiện / ẩn mở khép tại chỗ (Collapse), đổi câu khác khi đang hiện thì chữ đổi tại chỗ.
Collapse {
    id: root
    property string message: ""
    property string shownMessage: ""
    signal retry()
    onMessageChanged: if (message !== "") shownMessage = message      // khép lại thì giữ câu cũ tới khi thu xong
    open: message !== ""

    Item {
        width: root.width
        height: Math.max(row.height, 40) + 24
        Icon {
            x: 0
            y: 12 + (40 - 16) / 2
            name: "triangle-alert"
            size: 16
            color: Theme.danger
        }
        Flow {
            id: row
            x: 28
            y: 12
            width: parent.width - x
            spacing: 4
            Text {
                id: said
                width: Math.min(implicitWidth, row.width)
                topPadding: (40 - 20) / 2
                bottomPadding: (40 - 20) / 2
                text: root.shownMessage
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                lineHeight: 20
                lineHeightMode: Text.FixedHeight
                textFormat: Text.PlainText
            }
            // -ml-3 của bản web: đệm của nút chữ không đẩy chữ "Thử lại" lệch khỏi lề của câu báo khi nó xuống dòng
            Item {
                width: again.implicitWidth - 12
                height: again.implicitHeight
                Button {
                    id: again
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
