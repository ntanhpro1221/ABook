import QtQuick
import QtTest
import "ModalLayer.js" as ModalLayer
import ABook

// Lớp của mọi hộp thoại và bảng nổi: mở ra thì không phần tử nào của trang được vẽ đè lên mặt hộp, dù hộp khai báo ở đâu. Cảnh thử cố ý "khó":
// hộp đứng TRƯỚC phần còn lại của trang trong cùng một khung (anh em sau vẽ sau) và có một lớp phủ z 60 như thanh bên của Main. Mỗi loại hộp / bảng
// của app (mọi Modal, mọi Popover; loại khai báo bên trong một màn thì dựng cả màn rồi mở từng lớp tìm được) được mở trong cảnh ấy và máy dò
// ModalLayer lấy phần tử nhìn thấy trên cùng ở lưới điểm trong mặt lớp.
Item {
    id: host
    width: 1280
    height: 800
    Rectangle { anchors.fill: parent; color: Theme.bg }

    // Cảnh: `holder` khai báo đầu, sau đó là trang (z 0) và thanh bên (z 60) phủ kín, đều có chữ / nút / ô cuộn
    Component {
        id: sceneFactory
        Item {
            property alias holder: holder
            property alias anchor: anchor
            Item { id: holder; anchors.fill: parent }
            Rectangle {
                anchors.fill: parent
                color: Theme.bg
                Repeater {
                    model: 24
                    Text { x: 40 + (index % 4) * 300; y: 30 + Math.floor(index / 4) * 120; text: "Dòng của trang " + index; color: Theme.text; font.pixelSize: 18 }
                }
                MouseArea { anchors.fill: parent }
                Flickable { anchors.fill: parent; contentHeight: 3000 }
                Rectangle { id: anchor; x: 600; y: 300; width: 40; height: 40; radius: 8; color: Theme.accent }
            }
            Rectangle {
                z: 60
                width: 260
                height: parent.height
                color: Theme.panel
                Text { x: 24; y: 40; text: "Thanh bên"; color: Theme.text; font.pixelSize: 18 }
                MouseArea { anchors.fill: parent }
            }
        }
    }

    // Mọi Modal (gốc là Modal / CastModal)
    Component { id: addBook; AddBook {} }
    Component { id: castGender; CastGender {} }
    Component { id: castMerge; CastMerge {} }
    Component { id: castRename; CastRename {} }
    Component { id: castVoice; CastVoice {} }
    Component { id: chapterReader; ChapterReader {} }
    Component { id: devicesUnpair; DevicesUnpair {} }
    Component { id: editBook; EditBook {} }
    Component { id: editBookRename; EditBookRename {} }
    Component { id: editBookSaveAs; EditBookSaveAs {} }
    Component { id: findInBook; FindInBook {} }
    Component { id: phoneDiagnostics; PhoneDiagnostics {} }
    Component { id: playerConsent; PlayerConsent {} }
    Component { id: readingSuggestions; ReadingSuggestions {} }
    Component { id: recordDialogs; RecordDialogs {} }
    Component { id: shortcutsDialog; ShortcutsDialog {} }
    Component { id: studioConfirm; StudioConfirm {} }
    Component { id: studioRename; StudioRename {} }
    Component { id: plainModal; Modal { title: "Hộp thử"; Text { text: "Nội dung hộp"; color: Theme.text } } }
    // Mọi Popover (gốc là Popover)
    Component { id: chaptersPopover; ChaptersPopover {} }
    Component { id: musicPopover; MusicPopover {} }
    Component { id: outputPopover; OutputPopover {} }
    Component { id: playerVoicePopover; PlayerVoicePopover {} }
    Component { id: sleepPopover; SleepPopover {} }
    Component { id: speedPopover; SpeedPopover {} }
    Component { id: castMenu; CastMenu {} }
    Component { id: projectMenu; ProjectMenu {} }
    Component { id: scriptChapterMenu; ScriptChapterMenu {} }
    Component { id: chapterError; ChapterError {} }
    Component { id: plainPopover; Popover { Text { text: "Bảng thử"; color: Theme.text } } }
    // Màn / khối có Modal hay Popover khai báo bên trong
    Component { id: advancedAbout; AdvancedAbout {} }
    Component { id: advancedStorage; AdvancedStorage {} }
    Component { id: coverEditor; CoverEditor {} }
    Component { id: libraryScreen; LibraryScreen {} }
    Component { id: nowPlaying; NowPlaying {} }
    Component { id: phoneSync; PhoneSync {} }
    Component { id: voiceModule; VoiceModule {} }
    Component { id: otherComputers; OtherComputers {} }
    Component { id: bookPage; BookPage {} }
    Component { id: chapterList; ChapterList {} }
    Component { id: playerBar; PlayerBar {} }
    Component { id: scriptTab; ScriptTab {} }
    Component { id: studioScreen; StudioScreen {} }
    Component { id: tellerMode; TellerMode {} }
    Component { id: workBulkKeep; WorkBulkKeep {} }
    Component { id: phoneEdits; PhoneEdits {} }

    TestCase {
        id: test
        name: "ModalLayer"
        when: windowShown

        property var failures: []

        function init() {
            Theme.reduceMotion = false
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture", dialogs: true}
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
        }
        function cleanup() { Nav.layers = [] }

        function root() { return host.Window.window.contentItem }
        function waitShown(layer, value) { tryCompare(layer, "shown", value, 3000) }

        // Dựng `factory` trong cảnh khó và trả các lớp (Modal / Popover) mới sinh ra, dù còn dưới `made` hay đã tự dời lên gốc cửa sổ
        function build(factory) {
            const scene = createTemporaryObject(sceneFactory, host, {width: host.width, height: host.height})
            verify(scene !== null)
            const known = ModalLayer.layersIn(root(), [])
            const made = createTemporaryObject(factory, scene.holder, {})
            verify(made !== null)
            if (made.width === 0) { made.width = host.width; made.height = host.height }      // màn dựng riêng không có chỗ neo: cho đủ khổ cửa sổ
            const own = ModalLayer.layersIn(root(), []).filter(layer => known.indexOf(layer) < 0)
            verify(own.length > 0, "no Modal or Popover found inside the component")
            for (const layer of own) if (layer.anchorItem !== undefined && !layer.anchorItem) layer.anchorItem = scene.anchor
            return own
        }
        // Mở từng lớp, chờ mở hẳn, hỏi máy dò; trả danh sách lỗi
        function covered(layers) {
            const out = []
            for (const layer of layers) {
                layer.show()
                waitShown(layer, 1)
                const panel = ModalLayer.panelOf(layer)
                verify(panel !== undefined && panel.width > 0 && panel.height > 0, "an open layer must have a panel with a size")
                host.Window.window.update()
                waitForRendering(host)
                out.push.apply(out, ModalLayer.violations(root()))
                layer.close()
                waitShown(layer, 0)
            }
            return out
        }

        function test_nothingPaintsAboveTheLayer_data() { return layerTypes() }
        function test_layerHostsItselfAtTheWindowRoot_data() { return layerTypes() }
        function layerTypes() {
            return [
                {tag: "AddBook", factory: addBook}, {tag: "CastGender", factory: castGender}, {tag: "CastMerge", factory: castMerge},
                {tag: "CastRename", factory: castRename}, {tag: "CastVoice", factory: castVoice}, {tag: "ChapterReader", factory: chapterReader},
                {tag: "DevicesUnpair", factory: devicesUnpair}, {tag: "EditBook", factory: editBook}, {tag: "EditBookRename", factory: editBookRename},
                {tag: "EditBookSaveAs", factory: editBookSaveAs}, {tag: "FindInBook", factory: findInBook}, {tag: "PhoneDiagnostics", factory: phoneDiagnostics},
                {tag: "PlayerConsent", factory: playerConsent}, {tag: "ReadingSuggestions", factory: readingSuggestions}, {tag: "RecordDialogs", factory: recordDialogs},
                {tag: "ShortcutsDialog", factory: shortcutsDialog}, {tag: "StudioConfirm", factory: studioConfirm}, {tag: "StudioRename", factory: studioRename},
                {tag: "Modal", factory: plainModal},
                {tag: "ChaptersPopover", factory: chaptersPopover}, {tag: "MusicPopover", factory: musicPopover}, {tag: "OutputPopover", factory: outputPopover},
                {tag: "PlayerVoicePopover", factory: playerVoicePopover}, {tag: "SleepPopover", factory: sleepPopover}, {tag: "SpeedPopover", factory: speedPopover},
                {tag: "CastMenu", factory: castMenu}, {tag: "ProjectMenu", factory: projectMenu}, {tag: "ScriptChapterMenu", factory: scriptChapterMenu},
                {tag: "ChapterError", factory: chapterError}, {tag: "Popover", factory: plainPopover},
                {tag: "AdvancedAbout", factory: advancedAbout}, {tag: "AdvancedStorage", factory: advancedStorage}, {tag: "CoverEditor", factory: coverEditor},
                {tag: "LibraryScreen", factory: libraryScreen}, {tag: "NowPlaying", factory: nowPlaying}, {tag: "PhoneSync", factory: phoneSync},
                {tag: "VoiceModule", factory: voiceModule}, {tag: "OtherComputers", factory: otherComputers}, {tag: "BookPage", factory: bookPage},
                {tag: "ChapterList", factory: chapterList}, {tag: "PlayerBar", factory: playerBar}, {tag: "ScriptTab", factory: scriptTab},
                {tag: "StudioScreen", factory: studioScreen}, {tag: "TellerMode", factory: tellerMode}, {tag: "WorkBulkKeep", factory: workBulkKeep},
                {tag: "PhoneEdits", factory: phoneEdits}
            ]
        }
        // Mở trong cảnh khó: không phần tử nào của trang vẽ đè lên mặt lớp
        function test_nothingPaintsAboveTheLayer(data) {
            const list = covered(build(data.factory))
            verify(list.length === 0, ModalLayer.report(list))
        }
        // Mỗi lớp tự đặt mình ở gốc cửa sổ, không để chỗ khai báo quyết định thứ tự vẽ
        function test_layerHostsItselfAtTheWindowRoot(data) {
            for (const layer of build(data.factory)) compare(layer.parent, root(), "layer parent")
        }
    }
}
