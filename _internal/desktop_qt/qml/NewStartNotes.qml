import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "StudioLogic.js" as Studio

// Lời nhắc ngay trên nút tạo, luôn thấy (không nằm trong "Tuỳ chọn"): máy không đủ thì nói vì sao, làm lại thì bản dở vào Thùng rác, và luật phân tích không bị ngắt (AGENTS.md):
// cần nghỉ thì dùng Tạm dừng, đừng Dừng - dừng giữa phân tích là đổi cả quyển sách.
Column {
    id: root
    property var form: null
    signal peerRequested(string id)
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property var replaces: draft.replaces
    readonly property bool exact: Logic.matchesMeasured(form ? form.gpu : null, draft.analysisModel || "")
    readonly property var guess: scan ? Logic.estimate(scan.totals.words, scan.files.length, exact) : null
    readonly property string analysis: guess && draft.profile === "high_quality" ? (exact ? Studio.formatLength(guess.analysis) : Logic.lengthRange(guess.analysisLow, guess.analysisHigh)) : ""
    spacing: 8

    StudioSetupNotice { objectName: "newStartUnfit"; width: parent.width; form: root.form; unfitOnly: true; onPeerRequested: id => root.peerRequested(id) }
    Collapse {
        width: parent.width
        open: Boolean(root.replaces && root.replaces.restart)
        NewNote {
            objectName: "newRestartNote"
            width: parent.width
            gap: 0
            pad: 0
            icon: "info"
            Prose { text: "Tạo cuốn mới từ đầu, giữ bìa và file gốc; bản dở “" + (root.replaces ? root.replaces.title : "") + "” vào Thùng rác." }
        }
    }
    NewNote {
        objectName: "newPauseNote"
        width: parent.width
        gap: 0
        pad: 0
        icon: "triangle-alert"
        tone: Theme.warning
        Prose { objectName: "newPauseText"; text: Logic.PAUSE_NOTE }
        MoreInfo {
            width: parent.width
            label: "Vì sao?"
            Prose { objectName: "newPauseWhy"; small: true; text: Logic.pauseWhy(root.form ? root.form.noStudio : false, root.analysis) }
        }
    }
}
