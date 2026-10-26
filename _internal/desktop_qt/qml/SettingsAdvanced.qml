import QtQuick
import ABook

// Nhóm "Nâng cao" (AdvancedGroup của desktop/SettingsScreen.tsx).
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    SectionBlock {
        width: parent.width
        title: "Giới thiệu"
        fold: "advanced.about"
        SettingsItem { width: parent.width; FormLabel { width: parent.width; color: Theme.text2; text: "ABook " + (Api.info.version || "") + " - nghe sách tiếng Việt và làm sách nói." } }
    }
}
