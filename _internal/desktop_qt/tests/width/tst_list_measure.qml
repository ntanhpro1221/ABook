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
                // ba nhãn khác bề ngang ("", "Có lời", "Chưa phân tích"): công tắc Tự chọn phải cùng cột ở cả ba hàng
                "/api/music/local": {status: 200, data: {tracks: [{link: "local:" + "a1".repeat(20), title: "Bản nhạc bên sông",
                    creator: "Người kể chuyện", duration: 195, analysed: true},
                    {link: "local:" + "b2".repeat(20), title: "Bài hát có lời", creator: "Ca sĩ", duration: 201, analysed: true, vocalsLikely: true},
                    {link: "local:" + "c3".repeat(20), title: "Bài mới thêm", duration: 88, analysed: false}], module: null}}
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
        // Phần tử lặp ở các hàng anh em của một danh sách (cùng objectName: công tắc, nút, nhãn) phải đứng cùng một cột - một nhãn dài ngắn
        // khác nhau đứng trước đẩy mỗi hàng một x (01-11: "Tự chọn" ở 444/486/541 trên ảnh 1440).
        function sameColumn(list) {
            const groups = {}
            function walk(item) {
                if (!item.visible || item.opacity === 0) return
                if (item !== list && item.objectName) (groups[item.objectName] = groups[item.objectName] || []).push(item.mapToItem(list, 0, 0).x)
                for (const child of item.children || []) walk(child)
            }
            walk(list)
            let compared = 0
            for (const name in groups) {
                const xs = groups[name]
                if (xs.length < 2) continue
                ++compared
                verify(Math.max(...xs) - Math.min(...xs) <= 0.5, list.objectName + ": '" + name + "' của các hàng lệch cột: " + xs.map(x => Math.round(x)).join("/"))
            }
            return compared
        }
        function findNamed(item, name) {
            if (item.objectName === name) return item
            for (const child of item.children || []) {
                const found = findNamed(child, name)
                if (found) return found
            }
            return null
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
            sameColumn(d.scene === "chapter_list" ? page.contentItem : page) // mọi cảnh: phần tử lặp ở các hàng anh em cùng cột
            if (d.scene === "music_lists")
                for (const name of ["musicTrackList", "bookMusicList"]) {
                    const list = findNamed(page, name)
                    verify(list !== null, name)
                    verify(sameColumn(list) > 0, name + ": không có phần tử lặp nào để so")
                    let switches = 0
                    const count = item => { if (item.objectName === "autoPick" && item.visible) ++switches; for (const c of item.children || []) count(c) }
                    count(list)
                    compare(switches, 3, name + ": ba hàng đều có công tắc")
                }
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
