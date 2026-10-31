import QtQuick
import ABook

// Hẹn giờ tắt: tắt sau N phút (giờ chỉ chạy khi có tiếng thật, dừng thì đứng) hay hết chương này. Đang hẹn: tắt sau bao lâu, +10 phút, tắt hẹn giờ. Chữ như bản web (SleepPicker).
Popover {
    id: root
    panelWidth: 296
    maxHeight: Math.max(280, Math.min(600, height - 32))
    readonly property int fadeSeconds: Math.max(10, Math.min(60, Number(Api.preferences.sleepFadeSeconds || 30)))
    readonly property int extendMinutes: Math.max(5, Math.min(15, Number(Api.preferences.sleepExtendMinutes || 10)))

    ClockUser { wanted: root.visible }

    Column {
        width: parent.width
        spacing: Theme.s12
        Collapse {
            width: parent.width; open: Player.sleepKind === "off"
            Text { width: parent.width; text: "Dừng phát sau"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
        }
        // Đang hẹn: dòng nhỏ "Tắt sau" / "Dừng khi" trên đồng hồ đếm lùi lớn (như web SleepPicker).
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"; spacing: 2
            Text {
                objectName: "sleepCaption"
                width: parent.width
                text: Player.sleepKind === "chapter" ? "Dừng khi" : "Tắt sau"
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "sleepCountdown"
                width: parent.width
                text: Player.sleepKind === "chapter" ? "hết chương này" : Player.clockText(Player.clock.sleepLeft)
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeTitlePhone
                font.weight: 600
                font.features: { "tnum": 1 }
            }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind === "minutes" && !Player.playing
            Text { width: parent.width; text: "Đang tạm dừng - đồng hồ cũng dừng."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        }
        Text {
            visible: Player.sleepStoppedText !== "" && Player.sleepKind === "off"
            width: parent.width
            text: "Hẹn giờ đã tắt tiếng lúc " + Player.sleepStoppedText + "."
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        Collapse {
            width: parent.width; open: Player.sleepStoppedText !== "" && Player.sleepKind === "off"
            Button { objectName: "sleepRestart"; text: "Bật lại " + Player.lastSleepMinutes + " phút"; kind: "ghost"; onClicked: { Player.setSleep("minutes", Player.lastSleepMinutes); root.close() } }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"
            Text { text: "Đặt lại"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        Flow {
            width: parent.width
            spacing: Theme.s8
            Repeater {
                model: Player.sleepChoices
                ChoiceChip {
                    required property var modelData
                    objectName: "sleepChoice_" + modelData
                    text: modelData + " phút"
                    selected: Player.sleepKind === "minutes" && Player.sleepMinutes === modelData
                    onClicked: { Player.setSleep("minutes", modelData); root.close() }
                }
            }
        }
        ChoiceChip {
            objectName: "sleepChapter"
            fullWidthReason: "Single-column menu (DESIGN 6)"
            width: parent.width
            text: "Hết chương này"
            selected: Player.sleepKind === "chapter"
            onClicked: { Player.setSleep("chapter"); root.close() }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"
            Row {
            spacing: Theme.s8
            Button {
                objectName: "sleepExtend"
                kind: "text"
                text: "+" + root.extendMinutes + " phút"
                visible: Player.sleepKind === "minutes"
                onClicked: Player.extendSleep()
            }
            Button {
                objectName: "sleepOff"
                kind: "text"
                text: "Tắt hẹn giờ"
                onClicked: { Player.setSleep("off"); root.close() }
            }
            }
        }
        Text {
            width: parent.width
            text: "Tiếng nhỏ dần " + root.fadeSeconds + " giây trước khi dừng. Lúc đó chạm phím hoặc chuột để nghe thêm " + root.extendMinutes + " phút."
            wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption
        }
    }
}
