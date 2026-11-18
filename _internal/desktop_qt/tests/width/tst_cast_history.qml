import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 640
    height: 480
    Component { id: factory; CastHistory { width: 600 } }
    QtObject {
        id: transport
        property int calls: 0
        property var lastBody: null
        property string lastPath: ""
        function quiet(method, path, body, answer) { calls++; lastPath = path; lastBody = body; answer({state: "pending"}, "") }
        function editedCast(id) {}
    }
    TestCase {
        name: "CastHistory"
        when: windowShown
        property var fixture: null
        function initTestCase() {
            const xhr = new XMLHttpRequest()
            xhr.open("GET", Qt.resolvedUrl("../../../tests/fixtures/cast_history.json"), false)
            xhr.send()
            fixture = JSON.parse(xhr.responseText)
        }
        function init() { Platform.reset(); transport.calls = 0 }
        function test_twoClicksQueueExactOperation() {
            const view = createTemporaryObject(factory, host, {bookId: "book1", history: fixture.history, editable: true, store: transport})
            verify(view)
            // First click opens the actual disclosure; second clicks the actual undo control.
            mouseClick(view.children[0])
            tryCompare(view, "expanded", true)
            const actions = []
            function collect(item) {
                if (item.text === "Hoàn tác" && item.kind === "ghost") actions.push(item)
                for (const child of item.children || []) collect(child)
            }
            tryVerify(function() { actions.length = 0; collect(view); return actions.length === 1 && actions[0].visible && actions[0].height > 0 })
            mouseClick(actions[0])
            compare(transport.calls, 1)
            compare(transport.lastPath, "/api/books/book1/cast-history/undo")
            compare(transport.lastBody.operationId, fixture.original)
        }
        function test_manualOnly() {
            const view = createTemporaryObject(factory, host, {bookId: "book1", history: {items: []}, editable: true, store: transport})
            verify(view)
            view.expanded = true
            wait(300) // fixed: proves absence - opening history never sends a request
            compare(transport.calls, 0)
        }
    }
}
