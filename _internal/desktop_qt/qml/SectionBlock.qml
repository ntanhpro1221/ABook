import QtQuick
import ABook

// Khối phẳng của một nhóm Cài đặt (SettingsBlock của shared/SettingsNav.tsx): cách 32 với thứ phía trên, tiêu đề mục 18/500 trong hàng cao 56,
// các mục có vạch chia giữa nhau (SettingsItem / SettingRow tự vẽ). `fold` (khoá nhớ): khối ít dùng gập sau tiêu đề bấm được (DisclosureRow
// kiểu mục), mở rồi thì lần sau vẫn mở (Platform.setting "fold.settings.<khoá>", như localStorage abook.fold.* của web).
Column {
    id: root
    property string title: ""
    property string fold: ""
    property bool expanded: fold === "" || Platform.setting("fold.settings." + fold, "0") === "1"
    default property alias rows: body.content
    topPadding: Theme.s32
    Text {
        visible: root.title !== "" && root.fold === ""
        width: parent.width
        height: Math.max(56, implicitHeight)
        verticalAlignment: Text.AlignVCenter
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeSection
        font.weight: Theme.weightMedium
    }
    DisclosureRow {
        visible: root.title !== "" && root.fold !== ""
        width: parent.width
        section: true
        title: root.title
        expanded: root.expanded
        onClicked: {
            root.expanded = !root.expanded
            Platform.setSetting("fold.settings." + root.fold, root.expanded ? "1" : "0")
        }
    }
    Collapse {
        id: body
        width: parent.width
        open: root.expanded
    }
}
