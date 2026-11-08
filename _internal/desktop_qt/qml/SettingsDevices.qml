import "UiStrings.js" as S
import QtQuick
import ABook

// Nhóm "Thiết bị" (DevicesGroup của desktop/SettingsScreen.tsx): hai khối "Máy này" và "Máy đã ghép" do PhoneSync tự dựng, rồi
// "Máy tính khác" (OtherComputers). Chữ và hành vi chép từng chữ từ bản web.
Column {
    id: root
    PhoneSync { id: phone; width: parent.width }
    SectionBlock {
        width: Theme.listWidth(parent, parent.width)
        title: S.s_may_tinh_khac_8c7c9cae
        SettingsItem {
            width: parent.width
            OtherComputers { id: computers; width: parent.width }
        }
    }
}
