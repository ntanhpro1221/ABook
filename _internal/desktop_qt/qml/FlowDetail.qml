import QtQuick
import ABook

// Mảnh phụ "· chi tiết" đứng sau mảnh chính trong một Flow ("4 chương" · "12.345 chữ", "Máy chưa chắc" · "2 việc ..."). Hẹp tới mức
// Flow đẩy mảnh này xuống hàng mới thì nó đứng đầu hàng và bỏ dấu ngăn: "·" không bao giờ đứng đầu dòng (Lead soát 0.4.151, máy dò
// Separators). Bề rộng luôn tính theo bản CÓ dấu nên bỏ dấu không làm Flow xếp lại vòng vòng; câu dài vẫn gãy dòng trong bề rộng Flow.
Text {
    id: root
    property string detail: ""
    readonly property bool leadsRow: x < 1
    // Đo bản có dấu bằng một Text ẩn cùng phông (đủ font.features như số đều - TextMetrics bỏ qua và đo hụt, chữ cuối gãy xuống dòng)
    Text { id: dotted; visible: false; font: root.font; text: "· " + root.detail; textFormat: Text.PlainText }
    width: Math.min(Math.ceil(dotted.implicitWidth), parent ? parent.width : Math.ceil(dotted.implicitWidth))
    text: (leadsRow ? "" : "· ") + detail
    color: Theme.text2
    wrapMode: Text.Wrap
    font.pixelSize: Theme.sizeBodySmall
    textFormat: Text.PlainText
}
