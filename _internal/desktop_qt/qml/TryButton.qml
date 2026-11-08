import "UiStrings.js" as S
import QtQuick
import ABook

// Nút "Nghe thử" của một TryReading: biểu tượng loa khi nghỉ, tạm dừng khi đang phát ("Dừng"), vòng xoay lúc máy đang đọc thử.
Button {
    id: root
    property var reading: null
    kind: "ghost"
    size: "sm"
    text: reading && reading.playing ? S.s_dung_11554138 : S.s_nghe_thu_fa024065
    icon: reading && reading.playing ? "pause" : "volume-2"
    busy: !!reading && reading.pending
    enabled: !!reading && !reading.blocked && reading.spoken !== ""
    Accessible.name: reading && reading.playing ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_thu_48ce1620 + (reading ? reading.surface : "") + S.s_doc_la_6f6aa509 + (reading ? reading.spoken : "")
    onActivated: reading.press()
}
