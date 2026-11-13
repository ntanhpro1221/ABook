import "UiStrings.js" as S
import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Popover {
    id: root
    property bool resumeAfter: false
    signal settingsRequested()
    panelWidth: 320
    function fromAlert() { resumeAfter = true; show() }
    onOpenChanged: { if (open) Api.loadVoiceName(); else { resumeAfter = false; consent.dismiss() } }
    Connections { target: Player; function onLoadedChanged() { if (!Player.loaded) root.close() } }
    Column {
        width: parent.width; spacing: Theme.s8
        Text { width: parent.width; text: S.s_giong_doc_u00a0_u00a0nho_rieng_cho_cuon_na_ae337d03; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        Repeater {
            model: Api.voiceList
            MenuRow {
                required property var modelData
                objectName: "playerVoice_" + modelData.id
                width: parent.width; text: VoiceLogic.spokenVoiceName(modelData.name)
                selected: Player.voiceId === modelData.id || !Player.voiceId && modelData.default === true
                icon: selected ? "check" : ""
                onClicked: {
                    const resume = root.resumeAfter
                    consent.ask(modelData, function(picked) { if (picked) { Player.chooseVoice(picked.id, resume); root.close() } })
                }
            }
        }
        Button { width: parent.width; wrap: true; text: S.s_them_giong_15d3a618; icon: "plus"; kind: "ghost"; onClicked: { root.close(); root.settingsRequested() } }
    }
    PlayerConsent { id: consent; parent: root.parent }
}
