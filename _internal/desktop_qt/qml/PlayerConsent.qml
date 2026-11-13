import "UiStrings.js" as S
import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Modal {
    id: root
    property var voice: ({})
    property var answer: null
    property bool choosing: false
    title: choosing ? S.s_chon_giong_doc_a3941a79 : S.s_giong_doc_truc_tuyen_44ae53c1
    description: {
        const name = VoiceLogic.spokenVoiceName(voice.name || "")
        const keyed = VoiceLogic.KEYED[voice.provider]
        const where = keyed || (voice.provider === "edge" ? S.s_may_chu_microsoft_1e47d07c : S.s_dich_vu_ngoai_0bb5b472)
        if (keyed) return S.s_giong_0_dung_khoa_1_cua_ban_chu_cua_doan_d_005b3ec4(name, where, where)
        return S.s_giong_0_la_giong_1_chu_cua_doan_dang_doc_d_48efa5c3(name, voice.provider === "edge" ? S.s_edge_0f82fe72 : S.s_truc_tuyen_ada49667, where)
    }
    function allowed(provider) {
        try { return JSON.parse(Api.store("abook-readaloud-online-ok") || "[]").includes(provider) }
        catch (error) { return false }
    }
    function ask(item, done) {
        if (!item.online || allowed(item.provider)) { done(item); return }
        voice = item; answer = done; choosing = false; show()
    }
    function finish(item) {
        if (item && item.online) {
            let list = []
            try { list = JSON.parse(Api.store("abook-readaloud-online-ok") || "[]") } catch (error) {}
            if (!Array.isArray(list)) list = []
            if (!list.includes(item.provider)) Api.store("abook-readaloud-online-ok", JSON.stringify(list.concat([item.provider])))
        }
        const done = answer; answer = null; dismiss()
        if (done) done(item)
    }
    onClosed: { if (answer) { const done = answer; answer = null; done(null) } }
    Column {
        width: parent.width; spacing: Theme.s8
        Repeater {
            model: root.choosing ? Api.voiceList : []
            MenuRow {
                required property var modelData
                width: parent.width; text: VoiceLogic.spokenVoiceName(modelData.name)
                selected: root.voice.id === modelData.id; icon: selected ? "check" : ""
                onClicked: root.finish(modelData)
            }
        }
        Button { objectName: "consentOtherVoice"; Reveal { shown: !root.choosing } width: parent.width; wrap: true; kind: "ghost"; text: S.s_chon_giong_khac_d31cfe89; onClicked: root.choosing = true }
        Button { objectName: "consentListen"; Reveal { shown: !root.choosing } width: parent.width; text: S.s_nghe_a43aafef; onClicked: root.finish(root.voice) }
    }
}
