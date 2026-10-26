import QtQuick
import ABook
Column {
    id: root
    property var voices: []
    property var providers: []
    property var speed: ({})
    property string problem: ""
    property string sample: ""
    property int ticket: 0
    readonly property var groups: [
        {provider: "edge", title: "Edge", detail: "trực tuyến, miễn phí"},
        {provider: "azure", title: "Azure Speech", detail: "dùng khóa của bạn"},
        {provider: "google", title: "Google Cloud", detail: "dùng khóa của bạn"},
        {provider: "fpt", title: "FPT.AI", detail: "dùng khóa của bạn"},
        {provider: "viettel", title: "Viettel AI", detail: "dùng khóa của bạn"},
        {provider: "vieneu", title: "VieNeu", detail: "trên máy này, không cần mạng"},
        {provider: "supertonic", title: "Supertonic", detail: "trên máy này, không cần mạng"},
        {provider: "device", title: "Giọng của máy", detail: "không cần mạng"}
    ]
    function load() {
        Api.call("GET", "/api/readaloud/voices", null, function(data, error) { if (!error) root.voices = data; root.problem = error || "" })
        Api.call("GET", "/api/readaloud/online", null, function(data, error) { if (!error) root.providers = data })
        Api.call("GET", "/api/readaloud/voice-speed", null, function(data, error) { if (!error) root.speed = data })
    }
    function stop() { ticket++; sample = ""; DesktopApi.stopPreview() }
    function tryVoice(voice) {
        if (sample === voice.id) { stop(); return }
        stop(); sample = voice.id
        const mine = ticket
        Api.call("POST", "/api/readaloud/clip", {voice: voice.id, text: "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?"}, function(data, error) {
            if (mine !== root.ticket || !root.visible) return
            if (!error && data.url) DesktopApi.preview(data.url)
            else root.sample = ""
        })
    }
    onVisibleChanged: { if (visible) load(); else stop() }
    Component.onDestruction: stop()
    FormLabel { width: parent.width; text: root.problem; visible: text !== ""; color: Theme.danger }
    Repeater {
        model: root.groups
        SectionBlock {
            id: group
            required property var modelData
            readonly property var listed: root.voices.filter(v => v.provider === modelData.provider)
            width: parent.width
            title: modelData.title
            fold: true
            expanded: modelData.provider === "edge"
            visible: listed.length > 0 || modelData.provider === "device"
            FormLabel { width: parent.width; text: group.modelData.detail; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            FormLabel { width: parent.width; visible: group.listed.length === 0; text: "Cài giọng tiếng Việt tại Cài đặt Windows › Thời gian và ngôn ngữ › Giọng nói."; color: Theme.text2 }
            Repeater {
                model: group.listed
                SettingRow {
                    required property var modelData
                    width: parent.width
                    label: modelData.name
                    hint: (modelData.gender === "female" ? "Nữ" : modelData.gender === "male" ? "Nam" : "") + (Api.preferences.readAloudVoice === modelData.id ? " · Mặc định" : "")
                    Row {
                        spacing: 4
                        IconButton { icon: Api.preferences.readAloudVoice === modelData.id ? "check" : "circle"; tip: "Mặc định"; enabled: !Api.saving; onClicked: Api.update({readAloudVoice: modelData.id}) }
                        Button { text: root.sample === modelData.id ? "Dừng" : "Thử giọng"; icon: root.sample === modelData.id ? "square" : "play"; kind: "text"; onClicked: root.tryVoice(modelData) }
                    }
                }
            }
            FormLabel { width: parent.width; visible: group.modelData.provider === "edge"; text: "Giọng Edge gửi chữ của sách tới máy chủ Microsoft để đọc."; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
    }
    SectionBlock {
        width: parent.width; title: "Bộ giọng"; fold: true
        VoiceModule { width: parent.width; module: "vieneu"; title: "Giọng VieNeu"; onChanged: root.load() }
        VoiceModule { width: parent.width; module: "supertonic"; title: "Giọng Supertonic"; onChanged: root.load() }
    }
    SectionBlock {
        width: parent.width; title: "Hiệu năng"; fold: true
        SettingChoices { width: parent.width; label: "Tốc độ đọc"; value: root.speed.choice || "auto"; options: [{value: "auto", label: "Tự động"}, {value: "quality", label: "Chất lượng cao nhất"}, {value: "fast", label: "Nhanh hơn"}]; onPicked: value => Api.call("POST", "/api/readaloud/voice-speed", {choice: value}, function(data, error) { if (!error) root.speed = data }) }
        FormLabel { width: parent.width; text: (root.speed.choice === "quality" ? "Luôn đọc bản hay nhất; máy chậm có thể phải chờ." : root.speed.choice === "fast" ? "Nhanh hơn, tiếng kém hơn chút - hợp máy yếu." : "Máy kịp thì đọc bản hay nhất.") + " Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất."; color: Theme.text2 }
    }
    SectionBlock {
        width: parent.width; title: "Khoá trực tuyến"; fold: true; visible: root.providers.length > 0
        FormLabel { width: parent.width; text: "Chữ của sách gửi tới dịch vụ ấy; có thể bị tính tiền."; color: Theme.text2 }
        SectionBlock { width: parent.width; title: "Tìm hiểu thêm"; fold: true; FormLabel { width: parent.width; text: "Khoá chỉ lưu trên máy. Dịch vụ có thể tính phí; lỗi khoá thì tạm dùng Edge hoặc giọng máy."; color: Theme.text2 } }
        Repeater { model: root.providers; ProviderKey { required property var modelData; width: parent.width; info: modelData; onChanged: root.load() } }
    }
}
