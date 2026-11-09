import "UiStrings.js" as S
import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Collapse {
    id: root
    property var voices: Api.voiceList
    property var current: voices.find(v => v.id === Player.voiceId) || voices.find(v => v.default) || voices[0]
    readonly property bool stuck: Player.error.startsWith(S.s_khong_co_mang_5485dfea) || /^Giọng .+ đang không dùng được\.$/.test(Player.error)
    readonly property var local: voices.filter(v => !v.online && v.provider !== "device").find(v => current && v.gender === current.gender)
        || voices.find(v => !v.online && v.provider !== "device")
    signal voiceRequested()
    signal settingsRequested()
    open: Player.error !== ""
    Column {
        width: parent.width; spacing: Theme.s8
        Item {
            width: parent.width; height: Math.max(message.y + message.implicitHeight, close.height)
            // Tam giác, dòng chữ ĐẦU và nút ✕ cùng một tâm dọc (máy dò IconText); câu dài xuống dòng bên dưới
            readonly property real firstLine: message.implicitHeight / Math.max(1, message.lineCount)
            Icon { objectName: "playerErrorIcon"; name: "triangle-alert"; size: 16; y: (close.height - size) / 2; color: Theme.danger }
            Text {
                id: message; objectName: "playerErrorText"; x: 24; y: Math.max(0, (close.height - parent.firstLine) / 2); width: Math.max(0, parent.width - x - close.width)
                text: root.stuck && root.current ? Player.error.startsWith(S.s_khong_co_mang_5485dfea)
                    ? S.s_khong_co_mang_giong_0_can_mang_9eb86c71(VoiceLogic.spokenVoiceName(root.current.name))
                    : S.s_giong_0_dang_khong_dung_duoc_65353328(VoiceLogic.spokenVoiceName(root.current.name)) : Player.error
                wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; Accessible.role: Accessible.AlertMessage
            }
            IconButton { id: close; objectName: "playerErrorClose"; anchors.right: parent.right; icon: "x"; tip: S.s_dong_loi_bao_d13d19ff; onClicked: Player.dismissError() }
        }
        Flow {
            width: parent.width; spacing: Theme.s4
            Button { objectName: "playerLocalVoice"; visible: root.stuck && !!root.local; text: S.s_doc_bang_f7f5f3b1 + (root.local ? VoiceLogic.spokenVoiceName(root.local.name) : ""); kind: "ghost"; wrap: true; width: Math.min(implicitWidth, parent.width); onClicked: Player.chooseVoice(root.local.id, true) }
            Button { objectName: "playerRetry"; text: S.s_thu_lai_c58d068c; kind: "ghost"; onClicked: Player.retry() }
            Button { objectName: "playerOtherVoice"; visible: root.stuck && root.voices.length > 0; text: S.s_chon_giong_khac_d31cfe89; kind: "ghost"; onClicked: root.voiceRequested() }
            Button { visible: root.stuck && !root.local; text: S.s_tai_giong_vieneu_94c86884; kind: "ghost"; onClicked: root.settingsRequested() }
        }
    }
}
