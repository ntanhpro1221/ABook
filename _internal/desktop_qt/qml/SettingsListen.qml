import QtQuick
import ABook

// Nhóm "Nghe" (ListenGroup của desktop/SettingsScreen.tsx).
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    SectionBlock {
        width: parent.width
        SettingRow {
            width: parent.width
            label: "Tự lùi"
            hint: "Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây)."
            Switch { label: "Tự lùi"; checked: root.prefs.autoRewind !== false; onToggled: value => Api.update({autoRewind: value}) }
        }
    }
    SectionBlock {
        width: parent.width
        title: "Nhạc nền"
        SettingRow {
            width: parent.width
            label: "Tự chọn nhạc nền"
            hint: "Sách chỉ có chữ: nhạc nhẹ đổi theo cảnh."
            Switch { label: "Tự chọn nhạc nền"; checked: root.prefs.autoMusic !== false; onToggled: value => Api.update({autoMusic: value}) }
        }
        SettingsItem { width: parent.width; MyMusicSettings { width: parent.width } }
    }
}
