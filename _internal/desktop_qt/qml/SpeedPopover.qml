import "UiStrings.js" as S
import QtQuick
import ABook

// Tốc độ đọc: lưới ô, ô đang chọn nhạt màu nhấn. Tốc độ nhớ riêng cho từng cuốn (như bản web).
Popover {
    id: root
    panelWidth: 296

    function label(value) { return String(value).replace(".", ",") + "×" }

    Column {
        width: parent.width
        spacing: Theme.s12
        Text {
            width: parent.width
            text: S.s_toc_do_doc_u00a0_u00a0nho_rieng_cho_cuon_n_de460f94
            wrapMode: Text.Wrap
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            font.weight: Theme.weightMedium
        }
        Flow {
            width: parent.width
            spacing: Theme.s8
            Repeater {
                model: Player.speeds
                ChoiceChip {
                    required property var modelData
                    text: root.label(modelData)
                    selected: Math.abs(modelData - Player.rate) < 0.001
                    onClicked: { Feedback.play("toggle"); Player.setRate(modelData) }
                }
            }
        }
        Text {
            objectName: "speedKeyHint"
            width: parent.width
            text: S.s_phim_va_de_giam_tang_b1dca426
            wrapMode: Text.Wrap
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
        }
    }
}
