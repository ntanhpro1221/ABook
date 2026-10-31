import QtQuick
import ABook

// Nút nghe thử của một dòng nhân vật / người kể (SampleButton của listen/BookScreen.tsx): ▶ khi nghỉ, vòng xoay lúc chờ clip, biểu tượng sóng âm
// lúc đang ra tiếng; bấm lúc đang phát thì dừng ("Dừng nghe thử"). Ô tròn 36 như web. Clip đi qua Clip (MỘT clip một lúc cho cả app).
// Nút "Nghe thử bằng câu của sách" (VoiceTry.tsx) cũng là ô này: `asks` - bấm thì phát `requested()` (hộp giọng hỏi máy thu câu rồi phát qua Clip), icon
// nghỉ là quyển sách (`idleIcon`), `busy` trong lúc máy chủ đang thu thử.
Interactive {
    id: root
    property string clipId: ""
    property string url: ""
    property string label: ""
    property string stopLabel: "Dừng nghe thử"     // tên trợ năng lúc đang phát (trình tạo: "Dừng nghe <giọng>")
    property string idleIcon: "play"
    property bool asks: false
    property bool busy: false
    signal requested()
    readonly property bool active: clipId !== "" && Clip.current === clipId
    readonly property bool loading: busy || (active && Clip.loading)
    readonly property int fade: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionFast
    implicitWidth: 36
    implicitHeight: 36
    ringRadius: width / 2
    tip: active ? "Dừng" : label
    Accessible.role: Accessible.Button
    Accessible.name: active ? stopLabel : label
    onClicked: { if (asks) root.requested(); else Clip.toggle(clipId, url) }

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Theme.hover
        opacity: root.hovered || root.pressed ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.fade } }
    }
    Icon {
        anchors.centerIn: parent
        name: root.idleIcon
        size: root.idleIcon === "play" ? 14 : 16
        color: Theme.text2
        opacity: root.active || root.busy ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: root.fade } }
    }
    Icon {
        anchors.centerIn: parent
        name: "loader-circle"
        size: 16
        color: Theme.accentText
        opacity: root.loading ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.fade } }
        RotationAnimator on rotation { running: root.loading && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
    }
    Icon {
        anchors.centerIn: parent
        name: "audio-lines"
        size: 16
        color: Theme.accentText
        opacity: root.active && !root.loading ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.fade } }
    }
}
