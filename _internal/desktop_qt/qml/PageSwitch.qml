import QtQuick
import ABook

// Công tắc vài lựa chọn ("Bìa" / "Đọc theo"; "Chương" / "Lịch sử" / "Nhân vật" của trang sách): nền chìm, khối sáng trượt sang lựa chọn mới.
// Mỗi lựa chọn rộng theo chữ của nó (chữ đậm vừa, để chọn rồi không làm công tắc nhảy); hai hay ba nhãn đều dùng một công tắc.
Item {
    id: root
    property var labels: ["", ""]
    property int index: 0
    property string label: "Bảng"
    Accessible.role: Accessible.PageTabList
    Accessible.name: label
    signal picked(int index)
    readonly property int count: labels.length
    // Chỗ và bề rộng của lựa chọn đang chọn: chính lựa chọn ấy báo lại mỗi khi nó đổi chỗ / đổi cỡ / được chọn
    property real thumbX: 0
    property real thumbW: 40
    property bool settled: false            // khối sáng chỉ trượt sau lần xếp đầu tiên
    Component.onCompleted: Later.call(root, function() { root.settled = true })
    property real stripEnd: 2               // mép phải lựa chọn cuối
    implicitWidth: stripEnd + 2
    onCountChanged: Later.call(root, function() {
        const last = tabs.itemAt(root.count - 1)
        if (last) root.stripEnd = last.x + last.width
    })
    implicitHeight: 36

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.sunken
    }
    Rectangle {
        x: 2 + root.thumbX
        y: 2
        width: root.thumbW
        height: root.height - 4
        radius: Theme.radiusControl
        color: Theme.panel
        Behavior on x {
            enabled: root.settled
            NumberAnimation {
                duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
        Behavior on width {
            enabled: root.settled
            NumberAnimation {
                duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
    }
    Repeater {
        id: tabs
        model: root.labels
        Interactive {
            id: tab
            required property int index
            required property var modelData
            readonly property string text: String(modelData === undefined || modelData === null ? "" : modelData)
            readonly property bool current: root.index === index
            // Các lựa chọn nối nhau từ mép trái: mỗi cái xếp sau cái trước, đổi cỡ thì đẩy cái sau; cái đang chọn báo chỗ cho khối sáng
            function place() {
                const before = index > 0 ? tabs.itemAt(index - 1) : null
                x = before ? before.x + before.width : 2
            }
            function sync() {
                if (current) { root.thumbX = x - 2; root.thumbW = width }
                if (index === root.count - 1) root.stripEnd = x + width
                const after = tabs.itemAt(index + 1)
                if (after) after.place()
            }
            y: 2
            onCurrentChanged: sync()
            onXChanged: sync()
            onWidthChanged: sync()
            Component.onCompleted: { place(); sync() }
            width: Math.max(40, metrics.advanceWidth + 2 * Theme.s12)
            height: root.height - 4
            pressScaling: false
            Accessible.role: Accessible.PageTab
            Accessible.name: text
            Accessible.checkable: true
            Accessible.checked: current
            activeFocusOnTab: current || activeFocus
            Keys.onPressed: event => {
                let next = -1
                if (event.key === Qt.Key_Left) next = (root.index + root.count - 1) % root.count
                else if (event.key === Qt.Key_Right) next = (root.index + 1) % root.count
                else if (event.key === Qt.Key_Home) next = 0
                else if (event.key === Qt.Key_End) next = root.count - 1
                if (next >= 0) { root.picked(next); tabs.itemAt(next).forceActiveFocus(); event.accepted = true }
            }
            ringRadius: Theme.radiusControl - 2
            onClicked: root.picked(index)
            TextMetrics { id: metrics; text: tab.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Text {
                anchors.centerIn: parent
                text: tab.text
                color: tab.current ? Theme.text : Theme.text2
                font.pixelSize: Theme.sizeBodySmall
                font.weight: tab.current ? Theme.weightMedium : Theme.weightRegular
            }
        }
    }
}
