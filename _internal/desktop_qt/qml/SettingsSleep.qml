import "UiStrings.js" as S
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Nhóm "Hẹn giờ ngủ" (SleepGroup của desktop/SettingsScreen.tsx + desktop/SleepSchedule.tsx). Lịch đêm: phản hồi ngay cả khi PUT chậm (bản nháp `draft`
// hiện giá trị mới, ba ô và công tắc khoá tới khi máy chủ đáp); chỉ nhận thành công khi máy chủ trả đúng lịch đã gửi.
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    readonly property string extendGesture: S.s_cham_phim_hoac_chuot_95c35886    // EXTEND_GESTURE của máy tính có bàn phím / chuột
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
            if (!matches) Api.notice = S.s_chua_doi_duoc_lich_dem_may_chu_chua_nhan_l_778caf1e
        })
    }

    SectionBlock {
        width: parent.width
        SettingRow {
            width: parent.width
            label: S.s_lich_dem_5f61612f
            hint: S.s_may_ranh_2_phut_trong_khung_gio_nay_moi_tu_93ce72b6
            Switch {
                label: S.s_lich_dem_5f61612f
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
        // Bộ chọn giá trị (DESIGN mục 6): chip tiêu biểu + chọn tự do; miền ở ValuePickerLogic.SPECS, cùng hợp đồng với webui/library.py SLEEP_RANGES.
        SettingsItem {
            width: parent.width
            padding: 12
            ValuePicker {
                objectName: "sleepExtendPicker"
                width: parent.width
                dense: true
                spec: Logic.SPECS.sleepExtendMinutes
                value: root.prefs.sleepExtendMinutes ?? 10
                label: S.s_moi_lan_nghe_them_9a74fcef
                hint: S.s_luc_dang_nho_dan_7102c304 + root.extendGesture + "."
                format: Logic.minutesLabel
                enabled: Api.loaded
                onPicked: value => store.update({sleepExtendMinutes: value})
            }
        }
        SettingsItem {
            width: parent.width
            padding: 12
            ValuePicker {
                objectName: "sleepFadePicker"
                width: parent.width
                dense: true
                spec: Logic.SPECS.sleepFadeSeconds
                value: root.prefs.sleepFadeSeconds ?? 30
                label: S.s_nho_dan_ae8f3a2d
                format: Logic.secondsLabel
                enabled: Api.loaded
                onPicked: value => store.update({sleepFadeSeconds: value})
            }
        }
    }
}
