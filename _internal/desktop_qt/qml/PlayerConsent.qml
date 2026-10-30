import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

Modal {
    id: root
    property var voice: ({})
    property var answer: null
    property bool choosing: false
    title: choosing ? "Chọn giọng đọc" : "Giọng đọc trực tuyến"
    description: {
        const name = VoiceLogic.spokenVoiceName(voice.name || "")
        const keyed = VoiceLogic.KEYED[voice.provider]
        const where = keyed || (voice.provider === "edge" ? "máy chủ Microsoft" : "dịch vụ ngoài")
        if (keyed) return `Giọng ${name} dùng khoá ${where} của bạn: chữ của đoạn đang đọc được gửi tới ${where} để đọc, và dịch vụ có thể tính tiền vào tài khoản của bạn.`
        return `Giọng ${name} là giọng ${voice.provider === "edge" ? "Edge" : "trực tuyến"}: chữ của đoạn đang đọc được gửi tới ${where} để đọc.`
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
        Button { objectName: "consentOtherVoice"; visible: !root.choosing; width: parent.width; wrap: true; kind: "ghost"; text: "Chọn giọng khác"; onClicked: root.choosing = true }
        Button { objectName: "consentListen"; visible: !root.choosing; width: parent.width; text: "Nghe"; onClicked: root.finish(root.voice) }
    }
}
