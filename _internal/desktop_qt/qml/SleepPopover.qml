import "UiStrings.js" as S
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Hẹn giờ tắt: tắt sau N phút (giờ chỉ chạy khi có tiếng thật, dừng thì đứng) hay hết chương này. Đang hẹn: tắt sau bao lâu, hẹn lại N phút (về số đã chọn, không cộng thêm), tắt hẹn giờ. Chữ như bản web (SleepPicker).
Popover {
    id: root
    panelWidth: 296
    maxHeight: Math.max(280, Math.min(600, height - 32))
    readonly property int fadeSeconds: Logic.quantize(Logic.SPECS.sleepFadeSeconds, Number(Api.preferences.sleepFadeSeconds || 30))
    // N của nút "Hẹn lại N phút": số đã chọn khi hẹn phút, "Mỗi lần nghe thêm" khi hẹn theo chương (một nơi: Player::sleepExtendMinutes)
    readonly property int extendMinutes: Player.sleepExtendMinutes

    ClockUser { wanted: root.visible }

    Column {
        width: parent.width
        spacing: Theme.s12
        Collapse {
            width: parent.width; open: Player.sleepKind === "off"
            Text { width: parent.width; text: S.s_dung_phat_sau_41477737; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
        }
        // Đang hẹn: dòng nhỏ "Tắt sau" / "Dừng khi" trên đồng hồ đếm lùi lớn (như web SleepPicker).
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"; spacing: 2
            Text {
                objectName: "sleepCaption"
                width: parent.width
                text: Player.sleepKind === "chapter" ? S.s_dung_khi_f05a4cb5 : S.s_tat_sau_8d10e047
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "sleepCountdown"
                width: parent.width
                text: Player.sleepKind === "chapter" ? (Player.sleepChapters > 1 ? S.s_het_0_chuong_79433c77(Player.sleepChapters) : S.s_het_chuong_nay_8ccc288f) : Player.clockText(Player.clock.sleepLeft)
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeTitlePhone
                font.weight: 600
                font.features: { "tnum": 1 }
            }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind === "minutes" && !Player.playing
            Text { width: parent.width; text: S.s_dang_tam_dung_dong_ho_cung_dung_474889f9; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        }
        Text {
            visible: Player.sleepStoppedText !== "" && Player.sleepKind === "off"
            width: parent.width
            text: S.s_hen_gio_da_tat_tieng_luc_5d5e4231 + Player.sleepStoppedText + "."
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        Collapse {
            width: parent.width; open: Player.sleepStoppedText !== "" && Player.sleepKind === "off"
            Button { objectName: "sleepRestart"; text: S.s_bat_lai_0bad8bcf + Player.lastSleepMinutes + S.s_phut_cf728a6a; kind: "ghost"; onClicked: { Feedback.play("toggle"); Player.setSleep("minutes", Player.lastSleepMinutes); root.close() } }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"
            Text { text: S.s_dat_lai_51a46825; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        // Bộ chọn giá trị (DESIGN mục 6, chủ sách 09-11): chip tiêu biểu + chọn tự do 1-240 phút; hàng riêng dưới là "Hết chương này" / "Hết N chương".
        // Chọn là đặt ngay, bảng không tự đóng (kéo thước cần bảng đứng yên).
        ValuePicker {
            objectName: "sleepPicker"
            width: parent.width
            spec: Logic.SPECS.sleepMinutes
            value: Player.sleepKind === "minutes" ? Player.sleepMinutes : Player.lastSleepMinutes
            current: Player.sleepKind === "minutes"
            label: S.s_hen_gio_ngu_21073488
            format: Logic.minutesLabel
            chipLabel: function(v) { return String(v) }
            onPicked: value => { Feedback.play("toggle"); Player.setSleep("minutes", value) }
            // "Hết chương này", -/+ thành "Hết N chương" (N 1-10). Chạm tên là đặt; -/+ đổi N và đặt luôn.
            Row {
                id: chapterRow
                objectName: "sleepChapters"
                width: parent.width
                height: 40
                property int count: Player.sleepKind === "chapter" ? Math.max(1, Player.sleepChapters) : 1
                readonly property bool active: Player.sleepKind === "chapter" && Player.sleepChapters === count
                function pick(n) { count = n; Feedback.play("toggle"); Player.setSleep("chapter", n) }
                IconButton {
                    objectName: "sleepChaptersDown"; icon: "minus"; iconSize: 18; tip: S.s_giam_a6c2901a; Accessible.name: S.s_giam_a6c2901a
                    enabled: chapterRow.count > Logic.SPECS.sleepChapters.min; opacity: enabled ? 1 : 0.4
                    onClicked: chapterRow.pick(chapterRow.count - 1)
                }
                ChoiceChip {
                    objectName: "sleepChapter"
                    fullWidthReason: "Single-column menu (DESIGN 6)"
                    width: parent.width - 2 * Theme.buttonHeight
                    height: Theme.buttonHeight
                    text: chapterRow.count > 1 ? S.s_het_0_chuong_79433c77(chapterRow.count) : S.s_het_chuong_nay_918907cf
                    selected: chapterRow.active
                    onClicked: chapterRow.pick(chapterRow.count)
                }
                IconButton {
                    objectName: "sleepChaptersUp"; icon: "plus"; iconSize: 18; tip: S.s_tang_a2363bce; Accessible.name: S.s_tang_a2363bce
                    enabled: chapterRow.count < Logic.SPECS.sleepChapters.max; opacity: enabled ? 1 : 0.4
                    onClicked: chapterRow.pick(chapterRow.count + 1)
                }
            }
        }
        Collapse {
            width: parent.width; open: Player.sleepKind !== "off"
            Row {
            spacing: Theme.s8
            Button {
                objectName: "sleepExtend"
                kind: "text"
                text: S.s_hen_lai_c2aae1b7 + root.extendMinutes + S.s_phut_cf728a6a
                visible: Player.sleepKind === "minutes"
                onClicked: Player.extendSleep()
            }
            Button {
                objectName: "sleepOff"
                kind: "text"
                text: S.s_tat_hen_gio_fc8af231
                onClicked: { Feedback.play("toggle"); Player.setSleep("off"); root.close() }
            }
            }
        }
        Text {
            width: parent.width
            text: S.s_tieng_nho_dan_39149d9b + root.fadeSeconds + S.s_giay_truoc_khi_dung_luc_do_cham_phim_hoac_00cc036f
            wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption
        }
    }
}
