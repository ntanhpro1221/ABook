import QtQuick
import ABook

Collapse {
    id: root
    readonly property int extend: Player.sleepExtendMinutes
    open: Player.fading
    Column {
        width: parent.width; spacing: Theme.s4
        Row {
            width: parent.width; spacing: Theme.s8
            Icon { name: "moon"; size: 16 }
            Text { objectName: "playerFadeText"; width: Math.max(0, parent.width - 24); text: `Sắp tắt\u00a0·\u00a0chạm phím hoặc chuột để hẹn lại ${root.extend} phút`; wrapMode: Text.Wrap; color: Theme.accentText; font.pixelSize: Theme.sizeBodySmall }
        }
        Button { objectName: "playerFadeExtend"; text: `Hẹn lại ${root.extend} phút`; kind: "ghost"; onClicked: Player.extendSleep() }
    }
}
