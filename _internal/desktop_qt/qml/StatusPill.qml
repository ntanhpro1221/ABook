import QtQuick
import ABook

// Viên trạng thái (StatusPill của shared/ui.tsx): cao 24, bo tròn, nền nhạt + chữ theo `tone` (accent / success / danger / warning / muted), chấm tròn đầu
// viên; `live` (đang chạy) thay chấm bằng biểu tượng sóng. Đổi nhãn / màu thì màu chuyển dần, không nhảy.
Rectangle {
    id: root
    property string label: ""
    property string tone: "muted"
    property bool live: false
    readonly property color ink: tone === "accent" ? Theme.accentText : tone === "success" ? Theme.success : tone === "danger" ? Theme.danger
                                 : tone === "warning" ? Theme.warning : Theme.text2
    readonly property color back: tone === "accent" ? Theme.accentSoft : tone === "success" ? Qt.alpha(Theme.success, 0.14) : tone === "danger" ? Theme.dangerSoft
                                  : tone === "warning" ? Theme.warningSoft : Theme.hover
    implicitHeight: 24
    implicitWidth: lead.width + text.implicitWidth + 20 + 6
    height: implicitHeight
    radius: height / 2
    color: back
    Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    Accessible.role: Accessible.StaticText
    Accessible.name: label
    Item {
        id: lead
        x: 10
        width: root.live ? 12 : 6
        height: 12
        anchors.verticalCenter: parent.verticalCenter
        Rectangle { visible: !root.live; anchors.centerIn: parent; width: 6; height: 6; radius: width / 2; color: root.ink }
        Icon { visible: root.live; anchors.centerIn: parent; name: "audio-lines"; size: 12; color: root.ink }
    }
    Text {
        id: text
        objectName: "pillText"
        x: lead.x + lead.width + 6
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: root.ink
        wrapMode: Text.NoWrap
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
}
