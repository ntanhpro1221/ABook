pragma Singleton
import QtQuick
QtObject {
    property var requests: []
    property var responses: ({})
    property var pending: []
    property int nextRequest: 0
    property string thirdParty: "Qt Quick"
    property bool delayed: false
    // Nghe thử (câu mẫu của nhân vật, giọng): đường đã mở và số lần dừng; ba tín hiệu như DesktopApi thật
    property var previews: []
    property var starts: []                 // giây bắt đầu của mỗi lần nghe một đoạn (previewFrom)
    property int stops: 0
    signal previewStarted()
    signal previewBuffering(bool pending)
    signal requestStarted(int id)
    signal requestFinished(int id, int status)
    signal previewEnded()
    signal previewFailed(string reason)
    function reset() { for (const job of pending) requestFinished(job.requestId, 0); requests = []; responses = {}; pending = []; delayed = false; previews = []; starts = []; stops = 0; sources = []; read = []; pickers = []; folders = []; folderAnswer = "D:/Đã xuất" }
    function request(method, path, body, done) {
        const id = ++nextRequest
        requestStarted(id)
        requests = requests.concat([{method: method, path: path, body: body}])
        // Đáp giả: "PUT /api/x" (theo cách gọi) trước, rồi "/api/x"; đáp là hàm thì gọi với (body, method).
        let response = responses[method + " " + path] || responses[path] || {status: 200, data: path === "/api/preferences" ? (method === "PUT" ? body : {theme: "system"}) : path === "/api/app" ? {version: "fixture"} : /voices$|online$/.test(path) ? [] : {}}
        if (typeof response === "function") response = response(body, method)
        const complete = function() { requestFinished(id, response.status); done(response.status, response.data) }
        complete.requestId = id
        if (delayed) pending = pending.concat([complete])
        else complete()
        return id
    }
    function finish() { const jobs = pending; pending = []; for (const job of jobs) job() }
    function cancel(id) { const found = pending.some(job => job.requestId === id); pending = pending.filter(job => job.requestId !== id); if (found) requestFinished(id, 0) }
    function localPath(url) { return String(url).replace(/^file:\/\//, "") }
    function mediaUrl(path) { return path }
    function refreshLibrary() {}
    function preview(path) { previews = previews.concat([path]); starts = starts.concat([0]) }
    function previewFrom(path, start) { previews = previews.concat([path]); starts = starts.concat([start]) }
    function stopPreview() { stops++ }
    property real musicPosition: 0
    property real musicDuration: 180
    function previewPosition() { return musicPosition }
    function previewDuration() { return musicDuration }
    function seekPreview(seconds) { musicPosition = seconds }
    function previewVolume(volume) {}
    function pausePreview() {}
    function resumePreview() { previewStarted() }
    function imageData(file) { return "data:image/png;base64,fixture" }
    property string clipboard: ""            // ảnh trong bộ nhớ tạm giả (data URL), "" = không có
    function clipboardImage() { return clipboard }
    // Gửi chương lên máy khác: kể file/thư mục đã chọn (`sources` do test đặt, mỗi phần tử {name, size, path, local}) và byte giả
    property var sources: []
    property var read: []
    property var pickers: []                // lần mở hộp chọn file giả của trình tạo sách (NewPicker giả)
    property var folders: []                // lần mở hộp chọn thư mục giả (NativeFolders giả): {title, start}
    property string folderAnswer: "D:/Đã xuất"   // thư mục hộp giả "chọn"; rỗng = người dùng đóng hộp mà không chọn
    function sourceFiles(paths) { return sources }
    function fileBase64(local) { read = read.concat([local]); return "ZmFrZQ==" }
}
