import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Collapse {
    id: root
    property var voices: Api.voiceList
    property var current: voices.find(v => v.id === Player.voiceId) || voices.find(v => v.default) || voices[0]
    readonly property bool stuck: Player.error.startsWith("Không có mạng - ") || /^Giọng .+ đang không dùng được\.$/.test(Player.error)
    readonly property var local: voices.filter(v => !v.online && v.provider !== "device").find(v => current && v.gender === current.gender)
        || voices.find(v => !v.online && v.provider !== "device")
    signal voiceRequested()
    signal settingsRequested()
    open: Player.error !== ""
    Column {
        width: parent.width; spacing: Theme.s8
        Item {
            width: parent.width; height: Math.max(message.implicitHeight, close.height)
            Icon { name: "triangle-alert"; size: 16; y: 6; color: Theme.danger }
            Text {
                id: message; objectName: "playerErrorText"; x: 24; width: Math.max(0, parent.width - x - close.width)
                text: root.stuck && root.current ? Player.error.startsWith("Không có mạng - ")
                    ? `Không có mạng - giọng ${VoiceLogic.spokenVoiceName(root.current.name)} cần mạng.`
                    : `Giọng ${VoiceLogic.spokenVoiceName(root.current.name)} đang không dùng được.` : Player.error
                wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; Accessible.role: Accessible.AlertMessage
            }
            IconButton { id: close; objectName: "playerErrorClose"; anchors.right: parent.right; icon: "x"; tip: "Đóng lời báo"; onClicked: Player.dismissError() }
        }
        Flow {
            width: parent.width; spacing: Theme.s4
            Button { objectName: "playerLocalVoice"; visible: root.stuck && !!root.local; text: "Đọc bằng " + (root.local ? VoiceLogic.spokenVoiceName(root.local.name) : ""); kind: "ghost"; wrap: true; width: Math.min(implicitWidth, parent.width); onClicked: Player.chooseVoice(root.local.id, true) }
            Button { objectName: "playerRetry"; text: "Thử lại"; kind: "ghost"; onClicked: Player.retry() }
            Button { objectName: "playerOtherVoice"; visible: root.stuck && root.voices.length > 0; text: "Chọn giọng khác"; kind: "ghost"; onClicked: root.voiceRequested() }
            Button { visible: root.stuck && !root.local; text: "Tải giọng VieNeu"; kind: "ghost"; onClicked: root.settingsRequested() }
        }
    }
}
