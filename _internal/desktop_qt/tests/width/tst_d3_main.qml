import QtQuick
import QtTest
import ABook

// D3 trong cửa sổ thật (qml/Main.qml, WindowChrome giả): phím "?" mở hộp Phím tắt, "Phím tắt chữ" tắt thì "?" và M không làm gì, M tắt / bật
// tiếng, tuỳ chọn "Âm thanh chạm" và "Nền đọc" có hiệu lực ngay, sự kiện "abook-update" của host đọc lại /api/app, lời báo nằm dưới mặt hộp.
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

    function test_0_bookActionsAreNotConstructedAtStartup() {
        for (const name of ["editBookLoader", "renameChapterLoader", "castDialogsLoader", "recordDialogsLoader", "saveBookAsLoader"]) {
            const loader = findChild(win.contentItem, name)
            verify(loader !== null, name)
            compare(loader.active, false)
            compare(loader.item, null)
        }
    }

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
    function test_5_toastSitsTopRightBelowDialogs() {
        const stack = all(win.contentItem, "toastStack")[0]
        const toast = all(stack, "successToast")[0]
        Api.toast("Đã lưu file sách", {action: {label: "Mở thư mục", run: function() {}}})
        tryVerify(function() { return toast.t === 1 })
        const p = toast.mapToItem(win.contentItem, 0, 0)
        fuzzyCompare(p.x + toast.width, win.width - 16, 0.5)
        verify(p.y >= 40 + 16 - 0.5)
        verify(stack.z < dialog().z)
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

    function test_8_bookActionsLoadSynchronouslyAndRetainTheirDialogs() {
        const book = {id: "lazy", title: "Book", stage: "audio", chapters: [], capabilities: {}}
        const edit = findChild(win.contentItem, "editBookLoader")
        edit.begin(book)
        const first = edit.item
        verify(first.open)
        compare(first.parent, win.contentItem)
        first.dismiss()
        edit.begin({id: "second", title: "Second book", stage: "audio", capabilities: {}})
        compare(edit.item, first)
        compare(first.book.id, "second")
        first.dismiss()

        const rename = findChild(win.contentItem, "renameChapterLoader")
        rename.begin(book, {id: 1, title: "Chapter", subtitle: "Title"})
        verify(rename.item.open)
        compare(rename.item.chapter.id, 1)
        rename.item.dismiss()

        const cast = findChild(win.contentItem, "castDialogsLoader")
        cast.begin("rename", {bookId: "lazy", person: {name: "A", displayName: "A"}})
        const castRename = findChild(win.contentItem, "castRenameDialog")
        verify(castRename.open)
        castRename.dismiss()

        const record = findChild(win.contentItem, "recordDialogsLoader")
        record.begin("rename", {bookId: "lazy", book: {}, dialog: {kind: "rename", name: "Profile"}})
        verify(record.item.open)
        record.item.dismiss()

        const save = findChild(win.contentItem, "saveBookAsLoader")
        save.begin(book)
        verify(save.item.open)
        save.item.dismiss()
        DesktopApi.responses["POST /api/books/lazy/save"] = {status: 200, data: {edits: 1}}
        save.quick(book)
        compare(save.item.book.id, "lazy")
        verify(DesktopApi.requests.some(r => r.method === "POST" && r.path === "/api/books/lazy/save"))
        Api.notice = ""
    }

    function test_9_voicesAreDeferredUntilTextOrSettingsNeedThem() {
        DesktopApi.reset()
        Api.voiceList = []; Api.voicesLoaded = false; Api.voicesLoading = false
        const bridge = Api.transport
        Api.transport = null
        Api.ensureVoiceName()
        compare(Api.voicesLoading, false)
        Api.transport = bridge
        Api.load()
        Backend.libraryFetched([{id: "audio", stage: "audio"}])
        verify(!DesktopApi.requests.some(r => r.path === "/api/readaloud/voices"))

        const voice = {id: "device:An", name: "An", provider: "device", online: false}
        DesktopApi.responses["GET /api/readaloud/voices"] = {status: 200, data: [voice]}
        Api.defaultVoice = voice.id
        DesktopApi.delayed = true
        Backend.libraryFetched([{id: "text", stage: "text"}])
        Backend.libraryFetched([{id: "text", stage: "text"}])
        compare(DesktopApi.requests.filter(r => r.path === "/api/readaloud/voices").length, 1)
        DesktopApi.finish(); DesktopApi.delayed = false
        compare(Api.voiceName, "An")
        compare(Api.defaultVoice, voice.id)
        verify(Api.voicesLoaded)
        Backend.libraryFetched([{id: "text", stage: "text"}])
        compare(DesktopApi.requests.filter(r => r.path === "/api/readaloud/voices").length, 1)

        Api.voiceList = []; Api.voicesLoaded = false
        DesktopApi.responses["GET /api/listen/books/text"] = {status: 200, data: {id: "text", stage: "text", chapters: [], capabilities: {}}}
        const bookComponent = Qt.createComponent(Qt.resolvedUrl("../../qml/BookPage.qml"))
        compare(bookComponent.status, Component.Ready, bookComponent.errorString())
        const page = bookComponent.createObject(win.contentItem, {book: {bookId: "text"}, width: 560, height: 800})
        verify(page !== null)
        compare(Api.voiceName, "An")
        compare(DesktopApi.requests.filter(r => r.path === "/api/readaloud/voices").length, 2)
        page.destroy()

        Api.voiceList = []; Api.voicesLoaded = false
        const component = Qt.createComponent(Qt.resolvedUrl("../../qml/SettingsScreen.qml"))
        compare(component.status, Component.Ready, component.errorString())
        const settings = component.createObject(win.contentItem, {width: 560, height: 800})
        verify(settings !== null)
        compare(Api.voiceName, "An")
        settings.destroy()
        Api.voiceList = []; Api.voicesLoaded = false
        const beforeMixed = DesktopApi.requests.filter(r => r.path === "/api/readaloud/voices").length
        Backend.libraryFetched([{id: "mixed", stage: null, chaptersAvailable: 1, chaptersTotal: 2}])
        compare(DesktopApi.requests.filter(r => r.path === "/api/readaloud/voices").length, beforeMixed + 1)
        compare(Api.voiceName, "An")
        verify(Api.needsVoiceList({stage: null, chapters: [{state: "text"}]}))
        verify(!Api.needsVoiceList({stage: null, chaptersAvailable: 2, chaptersTotal: 2}))
        Api.defaultVoice = ""; Api.voiceList = []; Api.voicesLoaded = false
    }
}
