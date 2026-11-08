import "UiStrings.js" as S
import QtQuick
import ABook

// Nhóm "Giao diện" (LookGroup của desktop/SettingsScreen.tsx; máy này không điều khiển từ xa, có bàn phím nên đủ hai khối).
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    ListenSave { id: store }
    SectionBlock {
        width: parent.width
        SettingRow {
            width: parent.width
            label: S.s_thu_vao_khay_khi_dong_8596fce2
            Switch { label: S.s_thu_vao_khay_khi_dong_8596fce2; checked: Nav.windowMode ? Nav.windowMode.closeToTray : true; onToggled: value => { if (Nav.windowMode) Nav.windowMode.closeToTray = value } }
        }
        SettingRow {
            width: parent.width
            label: S.s_tu_mo_cua_so_mini_a93a51d2
            Switch { label: S.s_tu_mo_cua_so_mini_a93a51d2; checked: Nav.windowMode ? Nav.windowMode.autoMini : true; onToggled: value => { if (Nav.windowMode) Nav.windowMode.autoMini = value } }
        }
        SettingChoices {
            width: parent.width
            label: S.s_mau_bf45a510
            value: root.prefs.theme || "system"
            options: [{value: "system", label: S.s_tu_dong_a25c8028}, {value: "light", label: S.s_sang_8f0c677d}, {value: "dark", label: S.s_toi_4ac2d267}]
            onPicked: value => store.update({theme: value})
        }
        SettingChoices {
            width: parent.width
            label: S.s_nen_doc_25ec1519
            hint: S.s_nen_cua_chu_khi_doc_theo_d0cbef86
            value: ["auto", "paper", "ivory", "night"].indexOf(root.prefs.readingSurface) >= 0 ? root.prefs.readingSurface : "auto"
            options: [{value: "auto", label: S.s_tu_dong_a25c8028}, {value: "paper", label: S.s_giay_702e14de}, {value: "ivory", label: S.s_nga_370ffbed}, {value: "night", label: S.s_dem_98ef3f93}]
            onPicked: value => store.update({readingSurface: value})
        }
        SettingRow {
            width: parent.width
            label: S.s_am_thanh_cham_a33e2a3c
            hint: S.s_tieng_khe_khi_ban_chon_im_khi_dang_nghe_b844543e
            Switch { label: S.s_am_thanh_cham_a33e2a3c; checked: root.prefs.touchSounds !== false; onToggled: value => store.update({touchSounds: value}) }
        }
    }
    SectionBlock {
        width: parent.width
        title: S.s_phim_tat_7baaed2f
        SettingRow {
            width: parent.width
            label: S.s_phim_tat_chu_f1e88b8a
            hint: S.s_tat_neu_hay_lo_cham_phim_hay_nhap_bang_gio_03fe0a14
            Switch { label: S.s_phim_tat_chu_f1e88b8a; checked: root.prefs.letterShortcuts !== false; onToggled: value => store.update({letterShortcuts: value}) }
        }
        SettingsItem {
            width: parent.width
            padding: 12
            LookShortcuts { width: parent.width; letters: root.prefs.letterShortcuts !== false }
        }
    }
}
