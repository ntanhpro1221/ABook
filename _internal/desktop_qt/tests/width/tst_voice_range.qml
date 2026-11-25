import QtQuick
import QtTest
import ABook
import "../../qml" as UI
import "../../qml/WorkLogic.js" as W

Item {
    id: host
    width: 800
    height: 1200
    Rectangle { anchors.fill: parent; color: Theme.bg }
    property var fixture: ({})
    property var sent: []
    QtObject {
        id: fakeWork
        property string pendingNote: ""
        function saveSpeaker(item, lines, scope, request, done) {
            host.sent = [{lines: lines, speaker: request.speaker}]
            done()
        }
        function keepAllSpeakers(item, requests, done) { host.sent = requests; done() }
    }
    Component { id: factory; UI.WorkSpeaker { width: 760; work: fakeWork } }
    TestCase {
        name: "VoiceRange"
        when: windowShown
        function initTestCase() {
            const request = new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("../../../tests/fixtures/voice_review/contract.json"), false)
            request.send()
            host.fixture = JSON.parse(request.responseText)
        }
        function init() { host.sent = [] }
        function press(view, name) {
            const button = findChild(view, name)
            verify(button !== null, name)
            mouseClick(button)
            if (name === "voiceRange") tryCompare(findChild(view, "voiceRangeBody"), "settled", true)
        }
        function shot(name) {
            waitForRendering(host)
            const path = Qt.resolvedUrl("../../build/d2shots/g4_" + name + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1")
            grabImage(host).save(path); verify(qtUiTree.save(path, host))   // cây UI cạnh ảnh cho máy dò affordance của cổng phát hành
        }
        function test_openingDoesNotWriteAndSelectionIsExplicit() {
            const view = createTemporaryObject(factory, host, {item: host.fixture})
            verify(view !== null)
            compare(host.sent, [])
            shot("before")
            press(view, "voiceRange")
            shot("range")
            compare(view.rangeLines.map(line => line.stableId), ["near"])
            press(findChild(view, "voiceRangeExample_2"), "exampleTick")
            compare(view.rangeLines.map(line => line.stableId), host.fixture.selectedIds)
            press(view, "speakerNew")
            compare(host.sent[0].lines.map(line => line.stableId), host.fixture.selectedIds)
            compare(host.sent[0].speaker, host.fixture.newPerson)
        }
        function test_keepSeparateRespectsSelectionAndDefaultKeepIsOneLine() {
            compare(W.keepRequests(host.fixture)[0].lines.map(line => line.stableId), ["near"])
            const view = createTemporaryObject(factory, host, {item: host.fixture})
            press(view, "voiceRange")
            press(findChild(view, "voiceRangeExample_2"), "exampleTick")
            press(view, "speakerKeepGroups")
            compare(host.sent.length, 1)
            compare(host.sent[0].speaker, "MAI")
            compare(host.sent[0].lines.map(line => line.stableId), host.fixture.selectedIds)
            compare(W.keepRequests(host.fixture, []), [])
        }
        function test_pollingPreservesSelectionAndClosingRestoresSingleLine() {
            const view = createTemporaryObject(factory, host, {item: host.fixture})
            press(view, "voiceRange")
            press(findChild(view, "voiceRangeExample_2"), "exampleTick")
            view.item = JSON.parse(JSON.stringify(host.fixture))
            compare(view.rangeLines.length, 2)
            press(view, "voiceRange")
            compare(view.lines.map(line => line.stableId), ["near"])
        }
        function test_selectAllIsExplicitAndExceptionsStaySeparate() {
            const view = createTemporaryObject(factory, host, {item: host.fixture})
            press(view, "voiceRange")
            press(view, "voiceRangeAll")
            compare(view.rangeLines.length, 3)
            press(findChild(view, "voiceRangeExample_1"), "exampleTick")
            press(view, "speakerNew")
            compare(host.sent[0].lines.map(line => line.stableId), host.fixture.selectedIds)
            press(view, "voiceRangeNone")
            compare(view.rangeLines, [])
            compare(findChild(view, "speakerNew").enabled, false)
        }
    }
}
