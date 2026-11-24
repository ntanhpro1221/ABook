import QtQuick
import QtTest
import ABook

// Khay trong cửa sổ thật (qml/Main.qml, TrayIcon giả của bộ thử): chủ sách 24-11 bấm "Thoát ABook" ở khay mà app vẫn nằm ở khay.
// Gốc: Main truyền `DesktopTray { windowMode: windowMode }` trong component lồng của Loader, vế phải là thuộc tính của chính
// DesktopTray nên khay nhận null và TrayMenuModel.dispatch bỏ qua MỌI mục (Mở, Thoát, Mini...). Mỗi ca dựng một Main mới, bấm
// mục menu như khay thật (tín hiệu triggered / activated của TrayIcon), và Thoát phải tới đúng lối thoát chắc chắn
// (Platform.exitApp = QCoreApplication::exit) ở mọi trạng thái cửa sổ: đang hiện, ẩn khay, thu nhỏ, mini, có hộp đang mở.
TestCase {
    id: test
    name: "TrayQuit"
    when: windowShown
    property var win: null

    function all(item, name, out) {
        out = out || []
        if (!item) return out
        if (item.objectName === name) out.push(item)
        for (const child of item.children || []) all(child, name, out)
        return out
    }
    function initTestCase() {
        DesktopApi.reset()
        Api.bind(DesktopApi, Theme)
        Api.preferences = {theme: "system"}
        Api.loaded = true
        Api.notice = ""
    }
    function init() {
        Platform.reset()
        Bench.hiddenDesktop = false          // Main dựng khay như máy thật
        Nav.layers = []
        const component = Qt.createComponent(Qt.resolvedUrl("../../qml/Main.qml"))
        compare(component.status, Component.Ready, component.errorString())
        win = component.createObject(null)
        verify(win !== null)
        tryVerify(function() { return win.visible })
        verify(win.tray !== null, "Main dựng khay khi không phải desktop ẩn")
        verify(win.tray.available)
    }
    function cleanup() {
        Nav.layers = []
        if (win) win.destroy()
        win = null
        Nav.stack = null
        Nav.windowMode = null
        Bench.hiddenDesktop = true
        if (Player.loaded) Player.pause()
    }
    function quitFromTray() {
        compare(Platform.exits, 0)
        win.tray.triggered("quit")
        compare(Platform.exits, 1, "Thoát ABook ở khay phải thoát app")
    }

    function test_quitWhileHiddenInTheTray() {
        win.close()                           // nút X: closeToTray mặc định bật, khay có -> ẩn vào khay
        tryVerify(function() { return !win.visible })
        compare(Platform.exits, 0, "đóng cửa sổ chỉ ẩn vào khay")
        quitFromTray()
        verify(Platform.store.window !== undefined, "thoát lưu vị trí cửa sổ trước")
    }
    function test_quitWhileShown() {
        quitFromTray()
    }
    function test_quitWhileMinimized() {
        win.showMinimized()
        quitFromTray()
    }
    function test_quitWithADialogOpen() {
        win.requestActivate()
        tryVerify(function() { return win.active })
        keyClick("?", Qt.ShiftModifier, -1, win)
        tryVerify(function() { return all(win.contentItem, "shortcutsDialog").some(item => item.visible) })
        quitFromTray()
    }
    function test_quitFromTheMiniWindowWhilePlaying() {
        Player.open("width", 1, 0, true)
        tryVerify(function() { return Player.loaded })
        win.tray.triggered("mini")
        tryVerify(function() { return Nav.windowMode.mini }, 5000, "Cửa sổ mini từ khay")
        quitFromTray()
    }
    function test_openAndClickRevealTheWindowFromTheTray() {
        win.close()
        tryVerify(function() { return !win.visible })
        win.tray.triggered("open")
        tryVerify(function() { return win.visible }, 5000, "Mở ABook ở khay hiện lại cửa sổ")
        win.close()
        tryVerify(function() { return !win.visible })
        win.tray.activated()
        tryVerify(function() { return win.visible }, 5000, "bấm icon khay hiện lại cửa sổ")
    }
    // Nút X khi tắt "đóng vào khay": cũng là thoát có chủ ý, cùng một lối.
    function test_closeWithoutTrayModeExits() {
        Nav.windowMode.closeToTray = false
        win.close()
        compare(Platform.exits, 1)
    }
}
