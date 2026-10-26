import QtQuick
import ABook

// Ô sách trong lưới (DESIGN.md mục 6, "Lưới bìa"): bìa 2:3 bo 12, tên dưới bìa tối đa 2 dòng, dòng phụ một dòng.
// Tiến độ nghe = vạch mảnh ở đáy bìa; sách của máy khác có nhãn nhỏ ở góc bìa.
Interactive {
    id: root
    property string title: ""
    property string subtitle: ""
    property string coverKey: ""
    property real progress: 0
    property string source: ""
    property real coverWidth: Theme.coverMin
    readonly property real coverHeight: Math.round(coverWidth * Theme.coverRatio)
    // Chiều cao khối chữ dưới bìa: 12 cách + 2 dòng tên + 4 + 1 dòng phụ
    readonly property real textBlock: 12 + 38 + 4 + 17

    activeFocusOnTab: false
    ringRadius: Theme.radiusCover
    ringHeight: coverHeight
    pressScaling: false
    implicitWidth: coverWidth
    implicitHeight: coverHeight + textBlock
    tip: title

    Item {
        id: cover
        width: root.coverWidth
        height: root.coverHeight
        // Rê chuột: bìa nhích lên 1,02; nhấn: thu 0,97 + tối 6 % (DESIGN.md 5.2). Chỉ transform / opacity.
        scale: root.pressed ? Theme.pressScale : (root.hovered && !Theme.reduceMotion ? 1.02 : 1)
        Behavior on scale {
            NumberAnimation {
                duration: root.pressed ? Theme.motionFastOut : Theme.motionFast
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
        CoverView {
            anchors.fill: parent
            coverKey: root.coverKey
            title: root.title
        }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: "#000000"
            opacity: root.pressed ? Theme.pressShade : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFastOut } }
        }
        Rectangle {          // vạch tiến độ
            visible: root.progress > 0.005 && root.progress < 0.995
            x: 8
            y: parent.height - 11
            width: parent.width - 16
            height: 3
            radius: 1.5
            color: "#66000000"
            Rectangle {
                width: parent.width * root.progress
                height: parent.height
                radius: parent.radius
                color: Theme.accent
            }
        }
        Rectangle {          // dấu nguồn: sách ở máy khác
            visible: root.source !== ""
            x: 8
            y: 8
            width: Math.min(parent.width - 16, sourceLabel.implicitWidth + 16)
            height: 22
            radius: 11
            color: "#a6000000"
            Text {
                id: sourceLabel
                anchors.centerIn: parent
                width: parent.width - 16
                text: root.source
                color: "#ffffff"
                font.pixelSize: Theme.sizeCaption
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
    Text {
        id: titleText
        x: 0
        y: root.coverHeight + 12
        width: root.coverWidth
        height: 38
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        lineHeight: 1.3
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
    Text {
        x: 0
        y: root.coverHeight + 12 + 38 + 4
        width: root.coverWidth
        text: root.subtitle
        color: Theme.text3
        elide: Text.ElideRight
        font.pixelSize: Theme.sizeCaption
    }
}
