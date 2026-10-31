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
    title: "Chẩn đoán " + shownName
    description: "Nhật ký có tên sách; thông tin riêng được che nhưng hãy xem lại trước khi gửi."
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
        const message = data && (data.message || data.error) || "Chưa làm được lúc này."
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
        title: "Chọn nơi lưu nhật ký"
        onAccepted: {
            root.saving = true
            Api.transport.request("POST", "/api/remote/" + root.computer.id + "/diagnostics/save", {lines: 2000, target: DesktopApi.localPath(selectedFolder)}, function(status, data) {
                root.saving = false
                if (status >= 200 && status < 300) Api.notice = "Đã lưu nhật ký"
                else Api.notice = "Chưa lưu được nhật ký"
            })
        }
    }

    Flow {
        width: parent.width
        spacing: 8
        Button { objectName: "diagnosticsRefresh"; size: "sm"; kind: "ghost"; icon: "refresh-cw"; text: "Làm mới"; busy: root.loading; onActivated: root.reload() }
        Button { objectName: "diagnosticsSave"; size: "sm"; kind: "ghost"; icon: "save"; text: "Lưu nhật ký"; busy: root.saving; enabled: !root.failure; onActivated: folder.open() }
    }
    Collapse {
        width: parent.width
        open: root.loading && !root.report
        DevicesSkeleton { width: parent.width; count: 2; label: "Đang tải chẩn đoán" }
    }
    DevicesError {
        width: parent.width
        open: Boolean(root.failure)
        message: root.failure ? root.failure.title + " " + (root.failure.help || "Bạn hãy thử tải lại chẩn đoán.") : ""
        onRetry: root.reload()
    }
    Column {
        width: parent.width
        visible: root.report !== null
        spacing: 16
        Column {
            width: parent.width
            visible: root.rows.length > 0
            Repeater {
                model: root.rows
                Item {
                    required property var modelData
                    required property int index
                    width: parent.width
                    implicitHeight: valueText.height + 16 + (index > 0 ? 1 : 0)
                    height: implicitHeight
                    Rectangle { width: parent.width; height: 1; color: Theme.line; visible: index > 0 }
                    Text { x: 0; y: 8 + (index > 0 ? 1 : 0); width: 176; text: modelData.label; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                    Text { id: valueText; x: 176 + 16; y: 8 + (index > 0 ? 1 : 0); width: parent.width - x; text: modelData.value; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall }
                }
            }
        }
        MoreInfo {
            width: parent.width
            visible: root.errors.length > 0
            label: "Chi tiết kỹ thuật"
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
            title: "Nhật ký của ABook (" + root.appLog.length + " dòng)"
            lines: root.appLog
            empty: root.report ? Logic.emptyLogNote(root.report, "log") : ""
            startOpen: true
        }
        DevicesLogBox {
            width: parent.width
            visible: root.report !== null && (root.systemLog.length > 0 || root.report.logcat !== undefined)
            title: "Nhật ký hệ thống của app (" + root.systemLog.length + " dòng)"
            lines: root.systemLog
            empty: root.report ? Logic.emptyLogNote(root.report, "logcat") : ""
        }
        HintText { width: parent.width; visible: Boolean(root.report && root.report.truncated); color: Theme.text3; text: "Nhật ký dài nên đã cắt bớt phần cũ nhất." }
    }
}
