import "UiStrings.js" as S
import QtQuick
import ABook

// Nhóm "Studio" (StudioGroup của desktop/SettingsScreen.tsx, máy này - không phải Studio từ xa). Trạng thái Studio (đã cài / chưa cài + Gỡ
// hay Cài) ở đầu nhóm cùng việc của riêng máy này; chưa cài thì các tuỳ chọn vẫn xem và chỉnh được, có một dòng nói rõ.
// `studioRequested`: màn Studio (xem tiến độ cài, Sửa / Cập nhật Studio) - chỗ gắn là Main.qml.
Column {
    id: root
    signal studioRequested()
    SectionBlock {
        width: parent.width
        title: S.s_may_nay_4668c138
        StudioSettings { width: parent.width; onStudioRequested: root.studioRequested() }
        SettingRow {
            width: parent.width
            label: S.s_tam_dung_dung_pin_8786ee21
            hint: S.s_cam_sac_lai_thi_tu_lam_tiep_dung_cho_ce18fa7b
            Switch {
                objectName: "pauseOnBattery"
                label: S.s_tam_dung_dung_pin_8786ee21
                checked: Api.preferences.pauseOnBattery !== false
                onToggled: value => Api.update({pauseOnBattery: value})
            }
        }
    }
    Collapse {
        width: parent.width
        open: !(Api.info && Api.info.studio && Api.info.studio.installed)
        Text { objectName: "notInstalledNote"; width: parent.width; topPadding: 8; text: S.s_tuy_chon_o_trang_nay_dung_khi_da_cai_studi_f1c313c4; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: 13 }
    }
    SectionBlock {
        width: parent.width
        title: S.s_sach_moi_099947f8
        fold: "studio.new-book"
        NewBookDefaults { width: parent.width }
        SettingsItem { width: parent.width; BookTemplates { width: Math.min(parent.width, 576) } }
    }
    SectionBlock {
        width: parent.width
        title: S.s_cach_doc_chung_a7e00c51
        fold: "studio.shared-readings"
        SharedReadingsSettings { width: parent.width }
    }
}
