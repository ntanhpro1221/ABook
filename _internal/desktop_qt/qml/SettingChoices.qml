import QtQuick
import ABook

// Hàng Cài đặt có nhóm lựa chọn bên phải: SettingRow + ChoiceRow (cách dùng của bản web: <SettingsRow label><ChoiceRow/></SettingsRow>).
// `choiceLabel`: tên đọc cho trình đọc màn hình khi khác nhãn ("Số phút nghe thêm").
SettingRow {
    id: root
    property var options: []
    property var value: ""
    property string choiceLabel: label
    signal picked(var value)
    ChoiceRow {
        width: Math.min(implicitWidth, root.width * 0.6)
        label: root.choiceLabel
        options: root.options
        value: root.value
        enabled: root.enabled
        onPicked: value => root.picked(value)
    }
}
