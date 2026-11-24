import QtQuick
import QtTest
import "../../qml/ScriptScope.js" as Scope
import ABook
import "../../qml/UiStrings.js" as S
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 900; height: 850
    property var currentScope: null
    Button { id: entry; text: S.s_scope_title; onClicked: if (host.currentScope) host.currentScope.begin(host.currentScope.script.lines[0]) }
    Component { id: scopeFactory; ScriptScope {} }
    QtObject {
        id: fakeStore
        property string revision: "fixture-v1"
        property var requests: []
        function request(method, path, body, done) { requests = requests.concat([{method: method, path: path}]); done(200, {scopeRevision: revision}) }
        function ok(status) { return status === 200 }
    }
    TestCase {
        name: "ScriptScopeContract"
        when: windowShown
        function fixture() {
            const request = new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("../../../tests/fixtures/script_scope.json"), false)
            request.send()
            return JSON.parse(request.responseText)
        }
        function test_sharedIds_data() { return fixture().cases.map(item => Object.assign({tag: item.name}, item)) }
        function test_sharedIds(sample) {
            const lines = fixture().lines.map(line => sample.noMarkers ? Object.assign({}, line, {scene: null}) : line)
            const candidates = Scope.lines(lines, sample.anchor, sample.mode, sample.start, sample.end)
            compare(candidates.map(line => line.stableId), sample.ids)
            compare(Scope.selected(candidates, sample.toggled || []).map(line => line.stableId), sample.selected)
        }
        function test_tenLinesInThreeTaps() {
            const rows = fixture().lines.slice(0, 12).map(line => Object.assign({}, line, {wish: null, lineWish: null}))
            const script = {chapterId: 1, scopeRevision: "fixture-v1", cast: [{value: "OTHER", label: "Khách", lines: 1}], others: [], lines: rows}
            const modal = createTemporaryObject(scopeFactory, host, {script: script, store: fakeStore, bookId: "book"})
            verify(modal)
            let applied = []
            modal.apply.connect((lines, person) => applied.push({lines: lines, person: person}))
            fakeStore.revision = "fixture-v1"; fakeStore.requests = []
            host.currentScope = modal
            mouseClick(entry, entry.width / 2, entry.height / 2)
            tryVerify(() => modal.shown === 1)
            compare(applied.length, 0); compare(fakeStore.requests.length, 0)
            const person = findChild(modal, "scopePerson_OTHER")
            verify(person)
            mouseClick(person, person.width / 2, person.height / 2)
            tryVerify(() => modal.person !== null)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            grabImage(VisualReady.grabTarget(host.Window.window, host)).save(Qt.resolvedUrl("../../build/d2shots/scope_qt.png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1"))
            verify(qtUiTree.save(Qt.resolvedUrl("../../build/d2shots/scope_qt.png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1"), VisualReady.grabTarget(host.Window.window, host)))
            const apply = findChild(modal, "scopeApply")
            verify(apply)
            mouseClick(apply, apply.width / 2, apply.height / 2)
            compare(applied.length, 1); compare(applied[0].lines.length, 10)
            compare(applied[0].lines.map(line => line.stableId), fixture().cases[1].ids)
            compare(fakeStore.requests.length, 1)
            compare(fakeStore.requests[0].method, "GET")
        }
        function test_changedPreviewWritesNothing() {
            const rows = fixture().lines.slice(0, 12)
            const modal = createTemporaryObject(scopeFactory, host, {script: {chapterId: 1, scopeRevision: "fixture-v1", cast: [], others: [], lines: rows}, store: fakeStore, bookId: "book"})
            let applied = 0
            modal.apply.connect(() => ++applied)
            modal.begin(rows[0]); modal.person = {value: "OTHER", label: "Khách", lines: 0}
            fakeStore.revision = "fixture-v2"
            modal.submit()
            compare(applied, 0); verify(modal.error.length > 0)
        }
    }
}
