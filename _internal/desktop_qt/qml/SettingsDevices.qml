import QtQuick
import ABook

// Nhóm "Thiết bị" (DevicesGroup của desktop/SettingsScreen.tsx): hai khối "Máy này" và "Máy đã ghép" do PhoneSync tự dựng, rồi
// "Máy tính khác" (OtherComputers). Chữ và hành vi chép từng chữ từ bản web.
Column {
    id: root
    PhoneSync { id: phone; width: parent.width }
    SectionBlock {
        width: parent.width
        title: "Máy tính khác"
        SettingsItem {
            width: parent.width
            OtherComputers { id: computers; width: parent.width }
        }
    }
}
