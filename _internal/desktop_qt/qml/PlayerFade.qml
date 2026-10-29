import QtQuick
import ABook

Collapse {
    id: root
    readonly property int extend: Number(Api.preferences.sleepExtendMinutes || 10)
    open: Player.fading
    Column {
        width: parent.width; spacing: Theme.s4
        Row {
            width: parent.width; spacing: Theme.s8
            Icon { name: "moon"; size: 16 }
            Text { objectName: "playerFadeText"; width: Math.max(0, parent.width - 24); text: `Sắp tắt · chạm phím hoặc chuột để nghe thêm ${root.extend} phút`; wrapMode: Text.Wrap; color: Theme.accentText; font.pixelSize: Theme.sizeBodySmall }
        }
        Button { objectName: "playerFadeExtend"; text: `+${root.extend} phút`; kind: "ghost"; onClicked: Player.extendSleep() }
    }
}
