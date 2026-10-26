import QtQuick
import ABook

// Nhóm "Hẹn giờ ngủ" (SleepGroup của desktop/SettingsScreen.tsx + desktop/SleepSchedule.tsx).
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    SectionBlock {
        width: parent.width
        SettingChoices {
            width: parent.width
            label: "Tự tắt"
            hint: "Không ai chạm máy chừng này thì nhỏ dần rồi dừng."
            value: String(root.prefs.safetyStopHours ?? 2)
            options: [{value: "0", label: "Không"}, {value: "1", label: "1 giờ"}, {value: "2", label: "2 giờ"}, {value: "3", label: "3 giờ"}]
            onPicked: value => Api.update({safetyStopHours: Number(value)})
        }
        SettingChoices {
            width: parent.width
            label: "Mỗi lần nghe thêm"
            choiceLabel: "Số phút nghe thêm"
            hint: "Lúc đang nhỏ dần: chạm phím hoặc chuột."
            value: String(root.prefs.sleepExtendMinutes ?? 10)
            options: [{value: "5", label: "5 phút"}, {value: "10", label: "10 phút"}, {value: "15", label: "15 phút"}]
            onPicked: value => Api.update({sleepExtendMinutes: Number(value)})
        }
        SettingChoices {
            width: parent.width
            label: "Nhỏ dần"
            choiceLabel: "Độ dài nhỏ dần"
            value: String(root.prefs.sleepFadeSeconds ?? 30)
            options: [{value: "10", label: "10 giây"}, {value: "30", label: "30 giây"}, {value: "60", label: "1 phút"}]
            onPicked: value => Api.update({sleepFadeSeconds: Number(value)})
        }
    }
}
