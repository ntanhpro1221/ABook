import "UiStrings.js" as S
pragma Singleton
import QtQuick

// Trình phát clip ngắn (ClipProvider của listen/clip.tsx): nghe thử câu mẫu của một nhân vật, giọng kể, giọng trong hộp "Đổi giọng".
// MỘT clip một lúc cho cả app: bấm clip khác thì clip trước dừng; bấm lại chính nó thì dừng. Đi đường nghe thử có sẵn (DesktopApi.preview, cũng là
// đường "Thử giọng" của Cài đặt) nên không chen vào bộ phát chương. Chương chỉ dừng khi clip THẬT SỰ ra tiếng (`started`): clip hỏng không làm
// sách im lặng. Không import ABook (singleton, như Api): bộ phát nghe thử lấy từ Api.transport.
// Đầu ra nghe thử dùng chung với VoiceSample (hộp giọng, Cài đặt): như VoiceSample, clip chỉ coi tín hiệu của đầu ra là của mình khi nó vừa giao
// clip cho đầu ra (`starting`); mẫu khác chiếm đầu ra thì clip rời "đang phát" mà không dừng mẫu ấy, không toast lỗi của mẫu ấy.
QtObject {
    id: root
    property string current: ""         // mã clip đang chạy (đang tải cũng tính), "" = không clip nào
    property real position: 0
    property real duration: 0
    property bool paused: false
    property bool music: current.indexOf("library:") === 0 || current.indexOf("music:") === 0
    function seek(seconds) { if (Api.transport && current !== "") { const target = Math.max(0, Math.min(duration, seconds)); Api.transport.seekPreview(target); position = target } }
    property var lastRequest: null
    function fail(message) {
        const retry = lastRequest
        stop()
        Api.toast(message, {action: {label: S.s_thu_lai_c58d068c, run: function() {
            if (retry) root.toggle(retry.id, retry.url, retry.start, retry.end, retry.gain)
        }}})
    }
    property Timer tick: Timer {
        interval: 200; repeat: true; running: root.current !== "" && !root.paused
        onTriggered: { if (!Api.transport) return; root.position = Api.transport.previewPosition(); root.duration = Api.transport.previewDuration(); if (root.span > 0 && root.position >= root.span) root.stop() }
    }
    property bool loading: false        // đã bấm, chưa ra tiếng
    property bool starting: false       // clip của mình vừa giao cho đầu ra (mở hay phát tiếp), previewStarted của nó chưa về
    property real span: 0               // giây của đoạn cần nghe trong file dài (0 = nghe cả file); hết đoạn thì dừng
    signal started()
    // `start` / `end` (giây): chỉ nghe đoạn ấy của file (ClipSource của bản web) - câu của chương đã ghép nghe đúng chỗ của nó
    function toggle(id, url, start, end, gain) {
        if (current === id) {
            if (!music) { stop(); return }
            paused = !paused
            loading = !paused
            if (paused) { loadingDeadline.stop(); starting = false; Api.transport.pausePreview() }
            else { loadingDeadline.restart(); starting = true; Api.transport.resumePreview() }
            return
        }
        if (!Api.transport) return
        stop()
        lastRequest = {id: id, url: url, start: start, end: end, gain: gain}
        const part = start !== undefined && start !== null && start >= 0
        span = end > start ? end : 0
        position = start || 0; duration = 0; paused = false
        current = id
        loading = true
        starting = true
        loadingDeadline.restart()
        if (part) Api.transport.previewFrom(url, start); else Api.transport.preview(url)
        Api.transport.previewVolume(gain === undefined ? 1 : gain)
    }
    function stop() {
        loadingDeadline.stop()
        if (Api.transport && current !== "") Api.transport.stopPreview()
        release()
    }
    // Rời "đang phát" mà không đụng đầu ra (nó đã hết, hỏng, hay đang phát mẫu của người khác).
    function release() {
        loadingDeadline.stop()
        current = ""
        loading = false
        paused = false
        starting = false
    }
    property Timer loadingDeadline: Timer { interval: 30000; onTriggered: root.fail(S.s_preview_timeout) }
    property var link: Connections {
        target: Api.transport
        ignoreUnknownSignals: true
        function onPreviewStarted() {
            if (root.current === "") return
            if (!root.starting) { root.release(); return } // mẫu khác vừa chiếm đầu ra
            root.starting = false
            root.loadingDeadline.stop(); root.loading = false; root.started()
        }
        function onPreviewBuffering(pending) {
            if (root.current === "" || root.paused) return
            root.loading = pending
            if (pending) root.loadingDeadline.restart(); else root.loadingDeadline.stop()
        }
        function onPreviewEnded() { if (root.current !== "" && !root.starting) root.release() }
        function onPreviewFailed(reason) {
            if (root.current === "") return
            // Hỏng khi clip đã phát (hay mẫu khác chiếm đầu ra rồi hỏng): rời "đang phát", không toast câu của clip này.
            if (!root.starting) { root.release(); return }
            const library = root.current.indexOf("library:") === 0
            root.fail(library ? S.s_chua_nghe_thu_duoc_luc_nay_58b11ef5 : S.s_chua_nghe_thu_duoc_cau_mau_nay_chua_co_ban_34bbd4d4)
        }
    }
}
