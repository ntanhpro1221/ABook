import QtQuick
import ABook

// Nhóm "Giao diện" (LookGroup của desktop/SettingsScreen.tsx).
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    SectionBlock {
        width: parent.width
        SettingChoices {
            width: parent.width
            label: "Màu"
            value: root.prefs.theme || "system"
            options: [{value: "system", label: "Tự động"}, {value: "light", label: "Sáng"}, {value: "dark", label: "Tối"}]
            onPicked: value => Api.update({theme: value})
        }
        SettingChoices {
            width: parent.width
            label: "Nền đọc"
            hint: "Nền của chữ khi đọc theo."
            value: root.prefs.readingSurface || "auto"
            options: [{value: "auto", label: "Tự động"}, {value: "paper", label: "Giấy"}, {value: "ivory", label: "Ngà"}, {value: "night", label: "Đêm"}]
            onPicked: value => Api.update({readingSurface: value})
        }
    }
}
