import QtQuick
import ABook

// Vùng lời báo của app (Toaster của desktop/App.tsx: sonner, góc trên bên phải, visibleToasts 2, closeButton; styles.css viết lại cỡ chữ / ✕ / nút).
// Mỗi thẻ: tiêu đề một dòng (xuống dòng, không bao giờ cắt), MỘT nút (việc của thẻ: "Hoàn tác", "Mở thư mục" - nền hổ phách; hay "Chi tiết" khi lời báo
// có phần chi tiết, ToastDetails của web) và ✕ "Đóng thông báo" ở góc phải. Tự khép sau `duration` (mặc định 4 giây như sonner).
// Chồng thẻ như sonner: thẻ mới nhất ở trước; thẻ sau nấp dưới nó, thấp hơn 14 px và nhỏ đi 5 % (chỉ lộ mép), thẻ thứ ba trở đi ẩn. Rê chuột vào vùng
// thì xoè ra (các thẻ xếp dọc, cách 14) và mọi thẻ dừng đếm. Vào: trượt xuống từ trên (-100 % chiều cao) + hiện dần; khép: thẻ trước trượt lên mất,
// thẻ sau trôi xuống 40 % và mờ đi; các thẻ còn lại trượt về chỗ mới. Giảm chuyển động: chỉ mờ.
Item {
    id: root
    objectName: "toast"
    readonly property int defaultDuration: 4000      // TOAST_LIFETIME của sonner
    readonly property int gap: 14                    // GAP của sonner
    readonly property int visibleToasts: 2
    width: 356
    // Thẻ đang hiện (Api.toasts) + thẻ vừa khép còn chạy hoạt cảnh ra. Mỗi thẻ một delegate sống suốt đời nó: đổi chỗ trong chồng là trượt, không dựng lại.
    ListModel { id: cards }
    property var heights: ({})                       // id -> chiều cao tự nhiên của thẻ
    property bool hovered: hover.hovered
    property bool detailsOpen: false                 // một thẻ đang mở "Chi tiết": vẫn xoè, không thẻ nào tự khép
    readonly property bool expanded: hovered || detailsOpen
    readonly property var live: Api.toasts.map(t => t.id)
    readonly property real frontHeight: live.length ? (heights[live[0]] || 0) : 0
    height: {
        if (!live.length) return 0
        if (!expanded) return frontHeight + gap * (Math.min(visibleToasts, live.length) - 1)
        let total = 0
        for (let i = 0; i < Math.min(visibleToasts, live.length); ++i) total += (heights[live[i]] || 0) + (i ? gap : 0)
        return total
    }
    visible: cards.count > 0

    function sync() {
        const ids = Api.toasts.map(t => t.id)
        // thẻ mới: vào trước chồng (chỉ số 0 = mới nhất); thẻ cũ cùng id: cập nhật chữ tại chỗ
        for (let i = Api.toasts.length - 1; i >= 0; --i) {
            const t = Api.toasts[i]
            let found = -1
            for (let j = 0; j < cards.count; ++j) if (cards.get(j).key === t.id) { found = j; break }
            if (found < 0) cards.insert(0, {key: t.id, removed: false})
            else if (cards.get(found).removed) cards.setProperty(found, "removed", false)
        }
        for (let j = 0; j < cards.count; ++j) if (ids.indexOf(cards.get(j).key) < 0 && !cards.get(j).removed) cards.setProperty(j, "removed", true)
        if (detailsOpen && !Api.toasts.some(t => t.id === openDetails)) closeDetails()
    }
    function forget(key) {
        for (let j = 0; j < cards.count; ++j) if (cards.get(j).key === key) { cards.remove(j); break }
        const h = Object.assign({}, heights); delete h[key]; heights = h
    }
    function setHeight(key, value) { if (heights[key] !== value) { const h = Object.assign({}, heights); h[key] = value; heights = h } }
    function offsetOf(index) {
        let y = 0
        for (let i = 0; i < index; ++i) y += (heights[live[i]] || 0) + gap
        return y
    }
    Connections { target: Api; function onToastsChanged() { root.sync() } }
    Component.onCompleted: sync()

    // ---- "Chi tiết" (ToastDetails): bảng mặt nổi neo dưới thẻ, tiêu đề + chi tiết + nút việc của thẻ. Back / bấm ra ngoài là đóng. ----
    property string openDetails: ""
    readonly property var detailsEntry: Api.toasts.find(t => t.id === openDetails) || null
    property var lastDetails: null                   // giữ chữ trong lúc bảng khép (không nhấp nháy)
    onDetailsEntryChanged: if (detailsEntry) lastDetails = detailsEntry
    // Bấm chỗ khác trong cửa sổ (Main gọi với toạ độ cửa sổ): "Chi tiết" đóng, cú bấm vẫn tới chỗ được bấm (pointerdown ngoài của ToastDetails)
    function pressedAt(scene) {
        if (!detailsOpen) return
        for (const item of [details, details.card]) {
            if (!item) continue
            const local = item.mapFromItem(null, scene.x, scene.y)
            if (local.x >= 0 && local.y >= 0 && local.x <= item.width && local.y <= item.height) return
        }
        closeDetails()
    }
    function openDetailsFor(key) {
        openDetails = key
        detailsOpen = true
        Nav.openLayer(detailsLayer)
    }
    function closeDetails() {
        if (!detailsOpen) return
        detailsOpen = false
        openDetails = ""
        Nav.closedLayer(detailsLayer)
    }
    QtObject { id: detailsLayer; function close() { root.closeDetails() } }
    Component.onDestruction: Nav.closedLayer(detailsLayer)

    HoverHandler { id: hover }

    Repeater {
        model: cards
        Item {
            id: card
            objectName: "toastCard"
            required property string key
            required property bool removed
            required property int index
            readonly property var entry: Api.toasts.find(t => t.id === key) || null
            property var shownEntry: entry                 // chữ cuối cùng, giữ trong lúc khép
            onEntryChanged: { if (entry) shownEntry = entry; runClock() }
            readonly property int order: root.live.indexOf(key)          // 0 = trước; -1 = đã khép
            readonly property bool front: order === 0
            readonly property bool inStack: order >= 0 && order < root.visibleToasts
            readonly property real naturalHeight: Math.max(48, body.height + 2 * 16)
            onNaturalHeightChanged: root.setHeight(key, naturalHeight)
            Component.onCompleted: { root.setHeight(key, naturalHeight); mounted = true; runClock() }
            property bool mounted: false
            readonly property int duration: shownEntry && shownEntry.duration > 0 ? shownEntry.duration : root.defaultDuration
            readonly property bool detailsHere: root.openDetails === key

            width: root.width
            height: removed || front || root.expanded ? naturalHeight : root.frontHeight
            z: 100 - Math.max(0, order)
            // Đích theo trạng thái (sonner: data-mounted / data-front / data-expanded / data-removed)
            readonly property real targetY: !mounted ? -naturalHeight
                : removed ? (lastFront || root.expanded ? lastOffset - naturalHeight : lastOffset + naturalHeight * 0.4)
                : root.expanded ? root.offsetOf(order) : root.gap * order
            readonly property real targetScale: removed || front || root.expanded || !mounted ? 1 : 1 - 0.05 * order
            readonly property real targetOpacity: !mounted || removed || !inStack ? 0 : 1
            // Chỗ và vai lúc còn sống, để hoạt cảnh ra đi từ đúng chỗ ấy
            property real lastOffset: 0
            property bool lastFront: true
            onOrderChanged: if (order >= 0) { lastOffset = root.expanded ? root.offsetOf(order) : root.gap * order; lastFront = order === 0 }
            onRemovedChanged: if (removed) { clock.stop(); gone.restart() } else gone.stop()
            Timer { id: gone; interval: Theme.reduceMotion ? Theme.motionFastOut : Theme.motionMediumOut; onTriggered: root.forget(card.key) }

            y: Theme.reduceMotion ? (mounted && !removed ? targetY : lastOffset) : targetY
            scale: targetScale             // giảm chuyển động: vẫn chồng như thường, chỉ không tween
            opacity: targetOpacity
            transformOrigin: Item.Center
            enabled: inStack && !removed
            Behavior on y { enabled: !Theme.reduceMotion; NumberAnimation { duration: card.removed ? Theme.motionMediumOut : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.reduceMotion ? (card.removed ? Theme.motionFastOut : Theme.motionFast) : (card.removed ? Theme.motionMediumOut : Theme.motionMedium)
                }
            }

            // Đếm giờ từ đầu mỗi lần thẻ hiện / được báo lại; dừng khi vùng xoè (rê chuột, đang mở Chi tiết), xoè xong thì đếm lại
            Timer { id: clock; interval: card.duration; onTriggered: Api.dismiss(card.key) }
            function runClock() {
                if (card.entry && !card.removed && !root.expanded) clock.restart()
                else clock.stop()
            }
            Connections { target: root; function onExpandedChanged() { card.runClock() } }

            // Bóng của lớp nổi (như Popover: DESIGN.md 5.5)
            Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
            Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusCover
                color: Theme.panel
                border.width: 1
                border.color: Theme.line
            }
            // Thẻ nấp sau (chồng gọn): chỉ thấy mép, chữ ẩn
            Item {
                id: content
                anchors.fill: parent
                opacity: card.front || root.expanded || card.removed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
                Item {
                    id: body
                    x: 16
                    y: 16
                    width: card.width - 32 - 24          // chừa chỗ ✕ ở góc phải
                    // Như sonner + styles.css (thông báo MỘT dòng): nút cùng hàng với chữ, không đủ chỗ (chữ hẹp hơn 8rem) thì xuống hàng riêng, mép phải
                    readonly property bool wraps: actionButton.visible && titleText.implicitWidth > width - actionButton.width - 6 && width - actionButton.width - 6 < 128
                    height: wraps ? titleText.height + 12 + actionButton.height : Math.max(titleText.height, actionButton.visible ? actionButton.height : 0)
                    Text {
                        id: titleText
                        objectName: "toastTitle"
                        width: body.wraps || !actionButton.visible ? body.width : body.width - actionButton.width - 6
                        y: body.wraps ? 0 : Math.max(0, (body.height - height) / 2)
                        text: card.shownEntry ? card.shownEntry.title : ""
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                        font.weight: Theme.weightMedium
                    }
                    Interactive {
                        id: actionButton
                        objectName: "toastAction"
                        // Lời báo có chi tiết: nút "Chi tiết" (chữ nhấn, nền trong); không thì nút việc của thẻ (nền hổ phách)
                        readonly property bool details: Boolean(card.shownEntry && card.shownEntry.description)
                        visible: details || Boolean(card.shownEntry && card.shownEntry.action)
                        x: body.width - width
                        y: body.wraps ? titleText.height + 12 : (body.height - height) / 2
                        implicitWidth: actionLabel.implicitWidth + 16
                        implicitHeight: Math.max(24, actionLabel.implicitHeight + 6)
                        Accessible.role: Accessible.Button
                        Accessible.name: actionLabel.text
                        onClicked: details ? (card.detailsHere ? root.closeDetails() : root.openDetailsFor(card.key)) : Api.runToastAction(card.key)
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusControl
                            color: actionButton.details ? Theme.hover : Theme.accent
                            opacity: actionButton.details ? (actionButton.hovered ? 1 : 0) : 1
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Rectangle {
                                visible: !actionButton.details
                                anchors.fill: parent
                                radius: parent.radius
                                color: "#000000"
                                opacity: actionButton.pressed ? Theme.pressShade : actionButton.hovered ? 0.04 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            }
                        }
                        Text {
                            id: actionLabel
                            anchors.centerIn: parent
                            text: actionButton.details ? "Chi tiết" : (card.shownEntry && card.shownEntry.action ? card.shownEntry.action.label : "")
                            color: actionButton.details ? Theme.accentText : Theme.accentInk
                            font.pixelSize: 12
                            font.weight: actionButton.details ? Theme.weightMedium : 600
                        }
                    }
                }
                // ✕ trong góc phải, thẳng dòng tiêu đề (styles.css: right 0.75rem, top 1rem, cao một dòng, rê chuột nền hover)
                Interactive {
                    id: close
                    objectName: "toastClose"
                    x: card.width - 12 - width
                    y: 16 + Math.max(0, (Math.min(titleText.height, 20) - height) / 2)
                    width: 20
                    height: 20
                    tip: ""
                    Accessible.role: Accessible.Button
                    Accessible.name: "Đóng thông báo"
                    onClicked: Api.dismiss(card.key)
                    Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: close.hovered ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                    Icon { anchors.centerIn: parent; name: "x"; size: 12; color: Theme.text2 }
                }
            }
        }
    }

    // Bảng "Chi tiết thông báo": rộng 320, dưới thẻ đang mở 12 px, mép phải thẳng thẻ; trượt 8 px + hiện dần (MotionPresence)
    Item {
        id: details
        objectName: "toastDetails"
        // Thẻ đang mở chi tiết (giữ lại trong lúc bảng khép)
        property Item card: null
        property real shown: root.detailsOpen ? 1 : 0
        Behavior on shown {
            NumberAnimation {
                duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : (root.detailsOpen ? Theme.motionMedium : Theme.motionMediumOut)
                easing.type: Easing.BezierSpline
                easing.bezierCurve: root.detailsOpen ? Theme.easeDecelerate : Theme.easeAccelerate
            }
        }
        visible: shown > 0
        z: 200
        width: 320
        x: root.width - width
        y: (card ? card.y + card.height : 0) + 12
        height: detailsColumn.height + 32
        opacity: shown
        transform: Translate { y: Theme.reduceMotion ? 0 : -8 * (1 - details.shown) }
        Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
        Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
        Rectangle { anchors.fill: parent; radius: Theme.radiusCover; color: Theme.panel }
        MouseArea { anchors.fill: parent }          // bấm trong bảng không đóng
        Accessible.role: Accessible.Grouping
        Accessible.name: "Chi tiết thông báo"
        Column {
            id: detailsColumn
            x: 16
            y: 16
            width: details.width - 32
            spacing: 12
            Text {
                width: parent.width
                text: root.lastDetails ? root.lastDetails.title : ""
                color: Theme.text
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            Text {
                objectName: "toastDescription"
                width: parent.width
                text: root.lastDetails ? root.lastDetails.description : ""
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
            }
            Button {
                objectName: "toastDetailsAction"
                visible: Boolean(root.lastDetails && root.lastDetails.action)
                x: -12                     // edge-start-action: chữ thẳng mép chữ trên
                kind: "ghost"
                size: "sm"
                text: root.lastDetails && root.lastDetails.action ? root.lastDetails.action.label : ""
                onClicked: { const key = root.openDetails; root.closeDetails(); Api.runToastAction(key) }
            }
        }
    }
    onOpenDetailsChanged: {
        if (!openDetails) return
        for (const child of root.children) if (child.objectName === "toastCard" && child.key === openDetails) details.card = child
    }
}
