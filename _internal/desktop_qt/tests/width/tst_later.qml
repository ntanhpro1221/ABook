import QtQuick
import QtTest
import ABook

// Later.call (src/later.h) thay Qt.callLater ở mọi chỗ trong qml/: chạy ở vòng sự kiện kế, gộp cùng một hàm, và KHÔNG chạy khi màn
// của owner đã bị gỡ. Ca gỡ bằng Loader là đúng chỗ Qt.callLater để lọt: ngữ cảnh mất ngay (id thành null) mà object còn chờ xoá -
// EditBookActions báo "Cannot read property 'children' of null" ở tst_studio3, NewChapters "root is not defined".
Item {
    id: host
    width: 400
    height: 200
    property int calls: 0
    property var seen: null

    Text { text: "Later"; font.pixelSize: 14 }

    Component {
        id: screen
        Item {
            id: root
            property alias label: inner
            Item { id: inner }
            function later() { Later.call(root, function() { host.calls += 1; host.seen = inner }) }
            function relayout() { host.calls += 1 }
        }
    }

    Loader { id: loader; sourceComponent: screen }

    TestCase {
        name: "Later"
        when: windowShown

        function init() { host.calls = 0; host.seen = null; loader.active = true; tryVerify(() => loader.item !== null) }

        function test_runsOnTheNextTurnWithTheScreenAlive() {
            loader.item.later()
            compare(host.calls, 0, "chưa chạy ngay trong lượt gọi")
            tryCompare(host, "calls", 1)
            verify(host.seen !== null, "id trong màn vẫn đọc được")
        }
        function test_sameFunctionRunsOnce() {
            const item = loader.item
            let flushed = false
            for (let i = 0; i < 5; ++i) Later.call(item, item.relayout)
            Later.call(item, function() { flushed = true })
            tryVerify(() => flushed)
            compare(host.calls, 1)
        }
        function test_skipsWhenTheLoaderDropsTheScreen() {
            const before = Later.skipped()
            loader.item.later()
            loader.active = false
            tryVerify(() => Later.skipped() === before + 1)
            compare(host.calls, 0, "màn đã gỡ thì hàm hẹn không chạy (Qt.callLater vẫn chạy và báo TypeError)")
            compare(Later.skipped(), before + 1)
        }
    }
}
