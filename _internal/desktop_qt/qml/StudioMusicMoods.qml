import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic

// "Nhạc theo ngữ cảnh" (MoodsPanel của MusicTab.tsx): model nhỏ (tuỳ chọn, tải khi bấm) đọc nguyên đoạn để chọn nhạc sát không khí hơn. Chưa tải:
// "Tải thêm"; đang tải: tiến độ (hỏi lại mỗi 2 giây, chỉ khi cửa sổ đang thấy); đã tải: "Đọc lại ngữ cảnh" cho cuốn này.
Column {
    id: root
    objectName: "studioMusicMoods"
    property var store: null
    property string bookId: ""
    property var moods: null                // {running, error} của GET /music
    signal computed(var view)
    property var model: null
    property bool downloading: false        // đang gửi lệnh tải
    property bool computing: false          // đang gửi lệnh đọc lại
    readonly property bool running: Boolean(moods && moods.running) || computing
    readonly property string phase: Logic.moodsState(model, !!store && (store.remote || !!store.peer))
    readonly property var percent: Logic.moodsPercent(model)
    spacing: 8

    function load() {
        store.request("GET", "/api/music/moods-model", null, function(status, data) {
            if (root.store.ok(status) && data) root.model = data
        })
    }
    function download() {
        downloading = true
        store.request("POST", "/api/music/moods-model", null, function(status, data) {
            root.downloading = false
            if (root.store.ok(status) && data) root.model = data
            else Api.notice = "Không tải được phần đọc không khí\n" + root.store.errorText(status, data)
        })
    }
    function compute() {
        computing = true
        store.request("POST", "/api/books/" + bookId + "/music/moods", null, function(status, data) {
            root.computing = false
            if (root.store.ok(status) && data) root.computed(data)
            else Api.notice = "Không đọc lại được không khí các đoạn\n" + root.store.errorText(status, data)
        })
    }
    Component.onCompleted: load()
    Timer {
        objectName: "moodsModelPoll"
        interval: 2000
        repeat: true
        running: !!root.store && root.store.active && !!root.model && Boolean(root.model.downloading)
        onTriggered: root.load()
    }

    Collapse {
        width: parent.width
        open: root.phase !== "none"
        spacing: 8
        Text { width: parent.width; text: "Hiểu ngữ cảnh để chọn nhạc; ~1 phút mỗi giờ sách."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        Flow {
            width: parent.width
            visible: root.phase === "installed"
            spacing: 12
            Button {
                objectName: "moodsCompute"
                text: root.running ? "Đang đọc không khí" : "Đọc lại ngữ cảnh"
                icon: "refresh-cw"; kind: "ghost"; size: "sm"
                busy: root.running
                onActivated: root.compute()
            }
            Text {
                visible: !!root.moods && !!root.moods.error
                width: Math.min(implicitWidth, parent.width)
                height: 32; verticalAlignment: Text.AlignVCenter
                text: root.moods ? root.moods.error || "" : ""
                color: Theme.warning
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        ClockLabel {
            width: parent.width
            visible: root.phase === "downloading"
            text: "Đang tải phần đọc không khí" + (root.percent !== null ? " - " + root.percent + "%" : "")
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Flow {
            width: parent.width
            visible: root.phase === "offer"
            spacing: 12
            Button {
                objectName: "moodsDownload"
                text: "Tải thêm (3,2 GB)"
                icon: "download"; kind: "ghost"; size: "sm"
                busy: root.downloading
                onActivated: root.download()
            }
            Text {
                visible: !!root.model && !!root.model.error
                width: Math.min(implicitWidth, parent.width)
                height: 32; verticalAlignment: Text.AlignVCenter
                text: root.model ? root.model.error || "" : ""
                color: Theme.warning
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
        Text {
            width: parent.width
            visible: root.phase === "elsewhere"
            text: root.model && root.model.downloadable ? "Tải phần đọc không khí trên máy tính chủ sách." : "Máy này chưa có phần đọc không khí (cài qua Ollama)."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
}
