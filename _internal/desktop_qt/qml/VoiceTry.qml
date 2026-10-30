import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Nghe thử bằng câu của sách" (useVoiceTry của VoiceTry.tsx, webui/reading_preview.py `voice_preview`): máy thu thử một câu của chính nhân vật bằng giọng đang
// cân nhắc - đúng giọng sẽ áp, không ghi gì vào sách. MỘT chỗ làm việc ấy cho hộp "Giọng của …" (CastVoice) và hộp "Áp dụng" (ApplyChanges): nơi dùng giữ nút
// (CastSample, `asks`), còn đây giữ `asking` (khoá bản đang chờ máy thu), `said` (dòng máy đang làm gì / đã đọc câu nào / vì sao chưa nghe được) và `tried`
// (bản vừa phát theo `tag` của nút, để nút biết bản nào đang ra tiếng). Bản đã nghe trong phiên (Logic.heard) bấm lại là phát lại, không hỏi máy chủ.
QtObject {
    id: root
    property var store: null                // Studio: mọi lời gọi đi qua StudioStore (cả máy tính ghép); không có thì là trang sách của máy này
    property string bookId: ""
    property string asking: ""
    property var said: null                 // {text, status}
    property var tried: ({})
    property int generation: 0

    function quiet(method, path, body, done) { return store ? store.quiet(method, path, body, done) : Api.quiet(method, path, body, done) }
    function media(url) { return store ? store.path(url) : url }
    function key(request) { return (store && store.peer ? store.peer + ":" : "") + Logic.tryKey(bookId, request) }
    // Đóng hộp / đổi người: bỏ lời máy đang đợi và dòng cũ
    function reset() { generation++; asking = ""; said = null; tried = ({}) }
    function play(preview, voiceName, tag) {
        Clip.toggle(Logic.tryId(preview), media(preview.url))
        tried = Object.assign({}, tried, {[tag]: preview})
        said = {text: Logic.previewCaption(preview.text, voiceName), status: false}
    }
    // `request`: {character, preset | gender | avoid}; `tag`: khoá của nút; `fallback`: hàm phát câu mẫu chung của giọng khi người ấy chưa có câu nào (hay null)
    function ask(request, voiceName, tag, fallback) {
        const asked = key(request)
        const known = Logic.heard[asked]
        if (known) { play(known, voiceName, tag); return }
        Clip.stop()
        asking = asked
        said = {text: Logic.tryAsking(voiceName), status: true}
        const mine = generation
        quiet("POST", "/api/books/" + bookId + "/voice/preview", request, function(preview, error, detail) {
            if (mine !== root.generation) return
            root.asking = ""
            if (!error && preview) {
                Logic.heard[asked] = preview
                root.play(preview, voiceName, tag)
                return
            }
            const reason = detail ? detail.reason : undefined
            if (reason === "no-line" && fallback) {
                fallback()
                root.said = {text: Logic.NO_LINE, status: true}
                return
            }
            const why = Logic.refusalText(reason, error, Boolean(detail && detail.busyBook))
            root.said = {text: fallback ? why + " - nút ▶ vẫn nghe được câu mẫu chung của giọng" : why, status: true}
        })
    }
}
