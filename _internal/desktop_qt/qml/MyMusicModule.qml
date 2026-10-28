import QtQuick
import ABook
import "MyMusicText.js" as Music

// Thẻ duy nhất của mô-đun "Phân tích nhạc" dưới danh sách nhạc (MusicModuleNotice của studio/MusicModuleNotice.tsx): nhập nhạc chạy không cần nó,
// nó chỉ cho máy NGHE nhạc để hiểu không khí từng bài. Người dùng thấy tổng dung lượng và bấm mới tải (không bao giờ tự tải). Có bản mới thì nói
// "Có bản mới - N MB"; cập nhật xong KHÔNG tự phân tích lại bài cũ (nút "Phân tích N bài"). Máy đủ RAM còn có "Cảm xúc chính xác". Mọi phần
// hiện / ẩn đều mở tại chỗ. Đang tải hay phân tích thì hỏi lại trạng thái mỗi giây.
Column {
    id: root
    UiActivity { target: root; id: activity; onResumed: Api.call("GET", "/api/music/local", null, function(data, error) { if (!error) root.updated(data) }) }
    objectName: "musicModule"
    property var view: null
    property bool starting: false
    signal updated(var view)
    readonly property var module: view ? view.module : undefined
    readonly property int stale: module ? (module.stale || 0) : 0
    readonly property var precise: Music.preciseOffered(module) ? module.precise : null
    readonly property bool busy: Boolean(module) && (module.state === "downloading" || Boolean(module.analysing) || Music.preciseBusy(module.precise))
    readonly property bool calm: Boolean(module) && module.state === "ready" && !module.analysing && !module.restart && stale === 0
    readonly property bool showModule: Boolean(module) && !calm
    readonly property bool downloadingModule: Boolean(module) && module.state === "downloading"
    readonly property bool failed: Boolean(module) && module.state === "error"
    readonly property string label: module ? Music.moduleLabel(module) : ""
    readonly property string action: !module || busy || module.state === "unsupported" || module.restart ? "" : (stale > 0 && module.state === "ready" ? "reanalyse" : "install")
    function post(path, body) {
        starting = true
        Api.call("POST", path, body || {}, function(data, error) {
            root.starting = false
            if (!error) root.updated(data)
        })
    }
    function installText() {
        const size = Music.formatSize(module.outdatedBytes !== undefined ? module.outdatedBytes : module.total)
        return failed ? "Thử lại" : module.stopped ? "Tải lại (" + size + ")" : module.state === "outdated" ? "Cập nhật (" + size + ")" : "Tải (" + Music.formatSize(module.total) + ")"
    }
    function preciseText() {
        const p = root.precise
        return p.state === "error" ? "Thử lại" : p.state === "missing" ? "Tải tiếp (" + Music.formatSize(p.bytes) + ")" : p.state === "ready" ? "Tắt đo cảm xúc" : p.present ? "Bật đo cảm xúc" : "Tải (" + Music.formatSize(p.bytes) + ")"
    }

    Timer {
        interval: 1000
        running: activity.running && root.busy
        repeat: true
        onTriggered: Api.call("GET", "/api/music/local", null, function(data, error) { if (!error) root.updated(data) })
    }

    Collapse {
        width: parent.width
        open: root.showModule || root.precise !== null
        spacing: 12
        // ---- mô-đun Phân tích nhạc ----
        Collapse {
            width: parent.width
            open: root.showModule
            spacing: 6
            Text {
                width: parent.width
                text: root.label
                visible: text !== ""
                color: root.failed ? Theme.danger : Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeCaption
                lineHeight: 1.3
            }
            MyMusicDetails { width: parent.width; technical: root.failed ? (root.module.errorDetail || "") : "" }
            Collapse {
                width: parent.width
                open: Boolean(root.module) && root.module.state === "missing"
                MoreInfo {
                    width: parent.width
                    label: "Phân tích nhạc"
                    HintText { width: parent.width; text: "Tải một lần, phân tích trên máy rồi dùng không cần mạng. Chưa tải vẫn nhập, nghe và ghim nhạc bằng tay." }
                }
            }
            Collapse {
                width: parent.width
                open: root.downloadingModule
                Item {
                    width: parent.width
                    height: 40
                    MyMusicBar {
                        anchors.left: parent.left
                        anchors.right: cancel.visible ? cancel.left : parent.right
                        anchors.rightMargin: cancel.visible ? 12 : 0
                        anchors.verticalCenter: parent.verticalCenter
                        value: root.module ? Music.modulePercent(root.module) / 100 : 0
                        label: "Đang tải Phân tích nhạc"
                    }
                    Button {
                        id: cancel
                        anchors.right: parent.right
                        visible: Boolean(root.module) && Boolean(root.module.cancellable)
                        text: "Huỷ"; kind: "ghost"; size: "sm"
                        busy: root.starting
                        onActivated: root.post("/api/music/local/module/cancel")
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.action !== ""
                Flow {
                    width: parent.width
                    spacing: 8
                    Button {
                        visible: root.action === "install"
                        text: root.module && root.action === "install" ? root.installText() : ""
                        kind: "ghost"; size: "sm"; wrap: true
                        width: Math.min(implicitWidth, parent.width)
                        busy: root.starting
                        onActivated: root.post("/api/music/local/module")
                    }
                    Button {
                        visible: root.action === "reanalyse"
                        text: "Phân tích " + root.stale + " bài"
                        kind: "ghost"; size: "sm"; wrap: true
                        width: Math.min(implicitWidth, parent.width)
                        busy: root.starting
                        onActivated: root.post("/api/music/local/reanalyse")
                    }
                    Item {
                        visible: Boolean(root.module) && root.module.metered && root.action === "install" && !root.failed
                        width: Math.min(warn.implicitWidth, parent.width)
                        height: 40
                        Text {
                            id: warn
                            width: parent.width
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Bạn đang dùng dữ liệu di động - nên đợi khi có Wi-Fi."
                            color: Theme.warning
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                        }
                    }
                }
            }
        }
        // ---- Cảm xúc chính xác ----
        Collapse {
            width: parent.width
            open: root.precise !== null
            spacing: 6
            Text { width: parent.width; text: "Cảm xúc chính xác"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
            Text {
                width: parent.width
                text: root.precise ? Music.preciseLabel(root.precise) : ""
                color: root.precise && root.precise.state === "error" ? Theme.danger : Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeCaption
                lineHeight: 1.3
            }
            MyMusicDetails { width: parent.width; technical: root.precise && root.precise.state === "error" ? (root.precise.errorDetail || "") : "" }
            Collapse {
                width: parent.width
                open: Boolean(root.precise) && root.precise.state === "downloading"
                MyMusicBar {
                    width: parent.width
                    value: root.precise && root.precise.total > 0 ? root.precise.done / root.precise.total : 0
                    label: "Đang tải bộ đo cảm xúc chính xác hơn"
                }
            }
            Collapse {
                width: parent.width
                open: Boolean(root.precise) && root.precise.state === "downloading" && Boolean(root.module) && Boolean(root.module.cancellable)
                Button { text: "Huỷ"; kind: "ghost"; size: "sm"; busy: root.starting; onActivated: root.post("/api/music/local/precise/cancel") }
            }
            Collapse {
                width: parent.width
                open: Boolean(root.precise) && root.precise.state !== "downloading"
                Flow {
                    width: parent.width
                    spacing: 8
                    Button {
                        text: root.precise ? root.preciseText() : ""
                        kind: "ghost"; size: "sm"; wrap: true
                        width: Math.min(implicitWidth, parent.width)
                        busy: root.starting
                        onActivated: root.post("/api/music/local/precise", {enabled: root.precise.state !== "ready"})
                    }
                    Button {
                        visible: Boolean(root.precise) && root.precise.removable
                        text: root.precise ? "Xoá file (" + Music.formatSize(root.precise.bytes) + ")" : ""
                        kind: "ghost"; size: "sm"
                        busy: root.starting
                        onActivated: root.post("/api/music/local/precise/remove")
                    }
                }
            }
        }
    }
}
