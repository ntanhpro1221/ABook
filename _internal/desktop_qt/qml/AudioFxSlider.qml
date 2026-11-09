import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6; web AudioFxPanel FxSlider, Android AudioFxPage FxSlider): tên + giá trị (bấm để gõ),
// thước giữa -/+, chip tiêu biểu. Kéo là nghe ngay (`previewed` cũng phát `picked`).
ValuePicker {
    id: root
    property string suffix: " dB"
    dense: true
    format: function(v) { return Logic.formatNumber(root.spec, v) + root.suffix }
    chipLabel: function(v) { return Logic.formatNumber(root.spec, v) }
    onPreviewed: value => root.picked(value)
}
