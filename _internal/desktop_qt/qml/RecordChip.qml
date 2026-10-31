import QtQuick
import ABook

// Nút "Hồ sơ nghe: {tên}" dưới tiến độ của trang sách (nút của RecordPicker, listen/BookScreen.tsx): viên thuốc cao tối thiểu 32, icon người + nhãn + tên hồ sơ
// đang dùng + mũi tên; bấm mở danh sách hồ sơ. Chỉ có khi cuốn có từ hai hồ sơ trở lên (một hồ sơ thì việc ấy nằm ở menu "Thêm"). Tên dài xuống dòng, nút cao thêm.
Interactive {
    id: root
    property string name: ""
    property real maxWidth: 10000
    readonly property real extra: 12 + 14 + 6 + 6 + 14 + 12      // đệm, icon người, khe, khe, mũi tên, đệm
    Accessible.role: Accessible.Button
    Accessible.name: "Hồ sơ nghe: " + name
    implicitWidth: Math.min(maxWidth, labelText.implicitWidth + 4 + nameText.implicitWidth + extra)
    implicitHeight: Math.max(32, flow.height + 12)
    width: implicitWidth
    height: implicitHeight
    ringRadius: height / 2

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Theme.hover
        opacity: root.hovered || root.pressed ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: "transparent"
        border.width: 1
        border.color: Theme.line
    }
    Icon { x: 12; y: (root.height - 14) / 2; name: "user-round"; size: 14; color: Theme.text2 }
    Flow {
        id: flow
        x: 12 + 14 + 6
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(0, root.width - root.extra)
        spacing: 4
        Text {
            id: labelText
            text: "Hồ sơ nghe:"
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
        }
        Text {
            id: nameText
            objectName: "recordChipName"
            width: Math.min(implicitWidth, flow.width)
            text: root.name
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
            font.weight: Theme.weightMedium
        }
    }
    Icon { x: root.width - 12 - 14; y: (root.height - 14) / 2; name: "chevron-down"; size: 14; color: Theme.text2 }
}
