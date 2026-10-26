import QtQuick
import ABook

// Tốc độ nghe: lưới ô, ô đang chọn nhạt màu nhấn. Tốc độ nhớ riêng cho từng cuốn (như bản web).
Popover {
    id: root
    panelWidth: 296

    function label(value) { return String(value).replace(".", ",") + "×" }

    Column {
        width: parent.width
        spacing: Theme.s12
        Text {
            width: parent.width
            text: "Tốc độ nghe"
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            font.weight: Theme.weightMedium
        }
        Grid {
            columns: 4
            spacing: Theme.s8
            Repeater {
                model: Player.speeds
                ChoiceChip {
                    required property var modelData
                    width: (root.panelWidth - 2 * root.pad - 3 * Theme.s8) / 4
                    text: root.label(modelData)
                    selected: Math.abs(modelData - Player.rate) < 0.001
                    onClicked: Player.setRate(modelData)
                }
            }
        }
        Text {
            width: parent.width
            text: "Cuốn này nhớ tốc độ riêng của nó."
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
}
