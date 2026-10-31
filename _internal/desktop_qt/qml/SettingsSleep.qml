import QtQuick
import ABook

// Nhóm "Hẹn giờ ngủ" (SleepGroup của desktop/SettingsScreen.tsx + desktop/SleepSchedule.tsx). Lịch đêm: phản hồi ngay cả khi PUT chậm (bản nháp `draft`
// hiện giá trị mới, ba ô và công tắc khoá tới khi máy chủ đáp); chỉ nhận thành công khi máy chủ trả đúng lịch đã gửi.
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    readonly property string extendGesture: "chạm phím hoặc chuột"    // EXTEND_GESTURE của máy tính có bàn phím / chuột
    property var draft: null                  // {value: lịch | null} đang chờ máy chủ
    readonly property var schedule: draft ? draft.value : (prefs.sleepSchedule || null)
    readonly property var defaultSchedule: ({from: "22:00", to: "06:00", minutes: 30})
    ListenSave { id: store }

    function change(value) {
        if (!Api.loaded || draft !== null || Api.saving) return
        draft = {value: value}
        store.update({sleepSchedule: value}, function(data, error) {
            root.draft = null
            if (error) return
            const actual = data.sleepSchedule
            const matches = value === null ? !actual : Boolean(actual) && actual.from === value.from && actual.to === value.to && actual.minutes === value.minutes
            if (!matches) Api.notice = "Chưa đổi được lịch đêm\nMáy chủ chưa nhận lịch. Thử lại sau."
        })
    }

    SectionBlock {
        width: parent.width
        SettingChoices {
            width: parent.width
            label: "Tự tắt"
            hint: "Không ai chạm máy chừng này thì nhỏ dần rồi dừng."
            value: String(root.prefs.safetyStopHours ?? 2)
            options: [{value: "0", label: "Không"}, {value: "1", label: "1 giờ"}, {value: "2", label: "2 giờ"}, {value: "3", label: "3 giờ"}]
            onPicked: value => store.update({safetyStopHours: Number(value)})
        }
        SettingRow {
            width: parent.width
            label: "Lịch đêm"
            hint: "Nghe trong khung giờ này thì tự hẹn giờ."
            Switch {
                label: "Lịch đêm"
                checked: Boolean(root.schedule)
                enabled: Api.loaded && root.draft === null
                onToggled: value => root.change(value ? root.defaultSchedule : null)
            }
        }
        SleepWindow {
            width: parent.width
            schedule: root.schedule
            locked: root.draft !== null
            onChanged: value => root.change(value)
        }
        SettingChoices {
            width: parent.width
            label: "Mỗi lần nghe thêm"
            choiceLabel: "Số phút nghe thêm"
            hint: "Lúc đang nhỏ dần: " + root.extendGesture + "."
            value: String(root.prefs.sleepExtendMinutes ?? 10)
            options: [{value: "5", label: "5 phút"}, {value: "10", label: "10 phút"}, {value: "15", label: "15 phút"}]
            onPicked: value => store.update({sleepExtendMinutes: Number(value)})
        }
        SettingChoices {
            width: parent.width
            label: "Nhỏ dần"
            choiceLabel: "Độ dài nhỏ dần"
            value: String(root.prefs.sleepFadeSeconds ?? 30)
            options: [{value: "10", label: "10 giây"}, {value: "30", label: "30 giây"}, {value: "60", label: "1 phút"}]
            onPicked: value => store.update({sleepFadeSeconds: Number(value)})
        }
    }
}
