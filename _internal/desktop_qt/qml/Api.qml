import "UiStrings.js" as S
pragma Singleton
import QtQuick
import "VoiceLogic.js" as VoiceLogic

QtObject {
    id: root
    property var preferences: ({})
    property var info: ({})
    property bool loaded: false
    property bool saving: false
    property string notice: ""
    // Slot có ID của web: cảnh báo edited-elsewhere sống độc lập với lời Đã ghi.
    property var elsewhereNotice: null
    // Nút của lời báo ("Hoàn tác", "Mở thư mục"; action của toast bên web): {label, run} hay null. Gán `notice` thẳng là lời báo trơn, không nút.
    property var noticeAction: null
    property int noticeDuration: 0         // ms; 0 = mặc định của Toast (như sonner)
    property bool toasting: false
    onNoticeChanged: if (!toasting) { noticeAction = null; noticeDuration = 0 }
    // Lời báo kèm tuỳ chọn (toast(text, {duration, action: {label, onClick}}) của web): `options.action` = {label, run}. Cùng lời lần nữa vẫn hiện lại.
    function toast(text, options) {
        if (options && options.id === "edited-elsewhere") {
            elsewhereNotice = {text: text, action: options.action || null, duration: options.duration || 20000}
            return
        }
        toasting = true
        if (notice === text) notice = ""
        noticeAction = options && options.action ? options.action : null
        noticeDuration = options && options.duration ? options.duration : 0
        notice = text
        toasting = false
    }
    // Bấm nút của lời báo: lời báo khép lại rồi mới làm việc (việc ấy có thể báo lời mới)
    function dismissNotice(slot) { if (slot === "edited-elsewhere") elsewhereNotice = null; else notice = "" }
    function runNoticeAction(slot) {
        const action = slot === "edited-elsewhere" ? (elsewhereNotice ? elsewhereNotice.action : null) : noticeAction
        dismissNotice(slot)
        if (action && action.run) action.run()
    }
    property string voiceName: ""          // tên giọng đọc mặc định (dòng tóm tắt "Giọng đọc", useDefaultVoiceName của web)
    property string defaultVoice: ""       // mã giọng mặc định ("" = chưa chọn): localStorage "abook-readaloud-voice" của web + tuỳ chọn readAloudVoice (App.tsx)
    property var voiceList: []             // danh sách giọng lần hỏi gần nhất (GET /api/readaloud/voices)
    property bool voicesLoaded: false
    property bool voicesLoading: false
    property var transport: null
    property int requestSerial: 0
    property var requestsPending: ({})
    property int finishedRequest: 0
    property int finishedStatus: 0
    signal requestBegan(int id)
    signal requestDone(int id, int status)
    property var pendingLink: Connections {
        target: root.transport
        ignoreUnknownSignals: true
        function onRequestStarted(id) { root.requestSerial = id; const next = Object.assign({}, root.requestsPending); next[id] = true; root.requestsPending = next; root.requestBegan(id) }
        function onRequestFinished(id, status) { root.finishedRequest = id; root.finishedStatus = status; const next = Object.assign({}, root.requestsPending); delete next[id]; root.requestsPending = next; root.requestDone(id, status) }
    }
    property var themeObject: null
    function bind(bridge, theme) { transport = bridge; themeObject = theme }
    signal edited(string bookId)
    function call(method, path, body, done) {
        if (!transport) return 0
        return transport.request(method, path, body, function(status, data) {
            if (status >= 200 && status < 300) { if (done) done(data, null) }
            else {
                const error = data && (data.message || data.error) || S.s_chua_lam_duoc_luc_nay_2e7cacde
                notice = error
                if (done) done(null, error)
            }
        })
    }
    // Như call() nhưng KHÔNG đặt Api.notice: chỗ gọi tự hiện lỗi tại chỗ (khung khoá giọng, thẻ giọng trên máy) hay tự dựng lời báo.
    // Lỗi thì done(null, lời, thân) - `thân` là cả JSON máy chủ gửi (mã `reason` của "Nghe thử bằng câu của sách"), như ApiError.detail của web.
    function quiet(method, path, body, done) {
        if (!transport) return 0
        return transport.request(method, path, body, function(status, data) {
            if (status >= 200 && status < 300) { if (done) done(data, null) }
            else if (done) done(null, data && (data.message || data.error) || S.s_chua_lam_duoc_luc_nay_2e7cacde, data)
        })
    }
    // ---- Lượt thêm sách của máy chủ (import_jobs.py): người xem cấp app, như useImportJobs của web và thông báo của điện thoại ----
    // AddBook.qml chỉ là một người xem: đóng hộp giữa chừng thì lượt vẫn chạy, thanh bên hiện tiến độ (ImportStatus.qml), và chính người xem này làm mới
    // thư viện khi lượt xong - không nhờ lời gọi lại của hộp đã đóng. Lượt lỗi / dở (app đóng giữa chừng) ở lại kèm "Thử lại".
    property var importJobs: []
    property int importRevision: -1
    property int importScreens: 0           // AddBook đang mở thì nó tự báo kết quả
    readonly property var importRows: importJobs.filter(job => job.state !== "done").slice(0, 3)
    readonly property bool importRunning: importJobs.some(job => job.state === "running")
    // Chỉ hỏi khi có lý do (không có nhịp hỏi suốt ngày): lúc mở app (Main.qml - lượt dở của lần trước), khi hộp gửi / đóng (watchImports), và mỗi 800 ms
    // khi còn lượt đang chạy.
    property var importTimer: Timer {
        interval: 800
        repeat: true
        running: root.transport !== null && root.importRunning
        onTriggered: root.pollImports()
    }
    function pollImports() {
        quiet("GET", "/api/listen/import/jobs", null, function(data, error) {
            if (error || !data || typeof data.revision !== "number" || !Array.isArray(data.jobs) || data.revision === root.importRevision) return
            const first = root.importRevision < 0
            const known = ({})
            for (const job of root.importJobs) known[job.id] = job.state
            root.importRevision = data.revision
            root.importJobs = data.jobs
            if (first) return
            const ended = data.jobs.filter(job => job.state !== "running" && (known[job.id] || "running") === "running")
            if (ended.some(job => job.state === "done") && transport) transport.refreshLibrary()
            if (root.importScreens > 0) return
            for (const job of ended) {
                if (job.state === "done") notice = job.result && job.result.how === "updated" ? S.s_da_cap_nhat_0_627a2681(job.name)
                    : job.result && job.result.how === "existing" ? S.s_da_co_trong_thu_vien_3bb6eeb4 : S.s_da_them_0_ea40abe7(job.name)
                else notice = S.s_chua_them_duoc_sach_b327e086 + " - " + (job.state === "interrupted" ? S.s_import_interrupted : job.problem)
            }
        })
    }
    function watchImports() { pollImports() }
    function retryImport(id) { quiet("POST", "/api/listen/import/jobs/" + id + "/retry", null, function() { root.watchImports() }) }
    function dismissImport(id) { quiet("DELETE", "/api/listen/import/jobs/" + id, null, function() { root.watchImports() }) }
    function load() {
        call("GET", "/api/preferences", null, function(data, error) {
            if (error) return
            preferences = data; loaded = true
            defaultVoice = data.readAloudVoice || store("abook-readaloud-voice") || ""
            refreshVoiceName()
            if (themeObject) themeObject.mode = data.theme === "system" ? "auto" : (data.theme || "auto")
        })
        call("GET", "/api/app", null, function(data, error) { if (!error) info = data })
    }
    function update(changes, done) {
        if (saving) return
        saving = true
        call("PUT", "/api/preferences", changes, function(data, error) {
            saving = false
            if (!error) {
                preferences = Object.assign({}, preferences, data)
                if (themeObject) themeObject.mode = data.theme === "system" ? "auto" : (data.theme || "auto")
            }
            if (done) done(data, error)
        })
    }
    function editedBook(id) { if (transport) transport.refreshLibrary(); edited(id) }
    // Chỗ nhớ giọng mặc định (Platform.setting, như localStorage của web). Api không import ABook (vòng tự gọi), nên Platform được tạo muộn, lần đầu cần tới.
    property var storage: null
    function store(key, value) {
        if (!storage) {
            try { storage = Qt.createQmlObject('import QtQuick\nimport ABook\nQtObject { function get(k, f) { return Platform.setting(k, f) }\n function set(k, v) { Platform.setSetting(k, v) } }', root, "ApiStorage") }
            catch (error) { return value }
        }
        if (value !== undefined) { storage.set(key, value); return value }
        return storage.get(key, "")
    }
    // Tên giọng mặc định cho dòng tóm tắt ở trang gốc Cài đặt ("Hoài My"); "" khi máy chưa báo giọng nào
    function refreshVoiceName() {
        const voice = voiceList.length ? VoiceLogic.resolveVoice(voiceList, defaultVoice) : undefined
        voiceName = voice ? VoiceLogic.spokenVoiceName(voice.name) : ""
    }
    function loadVoiceName() {
        if (!transport || voicesLoading) return
        voicesLoading = true
        call("GET", "/api/readaloud/voices", null, function(data, error) {
            voicesLoading = false
            if (!error && Array.isArray(data)) { voicesLoaded = true; voiceList = data; refreshVoiceName() }
        })
    }
    // Saved audio needs no speech providers; text books and voice settings do.
    function ensureVoiceName() { if (!voicesLoaded && voiceList.length === 0) loadVoiceName() }
    function needsVoiceList(book) {
        // A partly recorded book may contain text-only chapters as well.
        return book.stage === "text" || Number(book.chaptersAvailable) < Number(book.chaptersTotal)
            || (book.chapters || []).some(chapter => chapter.state === "text")
    }
    // Đặt giọng mặc định từ Cài đặt (chooseDefaultVoice + App.tsx: lưu tuỳ chọn readAloudVoice, lỗi thì báo cách thử lại)
    property var savingVoice: null
    function chooseDefaultVoice(id) {
        if (savingVoice !== null || defaultVoice === id) return
        savingVoice = id
        call("PUT", "/api/preferences", {readAloudVoice: id}, function(data, error) {
            savingVoice = null
            if (error) { notice = VoiceLogic.DEFAULT_VOICE_ERROR; return }
            defaultVoice = id
            store("abook-readaloud-voice", id)
            preferences = Object.assign({}, preferences, {readAloudVoice: id})
            refreshVoiceName()
        })
    }
}
