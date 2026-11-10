import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Màn Nhạc (MusicScreen.qml) với máy chủ giả (DesktopApi.responses): Kho nhạc / Đã lưu / chế độ chọn / chi tiết bài (có "Vì sao bài này") / đang tải,
// ở 1440 và 1024 px, sáng + tối -> build/d2shots/music_*.png (tự xem ảnh: chữ không đè, không cắt). Cùng dữ liệu giả với phòng trưng bày web
// (ui/src/gallery/musicLibrary.ts, rút gọn). Lọc / tìm chạy ở máy chủ (bảng ca chung: test_music_library.py + MusicLibraryTests).
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: screenFactory; MusicScreen {} }

    TestCase {
        id: test
        name: "MusicLibrary"
        when: windowShown

        readonly property var styles: [["eastern_ancient", "Cổ phong phương Đông"], ["orchestral_epic", "Giao hưởng hùng tráng"], ["piano", "Piano"],
            ["ambient", "Ambient / không gian"], ["dark", "U tối / kinh dị"], ["world_other", "Nhạc thế giới khác (Ấn, Trung Đông, Phi...)"]]
        readonly property var emotions: [["peacefulness", "bình yên"], ["tenderness", "dịu dàng"], ["nostalgia", "hoài niệm"], ["sadness", "buồn"],
            ["joy", "vui tươi"], ["playful", "tinh nghịch"], ["power", "hào hùng"], ["wonder", "kỳ vĩ"], ["tension", "căng thẳng"], ["fear", "rùng rợn"],
            ["anger", "giận dữ"], ["mystery", "bí ẩn"], ["moved", "xúc động"]]
        readonly property var titles: ["Ghostpocalypse - 5 Apotheosis", "Air Prelude", "Mưa trên phố cổ",
            "Bản tình ca của những người lữ hành trong đêm dài không trăng", "Clean Soul", "Đồi gió", "Hành khúc đêm", "Long Road Ahead"]
        readonly property var creators: ["Kevin MacLeod", "Scott Buckley", "Shane Ivers", "Nhóm nhạc rất dài tên để kiểm chữ cắt ở dòng người sáng tác"]
        property var downloading: []

        function track(index) {
            const link = "https://music.example/" + index + ".mp3"
            const saved = index % 5 === 0
            return {link: link, title: titles[index % titles.length] + (index >= titles.length ? " " + (Math.floor(index / titles.length) + 1) : ""),
                creator: creators[index % creators.length], duration: 45 + (index * 53) % 420, bpm: 60 + (index * 17) % 110,
                style: styles[index % styles.length][0], bytes: 2400000 + index * 91000, lufs: -16, audibleStart: 0.4, saved: saved, downloaded: saved}
        }
        function tracks() { const out = []; for (let i = 0; i < 24; i++) out.push(track(i)); return out.sort((a, b) => a.title.localeCompare(b.title)) }
        function list(onlySaved) {
            const rows = tracks().filter(t => !onlySaved || t.saved)
            const kept = tracks().filter(t => t.saved)
            return {tracks: rows, count: rows.length, error: "", missingBytes: rows.filter(t => !t.downloaded).reduce((s, t) => s + t.bytes, 0),
                saved: {count: kept.length, bytes: kept.reduce((s, t) => s + t.bytes, 0)}}
        }
        function detailOf(index, why) {
            const base = track(index)
            const scores = emotions.map((e, at) => ({id: e[0], score: ((index * 37 + at * 53) % 100) / 100})).sort((a, b) => b.score - a.score)
            const out = Object.assign({}, base, {arousal: 0.58, license: "by", licenseUrl: "https://creativecommons.org/licenses/by/4.0/",
                attribution: "\"" + base.title + "\" " + base.creator + ", Licensed under Creative Commons: By Attribution 4.0 License",
                landing: "https://incompetech.com/music/royalty-free/", vocals: 0.1, emotions: scores,
                playlists: [{id: "fantasy_adventure", name: "Kỳ ảo phiêu lưu"}, {id: "calm_reading", name: "Đọc êm"}]})
            if (why) out.why = {fit: 0.86, matches: scores.slice(0, 3).map((e, at) => ({id: e.id, scene: Math.max(0, 0.9 - at * 0.2), track: e.score}))}
            return out
        }
        function api() {
            const r = {}
            r["GET /api/music/library/meta"] = {status: 200, data: {styles: styles.map(s => ({id: s[0], label: s[1]})), emotions: emotions.map(e => ({id: e[0], label: e[1]})),
                playlists: [{id: "fantasy_adventure", name: "Kỳ ảo phiêu lưu", count: 8}, {id: "calm_reading", name: "Đọc êm", count: 6}], error: ""}}
            r["GET /api/music/library"] = () => ({status: 200, data: test.list(false)})
            r["GET /api/music/library?saved=1"] = () => ({status: 200, data: test.list(true)})
            r["GET /api/music/library/downloads"] = () => ({status: 200, data: {active: test.activeDownloads(), failed: {}}})
            r["GET /api/music/local"] = {status: 200, data: {tracks: [], analyzer: false}}
            for (let i = 0; i < 24; i++) {
                const link = encodeURIComponent(track(i).link)
                r["GET /api/music/library/track?link=" + link] = {status: 200, data: detailOf(i, false)}
                r["GET /api/music/library/track?link=" + link + "&book=b&scene=" + encodeURIComponent("1:0")] = {status: 200, data: detailOf(i, true)}
            }
            r["PUT /api/books/b/music"] = {status: 200, data: {}}
            DesktopApi.responses = r
        }
        function activeDownloads() {
            const out = {}
            downloading.forEach((link, at) => { out[link] = {done: (at + 1) * 1100000, total: 2500000} })
            return out
        }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
            downloading = []
            api()
        }
        function cleanup() { Nav.layers = []; Theme.mode = "auto"; host.width = 1440; Api.notice = "" }

        function find(item, predicate) {
            if (!item) return null
            if (predicate(item)) return item
            for (const child of item.children || []) { const hit = find(child, predicate); if (hit) return hit }
            if (item.contentItem && item.contentItem !== item) { const hit = find(item.contentItem, predicate); if (hit) return hit }
            return null
        }
        function named(item, name) { return find(item, i => i.objectName === name) }
        function make(props) {
            const page = createTemporaryObject(screenFactory, host, Object.assign({width: host.width, height: host.height}, props || {}))
            verify(page !== null)
            tryVerify(function() { return page.meta !== null && page.shown.length > 0 }, 3000)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            return page
        }
        function shot(name) {
            host.Window.window.update()
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            qtGlyphAudit.scan()
            const img = grabImage(VisualReady.grabTarget(host.Window.window, host))
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(fn) { for (const mode of ["light", "dark"]) { Theme.mode = mode; fn() } }

        // ---- hành vi ----
        function test_libraryListsEveryTrackAndCountsThem() {
            const page = make({part: 1})
            compare(page.shown.length, 24)
            verify(named(page, "musicCount") !== null)
            verify(named(page, "musicList") !== null)
            // danh sách ảo hoá: không dựng đủ 24 hàng cùng lúc ở 900 px
            const rows = named(page, "musicList")
            verify(rows.count === 24)
        }
        function test_savedPartAsksTheServerForSavedTracks() {
            const page = make({part: 0})
            verify(DesktopApi.requests.some(r => r.path === "/api/music/library?saved=1"))
            compare(page.shown.length, 5)
            verify(named(page, "myMusic") !== null, "Nhạc của tôi là một phần của Đã lưu")
        }
        function test_pickModeUsesTheTrackForTheScene() {
            const page = make({pickBook: "b", pickScene: "1:0"})
            compare(page.part, 1)
            page.use(track(3).link)
            const put = DesktopApi.requests.filter(r => r.method === "PUT" && r.path === "/api/books/b/music")
            compare(put.length, 1)
            compare(put[0].body.pins["1:0"], track(3).link)
        }
        function test_detailShowsAllThirteenEmotionsAndWhy() {
            const page = make({pickBook: "b", pickScene: "1:0"})
            const detail = named(host.Window.window.contentItem, "musicTrackDetail")
            detail.show(track(5).link, {book: "b", scene: "1:0"})
            tryVerify(function() { return detail.detail !== null })
            compare(detail.detail.emotions.length, 13)
            verify(detail.detail.why !== undefined)
            detail.open = false
        }

        // ---- ảnh ----
        function test_shots() {
            for (const w of [1440, 1024]) {
                host.width = w
                both(function() {
                    const library = make({part: 1})
                    shot("music_library_" + w)
                    library.destroy()
                    const saved = make({part: 0})
                    shot("music_saved_" + w)
                    saved.destroy()
                    const pick = make({pickBook: "b", pickScene: "1:0"})
                    shot("music_pick_" + w)
                    const detail = named(host.Window.window.contentItem, "musicTrackDetail")
                    detail.show(track(5).link, {book: "b", scene: "1:0"})
                    tryVerify(function() { return detail.detail !== null })
                    tryVerify(function() { return detail.shown === 1 }, 3000, "tấm chi tiết mở hẳn trước khi chụp")
                    shot("music_track_" + w)
                    detail.open = false
                    pick.destroy()
                    test.downloading = [track(1).link, track(2).link]
                    const loading = make({part: 1})
                    tryVerify(function() { return loading.busy })
                    shot("music_downloading_" + w)
                    loading.destroy()
                    test.downloading = []
                })
            }
        }
    }
}
