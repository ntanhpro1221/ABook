import QtQuick
import QtTest
import ABook
import "../../qml" as Screens

Item {
    id: host
    width: 1280; height: 900
    Component { id: now; Screens.NowPlaying {} }
    Component { id: book; Screens.BookPage {} }
    Component { id: settings; Screens.SettingsScreen {} }
    Component { id: modal; Screens.Modal {} }
    TestCase {
        name: "Landscape"
        when: windowShown
        function geometry(item, path) {
            path = (path || "") + "/" + (item.objectName || item.toString().split("(")[0])
            const detail = path + " text=" + (item.text || "") + " size=" + item.width + "x" + item.height
            verify(isFinite(item.width) && item.width >= 0, "negative or invalid width: " + detail)
            verify(isFinite(item.height) && item.height >= 0, "negative or invalid height: " + detail)
            for (const child of item.children || []) geometry(child, path)
        }
        function test_windows_data() {
            return [
                {tag: "portrait", w: 360, h: 780, panes: false},
                {tag: "phone", w: 800, h: 360, panes: true},
                {tag: "small-phone", w: 640, h: 320, panes: true},
                {tag: "split", w: 600, h: 240, panes: true},
                {tag: "tiny", w: 240, h: 200, panes: false},
                {tag: "tablet", w: 840, h: 900, panes: true}
            ]
        }
        function test_windows(data) {
            Theme.reduceMotion = true
            host.Window.window.width = data.w
            host.Window.window.height = data.h
            const player = createTemporaryObject(now, host, {width: data.w, height: data.h})
            verify(player !== null)
            compare(player.wide, data.w >= 1200 || data.h < 480 && data.w >= 600)
            verify(player.colW >= 0)
            verify(player.textW >= 0)
            geometry(player)
            const page = createTemporaryObject(book, host, {width: data.w, height: data.h})
            verify(page !== null)
            compare(page.expanded, data.panes)
            verify(page.compositionWidth >= 0)
            geometry(page)
            const prefs = createTemporaryObject(settings, host, {width: data.w, height: data.h})
            verify(prefs !== null)
            compare(prefs.expanded, data.panes)
            geometry(prefs)
            const dialog = createTemporaryObject(modal, host, {width: data.w, height: data.h, title: "Kiểm tra cửa sổ"})
            verify(dialog !== null)
            const panel = findChild(dialog, "modalPanel")
            verify(panel.width >= 0 && panel.height >= 0)
            geometry(panel)
        }
    }
}
