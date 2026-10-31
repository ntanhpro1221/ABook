import QtQuick
import ABook

// Một mục nhật ký của hộp Chẩn đoán (LogBox của shared/DiagnosticsView.tsx, <details>): hàng tên (14/500, mũi tên xoay) bấm gập / mở tại chỗ;
// thân là khung cuộn cao tối đa 288, chữ 11 chọn được, cuộn sẵn xuống cuối (dòng mới nhất là dòng cần xem trước). Không có dòng thì một câu 12.
Column {
    id: root
    property string title: ""
    property var lines: []
    property string empty: ""
    property bool startOpen: false
    property bool open: startOpen
    Interactive {
        id: head
        width: parent.width
        implicitHeight: Math.max(40, label.implicitHeight + 16)
        pressScaling: false
        Accessible.role: Accessible.Button
        Accessible.name: root.title
        onClicked: root.open = !root.open
        Icon {
            id: chevron
            anchors.verticalCenter: parent.verticalCenter
            name: "chevron-right"
            size: 14
            color: Theme.text3
            rotation: root.open ? 90 : 0
            Behavior on rotation { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        }
        Text {
            id: label
            x: 14 + 8
            width: parent.width - x
            anchors.verticalCenter: parent.verticalCenter
            text: root.title
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
        }
    }
    Collapse {
        width: parent.width
        open: root.open
        Rectangle { width: parent.width; height: 1; color: Theme.line }
        Item {
            width: parent.width
            visible: root.lines.length > 0
            height: visible ? Math.min(288, log.contentHeight + 16) : 0
            Flickable {
                id: log
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                clip: true
                contentWidth: width
                contentHeight: logText.height
                boundsBehavior: Flickable.StopAtBounds
                function toEnd() { contentY = Math.max(0, contentHeight - height) }
                onContentHeightChanged: toEnd()
                onHeightChanged: toEnd()
                SmoothWheel { flick: log }
                TextEdit {
                    id: logText
                    width: log.width
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.WrapAnywhere
                    color: Theme.text2
                    font.family: "monospace"
                    font.pixelSize: 11
                    text: root.lines.join("\n")
                }
            }
            Scrollbar { target: log }
        }
        Text {
            width: parent.width
            visible: root.lines.length === 0
            topPadding: 8
            bottomPadding: 8
            text: root.empty
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
}
