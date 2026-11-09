import "UiStrings.js" as S
import QtQuick
import ABook

// Mô hình chung cho khay native và bộ thử; tự nó không tạo icon hay cửa sổ hệ thống.
QtObject {
    id: root
    property var windowMode: null
    property var player: Player
    property bool loaded: player.loaded
    property bool playing: player.playing
    readonly property string tooltip: loaded ? player.bookTitle + "\u00a0·\u00a0" + player.chapterTitle : S.s_abook_1c37d334
    readonly property var actions: [
        {action: "open", label: S.s_mo_abook_feeae114, enabled: true},
        {separator: true},
        {action: "play", label: playing ? S.s_tam_dung_67635815 : S.s_phat_343e7e48, enabled: loaded},
        {action: "back", label: S.s_lui_0_giay_718bdd89(player.skipSeconds), enabled: loaded},
        {action: "forward", label: S.s_toi_0_giay_84234225(player.skipSeconds), enabled: loaded},
        {action: "previous", label: S.s_chuong_truoc_4750f9e9, enabled: loaded && player.canPrevious},
        {action: "next", label: S.s_chuong_sau_17d1bd20, enabled: loaded && player.canNext},
        {separator: true},
        {action: "mini", label: S.s_cua_so_mini_65edeb9b, enabled: loaded},
        {separator: true},
        {action: "quit", label: S.s_thoat_abook_523599d6, enabled: true}
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
