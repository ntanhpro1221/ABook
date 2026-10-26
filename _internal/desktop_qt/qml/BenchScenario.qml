import QtQuick
import ABook

// Kịch bản đo tự chạy khi ABOOK_BENCH được đặt (tools/measure.py): chờ thư viện về -> nghỉ (đo RAM nghỉ) -> cuộn lưới từ đầu tới cuối
// rồi ngược lại hai lượt -> nghỉ -> ghi file và thoát. Mỗi mốc đi vào Bench (idle_begin, scroll_begin, scroll_end, done).
Item {
    id: root
    visible: false
    property var stack: null
    readonly property var grid: {
        const s = stack && stack._stacks ? stack._stacks[0] : null
        return s && s.length && s[0].content ? s[0].content.grid : null
    }
    readonly property real maxY: grid ? grid.originY + grid.contentHeight - grid.height + grid.bottomMargin : 0
    readonly property real minY: grid ? grid.originY - grid.topMargin : 0

    // Thư viện về rồi chờ bìa giải mã xong trước khi đo nghỉ
    Timer {
        running: Bench.enabled && Backend.libraryLoaded
        interval: 3000
        onTriggered: { Bench.note("idle_begin"); idle.start() }
    }
    Timer { id: idle; interval: 3000; onTriggered: { Bench.note("scroll_begin"); scroll.start() } }
    // 12 000 px trong 4 s = 3000 px/s: nhanh hơn một cú vuốt mạnh bằng bánh xe, để bắt cả lúc bìa dồn về
    SequentialAnimation {
        id: scroll
        NumberAnimation { target: root.grid; property: "contentY"; from: root.minY; to: root.maxY; duration: 4000 }
        NumberAnimation { target: root.grid; property: "contentY"; to: root.minY; duration: 4000 }
        NumberAnimation { target: root.grid; property: "contentY"; to: root.maxY; duration: 4000 }
        onFinished: { Bench.note("scroll_end"); tail.start() }
    }
    Timer { id: tail; interval: 3000; onTriggered: { Bench.note("done"); Bench.finish() } }
    // Backend không lên: ghi lại những gì có rồi thoát, để script đo báo lỗi thay vì treo
    Timer { running: Bench.enabled; interval: 40000; onTriggered: { Bench.note("timeout"); Bench.finish() } }
}
