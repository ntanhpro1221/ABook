import QtQuick
import QtTest
import ABook

// D3 trong cửa sổ thật (qml/Main.qml, WindowChrome giả): phím "?" mở hộp Phím tắt, "Phím tắt chữ" tắt thì "?" và M không làm gì, M tắt / bật
// tiếng, tuỳ chọn "Âm thanh chạm" và "Nền đọc" có hiệu lực ngay, sự kiện "abook-update" của host đọc lại /api/app, lời báo có nút nằm trên cùng.
TestCase {
    id: test
    name: "D3Main"
    when: windowShown
    property var win: null

    function all(item, name, out) {
        out = out || []
        if (item.objectName === name) out.push(item)
        for (const child of item.children || []) all(child, name, out)
        return out
    }
    function initTestCase() {
        DesktopApi.reset()
        Platform.reset()
        Api.bind(DesktopApi, Theme)
        Api.preferences = {theme: "system"}
        Api.loaded = true
        Api.notice = ""
        Theme.reduceMotion = false
        const component = Qt.createComponent(Qt.resolvedUrl("../../qml/Main.qml"))
        compare(component.status, Component.Ready, component.errorString())
        win = component.createObject(null)
        verify(win !== null)
        tryVerify(function() { return win.visible })
        win.requestActivate()
        tryVerify(function() { return win.active && win.activeFocusItem !== null })
        waitForRendering(win.contentItem)
    }
    function cleanupTestCase() {
        Nav.layers = []
        win.destroy()
        Nav.stack = null
        Theme.reduceMotion = false
        Theme.readingSurface = "auto"
        Feedback.sounds = true
        Api.preferences = {theme: "system"}
        if (Player.volume === 0) Player.toggleMute()
    }
    function dialog() { return all(win.contentItem, "shortcutsDialog")[0] }

    function test_1_questionMarkOpensShortcuts() {
        Api.preferences = {theme: "system"}
        keyClick("?", Qt.ShiftModifier, -1, win)
        tryVerify(function() { return dialog().open })
        keyClick(Qt.Key_Escape, Qt.NoModifier, -1, win)
        tryVerify(function() { return !dialog().open })
    }
    function test_2_letterShortcutsOff() {
        Player.open("width", 1, 0, true); Player.pause()
        Api.preferences = {theme: "system", letterShortcuts: false}
        keyClick("?", Qt.ShiftModifier, -1, win)
        keyClick(Qt.Key_M, Qt.NoModifier, -1, win)
        tryVerify(function() { return !dialog().open })
        tryCompare(Player, "volume", 0.9)
        Api.preferences = {theme: "system"}
        keyClick(Qt.Key_M, Qt.NoModifier, -1, win)
        compare(Player.volume, 0)
        keyClick(Qt.Key_M, Qt.NoModifier, -1, win)
        compare(Player.volume, 0.9)
    }
    function test_3_preferencesTakeEffectNow() {
        Api.preferences = {theme: "system", touchSounds: false, readingSurface: "ivory"}
        compare(Feedback.sounds, false)
        compare(Theme.readingSurface, "ivory")
        Api.preferences = {theme: "system", readingSurface: "khác"}
        compare(Feedback.sounds, true)
        compare(Theme.readingSurface, "auto")
    }
    function test_4_hostUpdateEventRereadsAppInfo() {
        DesktopApi.responses = {"/api/app": {status: 200, data: {version: "0.4.147", update: {version: "0.4.148", notes: ""}}}}
        Backend.hostEvent("abook-update", {version: "0.4.148"})
        compare(Api.info.update.version, "0.4.148")
        Backend.hostEvent("abook-update-failed", "Đường tải bản mới đứng yên quá lâu.")
        compare(Api.notice, "Chưa tải được bản mới\nĐường tải bản mới đứng yên quá lâu.")
        Api.notice = ""
    }
    function test_5_toastSitsTopRightAboveDialogs() {
        const toast = all(win.contentItem, "toast")[0]
        Api.toast("Đã lưu file sách", {action: {label: "Mở thư mục", run: function() {}}})
        tryVerify(function() { return toast.t === 1 })
        const p = toast.mapToItem(win.contentItem, 0, 0)
        compare(p.x + toast.width, win.width - 16)
        verify(p.y >= 40 + 16 - 0.5)
        verify(toast.z > dialog().z)
        Api.notice = ""
    }
    function test_6_minimizeStopsMotionAndRestoreShowsShell() {
        win.showMinimized()
        tryCompare(Nav, "uiVisible", false)
        compare(Theme.motionMedium, 0)
        compare(findChild(win, "mainShell").visible, false)
        win.showNormal()
        tryCompare(Nav, "uiVisible", true)
        verify(Theme.motionMedium > 0)
        compare(findChild(win, "mainShell").visible, true)
        win.hide()
        tryCompare(Nav, "uiVisible", false)
        compare(Theme.motionMedium, 0)
        win.show()
        tryCompare(Nav, "uiVisible", true)
    }
    // "Tới nội dung" (web Shell): Tab đầu tiên tới nút, nút trượt vào; bấm thì tiêu điểm vào màn đang xem, bỏ qua thanh bên.
    function test_7_skipToContent() {
        const skip = all(win.contentItem, "skipToContent")[0]
        const shell = all(win.contentItem, "mainShell")[0]
        shell.forceActiveFocus()
        compare(skip.opacity, 0)
        keyClick(Qt.Key_Tab, Qt.NoModifier, -1, win)
        verify(skip.activeFocus)
        tryCompare(skip, "opacity", 1)
        verify(skip.y >= 0)
        keyClick(Qt.Key_Return, Qt.NoModifier, -1, win)
        verify(!skip.activeFocus)
        let inside = false
        for (let up = win.activeFocusItem; up; up = up.parent) if (up.objectName === "screenStack") inside = true
        verify(inside, "tiêu điểm phải nằm trong màn đang xem: " + win.activeFocusItem)
        tryCompare(skip, "opacity", 0)
    }
}
