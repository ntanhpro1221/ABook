import QtQuick
import ABook
Column {
    id: root
    property string bookId: ""
    property string query: ""
    property var results: []
    property var failed: []
    property bool busy: false
    property bool choosing: false
    property string problem: ""
    property int generation: 0
    property int requestId: 0
    spacing: 12
    signal chosen()
    signal chooseFile()
    function begin(id, title) { cancel(); bookId = id; query = title; results = []; failed = []; problem = ""; search() }
    function cancel() { generation++; if (requestId) DesktopApi.cancel(requestId); requestId = 0; busy = false; choosing = false }
    function search() {
        cancel(); busy = true; problem = ""
        const mine = generation
        requestId = Api.call("GET", "/api/books/" + bookId + "/cover/search?q=" + encodeURIComponent(query), null, function(data, error) {
            if (mine !== root.generation) return
            root.requestId = 0; root.busy = false
            if (error) { root.problem = "Bạn hãy kiểm tra kết nối rồi tìm lại ảnh bìa."; return }
            root.results = data.results || []; root.failed = data.failed || []
        }) || 0
    }
    function choose(found) {
        choosing = true; problem = ""
        const mine = generation
        requestId = Api.call("PUT", "/api/books/" + bookId + "/cover", {url: found.url}, function(data, error) {
            if (mine !== root.generation) return
            root.requestId = 0; root.choosing = false
            if (error) { root.problem = "Bạn hãy kiểm tra kết nối rồi đặt lại ảnh bìa."; return }
            root.chosen()
        }) || 0
    }
    FormField { objectName: "coverQuery"; width: parent.width; label: "Tên sách để tìm bìa"; placeholderText: "Tên sách (tiếng Anh thường cho nhiều kết quả hơn)"; text: root.query; onTextChanged: root.query = text; onAccepted: root.search() }
    Button { text: "Tìm"; icon: "search"; enabled: !root.busy && !root.choosing; onClicked: root.search() }
    FormLabel { width: parent.width; text: "Đang tìm ảnh bìa"; visible: root.busy; color: Theme.text2 }
    Flow {
        width: parent.width; spacing: 12
        Repeater {
            model: root.results
            Interactive {
                required property var modelData
                width: Math.max(120, (root.width - 24) / 3)
                height: photo.height + caption.height + provider.height + 16
                enabled: !root.choosing
                visible: photo.status !== Image.Error
                Accessible.name: modelData.title + (modelData.author ? " - " + modelData.author : "") + " (" + modelData.provider + ")"
                onClicked: root.choose(modelData)
                Image { id: photo; width: parent.width; height: width * 1.5; source: modelData.thumb; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                FormLabel { id: caption; y: photo.height + 6; width: parent.width; text: modelData.title; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
                FormLabel { id: provider; y: caption.y + caption.height + 2; width: parent.width; text: modelData.provider; color: Theme.text3; font.pixelSize: 11 }
            }
        }
    }
    FormLabel { width: parent.width; text: root.problem || (root.failed.length ? "Bạn hãy kiểm tra kết nối rồi tìm lại các nguồn bìa." : ""); visible: text !== ""; color: Theme.danger }
    FormLabel { width: parent.width; visible: !root.busy && !root.results.length && !root.failed.length; text: "Bạn hãy chọn ảnh trên máy"; color: Theme.text2 }
    Button { text: "Chọn ảnh"; kind: "text"; visible: !root.busy && !root.results.length; onClicked: root.chooseFile() }
}
