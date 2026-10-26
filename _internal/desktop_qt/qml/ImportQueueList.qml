import QtQuick
import ABook
import "ImportQueue.js" as Queue

// Danh sách các file đã chọn kèm tình trạng từng cái (QueueList của AddBook.tsx): cuốn đang xem đậm, cuốn đã thêm / đã có / đã mở có dấu ✓ xanh, cuốn bỏ qua có
// dấu trừ, cuốn lỗi có dấu cảnh báo kèm lý do, cuốn chờ có vòng rỗng. Tên file và lý do xuống dòng đủ, không cắt. Danh sách dài cuộn trong khung cao
// tối đa 144 (288 khi `tall`), mép còn nội dung thì mờ dần.
Item {
    id: root
    property var items: []
    property int currentId: -1
    property string working: ""
    property bool tall: false
    readonly property var spot: Queue.queueFocus(items, currentId, working)
    objectName: "importQueueList"
    implicitHeight: view.height + 20

    Flickable {
        id: view
        y: 10
        width: root.width
        height: Math.min(root.tall ? 288 : 144, column.height)
        contentWidth: width
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }

        Column {
            id: column
            width: view.width
            spacing: 6
            Repeater {
                model: root.items.length
                Item {
                    id: line
                    required property int index
                    readonly property var modelData: root.items[index] || ({})
                    readonly property bool current: modelData.state === "waiting" && modelData.id === root.spot.id
                    readonly property bool seen: line.y >= view.contentY && line.y + 16 <= view.contentY + view.height   // Shape không theo khung cắt của bộ vẽ phần mềm
                    readonly property string said: Queue.rowSaid(modelData, root.spot)
                    width: column.width
                    height: Math.max(names.height + saidText.height, 14)
                    Item {
                        x: 0
                        y: 2
                        width: 14
                        height: 14
                        // Dấu tình trạng: mỗi kiểu một lớp, đổi kiểu thì lớp cũ co lại + mờ đi, lớp mới nở ra (không bật tắt cứng)
                        Rectangle {
                            readonly property bool on: line.modelData.state === "waiting" && !line.current
                            anchors.centerIn: parent
                            width: 12; height: 12; radius: width / 2
                            color: "transparent"; border.width: 1; border.color: Theme.controlLine
                            opacity: on ? 1 : 0
                            scale: on || Theme.reduceMotion ? 1 : 0.5
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 12; height: 12; radius: width / 2
                            color: Theme.accent
                            opacity: line.current ? 1 : 0
                            scale: line.current || Theme.reduceMotion ? 1 : 0.5
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                        }
                        Icon {
                            readonly property bool on: ["added", "existing", "opened"].indexOf(line.modelData.state) >= 0
                            anchors.centerIn: parent
                            name: "check"; size: 14; color: Theme.success
                            visible: line.seen
                            opacity: on ? 1 : 0
                            scale: on || Theme.reduceMotion ? 1 : 0.5
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                        }
                        Icon {
                            readonly property bool on: line.modelData.state === "error"
                            anchors.centerIn: parent
                            name: "circle-alert"; size: 14; color: Theme.danger
                            visible: line.seen
                            opacity: on ? 1 : 0
                            scale: on || Theme.reduceMotion ? 1 : 0.5
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                        }
                        Icon {
                            readonly property bool on: line.modelData.state === "skipped"
                            anchors.centerIn: parent
                            name: "minus"; size: 14; color: Theme.text3
                            visible: line.seen
                            opacity: on ? 1 : 0
                            scale: on || Theme.reduceMotion ? 1 : 0.5
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                        }
                    }
                    Text {
                        id: names
                        objectName: "importQueueName"
                        x: 22
                        width: line.width - x
                        text: line.modelData.name
                        color: line.current ? Theme.text : Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                        font.weight: line.current ? 600 : Theme.weightRegular
                        textFormat: Text.PlainText
                    }
                    Text {
                        id: saidText
                        objectName: "importQueueSaid"
                        x: 22
                        y: names.height
                        width: line.width - x
                        text: line.said
                        color: line.modelData.state === "error" ? Theme.danger : Theme.text3
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                        textFormat: Text.PlainText
                    }
                }
            }
        }
    }
    ScrollEdges { target: view; color: Theme.panel; x: view.x; y: view.y; width: view.width; height: view.height }
    Scrollbar { target: view }
    SmoothWheel { flick: view }
}
