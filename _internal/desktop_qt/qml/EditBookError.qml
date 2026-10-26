import QtQuick
import ABook

// Lỗi ngay ở vùng bị ảnh hưởng (InlineError của shared/ui.tsx): tam giác cảnh báo + câu mực phụ + nút "Thử lại"; nội dung đã có vẫn dùng được.
// `open`: hiện / ẩn bằng Collapse (mở khép tại chỗ, không bật tắt). Nút đứng ngay sau câu; hẹp thì xuống dòng, thẳng mép với chữ (-ml-3).
Collapse {
    id: root
    property string message: ""
    property string lastMessage: ""      // câu cuối khi khép: chữ không biến mất trước khi khung khép xong
    signal retry()
    onMessageChanged: if (message !== "") lastMessage = message
    // Đo bề ngang một dòng của câu để nút "Thử lại" đứng ngay sau nó khi còn chỗ
    Text { id: natural; visible: false; text: root.lastMessage; font.pixelSize: Theme.sizeBodySmall; readonly property real width1: implicitWidth }
    Item {
        width: root.width
        height: flow.height + 24
        Icon { x: 0; y: 24; name: "triangle-alert"; size: 16; color: Theme.danger }
        Flow {
            id: flow
            x: 28
            y: 12
            width: parent.width - 28
            spacing: 4
            Item {
                width: Math.min(natural.implicitWidth, flow.width - 8) + 8
                height: words.height
                Text {
                    id: words
                    width: parent.width - 8
                    topPadding: 10
                    bottomPadding: 10
                    text: root.lastMessage
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                    Accessible.role: Accessible.AlertMessage
                }
            }
            Item {
                width: again.implicitWidth - 12
                height: again.height
                Button {
                    id: again
                    x: -12
                    text: "Thử lại"
                    icon: "rotate-cw"
                    kind: "ghost"
                    size: "sm"
                    onClicked: root.retry()
                }
            }
        }
    }
}
