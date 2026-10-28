import QtQuick
import QtTest
import ABook

TestCase {
    name: "HiddenPolling"
    when: windowShown
    property var win: null
    Component {
        id: factory
        Window {
            width: 800; height: 600
            property alias storage: storage
            AdvancedStorage { id: storage; width: 700 }
        }
    }
    function cache(total) {
        DesktopApi.responses = {"/api/readaloud/cache": {status: 200, data: {total: total, book: 0}}}
    }
    function requests() { return DesktopApi.requests.filter(r => r.path === "/api/readaloud/cache").length }
    function init() {
        DesktopApi.reset()
        Api.bind(DesktopApi, Theme)
        cache(10)
        win = factory.createObject(null)
        win.show()
        tryVerify(function() { return win.storage.usage !== null })
        findChild(win.storage, "storagePoll").interval = 40
        tryVerify(function() { return requests() >= 3 })
    }
    function cleanup() { win.destroy(); win = null }
    function test_minimizeStopsNetworkAndRestoreRefreshes() {
        win.showMinimized()
        wait(80)
        const n = requests()
        cache(42)
        wait(160)
        compare(requests(), n)
        compare(win.storage.usage.total, 10)
        win.showNormal()
        tryCompare(win.storage, "usage", {total: 42, book: 0})
        verify(requests() > n)
    }
    function test_trayHideStopsNetworkAndShowRefreshes() {
        win.hide()
        wait(80)
        const n = requests()
        cache(99)
        wait(160)
        compare(requests(), n)
        win.show()
        tryVerify(function() { return win.storage.usage.total === 99 })
        verify(requests() > n)
    }
}
