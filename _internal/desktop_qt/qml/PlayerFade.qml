import "UiStrings.js" as S
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
            Text { objectName: "playerFadeText"; width: Math.max(0, parent.width - 24); text: S.s_sap_tat_u00a0_u00a0cham_phim_hoac_chuot_de_7b680793(root.extend); wrapMode: Text.Wrap; color: Theme.accentText; font.pixelSize: Theme.sizeBodySmall }
        }
        Button { objectName: "playerFadeExtend"; text: S.s_hen_lai_0_phut_d6009aba(root.extend); kind: "ghost"; onClicked: Player.extendSleep() }
    }
}
