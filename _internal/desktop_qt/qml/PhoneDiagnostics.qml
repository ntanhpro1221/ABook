import "UiStrings.js" as S
import QtQuick
import QtQuick.Dialogs
import ABook
import "DevicesLogic.js" as Logic

// Hộp "Chẩn đoán" của một điện thoại đã ghép (desktop/PhoneDiagnostics.tsx + shared/DiagnosticsView.tsx): máy tính hỏi điện thoại qua cổng
// đồng bộ (GET /api/remote/<mã>/diagnostics?lines=400) nên đi được cả khi điện thoại ở mạng khác. Tóm tắt từng mục, "Chi tiết kỹ thuật" gập,
// nhật ký cuộn được (dòng mới nhất ở cuối, cuộn sẵn xuống đó). "Lưu nhật ký" hỏi thư mục rồi POST .../diagnostics/save. Là một lớp của Back.
Modal {
    id: root
    property var computer: null           // {id, name}
    property string shownName: ""
    property var report: null
    property bool loading: false
    property bool saving: false
    property var failure: null            // {title, help}
    property int generation: 0
    readonly property var rows: report ? Logic.summaryRows(report).concat(Logic.workProgressRows(report)) : []
    readonly property var errors: report ? Logic.failureDetails(report) : []
    readonly property var appLog: report ? Logic.logLines(report, "log") : []
    readonly property var systemLog: report ? Logic.logLines(report, "logcat") : []
    title: S.s_chan_doan_738cc26b + shownName
    description: S.s_nhat_ky_co_ten_sach_thong_tin_rieng_duoc_c_bbe37d25
    panelWidth: 560

    function openFor(target) {
        computer = target
        shownName = target.name || ""
        report = null
        failure = null
        show()
        reload()
    }
    function failureOf(status, data) {
        const message = data && (data.message || data.error) || S.s_chua_lam_duoc_luc_nay_2e7cacde
        return {title: message, help: status === 409 || status === 404 ? "" : Logic.UNREACHABLE_HELP}
    }
    function reload() {
        if (!computer || !Api.transport) return
        const mine = ++generation
        loading = true
        Api.transport.request("GET", "/api/remote/" + computer.id + "/diagnostics?lines=400", null, function(status, data) {
            if (mine !== root.generation) return
            root.loading = false
            if (status >= 200 && status < 300) { root.report = data; root.failure = null }
            else root.failure = root.failureOf(status, data)
        })
    }
    onClosed: generation++

    FolderDialog {
        id: folder
        title: S.s_luu_nhat_ky_57df5372
        onAccepted: {
            root.saving = true
            Api.transport.request("POST", "/api/remote/" + root.computer.id + "/diagnostics/save", {lines: 2000, target: DesktopApi.localPath(selectedFolder)}, function(status, data) {
                root.saving = false
                if (status >= 200 && status < 300) Api.notice = S.s_da_luu_nhat_ky_65019295
                else Api.notice = S.s_chua_luu_duoc_nhat_ky_c92f8b79
            })
        }
    }

    Flow {
        width: parent.width
        spacing: 8
        Button { objectName: "diagnosticsRefresh"; size: "sm"; kind: "ghost"; icon: "refresh-cw"; text: S.s_lam_moi_b4c61340; busy: root.loading; onActivated: root.reload() }
        Button { objectName: "diagnosticsSave"; size: "sm"; kind: "ghost"; icon: "save"; text: S.s_luu_nhat_ky_57df5372; busy: root.saving; enabled: !root.failure; onActivated: folder.open() }
    }
    Collapse {
        width: parent.width
        open: root.loading && !root.report
        DevicesSkeleton { width: parent.width; count: 2; label: S.s_dang_tai_chan_doan_0427c039 }
    }
    InlineError {
        width: parent.width
        open: Boolean(root.failure)
        message: root.failure ? root.failure.title + " " + (root.failure.help || S.s_ban_hay_thu_tai_lai_chan_doan_eea0bd09) : ""
        onRetry: root.reload()
    }
    Column {
        width: parent.width
        Reveal { shown: root.report !== null }
        spacing: 16
        Column {
            width: parent.width
            Reveal { shown: root.rows.length > 0 }
            Repeater {
                model: root.rows
                Item {
                    required property var modelData
                    required property int index
                    width: parent.width
                    implicitHeight: valueText.height + 16 + (index > 0 ? 1 : 0)
                    height: implicitHeight
                    Rectangle { width: parent.width; height: 1; color: Theme.line; Reveal { shown: index > 0 }}
                    Text { x: 0; y: 8 + (index > 0 ? 1 : 0); width: 176; text: modelData.label; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                    Text { id: valueText; x: 176 + 16; y: 8 + (index > 0 ? 1 : 0); width: parent.width - x; text: modelData.value; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall }
                }
            }
        }
        MoreInfo {
            id: moreInfoShown
            width: parent.width
            Reveal { target: moreInfoShown; shown: root.errors.length > 0 }
            label: S.s_chi_tiet_ky_thuat_f27eb5f6
            TextEdit {
                width: parent.width
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: Theme.text2
                font.family: "monospace"
                font.pixelSize: Theme.sizeCaption
                text: root.errors.map(row => row.label + ": " + row.value).join("\n")
            }
        }
        DevicesLogBox {
            width: parent.width
            title: S.s_nhat_ky_cua_abook_0_dong_9a189053(root.appLog.length)
            lines: root.appLog
            empty: root.report ? Logic.emptyLogNote(root.report, "log") : ""
            startOpen: true
        }
        DevicesLogBox {
            width: parent.width
            Reveal { shown: root.report !== null && (root.systemLog.length > 0 || root.report.logcat !== undefined) }
            title: S.s_nhat_ky_he_thong_cua_app_5d62b230 + root.systemLog.length + S.s_dong_8fe5919d
            lines: root.systemLog
            empty: root.report ? Logic.emptyLogNote(root.report, "logcat") : ""
        }
        HintText { width: parent.width; Reveal { shown: Boolean(root.report && root.report.truncated) } color: Theme.text3; text: S.s_nhat_ky_dai_nen_da_cat_bot_phan_cu_nhat_ad1b7371 }
    }
}
