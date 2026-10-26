import QtQuick
import ABook

// Hẹn giờ ngủ: tắt sau N phút (giờ chỉ chạy khi có tiếng thật, dừng thì đứng) hay hết chương này. Đang hẹn: còn bao lâu, thêm 10 phút, tắt hẹn giờ.
Popover {
    id: root
    panelWidth: 296

    ClockUser { wanted: root.visible }

    Column {
        width: parent.width
        spacing: Theme.s12
        Text {
            width: parent.width
            text: Player.sleepKind === "minutes" ? "Còn " + Player.clockText(Player.clock.sleepLeft)
                : (Player.sleepKind === "chapter" ? "Dừng khi hết chương này" : "Hẹn giờ ngủ")
            color: Player.sleepKind === "off" ? Theme.text2 : Theme.accentText
            wrapMode: Text.Wrap
            font.pixelSize: Player.sleepKind === "off" ? Theme.sizeCaption : Theme.sizeBodySmall
            font.weight: Theme.weightMedium
        }
        Text {
            visible: Player.sleepStoppedText !== "" && Player.sleepKind === "off"
            width: parent.width
            text: "Đã dừng lúc " + Player.sleepStoppedText
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        Grid {
            columns: 3
            spacing: Theme.s8
            Repeater {
                model: Player.sleepChoices
                ChoiceChip {
                    required property var modelData
                    width: (root.panelWidth - 2 * root.pad - 2 * Theme.s8) / 3
                    text: modelData + " phút"
                    selected: Player.sleepKind === "minutes" && Player.sleepMinutes === modelData
                    onClicked: { Player.setSleep("minutes", modelData); root.close() }
                }
            }
        }
        ChoiceChip {
            width: parent.width
            text: "Hết chương này"
            selected: Player.sleepKind === "chapter"
            onClicked: { Player.setSleep("chapter"); root.close() }
        }
        Row {
            visible: Player.sleepKind !== "off"
            spacing: Theme.s8
            Button {
                kind: "text"
                text: "Thêm 10 phút"
                visible: Player.sleepKind === "minutes"
                onClicked: Player.extendSleep()
            }
            Button {
                kind: "text"
                text: "Tắt hẹn giờ"
                onClicked: { Player.setSleep("off"); root.close() }
            }
        }
    }
}
