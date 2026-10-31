import QtQuick
import ABook
import "CastLogic.js" as Cast
import "ReviewLogic.js" as R

// "Nghe thử" một cách đọc trước khi lưu (TryReading.tsx, webui/reading_preview.py): máy thu thử một câu có tên ấy bằng đúng cách đang gõ, không ghi gì vào sách. Đây là
// phần trạng thái; TryButton là nút, TryNote là dòng nói máy đang làm gì. Clip đi qua Clip (MỘT clip một lúc, dừng bộ phát chương). Đã nghe đúng cách đọc này rồi thì bấm
// lại là phát lại, không hỏi máy chủ.
QtObject {
    id: root
    property var work: null
    property string surface: ""
    property string spoken: ""
    property bool blocked: false            // ô đang báo lỗi
    property bool pending: false
    property string refusal: ""
    property bool needsStudio: false
    property var heard: null                // {surface, spoken, preview: {url, text, speaker}}
    signal rejected(string message, string suggestion)

    readonly property bool same: heard !== null && heard.surface === surface && heard.spoken === spoken
    readonly property string clipId: heard ? "try-" + heard.preview.url : ""
    readonly property bool playing: same && Clip.current === clipId
    readonly property string note: R.tryNote({pending: pending, refusal: refusal, playing: playing,
                                              caption: same ? Cast.previewCaption(heard.preview.text, heard.preview.speaker) : null, bookBusy: !!work && work.live}) || ""
    readonly property bool warns: refusal !== "" && !pending
    readonly property bool offersStudio: needsStudio && refusal !== "" && !!work && !!work.store && !work.store.remote && work.store.studioState.missing
    onSpokenChanged: { refusal = ""; needsStudio = false }

    function play(preview) { Clip.toggle("try-" + preview.url, work.store.path(preview.url)) }
    function press() {
        refusal = ""
        needsStudio = false
        if (same) play(heard.preview)
        else ask()
    }
    function ask() {
        if (!work || pending) return
        pending = true
        const asked = {surface: surface, spoken: spoken}
        work.post("/pronunciation/preview", {surface: asked.surface, spokenForm: asked.spoken}, function(status, data) {
            root.pending = false
            if (work.ok(status) && data) { root.heard = {surface: asked.surface, spoken: asked.spoken, preview: data}; root.play(data); return }
            const message = work.store.errorText(status, data)
            if (status === 400) { root.rejected(message, work.suggestionOf(data)); return }
            const reason = data ? data.reason : undefined
            const named = Boolean(data && data.busyBook)
            root.needsStudio = reason === "studio"
            const why = Cast.refusalText(reason, message, named)
            root.refusal = why === message && !named ? "Chưa nghe thử được - " + why : why
        })
    }
}
