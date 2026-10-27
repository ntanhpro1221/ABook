import QtQuick
import QtTest
import ABook

// D4 trong cửa sổ thật (qml/Main.qml, WindowChrome giả): Studio của máy đã ghép chỉ cho nghe -> "Về Thư viện" là Thư viện CỦA MÁY ẤY (thanh
// "…" vẫn ở trên, màn đẩy xuống dưới nó), "Về máy này" về Thư viện của máy này; trang sách -> "Đọc chương này" -> màn đọc, Esc lùi về trang sách.
TestCase {
    id: test
    name: "D4Main"
    when: windowShown
    property var win: null
    readonly property string peerId: "c0ffee000003"

    function all(item, name, out) {
        out = out || []
        if (item.objectName === name) out.push(item)
        for (const child of item.children || []) all(child, name, out)
        return out
    }
    function one(name) { const found = all(win.contentItem, name); verify(found.length > 0, "thiếu " + name); return found[0] }
    function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
    function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
    function initTestCase() {
        DesktopApi.reset()
        Platform.reset()
        Api.bind(DesktopApi, Theme)
        Api.preferences = {theme: "system"}
        Api.loaded = true
        Api.toasts = []
        Theme.reduceMotion = true
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
        Nav.studioPeer = ""
        win.visible = false
        win.destroy()
        wait(100)
        Nav.stack = null
        Theme.reduceMotion = false
    }

    function test_1_peerLibraryFromListenOnlyStudioAndHome() {
        reply("GET /api/peers/" + peerId + "/studio/api/app", {status: 200, data: {version: "0.4.147", listenOnly: true, peer: {id: peerId, name: "Máy bàn"}}})
        reply("GET /api/peers/" + peerId + "/studio/api/listen/library", {status: 200, data: [{id: "p1", title: "Truyện ở máy bàn", author: "Nam Cao"}]})
        Nav.openPeerStudio(peerId)
        compare(Nav.stack.current, 1)
        tryVerify(function() { return shown(one("studioClosed")) })
        const bar = one("peerBar")
        tryVerify(function() { return shown(bar) && bar.height > 0 })
        mouseClick(one("studioClosedLibrary"))
        compare(Nav.stack.current, 0)
        compare(Nav.studioPeer, peerId)                 // vẫn đang xem máy ấy
        tryVerify(function() { return all(win.contentItem, "libraryGridRow").some(r => shown(r)) })
        const library = all(win.contentItem, "libraryGridRow").filter(r => shown(r))[0]
        compare(library.children.filter(c => c.title !== undefined)[0].title, "Truyện ở máy bàn")
        verify(shown(bar))
        // màn nằm dưới thanh, không bị thanh che
        const stackTop = Nav.stack.mapToItem(win.contentItem, 0, 0).y
        const barBottom = bar.mapToItem(win.contentItem, 0, bar.height).y
        verify(stackTop >= barBottom - 0.5, stackTop + " >= " + barBottom)
        mouseClick(one("peerHome"))
        compare(Nav.studioPeer, "")
        compare(Nav.stack.current, 0)
        tryVerify(function() { return !shown(bar) })
        tryVerify(function() { return all(win.contentItem, "libraryGridRow").some(r => shown(r) && r.children.some(c => c.title === "Sách 1")) })
    }
    function test_2_readerFromChapterMenuAndBack() {
        const chapters = [1, 2].map(n => ({id: n, title: "Chương " + n, subtitle: "Tên " + n, state: null, available: true}))
        reply("GET /api/listen/books/width", {status: 200, data: {id: "width", title: "Sách width", chapters: chapters, records: [{id: "r1", active: true}], state: {}}})
        win.openBookId("width")
        tryCompare(Nav.stack, "depth", 2)
        tryVerify(function() { return all(win.contentItem, "bookChapterRow").filter(r => shown(r)).length > 1 })
        const row = all(win.contentItem, "bookChapterRow").filter(r => shown(r) && r.title === "Chương 1")[0]
        all(row, "chapterMore")[0].clicked()
        tryVerify(function() { return shown(one("chapterRead")) })
        mouseClick(one("chapterRead"))
        tryCompare(Nav.stack, "depth", 3)
        tryVerify(function() { return all(win.contentItem, "readerScreen").some(r => shown(r)) })
        tryCompare(all(win.contentItem, "readerText")[0].source, "status", "ready", 3000)
        compare(all(win.contentItem, "readerTitle")[0].text, "Tên 1")
        keyClick(Qt.Key_Escape, Qt.NoModifier, -1, win)
        tryCompare(Nav.stack, "depth", 2)
        tryVerify(function() { return all(win.contentItem, "readerScreen").length === 0 })
        compare(Nav.toastTop, 0)
    }
}
