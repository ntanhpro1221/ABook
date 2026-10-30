import QtQuick
import ABook
import "MyMusicText.js" as Music

// Khối "Bộ nhớ" (ReadAloudStorage của listen/ReadAloudStorage.tsx): bản đọc đã làm (các đoạn đã đọc xong nằm trong bộ đệm của máy, kể cả phần "Làm trước")
// chiếm bao nhiêu, và "Dọn bản đọc". Hỏi lại trong hộp thoại (Back đóng hộp, đang dọn thì chưa đóng được). Số liệu hỏi lại mỗi 15 giây.
// GET /api/readaloud/cache -> {book, total}; DELETE /api/readaloud/cache?all=1 -> số liệu mới.
Collapse {
    id: root
    UiActivity { target: root; id: activity; onResumed: root.load() }
    objectName: "advancedStorage"
    property alias confirmDialog: dialog
    property var usage: null
    property bool busy: false
    readonly property bool hasStorage: usage !== null && usage.total > 0
    open: usage !== null

    function load() {
        Api.call("GET", "/api/readaloud/cache", null, function(data, error) { if (!error) root.usage = data })
    }
    function ask() { if (hasStorage) dialog.show() }
    function clear() {
        busy = true
        Api.call("DELETE", "/api/readaloud/cache?all=1", null, function(data, error) {
            root.busy = false
            if (error) {
                Api.notice = Music.toast("Chưa dọn được bản đọc", error)
            } else {
                root.usage = data
                Api.notice = "Đã dọn bản đọc đã làm"
            }
            dialog.dismiss()
        })
    }
    Component.onCompleted: load()
    Timer { objectName: "storagePoll"; interval: 15000; running: activity.running && root.visible; repeat: true; onTriggered: root.load() }
    onHasStorageChanged: if (!hasStorage && dialog.open) dialog.dismiss()

    SettingRow {
        width: parent.width
        label: "Bản đọc đã làm"
        hint: root.usage ? Music.storageLabel(root.usage) : ""
        Item {
            implicitWidth: root.hasStorage ? clean.implicitWidth - 12 : 0     // chữ nút thẳng mép phải (settings-row-control > ghost: -mr-3)
            implicitHeight: clean.implicitHeight
            Behavior on implicitWidth { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            opacity: root.hasStorage ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Button { id: clean; text: "Dọn bản đọc"; kind: "ghost"; size: "sm"; enabled: root.hasStorage; onClicked: root.ask() }
        }
    }
    MoreInfo {
        width: parent.width
        HintText { width: parent.width; text: "Nghe lại đoạn đã đọc xong thì không phải chờ máy đọc lại; dọn đi thì lấy lại chỗ trống." }
    }
    Modal {
        id: dialog
        title: "Dọn bản đọc đã làm"
        description: root.usage ? Music.clearStorageQuestion(root.usage) : ""
        dismissable: !root.busy
        keepOpen: function() { return root.busy }
        footer: [
            Flow {
                width: dialog.bodyWidth
                layoutDirection: Qt.RightToLeft
                spacing: 8
                Button { text: "Dọn"; kind: "danger"; busy: root.busy; onActivated: root.clear() }
                Button { text: "Giữ lại"; kind: "ghost"; enabled: !root.busy; onClicked: dialog.close() }
            }
        ]
    }
}
