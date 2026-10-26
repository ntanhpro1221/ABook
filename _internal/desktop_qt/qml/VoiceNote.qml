import QtQuick
import ABook

// Một đoạn chữ ngắn của thẻ giọng (p text-[0.8125rem] text-fg-2 text-pretty): hiện khi `text` không rỗng, mở / khép theo chiều cao; giữ chữ cũ
// trong lúc khép. Không bao giờ cắt chữ.
VoiceBlock {
    id: root
    property string text: ""
    property color ink: Theme.text2
    property int px: 13
    property int weight: Theme.weightRegular
    property string shown: ""
    show: text !== ""
    onTextChanged: if (text !== "") shown = text
    Text {
        width: parent.width
        text: root.shown
        color: root.ink
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        font.pixelSize: root.px
        font.weight: root.weight
    }
}
