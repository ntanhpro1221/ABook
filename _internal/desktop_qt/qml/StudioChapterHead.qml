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
        font.weight: Font.DemiBold
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 0.72
        Accessible.role: Accessible.ColumnHeader
        Accessible.name: text
    }
    Head { x: root.pad; text: "#"; Accessible.name: "Số chương" }
    Head { x: root.titleX; text: "Chương" }
    Head { visible: root.wide; x: root.statusX; text: "Trạng thái" }
    Head {
        id: length
        visible: root.wide
        x: root.lengthX
        width: 110
        horizontalAlignment: Text.AlignRight
        text: "Độ dài"
        HoverHandler {
            id: lengthHover
            onHoveredChanged: if (hovered) lengthTip.restart(); else { lengthTip.stop(); Nav.hideTip(length) }
        }
        Timer { id: lengthTip; interval: 600; onTriggered: Nav.showTip(length, "Số phút khi chương đã có audio; chưa có thì số câu của chương") }
        Accessible.description: "Số phút khi chương đã có audio; chưa có thì số câu của chương"
    }
    Head { visible: root.wide; x: root.doneX; width: 96; horizontalAlignment: Text.AlignRight; text: "Xong lúc" }
    Rectangle { x: root.pad; width: parent.width - 2 * root.pad; height: 1; anchors.bottom: parent.bottom; color: Theme.line }
}
