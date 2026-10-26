import QtQuick
import QtQuick.Dialogs
import ABook
SectionBlock {
    id: root
    title: "Nhạc của tôi"
    fold: "wip"
    property var view: ({tracks: []})
    property bool busy: false
    property string removing: ""
    property int done: 0
    property int total: 0
    function load() { Api.call("GET", "/api/music/local", null, function(data, error) { if (!error) root.view = data }) }
    function act(path, body, method) { busy = true; Api.call(method || "POST", path, body, function(data, error) { root.busy = false; if (!error) { root.view = data; root.removing = "" } }) }
    function importNext(paths, at) {
        if (at >= paths.length) { busy = false; return }
        done = at; total = paths.length
        Api.call("POST", "/api/music/local/import", {paths: [DesktopApi.localPath(paths[at])]}, function(data, error) { if (error) { root.busy = false; return } root.view = data; root.done = at + 1; root.importNext(paths, at + 1) })
    }
    onVisibleChanged: if (visible) load()
    Timer { interval: 1000; running: root.visible && Boolean(root.view.module?.state === "downloading" || root.view.module?.analysing); repeat: true; onTriggered: root.load() }
    Button { text: root.busy ? "Đang thêm " + root.done + "/" + root.total : "Thêm nhạc của bạn"; icon: "upload"; kind: "text"; enabled: !root.busy; onClicked: files.open() }
    FormLabel { width: parent.width; text: "Thêm nhạc làm nền; bài đã chọn đi cùng file sách."; color: Theme.text2 }
    SectionBlock { width: parent.width; title: "Nhạc riêng"; fold: "wip"; FormLabel { width: parent.width; text: "Nhạc được chép vào kho máy này; dùng Đổi bài để chọn cho từng đoạn. Hỗ trợ mp3, m4a, ogg, opus, flac, wav. Bài đã chọn đi cùng .abook / .abookproj, vẫn nghe được trên máy khác, không ai khác tải được. Tên bài và nghệ sĩ lấy từ file; ABook không xác nhận giấy phép."; color: Theme.text2 } }
    FormLabel { width: parent.width; text: "Chưa có bài nào"; visible: !(root.view.tracks || []).length; color: Theme.text2 }
    SectionBlock {
        width: parent.width; title: "Phân tích nhạc"; fold: "wip"; visible: Boolean(root.view.module)
        FormLabel { width: parent.width; text: root.view.module?.error || "Tải một lần, phân tích trên máy rồi dùng không cần mạng. Chưa tải vẫn nhập, nghe và ghim nhạc bằng tay."; color: Theme.text2 }
        Button { text: root.view.module?.state === "downloading" ? "Huỷ" : "Tải"; kind: "text"; enabled: !root.busy; onClicked: root.act(root.view.module?.state === "downloading" ? "/api/music/local/module/cancel" : "/api/music/local/module", {}) }
        SettingRow { width: parent.width; visible: root.view.module?.precise?.state !== "unavailable"; label: "Đo cảm xúc nhạc chính xác hơn"; Switch { label: "Đo cảm xúc nhạc chính xác hơn"; checked: Boolean(root.view.module?.precise?.enabled); onToggled: value => root.act("/api/music/local/precise", {enabled: value}) } }
    }
    Repeater {
        model: root.view.tracks || []
        Column {
            required property var modelData
            width: parent.width
            SettingRow { width: parent.width; label: modelData.title + (modelData.creator ? " · " + modelData.creator : ""); hint: modelData.auto === "off" ? "Máy không tự chọn bài này" : modelData.vocalsLikely ? "Có vẻ có lời" : modelData.analysed ? "" : "Chưa phân tích"; Button { text: root.removing === modelData.link ? "Xoá bài" : "Xoá"; kind: "text"; icon: "trash-2"; enabled: !root.busy; onClicked: { if (root.removing === modelData.link) root.act("/api/music/local/" + modelData.link.replace(/^local:/, ""), null, "DELETE"); else root.removing = modelData.link } } }
            Button { text: "Giữ lại"; kind: "text"; visible: root.removing === modelData.link; onClicked: root.removing = "" }
            Button { text: modelData.auto === "off" ? "Cho tự chọn" : "Không tự chọn"; kind: "text"; enabled: !root.busy; onClicked: root.act("/api/music/local/" + modelData.link.replace(/^local:/, "") + "/auto", {auto: modelData.auto === "off" ? "on" : "off"}) }
        }
    }
    FileDialog { id: files; title: "Chọn nhạc của bạn"; fileMode: FileDialog.OpenFiles; nameFilters: ["Nhạc (*.mp3 *.m4a *.ogg *.opus *.flac *.wav)"]; onAccepted: { root.busy = true; root.importNext(selectedFiles, 0) } }
}
