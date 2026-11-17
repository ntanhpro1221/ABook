import "UiStrings.js" as S
import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Popover {
    id: root
    property bool resumeAfter: false
    readonly property var currentVoice: VoiceLogic.resolveVoice(Api.voiceList, Player.voiceId)
    signal settingsRequested()
    panelWidth: 400
    function fromAlert() { resumeAfter = true; show() }
    function focusVoice(index) {
        const count = choices.count
        if (count) choices.itemAt((index + count) % count).radio.forceActiveFocus(Qt.TabFocusReason)
    }
    onOpenChanged: { if (open) Api.loadVoiceName(); else { resumeAfter = false; consent.dismiss(); samples.stopSample() } }
    Listen { target: Player; function onLoadedChanged() { if (!Player.loaded) root.close() } }
    Column {
        width: parent.width; spacing: Theme.s8
        Text { width: parent.width; text: S.s_giong_doc_u00a0_u00a0nho_rieng_cho_cuon_na_ae337d03; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        Repeater {
            id: choices
            model: Api.voiceList
            VoiceRow {
                required property var modelData
                required property int index
                objectName: "playerVoice_" + modelData.id
                width: parent.width
                voice: modelData
                shown: VoiceLogic.spokenVoiceName(modelData.name)
                selected: root.currentVoice !== undefined && root.currentVoice.id === modelData.id
                first: true
                tabbable: selected
                playing: samples.playing === modelData.id
                loading: samples.loading === modelData.id
                failure: samples.failedVoice === modelData.id ? samples.failedMessage : ""
                onSample: playing ? samples.stopSample() : samples.playSample(modelData.id)
                onStep: direction => root.focusVoice(index + direction)
                onJump: end => root.focusVoice(end ? choices.count - 1 : 0)
                onChoose: {
                    const resume = root.resumeAfter
                    consent.ask(modelData, function(picked) { if (picked) { Player.chooseVoice(picked.id, resume); root.close() } })
                }
            }
        }
        InlineActionRow { objectName: "playerVoiceAdd"; width: parent.width; text: S.s_them_giong_15d3a618; onClicked: { root.close(); root.settingsRequested() } }
    }
    VoiceSample { id: samples }
    PlayerConsent { id: consent; parent: root.parent }
}
