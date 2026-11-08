import "UiStrings.js" as S
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
        SettingChoices {
            width: parent.width
            label: S.s_tu_tat_d7ae4633
            hint: S.s_may_ranh_du_lau_moi_nho_dan_roi_dung_a273f5e3
            value: String(root.prefs.safetyStopHours ?? 2)
            options: [{value: "0", label: S.s_khong_5b3c9ba4}, {value: "1", label: S.s_1_gio_d06edd9a}, {value: "2", label: S.s_2_gio_081d2a06}, {value: "3", label: S.s_3_gio_cefc3cb2}]
            onPicked: value => store.update({safetyStopHours: Number(value)})
        }
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
        SettingChoices {
            width: parent.width
            label: S.s_moi_lan_nghe_them_9a74fcef
            choiceLabel: S.s_so_phut_nghe_them_92256232
            hint: S.s_luc_dang_nho_dan_7102c304 + root.extendGesture + "."
            value: String(root.prefs.sleepExtendMinutes ?? 10)
            options: [{value: "5", label: S.s_5_phut_e98d21d5}, {value: "10", label: S.s_10_phut_ed33fe6a}, {value: "15", label: S.s_15_phut_43786c01}]
            onPicked: value => store.update({sleepExtendMinutes: Number(value)})
        }
        SettingChoices {
            width: parent.width
            label: S.s_nho_dan_ae8f3a2d
            choiceLabel: S.s_do_dai_nho_dan_7c53ef6a
            value: String(root.prefs.sleepFadeSeconds ?? 30)
            options: [{value: "10", label: S.s_10_giay_942f8aa9}, {value: "30", label: S.s_30_giay_03dbee33}, {value: "60", label: S.s_1_phut_eca10dbb}]
            onPicked: value => store.update({sleepFadeSeconds: Number(value)})
        }
    }
}
