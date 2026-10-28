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
    signal started()
    function toggle(id, url) {
        if (current === id) { stop(); return }
        if (!Api.transport) return
        Api.transport.preview(url)
        current = id
        loading = true
    }
    function stop() {
        if (Api.transport && current !== "") Api.transport.stopPreview()
        current = ""
        loading = false
    }
    property var link: Connections {
        target: Api.transport
        ignoreUnknownSignals: true
        function onPreviewStarted() { if (root.current !== "" && root.loading) { root.loading = false; root.started() } }
        function onPreviewEnded() { root.current = ""; root.loading = false }
        function onPreviewFailed(reason) {
            if (root.current === "") return
            root.current = ""
            root.loading = false
            Api.notice = "Chưa nghe thử được\nCâu mẫu này chưa có bản thu."
        }
    }
}
