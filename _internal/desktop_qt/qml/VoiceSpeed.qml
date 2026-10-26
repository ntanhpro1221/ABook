import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

// Mục "Hiệu năng" (VoiceSpeedSetting.tsx): "Tốc độ đọc" Tự động / Chất lượng cao nhất / Nhanh hơn, một lựa chọn cho cả máy; dưới đó mỗi giọng có hai bậc (Supertonic)
// nói đang dùng bậc nào và vì sao. Muốn bậc nhanh mà chưa có bản nhanh hơn: nút tải kèm cỡ (tải qua thẻ Supertonic nên tiến độ hiện ở thẻ ấy).
VoiceFold {
    id: root
    property var status: ({})
    property var supertonic: null               // thẻ VoiceModule của Supertonic
    property bool busy: false
    readonly property bool ready: status.choice !== undefined && Array.isArray(status.voices)
    storageKey: "voice.performance"
    title: "Hiệu năng"
    summary: ready ? VoiceLogic.speedLabel(status.choice) : ""

    function refresh() {
        Api.quiet("GET", "/api/readaloud/voice-speed", null, function(data, error) { if (!error && data) root.status = data })
    }
    function choose(choice) {
        if (busy) return
        busy = true
        Api.quiet("POST", "/api/readaloud/voice-speed", {choice: choice}, function(data, error) {
            root.busy = false
            if (error) { Api.notice = "Chưa đổi được tốc độ giọng\n" + error; return }
            root.status = data
            // Thẻ mô-đun mời / thôi mời tải bản nhanh hơn theo lựa chọn mới
            if (root.supertonic) root.supertonic.refresh()
        })
    }
    Component.onCompleted: refresh()
    // Thẻ Supertonic tải / đo xong: số đo hay bản nhanh hơn vừa đổi - hỏi lại dòng này
    Connections { target: root.supertonic; function onChanged() { root.refresh() } }

    Column {
        width: parent.width
        spacing: 8
        Text {
            width: parent.width
            text: VoiceLogic.SPEED_TITLE
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
            font.weight: 600
        }
        ChoiceRow {
            objectName: "voiceSpeedChoice"
            width: parent.width
            label: VoiceLogic.SPEED_TITLE
            options: VoiceLogic.SPEED_OPTIONS
            value: root.ready ? root.status.choice : ""      // "" lúc chưa có số liệu: gạch chân của hàng chọn dựng lại khi có giá trị
            onPicked: value => root.choose(value)
        }
        Text {
            width: parent.width
            text: VoiceLogic.speedDescription(root.status.choice || "auto")
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: 13
        }
        Column {
            width: parent.width
            spacing: 6
            Repeater {
                model: root.ready ? root.status.voices.length : 0
                Item {
                    id: line
                    required property int index
                    readonly property var voice: root.status.voices[index] || ({})
                    readonly property bool wants: VoiceLogic.needsFastDownload(voice)
                    width: parent.width
                    height: Math.max(sentence.height, download.visible ? download.implicitHeight : 0)
                    Text {
                        id: sentence
                        width: line.wants ? parent.width - download.width - 12 : parent.width
                        anchors.verticalCenter: parent.verticalCenter
                        text: VoiceLogic.speedLine(line.voice, root.status.choice)
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                    }
                    Button {
                        id: download
                        objectName: "voiceSpeedDownload"
                        visible: line.wants
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        size: "sm"
                        kind: "text"
                        text: "Tải (" + VoiceLogic.formatSize(line.voice.fastBytes || 0) + ")"
                        busy: root.supertonic !== null && root.supertonic.downloading
                        enabled: root.supertonic !== null && !root.supertonic.working
                        onActivated: root.supertonic.start([line.voice.fastChoice], "Chưa tải được bản nhanh hơn")
                    }
                }
            }
        }
    }
}
