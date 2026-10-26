pragma Singleton
import QtQuick

QtObject {
    id: root
    property var preferences: ({})
    property var info: ({})
    property bool loaded: false
    property bool saving: false
    property string notice: ""
    property string voiceName: ""          // tên giọng đọc mặc định (dòng tóm tắt "Giọng đọc"), do SettingsVoice điền
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
    function load() {
        call("GET", "/api/preferences", null, function(data, error) {
            if (error) return
            preferences = data; loaded = true
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
}
