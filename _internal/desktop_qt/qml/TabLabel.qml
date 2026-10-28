import QtQuick
import ABook

// Chữ của một tab (TabLabel của shared/ui.tsx): tên + số nhỏ cạnh bên (nếu có) + mũi tên xuống cho nút "Thêm". Đang chọn thì mực đậm, không thì mực phụ.
Item {
    id: root
    property string text: ""
    property int count: 0
    property bool active: false
    property bool hovered: false
    property bool chevron: false
    implicitWidth: label.implicitWidth + (count > 0 ? countText.implicitWidth + 6 : 0) + (chevron ? 14 + 6 : 0)
    width: implicitWidth
    height: 44
    Text {
        id: label
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.active || root.hovered ? Theme.text : Theme.text2
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
    Text {
        id: countText
        visible: root.count > 0
        x: label.implicitWidth + 6
        anchors.verticalCenter: parent.verticalCenter
        text: root.count
        color: Theme.text3
        font.pixelSize: Theme.sizeCaption
        font.features: { "tnum": 1 }
    }
    Icon {
        visible: root.chevron
        x: parent.width - 14
        anchors.verticalCenter: parent.verticalCenter
        name: "chevron-down"
        size: 14
        color: Theme.text3
    }
}
