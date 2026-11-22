import QtQuick
import ABook
import "UiStrings.js" as S

// Flat track, like the app's progress bars. Emotion scores have no input border.
Rectangle {
    id: root
    property real score: 0
    property color ink: Theme.accent
    property string label: ""
    // Thanh tiến độ (Đã nghe): dưới Theme.progressFillMin không tô (như web progressFill / Android ProgressFill.of) và đổi giá trị thì chạy dần
    // (web motion-progress). Thang điểm cảm xúc giữ vạch tĩnh.
    property bool progress: false
    implicitHeight: 6
    radius: height / 2
    color: Theme.line
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Accessible.description: S.s_percent(Math.round(score * 100))
    Rectangle {
        objectName: "levelBarFill"
        readonly property real shown: root.progress && root.score < Theme.progressFillMin ? 0 : Math.max(0, Math.min(1, root.score))
        width: parent.width * shown; height: parent.height; radius: height / 2; color: root.ink // tick-ok: "Đã nghe" đổi sau khi nghe, không tự chạy từng giây; chạy dần như web motion-progress (Lead chốt leftfix)
        Behavior on width { enabled: root.progress && !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
