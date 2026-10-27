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
            label: "Thu vào khay khi đóng"
            Switch { label: "Thu vào khay khi đóng"; checked: Nav.windowMode ? Nav.windowMode.closeToTray : true; onToggled: value => { if (Nav.windowMode) Nav.windowMode.closeToTray = value } }
        }
        SettingRow {
            width: parent.width
            label: "Tự mở cửa sổ mini"
            Switch { label: "Tự mở cửa sổ mini"; checked: Nav.windowMode ? Nav.windowMode.autoMini : true; onToggled: value => { if (Nav.windowMode) Nav.windowMode.autoMini = value } }
        }
        SettingChoices {
            width: parent.width
            label: "Màu"
            value: root.prefs.theme || "system"
            options: [{value: "system", label: "Tự động"}, {value: "light", label: "Sáng"}, {value: "dark", label: "Tối"}]
            onPicked: value => store.update({theme: value})
        }
        SettingChoices {
            width: parent.width
            label: "Nền đọc"
            hint: "Nền của chữ khi đọc theo."
            value: ["auto", "paper", "ivory", "night"].indexOf(root.prefs.readingSurface) >= 0 ? root.prefs.readingSurface : "auto"
            options: [{value: "auto", label: "Tự động"}, {value: "paper", label: "Giấy"}, {value: "ivory", label: "Ngà"}, {value: "night", label: "Đêm"}]
            onPicked: value => store.update({readingSurface: value})
        }
        SettingRow {
            width: parent.width
            label: "Âm thanh chạm"
            hint: "Tiếng khẽ khi bạn chọn. Im khi đang nghe."
            Switch { label: "Âm thanh chạm"; checked: root.prefs.touchSounds !== false; onToggled: value => store.update({touchSounds: value}) }
        }
    }
    SectionBlock {
        width: parent.width
        title: "Phím tắt"
        SettingRow {
            width: parent.width
            label: "Phím tắt chữ"
            hint: "Tắt nếu hay lỡ chạm phím hay nhập bằng giọng nói."
            Switch { label: "Phím tắt chữ"; checked: root.prefs.letterShortcuts !== false; onToggled: value => store.update({letterShortcuts: value}) }
        }
        SettingsItem {
            width: parent.width
            padding: 12
            LookShortcuts { width: parent.width; letters: root.prefs.letterShortcuts !== false }
        }
    }
}
