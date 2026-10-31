import QtQuick
import ABook

// Mô hình chung cho khay native và bộ thử; tự nó không tạo icon hay cửa sổ hệ thống.
QtObject {
    id: root
    property var windowMode: null
    property var player: Player
    property bool loaded: player.loaded
    property bool playing: player.playing
    readonly property string tooltip: loaded ? player.bookTitle + " · " + player.chapterTitle : "ABook"
    readonly property var actions: [
        {action: "open", label: "Mở ABook", enabled: true},
        {separator: true},
        {action: "play", label: playing ? "Tạm dừng" : "Phát", enabled: loaded},
        {action: "back", label: `Lùi ${player.skipSeconds} giây`, enabled: loaded},
        {action: "forward", label: `Tới ${player.skipSeconds} giây`, enabled: loaded},
        {action: "previous", label: "Chương trước", enabled: loaded && player.canPrevious},
        {action: "next", label: "Chương sau", enabled: loaded && player.canNext},
        {separator: true},
        {action: "mini", label: "Cửa sổ mini", enabled: loaded},
        {separator: true},
        {action: "quit", label: "Thoát ABook", enabled: true}
    ]
    function activate() { if (windowMode) windowMode.reveal() }
    function dispatch(action) {
        if (!windowMode) return
        if (action === "open") windowMode.expand()
        else if (action === "quit") windowMode.quit()
        else if (!loaded) return
        else if (action === "mini") windowMode.enter()
        else if (action === "play") player.toggle()
        else if (action === "back") player.skip(-player.skipSeconds)
        else if (action === "forward") player.skip(player.skipSeconds)
        else if (action === "previous") player.previous()
        else if (action === "next") player.next()
    }
}
