import "UiStrings.js" as S
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
                Api.notice = Music.toast(S.s_chua_cap_nhat_duoc_1ceb4e4b, error)
            } else {
                Api.notice = S.s_dang_tai_abook_36a50850 + root.update.version + S.s_app_se_tu_mo_lai_75d4ab5f
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
    // Kênh của vỏ (Backend đọc dòng JSON của host, như vỏ Tauri phát sự kiện cửa sổ): kết quả kiểm, tải hỏng
    Connections {
        target: Backend
        function onUpdateChecked(detail) { root.heard(detail) }
        function onHostEvent(name, detail) { if (name === "abook-update-failed") root.failed() }
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
                        text: "<b>" + S.s_abook_0_555fc57e(root.update ? root.update.version : "") + S.s_b_da_co_beb7c8b1 + (root.current ? S.s_nbsp_nbsp_dang_dung_a1795199 + root.current : "")
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
                        font.pixelSize: 14
                        lineHeight: 1.625
                    }
                    Item { width: 1; height: 12 }
                    Button {
                        text: root.installing ? S.s_dang_tai_ban_moi_2c868c00 : S.s_cap_nhat_abook_66fb9f08
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
                label: root.current ? S.s_abook_76b9d6fa + root.current : S.s_ban_moi_422f08ca
                hint: root.line ? root.line.text : ""
                hintColor: root.line && root.line.tone === "error" ? Theme.danger : Theme.text2
                Behavior on implicitHeight { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                Item {
                    implicitWidth: checkButton.implicitWidth - 12      // chữ nút thẳng mép phải (settings-row-control > ghost: -mr-3)
                    implicitHeight: checkButton.implicitHeight
                    Button {
                        id: checkButton
                        text: root.checking ? S.s_dang_kiem_tra_0726ac0c : S.s_kiem_tra_ban_moi_f66eda92
                        kind: "ghost"; size: "sm"
                        enabled: !root.checking
                        onClicked: root.check()
                    }
                }
            }
        }
    }
}
