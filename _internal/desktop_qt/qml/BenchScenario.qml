import QtQuick
import ABook

// Kịch bản đo tự chạy khi ABOOK_BENCH được đặt (tools/measure.py).
//   "library" (mặc định): chờ thư viện về -> nghỉ (đo RAM nghỉ) -> cuộn lưới từ đầu tới cuối rồi ngược lại hai lượt -> nghỉ -> ghi file và thoát.
//     Mốc: idle_begin, scroll_begin, scroll_end, done.
//   "player": nạp một cuốn có tiếng ở trạng thái dừng (RAM nghỉ khi có sách) -> mở / đóng Đang nghe 5 lần (khung lúc biến hình) -> mở Đang nghe,
//     phát (tắt tiếng), chữ chạy theo giọng 10 s (khung + bộ đếm) -> đóng, thu nhỏ cửa sổ, vẫn phát 10 s (RAM + CPU) -> mở lại cửa sổ 1,5 s -> ghi file và thoát.
//     Mốc: idle_begin, idle_end, morph_begin/morph_end, unmorph_begin/unmorph_end, follow_begin/follow_end, min_begin/min_end, restore_begin/restore_end, count:<tag>:..., done.
Item {
    id: root
    width: 0
    height: 0
    property var stack: null
    property var win: null
    property var nowPlaying: null
    readonly property bool playerScenario: Bench.scenario === "player"
    readonly property var list: {
        const s = stack && stack._stacks ? stack._stacks[0] : null
        return s && s.length && s[0].content ? s[0].content.list : null
    }
    readonly property real maxY: list ? list.originY + list.contentHeight - list.height + list.bottomMargin : 0
    readonly property real minY: list ? list.originY - list.topMargin : 0

    // ---- library ----
    // Thư viện về rồi chờ bìa giải mã xong trước khi đo nghỉ
    Timer {
        running: Bench.enabled && !root.playerScenario && Backend.libraryLoaded
        interval: 3000
        onTriggered: { Bench.note("idle_begin"); idle.start() }
    }
    Timer { id: idle; interval: 3000; onTriggered: { Bench.note("scroll_begin"); scroll.start() } }
    // 12 000 px trong 4 s = 3000 px/s: nhanh hơn một cú vuốt mạnh bằng bánh xe, để bắt cả lúc bìa dồn về
    SequentialAnimation {
        id: scroll
        NumberAnimation { target: root.list; property: "contentY"; from: root.minY; to: root.maxY; duration: 4000 }
        NumberAnimation { target: root.list; property: "contentY"; to: root.minY; duration: 4000 }
        NumberAnimation { target: root.list; property: "contentY"; to: root.maxY; duration: 4000 }
        onFinished: { Bench.note("scroll_end"); tail.start() }
    }
    Timer { id: tail; interval: 3000; onTriggered: { Bench.note("done"); Bench.finish() } }

    // ---- player ----
    property int step: 0
    property int morphRound: 0
    property bool beat: false
    // Nhịp tim: một điểm ảnh cùng màu nền nhúc nhích mỗi khung, để cảnh luôn vẽ lại ở tần số quét và khoảng cách giữa hai khung lộ ra mọi khung nặng
    // (không có nó, lúc phát chỉ có vài khung mỗi giây và p99 của khoảng cách khung vô nghĩa).
    Rectangle {
        visible: root.beat
        z: 1000
        width: 1
        height: 1
        y: 0
        color: Theme.bg
        NumberAnimation on x { running: root.beat; from: 2; to: 6; duration: 300; loops: Animation.Infinite }
    }
    Timer {
        id: starter
        running: Bench.enabled && root.playerScenario && Backend.libraryLoaded
        interval: 1000
        onTriggered: {
            win.width = 1920                // đo cùng khổ rộng trước / sau thay đổi bố cục
            win.height = 1080
            if (!Player.loaded && Bench.book) Player.open(Bench.book, -1, -1, false)
            waitLoaded.start()
        }
    }
    Timer {
        id: waitLoaded
        interval: 200
        repeat: true
        onTriggered: if (Player.loaded) { stop(); root.step = 0; root.advance(3000) }
    }
    Timer { id: stepper; onTriggered: root.run() }
    function advance(ms) { stepper.interval = ms; stepper.start() }
    function counters(tag) { Bench.noteCounters(tag, Player, ReadAlong) }
    function run() {
        if (Bench.enabled) console.log("bench step", root.step)
        switch (root.step++) {
        case 0: Bench.note("idle_begin"); advance(3500); break
        case 1: Bench.note("idle_end"); advance(200); break
        case 2: Bench.note("morph_begin"); win.openNowPlaying(); advance(900); break
        case 3: Bench.note("morph_end"); advance(300); break
        case 4: Bench.note("unmorph_begin"); nowPlaying.close(); advance(900); break
        case 5:
            Bench.note("unmorph_end")
            if (++morphRound < 5) { root.step = 2; advance(300) } else advance(200)
            break
        case 6: win.openNowPlaying(); advance(1200); break
        case 7: Player.resume(); advance(1500); break
        case 8: root.beat = true; advance(200); break
        case 9: counters("follow_begin"); Bench.note("follow_begin"); advance(10000); break
        case 10: Bench.note("follow_end"); counters("follow_end"); root.beat = false; advance(300); break
        case 11: nowPlaying.close(); advance(1500); break
        case 12: counters("min_begin"); Bench.note("min_begin"); win.showMinimized(); advance(10000); break
        case 13: Bench.note("min_end"); counters("min_end"); advance(300); break
        // Mở lại sau khi thu nhỏ (bộ nhớ đã trả về hệ điều hành lúc thu nhỏ phải nạp lại): khung đầu và khung chậm nhất trong 1,5 s.
        case 14: Bench.note("restore_begin"); win.showNormal(); win.raise(); win.requestActivate(); advance(1500); break
        case 15: Bench.note("restore_end"); advance(300); break
        default: Player.pause(); Bench.note("done"); Bench.finish()
        }
    }

    // Backend không lên: ghi lại những gì có rồi thoát, để script đo báo lỗi thay vì treo
    Timer { running: Bench.enabled; interval: root.playerScenario ? 90000 : 40000; onTriggered: { Bench.note("timeout"); Bench.finish() } }
}
