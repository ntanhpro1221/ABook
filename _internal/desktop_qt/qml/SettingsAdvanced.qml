import QtQuick
import ABook

// Nhóm "Nâng cao" (AdvancedGroup của desktop/SettingsScreen.tsx): Thư viện, Cập nhật, Bộ nhớ, Chẩn đoán, Giới thiệu. Khối nào hiện theo máy này
// (không điều khiển từ xa; app Qt luôn có hộp chọn thư mục của hệ điều hành) và mở / khép tại chỗ.
Column {
    id: root
    readonly property var prefs: Api.preferences || {}
    readonly property var info: Api.info || {}
    readonly property bool remote: Boolean(info.remote)
    ListenSave { id: store }

    // Đổi thư mục thư viện: báo "đã đổi" chỉ khi máy chủ đã nhận; bị từ chối thì ListenSave báo lý do và đường dẫn cũ ở nguyên
    function useLibrary(path) {
        if (!path) return
        store.update({libraryRoot: path}, function(data, error) {
            if (error) return
            Api.notice = "Đã đổi thư mục thư viện"
            DesktopApi.refreshLibrary()
        })
    }
    NativeFolders { id: folders; onPicked: path => root.useLibrary(path) }

    Collapse {
        width: parent.width
        open: !root.info.listenOnly
        SectionBlock {
            width: parent.width
            title: "Thư viện"
            SettingsItem {
                id: library
                width: parent.width
                padding: 12
                // Đường dẫn dài xuống dòng, không cắt (bản web cắt bằng truncate + title; luật của chủ app: không cắt chữ người dùng)
                readonly property bool sameLine: width >= 192 + 8 + change.width - 12
                readonly property real pathWidth: sameLine ? width - change.width + 12 - 8 : width
                Item {
                    width: parent.width
                    height: library.sameLine ? Math.max(path.height, change.height) : path.height + 8 + change.height
                    Row {
                        id: path
                        width: library.pathWidth
                        spacing: 12
                        height: Math.max(40, label.implicitHeight + 8)
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "folder-open"; size: 16; color: Theme.text2 }
                        Text {
                            id: label
                            anchors.verticalCenter: parent.verticalCenter
                            width: path.width - 16 - path.spacing
                            text: root.prefs.libraryRoot || ""
                            color: Theme.text2
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                        }
                    }
                    // Chữ nút thẳng mép phải cột (settings-edge-action: bù đệm ngang 12 của nút sm)
                    Button {
                        id: change
                        x: parent.width - width + 12
                        y: library.sameLine ? (parent.height - height) / 2 : path.height + 8
                        text: "Đổi thư mục"; kind: "ghost"; size: "sm"; wrap: true
                        onClicked: folders.choose("Chọn thư mục thư viện", root.prefs.libraryRoot || "")
                    }
                }
            }
        }
    }
    Collapse {
        width: parent.width
        open: !root.remote && Boolean(root.info.update || root.info.canCheckUpdate)
        SectionBlock {
            width: parent.width
            title: "Cập nhật"
            SettingsItem { width: parent.width; padding: 0; AdvancedUpdate { width: parent.width } }
        }
    }
    SectionBlock {
        width: parent.width
        title: "Bộ nhớ"
        visible: !root.remote
        SettingsItem { width: parent.width; padding: 0; AdvancedStorage { width: parent.width } }
    }
    SectionBlock {
        width: parent.width
        title: "Chẩn đoán"
        fold: "advanced.diagnostics"
        visible: !root.remote
        SettingsItem { width: parent.width; AdvancedDiagnostics { width: parent.width } }
    }
    SectionBlock {
        width: parent.width
        title: "Giới thiệu"
        fold: "advanced.about"
        SettingsItem { width: parent.width; AdvancedAbout { width: parent.width } }
    }
}
