import QtQuick
import ABook

// Nút nghe thử của một dòng nhân vật / người kể (SampleButton của listen/BookScreen.tsx): ▶ khi nghỉ, vòng xoay lúc chờ clip, biểu tượng sóng âm
// lúc đang ra tiếng; bấm lúc đang phát thì dừng ("Dừng nghe thử"). Ô tròn 36 như web. Clip đi qua Clip (MỘT clip một lúc cho cả app).
Interactive {
    id: root
    property string clipId: ""
    property string url: ""
    property string label: ""
    readonly property bool active: Clip.current === clipId
    readonly property bool loading: active && Clip.loading
    readonly property int fade: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionFast
    implicitWidth: 36
    implicitHeight: 36
    ringRadius: width / 2
    tip: active ? "Dừng" : label
    Accessible.role: Accessible.Button
    Accessible.name: active ? "Dừng nghe thử" : label
    onClicked: Clip.toggle(clipId, url)

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Theme.hover
        opacity: root.hovered || root.pressed ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.fade } }
    }
    Icon {
        anchors.centerIn: parent
        name: "play"
        size: 14
        color: Theme.text2
        opacity: root.active ? 0 : 1
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
