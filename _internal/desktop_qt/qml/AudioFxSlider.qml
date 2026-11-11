import "PlayerLabels.js" as Labels
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Núm âm thanh = bộ chọn giá trị hàng gọn (DESIGN mục 6; web AudioFxPanel FxSlider, Android AudioFxPage FxSlider): tên + giá trị (bấm để gõ),
// thước giữa -/+, chip tiêu biểu. Kéo là nghe ngay (`previewed` cũng phát `picked`).
// Thanh hai phía (Cao độ, ngưỡng dBFS): số đang chọn có dấu, dấu trừ thật.
ValuePicker {
    id: root
    property string suffix: " dB"
    dense: true
    format: function(v) { return (root.spec.min < 0 ? Labels.signed(v) : Logic.formatNumber(root.spec, v)) + root.suffix }
    chipLabel: function(v) { return Logic.formatNumber(root.spec, v) }
    onPreviewed: value => root.picked(value)
}
