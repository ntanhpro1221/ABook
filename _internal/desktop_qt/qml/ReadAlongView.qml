import QtQuick
import ABook

// Văn bản chương chạy theo giọng (bản web: ReadAlongText.tsx + follow.ts). Danh sách đoạn ảo hoá: chỉ đoạn đang thấy mới có TextEdit. Câu đang nghe được tô nền
// theo từng dòng chữ (hình chữ nhật lấy từ QTextLayout của chính TextEdit; chỉ đoạn có câu đổi mới vẽ lại), chữ đang đọc tô đậm hơn khi sách có mốc chữ,
// câu đã nghe nhạt đi. Đang theo: câu sắp khuất thì cuộn nó lên khoảng một phần ba từ trên. Người tự cuộn là thôi theo và hiện "Tới câu đang nghe";
// thôi cuộn 1,5 giây mà câu đang đọc nằm trong khung thì theo lại. Bấm một câu (hay một chữ) là nghe từ đó.
// Mặt đọc (Cài đặt › Giao diện › "Nền đọc", Theme.read; .reading-surface của web): nền, chữ, chữ phụ, màu nhấn và lớp tô câu / chữ của vùng này
// theo MẶT ĐỌC chứ không theo giao diện của app; đổi mặt thì nền và chữ mờ chéo theo motionSlow.
// `source`: ReadAlong (chương đang phát, màn Đang nghe) hay một ChapterText (màn đọc "Đọc chương này") - cùng giao diện. Cỡ chữ / giãn dòng là của màn
// đọc (Api.reader, "Cỡ chữ và giãn dòng" ở thanh dưới màn đọc): đổi ở đó là chữ ở đây đổi theo.
Item {
    id: root
    property QtObject source: ReadAlong
    // Màn đọc dàn cả chương chưa có mốc (chương chỉ có chữ, chưa thu); Đang nghe chỉ hiện chữ có mốc
    property bool untimed: false
    // Đầu / cuối danh sách (lời nhắc, thẻ "Chương tiếp theo" của màn đọc), cuộn cùng chữ
    property Component header: null
    property Component footer: null
    property real headingScale: 1.4
    property real topPad: 24
    property real bottomPad: 96
    // Khoảng từ đáy khung tới đáy viên "Tới câu đang nghe" (màn đọc: trên thanh nổi)
    property real chipBottom: Theme.s24
    readonly property alias view: list
    readonly property real textW: Math.min(width - 40, textMax)
    // Lớp nằm trên chữ (thanh nổi, bảng nổi): TapHandler của chữ vẫn thấy cú bấm trên chúng (Qt 6 đưa cú bấm tới mọi handler dưới điểm), nên chữ tự bỏ qua
    property var overlays: []
    function covered(scene) {
        for (const item of overlays.concat([chip])) {
            if (!item || !item.visible || item.opacity === 0) continue
            const local = item.mapFromItem(null, scene.x, scene.y)
            if (item.contains(local)) return true
        }
        return false
    }
    signal userScrolled()       // người tự cuộn (lăn, kéo, thanh cuộn)
    signal pageTapped()         // bấm vào chữ
    signal scrolled()           // khung cuộn đổi chỗ (người hay app)
    property bool following: true
    property string placement: "inside"
    property bool firstPlacement: true
    readonly property real fontPx: Math.max(14, Number(Api.reader.size || Theme.sizeReading))
    readonly property real leading: Math.max(1.2, Number(Api.reader.leading || Theme.lineHeightReading))
    Component.onCompleted: Api.loadReader()
    readonly property bool showChip: !following && root.source.currentSegment >= 0 && placement !== "inside"
    property real textMax: 640
    readonly property var surface: Theme.read
    property color surfaceBg: surface.bg
    Behavior on surfaceBg { ColorAnimation { duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionSlow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    Rectangle { objectName: "readingSurface"; anchors.fill: parent; color: root.surfaceBg }

    // ---- đi theo giọng ----
    function manual() {
        root.userScrolled()
        following = false
        followAnim.stop()
        settle.restart()
    }
    function minY() { return list.originY - list.topMargin }
    function maxY() { return Math.max(minY(), list.originY + list.contentHeight - list.height + list.bottomMargin) }
    function scrollTo(y, animate) {
        const target = Math.max(minY(), Math.min(maxY(), y))
        followAnim.stop()
        if (!animate || Theme.reduceMotion) {
            list.contentY = target
            return
        }
        followAnim.from = list.contentY
        followAnim.to = target
        followAnim.start()
    }
    function currentBox() {
        const item = list.itemAtIndex(root.source.currentPara)
        if (!item || item.sentRects.length === 0) return null
        const first = item.sentRects[0]
        const last = item.sentRects[item.sentRects.length - 1]
        const base = item.y - list.contentY + item.bodyY
        return { top: base + first.y, bottom: base + last.y + last.height }
    }
    function refreshPlacement() {
        if (root.source.currentSegment < 0) {
            placement = "inside"
            return
        }
        const box = currentBox()
        if (box) {
            placement = root.source.placement(box.top, box.bottom, 0, list.height)
            return
        }
        const middle = list.indexAt(list.width / 2, list.contentY + list.height / 2)
        placement = middle >= 0 && root.source.currentPara < middle ? "above" : "below"
    }
    function follow(animate) {
        if (root.source.currentSegment < 0 || root.source.currentPara < 0) return
        const box = currentBox()
        if (!box) {
            // Đoạn chưa dựng (nhảy xa, mới mở): đưa nó vào rồi đợi nó báo hình chữ nhật của câu (currentRectsChanged)
            list.positionViewAtIndex(root.source.currentPara, ListView.Beginning)
            return
        }
        if (firstPlacement || root.source.needsFollow(box.top, box.bottom, 0, list.height))
            scrollTo(root.source.followTop(box.top, 0, list.height, list.contentY), animate && !firstPlacement)
        firstPlacement = false
        placement = "inside"
    }
    function afterSegment() {
        if (following) follow(true)
        else refreshPlacement()
    }
    // Đoạn đang đọc vừa tính xong hình chữ nhật của câu. Gọi từ Component.onCompleted của dòng đang được dựng: để sau (callLater gộp các lần gọi), vì
    // cuộn / positionViewAtIndex ngay trong lúc ListView đang dựng dòng bằng incubator làm dòng bị đụng lại giữa chừng (app chết trong QQmlObjectCreator::finalize).
    function currentRectsChanged() { Qt.callLater(rectsSettled) }
    function rectsSettled() {
        if (following) follow(true)
        else refreshPlacement()
    }
    // Câu đầu tiên còn thấy trong khung (follow.firstVisibleIndex): chỗ đọc của màn đọc
    function firstVisibleSegment() {
        const y = list.contentY + 4
        const index = list.indexAt(list.width / 2, y)
        if (index < 0) {
            // trên đoạn đầu (lời nhắc, lề trên) hay dưới đoạn cuối (thẻ "Chương tiếp theo")
            const first = list.itemAtIndex(0)
            return !first || y < first.y ? 0 : root.source.firstOf(Math.max(0, list.count - 1))
        }
        const item = list.itemAtIndex(index)
        return item ? item.segmentAtY(y - item.y) : root.source.firstOf(index)
    }
    // Đưa câu `segment` lên đầu khung (mở màn đọc ở chỗ đọc dở); câu đầu chương: về đầu trang (lời nhắc đứng trước câu ấy)
    function showSegment(segment) {
        followAnim.stop()
        if (segment <= 0) { list.positionViewAtBeginning(); list.contentY = minY(); return }
        const paragraph = root.source.paragraphOf(segment)
        if (paragraph < 0) return
        list.positionViewAtIndex(paragraph, ListView.Beginning)
        Qt.callLater(function() {
            const item = list.itemAtIndex(paragraph)
            if (item) list.contentY = Math.max(minY(), Math.min(maxY(), item.y + item.lineTopOf(segment)))
        })
    }
    // Câu đang nghe nằm trong khung
    function playingInView() {
        const box = currentBox()
        return box !== null && root.source.placement(box.top, box.bottom, 0, list.height) === "inside"
    }
    function goBackToReading() {
        following = true
        follow(true)
    }

    Timer {
        id: settle
        interval: root.source.settleMs()
        onTriggered: {
            refreshPlacement()
            if (!root.following && root.placement === "inside") root.following = true
        }
    }
    NumberAnimation {
        id: followAnim
        target: list
        property: "contentY"
        duration: 300
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDecelerate
    }
    Connections {
        target: root.source
        function onCurrentSegmentChanged() { Qt.callLater(root.afterSegment) }
        function onListened() { root.following = true; root.firstPlacement = false }
        function onStatusChanged() {
            if (root.source.status === "ready") {
                root.following = true
                root.firstPlacement = true
            }
        }
    }
    Connections {
        target: Theme
        function onDarkChanged() { root.shadeAll() }
        function onReadChanged() { root.shadeAll() }
    }
    signal shadeAll()

    ListView {
        id: list
        anchors.fill: parent
        model: root.source.timed || (root.untimed && root.source.status === "ready") ? root.source.paragraphs : null
        clip: true
        cacheBuffer: 900
        topMargin: root.topPad
        bottomMargin: root.bottomPad
        header: root.header
        footer: root.footer
        boundsBehavior: Flickable.StopAtBounds
        onMovementStarted: root.manual()
        onContentYChanged: {
            root.scrolled()
            if (!root.following) {
                settle.restart()
                root.refreshPlacement()
            }
        }

        delegate: Item {
            id: del
            required property int index
            required property string text
            required property string kind
            required property string speaker
            readonly property real textW: Math.min(list.width - 40, root.textMax)
            readonly property bool heading: kind === "heading"
            readonly property bool scene: kind === "scene"
            readonly property real px: heading ? Math.round(root.fontPx * root.headingScale) : root.fontPx
            readonly property real lineH: Math.round(px * (heading ? 1.25 : root.leading))
            readonly property real bodyY: speakerLabel.visible ? speakerLabel.height + 2 : 0
            property var sentRects: []
            property var wordRects: []
            property var hoverRects: []
            property int hoverSeg: -1
            width: list.width
            height: bodyY + edit.height + (heading ? Theme.s12 : Theme.s24)

            function refresh() {
                if (root.source.currentPara === index) {
                    sentRects = root.source.sentenceRects(edit.textDocument, index, root.source.currentSegment)
                    wordRects = root.source.wordRects(edit.textDocument, index, root.source.currentSegment, root.source.currentWord)
                    root.currentRectsChanged()
                } else if (sentRects.length > 0 || wordRects.length > 0) {
                    sentRects = []
                    wordRects = []
                }
                refreshHover()
            }
            function refreshHover() {
                hoverRects = hoverSeg >= 0 && hoverSeg !== root.source.currentSegment ? root.source.sentenceRects(edit.textDocument, index, hoverSeg) : []
            }
            // Câu có dòng chữ ở toạ độ `y` của dòng (ngay dưới mép trên khung), và đỉnh dòng đầu của một câu
            function segmentAtY(y) {
                const local = y - bodyY
                if (local <= 0) return root.source.firstOf(index)
                return root.source.segmentAt(index, edit.positionAt(0, Math.min(local, edit.height - 1)))
            }
            function lineTopOf(segment) {
                const rects = root.source.sentenceRects(edit.textDocument, index, segment)
                return rects.length ? bodyY + rects[0].y : 0
            }
            function shade() {
                root.source.shade(edit.textDocument, index, root.surface.fg2, root.surface.fg)
            }
            onHoverSegChanged: refreshHover()

            Text {
                id: speakerLabel
                visible: del.speaker !== "" && !del.heading && !del.scene
                x: Math.round((del.width - del.textW) / 2)
                width: del.textW
                text: del.speaker
                color: root.surface.fg2
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Item {
                id: body
                x: Math.round((del.width - del.textW) / 2)
                y: del.bodyY
                width: del.textW
                height: edit.height
                Repeater {
                    model: del.hoverRects.length
                    Rectangle {
                        required property int index
                        readonly property var r: del.hoverRects[index]
                        x: r.x - 3; y: r.y; width: r.width + 6; height: r.height
                        radius: Theme.radiusControl
                        color: root.surface.fg
                        opacity: 0.05
                    }
                }
                Repeater {
                    model: del.sentRects.length
                    Rectangle {
                        required property int index
                        readonly property var r: del.sentRects[index]
                        x: r.x - 3; y: r.y; width: r.width + 6; height: r.height
                        radius: Theme.radiusControl
                        color: Qt.alpha(root.surface.accent, root.surface.along)
                    }
                }
                Repeater {
                    model: del.wordRects.length
                    Rectangle {
                        required property int index
                        readonly property var r: del.wordRects[index]
                        x: r.x - 2; y: r.y + 1; width: r.width + 4; height: r.height - 2
                        radius: Theme.radiusControl
                        color: Qt.alpha(root.surface.accent, root.surface.word)
                    }
                }
                TextEdit {
                    id: edit
                    width: parent.width
                    text: del.text
                    readOnly: true
                    enabled: false          // chỉ để dàn chữ; bấm / rê do TapHandler + HoverHandler của đoạn lo
                    selectByMouse: false
                    activeFocusOnPress: false
                    wrapMode: TextEdit.Wrap
                    color: root.surface.fg
                    font.pixelSize: del.px
                    font.weight: del.heading ? Theme.weightBold : Theme.weightRegular
                    horizontalAlignment: del.scene ? TextEdit.AlignHCenter : TextEdit.AlignLeft
                    font.letterSpacing: del.scene ? 4 : 0
                    onContentHeightChanged: del.refresh()
                    onWidthChanged: del.refresh()
                    Component.onCompleted: {
                        root.source.setLineHeight(textDocument, del.lineH)
                        del.shade()
                        del.refresh()
                    }
                }
            }
            Connections {
                target: root.source
                function onCurrentSegmentChanged() {
                    if (root.source.currentPara === del.index) del.shade()
                    del.refresh()
                }
                function onCurrentParaChanged() { del.shade(); del.refresh() }
                function onCurrentWordChanged() {
                    if (root.source.currentPara === del.index)
                        del.wordRects = root.source.wordRects(edit.textDocument, del.index, root.source.currentSegment, root.source.currentWord)
                }
            }
            Connections {
                target: root
                function onShadeAll() { del.shade() }
            }
            HoverHandler {
                cursorShape: Qt.PointingHandCursor
                onPointChanged: {
                    const y = point.position.y - body.y
                    if (y < 0 || y > edit.height) {
                        del.hoverSeg = -1
                        return
                    }
                    del.hoverSeg = root.source.segmentAt(del.index, edit.positionAt(point.position.x - body.x, y))
                }
                onHoveredChanged: if (!hovered) del.hoverSeg = -1
            }
            TapHandler {
                property bool covered: false
                onPressedChanged: if (pressed) covered = Nav.coveredFor(del)
                onTapped: (eventPoint) => {
                    if (covered) return
                    if (root.covered(del.mapToItem(null, eventPoint.position.x, eventPoint.position.y))) return
                    root.pageTapped()
                    const y = eventPoint.position.y - body.y
                    if (y < 0 || y > edit.height) return
                    root.source.listenFrom(del.index, edit.positionAt(eventPoint.position.x - body.x, y))
                }
            }
        }
        SmoothWheel { flick: list; onScrolled: root.manual() }
        Scrollbar { target: list; onDraggingChanged: if (dragging) root.manual() }
    }

    // Mép trên / dưới mờ dần: chữ cuộn không bị cắt ngang sát mép
    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 24
        gradient: Gradient {
            GradientStop { position: 0; color: root.surfaceBg }
            GradientStop { position: 1; color: Qt.rgba(root.surfaceBg.r, root.surfaceBg.g, root.surfaceBg.b, 0) }
        }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 48
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(root.surfaceBg.r, root.surfaceBg.g, root.surfaceBg.b, 0) }
            GradientStop { position: 1; color: root.surfaceBg }
        }
    }

    Text {
        anchors.centerIn: parent
        width: Math.min(parent.width - 2 * Theme.s24, 360)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        visible: !root.untimed && (root.source.status === "loading" || root.source.status === "failed")
        text: root.source.status === "loading" ? "Đang mở văn bản chương…" : "Chưa mở được văn bản chương này."
        color: root.surface.fg2
        font.pixelSize: Theme.sizeBodySmall
    }

    // "Tới câu đang nghe" (JumpToPlaying của web: icon locate, viên tròn): trượt lên từ đáy khung khi người đã cuộn đi chỗ khác
    Rectangle {
        id: chip
        readonly property bool shown: root.showChip
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height - height - root.chipBottom + (shown ? 0 : 16)
        width: chipRow.implicitWidth + 2 * Theme.s16
        height: 40
        radius: height / 2
        color: Theme.dark ? Theme.text : "#2a2723"
        opacity: shown ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: chip.shown ? Theme.motionMedium : Theme.motionFastOut } }
        Behavior on y {
            NumberAnimation {
                duration: Theme.reduceMotion ? 0 : (chip.shown ? Theme.motionMedium : Theme.motionFastOut)
                easing.type: Easing.BezierSpline
                easing.bezierCurve: chip.shown ? Theme.easeDecelerate : Theme.easeAccelerate
            }
        }
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: Theme.s8
            Icon {
                name: "locate"
                size: 16
                color: Theme.dark ? Theme.bg : "#f5f3ef"
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: "Tới câu đang nghe"
                color: Theme.dark ? Theme.bg : "#f5f3ef"
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        TapHandler { enabled: chip.shown; onTapped: root.goBackToReading() }
        HoverHandler { enabled: chip.shown; cursorShape: Qt.PointingHandCursor }
    }
}
