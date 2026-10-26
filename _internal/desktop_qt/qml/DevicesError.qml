import QtQuick
import ABook

// Lỗi ngay tại vùng bị ảnh hưởng (InlineError của shared/ui.tsx): icon cảnh báo đỏ, câu mực phụ, nút "Thử lại" đứng ngay sau câu.
// Mở / khép tại chỗ bằng Collapse.
Collapse {
    id: root
    property string message: ""
    signal retry()
    Item {
        width: parent.width
        implicitHeight: flow.height + 24
        height: implicitHeight
        Icon { x: 0; y: 12 + 12; name: "triangle-alert"; size: 16; color: Theme.danger }
        Flow {
            id: flow
            x: 28
            y: 12
            width: parent.width - 28
            spacing: 4
            Item {
                width: Math.min(sentence.implicitWidth, flow.width)
                height: sentence.height + 19
                Text {
                    id: sentence
                    y: 9.5
                    width: Math.min(implicitWidth, flow.width)
                    text: root.message
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
            Item {
                width: again.width - 12
                height: again.height
                Button { id: again; x: -12; kind: "ghost"; size: "sm"; icon: "rotate-cw"; text: "Thử lại"; onClicked: root.retry() }
            }
        }
    }
}
