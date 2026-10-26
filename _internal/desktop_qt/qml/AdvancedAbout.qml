import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Nội dung khối "Giới thiệu" (phần cuối AdvancedGroup + ThirdPartyButton của desktop/SettingsScreen.tsx): tên + phiên bản, liên kết mã nguồn mở, và
// "Thành phần sử dụng" mở danh sách bên thứ ba trong một hộp (trang Cài đặt không dài thêm). Liên kết mở bằng trình duyệt của hệ điều hành.
Column {
    id: root
    objectName: "advancedAbout"
    property alias thirdDialog: third
    readonly property string sourceUrl: "https://github.com/ntanhpro1221/ABook/"
    spacing: 12
    Text {
        width: parent.width
        text: "ABook " + ((Api.info || {}).version || "") + " - nghe sách tiếng Việt và làm sách nói."
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
    Flow {
        width: parent.width
        Text {
            id: lead
            height: 24
            verticalAlignment: Text.AlignVCenter
            text: "Mã nguồn mở (MIT): "
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
        Interactive {
            id: link
            width: Math.min(linkText.implicitWidth, root.width)
            height: 24
            ringRadius: 2
            Accessible.role: Accessible.Link
            Accessible.name: "github.com/ntanhpro1221/ABook"
            onClicked: Qt.openUrlExternally(root.sourceUrl)
            Text {
                id: linkText
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                text: "github.com/ntanhpro1221/ABook"
                color: Theme.accentText
                wrapMode: Text.WrapAnywhere
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
                font.underline: true
            }
        }
    }
    DisclosureRow {
        width: parent.width
        title: "Thành phần sử dụng"
        onClicked: third.show()
    }
    Modal {
        id: third
        parent: C.Overlay.overlay
        title: "Thành phần sử dụng"
        panelWidth: 560
        ThirdPartyText { width: parent.width }
    }
}
