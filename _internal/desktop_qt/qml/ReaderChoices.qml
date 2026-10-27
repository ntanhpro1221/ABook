import QtQuick
import ABook

// Một nhóm lựa chọn của hộp "Cỡ chữ và giãn dòng" ở màn đọc (ReaderScreen.tsx): nhãn nhỏ mực phụ, các nút chia đều một hàng (lưới N cột, cách 4),
// chữ trái 14, mục đang chọn màu nhấn (Giãn dòng: đậm thêm) + gạch chân hổ phách 2 px trượt giữa các mục (SlidingIndicator "line"), rê chuột nền
// hover. Giảm chuyển động: gạch nhảy, không trượt. Mũi tên trái / phải đổi lựa chọn.
Column {
    id: root
    property string label: ""
    property var options: []          // [{value, label, name}]
    property var value: null
    property bool boldSelected: false
    signal picked(var value)
    readonly property int currentIndex: {
        for (let i = 0; i < options.length; ++i) if (options[i].value === value) return i
        return -1
    }
    spacing: 6

    Text {
        width: root.width
        text: root.label
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
    }
    Item {
        id: grid
        width: root.width
        height: 36
        Accessible.role: Accessible.Grouping
        Accessible.name: root.label
        readonly property real cell: (width - 4 * (root.options.length - 1)) / Math.max(1, root.options.length)
        Repeater {
            id: repeater
            model: root.options
            Interactive {
                id: choice
                required property var modelData
                required property int index
                readonly property bool selected: index === root.currentIndex
                readonly property real wordWidth: word.implicitWidth
                objectName: "readerChoice"
                x: index * (grid.cell + 4)
                width: grid.cell
                height: grid.height
                pressScaling: false
                Accessible.role: Accessible.Button
                Accessible.name: modelData.name
                Accessible.checked: selected
                onClicked: root.picked(modelData.value)
                Keys.onRightPressed: if (index + 1 < root.options.length) root.picked(root.options[index + 1].value)
                Keys.onLeftPressed: if (index > 0) root.picked(root.options[index - 1].value)
                Rectangle {
                    anchors.fill: parent
                    radius: Theme.radiusControl
                    color: Theme.hover
                    opacity: choice.hovered && !choice.selected ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Text {
                    id: word
                    anchors.verticalCenter: parent.verticalCenter
                    text: choice.modelData.label
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: choice.selected && root.boldSelected ? 600 : (root.boldSelected ? Theme.weightRegular : Theme.weightMedium)
                    font.features: { "tnum": 1 }
                    color: choice.selected ? Theme.accentText : Theme.text
                    Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
                }
            }
        }
        // Gạch chân của mục đang chọn: dưới đúng chữ của mục, trượt (x, bề ngang) khi đổi mục
        Rectangle {
            objectName: "readerChoiceLine"
            readonly property Item target: repeater.count > 0 && root.currentIndex >= 0 ? repeater.itemAt(root.currentIndex) : null
            visible: target !== null
            x: target ? target.x : 0
            y: grid.height - height
            width: target ? target.wordWidth : 0
            height: 2
            color: Theme.accent
            Behavior on x { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        }
    }
}
