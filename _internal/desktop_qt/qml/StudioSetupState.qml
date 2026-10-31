import QtQuick
import ABook
import "StudioSetupLogic.js" as Setup

// Tình trạng cài Studio của máy (GET /api/studio/setup) và các lệnh Cài / Dừng / Gỡ: MỘT nơi cho thẻ "Cài Studio" ở màn Dự án (StudioSetupCard), khối nhắc ở
// trình tạo sách (StudioSetupNotice) và Cài đặt › Studio (StudioSettings) - ba nơi cùng một lời gọi, cùng một cách nói lỗi. `store` (StudioStore) đưa
// lời gọi qua máy tính đã ghép; không có thì đi thẳng Api.transport. Hỏi lại mỗi 1 giây lúc đang cài, 2 giây khi còn lượt cài cũ chạy ngầm.
QtObject {
    id: root
    property var store: null
    property var info: store ? store.info : Api.info
    property bool wanted: true              // false: không hỏi gì (cửa sổ ẩn, màn không cần)
    property var status: null
    property bool busy: false
    readonly property bool present: Boolean(info && info.studio)
    readonly property bool installed: status !== null && Boolean(status.installed)
    readonly property var fit: status ? Setup.studioFit(status.gpu) : null
    readonly property var gpu: status ? status.gpu : null
    readonly property int pollMs: status && status.running ? 1000 : status && status.leftover ? 2000 : 0
    signal finished(var status)             // lượt cài vừa dừng (xong hay lỗi)

    function request(method, path, body, done) {
        if (store) store.request(method, path, body, done)
        else if (Api.transport) Api.transport.request(method, path, body, done)
        else if (done) done(0, null)
    }
    function load() {
        if (!present || !wanted) return
        request("GET", "/api/studio/setup", null, function(code, data) { if (code >= 200 && code < 300 && data) root.adopt(data) })
    }
    function adopt(data) {
        const was = status !== null && Boolean(status.running)
        status = data
        if (was && !data.running) finished(data)
    }
    // POST / DELETE: done(ok, data); lỗi chưa được nói thì chỗ gọi nói bằng failure()
    function ask(method, path, done) {
        busy = true
        request(method, path, method === "DELETE" ? null : {}, function(code, data) {
            root.busy = false
            const ok = code >= 200 && code < 300
            if (ok && data) root.adopt(data)
            if (done) done(ok, data)
        })
    }
    function install(done) { ask("POST", "/api/studio/setup", done) }
    function cancel(done) { ask("POST", "/api/studio/setup/cancel", done) }
    function remove(done) { ask("DELETE", "/api/studio/setup", done) }
    function failure(title, data) { Api.notice = title + "\n" + (data && (data.message || data.error) || "Chưa làm được lúc này.") }
    // Hỏi lại /api/app sau khi cài / gỡ để cả app biết Studio đã đổi
    function refreshInfo() { if (!store) Api.call("GET", "/api/app", null, function(data, error) { if (!error) Api.info = data }) }

    property Timer poll: Timer {
        interval: Math.max(1, root.pollMs)
        repeat: true
        running: root.wanted && root.present && root.pollMs > 0
        onTriggered: root.load()
    }
    onPresentChanged: if (present && status === null) load()
    onWantedChanged: if (wanted && status === null) load()
    Component.onCompleted: load()
}
