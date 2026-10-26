import QtQuick
import ABook

// Phím tắt của cửa sổ (bộ bắt phím của listen/player.tsx + ShortcutsHost của listen/Shortcuts.tsx): Space phát / tạm dừng, ← → lùi / tới 15 giây,
// Shift + ← → chương trước / sau, M tắt / bật tiếng, [ ] giảm / tăng tốc độ đọc, ? mở hộp Phím tắt. Phím MỘT chữ cái (M, [ ], ?) tắt được ở
// Cài đặt › Giao diện › "Phím tắt chữ" (`letters`; WCAG 2.1.4) - Space, mũi tên, Esc vẫn chạy. Phím có Ctrl / Alt / Win không thuộc nhóm này.
// `handle(event)` trả true khi đã dùng phím (Main.qml đặt event.accepted).
QtObject {
    id: root
    property bool letters: true
    signal shortcutsRequested()

    function handle(event) {
        if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) return false
        const text = event.text || ""
        if (text.length === 1 && text !== " " && !letters) return false
        if (text === "?") { shortcutsRequested(); return true }        // hộp Phím tắt mở được cả khi chưa có sách
        if (!Player.loaded) return false
        if (event.key === Qt.Key_Space) {
            if (event.isAutoRepeat) return false
            Player.toggle()
            return true
        }
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
            const forward = event.key === Qt.Key_Right
            if (event.modifiers & Qt.ShiftModifier) { if (forward) Player.next(); else Player.previous() }
            else Player.skip(forward ? 15 : -15)
            return true
        }
        if (text === "m" || text === "M") { Player.toggleMute(); return true }
        if (text === "[" || text === "]") { Player.stepRate(text === "]" ? 1 : -1); return true }
        return false
    }
}
