import QtQuick
import ABook

// Hộp thoại giữa màn (Dialog của shared/ui.tsx; DESIGN 6: máy tính = hộp giữa màn rộng <= 560): nền --panel, viền --line, bo 20, đệm 24,
// bóng lớp nổi. Đầu hộp: tên 18 đậm + mô tả 14 mực phụ, nút ✕ ("Đóng") ở góc. Thân cuộn trong hộp khi cao hơn cửa sổ (mép còn nội dung thì
// mờ dần), chân hộp (`footer`) tách khỏi thân bằng vạch, luôn thấy. Mở: nổi lên 10 px + phóng từ 96 % trong motionMedium (decelerate), nền
// mờ --scrim; đóng ngược lại trong motionMediumOut. Giảm chuyển động: chỉ mờ. Là một lớp của ngăn xếp Back; trang con trong hộp (tìm bìa...)
// tự mở lớp riêng của nó nên Back đóng trang con trước rồi mới tới hộp. Đóng thì trả tiêu điểm về chỗ đã mở hộp.
FocusScope {
    id: root
    anchors.fill: parent
    z: 70
    property bool open: false
    property string title: ""
    property string description: ""
    property real panelWidth: 512           // max-w-lg; hộp rộng hơn đặt 560
    property bool dismissable: true         // false: bấm ra ngoài không đóng (đang chạy việc không huỷ được)
    property var opener: null
    property real shown: open ? 1 : 0
    default property alias content: body.data
    property alias footer: footerBox.data
    readonly property bool hasFooter: footerBox.children.length > 0 && footerBox.childrenRect.height > 0
    readonly property real bodyWidth: panel.width - 48
    readonly property alias scroll: scroll
    signal closed()
    visible: shown > 0
    enabled: open

    function show() {
        if (open) return
        opener = Window.window ? Window.window.activeFocusItem : null
        open = true
        Nav.openLayer(root)
        forceActiveFocus(Qt.TabFocusReason)
        scroll.contentY = 0
    }
    // Back, ✕, bấm ra ngoài: cùng một đường. `keepOpen()` (tuỳ) trả true thì hộp ở lại - nó tự lùi một bậc bên trong (đóng trang con,
    // huỷ hỏi lại...). dismiss(): đóng thẳng, không hỏi.
    property var keepOpen: null
    function close() {
        if (!open) return
        if (keepOpen && keepOpen()) return
        dismiss()
    }
    function dismiss() {
        if (!open) return
        open = false
        Nav.closedLayer(root)
        if (opener && opener.forceActiveFocus) opener.forceActiveFocus(Qt.BacktabFocusReason)
        opener = null
        root.closed()
    }
    function containsItem(item) { for (let node = item; node; node = node.parent) if (node === root) return true; return false }
    Component.onDestruction: Nav.closedLayer(root)

    Behavior on shown {
        NumberAnimation {
            duration: root.open ? Theme.motionMedium : Theme.motionMediumOut
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }
    Rectangle { anchors.fill: parent; color: Theme.scrim; opacity: root.shown }
    MouseArea { anchors.fill: parent; onPressed: if (root.dismissable) root.close() }

    Item {
        id: panel
        width: Math.min(root.panelWidth, root.width - 32)
        height: Math.min(Math.max(root.height * 0.9, 0), Math.max(0, root.height - 32), heading.height + 16 + body.implicitHeight + footerArea.height + 48)
        x: (root.width - width) / 2
        y: (root.height - height) / 2 + (Theme.reduceMotion ? 0 : 10 * (1 - root.shown))
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.shown
        opacity: root.shown

        // Bóng lớp nổi (DESIGN 5.5) như Popover
        Rectangle { anchors.fill: parent; anchors.margins: -12; radius: Theme.radiusSheet + 12; color: "#000000"; opacity: 0.05 }
        Rectangle { anchors.fill: parent; anchors.margins: -4; anchors.topMargin: -2; anchors.bottomMargin: -8; radius: Theme.radiusSheet + 4; color: "#000000"; opacity: 0.08 }
        Rectangle { anchors.fill: parent; radius: Theme.radiusSheet; color: Theme.panel; border.width: 1; border.color: Theme.line }
        MouseArea { anchors.fill: parent }      // bấm trong hộp không đóng

        Column {
            id: heading
            x: 24
            y: 24
            width: panel.width - 48 - 44 - 16 + 17     // chừa nút ✕ (mực ✕ thẳng mép nội dung bên phải)
            spacing: 4
            Text { width: parent.width; text: root.title; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightBold }
            Text { width: parent.width; text: root.description; visible: text !== ""; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        }
        IconButton {
            id: closeButton
            objectName: "modalClose"
            x: panel.width - 24 - width + 17
            y: 24 - 12
            width: 44
            height: 44
            icon: "x"
            iconSize: 20
            ink: Theme.text3
            hoverInk: Theme.text
            tip: "Đóng"
            Accessible.name: "Đóng"
            onClicked: root.close()
        }
        Flickable {
            id: scroll
            x: 20
            y: heading.y + Math.max(heading.height, 20) + 16
            width: panel.width - 40
            height: panel.height - y - 24 - footerArea.height
            contentWidth: width
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column { id: body; x: 4; width: scroll.width - 8; spacing: 16 }
            SmoothWheel { flick: scroll }
        }
        ScrollEdges { target: scroll; color: Theme.panel; x: scroll.x; y: scroll.y; width: scroll.width; height: scroll.height }
        Scrollbar { target: scroll }
        Item {
            id: footerArea
            x: 24
            width: panel.width - 48
            y: panel.height - 24 - height
            height: root.hasFooter ? footerBox.childrenRect.height + 32 : 0
            Rectangle { y: 16; width: parent.width; height: 1; color: Theme.line; visible: root.hasFooter }
            Item { id: footerBox; y: 32; width: parent.width; height: childrenRect.height }
        }
    }
    // Tiêu điểm bàn phím ở trong hộp: Tab ra ngoài thì quay về đầu hộp.
    Keys.onTabPressed: event => {
        const current = Window.window ? Window.window.activeFocusItem : null
        const next = current ? current.nextItemInFocusChain() : null
        if (!next || !root.containsItem(next)) { closeButton.forceActiveFocus(Qt.TabFocusReason); event.accepted = true }
        else event.accepted = false
    }
}
