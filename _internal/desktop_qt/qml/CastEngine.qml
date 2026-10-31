import QtQuick
import ABook
import "CastLogic.js" as Logic
import "VoiceLogic.js" as Voice

// Đầu một nhóm giọng ở hộp "Giọng của …" (EngineHeader của studio/VoicePicker.tsx): tên nhóm và - khi máy đọc ấy chưa có trên máy này - lời nhắn + nút
// "Tải giọng" / "Sửa giọng" / "Thử lại"; đang tải thì thanh tiến độ + "Huỷ" (phần đã tải giữ để làm tiếp). Hỏi lại trạng thái mỗi giây khi đang tải; tải xong
// thì phát `ready()` để hộp đọc lại danh sách giọng. Cùng đường tải và cùng chữ với thẻ giọng trên máy của Cài đặt › Giọng đọc (VoiceModule.qml, VoiceLogic.js:
// percent, CANCELLED_NOTE; cỡ file ở SizeFormat.js) - chỉ khác hình dạng trạng thái: GET/POST /api/studio/<máy đọc>[/cancel] trả {state, done, total, bytes, error, cancelled, damaged}.
Column {
    id: root
    property string engine: ""
    property string label: ""
    property var initial: null                  // trạng thái hộp gửi sẵn trong lời đáp /voices (modules[máy đọc])
    property var fetched: null
    property bool busy: false
    property var store: null                    // Studio: máy tính ghép (remote) thì tải giọng là việc của máy tính - chỉ nói ở đâu, không nút, không hỏi tiến độ
    readonly property bool remote: store ? store.remote : false
    readonly property var status: fetched !== null ? fetched : initial
    readonly property bool downloading: status !== null && status.state === "downloading"
    readonly property string note: Logic.moduleNote(status)
    readonly property string action: Logic.moduleAction(status)
    signal ready()
    UiActivity { target: root; id: activity; onResumed: if (root.downloading) root.refresh() }
    spacing: 2

    function refresh() {
        if (!root.engine || root.remote) return
        Api.quiet("GET", "/api/studio/" + root.engine, null, function(data, error) { if (!error && data && data.state) root.fetched = data })
    }
    // Một việc ghi lên mô-đun; lỗi thì lời báo hai dòng (tiêu đề + nguyên nhân) như toast.error(failure, {description})
    function run(suffix, failure) {
        busy = true
        Api.quiet("POST", "/api/studio/" + root.engine + suffix, {}, function(data, error) {
            root.busy = false
            if (error) Api.notice = failure + "\n" + error
            else root.fetched = data
        })
    }
    onStatusChanged: {
        if (root.initial && root.initial.state !== "ready" && status && status.state === "ready") root.ready()
    }
    onInitialChanged: fetched = null
    Timer { interval: 1000; running: activity.running && root.downloading && !root.remote; repeat: true; onTriggered: root.refresh() }

    Item {
        width: parent.width
        readonly property real tail: pill.visible ? pill.width : start.visible ? start.width : 0
        height: Math.max(head.height, pill.visible ? pill.height : start.visible ? start.height : 0)
        Text {
            id: head
            objectName: "engineLabel"
            width: Math.max(0, parent.width - (parent.tail > 0 ? parent.tail + 8 : 0))
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            color: Theme.text3
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
            font.weight: 600
        }
        Button {
            id: start
            objectName: "engineStart"
            visible: root.action !== "" && !root.remote
            x: parent.width - width
            anchors.verticalCenter: parent.verticalCenter
            size: "sm"
            kind: "ghost"
            text: root.action
            busy: root.busy
            onActivated: root.run("", "Chưa tải được giọng")
        }
        OnComputerPill {
            id: pill
            objectName: "engineOnComputer"
            visible: root.action !== "" && root.remote
            x: parent.width - width
            anchors.verticalCenter: parent.verticalCenter
            verb: "Tải giọng"
            computer: root.store ? root.store.computerName : "máy tính"
            maxWidth: Math.max(120, parent.width * 0.6)
        }
    }
    Text {
        objectName: "engineNote"
        visible: root.note !== ""
        width: parent.width
        text: root.note
        color: root.status && root.status.state === "error" ? Theme.danger : Theme.text2
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        font.pixelSize: Theme.sizeCaption
    }
    Item {
        visible: root.downloading
        width: parent.width
        height: visible ? Math.max(6, cancel.height) + 4 : 0
        MyMusicBar {
            objectName: "engineBar"
            y: 2 + (parent.height - 4 - height) / 2
            width: parent.width - (cancel.visible ? cancel.width + 12 : 0)
            value: root.status ? Voice.percent(root.status) / 100 : 0
            label: root.note
        }
        Button {
            id: cancel
            objectName: "engineCancel"
            visible: Boolean(root.status && root.status.cancellable) && !root.remote
            x: parent.width - width
            y: 2
            size: "sm"
            kind: "ghost"
            text: "Huỷ"
            busy: root.busy
            onActivated: root.run("/cancel", "Chưa huỷ được việc tải giọng")
        }
    }
}
