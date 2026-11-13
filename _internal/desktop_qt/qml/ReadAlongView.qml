import "UiStrings.js" as S
import QtQuick
import QtQuick.Shapes
import "ReadingInk.js" as ReadingInk
import ABook
import "PlayerLabels.js" as Labels

// Văn bản chương chạy theo giọng (bản web: ReadAlongText.tsx + follow.ts). Danh sách đoạn ảo hoá: chỉ đoạn đang thấy mới có TextEdit. Câu đang nghe được tô nền
// theo từng dòng chữ (hình chữ nhật lấy từ QTextLayout của chính TextEdit; chỉ đoạn có câu đổi mới vẽ lại), chữ đang đọc tô đậm hơn khi sách có mốc chữ,
// câu đã nghe nhạt đi. Đang theo: câu sắp khuất thì cuộn nó lên khoảng một phần ba từ trên; câu có mốc chữ thì chữ xuống dòng mới là cuộn dòng ấy về đúng chỗ đó. Người tự cuộn là thôi theo và hiện "Tới câu đang nghe";
// thôi cuộn 1,5 giây mà câu đang đọc nằm trong khung thì theo lại. Bấm một câu (hay một chữ) là nghe từ đó.
// Mặt đọc (Cài đặt › Giao diện › "Nền đọc", Theme.read; .reading-surface của web): nền, chữ, chữ phụ, màu nhấn và lớp tô câu / chữ của vùng này
// theo MẶT ĐỌC chứ không theo giao diện của app; đổi mặt thì nền và chữ mờ chéo theo motionSlow.
Item {
    id: root
    property bool following: true
    property bool tapped: false
    // Retain the paragraph at the viewport edge while its preceding text wraps.
    // Playback following still owns placement when following is enabled.
    property var viewportAnchor: null
    property bool restoringViewport: false
    readonly property bool settled: !restoringViewport
    function rememberViewport() {
        if (following || restoringViewport) return
        const index = list.indexAt(list.width / 2, list.contentY + 1)
        const item = index >= 0 ? list.itemAtIndex(index) : null
        if (item) viewportAnchor = {index: index, offset: item.y - list.contentY}
    }
    function restoreViewport() {
        const anchor = viewportAnchor
        const item = anchor ? list.itemAtIndex(anchor.index) : null
        if (item && !following) scrollTo(item.y - anchor.offset, false)
        restoringViewport = false
        rememberViewport()
    }
    onWidthChanged: {
        if (!following && viewportAnchor) {
            restoringViewport = true
        }
    }
    Connections {
        target: root.Window.window
        function onFrameSwapped() { if (root.restoringViewport) Later.call(root, root.restoreViewport) }
    }
    Connections { target: Player; function onChapterChanged() { root.tapped = false; root.viewportAnchor = null } }
    Connections { target: ReadAlong; function onListened() { root.tapped = true } }
    Text {
        id: hint; objectName: "readerHint"
        x: Theme.s24; y: Theme.s12; width: parent.width - 2 * Theme.s24
        visible: ReadAlong.status === "ready" && text !== ""
        text: Labels.readerHint(Player.speaking, Api.voiceList.length > 0, ReadAlong.timed, root.tapped)
        wrapMode: Text.Wrap; color: root.surface.fg2; font.pixelSize: Theme.sizeCaption
        z: 2
    }
    property string placement: "inside"
    property bool firstPlacement: true
    readonly property real fontPx: Math.max(14, Number(Platform.setting("readingSize", String(Theme.sizeReading))))
    readonly property real leading: Math.max(1.2, Number(Platform.setting("readingLeading", String(Theme.lineHeightReading))))
    readonly property bool showChip: !following && ReadAlong.currentSegment >= 0 && placement !== "inside"
    readonly property real textMax: 640
    readonly property var surface: Theme.read
    property color surfaceBg: surface.bg
    Behavior on surfaceBg { ColorAnimation { duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionSlow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    Rectangle { objectName: "readingSurface"; anchors.fill: parent; color: root.surfaceBg }

    // ---- đi theo giọng ----
    function manual() {
        following = false
        followAnim.stop()
        settle.restart()
    }
    function minY() { return -list.topMargin }
    function maxY() { return Math.max(minY(), list.contentHeight - list.height + list.bottomMargin) }
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
        const item = list.itemAtIndex(ReadAlong.currentPara)
        if (!item || item.sentRects.length === 0) return null
        const first = item.sentRects[0]
        const last = item.sentRects[item.sentRects.length - 1]
        const base = item.y - list.contentY + item.bodyY
        return { top: base + first.y, bottom: base + last.y + last.height }
    }
    function refreshPlacement() {
        if (ReadAlong.currentSegment < 0) {
            placement = "inside"
            return
        }
        const box = currentBox()
        if (box) {
            placement = ReadAlong.placement(box.top, box.bottom, 0, list.height)
            return
        }
        const middle = list.indexAt(list.width / 2, list.contentY + list.height / 2)
        placement = middle >= 0 && ReadAlong.currentPara < middle ? "above" : "below"
    }
    function follow(animate) {
        if (ReadAlong.currentSegment < 0 || ReadAlong.currentPara < 0) return
        const box = currentBox()
        if (!box) {
            // Đoạn chưa dựng (nhảy xa, mới mở): đưa nó vào rồi đợi nó báo hình chữ nhật của câu (currentRectsChanged)
            list.positionViewAtIndex(ReadAlong.currentPara, ListView.Beginning)
            return
        }
        if (firstPlacement || ReadAlong.needsFollow(box.top, box.bottom, 0, list.height))
            scrollTo(ReadAlong.followTop(box.top, 0, list.height, list.contentY), animate && !firstPlacement)
        firstPlacement = false
        placement = "inside"
    }
    function afterSegment() {
        if (following) follow(true)
        else refreshPlacement()
    }
    // Đỉnh dòng của chữ đang đọc, tính trong nội dung cuộn: chữ sang dòng khác thì đưa dòng ấy về chỗ đọc (luật ở follow.ts).
    property real wordLine: -1
    function afterWord() {
        if (!following) return
        const item = list.itemAtIndex(ReadAlong.currentPara)
        if (!item || item.wordRects.length === 0) return
        const rect = item.wordRects[0]
        const line = item.y + item.bodyY + rect.y
        if (Math.abs(line - wordLine) <= 4) return
        wordLine = line
        scrollTo(ReadAlong.followTop(line - list.contentY, 0, list.height, list.contentY), !firstPlacement)
    }
    // Đoạn đang đọc vừa tính xong hình chữ nhật của câu. Gọi từ Component.onCompleted của dòng đang được dựng: để sau (Later.call gộp các lần gọi), vì
    // cuộn / positionViewAtIndex ngay trong lúc ListView đang dựng dòng bằng incubator làm dòng bị đụng lại giữa chừng (app chết trong QQmlObjectCreator::finalize).
    function currentRectsChanged() { Later.call(root, rectsSettled) }
    function rectsSettled() {
        if (following) follow(true)
        else refreshPlacement()
    }
    function goBackToReading() {
        following = true
        follow(true)
    }

    Timer {
        id: settle
        interval: ReadAlong.settleMs()
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
        target: ReadAlong
        function onCurrentSegmentChanged() { Later.call(root, root.afterSegment) }
        function onCurrentWordChanged() { Later.call(root, root.afterWord) }
        function onListened() { root.following = true; root.firstPlacement = false }
        function onStatusChanged() {
            if (ReadAlong.status === "ready") {
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
        objectName: "readAlongParagraphs"
        anchors.fill: parent
        anchors.bottomMargin: 48
        anchors.topMargin: hint.visible ? hint.height + 2 * Theme.s12 : 0
        model: ReadAlong.timed ? ReadAlong.paragraphs : null
        clip: true
        cacheBuffer: 900
        topMargin: 24
        bottomMargin: 96
        boundsBehavior: Flickable.StopAtBounds
        onMovementStarted: root.manual()
        onContentYChanged: {
            if (!root.following) {
                root.rememberViewport()
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
            readonly property real px: heading ? Math.round(root.fontPx * 1.4) : root.fontPx
            readonly property real lineH: Math.round(px * (heading ? 1.25 : root.leading))
            readonly property real bodyY: speakerLabel.visible ? speakerLabel.height + 2 : 0
            property var sentRects: []
            property var wordRects: []
            property var hoverRects: []
            property int hoverSeg: -1
            width: list.width
            height: bodyY + edit.height + (heading ? Theme.s12 : Theme.s24)

            function refresh() {
                if (ReadAlong.currentPara === index) {
                    sentRects = ReadAlong.sentenceRects(edit.textDocument, index, ReadAlong.currentSegment)
                    wordRects = ReadAlong.wordRects(edit.textDocument, index, ReadAlong.currentSegment, ReadAlong.currentWord)
                    root.currentRectsChanged()
                } else if (sentRects.length > 0 || wordRects.length > 0) {
                    sentRects = []
                    wordRects = []
                }
                refreshHover()
            }
            function refreshHover() {
                hoverRects = hoverSeg >= 0 && hoverSeg !== ReadAlong.currentSegment ? ReadAlong.sentenceRects(edit.textDocument, index, hoverSeg) : []
            }
            function shade() {
                ReadAlong.shade(edit.textDocument, index, root.surface.fg2, root.surface.fg)
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
                Shape {
                    anchors.fill: parent
                    ShapePath {
                        strokeWidth: 0
                        strokeColor: "transparent"
                        fillColor: Qt.alpha(root.surface.accent, root.surface.along)
                        PathSvg { path: ReadingInk.sentenceOutline(del.sentRects) }
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
                        ReadAlong.setLineHeight(textDocument, del.lineH)
                        del.shade()
                        del.refresh()
                    }
                }
            }
            Connections {
                target: ReadAlong
                function onCurrentSegmentChanged() {
                    if (ReadAlong.currentPara === del.index) del.shade()
                    del.refresh()
                }
                function onCurrentParaChanged() { del.shade(); del.refresh() }
                function onCurrentWordChanged() {
                    if (ReadAlong.currentPara === del.index)
                        del.wordRects = ReadAlong.wordRects(edit.textDocument, del.index, ReadAlong.currentSegment, ReadAlong.currentWord)
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
                    del.hoverSeg = ReadAlong.segmentAt(del.index, edit.positionAt(point.position.x - body.x, y))
                }
                onHoveredChanged: if (!hovered) del.hoverSeg = -1
            }
            TapHandler {
                onTapped: (eventPoint) => {
                    const y = eventPoint.position.y - body.y
                    if (y < 0 || y > edit.height) return
                    ReadAlong.listenFrom(del.index, edit.positionAt(eventPoint.position.x - body.x, y))
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
        anchors.bottomMargin: 48
        width: parent.width
        height: 24
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
        visible: ReadAlong.status === "loading" || ReadAlong.status === "failed"
        text: ReadAlong.status === "loading" ? S.s_dang_mo_van_ban_chuong_703dec05 : S.s_chua_mo_duoc_van_ban_chuong_nay_fc50ef45
        color: root.surface.fg2
        font.pixelSize: Theme.sizeBodySmall
    }

    // "Tới câu đang nghe" (JumpToPlaying của web: icon locate, viên tròn): trượt lên từ đáy khung khi người đã cuộn đi chỗ khác
    Rectangle {
        id: jumpDock
        objectName: "readingDock"
        anchors.bottom: parent.bottom
        width: parent.width
        height: 48
        color: Theme.bg
    }
    Rectangle {
        id: chip
        readonly property bool shown: root.showChip
        anchors.horizontalCenter: parent.horizontalCenter
        y: jumpDock.y + (jumpDock.height - height) / 2 + (shown ? 0 : 16)
        width: chipRow.implicitWidth + 2 * Theme.s16
        height: 40
        radius: height / 2
        color: Theme.text
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
                color: Theme.bg
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: S.s_toi_cau_dang_nghe_4526cf38
                color: Theme.bg
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        TapHandler { enabled: chip.shown; onTapped: root.goBackToReading() }
        HoverHandler { enabled: chip.shown; cursorShape: Qt.PointingHandCursor }
    }
}
