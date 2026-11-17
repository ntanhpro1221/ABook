import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 1024; height: 768
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: voice; PlayerVoicePopover {} }
    Component { id: footer; InlineActionRow {} }
    Component { id: choices; ChoiceRow { options: [{value:"all",label:"Tất cả"},{value:"speech",label:"Chỉ lời nói"}]; value:"all" } }
    SignalSpy { id: settingsSpy }
    TestCase {
        name: "Affordance"
        when: windowShown
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function init() {
            settingsSpy.clear()
            Theme.reduceMotion = true; Nav.layers = []; Nav.uiVisible = true
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.voiceList = [{id: "device:local", name: "Google ngoại tuyến 1", provider: "device", default: true, online: false}, {id: "device:other", name: "Samsung cần mạng", provider: "device", online: true}]
            DesktopApi.responses["/api/readaloud/voices"] = {status: 200, data: Api.voiceList}
            DesktopApi.responses["POST /api/readaloud/clip"] = {status: 200, data: {url: "/media/sample.mp3", duration_ms: 4000}}
            Player.open("width", 1, 0, false); Player.pause()
        }
        function cleanup() { settingsSpy.target = null; Nav.layers = []; Theme.reduceMotion = false }
        function test_voice_data() { return [{tag: "light"}, {tag: "dark"}] }
        function test_voice(data) {
            Theme.mode = data.tag
            const sheet = createTemporaryObject(voice, host, {width: host.width, height: host.height})
            sheet.show(); tryCompare(sheet, "open", true); ready()
            const action = findChild(sheet, "playerVoiceAdd")
            verify(action); compare(action.action, true); compare(action.icon, "plus")
            const selected = findChild(sheet, "playerVoice_device:local")
            compare(selected.radio.Accessible.checked, true)
            const name = findChild(selected, "voiceName")
            const sample = findChild(selected, "voiceTry")
            selected.radio.forceActiveFocus()
            keyClick(Qt.Key_Down)
            const other = findChild(sheet, "playerVoice_device:other")
            compare(other.radio.activeFocus, true)
            keyClick(Qt.Key_Home)
            compare(selected.radio.activeFocus, true)
            compare(name.lineCount, 1)
            verify(sample.mapToItem(selected, 0, 0).x - name.mapToItem(selected, name.width, 0).x >= 12)
            compare(sample.Accessible.name, "Nghe thử Google ngoại tuyến 1")
            mouseClick(sample)
            tryCompare(selected, "playing", true)
            compare(DesktopApi.requests.filter(r => r.path === "/api/readaloud/clip").pop().body.voice, "device:local")
            mouseClick(sample)
            tryCompare(selected, "playing", false)
            settingsSpy.signalName = "settingsRequested"; settingsSpy.target = sheet
            const path = Qt.resolvedUrl("../../build/d2shots/affordance_voice_" + data.tag + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1")
            grabImage(host).save(path); verify(qtUiTree.save(path, host))
            action.forceActiveFocus(); keyClick(Qt.Key_Return)
            compare(settingsSpy.count, 1); compare(sheet.open, false)
        }
        function test_voiceClosingCancelsLatePreview() {
            const sheet = createTemporaryObject(voice, host, {width: host.width, height: host.height})
            sheet.show(); ready()
            DesktopApi.delayed = true
            const selected = findChild(sheet, "playerVoice_device:local")
            mouseClick(findChild(selected, "voiceTry"))
            sheet.close()
            DesktopApi.finish()
            tryCompare(selected, "playing", false)
        }
        function test_footer_responds_to_pointer() {
            const action = createTemporaryObject(footer, host, {width: 320, text: "Thêm giọng"})
            settingsSpy.signalName = "clicked"; settingsSpy.target = action
            ready(); mouseClick(action); compare(settingsSpy.count, 1)
        }
        function test_initial_choice_has_a_painted_underline() {
            const row = createTemporaryObject(choices, host, {width:320})
            ready()
            const marks = row.children.filter(child => child.height === 2 && child.width > 0 && String(child.color) === String(Theme.accent))
            compare(marks.length, 1)
            verify(marks[0].visible)
        }
    }
}
