import "UiStrings.js" as S
import QtQuick
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
        text: S.s_abook_76b9d6fa + ((Api.info || {}).version || "") + S.s_nghe_sach_tieng_viet_va_lam_sach_noi_63eff2aa
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
            text: S.s_ma_nguon_mo_mit_4bf65cf1
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
        Interactive {
            id: link
            width: Math.min(linkText.implicitWidth, root.width)
            height: 24
            ringRadius: 2
            Accessible.role: Accessible.Link
            Accessible.name: S.s_github_com_ntanhpro1221_abook_da672a7c
            onClicked: Qt.openUrlExternally(root.sourceUrl)
            Text {
                id: linkText
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                text: S.s_github_com_ntanhpro1221_abook_da672a7c
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
        title: S.s_thanh_phan_su_dung_46f70f05
        onClicked: third.show()
    }
    Modal {
        id: third
        title: S.s_thanh_phan_su_dung_46f70f05
        panelWidth: 560
        ThirdPartyText { width: parent.width }
    }
}
