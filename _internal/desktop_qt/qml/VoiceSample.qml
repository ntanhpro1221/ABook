import QtQuick
import ABook
import "UiStrings.js" as S
import "VoiceLogic.js" as VoiceLogic

// Settings and player rows share preview identity and cancellation. One preview output serves every sample on screen: a
// sample stops it only while it is its own, and a row shows "Dừng" only while its clip really plays - another sample or
// preview taking the output, its end, or a failure puts the row back to "Nghe thử".
Item {
    id: root
    visible: false
    property string playing: ""
    property string loading: ""
    property string failedVoice: ""
    property string failedMessage: ""
    property int turn: 0
    property bool starting: false   // our clip was handed to the output and its previewStarted has not come back yet
    function stopSample() {
        turn++
        if (playing !== "" || loading !== "") DesktopApi.stopPreview()
        release()
        loading = ""
    }
    function release() {
        playEnd.stop()
        starting = false
        playing = ""
    }
    function playSample(id) {
        stopSample()
        const mine = turn
        failedVoice = ""
        failedMessage = ""
        loading = id
        Api.quiet("POST", "/api/readaloud/clip", {voice: id, text: VoiceLogic.SAMPLE_TEXT}, function(data, error) {
            if (root.turn !== mine) return
            root.loading = ""
            if (error || !data || !data.url) {
                root.failedVoice = id
                root.failedMessage = error || S.s_chua_lam_duoc_luc_nay_2e7cacde
                return
            }
            root.starting = true
            DesktopApi.preview(data.url)
            root.playing = id
            playEnd.interval = Math.max(500, (data.duration_ms || 8000) + 300)
            playEnd.restart()
        })
    }
    Timer { id: playEnd; onTriggered: root.playing = "" }
    Listen {
        target: DesktopApi
        function onPreviewStarted() { if (root.starting) root.starting = false; else if (root.playing !== "") root.release() }
        function onPreviewEnded() { if (root.playing !== "" && !root.starting) root.release() }
        function onPreviewFailed(reason) { if (root.playing !== "") root.release() }
    }
    Component.onDestruction: if (playing !== "" || loading !== "") DesktopApi.stopPreview()
}
