import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Hàng tab của một dự án (ProjectTabBar của ProjectScreen.tsx): năm tab hiện thẳng (Chương · Việc cần duyệt · Cần nghe lại · Nhân vật · Nhạc nền), còn lại
// (Duyệt trước khi thu, Kịch bản, Nhật ký) vào "Thêm". Tab đang chọn nằm trong "Thêm" thì nút "Thêm" mang tên tab ấy và gạch chân như tab thường.
// Gạch chân trượt sang tab mới. Hàng hẹp hơn các tab thì cuộn ngang, không cắt.
Item {
    id: root
    property string tab: "chapters"
    property bool precast: false
    property var counts: ({})
    signal picked(string key)
    signal moreRequested(Item anchor)

    readonly property bool inMore: Logic.moreTabs(precast).indexOf(tab) >= 0
    readonly property alias moreButton: moreTab
    implicitHeight: 44
    height: 44
    Accessible.role: Accessible.PageTabList
    Accessible.name: "Mục của dự án"

    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
    Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: row.width
        contentHeight: height
        interactive: contentWidth > width
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Row {
            id: row
            spacing: 20
            Repeater {
                id: tabs
                model: Logic.MAIN_TABS
                delegate: Interactive {
                    id: tabButton
                    required property string modelData
                    readonly property bool active: root.tab === modelData
                    objectName: "tab_" + modelData
                    height: 44
                    width: label.implicitWidth
                    pressScaling: false
                    Accessible.role: Accessible.PageTab
                    Accessible.name: Logic.TAB_LABEL[modelData]
                    onClicked: root.picked(modelData)
                    TabLabel { id: label; active: tabButton.active; hovered: tabButton.hovered; text: Logic.TAB_LABEL[tabButton.modelData]; count: root.counts[tabButton.modelData] || 0 }
                }
            }
            Interactive {
                id: moreTab
                objectName: "tab_more"
                height: 44
                width: moreLabel.implicitWidth
                pressScaling: false
                Accessible.role: Accessible.Button
                Accessible.name: moreLabel.text
                onClicked: root.moreRequested(moreTab)
                TabLabel {
                    id: moreLabel
                    objectName: "tab_moreLabel"
                    active: root.inMore
                    hovered: moreTab.hovered
                    text: Logic.moreLabel(root.tab, root.precast)
                    count: Logic.moreCount(root.tab, root.precast, root.counts)
                    chevron: true
                }
            }
        }
    }
    // Gạch chân: trượt tới tab đang chọn
    Rectangle {
        id: underline
        objectName: "tabUnderline"
        property Item holder: { tabs.count; return root.inMore ? moreTab : tabs.itemAt(Math.max(0, Logic.MAIN_TABS.indexOf(root.tab))) }
        x: holder ? holder.x - scroller.contentX : 0
        width: holder ? holder.width : 0
        y: parent.height - 2
        height: 2
        color: Theme.accent
        Behavior on x { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
