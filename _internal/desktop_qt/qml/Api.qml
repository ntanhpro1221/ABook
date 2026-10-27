pragma Singleton
import QtQuick
import "VoiceLogic.js" as VoiceLogic

QtObject {
    id: root
    property var preferences: ({})
    property var info: ({})
    property bool loaded: false
    property bool saving: false
    // ---- lời báo (sonner của desktop/App.tsx: tối đa 2 thẻ chồng nhau, mới nhất ở trước) ----
    // `toasts`: các thẻ còn sống, mới nhất đầu tiên: {id, text, title, description, action: {label, run} | null, duration (ms, 0 = mặc định 4 giây),
    // version (đổi mỗi lần thẻ được báo lại cùng id: đếm lại từ đầu)}. Thẻ khép rồi rời danh sách ngay; Toast.qml giữ hình của nó cho tới hết hoạt cảnh ra.
    property var toasts: []
    property int toastSerial: 0
    // `notice` = chữ của thẻ mới nhất ("" = không có thẻ). Gán `notice = "chữ"` là báo một thẻ trơn (không nút); gán `notice = ""` là khép thẻ mới
    // nhất - chỗ gọi vừa tự hiện lỗi tại chỗ thì gỡ thẻ Api.call vừa báo.
    property string notice: ""
    readonly property var noticeAction: toasts.length ? toasts[0].action : null      // {label, run} của thẻ mới nhất hay null
    readonly property int noticeDuration: toasts.length ? toasts[0].duration : 0
    property bool syncingNotice: false
    onNoticeChanged: {
        if (syncingNotice) return
        if (notice === "") { if (toasts.length) dismiss(toasts[0].id) }
        else push(notice, {})
    }
    onToastsChanged: syncNotice()
    function syncNotice() {
        syncingNotice = true
        notice = toasts.length ? toasts[0].text : ""
        syncingNotice = false
    }
    function push(text, options) {
        const lines = String(text).split("\n")
        const id = options && options.id !== undefined ? String(options.id) : "abook-toast-" + (++toastSerial)
        const entry = {id: id, text: String(text), title: lines[0], description: lines.slice(1).join("\n"),
            action: options && options.action ? options.action : null, duration: options && options.duration ? options.duration : 0, version: ++toastSerial}
        // Cùng id (toast(..., {id}) của web): thay thẻ đang có tại chỗ, không thêm thẻ thứ hai
        const at = toasts.findIndex(t => t.id === id)
        if (at >= 0) { const list = toasts.slice(); list[at] = entry; toasts = list }
        else toasts = [entry].concat(toasts)
        syncNotice()
        return id
    }
    // Lời báo kèm tuỳ chọn (toast(text, {id, duration, action}) của web): `options.action` = {label, run}. Dòng đầu là tiêu đề; phần sau dòng đầu
    // là chi tiết, mở bằng nút "Chi tiết" (ToastDetails của web). Cùng lời lần nữa (không id) là một thẻ mới.
    function toast(text, options) { return push(text, options || {}) }
    function dismiss(id) {
        const list = toasts.filter(t => t.id !== id)
        if (list.length === toasts.length) return
        toasts = list
        syncNotice()
    }
    // Bấm nút của một thẻ: thẻ khép lại rồi mới làm việc (việc ấy có thể báo lời mới)
    function runToastAction(id) {
        const entry = toasts.find(t => t.id === id)
        dismiss(id)
        if (entry && entry.action && entry.action.run) entry.action.run()
    }
    function runNoticeAction() { if (toasts.length) runToastAction(toasts[0].id) }
    // Cỡ chữ / giãn dòng của chữ đọc và "đã nghe từ một câu" (ReaderPrefs của ReaderScreen.tsx, localStorage "abook-reader"): đổi ở màn đọc là
    // "Đọc theo" của Đang nghe đổi theo. Chỉ giữ cái người đã chọn; chưa chọn thì nơi dùng lấy Theme.sizeReading / Theme.lineHeightReading.
    property var reader: ({})
    property bool readerLoaded: false
    function loadReader() {
        if (readerLoaded) return
        readerLoaded = true
        try { const saved = JSON.parse(store("abook-reader") || "{}"); if (saved && typeof saved === "object") reader = saved }
        catch (error) { /* không đọc được thì như chưa chọn */ }
    }
    function setReader(changes) {
        loadReader()
        reader = Object.assign({}, reader, changes)
        store("abook-reader", JSON.stringify(reader))
    }
    property string voiceName: ""          // tên giọng đọc mặc định (dòng tóm tắt "Giọng đọc", useDefaultVoiceName của web)
    property string defaultVoice: ""       // mã giọng mặc định ("" = chưa chọn): localStorage "abook-readaloud-voice" của web + tuỳ chọn readAloudVoice (App.tsx)
    property var voiceList: []             // danh sách giọng lần hỏi gần nhất (GET /api/readaloud/voices)
    property var transport: null
    property var themeObject: null
    function bind(bridge, theme) { transport = bridge; themeObject = theme }
    signal edited(string bookId)
    function call(method, path, body, done) {
        if (!transport) return 0
        return transport.request(method, path, body, function(status, data) {
            if (status >= 200 && status < 300) { if (done) done(data, null) }
            else {
                const error = data && (data.message || data.error) || "Không làm được lúc này."
                notice = error
                if (done) done(null, error)
            }
        })
    }
    // Như call() nhưng KHÔNG đặt Api.notice: chỗ gọi tự hiện lỗi tại chỗ (khung khoá giọng, thẻ giọng trên máy) hay tự dựng lời báo
    function quiet(method, path, body, done) {
        if (!transport) return 0
        return transport.request(method, path, body, function(status, data) {
            if (status >= 200 && status < 300) { if (done) done(data, null) }
            else if (done) done(null, data && (data.message || data.error) || "Không làm được lúc này.")
        })
    }
    function load() {
        call("GET", "/api/preferences", null, function(data, error) {
            if (error) return
            preferences = data; loaded = true
            defaultVoice = data.readAloudVoice || store("abook-readaloud-voice") || ""
            refreshVoiceName()
            if (themeObject) themeObject.mode = data.theme === "system" ? "auto" : (data.theme || "auto")
        })
        call("GET", "/api/app", null, function(data, error) { if (!error) info = data })
        loadVoiceName()
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
        call("GET", "/api/readaloud/voices", null, function(data, error) { if (!error && Array.isArray(data)) { voiceList = data; refreshVoiceName() } })
    }
    // Đặt giọng mặc định từ Cài đặt (chooseDefaultVoice + App.tsx: lưu tuỳ chọn readAloudVoice, lỗi thì báo cách thử lại)
    function chooseDefaultVoice(id) {
        defaultVoice = id
        store("abook-readaloud-voice", id)
        preferences = Object.assign({}, preferences, {readAloudVoice: id})
        refreshVoiceName()
        call("PUT", "/api/preferences", {readAloudVoice: id}, function(data, error) { if (error) notice = VoiceLogic.DEFAULT_VOICE_ERROR })
    }
}
