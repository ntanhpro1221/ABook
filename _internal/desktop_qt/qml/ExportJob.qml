import QtQuick
import ABook
import "ExportLogic.js" as Logic

// Việc xuất nền của một cuốn (ExportJobHost + followPackJob của bản web, gom về MỘT chỗ cho cả bốn kiểu: MP3, M4B, .abook, .abookproj): bắt đầu qua
// `/api/books/<mã>/<kiểu>-job`, rồi hỏi lại mỗi giây tới khi xong / hỏng / bị huỷ. Chỉ hỏi khi cửa sổ đang thấy (`store.active`): ẩn thì dừng hỏi,
// hiện lại hỏi tiếp - việc vẫn chạy ở máy chủ. Hỏi hụt 5 lần liền mới coi là hỏng (mạng chớp không phải việc hỏng). `ended(lỗi, kết quả)` báo một lần.
QtObject {
    id: root
    property var store: null
    property string bookId: ""
    property string kind: ""                // kiểu của hộp đang chạy: mp3 | m4b | abook | abookproj
    property string phase: "idle"           // idle | running
    property var job: ({})
    property bool cancelling: false
    property var music: null                // {active, done, total}: máy đang tải nhạc nền lúc gói
    property int chapters: 0                // số chương hộp nói trước (cho dòng "N chương · đã 0:35")
    property string countText: ""
    readonly property bool running: phase === "running"
    readonly property var view: running
        ? Logic.busyView(kind, job, {chapters: chapters, countText: countText, downloading: music && music.active ? music : null, cancelling: cancelling})
        : ({title: "", note: "", fraction: -1})
    signal ended(string error, var result)

    property var onEnd: null
    property bool asking: false
    property int misses: 0
    property int generation: 0

    property Timer ticker: Timer {
        interval: 1000
        repeat: true
        running: root.running && root.store !== null && root.store.active
        onTriggered: root.tick()
    }

    function request(method, path, body, done) { return store.request(method, path, body, done) }
    function reset() { generation++; phase = "idle"; cancelling = false; job = ({}); music = null; asking = false; onEnd = null }

    // Theo việc tới khi xong; `done(lỗi, kết quả)`
    function follow(done) {
        onEnd = done
        misses = 0
        asking = false
        phase = "running"
        tick()
    }
    function finish(error, result) {
        generation++
        phase = "idle"
        cancelling = false
        job = ({})
        music = null
        asking = false
        onEnd = null
        ended(error || "", result || null)
    }
    // Bắt đầu một lượt xuất (hay `attach`: theo việc ĐÃ chạy ở máy chủ); hộp thấy "đang xuất" ngay, trước cả lúc máy chủ trả lời lệnh bắt đầu
    function start(chosen, body, attach) {
        reset()
        kind = chosen
        phase = "running"
        const path = Logic.jobPath(chosen, bookId)
        const done = function(error, result) { root.finish(error, result) }
        if (chosen === "abook") Logic.packBookFile(root.request, bookId, body, root.follow, attach, done)
        else Logic.startJob(root.request, path, body, root.follow, attach, done)
    }
    function tick() {
        if (!running || asking || !store) return
        asking = true
        const mine = generation
        request("GET", Logic.jobPath(kind, bookId), null, function(status, data) {
            if (mine !== root.generation) return
            root.asking = false
            if (!store.ok(status) || !data) {
                if (++root.misses >= 5) root.finishWith(store.errorText(status, data))
                return
            }
            root.misses = 0
            const step = Logic.followStep(data)
            if (step.state === "running") { root.job = data; root.askMusic(); return }
            if (step.state === "cancelled") root.finishWith(Logic.CANCELLED)
            else if (step.state === "error") root.finishWith(step.error)
            else root.finishWith("", step.result)
        })
    }
    function finishWith(error, result) { const done = onEnd; if (done) done(error, result); else finish(error, result) }
    // Gói .abook / .abookproj: máy có thể đang TẢI nhạc nền (vài phút) - hỏi để nói bài thứ mấy; trạng thái nhạc có khoá riêng theo kiểu xuất
    function askMusic() {
        if (kind !== "abook" && kind !== "abookproj") return
        const mine = generation
        store.quiet("GET", "/api/books/" + bookId + "/music-export" + Logic.musicKind(kind), null, function(data, error) {
            if (mine === root.generation && !error) root.music = data
        })
    }
    function cancel() {
        if (!running || cancelling) return
        cancelling = true
        request("POST", Logic.jobPath(kind, bookId) + "/cancel", {}, function(status) { if (!store.ok(status)) root.cancelling = false })
    }
    // Mở hộp lúc máy chủ đang xuất cuốn này (mở lại app, hay hộp bị đóng giữa chừng): theo tiếp thay vì cho bấm xuất lần nữa. `found(kiểu)` khi có.
    function attachRunning(found) {
        if (running || !store) return
        const mine = generation
        store.quiet("GET", "/api/export-jobs", null, function(all, error) {
            if (mine !== root.generation || error || root.running) return
            const attached = Logic.runningKind(all, root.bookId)
            if (!attached) return
            if (found) found(attached)
            root.start(attached, null, true)
        })
    }
}
