pragma Singleton
import QtQuick

// Trình phát clip ngắn (ClipProvider của listen/clip.tsx): nghe thử câu mẫu của một nhân vật, giọng kể, giọng trong hộp "Đổi giọng".
// MỘT clip một lúc cho cả app: bấm clip khác thì clip trước dừng; bấm lại chính nó thì dừng. Đi đường nghe thử có sẵn (DesktopApi.preview, cũng là
// đường "Thử giọng" của Cài đặt) nên không chen vào bộ phát chương. Chương chỉ dừng khi clip THẬT SỰ ra tiếng (`started`): clip hỏng không làm
// sách im lặng. Không import ABook (singleton, như Api): bộ phát nghe thử lấy từ Api.transport.
QtObject {
    id: root
    property string current: ""         // mã clip đang chạy (đang tải cũng tính), "" = không clip nào
    property bool loading: false        // đã bấm, chưa ra tiếng
    property real span: 0               // giây của đoạn cần nghe trong file dài (0 = nghe cả file); hết đoạn thì dừng
    signal started()
    // `start` / `end` (giây): chỉ nghe đoạn ấy của file (ClipSource của bản web) - câu của chương đã ghép nghe đúng chỗ của nó
    function toggle(id, url, start, end) {
        if (current === id) { stop(); return }
        if (!Api.transport) return
        const part = start !== undefined && start !== null && end > start
        if (part) Api.transport.previewFrom(url, start); else Api.transport.preview(url)
        span = part ? end - start : 0
        current = id
        loading = true
    }
    function stop() {
        stopper.stop()
        if (Api.transport && current !== "") Api.transport.stopPreview()
        current = ""
        loading = false
    }
    property Timer stopper: Timer { onTriggered: root.stop() }
    property var link: Connections {
        target: Api.transport
        ignoreUnknownSignals: true
        function onPreviewStarted() { if (root.current !== "" && root.loading) { root.loading = false; root.started(); if (root.span > 0) { stopper.interval = root.span * 1000; stopper.restart() } } }
        function onPreviewEnded() { stopper.stop(); root.current = ""; root.loading = false }
        function onPreviewFailed(reason) {
            if (root.current === "") return
            root.current = ""
            root.loading = false
            Api.notice = "Chưa nghe thử được\nCâu mẫu này chưa có bản thu."
        }
    }
}
