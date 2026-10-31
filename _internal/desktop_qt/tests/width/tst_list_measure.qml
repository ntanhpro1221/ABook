import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

Item {
    id: host
    width: 1920; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Sidebar { width: 232; height: parent.height }
    Item { id: content; x: 272; y: 40; width: host.width - x - 40; height: 820 }
    Component {
        id: queues
        Column {
            spacing: 24
            ImportQueueList {
                width: parent.width
                currentId: 1
                items: [{id: 1, name: "Hành trình qua những miền đất mới.epub", state: "waiting"},
                    {id: 2, name: "Một tên sách dài cần được xuống dòng đầy đủ ".repeat(4) + ".txt", state: "waiting"},
                    {id: 3, name: "Những câu chuyện bên bờ sông.txt", state: "added"}]
            }
            ImportChapters {
                width: parent.width
                picked: [1, 2]
                chapters: [{index: 1, title: "Buổi sáng bên bờ sông", words: 1250},
                    {index: 2, title: "Một tên chương dài không được cắt chữ ".repeat(5), words: 1400}]
            }
        }
    }
    Component { id: studio; Column { spacing: 24; BookTemplates { width: parent.width } SharedReadingsSettings { width: parent.width } } }
    Component { id: music; Column { spacing: 24; MyMusicSettings { width: parent.width } EditBookMyMusic { width: parent.width } } }
    Component { id: chapters; ChapterList { model: Player.chapters } }
    Component {
        id: voices
        Column {
            VoiceRow { width: parent.width; shown: "Mai"; voice: ({name: "Mai", gender: "female"}); selected: true }
            VoiceRow { width: parent.width; shown: "Một tên giọng cần xuống dòng đầy đủ ".repeat(5); voice: ({name: shown, gender: "male"}) }
        }
    }
    TestCase {
        name: "ListMeasure"
        when: windowShown
        function init() {
            Theme.reduceMotion = false
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Platform.setSetting("fold.my-music.library", "1")
            Api.loaded = true
            Api.preferences = {bookTemplates: [{name: "Đêm khuya", narrator: "Mai", profile: "balanced"},
                {name: "Những câu chuyện của gia đình", narrator: "Nam", profile: "high_quality"}]}
            DesktopApi.responses = {
                "/api/readings": {status: 200, data: {entries: [{surface: "Nasdell", spokenForm: "hên-cơ", from: "Rokujouma"},
                    {surface: "Aiya", spokenForm: "a-i-a"}]}},
                "/api/music/local": {status: 200, data: {tracks: [{link: "local:" + "a1".repeat(20), title: "Bản nhạc bên sông",
                    creator: "Người kể chuyện", duration: 195, analysed: true}], module: null}}
            }
        }
        function cleanup() { Theme.mode = "auto"; Theme.reduceMotion = false; Nav.layers = [] }
        function check(item) {
            if (!item.visible || item.opacity === 0) return
            if (["measuredStudioRow", "importQueueViewport", "importChapterViewport", "musicTrackList", "bookMusicList", "voiceListRow"].includes(item.objectName)) {
                verify(item.width <= Theme.listMeasure + 0.5, item.objectName + " exceeds readable measure")
                verify(item.width <= content.width + 0.5, item.objectName + " exceeds available width")
            }
            if (item.text !== undefined && item.paintedWidth !== undefined) {
                verify(item.paintedWidth <= item.width + 1, "clipped text: " + item.text)
                verify(item.paintedHeight <= item.height + 1, "clipped text height: " + item.text)
            }
            for (const child of item.children || []) check(child)
        }
        function test_rows_data() {
            let rows = []
            for (const mode of ["light", "dark"])
                for (const w of [1024, 1366, 1630, 1920])
                    for (const scene of ["queues", "studio_lists", "music_lists", "chapter_list", "voice_list"])
                        rows.push({tag: mode + "_" + scene + "_" + w, mode: mode, w: w, scene: scene})
            return rows
        }
        function test_rows(d) {
            Theme.mode = d.mode; host.width = d.w
            const factories = {queues: queues, studio_lists: studio, music_lists: music, chapter_list: chapters, voice_list: voices}
            const page = createTemporaryObject(factories[d.scene], content, {width: content.width, height: content.height})
            verify(page !== null)
            VisualReady.render(this, host.Window.window, page, qtVisualReady)
            check(page)
            if (d.scene === "chapter_list") {
                verify(page.count > 0)
                for (const row of page.contentItem.children)
                    if (row.title !== undefined) verify(row.width <= Theme.listMeasure + 0.5)
            }
            qtGlyphAudit.scan()
            if (qtWideShotDir !== "") {
                host.Window.window.update(); waitForRendering(host)
                grabImage(host).save(qtWideShotDir + "/" + d.tag + ".png")
            }
            page.destroy()
        }
    }
}
