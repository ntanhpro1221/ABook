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
            label: "Tự lùi"
            hint: "Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây)."
            Switch { label: "Tự lùi"; checked: root.prefs.autoRewind !== false; onToggled: value => store.update({autoRewind: value}) }
        }
    }
    SectionBlock {
        width: parent.width
        title: "Nhạc nền"
        SettingRow {
            width: parent.width
            label: "Tự chọn nhạc nền"
            hint: "Sách chỉ có chữ: nhạc nhẹ đổi theo cảnh."
            Switch {
                label: "Tự chọn nhạc nền"
                checked: root.prefs.autoMusic !== false
                onToggled: value => store.update({autoMusic: value}, function(data, error) {
                    if (error) return
                    if (Api.transport) Api.transport.refreshLibrary()
                    Music.reload("*")           // cuốn đang nghe đổi nhạc ngay, không đợi chương sau
                    Api.notice = value ? "Đã bật tự chọn nhạc nền" : "Đã tắt tự chọn nhạc nền"
                })
            }
        }
        SettingsItem { width: parent.width; MyMusicSettings { width: parent.width } }
    }
}
