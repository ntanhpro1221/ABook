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
        title: "Máy này"
        StudioSettings { width: parent.width; onStudioRequested: root.studioRequested() }
        SettingRow {
            width: parent.width
            label: "Tạm dừng dùng pin"
            hint: "Cắm sạc lại thì tự làm tiếp đúng chỗ."
            Switch {
                objectName: "pauseOnBattery"
                label: "Tạm dừng dùng pin"
                checked: Api.preferences.pauseOnBattery !== false
                onToggled: value => Api.update({pauseOnBattery: value})
            }
        }
    }
    Collapse {
        width: parent.width
        open: !(Api.info && Api.info.studio && Api.info.studio.installed)
        Text { objectName: "notInstalledNote"; width: parent.width; topPadding: 8; text: "Tuỳ chọn ở trang này dùng khi đã cài Studio."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: 13 }
    }
    SectionBlock {
        width: parent.width
        title: "Sách mới"
        fold: "studio.new-book"
        NewBookDefaults { width: parent.width }
        SettingsItem { width: parent.width; BookTemplates { width: Math.min(parent.width, 576) } }
    }
    SectionBlock {
        width: parent.width
        title: "Cách đọc chung"
        fold: "studio.shared-readings"
        SharedReadingsSettings { width: parent.width }
    }
}
