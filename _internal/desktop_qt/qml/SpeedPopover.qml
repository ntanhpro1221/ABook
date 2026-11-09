import "UiStrings.js" as S
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Tốc độ đọc: bộ chọn giá trị. Tốc độ nhớ riêng cho từng cuốn (như bản web).
Popover {
    id: root
    panelWidth: 296

    function label(value) { return Logic.formatNumber(Logic.SPECS.speed, value) + "×" }

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
        // Bộ chọn giá trị (DESIGN mục 6, chủ sách 09-11): chip tiêu biểu một chạm + kéo / -,+ / gõ số ra mọi tốc độ 0,5-3× bước 0,05. Đổi là áp ngay.
        ValuePicker {
            objectName: "speedPicker"
            width: parent.width
            spec: Logic.SPECS.speed
            value: Player.rate
            label: S.s_toc_do_doc_3657e59d
            format: root.label
            onPicked: value => Player.setRate(value)
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
