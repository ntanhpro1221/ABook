import "UiStrings.js" as S
import QtQuick
import ABook

// Nhóm "Nghe" (ListenGroup của desktop/SettingsScreen.tsx). "Nhạc của tôi" là kho chung mọi cuốn: ở đây, không chỉ trong hộp "Sửa sách" của từng cuốn.
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    ListenSave { id: store }
    SectionBlock {
        width: parent.width
        SettingRow {
            width: parent.width
            label: S.s_tu_lui_6fc7685a
            hint: S.s_nghi_qua_30_giay_thi_lui_5_giay_qua_10_phu_328c3ffd
            Switch { label: S.s_tu_lui_6fc7685a; checked: root.prefs.autoRewind !== false; onToggled: value => store.update({autoRewind: value}) }
        }
    }
    SectionBlock {
        width: parent.width
        title: S.s_nhac_nen_271fb292
        SettingRow {
            width: parent.width
            label: S.s_tu_chon_nhac_nen_a14c52b4
            hint: S.s_sach_chi_co_chu_nhac_nhe_doi_theo_canh_aef4ce0c
            Switch {
                label: S.s_tu_chon_nhac_nen_a14c52b4
                checked: root.prefs.autoMusic !== false
                onToggled: value => store.update({autoMusic: value}, function(data, error) {
                    if (error) return
                    if (Api.transport) Api.transport.refreshLibrary()
                    Music.reload("*")           // cuốn đang nghe đổi nhạc ngay, không đợi chương sau
                    Api.notice = value ? S.s_da_bat_tu_chon_nhac_nen_7c51e64e : S.s_da_tat_tu_chon_nhac_nen_5489759c
                })
            }
        }
        SettingsItem { width: parent.width; MusicOpenRow { width: parent.width } }
    }
}
