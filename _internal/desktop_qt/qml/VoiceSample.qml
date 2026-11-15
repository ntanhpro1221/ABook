import QtQuick
import ABook
import "UiStrings.js" as S
import "VoiceLogic.js" as VoiceLogic

// Settings and player rows share preview identity and cancellation.
Item {
    id: root
    visible: false
    property string playing: ""
    property string loading: ""
    property string failedVoice: ""
    property string failedMessage: ""
    property int turn: 0
    function stopSample() {
        turn++
        DesktopApi.stopPreview()
        playEnd.stop()
        playing = ""
        loading = ""
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
            DesktopApi.preview(data.url)
            root.playing = id
            playEnd.interval = Math.max(500, (data.duration_ms || 8000) + 300)
            playEnd.restart()
        })
    }
    Timer { id: playEnd; onTriggered: root.playing = "" }
    Component.onDestruction: if (playing !== "" || loading !== "") DesktopApi.stopPreview()
}
