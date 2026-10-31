import QtQuick
import ABook

// Kịch bản đo tự chạy khi ABOOK_BENCH được đặt (tools/measure.py).
//   "library" (mặc định): chờ thư viện về -> nghỉ (đo RAM nghỉ) -> cuộn lưới từ đầu tới cuối rồi ngược lại hai lượt -> nghỉ -> ghi file và thoát.
//     Mốc: idle_begin, scroll_begin, scroll_end, done.
//   "player": nạp một cuốn có tiếng ở trạng thái dừng (RAM nghỉ khi có sách) -> mở / đóng Đang nghe 5 lần (khung lúc biến hình) -> mở Đang nghe,
//     phát (tắt tiếng), chữ chạy theo giọng 10 s (khung + bộ đếm) -> đóng, thu nhỏ cửa sổ, vẫn phát 20 s (RAM + CPU; CPU ổn định tính từ giây 5) -> mở lại cửa sổ 1,5 s -> ghi file và thoát.
//     Mốc: idle_begin, idle_end, morph_begin/morph_end, unmorph_begin/unmorph_end, follow_begin/follow_end, min_begin/min_end, restore_begin/restore_end, count:<tag>:..., done.
//   "listen": nghe liền từ đầu cuốn ở tốc độ 1, không thao tác gì (tools/listen_audit.py). Mốc audio:tick mỗi giây, music:<bài> mỗi lần bài nhạc đổi;
//     hết cuốn (dừng hẳn 15 s sau khi đã phát) thì thoát.
Item {
    id: root
    width: 0
    height: 0
    property var stack: null
    property var win: null
    property var nowPlaying: null
    readonly property bool miniScenario: Bench.scenario === "mini"
    readonly property bool audioScenario: Bench.scenario === "audio"
    readonly property bool listenScenario: Bench.scenario === "listen"
    readonly property bool playerScenario: Bench.scenario === "player" || miniScenario || audioScenario || listenScenario
    readonly property bool focusProbe: Bench.scenario === "focus_probe"
    readonly property var list: {
        const s = stack && stack._stacks ? stack._stacks[0] : null
        return s && s.length && s[0].content ? s[0].content.list : null
    }
    readonly property real maxY: list ? list.originY + list.contentHeight - list.height + list.bottomMargin : 0
    readonly property real minY: list ? list.originY - list.topMargin : 0

    // ---- library ----
    // Thư viện về rồi chờ bìa giải mã xong trước khi đo nghỉ
    Timer {
        running: Bench.enabled && !root.playerScenario && !root.focusProbe && Backend.libraryLoaded
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
        if (miniScenario) { runMini(); return }
        if (audioScenario) { runAudio(); return }
        if (listenScenario) { runListen(); return }
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
        case 12: counters("min_begin"); Bench.note("min_begin"); win.showMinimized(); advance(20000); break
        case 13: Bench.note("min_end"); counters("min_end"); advance(300); break
        // Mở lại sau khi thu nhỏ (bộ nhớ đã trả về hệ điều hành lúc thu nhỏ phải nạp lại): khung đầu và khung chậm nhất trong 1,5 s.
        // Qt/Windows restore khi còn visible dùng SW_SHOWNORMAL, bỏ qua cả hai cờ no-activate.
        // Ẩn trước để showNormal đi qua đường show có kiểm cờ, không lấy focus của chủ máy.
        case 14: Bench.note("restore_begin"); win.hide(); win.showNormal(); advance(1500); break
        case 15: Bench.note("restore_end"); advance(300); break
        default: Player.pause(); Bench.note("done"); Bench.finish()
        }
    }

    // Đo cùng bộ phát Media Foundation thật nhưng cửa sổ offscreen; chương 4 dài hơn khoảng ẩn hai phút.
    function runMini() {
        switch (root.step++) {
        case 0: Player.jumpTo(4, 0); Player.resume(); advance(1500); break
        case 1: Bench.notePlayback("full"); Nav.windowMode.enter(); advance(1500); break
        case 2: Bench.notePlayback("mini"); Bench.note("mini_begin"); advance(10000); break
        case 3:
            Bench.note("mini_end"); Bench.notePlayback("hide_begin")
            Bench.note("hide_begin"); Nav.windowMode.hideToTray(); advance(120000); break
        case 4:
            Bench.note("hide_end"); Bench.notePlayback("hide_end")
            Nav.windowMode.reveal(); Nav.windowMode.expand(); advance(1500); break
        default: Bench.notePlayback("expanded"); Player.pause(); Bench.note("done"); Bench.finish()
        }
    }

    // Nghe liền như người nghe thật: phát từ đầu, rồi chỉ ghi lại. Cuốn hết là giọng dừng hẳn; 15 s không phát sau khi đã phát = xong.
    property int listenIdle: 0
    property int listenTickCount: 0
    property bool listenHeard: false
    Timer {
        id: listenTicks
        interval: 1000
        repeat: true
        onTriggered: {
            Bench.notePlayback("tick")
            if (++root.listenTickCount % 30 === 0) Bench.flush()
            // Player không có thuộc tính position cho QML (undefined > 0 là false: kịch bản không bao giờ thoát); vị trí ở Player.clock.
            root.listenHeard = root.listenHeard || Player.playing && Player.clock.position > 0
            root.listenIdle = Player.playing || !root.listenHeard ? 0 : root.listenIdle + 1
            if (root.listenIdle > 0) Bench.note("listen_idle:" + root.listenIdle + ":" + (root.listenHeard ? 1 : 0))
            if (root.listenIdle >= 15) { listenTicks.stop(); Bench.notePlayback("done"); Bench.note("done"); Bench.finish() }
        }
    }
    Connections {
        target: Music
        enabled: root.listenScenario
        // Tên sự kiện không được thoát JSON trong bench.cpp: chỉ ghi nhãn bài, bỏ ngoặc kép, gạch chéo ngược và dấu hai chấm.
        function onCreditChanged() { Bench.notePlayback("music:" + String(Music.credit && Music.credit.label || "").replace(/["\\:]/g, "")) }
    }
    function runListen() {
        Player.setRate(1.0)
        Bench.notePlayback("play")
        Player.resume()
        listenTicks.start()
    }

    // Tai kiểm tiếng (ABOOK_AUDIO_SINK, tools/audio_sink.py): mọi thao tác nghe trên một cuốn có nhạc, mỗi mốc ghi chương + vị trí.
    // Chương 1 của bản thử đổi nhạc ở giây 30 (mờ chéo), cuối chương tự sang chương 2.
    Timer { id: audioTicks; interval: 250; repeat: true; onTriggered: Bench.notePlayback("tick") }
    function audioMark(tag) { Bench.notePlayback(tag) }
    function runAudio() {
        switch (root.step++) {
        case 0: audioTicks.start(); audioMark("play"); Player.resume(); advance(6000); break
        case 1: audioMark("pause"); Player.pause(); advance(2000); break
        case 2: audioMark("resume"); Player.resume(); advance(4000); break
        case 3: audioMark("seek:22"); Player.seek(22); advance(12000); break
        case 4: audioMark("duck"); Music.setLevel(-32); advance(5000); break
        case 5: audioMark("unduck"); Music.setLevel(-20); advance(5000); break
        case 6: audioMark("rate:0.75"); Player.setRate(0.75); advance(8000); break
        case 7: audioMark("rate:1.25"); Player.setRate(1.25); advance(8000); break
        case 8: audioMark("rate:1.5"); Player.setRate(1.5); advance(8000); break
        case 9: audioMark("rate:2"); Player.setRate(2.0); advance(8000); break
        case 10: audioMark("rate:1"); Player.setRate(1.0); advance(6000); break
        case 11: audioMark("seek:150"); Player.seek(150); advance(4000); break
        case 12: audioMark("skip:-15"); Player.skip(-15); advance(4000); break
        // 30 s ở 3x (90 s nội dung): đủ dài để thấy tiếng nghe thấy trôi khỏi vị trí app báo
        case 13: audioMark("rate:3"); Player.setRate(3.0); advance(30000); break
        case 14: audioMark("rate:1"); Player.setRate(1.0); advance(3000); break
        case 15: audioMark("seek:end"); Player.seek(Player.clock.duration - 6); advance(12000); break
        case 16: audioMark("next"); Player.next(); advance(5000); break
        case 17: audioMark("stop"); Player.pause(); advance(1000); break
        default: audioTicks.stop(); audioMark("done"); Bench.note("done"); Bench.finish()
        }
    }

    // Thử riêng đường thu nhỏ/khôi phục trước khi đo dài; không cần tải sách hay phát tiếng.
    Timer {
        running: Bench.enabled && root.focusProbe
        interval: 200
        repeat: true
        property int step: 0
        onTriggered: {
            if (++step === 1) win.showMinimized()
            else if (step === 2) { win.hide(); win.showNormal() }
            else { stop(); Bench.note("done"); Bench.finish() }
        }
    }

    // Backend không lên: ghi lại những gì có rồi thoát, để script đo báo lỗi thay vì treo
    Timer { running: Bench.enabled; interval: root.miniScenario ? 170000 : root.audioScenario ? 200000 : root.listenScenario ? 3600000 : root.playerScenario ? 90000 : 40000; onTriggered: { Bench.note("timeout"); Bench.finish() } }
}
