import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Studio › tab "Nhạc nền" (MusicTab.tsx): cài đặt cả cuốn (bật/tắt, thể loại, mức nhạc, chọn lại), tải sẵn + huỷ, bài đã bỏ, Nhạc theo ngữ cảnh,
// Nhạc của tôi, các đoạn theo chương ("Đổi bài" tại chỗ, "…" im lặng / bỏ ghim / loại khỏi cuốn + Hoàn tác), nghe thử MỘT bài một lúc, ghi công,
// không hỏi khi cửa sổ ẩn, và Studio của máy đã ghép (mọi lời gọi qua /api/peers/<mã>/studio). HTTP là DesktopApi giả; ảnh sáng / tối ghi ra
// build/d2shots/sm_*.png để tự nhìn.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; StudioScreen {} }

    TestCase {
        id: test
        name: "StudioMusic"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string peerBase: "/api/peers/c0ffee000001/studio"
        readonly property string trackA: "https://music.example/bo-song.mp3"
        readonly property string trackB: "https://music.example/mua.mp3"
        readonly property string mineLink: "local:" + "ab".repeat(20)

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function all(item, name, out) {
            out = out || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children || []) all(child, name, out)
            return out
        }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found.filter(shown)[0] || found[0] }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function texts(item, out) {
            out = out || []
            if (item.text !== undefined && shown(item)) out.push(String(item.text))
            for (const child of item.children || []) texts(child, out)
            return out
        }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function shot(name, item) {
            const target = item || host
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            if (scrolled) { place(scrolled.page, scrolled.item); VisualReady.render(this, host.Window.window, target, qtVisualReady) }   // tải lại / đổi giao diện có thể kéo trang về đầu
            const path = Qt.resolvedUrl("../../build/d2shots/sm_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(target).save(path)
        }
        // Cuộn trang dự án để `item` nằm gần đầu khung (ảnh chụp chỉ thấy phần đang hiện)
        property var scrolled: null
        function place(page, item) {
            const list = one(page, "projectList")
            const y = item.mapToItem(list.contentItem, 0, 0).y - 24
            list.contentY = Math.max(list.originY, y)     // ListView ước cỡ phần chưa dựng: không chặn trên
        }
        function scrollTo(page, item) { scrolled = {page: page, item: item}; place(page, item); waitForRendering(page) }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }

        // ---- dữ liệu giả ----
        function stamp() { return Math.floor(Date.now() / 1000) }
        function book(id, over) {
            return Object.assign({
                id: id, title: "Cuốn " + id, statusLabel: "Hoàn tất", running: false, starting: false, paused: "", canPause: false, stopping: false,
                phase: "done", queuePosition: 0, pendingChanges: 0, audioSeconds: 5400, eta: null, startError: "", lastError: "", runEnd: null,
                createdAt: stamp() - 86400, updatedAt: stamp() - 3600, path: "D:\\Sách\\" + id, castLocked: false, precast: null,
                chapters: {total: 2, completed: 2, redo: 0, missingAudio: 0, failed: 0, working: 0},
                segments: {total: 120, analyzed: 120, recorded: 120, finished: 120, failed: 0, warnings: 0},
                progress: {overall: 1, analysis: 1, synthesis: 1},
                settings: {narrator: "Mai", profile: "balanced", profileLabel: "Cân bằng"}
            }, over || {})
        }
        function chapter(id) {
            return {
                id: id, index: id, title: "Chương " + id, displayTitle: "Chương " + id, subtitle: "", fullTitle: "Chương " + id, status: "completed", statusLabel: "Đã thu",
                segments: {total: 10, analyzed: 10, recorded: 10, finished: 10, failed: 0, warnings: 0}, seconds: 300, playable: true, redo: false,
                startedAt: stamp() - 7200, completedAt: stamp() - 3600, lastError: ""
            }
        }
        function scene(key, chapterId, start, end, over) {
            return Object.assign({key: key, chapterId: chapterId, start: start, end: end, valence: 0, arousal: 0, tension: 0, emotions: {}, link: trackA}, over || {})
        }
        function scenes() {
            return [
                scene("1:0", 1, 0, 90, {emotions: {sadness: 0.8, tenderness: 0.6}, moodSource: "llm"}),
                scene("1:1", 1, 90, 180, {continued: true}),
                scene("1:2", 1, 180, 300, {link: null, silenced: true}),
                scene("2:0", 2, 0, 120, {link: trackB, pinned: true, tension: 0.7}),
                scene("2:1", 2, 120, 200, {link: mineLink, pinned: true, pinUnavailable: true, valence: 0.5})
            ]
        }
        function tracks() {
            const out = {}
            out[trackA] = {title: "Bờ sông", creator: "Kevin MacLeod", attribution: "\"Bờ sông\" Kevin MacLeod (incompetech.com), CC BY 4.0", license: "cc-by"}
            out[trackB] = {title: "Mưa", creator: "Ai đó", license: "cc0"}
            out[mineLink] = {title: "Bài riêng", creator: "Tôi", source: "local"}
            return out
        }
        function musicData(over, overrides) {
            return Object.assign({
                plan: {enabled: true, levelDb: -20, genre: null, scenes: scenes(), tracks: tracks()},
                overrides: Object.assign({enabled: true, levelDb: -20, genre: null, pins: {}, silenced: [], banned: []}, overrides || {}),
                error: "",
                moods: {running: false, error: ""},
                taxonomy: {genres: {xianxia: {vi: "Tiên hiệp"}, western: {vi: "Dị giới / kỳ ảo phương Tây (kiếm, phép, rồng, hiệp sĩ)"}}, emotions: {sadness: "buồn", tenderness: "dịu dàng"}}
            }, over || {})
        }
        function localTrack(over) {
            return Object.assign({link: mineLink, title: "Bài riêng", creator: "Tôi", duration: 185, analysed: true, name: "rieng.mp3", bytes: 4200000}, over || {})
        }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "0.4.150", studio: {installed: true}, dialogs: true}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Nav.layers = []
            Nav.studioPeer = ""
            Theme.reduceMotion = false
            Clip.stop()
        }
        function cleanup() {
            Clip.stop()
            Theme.mode = "auto"; Theme.reduceMotion = false
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""; scrolled = null
            DesktopApi.delayed = false
        }
        // Mở cuốn "b" ở tab Nhạc nền; `folds` = các chương mở sẵn (khối gập nhớ theo Platform)
        function openMusic(data, options) {
            const opts = options || {}
            const base = opts.peer ? peerBase : ""
            const b = book("b")
            for (const id of opts.folds || []) Platform.setSetting("fold.studio.music.b." + id, "1")
            if (opts.local) Platform.setSetting("fold.studio.music.local", "1")
            if (opts.moods) Platform.setSetting("fold.studio.music.moods", "1")
            reply("GET " + base + "/api/library", {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: [b]}})
            reply("GET " + base + "/api/books/b", {status: 200, data: {book: b, chapters: [chapter(1), chapter(2)]}})
            reply("GET " + base + "/api/books/b/music", {status: 200, data: data || musicData()})
            if (opts.peer) {
                reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn"}}})
                Nav.studioPeer = peerId
            }
            const page = createTemporaryObject(studioFactory, host, {width: opts.width || 1280, height: opts.height || 900})
            verify(page !== null)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("b")
            tryCompare(page, "shownKey", "route:project")
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            one(page, "tab_music").clicked()
            tryCompare(page, "shownTab", "music")
            tryVerify(function() { const m = all(page, "studioMusic")[0]; return !!m && m.view !== null }, 3000)
            // phần cài đặt đã hiện hẳn (Collapse mờ dần vào)
            tryVerify(function() { return hasText(music(page), "Bài cho từng đoạn") }, 2000)
            return page
        }
        function music(page) { return all(page, "studioMusic")[0] }
        function sceneRows(page) { return all(page, "musicScene").filter(shown) }
        function sceneByKey(page, key) { return all(page, "musicScene").filter(r => r.scene.key === key)[0] }
        function pickMenu(page, key) {
            tryVerify(function() { return all(page, "menu_" + key).filter(shown).length > 0 }, 2000)
            one(page, "menu_" + key).clicked()
        }

        // ================= cả cuốn =================
        function test_settingsRowsAndChapterFolds() {
            const page = openMusic(musicData(), {folds: [1, 2]})
            const tab = music(page)
            for (const line of ["Nhạc nền", "Đang bật cho cuốn này.", "Thể loại truyện", "Chưa chọn thì nhạc lấy từ mọi thể loại", "Mức nhạc dưới giọng đọc",
                                "Nhỏ hơn giọng đọc bấy nhiêu; máy tự bù bài to hay nhỏ", "Bài cho từng đoạn", "Máy chọn lại theo thể loại và mức nhạc ở trên.",
                                "Chọn lại nhạc", "Nhạc theo ngữ cảnh", "Nhạc của tôi", "Chương 1", "Chương 2"])
                tryVerify(function() { return hasText(tab, line) }, 2000, line)
            compare(one(tab, "musicGenre").options.map(o => o.label), ["Chưa chọn", "Tiên hiệp", "Dị giới / kỳ ảo phương Tây (kiếm, phép, rồng, hiệp sĩ)"])
            compare(one(tab, "musicLevel").options.map(o => o.label), ["To", "Hơi to", "Vừa (mặc định)", "Nhỏ", "Rất nhỏ (dễ nghe lời nhất)"])
            compare(one(tab, "musicLevel").value, -20)
            // khối chương: tên chương + số đoạn
            const folds = all(tab, "musicChapter")
            compare(folds.length, 2)
            compare(folds[0].summary, "3")
            tryVerify(function() { return sceneRows(page).length === 5 })
            // giờ nối liền: đoạn này hết đúng chỗ đoạn sau bắt đầu
            compare(all(sceneByKey(page, "1:0"), "sceneTime")[0].text, "0:00–1:30")
            compare(all(sceneByKey(page, "1:2"), "sceneTime")[0].text, "3:00–5:00")
            // không khí: hai cảm xúc mạnh nhất (tên của danh mục) + nhãn AI; không cảm xúc nào đủ mạnh thì theo trục
            compare(all(sceneByKey(page, "1:0"), "sceneMood")[0].text, "buồn · dịu dàng")
            verify(shown(all(sceneByKey(page, "1:0"), "sceneAi")[0]))
            compare(all(sceneByKey(page, "1:0"), "sceneAi")[0].Accessible.description, "AI đã đọc cả đoạn này để chấm không khí")
            verify(!shown(all(sceneByKey(page, "1:1"), "sceneAi")[0]))
            compare(all(sceneByKey(page, "2:0"), "sceneMood")[0].text, "căng thẳng")
            compare(all(sceneByKey(page, "2:1"), "sceneMood")[0].text, "tươi vui")
            compare(all(sceneByKey(page, "1:2"), "sceneMood")[0].text, "êm")
            // bài: tên · tác giả; mảnh nối tiếp gọn; im lặng do bạn chọn; bài của bạn có nhãn; ghim không còn thì báo
            verify(hasPart(sceneByKey(page, "1:0"), "Bờ sông"))
            verify(hasPart(sceneByKey(page, "1:0"), "Kevin MacLeod"))
            verify(hasText(sceneByKey(page, "1:1"), "tiếp bài của đoạn trên"))
            compare(all(sceneByKey(page, "1:1"), "sceneSwap")[0].text, "Đổi từ đây")
            verify(!shown(all(sceneByKey(page, "1:1"), "sceneMore")[0]), "mảnh nối tiếp chỉ có một nút")
            verify(hasText(sceneByKey(page, "1:2"), "Im lặng (bạn chọn)"))
            verify(shown(all(sceneByKey(page, "2:0"), "scenePinned")[0]))
            verify(hasText(sceneByKey(page, "2:1"), "Nhạc của tôi"))
            verify(hasText(sceneByKey(page, "2:1"), "Bài bạn ghim không còn trên máy này - đoạn dùng bài khác."))
            // cột nút thẳng hàng (mép phải) ở mọi dòng: mảnh nối tiếp giữ chỗ cho "…"
            const edge = function(key) { const b = all(sceneByKey(page, key), "sceneSwap")[0]; return b.mapToItem(tab, b.width, 0).x }
            compare(edge("1:1"), edge("1:0"))
            compare(edge("2:0"), edge("1:0"))
            scrollTo(page, one(tab, "musicChapter"))
            both("overview", page)
            scrollTo(page, one(tab, "musicEnabled"))
            both("settings", page)
        }
        function test_chapterFoldsRememberAndBuildLazily() {
            const page = openMusic()
            const tab = music(page)
            compare(sceneRows(page).length, 0, "chương gập sẵn: chưa dựng đoạn nào")
            all(tab, "musicChapter")[1].children[0].clicked()
            tryVerify(function() { return sceneRows(page).length === 2 })
            compare(Platform.setting("fold.studio.music.b.2", "0"), "1")
        }
        function test_switchOffSendsPutAndDimsScenes() {
            const page = openMusic(musicData(), {folds: [1]})
            reply("PUT /api/books/b/music", function(body) { return {status: 200, data: musicData({}, {enabled: body.enabled})} })
            const tab = music(page)
            one(tab, "musicEnabled").clicked()
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 1 })
            compare(calls("PUT", "/api/books/b/music")[0].body, {enabled: false})
            tryVerify(function() { return hasText(tab, "Đang tắt: các đoạn dưới đây sẽ không phát.") })
            verify(shown(one(tab, "musicOffNote")))
            tryCompare(all(tab, "musicChapter")[0], "opacity", 0.5)
        }
        function test_genreSaysRebuildingWhileBusy() {
            const page = openMusic()
            const tab = music(page)
            DesktopApi.delayed = true
            reply("PUT /api/books/b/music", {status: 200, data: musicData({}, {genre: "xianxia"})})
            one(tab, "musicGenre").picked("xianxia")
            tryVerify(function() { return shown(one(tab, "musicBusy")) })
            compare(one(tab, "musicBusy").text, "Đang chọn lại nhạc, cỡ nửa phút.")
            compare(calls("PUT", "/api/books/b/music")[0].body, {genre: "xianxia"})
            verify(!one(tab, "musicGenre").enabled, "ô chọn mờ trong lúc chọn lại")
            DesktopApi.finish()
            tryVerify(function() { return !tab.changing })
            compare(one(tab, "musicGenre").value, "xianxia")
            // "Chưa chọn" gửi null
            DesktopApi.delayed = false
            one(tab, "musicGenre").picked("")
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 2 })
            compare(calls("PUT", "/api/books/b/music")[1].body, {genre: null})
        }
        function test_levelSavesQuietly() {
            const page = openMusic()
            const tab = music(page)
            DesktopApi.delayed = true
            reply("PUT /api/books/b/music", {status: 200, data: musicData({}, {levelDb: -28})})
            one(tab, "musicLevel").picked(-28)
            tryVerify(function() { return shown(one(tab, "musicBusy")) })
            compare(one(tab, "musicBusy").text, "Đang lưu lựa chọn")
            compare(calls("PUT", "/api/books/b/music")[0].body, {levelDb: -28})
            DesktopApi.finish()
        }
        function test_rebuildButtonAndLongGenreNameOnNarrow() {
            const page = openMusic(musicData({}, {genre: "western"}), {width: 560})
            const tab = music(page)
            tryVerify(function() { return hasPart(tab, "Dị giới / kỳ ảo phương Tây (kiếm, phép, rồng, hiệp sĩ)") }, 2000, "màn hẹp ghi đủ tên thể loại dưới lời nhắc")
            DesktopApi.delayed = true
            reply("POST /api/books/b/music/rebuild", {status: 200, data: musicData()})
            one(tab, "musicRebuild").clicked()
            tryCompare(one(tab, "musicRebuild"), "text", "Đang chọn lại")
            compare(one(tab, "musicBusy").text, "Đang chọn lại nhạc, cỡ nửa phút.")
            scrollTo(page, one(tab, "musicEnabled"))
            both("narrow", page)
            DesktopApi.finish()
            tryCompare(one(tab, "musicRebuild"), "text", "Chọn lại nhạc")
        }
        function test_downloadProgressAndCancel() {
            const page = openMusic(musicData({download: {active: true, done: 1, total: 4, doneBytes: 5000000, totalBytes: 12000000}}))
            const tab = music(page)
            tryVerify(function() { return shown(one(tab, "musicDownload")) })
            compare(one(tab, "musicDownload").text, "Đang tải sẵn nhạc nền: 4,8 MB / 11 MB (bài 2/4)")
            compare(one(tab, "musicDownload").Accessible.name, "Đang tải sẵn nhạc nền · 25%")
            verify(tab.polling, "đang tải sẵn: hỏi lại")
            reply("POST /api/books/b/music/download/cancel", {status: 200, data: musicData({download: {active: true, done: 1, total: 4}})})
            one(tab, "musicCancelDownload").clicked()
            tryVerify(function() { return calls("POST", "/api/books/b/music/download/cancel").length === 1 })
            tryVerify(function() { return !tab.polling })
            compare(Api.notice, "Đã dừng tải nhạc nền")
        }
        function test_noPollingWhileWindowHidden() {
            const page = openMusic(musicData({moods: {running: true, error: ""}}))
            const tab = music(page)
            verify(tab.polling)
            tab.store.active = false
            verify(!tab.polling, "cửa sổ ẩn: không hỏi")
            const before = calls("GET", "/api/books/b/music").length
            wait(3300) // fixed: proves absence
            compare(calls("GET", "/api/books/b/music").length, before)
            // hiện lại: hỏi ngay một lần; việc đọc không khí vừa xong thì báo
            reply("GET /api/books/b/music", {status: 200, data: musicData()})
            tab.store.active = true
            tryVerify(function() { return calls("GET", "/api/books/b/music").length > before })
            tryCompare(Api, "notice", "Đã đọc xong không khí các đoạn - nhạc đã chọn lại")
            verify(!tab.polling)
        }
        function test_bannedTracksCanComeBack() {
            const page = openMusic(musicData({bannedTracks: {"https://music.example/cu.mp3": {title: "Bài cũ", creator: "Người cũ"}}}, {banned: ["https://music.example/cu.mp3", "https://music.example/khong-ten%20bai.mp3"]}))
            const tab = music(page)
            const box = one(tab, "musicBanned")
            compare(box.summary, "Bài đã bỏ (2)")
            all(box, "detailsToggle")[0].clicked()
            tryVerify(function() { return all(tab, "musicUnban").filter(shown).length === 2 })
            verify(hasText(box, "Bài cũ · Người cũ"))
            verify(hasText(box, "khong-ten bai.mp3"), "không biết tên thì hiện tên file")
            reply("PUT /api/books/b/music", {status: 200, data: musicData()})
            all(tab, "musicUnban").filter(shown)[0].clicked()
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 1 })
            compare(calls("PUT", "/api/books/b/music")[0].body, {unban: ["https://music.example/cu.mp3"]})
        }
        function test_creditsListAndModifiedNote() {
            const page = openMusic()
            const tab = music(page)
            const box = one(tab, "musicCredits")
            compare(box.summary, "Ghi công (3)")
            all(box, "detailsToggle")[0].clicked()
            tryVerify(function() { return hasText(box, "\"Bờ sông\" Kevin MacLeod (incompetech.com), CC BY 4.0") })
            verify(hasText(box, "Mưa - Ai đó"))
            verify(hasText(box, "Bài riêng · Tôi - nhạc của bạn, không có thông tin giấy phép"))
            verify(hasText(box, "Đã chỉnh sửa: các bài nhạc được cắt vòng, trộn nhỏ dưới giọng đọc và chỉnh âm lượng cho vừa sách."))
        }
        function test_emptyErrorAndRetry() {
            const page = openMusic(musicData({plan: null}))
            const tab = music(page)
            verify(hasText(tab, "Chưa có đoạn nào - nhạc nền dựng sau khi sách đã phân tích."))
            compare(all(tab, "musicChapter").length, 0)
            verify(!shown(one(tab, "musicCredits")))
            // lỗi lần đầu: câu + Thử lại
            const b = book("b")
            reply("GET /api/books/b/music", {status: 500, data: {error: "hỏng"}})
            tab.view = null
            tab.load()
            tryVerify(function() { return hasText(tab, "Bạn hãy kiểm tra kết nối rồi tải lại nhạc nền.") })
            reply("GET /api/books/b/music", {status: 200, data: musicData()})
            const retry = texts(tab).indexOf("Thử lại")
            verify(retry >= 0)
            tab.failed = false
            tab.load()
            tryVerify(function() { return tab.view !== null && tab.groups.length === 2 })
        }

        // Cả tab nằm ở footer của danh sách dự án: mở / đóng một khối, mở "Đổi bài", tải lại - trang đứng yên chỗ đang cuộn
        function test_openingABlockKeepsTheScrollPosition() {
            const page = openMusic(musicData(), {folds: [2]})
            const tab = music(page)
            const list = one(page, "projectList")
            tryVerify(function() { return sceneRows(page).length === 2 })
            const before = list.contentHeight
            list.contentY = list.originY + 300
            all(tab, "musicChapter")[0].children[0].clicked()
            tryVerify(function() { return list.contentHeight > before + 100 })
            waitForRendering(page)
            compare(list.contentY - list.originY, 300)
            reply("GET /api/books/b/music/scenes/" + encodeURIComponent("2:0") + "/alternatives", {status: 200, data: {alternatives: [], mine: []}})
            all(sceneByKey(page, "2:0"), "sceneSwap")[0].clicked()
            tryVerify(function() { return all(sceneByKey(page, "2:0"), "musicAlternatives").filter(shown).length === 1 })
            waitForRendering(page)
            compare(list.contentY - list.originY, 300)
            reply("GET /api/books/b/music", {status: 200, data: musicData()})
            tab.load()
            tryVerify(function() { return calls("GET", "/api/books/b/music").length >= 2 })
            waitForRendering(page)
            compare(list.contentY - list.originY, 300)
        }

        // ================= từng đoạn =================
        function test_swapListsAlternativesAndPins() {
            const page = openMusic(musicData(), {folds: [1]})
            const tab = music(page)
            const alternatives = "/api/books/b/music/scenes/" + encodeURIComponent("1:2") + "/alternatives"
            reply("GET " + alternatives, {status: 200, data: {
                alternatives: [{link: "https://music.example/c.mp3", title: "Đồi gió", creator: "Kevin MacLeod", attribution: "", duration: 125, score: 0.9}],
                mine: [{link: mineLink, title: "Bài riêng", creator: "Tôi", duration: 185, analysed: true, fits: true}]}})
            tryVerify(function() { return sceneRows(page).length === 3 })
            const row = sceneByKey(page, "1:2")
            const layers = Nav.layers.length
            all(row, "sceneSwap")[0].clicked()
            tryVerify(function() { return calls("GET", alternatives).length === 1 })
            tryVerify(function() { return all(row, "musicChoose").filter(shown).length === 2 })
            compare(Nav.layers.length, layers + 1, "Đổi bài là một lớp Back")
            verify(hasPart(row, "Đồi gió"))
            verify(hasPart(row, "2:05"))
            verify(hasText(row, "Hợp không khí đoạn này"))
            scrollTo(page, row)
            both("swap", page)
            // Chọn = ghim; đoạn im lặng (bạn chọn) thì có nhạc lại
            reply("PUT /api/books/b/music", {status: 200, data: musicData()})
            all(row, "musicChoose").filter(shown)[0].clicked()
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 1 })
            compare(calls("PUT", "/api/books/b/music")[0].body, {pins: {"1:2": "https://music.example/c.mp3"}, silence: {"1:2": false}})
            tryCompare(tab, "swapping", "")
            compare(Nav.layers.length, layers)
        }
        function test_swapClosesWithBackAndEmptyLists() {
            const page = openMusic(musicData(), {folds: [2]})
            const tab = music(page)
            tryVerify(function() { return sceneRows(page).length === 2 })
            const row = sceneByKey(page, "2:0")
            all(row, "sceneSwap")[0].clicked()
            tryVerify(function() { return hasText(row, "Không còn bài nào khác trong danh mục đủ hợp đoạn này.") })
            verify(hasText(row, "Chưa có bài nào - bấm “Thêm nhạc của bạn” ở đầu trang."))
            Nav.back()
            tryCompare(tab, "swapping", "")
        }
        function test_sceneMenuSilenceUnpinAndBanWithUndo() {
            const page = openMusic(musicData(), {folds: [2]})
            const tab = music(page)
            reply("PUT /api/books/b/music", {status: 200, data: musicData()})
            tryVerify(function() { return sceneRows(page).length === 2 })
            scrollTo(page, sceneByKey(page, "2:0"))
            all(sceneByKey(page, "2:0"), "sceneMore")[0].clicked()
            tryVerify(function() { return all(page, "menu_silence").filter(shown).length > 0 })
            compare(one(page, "menu_silence").text, "Tắt nhạc đoạn này")
            compare(one(page, "menu_unpin").text, "Bỏ ghim")
            compare(one(page, "menu_ban").text, "Loại khỏi cuốn")
            verify(one(page, "menu_ban").danger)
            scrolled = null       // bảng "…" đứng theo chỗ nút lúc mở: không cuộn lại khi chụp
            both("menu", page)
            pickMenu(page, "unpin")
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 1 })
            compare(calls("PUT", "/api/books/b/music")[0].body, {pins: {"2:0": null}})
            // bỏ bài cho cả cuốn: báo số đoạn đang dùng + Hoàn tác
            tryVerify(function() { return !tab.changing })
            all(sceneByKey(page, "2:0"), "sceneMore")[0].clicked()
            pickMenu(page, "ban")
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 2 })
            compare(calls("PUT", "/api/books/b/music")[1].body, {ban: [trackB]})
            tryCompare(Api, "notice", "Đã bỏ “Mưa · Ai đó” cho cả cuốn (đang dùng ở 1 đoạn)")
            compare(Api.noticeAction.label, "Hoàn tác")
            Api.runNoticeAction()
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 3 })
            compare(calls("PUT", "/api/books/b/music")[2].body, {unban: [trackB]})
            // đoạn im lặng không có "Loại khỏi cuốn"
            const silent = musicData()
            silent.plan.scenes[3].link = null
            silent.plan.scenes[3].silenced = true
            silent.plan.scenes[3].pinned = false
            reply("GET /api/books/b/music", {status: 200, data: silent})
            tab.load()
            tryVerify(function() { return hasText(sceneByKey(page, "2:0"), "Im lặng (bạn chọn)") })
            all(sceneByKey(page, "2:0"), "sceneMore")[0].clicked()
            tryVerify(function() { return all(page, "menu_silence").filter(shown).length > 0 })
            compare(one(page, "menu_silence").text, "Bật nhạc đoạn này")
            compare(all(page, "menu_ban").filter(shown).length, 0)
            compare(all(page, "menu_unpin").filter(shown).length, 0)
            pickMenu(page, "silence")
            tryVerify(function() { return calls("PUT", "/api/books/b/music").length === 4 })
            compare(calls("PUT", "/api/books/b/music")[3].body, {silence: {"2:0": false}})
        }
        function test_previewPlaysOneAtATimeAndStopsAfterTwentySeconds() {
            const page = openMusic(musicData(), {folds: [1]})
            const tab = music(page)
            const c = "https://music.example/c.mp3"
            const d = "https://music.example/d.mp3"
            reply("GET /api/books/b/music/scenes/" + encodeURIComponent("1:0") + "/alternatives", {status: 200, data: {
                alternatives: [{link: c, title: "Đồi gió", creator: "", duration: 60, score: 1}, {link: d, title: "Đêm", creator: "", duration: 70, score: 0.8}], mine: []}})
            tryVerify(function() { return sceneRows(page).length === 3 })
            const row = sceneByKey(page, "1:0")
            all(row, "sceneSwap")[0].clicked()
            tryVerify(function() { return all(row, "musicPreview").filter(shown).length === 2 })
            const buttons = all(row, "musicPreview").filter(shown)
            buttons[0].clicked()
            compare(DesktopApi.previews, ["/api/music/track?link=" + encodeURIComponent(c)])
            compare(tab.previewing, c)
            tryCompare(buttons[0], "text", "Dừng nghe")
            // bài khác: bài trước dừng, chỉ một bài kêu
            buttons[1].clicked()
            compare(tab.previewing, d)
            compare(buttons[0].text, "Nghe thử")
            // ~20 giây rồi tự dừng (rút ngắn để thử)
            tab.previewMs = 50
            DesktopApi.previewStarted()
            tryCompare(tab, "previewing", "")
            compare(DesktopApi.stops, 1, "đổi bài nghe thử thay luôn, chỉ lần tự dừng gọi stop")
            // đóng "Đổi bài" thì bài đang nghe dừng
            buttons[0].clicked()
            compare(tab.previewing, c)
            all(row, "sceneSwap")[0].clicked()
            tryCompare(tab, "previewing", "")
        }
        function test_leavingTheTabStopsThePreview() {
            reply("GET /api/music/local", {status: 200, data: {tracks: [localTrack()], module: {state: "ready", done: 0, total: 0, error: "", ready: true, analysing: false, metered: false}}})
            const page = openMusic(musicData(), {local: true})
            const tab = music(page)
            tryVerify(function() { return all(tab, "musicPreview").filter(shown).length === 1 })
            all(tab, "musicPreview").filter(shown)[0].clicked()
            compare(DesktopApi.previews, ["/api/music/local/" + "ab".repeat(20) + "/file"])
            one(page, "tab_chapters").clicked()
            tryCompare(page, "shownTab", "chapters")
            tryCompare(Clip, "current", "")
        }

        // ================= nhạc theo ngữ cảnh, nhạc của tôi =================
        function test_moodsOfferDownloadThenCompute() {
            reply("GET /api/music/moods-model", {status: 200, data: {installed: false, downloading: false, progress: null, error: null, downloadable: true}})
            const page = openMusic(musicData(), {moods: true})
            const tab = music(page)
            tryVerify(function() { return shown(one(tab, "moodsDownload")) })
            verify(hasText(tab, "Hiểu ngữ cảnh để chọn nhạc; ~1 phút mỗi giờ sách."))
            compare(one(tab, "moodsDownload").text, "Tải thêm (3,2 GB)")
            reply("POST /api/music/moods-model", {status: 200, data: {installed: false, downloading: true, progress: {done: 1, total: 4}, error: null, downloadable: true}})
            one(tab, "moodsDownload").clicked()
            tryVerify(function() { return hasText(tab, "Đang tải phần đọc không khí - 25%") })
            // xong: "Đọc lại ngữ cảnh" -> máy chủ đọc lại, tab hỏi lại tới khi xong
            reply("GET /api/music/moods-model", {status: 200, data: {installed: true, downloading: false, progress: null, error: null, downloadable: true}})
            one(tab, "studioMusicMoods").load()
            tryVerify(function() { return shown(one(tab, "moodsCompute")) })
            compare(one(tab, "moodsCompute").text, "Đọc lại ngữ cảnh")
            reply("POST /api/books/b/music/moods", {status: 200, data: musicData({moods: {running: true, error: ""}})})
            one(tab, "moodsCompute").clicked()
            tryVerify(function() { return calls("POST", "/api/books/b/music/moods").length === 1 })
            tryCompare(one(tab, "moodsCompute"), "text", "Đang đọc không khí")
            verify(tab.polling)
            scrollTo(page, one(tab, "studioMusicMoods"))
            both("moods", page)
        }
        function test_moodsOllamaOnlyTellsWhereToInstall() {
            reply("GET /api/music/moods-model", {status: 200, data: {installed: false, downloading: false, progress: null, error: null, downloadable: false}})
            const page = openMusic(musicData(), {moods: true})
            tryVerify(function() { return hasText(music(page), "Máy này chưa có phần đọc không khí (cài qua Ollama).") })
        }
        function test_myMusicListPreviewAndRemove() {
            const view = {tracks: [localTrack(), localTrack({link: "local:" + "cd".repeat(20), title: "Bài hai", analysed: false})], module: {state: "ready", done: 0, total: 0, error: "", ready: true, analysing: false, metered: false}}
            reply("GET /api/music/local", {status: 200, data: view})
            const page = openMusic(musicData(), {local: true})
            const tab = music(page)
            tryVerify(function() { return all(tab, "musicPreview").filter(shown).length === 2 })
            for (const line of ["Thêm nhạc làm nền; bài đã chọn đi cùng file sách.", "Nhạc riêng", "Thêm nhạc của bạn"]) tryVerify(function() { return hasText(tab, line) }, 2000, line)
            verify(hasPart(tab, "Bài riêng"))
            scrollTo(page, one(tab, "studioMyMusic"))
            both("mymusic", page)
            // xoá hai bước, Back lùi bước hỏi lại
            const list = one(tab, "studioTrackList")
            const first = all(list, "track:" + mineLink)[0]
            texts(first)
            const ask = all(first, "").filter(n => n.text === "Xoá" && shown(n))[0]
            verify(ask !== undefined)
            ask.clicked()
            tryVerify(function() { return hasText(first, "Xoá bài") })
            Nav.back()
            tryVerify(function() { return !first.confirming })
            ask.clicked()
            tryVerify(function() { return first.confirming })
            reply("DELETE /api/music/local/" + "ab".repeat(20), {status: 200, data: {tracks: [view.tracks[1]], module: view.module}})
            all(first, "").filter(n => n.text === "Xoá bài")[0].clicked()
            tryVerify(function() { return calls("DELETE", "/api/music/local/" + "ab".repeat(20)).length === 1 })
            tryCompare(Api, "notice", "Đã xoá khỏi Nhạc của tôi")
        }
        function test_myMusicEmptyInvitesImport() {
            reply("GET /api/music/local", {status: 200, data: {tracks: [], module: {state: "missing", done: 0, total: 900000000, error: "", ready: false, analysing: false, metered: false}}})
            const page = openMusic(musicData(), {local: true})
            const tab = music(page)
            tryVerify(function() { return hasText(tab, "Nhập nhạc") })
            verify(hasText(tab, "Thêm nhạc của bạn"))
            verify(all(tab, "musicImport").filter(shown).length === 0, "chưa có bài: nút nằm trong lời mời")
        }

        // ================= Studio của máy đã ghép =================
        function test_peerRoutesThroughTheBridgeAndHidesImport() {
            const alternatives = peerBase + "/api/books/b/music/scenes/" + encodeURIComponent("1:0") + "/alternatives"
            reply("GET " + alternatives, {status: 200, data: {alternatives: [{link: "https://music.example/c.mp3", title: "Đồi gió", creator: "", duration: 60, score: 1}],
                                                             mine: [{link: mineLink, title: "Bài riêng", creator: "Tôi", duration: 185, analysed: true, fits: false}]}})
            reply("PUT " + peerBase + "/api/books/b/music", {status: 200, data: musicData()})
            const page = openMusic(musicData(), {peer: true, folds: [1], local: true})
            const tab = music(page)
            verify(calls("GET", peerBase + "/api/books/b/music").length >= 1)
            tryVerify(function() { return hasText(tab, "Nhập/xoá trên máy chủ; ở đây dùng “Đổi bài” để ghim nhạc.") })
            compare(all(tab, "musicImport").filter(shown).length, 0)
            tryVerify(function() { return sceneRows(page).length === 3 })
            const row = sceneByKey(page, "1:0")
            all(row, "sceneSwap")[0].clicked()
            tryVerify(function() { return calls("GET", alternatives).length === 1 })
            tryVerify(function() { return all(row, "musicMine").filter(shown).length === 1 })
            // nhạc của tôi nằm trên máy kia: không nghe thử qua đường theo sách; bài danh mục thì nghe qua cầu nối
            compare(all(all(row, "musicMine")[0], "musicPreview").filter(shown).length, 0)
            all(row, "musicPreview").filter(shown)[0].clicked()
            compare(DesktopApi.previews, [peerBase + "/api/music/track?link=" + encodeURIComponent("https://music.example/c.mp3")])
            scrollTo(page, row)
            both("peer", page)
            one(tab, "musicEnabled").clicked()
            tryVerify(function() { return calls("PUT", peerBase + "/api/books/b/music").length === 1 })
            const direct = DesktopApi.requests.filter(r => (/^\/api\/(books|music)/).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct))
        }

        // ================= ảnh chụp sạch =================
        // Bộ thử vẽ bằng phần mềm, chỉ vẽ lại vùng bẩn: trang hẹp hơn cửa sổ để tab "Thêm" bị cắt (x 565 > 560) lại thành "⌄" lạc ở 571,333
        // trong ảnh của test sau, dù không item nào ở đó. tests/test_width.cpp (FullRepaint) vẽ lại cả cửa sổ mỗi khung; chuỗi dưới đây là đúng
        // chuỗi từng để lại nó (đổi mức nhạc ở trang rộng, rồi chọn lại nhạc ở trang hẹp).
        function test_zzPagesLeaveNoPixelsBehind() {
            const frames = qtFullRepaint.frames()
            const wide = openMusic()
            verify(qtFullRepaint.frames() > frames, "mỗi khung vẽ lại cả cửa sổ")
            DesktopApi.delayed = true
            reply("PUT /api/books/b/music", {status: 200, data: musicData({}, {levelDb: -28})})
            one(music(wide), "musicLevel").picked(-28)
            tryVerify(function() { return shown(one(music(wide), "musicBusy")) }, 2000, "đang lưu")
            DesktopApi.finish()
            cleanup(); wide.destroy(); init()     // trang thứ hai như một test mới
            const narrow = openMusic(musicData({}, {genre: "western"}), {width: 560})
            const tab = music(narrow)
            DesktopApi.delayed = true
            reply("POST /api/books/b/music/rebuild", {status: 200, data: musicData()})
            one(tab, "musicRebuild").clicked()
            tryCompare(one(tab, "musicRebuild"), "text", "Đang chọn lại")
            scrollTo(narrow, one(tab, "musicEnabled"))
            both("narrow", narrow)
            DesktopApi.finish()
            tryCompare(one(tab, "musicRebuild"), "text", "Chọn lại nhạc")
            scrolled = null
            narrow.destroy()
            tryVerify(function() { return host.children.length === 2 }, 2000, "trang đã huỷ")
            waitForRendering(host)
            const image = grabImage(host)
            const bg = image.pixel(5, 5)
            const left = []
            for (let x = 0; x < host.width; x++)
                for (let y = 0; y < host.height; y++) {
                    const c = image.pixel(x, y)
                    if (Math.abs(c.r - bg.r) + Math.abs(c.g - bg.g) + Math.abs(c.b - bg.b) > 0.1) left.push(x + "," + y)
                }
            compare(left.length, 0, "cửa sổ trống còn pixel: " + left.slice(0, 8).join(" "))
        }
    }
}
