import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady

// Tên một dòng (DESIGN.md 5.5): thu cỡ tới Theme.oneLineMinScale cho vừa một dòng, không vừa thì xuống dòng ở cỡ gốc, không bao giờ "…".
// Cùng luật với điện thoại OneLineFit (TextCutScanTest) và web OneLineFit (shared/oneLineFit.dom.test.tsx).
Item {
    id: host
    width: 1024; height: 768
    Rectangle { anchors.fill: parent; color: Theme.bg }
    readonly property string mid: "Supertonic F1 - giọng nữ trầm ấm"
    readonly property string longName: "Supertonic F1 - giọng nữ trầm ấm đọc truyện dài cho những đêm khuya không ngủ"
    Component { id: fit; OneLineFit { baseSize: Theme.sizeBodySmall } }
    Component { id: row; VoiceRow {} }
    Component { id: voice; PlayerVoicePopover {} }
    TestCase {
        name: "OneLineFit"
        when: windowShown
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function init() {
            Theme.reduceMotion = true; Nav.layers = []; Nav.uiVisible = true
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
        }
        function cleanup() { Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto" }
        function uncut(item) {
            compare(item.elide, Text.ElideNone)
            verify(!item.truncated, "truncated: " + item.text)
            verify(item.paintedWidth <= item.width + 1, "painted past its width: " + item.text)
        }
        function test_short_stays_at_base_size() {
            const text = createTemporaryObject(fit, host, {room: 300, text: "Mai"})
            compare(text.fit, "one"); compare(text.font.pixelSize, Theme.sizeBodySmall); compare(text.lineCount, 1)
            verify(text.width < 300, "a short name keeps its own width so a label can follow it")
            uncut(text)
        }
        function test_slightly_long_shrinks_to_one_line() {
            const text = createTemporaryObject(fit, host, {text: host.mid})
            text.room = Math.floor(text.naturalWidth * 0.88)
            compare(text.fit, "shrunk")
            verify(text.font.pixelSize < Theme.sizeBodySmall, "smaller than base")
            verify(text.font.pixelSize >= Math.ceil(Theme.sizeBodySmall * Theme.oneLineMinScale), "not below the shared floor")
            compare(text.lineCount, 1)
            uncut(text)
        }
        function test_too_long_wraps_at_base_size() {
            const text = createTemporaryObject(fit, host, {text: host.longName})
            text.room = Math.floor(text.naturalWidth * 0.5)
            compare(text.fit, "wrap"); compare(text.font.pixelSize, Theme.sizeBodySmall)
            verify(text.lineCount > 1, "wraps instead of cutting")
            compare(text.width, text.room)
            uncut(text)
        }
        function test_room_grows_back() {
            const text = createTemporaryObject(fit, host, {text: host.longName})
            text.room = Math.floor(text.naturalWidth * 0.5); compare(text.fit, "wrap")
            text.room = text.naturalWidth + 10
            compare(text.fit, "one"); compare(text.font.pixelSize, Theme.sizeBodySmall); compare(text.lineCount, 1)
        }
        function test_voice_rows_data() { return [{tag: "wide", width: 520}, {tag: "narrow", width: 300}] }
        function test_voice_rows(data) {
            for (const name of ["Mai", host.mid, host.longName]) {
                const item = createTemporaryObject(row, host, {width: data.width, shown: name, voice: {id: "v", name: name, gender: "female"}})
                const label = findChild(item, "voiceName")
                verify(["one", "shrunk", "wrap"].includes(label.fit))
                compare(label.lineCount === 1, label.fit !== "wrap")
                uncut(label)
                const sample = findChild(item, "voiceTry")
                verify(sample.mapToItem(item, 0, 0).x - label.mapToItem(item, label.width, 0).x >= 12, "preview stays clear of the name")
            }
        }
        function test_popover_shot_data() { return [{tag: "light"}, {tag: "dark"}] }
        function test_popover_shot(data) {
            Theme.mode = data.tag
            Api.voiceList = [{id: "device:a", name: "Mai", provider: "device", default: true, online: false},
                {id: "device:b", name: host.mid, provider: "device", online: false},
                {id: "device:c", name: host.longName, provider: "device", online: true}]
            DesktopApi.responses["/api/readaloud/voices"] = {status: 200, data: Api.voiceList}
            Player.open("width", 1, 0, false); Player.pause()
            const sheet = createTemporaryObject(voice, host, {width: host.width, height: host.height})
            sheet.show(); tryCompare(sheet, "open", true); ready()
            for (const id of ["device:a", "device:b", "device:c"]) uncut(findChild(findChild(sheet, "playerVoice_" + id), "voiceName"))
            const path = Qt.resolvedUrl("../../build/d2shots/one_line_fit_voice_" + data.tag + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1")
            grabImage(host).save(path); verify(qtUiTree.save(path, host))
        }
    }
}
