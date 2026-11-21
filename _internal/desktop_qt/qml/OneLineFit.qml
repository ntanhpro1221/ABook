import QtQuick
import ABook

// Tên một dòng không cắt chữ (DESIGN.md 5.5 "Tên một dòng"; điện thoại OneLineFit, web OneLineFit): vừa một dòng ở cỡ gốc thì giữ nguyên;
// không vừa thì thu cỡ tới Theme.oneLineMinScale cỡ gốc; thu tới đó vẫn không vừa thì trả cỡ gốc và xuống dòng. Không bao giờ "…".
// Người dùng đặt `room` (chỗ tối đa) và `baseSize`; bề ngang tự là min(chữ ở cỡ gốc, room) để nhãn đứng sau (giới tính...) bám sát tên.
// Đo bằng Text ẩn cùng phông (TextMetrics bỏ qua font.features và đo hụt - xem FlowDetail.qml).
Text {
    id: root
    property real room: parent ? parent.width : 0
    property int baseSize: Theme.sizeBody
    readonly property int minSize: Math.ceil(baseSize * Theme.oneLineMinScale)
    readonly property real naturalWidth: Math.ceil(probe.implicitWidth)
    // Cỡ thử đầu tiên theo tỉ lệ bề ngang; Text ẩn thứ hai xác nhận ở cỡ nguyên đó (chữ không co đúng tuyến tính theo cỡ).
    readonly property int candidate: room <= 0 || naturalWidth <= room ? baseSize : Math.floor(baseSize * room / naturalWidth)
    readonly property int fitted: Math.ceil(probeFit.implicitWidth) <= room ? candidate : candidate - 1
    // "one": vừa ở cỡ gốc · "shrunk": thu cỡ vừa một dòng · "wrap": xuống dòng ở cỡ gốc
    readonly property string fit: room <= 0 || naturalWidth <= room ? "one" : fitted >= minSize ? "shrunk" : "wrap"
    // Chiều cao dòng đầu: icon đứng trước tên canh giữa dòng này (máy dò icon-off-center), cả khi tên xuống dòng
    readonly property real firstLineHeight: lineCount > 1 ? height / lineCount : height
    // Ô lưới cần mọi ô cao bằng nhau: holdLineHeight giữ hộp dòng ở cỡ gốc khi chữ đã thu cỡ (chữ nhỏ canh giữa hộp ấy), để ô có dòng
    // phụ dài (tên máy) không thấp hơn ô bên cạnh (soát leftfix T4).
    property bool holdLineHeight: false
    readonly property real baseLineHeight: probe.implicitHeight

    Text { id: probe; visible: false; text: root.text; textFormat: root.textFormat; font.family: root.font.family; font.weight: root.font.weight; font.features: root.font.features; font.pixelSize: root.baseSize }
    Text { id: probeFit; visible: false; text: root.text; textFormat: root.textFormat; font.family: root.font.family; font.weight: root.font.weight; font.features: root.font.features; font.pixelSize: Math.max(1, root.candidate) }

    width: Math.max(0, Math.min(naturalWidth, room))
    font.pixelSize: fit === "shrunk" ? fitted : baseSize
    wrapMode: fit === "wrap" ? Text.Wrap : Text.NoWrap
    height: holdLineHeight && fit === "shrunk" ? Math.max(implicitHeight, baseLineHeight) : implicitHeight
    verticalAlignment: holdLineHeight ? Text.AlignVCenter : Text.AlignTop
    textFormat: Text.PlainText
}
