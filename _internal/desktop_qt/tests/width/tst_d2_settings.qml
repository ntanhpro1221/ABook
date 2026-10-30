import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Cài đặt › Nghe / Hẹn giờ ngủ / Giao diện / Nâng cao (F2): hành vi (mỗi công tắc / lựa chọn PUT đúng thân, thất bại giữ giá trị cũ + lời báo, lịch đêm,
// nhạc của tôi, dọn bộ nhớ, kiểm tra bản mới, hộp thành phần) và ảnh sáng + tối của từng nhóm và hộp thoại -> build/d2shots/settings_*.png.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: listenFactory; SettingsListen {} }
    Component { id: sleepFactory; SettingsSleep {} }
    Component { id: lookFactory; SettingsLook {} }
    Component { id: advancedFactory; SettingsAdvanced {} }
    Component { id: screenFactory; SettingsScreen {} }

    TestCase {
        id: test
        name: "D2Settings"
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        when: windowShown

        readonly property string sha1: "1f".repeat(20)
        readonly property string sha2: "a7".repeat(20)
        readonly property string sha3: "3c".repeat(20)
        readonly property string sha4: "9e".repeat(20)
        readonly property string longPath: "D:\\Sách nói của tôi\\Audiobooks\\Truyện dài kỳ\\Những cuốn sách đã nghe rất nhiều lần\\ThưMụcRấtDàiKhôngCóDấuCáchNàoCảVàKhôngNênBịCắtĐi"
        property var view: null

        function tracks() {
            return [
                {link: "local:" + sha1, title: "Nocturne Op.9 No.2", creator: "Frédéric Chopin", duration: 271, analysed: true, name: "nocturne.mp3", bytes: 4200000},
                {link: "local:" + sha2, title: "Gymnopédie No.1", creator: "Erik Satie", duration: 198, analysed: true, vocalsLikely: true, name: "gymno.flac", bytes: 21000000},
                {link: "local:" + sha3, title: "Mưa đêm trên phố cổ - ambient dài", creator: "", duration: 3725, analysed: false, name: "rain.m4a", bytes: 52000000},
                {link: "local:" + sha4, title: "Piano ngủ ngon", creator: "Nguyễn Minh", duration: 612, analysed: true, auto: "off", name: "piano.ogg", bytes: 9000000}
            ]
        }
        function moduleMissing() {
            return {state: "missing", done: 0, total: 820000000, error: "", ready: false, analysing: false, metered: false, cancellable: true}
        }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system", autoRewind: true, autoMusic: true, safetyStopHours: 2, sleepExtendMinutes: 10, sleepFadeSeconds: 30,
                sleepSchedule: null, readingSurface: "auto", touchSounds: true, letterShortcuts: true, libraryRoot: "C:\\Users\\An\\Audiobooks"}
            Api.info = {version: "0.4.147", dialogs: true}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Nav.layers = []
            Theme.reduceMotion = false
            view = {tracks: [], analyzer: false}
            DesktopApi.thirdParty = "# Thành phần sử dụng\n\nABook dùng các thành phần mã nguồn mở sau.\n\n## Qt\n\n- **Qt 6** (LGPL-3.0): khung giao diện, `QtQuick` và `QtMultimedia`.\n- Lucide (ISC): bộ biểu tượng.\n\n## Python\n\n- **CPython** (PSF): chạy phần máy chủ.\n\n## Ghi chú cho người bảo trì\n\n- Cách phát hành, không hiện cho người dùng.\n"
        }
        function cleanup() { DesktopApi.delayed = false; Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto"; Api.notice = "" }

        // ---- tiện ích ----
        function make(factory, props) {
            const item = createTemporaryObject(factory, host, Object.assign({width: 760}, props || {}))
            verify(item !== null)
            ready()
            return item
        }
        function find(item, predicate) {
            if (predicate(item)) return item
            for (const child of item.children || []) { const found = find(child, predicate); if (found) return found }
            return null
        }
        function named(item, name) { return find(item, i => i.objectName === name) }
        function texts(item, out) {
            out = out || []
            if (item.text !== undefined) out.push(String(item.text))
            if (item.label !== undefined) out.push(String(item.label))
            if (item.title !== undefined) out.push(String(item.title))
            if (item.hint !== undefined) out.push(String(item.hint))
            for (const child of item.children || []) texts(child, out)
            return out
        }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function switchOf(page, label) { const s = find(page, i => i.label === label && typeof i.toggled === "function"); verify(s !== null, "no switch " + label); return s }
        function choiceOf(page, label) { const c = find(page, i => i.label === label && typeof i.picked === "function"); verify(c !== null, "no choice " + label); return c }
        function buttonOf(page, text) { const b = find(page, i => i.text === text && typeof i.clicked === "function" && i.visible); verify(b !== null, "no button " + text); return b }
        function last(method, path) {
            const list = DesktopApi.requests.filter(r => r.method === method && r.path === path)
            return list.length ? list[list.length - 1] : null
        }
        function count(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path).length }
        function reply(path, status, data) { const r = DesktopApi.responses; r[path] = {status: status, data: data}; DesktopApi.responses = r }
        function replyWith(path, fn) { const r = DesktopApi.responses; r[path] = fn; DesktopApi.responses = r }
        function musicApi() {
            replyWith("GET /api/music/local", () => ({status: 200, data: test.view}))
        }

        // ---- Nghe ----
        function test_listenSwitchesWriteAndFail() {
            const page = make(listenFactory)
            const rewind = switchOf(page, "Tự lùi")
            verify(rewind.checked)
            rewind.toggled(false)
            compare(last("PUT", "/api/preferences").body.autoRewind, false)
            compare(Api.preferences.autoRewind, false)
            compare(Api.notice, "")
            reply("/api/preferences", 500, {error: "Không ghi được tệp tuỳ chọn"})
            rewind.toggled(true)
            compare(Api.preferences.autoRewind, false)
            compare(Api.notice, "Chưa lưu được cài đặt\nKhông ghi được tệp tuỳ chọn")
            DesktopApi.responses = {}
            Api.notice = ""
            const music = switchOf(page, "Tự chọn nhạc nền")
            music.toggled(false)
            compare(last("PUT", "/api/preferences").body.autoMusic, false)
            compare(Api.notice, "Đã tắt tự chọn nhạc nền")
            music.toggled(true)
            compare(Api.notice, "Đã bật tự chọn nhạc nền")
        }
        function test_myMusicFoldAndStates() {
            musicApi()
            DesktopApi.delayed = true
            const page = make(listenFactory)
            const mine = named(page, "myMusic")
            compare(mine.phase, "loading")
            DesktopApi.finish()
            DesktopApi.delayed = false
            compare(mine.phase, "empty")
            verify(!mine.open)
            const head = find(mine, i => i.title === "Nhạc của tôi" && typeof i.clicked === "function")
            compare(head.summary, "Chưa có bài nào")
            head.clicked()
            verify(mine.open)
            compare(Platform.store["fold.my-music.library"], "1")
            tryVerify(function() { return hasText(mine, "Thêm nhạc làm nền; bài đã chọn đi cùng file sách.") })
            tryVerify(function() { return hasText(mine, "Nhạc riêng") })
            tryVerify(function() { return hasText(mine, "Chưa có bài nào") })
            // tải lỗi -> câu lỗi + Thử lại
            const failing = make(listenFactory)
            const broken = named(failing, "myMusic")
            reply("GET /api/music/local", 500, {error: "Máy chủ chưa sẵn sàng"})
            broken.load()
            DesktopApi.responses = {}
            broken.view = null
            broken.loadFailed = true
            compare(broken.phase, "error")
            musicApi()
            broken.load()
            compare(broken.phase, "empty")
        }
        function test_myMusicTracksRemoveAndBack() {
            view = {tracks: tracks(), analyzer: true}
            musicApi()
            const page = make(listenFactory)
            const mine = named(page, "myMusic")
            compare(mine.tracks.length, 4)
            compare(find(mine, i => i.title === "Nhạc của tôi" && typeof i.clicked === "function").summary, "4 bài")
            mine.open = true
            tryVerify(function() { return named(mine, "track:local:" + sha1) !== null })
            const row = named(mine, "track:local:" + sha1)
            verify(row !== null)
            compare(row.note, "Đã phân tích - máy có thể tự chọn")
            compare(named(mine, "track:local:" + sha2).note, "Có vẻ có lời - máy không tự chọn bài này")
            compare(named(mine, "track:local:" + sha3).note, "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được")
            compare(named(mine, "track:local:" + sha4).note, "Máy không tự chọn bài này")
            compare(named(mine, "track:local:" + sha4).switcher.text, "Tự chọn lại")
            // Xoá: bước hỏi lại mở một lớp Back
            row.askRemove()
            compare(mine.removing, "local:" + sha1)
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            compare(mine.removing, "")
            compare(Nav.layers.length, 0)
            // thất bại: giữ nguyên bước hỏi lại và có lời
            row.askRemove()
            reply("DELETE /api/music/local/" + sha1, 500, {error: "Tệp đang được dùng"})
            row.remove()
            compare(Api.notice, "Không xoá được bài này\nTệp đang được dùng")
            compare(mine.removing, "local:" + sha1)
            // thành công: bài ra khỏi danh sách (hàng khép lại rồi gỡ), lớp Back đóng
            view = {tracks: tracks().slice(1), analyzer: true}
            reply("DELETE /api/music/local/" + sha1, 200, view)
            row.remove()
            compare(Api.notice, "Đã xoá khỏi Nhạc của tôi")
            compare(mine.removing, "")
            compare(Nav.layers.length, 0)
            compare(mine.tracks.length, 3)
            tryVerify(function() { return named(mine, "track:local:" + sha1) === null })
            // công tắc tự chọn của một bài
            const gym = named(mine, "track:local:" + sha2)
            compare(gym.switcher.text, "Cho tự chọn")
            gym.pick("on")
            compare(last("POST", "/api/music/local/" + sha2 + "/auto").body.auto, "on")
        }
        function test_myMusicImportSummary() {
            musicApi()
            const page = make(listenFactory)
            const mine = named(page, "myMusic")
            let n = 0
            replyWith("POST /api/music/local/import", body => {
                n++
                if (body.paths[0] === "/music/hong.mp3") return {status: 400, data: {error: "File không đọc được"}}
                const track = {link: "local:" + (n % 2 ? test.sha1 : test.sha3), title: "Bài " + n, creator: "", duration: 100, analysed: false, name: "x", bytes: 1}
                return {status: 200, data: {tracks: [track], analyzer: false, added: [track], existing: [], failed: []}}
            })
            mine.importFiles(["/music/a.mp3", "/music/b.mp3"])
            compare(count("POST", "/api/music/local/import"), 2)
            compare(last("POST", "/api/music/local/import").body.paths[0], "/music/b.mp3")
            compare(Api.notice, "Đã thêm: 2 bài mới\n2 bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.")
            verify(mine.progress === null)
            // dừng giữa chừng: lời dừng + phần đã vào
            mine.importFiles(["/music/c.mp3", "/music/hong.mp3"])
            compare(Api.notice, "Đang thêm nhạc thì dừng\nFile không đọc được\n\nĐã thêm: 1 bài mới\n1 bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.")
            // tiến độ trên nút
            DesktopApi.delayed = true
            mine.importFiles(["/music/d.mp3", "/music/e.mp3", "/music/f.mp3"])
            compare(mine.progress.total, 3)
            verify(hasText(mine, "Đang thêm 0/3"))
            DesktopApi.delayed = false
            DesktopApi.finish()
        }
        function test_myMusicModuleCard() {
            view = {tracks: tracks(), analyzer: false, module: moduleMissing()}
            musicApi()
            const page = make(listenFactory)
            const mine = named(page, "myMusic")
            mine.open = true
            tryVerify(function() { return named(mine, "musicModule") !== null })
            const card = named(mine, "musicModule")
            compare(card.label, "Tải 782 MB để tự chọn nhạc phù hợp trên máy.")
            compare(card.installText(), "Tải (782 MB)")
            verify(hasText(card, "Tải một lần, phân tích trên máy rồi dùng không cần mạng. Chưa tải vẫn nhập, nghe và ghim nhạc bằng tay."))
            replyWith("POST /api/music/local/module", () => ({status: 200, data: {tracks: test.tracks(), analyzer: false, module: {state: "downloading", done: 410000000, total: 820000000, error: "", ready: false, analysing: false, metered: false, cancellable: true}}}))
            card.post("/api/music/local/module")
            compare(card.label, "Đang tải Phân tích nhạc (782 MB, một lần) 50%")
            verify(card.downloadingModule)
            // lỗi tải: câu lỗi + Thử lại; bản mới: Cập nhật
            mine.refresh({tracks: tracks(), analyzer: false, module: {state: "error", done: 0, total: 820000000, error: "Mạng đứt giữa chừng", errorDetail: "HTTP 503", ready: false, analysing: false, metered: false}})
            compare(card.installText(), "Thử lại")
            compare(card.label, "Mạng đứt giữa chừng")
            mine.refresh({tracks: tracks(), analyzer: true, module: {state: "ready", done: 0, total: 820000000, error: "", ready: true, analysing: false, metered: false, stale: 3, precise: {state: "off", enabled: false, present: false, removable: false, reason: "", bytes: 1900000000, done: 0, total: 0, error: "", working: false, pending: 0}}})
            compare(card.action, "reanalyse")
            compare(card.label, "3 bài dùng phân tích cũ; có thể phân tích lại.")
            compare(card.preciseText(), "Tải (1,8 GB)")
            replyWith("POST /api/music/local/reanalyse", () => ({status: 200, data: {tracks: test.tracks(), analyzer: true, module: {state: "ready", done: 0, total: 0, error: "", ready: true, analysing: true, metered: false}}}))
            card.post("/api/music/local/reanalyse")
            compare(card.label, "Đang phân tích nhạc đã thêm")
        }

        // ---- Hẹn giờ ngủ ----
        function test_sleepChoicesWriteNumbers() {
            const page = make(sleepFactory)
            choiceOf(page, "Tự tắt").picked("3")
            compare(last("PUT", "/api/preferences").body.safetyStopHours, 3)
            choiceOf(page, "Số phút nghe thêm").picked("15")
            compare(last("PUT", "/api/preferences").body.sleepExtendMinutes, 15)
            choiceOf(page, "Độ dài nhỏ dần").picked("60")
            compare(last("PUT", "/api/preferences").body.sleepFadeSeconds, 60)
            verify(hasText(page, "Lúc đang nhỏ dần: chạm phím hoặc chuột."))
            verify(hasText(page, "Không ai chạm máy chừng này thì nhỏ dần rồi dừng."))
            reply("/api/preferences", 500, {error: "Đĩa đầy"})
            choiceOf(page, "Tự tắt").picked("0")
            compare(Api.preferences.safetyStopHours, 3)
            compare(Api.notice, "Chưa lưu được cài đặt\nĐĩa đầy")
        }
        function test_nightSchedule() {
            const page = make(sleepFactory)
            const window = named(page, "sleepWindow")
            const toggle = switchOf(page, "Lịch đêm")
            verify(!toggle.checked)
            compare(window.height, 0)
            toggle.toggled(true)
            const sent = last("PUT", "/api/preferences").body.sleepSchedule
            compare(sent.from, "22:00"); compare(sent.to, "06:00"); compare(sent.minutes, 30)
            verify(toggle.checked)
            tryVerify(function() { return window.height > 40 })
            const from = choiceOf(window, "Từ"), to = choiceOf(window, "Đến"), minutes = choiceOf(window, "Số phút hẹn")
            compare(from.currentLabel, "22:00")
            compare(to.currentLabel, "06:00")
            compare(minutes.currentLabel, "30 phút")
            verify(hasText(window, "đến") && hasText(window, "hẹn"))
            from.picked("23:15")
            compare(last("PUT", "/api/preferences").body.sleepSchedule.from, "23:15")
            to.picked("05:45")
            compare(last("PUT", "/api/preferences").body.sleepSchedule.to, "05:45")
            minutes.picked(45)
            const body = last("PUT", "/api/preferences").body.sleepSchedule
            compare(body.minutes, 45); compare(body.from, "23:15"); compare(body.to, "05:45")
            compare(Api.preferences.sleepSchedule.minutes, 45)
            // giờ lệch 15 phút vẫn có trong danh sách
            Api.preferences = Object.assign({}, Api.preferences, {sleepSchedule: {from: "22:10", to: "06:00", minutes: 30}})
            tryCompare(from, "currentLabel", "22:10")
            tryVerify(function() { return from.options.length === 97 })
            // tắt
            toggle.toggled(false)
            verify(last("PUT", "/api/preferences").body.sleepSchedule === null)
            verify(!toggle.checked)
            tryCompare(window, "height", 0)
        }
        function test_nightScheduleDraftFailureAndMismatch() {
            const page = make(sleepFactory)
            const toggle = switchOf(page, "Lịch đêm")
            // máy chủ chậm: công tắc giữ giá trị mới, khoá tới khi có đáp; lệnh thứ hai bị bỏ qua
            DesktopApi.delayed = true
            toggle.toggled(true)
            verify(toggle.checked)
            verify(!toggle.enabled)
            toggle.toggled(false)
            compare(count("PUT", "/api/preferences"), 1)
            DesktopApi.delayed = false
            DesktopApi.finish()
            verify(toggle.enabled)
            verify(toggle.checked)
            // thất bại: về giá trị cũ + lý do máy chủ
            toggle.toggled(false)
            compare(Api.preferences.sleepSchedule, null)
            reply("PUT /api/preferences", 500, {error: "Tệp tuỳ chọn bị khoá"})
            toggle.toggled(true)
            verify(!toggle.checked)
            compare(Api.notice, "Chưa lưu được cài đặt\nTệp tuỳ chọn bị khoá")
            // máy chủ đáp 200 nhưng không nhận đúng lịch
            Api.notice = ""
            replyWith("PUT /api/preferences", () => ({status: 200, data: {sleepSchedule: null}}))
            toggle.toggled(true)
            compare(Api.notice, "Chưa đổi được lịch đêm\nMáy chủ chưa nhận lịch. Thử lại sau.")
            verify(!toggle.checked)
        }

        // ---- Giao diện ----
        function test_lookRows() {
            const page = make(lookFactory)
            choiceOf(page, "Màu").picked("dark")
            compare(last("PUT", "/api/preferences").body.theme, "dark")
            compare(Theme.mode, "dark")
            choiceOf(page, "Nền đọc").picked("ivory")
            compare(last("PUT", "/api/preferences").body.readingSurface, "ivory")
            switchOf(page, "Âm thanh chạm").toggled(false)
            compare(last("PUT", "/api/preferences").body.touchSounds, false)
            verify(hasText(page, "Tiếng khẽ khi bạn chọn. Im khi đang nghe."))
            verify(hasText(page, "Nền của chữ khi đọc theo."))
            verify(hasText(page, "Tắt nếu hay lỡ chạm phím hay nhập bằng giọng nói."))
            const list = find(page, i => i.rows !== undefined && i.letters !== undefined)
            verify(list.letters)
            verify(hasText(list, "Tắt / bật tiếng"))
            verify(!hasText(list, "Tắt / bật tiếng (đang tắt)"))
            switchOf(page, "Phím tắt chữ").toggled(false)
            compare(last("PUT", "/api/preferences").body.letterShortcuts, false)
            verify(!list.letters)
            verify(hasText(list, "Tắt / bật tiếng (đang tắt)"))
            verify(hasText(list, "Xem các phím tắt này (đang tắt)"))
            verify(hasText(list, "Phát / tạm dừng"))
            verify(!hasText(list, "Phát / tạm dừng (đang tắt)"))
            verify(hasText(list, "Phím một chữ cái đang tắt. Space, mũi tên, Esc vẫn chạy."))
        }

        // ---- Nâng cao ----
        function test_libraryPathWrapsAndChanges() {
            Api.preferences = Object.assign({}, Api.preferences, {libraryRoot: longPath})
            const page = make(advancedFactory, {width: 420})
            const label = find(page, i => i.text === longPath)
            verify(label !== null)
            verify(label.lineCount > 1, "path should wrap")
            verify(label.contentWidth <= label.width + 1)
            verify(!label.truncated)
            const change = buttonOf(page, "Đổi thư mục")
            verify(change.y > label.parent.y, "button drops under a long path")
            page.useLibrary("E:/Sách")
            compare(last("PUT", "/api/preferences").body.libraryRoot, "E:/Sách")
            compare(Api.notice, "Đã đổi thư mục thư viện")
            compare(Api.preferences.libraryRoot, "E:/Sách")
            Api.notice = ""
            reply("PUT /api/preferences", 400, {error: "Thư mục này không dùng được"})
            page.useLibrary("F:/Khác")
            compare(Api.preferences.libraryRoot, "E:/Sách")
            compare(Api.notice, "Chưa lưu được cài đặt\nThư mục này không dùng được")
        }
        function test_updateRowAndInstall() {
            Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true, update: {version: "0.4.148", notes: "Sửa lỗi nghe lại.\nThêm lịch đêm."}}
            const page = make(advancedFactory)
            const card = named(page, "advancedUpdate")
            tryVerify(function() { return hasText(card, "Cập nhật ABook") })
            tryVerify(function() { return hasText(card, "Sửa lỗi nghe lại.\nThêm lịch đêm.") })
            tryVerify(function() { return (find(card, i => i.textFormat === Text.StyledText).text) === ("<b>ABook 0.4.148</b> đã có · đang dùng 0.4.147") })
            reply("POST /api/app/update", 409, {error: "Không có bản mới để cài"})
            card.install()
            compare(Api.notice, "Chưa cập nhật được\nKhông có bản mới để cài")
            verify(!card.installing)
            DesktopApi.responses = {}
            card.install()
            compare(Api.notice, "Đang tải ABook 0.4.148 - app sẽ tự mở lại")
            verify(card.installing)
            verify(hasText(card, "Đang tải bản mới…"))
            card.failed()
            verify(!card.installing)
        }
        function test_updateCheckLines() {
            Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true}
            const page = make(advancedFactory)
            const card = named(page, "advancedUpdate")
            tryVerify(function() { return hasText(card, "ABook 0.4.147") })
            tryVerify(function() { return hasText(card, "Kiểm tra bản mới") })
            card.check()
            compare(count("POST", "/api/app/check-update"), 1)
            verify(card.checking)
            verify(hasText(card, "Đang kiểm tra…"))
            card.heard({state: "latest"})
            verify(!card.checking)
            compare(card.line.text, "ABook 0.4.147 là bản mới nhất.")
            card.check()
            card.heard({state: "failed", message: "Không tới được trang phát hành"})
            compare(card.line.text, "Không tới được trang phát hành")
            compare(card.line.tone, "error")
            // vỏ im: hết hạn chờ thì báo lỗi mạng
            card.waitMs = 60
            card.check()
            tryVerify(function() { return !card.checking })
            tryVerify(function() { return (card.line.text) === ("Chưa thấy trả lời từ trang phát hành - bạn kiểm tra mạng rồi thử lại.") })
            // lệnh hỏng: lời lỗi ngay dưới nút, không thêm lời báo
            reply("POST /api/app/check-update", 409, {error: "Bản chạy từ mã nguồn không tự cập nhật"})
            card.check()
            compare(card.line.text, "Bản chạy từ mã nguồn không tự cập nhật")
            compare(Api.notice, "")
            verify(!card.checking)
            DesktopApi.responses = {}
            // thấy bản mới: vỏ báo "found" qua kênh của nó (D3: không còn hỏi /api/app định kỳ), Main đọc lại /api/app -> mục "đã có" thay chỗ
            card.waitMs = 45000
            card.check()
            Api.info = {version: "0.4.147", canCheckUpdate: true, update: {version: "0.4.149", notes: ""}}
            Backend.updateChecked({state: "found"})
            verify(!card.checking)
            compare(card.line, null)
            verify(card.update !== null)
            compare(card.update.version, "0.4.149")
        }
        function test_storageClearDialog() {
            reply("GET /api/readaloud/cache", 200, {book: 0, total: 148000000})
            const page = make(advancedFactory)
            const storage = named(page, "advancedStorage")
            compare(storage.usage.total, 148000000)
            verify(hasText(storage, "Bản đọc đã làm chiếm 141 MB trên máy này."))
            verify(hasText(storage, "Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống."))
            buttonOf(storage, "Dọn bản đọc").clicked()
            const dialog = storage.confirmDialog
            verify(dialog.open)
            compare(dialog.title, "Dọn bản đọc đã làm")
            compare(dialog.description, "Dọn 141 MB bản đọc đã làm của mọi cuốn? Máy sẽ đọc lại khi nghe. Sách và chỗ đang nghe giữ nguyên.")
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
            // đang dọn thì chưa đóng được
            storage.ask()
            DesktopApi.delayed = true
            reply("DELETE /api/readaloud/cache?all=1", 200, {book: 0, total: 0})
            storage.clear()
            verify(storage.busy)
            dialog.close()
            verify(dialog.open)
            DesktopApi.delayed = false
            DesktopApi.finish()
            verify(!dialog.open)
            compare(Api.notice, "Đã dọn bản đọc đã làm")
            compare(storage.usage.total, 0)
            tryVerify(function() { return hasText(storage, "Chưa có bản đọc đã lưu.") })
            // lỗi: lời lỗi, hộp đóng như bản web
            reply("GET /api/readaloud/cache", 200, {book: 0, total: 31000000})
            storage.load()
            storage.ask()
            verify(dialog.open)
            reply("DELETE /api/readaloud/cache?all=1", 500, {error: "Tệp đang mở"})
            storage.clear()
            compare(Api.notice, "Chưa dọn được bản đọc\nTệp đang mở")
            verify(!dialog.open)
            compare(storage.usage.total, 31000000)
        }
        function test_diagnosticsSave() {
            const page = make(advancedFactory)
            const diag = named(page, "advancedDiagnostics")
            verify(hasText(diag, "Xem lại trước khi gửi; bạn tự gửi đi."))
            verify(hasText(diag, "Gửi nhật ký"))
            verify(hasText(diag, "Gồm thông tin máy và nhật ký gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được."))
            replyWith("POST /api/diagnostics/save", () => ({status: 200, data: {name: "abook-log.zip", folder: "D:/Nhật ký"}}))
            diag.busy = true
            diag.save("D:/Nhật ký")
            compare(last("POST", "/api/diagnostics/save").body.target, "D:/Nhật ký")
            compare(Api.notice, "Đã lưu gói nhật ký trong D:/Nhật ký")
            verify(!diag.busy)
            replyWith("POST /api/diagnostics/save", () => ({status: 200, data: {name: "abook-log.zip", folder: ""}}))
            diag.save("D:/X")
            compare(Api.notice, "Đã lưu gói nhật ký")
            reply("POST /api/diagnostics/save", 500, {error: "Không ghi được vào thư mục này"})
            diag.save("D:/X")
            compare(Api.notice, "Chưa lưu được gói nhật ký\nKhông ghi được vào thư mục này")
        }
        function test_aboutAndThirdPartyDialog() {
            const page = make(advancedFactory)
            const about = named(page, "advancedAbout")
            verify(hasText(about, "ABook 0.4.147 - nghe sách tiếng Việt và làm sách nói."))
            verify(hasText(about, "Mã nguồn mở (MIT): "))
            verify(hasText(about, "Thành phần sử dụng"))
            const dialog = about.thirdDialog
            verify(!dialog.open)
            find(about, i => i.title === "Thành phần sử dụng" && typeof i.clicked === "function").clicked()
            verify(dialog.open)
            compare(dialog.panelWidth, 560)
            compare(Nav.layers.length, 1)
            tryVerify(function() { const list = find(dialog, i => i.sections !== undefined && i.strong !== undefined); return list && list.sections.length === 3 })
            const list = find(dialog, i => i.sections !== undefined && i.strong !== undefined)
            compare(list.sections.length, 3)        // mở đầu, Qt, Python (mục người bảo trì bị bỏ)
            compare(list.sections[1].title, "Qt")
            compare(list.sections[1].items.length, 2)
            verify(list.sections[1].items[0].bullet)
            verify(!list.sections[0].items[0].bullet)
            verify(!JSON.stringify(list.sections).includes("Cách phát hành"))
            verify(Nav.back())
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
            DesktopApi.thirdParty = ""
            tryVerify(function() { return (list.sections.length) === (0) })
        }

        // ---- ảnh ----
        function shot(name, item) {
            const target = item || host
            target.Window.window.update()   // Cảnh tĩnh offscreen cần yêu cầu khung mới trước khi chờ.
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }
        function screen(group, props) {
            const page = createTemporaryObject(screenFactory, host, Object.assign({width: host.width, height: host.height, active: group}, props || {}))
            verify(page !== null)
            ready()
            return page
        }
        function overlayShot(name) { shot(name, host.Window.window.contentItem) }

        function test_shotListen() {
            view = {tracks: tracks(), analyzer: true, module: moduleMissing()}
            musicApi()
            both(function() {
                const page = screen("listen")
                shot("settings_listen_folded")
                const mine = named(page, "myMusic")
                mine.open = true
                ready()
                shot("settings_listen_music")
                mine.removing = "local:" + sha3
                ready()
                shot("settings_listen_remove_confirm")
                mine.removing = ""
                page.destroy()
                // chưa có bài nào
                view = {tracks: [], analyzer: false}
                const empty = screen("listen")
                named(empty, "myMusic").open = true
                ready()
                shot("settings_listen_empty")
                empty.destroy()
                view = {tracks: tracks(), analyzer: true, module: moduleMissing()}
            })
        }
        function test_shotMusicModule() {
            const precise = {state: "off", enabled: false, present: false, removable: false, reason: "", bytes: 1900000000, done: 0, total: 0, error: "", working: false, pending: 0}
            const states = [
                ["downloading", {state: "downloading", done: 369000000, total: 820000000, error: "", ready: false, analysing: false, metered: true, cancellable: true}],
                ["error", {state: "error", done: 0, total: 820000000, error: "Mạng đứt giữa chừng, bạn thử lại sau.", errorDetail: "HTTPSConnectionPool(host='huggingface.co'): Read timed out.", ready: false, analysing: false, metered: false}],
                ["precise", {state: "ready", done: 0, total: 0, error: "", ready: true, analysing: false, metered: false, stale: 3, precise: precise}],
                ["precise_working", {state: "ready", done: 0, total: 0, error: "", ready: true, analysing: true, metered: false, precise: Object.assign({}, precise, {state: "ready", enabled: true, present: true, working: true, pending: 2, removable: false})}]
            ]
            musicApi()
            both(function() {
                for (const [name, module] of states) {
                    view = {tracks: tracks().slice(0, 2), analyzer: true, module: module}
                    const page = screen("listen")
                    named(page, "myMusic").open = true
                    ready()
                    shot("settings_listen_module_" + name)
                    // đang tải: hỏi lại mỗi giây nên bảng vẽ lại, bỏ hẹn giờ để ảnh không đổi
                    page.destroy()
                }
            })
        }
        function test_shotSleep() {
            both(function() {
                const off = screen("sleep")
                shot("settings_sleep_off")
                off.destroy()
                Api.preferences = Object.assign({}, Api.preferences, {sleepSchedule: {from: "22:00", to: "06:00", minutes: 30}})
                const on = screen("sleep")
                ready()
                shot("settings_sleep_schedule")
                on.destroy()
                Api.preferences = Object.assign({}, Api.preferences, {sleepSchedule: null})
            })
        }
        function test_shotLook() {
            both(function() {
                const page = screen("look")
                shot("settings_look")
                page.destroy()
                Api.preferences = Object.assign({}, Api.preferences, {letterShortcuts: false})
                const off = screen("look")
                ready()
                shot("settings_look_letters_off")
                off.destroy()
                Api.preferences = Object.assign({}, Api.preferences, {letterShortcuts: true})
            })
        }
        function test_shotAdvanced() {
            reply("GET /api/readaloud/cache", 200, {book: 0, total: 148000000})
            both(function() {
                Api.info = {version: "0.4.147", dialogs: true}
                const plain = screen("advanced")
                ready()
                shot("settings_advanced")
                plain.destroy()
                // đủ mọi khối: có thể kiểm bản mới, khối gập mở sẵn
                Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true}
                Platform.setSetting("fold.settings.advanced.diagnostics", "1")
                Platform.setSetting("fold.settings.advanced.about", "1")
                const full = screen("advanced")
                ready()
                shot("settings_advanced_check")
                const card = named(full, "advancedUpdate")
                card.check()
                card.heard({state: "latest"})
                ready()
                shot("settings_advanced_checked")
                card.check()
                card.heard({state: "failed"})
                ready()
                shot("settings_advanced_check_failed")
                // cuối trang: khối Giới thiệu mở
                const scroller = find(full, i => i.contentY !== undefined && i.contentHeight !== undefined)
                scroller.contentY = Math.max(0, scroller.contentHeight - scroller.height)
                ready()
                shot("settings_advanced_bottom")
                full.destroy()
                Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true, update: {version: "0.4.148", notes: "Nghe lại đoạn đã đọc xong không phải chờ máy đọc lại.\nThêm lịch đêm trong Hẹn giờ ngủ."}}
                const update = screen("advanced")
                ready()
                shot("settings_advanced_update")
                const storage = named(update, "advancedStorage")
                storage.ask()
                ready()
                overlayShot("settings_advanced_storage_dialog")
                storage.confirmDialog.dismiss()
                const about = named(update, "advancedAbout")
                about.thirdDialog.show()
                ready()
                overlayShot("settings_advanced_third_party")
                about.thirdDialog.dismiss()
                update.destroy()
                // đường dẫn thư viện rất dài trên cửa sổ hẹp
                Api.info = {version: "0.4.147", dialogs: true}
                Api.preferences = Object.assign({}, Api.preferences, {libraryRoot: longPath})
                const narrow = screen("advanced", {width: 520, height: 900})
                ready()
                shot("settings_advanced_long_path", narrow)
                narrow.destroy()
                Api.preferences = Object.assign({}, Api.preferences, {libraryRoot: "C:\\Users\\An\\Audiobooks"})
                Platform.reset()
            })
        }
    }
}
