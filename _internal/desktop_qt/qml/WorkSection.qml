import QtQuick
import ABook

// Nhóm phụ cuối hộp việc ("Đã quyết, chờ áp dụng", "Chờ phân tích lại", "Đã ghi" - các <details> của WorkInbox.tsx): vạch trên + dòng tên bấm để mở / khép, thân mở tại chỗ.
// `present`: nhóm có việc thì hiện (khép / mở tại chỗ khi thẻ vào ra); `expanded`: người dùng đã mở thân.
Item {
    id: root
    property bool present: false
    property bool expanded: false
    property string title: ""
    property string shownTitle: ""
    property real gap: 24
    default property alias inner: holder.data
    width: parent ? parent.width : 400
    height: outer.height
    visible: outer.height > 0
    onTitleChanged: if (title !== "") shownTitle = title

    Collapse {
        id: outer
        width: root.width
        open: root.present
        Item {
            width: parent.width
            height: root.gap + column.height
            Column {
                id: column
                y: root.gap
                width: parent.width
                Rectangle { width: parent.width; height: 1; color: Theme.line }
                Interactive {
                    id: toggle
                    objectName: "workSectionToggle"
                    width: parent.width
                    height: Math.max(44, label.height + 16)
                    Accessible.role: Accessible.Button
                    Accessible.name: root.shownTitle
                    Accessible.description: root.expanded ? "Đang mở" : "Đang đóng"
                    onClicked: root.expanded = !root.expanded
                    Text {
                        id: label
                        objectName: "workSectionTitle"
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 28
                        text: root.shownTitle
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                        font.weight: Theme.weightMedium
                    }
                    Icon {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        name: "chevron-right"
                        size: 16
                        color: Theme.text3
                        rotation: root.expanded ? 90 : 0
                        Behavior on rotation { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
                    }
                }
                Collapse {
                    id: body
                    width: parent.width
                    open: root.expanded
                    Column { id: holder; width: parent.width }
                }
            }
        }
    }
}
