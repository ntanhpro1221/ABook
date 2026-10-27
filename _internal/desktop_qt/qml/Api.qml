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
    // Nút của lời báo ("Hoàn tác", "Mở thư mục"; action của toast bên web): {label, run} hay null. Gán `notice` thẳng là lời báo trơn, không nút.
    property var noticeAction: null
    property int noticeDuration: 0         // ms; 0 = mặc định của Toast (như sonner)
    property bool toasting: false
    onNoticeChanged: if (!toasting) { noticeAction = null; noticeDuration = 0 }
    // Lời báo kèm tuỳ chọn (toast(text, {duration, action: {label, onClick}}) của web): `options.action` = {label, run}. Cùng lời lần nữa vẫn hiện lại.
    function toast(text, options) {
        toasting = true
        if (notice === text) notice = ""
        noticeAction = options && options.action ? options.action : null
        noticeDuration = options && options.duration ? options.duration : 0
        notice = text
        toasting = false
    }
    // Bấm nút của lời báo: lời báo khép lại rồi mới làm việc (việc ấy có thể báo lời mới)
    function runNoticeAction() {
        const action = noticeAction
        notice = ""
        if (action && action.run) action.run()
    }
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
