import QtQuick
import ABook

// Nút "Nghe thử" của một TryReading: biểu tượng loa khi nghỉ, tạm dừng khi đang phát ("Dừng"), vòng xoay lúc máy đang đọc thử.
Button {
    id: root
    property var reading: null
    kind: "ghost"
    size: "sm"
    text: reading && reading.playing ? "Dừng" : "Nghe thử"
    icon: reading && reading.playing ? "pause" : "volume-2"
    busy: !!reading && reading.pending
    enabled: !!reading && !reading.blocked && reading.spoken !== ""
    Accessible.name: reading && reading.playing ? "Dừng nghe thử" : "Nghe thử " + (reading ? reading.surface : "") + " đọc là " + (reading ? reading.spoken : "")
    onActivated: reading.press()
}
