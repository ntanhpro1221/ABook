import QtQuick
import ABook
import "MyMusicText.js" as Music

// Nội dung khối "Cập nhật" (UpdateRow + UpdateCheck của desktop/SettingsScreen.tsx, desktop/updateCheck.ts). Có bản mới (vỏ đã tìm thấy, đã ký): hiện
// "ABook X đã có · đang dùng Y", ghi chú và nút "Cập nhật ABook" - cài chỉ khi bấm. Chưa có: dòng "ABook Y" + nút "Kiểm tra bản mới", bấm xong luôn có
// một lời (kể cả khi mạng đứt hay vỏ im: 45 giây thì báo lỗi mạng). Hai phần thay chỗ nhau bằng chiều cao.
Item {
    id: root
    objectName: "advancedUpdate"
    readonly property var info: Api.info || {}
    readonly property var update: info.update || null
    readonly property string current: info.version || ""
    property bool installing: false
    property bool checking: false
    property var line: null                 // {tone: "ok" | "error", text} hay null
    property int waitMs: Music.UPDATE_CHECK_WAIT_MS
    implicitHeight: column.height
    height: implicitHeight

    // Kết quả của vỏ ("abook-update-checked"): {state: "found" | "latest" | "failed", message?}; null = vỏ không trả lời
    function heard(detail) {
        if (!checking) return
        checking = false
        silent.stop()
        line = Music.checkLine(detail, current)
    }
    // Vỏ tải hỏng ("abook-update-failed"): nút bấm lại được
    function failed() { installing = false }
    function install() {
        installing = true
        Api.call("POST", "/api/app/update", {}, function(data, error) {
            if (error) {
                root.installing = false
                Api.notice = Music.toast("Chưa cập nhật được", error)
            } else {
                Api.notice = "Đang tải ABook " + root.update.version + " - app sẽ tự mở lại"
            }
        })
    }
    function check() {
        line = null
        checking = true
        silent.restart()
        Api.call("POST", "/api/app/check-update", {}, function(data, error) {
            if (!error) return
            if (Api.notice === error) Api.notice = ""       // lỗi hiện ngay dưới nút, không thêm lời báo
            root.checking = false
            silent.stop()
            root.line = {tone: "error", text: error}
        })
    }
    Timer { id: silent; interval: root.waitMs; onTriggered: root.heard(null) }
    // Vỏ Qt chưa có sự kiện "đã kiểm xong": hỏi lại /api/app, thấy `update` là bản mới đã có
    Timer {
        interval: 3000
        running: root.checking
        repeat: true
        onTriggered: Api.call("GET", "/api/app", null, function(data, error) {
            if (error || !data.update) return
            Api.info = data
            root.heard({state: "found"})
        })
    }

    Column {
        id: column
        width: parent.width
        Collapse {
            width: parent.width
            open: root.update !== null
            Item {
                width: parent.width
                height: pane.height + 24
                Column {
                    id: pane
                    y: 12
                    width: parent.width
                    Text {
                        width: parent.width
                        textFormat: Text.StyledText
                        text: "<b>ABook " + (root.update ? root.update.version : "") + "</b> đã có" + (root.current ? " · đang dùng " + root.current : "")
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Text {
                        visible: Boolean(root.update) && Boolean(root.update.notes)
                        width: parent.width
                        topPadding: 8
                        text: root.update ? root.update.notes : ""
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: 13
                        lineHeight: 1.625
                    }
                    Item { width: 1; height: 12 }
                    Button {
                        text: root.installing ? "Đang tải bản mới…" : "Cập nhật ABook"
                        icon: "download"; kind: "ghost"
                        enabled: !root.installing
                        onClicked: root.install()
                    }
                }
            }
        }
        Collapse {
            width: parent.width
            open: root.update === null
            SettingRow {
                width: parent.width
                label: root.current ? "ABook " + root.current : "Bản mới"
                hint: root.line ? root.line.text : ""
                hintColor: root.line && root.line.tone === "error" ? Theme.danger : Theme.text2
                Behavior on implicitHeight { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                Item {
                    implicitWidth: checkButton.implicitWidth - 12      // chữ nút thẳng mép phải (settings-row-control > ghost: -mr-3)
                    implicitHeight: checkButton.implicitHeight
                    Button {
                        id: checkButton
                        text: root.checking ? "Đang kiểm tra…" : "Kiểm tra bản mới"
                        kind: "ghost"; size: "sm"
                        enabled: !root.checking
                        onClicked: root.check()
                    }
                }
            }
        }
    }
}
