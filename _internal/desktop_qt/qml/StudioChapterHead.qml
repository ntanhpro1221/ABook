import "UiStrings.js" as S
import QtQuick
import ABook

// Hàng tiêu đề của bảng chương (hàng columnheader của ChapterList trong ProjectScreen.tsx): # · Chương · Trạng thái · Độ dài · Xong lúc, cùng cột với
// StudioChapterRow. Khổ hẹp hàng chương xếp trạng thái và độ dài xuống dưới tên, nên chỉ còn # và Chương.
Item {
    id: root
    readonly property bool wide: width >= 720
    readonly property real pad: 8
    readonly property real gap: 12
    readonly property real numberW: 48
    readonly property real titleX: pad + numberW + gap
    readonly property real moreX: width - pad - 32 + 4
    readonly property real doneX: moreX - gap - 96
    readonly property real lengthX: doneX - gap - 110
    readonly property real statusX: lengthX - gap - 150
    height: 36
    Accessible.role: Accessible.Row

    component Head: Text {
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text2
        elide: Text.ElideNone
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 0.72
        Accessible.role: Accessible.ColumnHeader
        Accessible.name: text
    }
    Head { x: root.pad; text: "#"; Accessible.name: S.s_so_chuong_6e52dccd }
    Head { x: root.titleX; text: S.s_chuong_2d157977 }
    Head { visible: root.wide; x: root.statusX; text: S.s_trang_thai_cb31de81 }
    Head {
        id: length
        visible: root.wide
        x: root.lengthX
        width: 110
        horizontalAlignment: Text.AlignRight
        text: S.s_do_dai_5e055f59
        HoverHandler {
            id: lengthHover
            onHoveredChanged: if (hovered) lengthTip.restart(); else { lengthTip.stop(); Nav.hideTip(length) }
        }
        Timer { id: lengthTip; interval: 600; onTriggered: Nav.showTip(length, S.s_so_phut_khi_chuong_da_co_audio_chua_co_thi_e936f4b1) }
        Accessible.description: S.s_so_phut_khi_chuong_da_co_audio_chua_co_thi_e936f4b1
    }
    Head { visible: root.wide; x: root.doneX; width: 96; horizontalAlignment: Text.AlignRight; text: S.s_xong_luc_e527f5af }
    Rectangle { x: root.pad; width: parent.width - 2 * root.pad; height: 1; anchors.bottom: parent.bottom; color: Theme.line }
}
