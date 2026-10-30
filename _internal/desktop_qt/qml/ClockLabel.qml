import QtQuick

// Chữ hiện một giá trị tự đổi (giờ đã nghe / còn lại, đếm ngược hẹn giờ, %, ETA, thời gian đã chạy). Luật chủ sách 30-10: giá trị
// đổi TẠI CHỖ - không Behavior, không trượt / cuộn / mờ chéo / co giãn; chữ số đều độ rộng (tnum có thật trong Be Vietnam Pro đóng kèm,
// mobile/android/scripts/add_tabular_digits.py, merge_fonts.py gọi). `reserve`: chữ mẫu rộng nhất giá trị có thể có (vd "00:00" hay ["00 phút", "00 giây"]) - bề rộng không nhỏ hơn
// nó, để giá trị đổi không đẩy phần bên cạnh. tools/check_ticks.py bắt chữ tự đổi không đi qua đây.
Text {
    id: root
    property var reserve: []
    font.features: {"tnum": 1}
    FontMetrics { id: metrics; font: root.font }
    readonly property real reservedWidth: {
        root.font
        return [].concat(reserve).reduce((widest, sample) => Math.max(widest, metrics.advanceWidth(sample)), 0)
    }
    width: Math.max(implicitWidth, reservedWidth)
}
