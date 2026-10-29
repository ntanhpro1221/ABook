import QtQuick
import ABook
import "LibraryLogic.js" as LibraryLogic

// Đang nghe: phủ kín khung nội dung (thanh bên vẫn ở đó). Mở bằng cách biến thanh phát: bìa nhỏ lớn dần thành bìa lớn theo đường thẳng, phần còn lại trượt lên;
// đóng là đúng gương (Esc, Alt+Left, nút Back của chuột đều đóng). Chỉ một tiến độ p chạy 0..1, mọi thứ là hàm của p - không có mờ thuần.
//   Khổ large trở lên: cột trái = bìa, tên, thanh tua, nút phát, rồi Tốc độ / Hẹn giờ / Chương / Nhạc nền; cột phải = văn bản chạy theo giọng
//   (sách chưa có mốc thì danh sách chương). Hẹp: một cột, công tắc "Bìa / Đọc theo" trượt theo thứ tự.
Item {
    id: root
    property Item bar: null
    property bool open: false
    property real p: 0
    property int page: 0                         // hẹp: 0 = Bìa, 1 = Chữ/Chương
    property int sidePage: 1
    signal settingsRequested(string group)
    readonly property var libraryBooks: {
        Backend.library.revision
        const rows = []
        for (let i = 0; i < Backend.library.count; ++i) rows.push(Backend.library.book(i))
        return rows
    }
    readonly property var currentBook: libraryBooks.find(b => b.bookId === Player.bookId) || ({})
    readonly property var nextVolume: {
        const groups = LibraryLogic.sections(libraryBooks)
        const group = groups.find(g => g.books.some(b => b.bookId === Player.bookId))
        if (!group) return null
        const at = group.books.findIndex(b => b.bookId === Player.bookId)
        return group.books.slice(at + 1).find(b => b.chaptersAvailable > 0) || null
    }
    readonly property var otherBooks: LibraryLogic.otherBooks(libraryBooks, Player.bookId, nextVolume ? nextVolume.bookId : "")
    property real pageT: page
    property point thumbFrom: Qt.point(0, 0)
    property real thumbW: 44
    property real barTop: 0

    readonly property bool wide: width >= Theme.widthLarge
    property real wideT: wide ? 1 : 0
    Behavior on wideT {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    function blend(narrow, broad) { return narrow + (broad - narrow) * wideT }
    // "Giảm hiệu ứng" của Windows: không bay / trượt, chỉ mờ <= 120 ms
    readonly property real g: Theme.reduceMotion ? (open ? 1 : 0) : p
    readonly property real fade: Math.max(0, Math.min(1, (g - 0.2) / 0.8))
    readonly property bool windowShown: Window.window !== null && Window.visibility !== Window.Minimized && Window.visibility !== Window.Hidden
    readonly property bool textWanted: open && windowShown && (wideT > 0 || page === 1)
    readonly property bool showText: wide ? sidePage === 1 : ReadAlong.status === "idle" || ReadAlong.status === "loading" || ReadAlong.timed
    property bool displayedText: true
    property real panelOpacity: 1
    onShowTextChanged: panelMotion.restart()
    SequentialAnimation {
        id: panelMotion
        NumberAnimation { target: root; property: "panelOpacity"; to: 0; duration: Theme.reduceMotion ? 60 : Theme.motionFastOut }
        ScriptAction { script: root.displayedText = root.showText }
        NumberAnimation { target: root; property: "panelOpacity"; to: 1; duration: Theme.reduceMotion ? 90 : Theme.motionMedium }
    }
    Component.onCompleted: displayedText = showText
    visible: p > 0
    opacity: Theme.reduceMotion ? p : 1
    z: 40

    Behavior on pageT {
        NumberAnimation {
            duration: Theme.reduceMotion ? 0 : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    Binding { target: ReadAlong; property: "active"; value: root.textWanted }

    function capture() {
        if (!bar) return
        const t = bar.thumb.mapToItem(root, 0, 0)
        thumbFrom = Qt.point(t.x, t.y)
        thumbW = bar.thumb.width
        barTop = bar.mapToItem(root, 0, 0).y
    }
    function show() {
        if (open || !Player.loaded) return
        capture()
        page = 0
        sidePage = ReadAlong.status === "ready" && !ReadAlong.timed ? 0 : 1
        columnScroll.contentY = 0
        open = true
        Nav.openLayer(root)
        speed.close(); sleep.close(); chapters.close()
    }
    function close() {
        if (!open) return
        capture()
        open = false
        speed.close(); sleep.close(); chapters.close(); music.close(); more.close(); shortcuts.close(); reader.close(); recommendations.close(); suggestions.close(); output.close(); voice.close()
        Nav.closedLayer(root)
    }
    onOpenChanged: {
        anim.stop()
        anim.to = open ? 1 : 0
        anim.duration = Theme.reduceMotion ? 120 : (open ? Theme.motionSlow : Theme.motionSlowOut)
        anim.easing.bezierCurve = open ? Theme.easeDecelerate : Theme.easeAccelerate
        anim.start()
    }
    // Đang mở mà sách bị đóng (không còn gì để nghe): thu lại ngay
    Connections {
        target: Player
        function onLoadedChanged() { if (!Player.loaded && root.open) root.close() }
    }
    NumberAnimation {
        id: anim
        target: root
        property: "p"
        easing.type: Easing.BezierSpline
    }

    // ---- số đo bố cục ----
    readonly property real gap: 48
    readonly property real topH: 72
    readonly property real colW: blend(Math.min(width - 2 * Theme.margin, 520), Math.min(440, Math.floor((width - 2 * Theme.margin - gap) * 0.42)))
    readonly property real colX: blend((width - colW) / 2, Theme.margin)
    readonly property real titlesH: titles.implicitHeight
    readonly property real controlsH: controls.implicitHeight
    readonly property real coverAvail: blend(height - 24 - controlsH - 16 - topH - titlesH - 16,
                                             height - topH - 24 - titlesH - 16 - controlsH - 24 - 24)
    readonly property real coverW: Math.max(120, Math.min(colW, Math.floor(coverAvail / Theme.coverRatio)))
    readonly property real coverH: Math.round(coverW * Theme.coverRatio)
    readonly property real blockH: coverH + 16 + titlesH + (24 + controlsH) * wideT
    readonly property real regionBottom: blend(height - 24 - controlsH - 16, height - 24)
    readonly property real blockY: topH + Math.max(0, (regionBottom - topH - blockH) / 2)
    readonly property real coverX: colX + (colW - coverW) / 2
    readonly property real coverY: blockY
    readonly property real titlesY: coverY + coverH + 16
    readonly property real controlsY: blend(Math.max(height - 24 - controlsH, page === 0 ? titlesY + titlesH + 24 : 0), titlesY + titlesH + 24)
    readonly property real shift: 64
    readonly property real coverPageX: -pageT * shift * (1 - wideT)
    readonly property real coverPageOpacity: blend(1 - pageT, 1)
    readonly property real textX: blend((width - Math.min(width - 2 * Theme.margin, 720)) / 2, colX + colW + gap)
    readonly property real textW: blend(Math.min(width - 2 * Theme.margin, 720), width - Theme.margin - textX)
    readonly property real textTop: blend(topH, topH - 24)
    readonly property real textBottom: blend(height - 24 - controlsH - 16, height)

    // ---- khung vẽ: mép trên đi từ mép trên thanh phát lên tới đỉnh ----
    Item {
        id: panel
        y: root.barTop * (1 - root.g)
        width: root.width
        height: root.height - y
        clip: true

        Rectangle {
            anchors.fill: parent
            color: Theme.bg
            opacity: Math.min(1, root.g * 2.5)
        }
        Item {
            id: stage
            y: -panel.y
            width: root.width
            height: root.height

            // Bìa lớn: cùng một bức ảnh với bìa nhỏ của thanh, đi từ chỗ bìa nhỏ tới chỗ của nó theo đường thẳng
            Flickable {
                id: columnScroll
                objectName: "nowColumnScroll"
                x: 0; y: root.topH
                width: root.wide ? root.colX + root.colW + Theme.margin : parent.width
                height: Math.max(0, parent.height - y)
                contentWidth: width
                contentHeight: Math.max(height, root.controlsY + controls.height - root.topH + Theme.s24,
                                        root.titlesY + titles.height - root.topH + Theme.s24)
                boundsBehavior: Flickable.StopAtBounds
                interactive: root.open && contentHeight > height
                clip: true
                Item {
                id: coverLayer
                x: root.coverPageX
                opacity: root.coverPageOpacity
                width: parent.width
                height: parent.height
                CoverView {
                    id: bigCover
                    width: root.coverW
                    height: root.coverH
                    x: root.thumbFrom.x + (root.coverX - root.thumbFrom.x) * root.g
                    y: root.thumbFrom.y + (root.coverY - root.thumbFrom.y) * root.g - root.topH + columnScroll.contentY * (1 - root.g)
                    scale: (root.thumbW / width) + (1 - root.thumbW / width) * root.g
                    transformOrigin: Item.TopLeft
                    coverKey: Player.coverKey
                    title: Player.bookTitle
                    radius: Theme.radiusCover
                }
                }
                SmoothWheel { flick: columnScroll; enabled: columnScroll.interactive }
                Scrollbar { parent: stage; target: columnScroll }
            }

            Item {
                id: inner
                width: parent.width
                height: parent.height
                y: (1 - root.g) * 28
                opacity: root.fade

                // ---- hàng trên ----
                IconButton {
                    id: moreButton; objectName: "nowMore"
                    x: root.colX + root.colW - width
                    y: Theme.s16
                    icon: "ellipsis"; tip: "Thêm tuỳ chọn"
                    onClicked: more.toggle()
                }
                Text {
                    x: root.colX + 44; y: Theme.s16 + 12
                    width: Math.max(0, root.colW - 88)
                    horizontalAlignment: Text.AlignHCenter
                    text: "Đang nghe"; color: Theme.text2; font.pixelSize: Theme.sizeCaption
                    opacity: root.wideT
                }
                IconButton {
                    x: root.blend(root.colX, Theme.margin) - 10
                    y: Theme.s16
                    icon: "chevron-down"
                    tip: "Thu nhỏ (Esc)"
                    onClicked: root.close()
                }
                PageSwitch {
                    visible: opacity > 0
                    opacity: 1 - root.wideT
                    enabled: !root.wide
                    x: Math.round((root.width - width) / 2)
                    y: Theme.s16 + 2
                    labels: ["Bìa", ReadAlong.status === "ready" && !ReadAlong.timed ? "Chương" : "Đọc theo"]
                    index: root.page
                    onPicked: (i) => root.page = i
                }

                // ---- tên ----
                Column {
                    id: titles
                    parent: columnScroll.contentItem
                    x: root.colX + root.coverPageX
                    y: root.titlesY - root.topH + (1 - root.g) * (28 + columnScroll.contentY)
                    width: root.colW
                    opacity: root.coverPageOpacity * root.fade
                    spacing: 4
                    Text {
                        objectName: "nowChapterTitle"
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: [Player.chapterTitle, Player.chapterSubtitle].filter(s => s !== "").join(" · ")
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeSection
                        font.weight: Theme.weightBold
                    }
                    PlayerSubtitle { width: parent.width; horizontalAlignment: Text.AlignHCenter }
                    Text {
                        visible: Player.narrator !== ""
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: Player.narrator.toLowerCase().startsWith("giọng") ? Player.narrator : "Giọng " + Player.narrator
                        color: Theme.text3
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                    }
                    MusicCredit { width: parent.width }
                }

                // ---- điều khiển ----
                Column {
                    id: controls
                    parent: columnScroll.contentItem
                    x: root.colX
                    y: root.controlsY - root.topH + (1 - root.g) * (28 + columnScroll.contentY)
                    width: root.colW
                    opacity: root.fade
                    spacing: Theme.s12

                    Collapse {
                        id: status
                        open: Player.atEnd !== "none"
                        width: parent.width
                        spacing: Theme.s8
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: Player.error !== "" ? Player.error
                                : (Player.atEnd === "finished" ? (root.nextVolume ? "Đã nghe hết cuốn này." : "Đã nghe hết sách") : "Đã nghe hết phần đã có.")
                            color: Player.error !== "" ? Theme.danger : Theme.text2
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Text {
                            width: parent.width; horizontalAlignment: Text.AlignHCenter
                            opacity: Player.atEnd === "caughtUp" ? 1 : 0; visible: opacity > 0
                            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
                            text: root.currentBook.producing ? "Chương tiếp theo sẽ nghe được khi máy làm xong chương ấy." : "Các chương sau chưa có audio."
                            color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption
                        }
                        Button {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: Player.atEnd === "finished"
                            kind: "text"
                            text: Player.error !== "" ? "Thử lại" : "Nghe lại từ đầu"
                            onClicked: Player.error !== "" ? Player.retry() : Player.restart()
                        }
                        Button {
                            objectName: "nowNextVolume"
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: Player.atEnd === "finished" && !!root.nextVolume
                            kind: "ghost"; text: "Nghe tiếp"
                            tip: root.nextVolume ? root.nextVolume.title : ""
                            onClicked: Player.playBook(root.nextVolume.bookId)
                        }
                        Button {
                            objectName: "nowOtherBooks"
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: Player.atEnd === "finished"
                            kind: "ghost"; text: "Nghe cuốn khác"
                            onClicked: recommendations.show()
                        }
                    }
                    PlayerFade { width: parent.width }
                    PlayerAlert { width: parent.width; onVoiceRequested: voice.fromAlert(); onSettingsRequested: root.settingsRequested("voice") }
                    Collapse {
                        width: parent.width; open: Player.sleepKind === "chapter" && !Player.fading
                        Text { width: parent.width; text: "Sẽ dừng khi hết chương này."; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                    }
                    SeekBar {
                        id: seek
                        width: parent.width
                    }
                    Item {
                        width: parent.width
                        height: elapsed.implicitHeight
                        Text {
                            id: elapsed
                            text: Player.clockText(seek.shownPosition)
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                        }
                        Text {
                            anchors.right: parent.right
                            text: "-" + Player.clockText(Math.max(0, seek.total - seek.shownPosition) / Player.rate)
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                        }
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: Theme.s8
                        IconButton {
                            icon: "skip-back"
                            enabled: Player.loaded
                            tip: "Chương trước (Shift+←)"
                            onClicked: Player.previous()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        SkipButton { forward: false; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        PlayButton { size: 56; anchors.verticalCenter: parent.verticalCenter }
                        SkipButton { forward: true; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        IconButton {
                            icon: "skip-forward"
                            enabled: Player.loaded && Player.chapters.rowOf(Player.chapterId) < Player.chapters.count - 1
                            opacity: enabled ? 1 : 0.4
                            tip: Player.canNext ? "Chương sau (Shift+→)" : Player.chapters.rowOf(Player.chapterId) >= Player.chapters.count - 1 ? "Đây là chương cuối" : "Chương sau chưa có audio"
                            onClicked: Player.next()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Flow {
                        id: chips
                        width: parent.width
                        spacing: Theme.s8
                        Accessible.role: Accessible.Grouping
                        Accessible.name: "Điều khiển phụ"
                        // Natural text + padding; wrap rather than stretching
                        // secondary actions across the entire player column.
                        property real musicT: 0
                        Behavior on musicT { NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                        readonly property real musicW: musicT * (Theme.buttonHeight + spacing)
                        move: Transition {
                            NumberAnimation { properties: "x,y"; duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
                        }
                        ControlChip {
                            id: speedChip
                            objectName: "nowSpeed"
                            text: Player.rate === 1 ? "Tốc độ" : String(Player.rate).replace(".", ",") + "×"
                            active: Player.rate !== 1
                            tip: "Tốc độ đọc"
                            onClicked: speed.toggle()
                        }
                        ControlChip {
                            id: sleepChip
                            objectName: "nowSleep"
                            icon: "moon"
                            // Nhãn trên nút có đơn vị ("14 phút", "40 giây") như web (sleepButtonLabel): "14:51" cạnh nút tốc độ trông như giờ đồng hồ
                            text: Player.sleepKind === "minutes"
                                ? (Player.clock.sleepLeft < 60 ? Math.max(1, Math.ceil(Player.clock.sleepLeft)) + " giây" : Math.ceil(Player.clock.sleepLeft / 60) + " phút")
                                : (Player.sleepKind === "chapter" ? "Hết chương" : "Hẹn giờ")
                            active: Player.sleepKind !== "off"
                            tip: "Hẹn giờ tắt"
                            Accessible.name: Player.sleepKind === "minutes"
                                ? Player.clock.sleepLeft < 60 ? `Hẹn giờ tắt: còn ${Math.ceil(Player.clock.sleepLeft)} giây` : `Hẹn giờ tắt: còn ${Math.ceil(Player.clock.sleepLeft / 60)} phút`
                                : "Hẹn giờ tắt"
                            onClicked: sleep.toggle()
                        }
                        ControlChip {
                            id: chaptersChip
                            objectName: "nowChapters"
                            width: implicitWidth * (1 - root.wideT)
                            opacity: 1 - root.wideT
                            visible: opacity > 0
                            enabled: !root.wide
                            icon: "list-ordered"
                            text: "Chương"
                            tip: "Danh sách chương"
                            onClicked: chapters.toggle()
                        }
                        ControlChip {
                            id: musicChip
                            visible: chips.musicT > 0
                            width: Math.max(0, chips.musicW - chips.spacing)
                            opacity: chips.musicT
                            icon: "eighth-note"
                            struck: !Music.enabled
                            active: Music.enabled
                            tip: "Nhạc nền"
                            onClicked: music.toggle()
                        }
                    }
                }

                // ---- văn bản chạy theo giọng / danh sách chương ----
                Item {
                    id: textRegion
                    objectName: "nowReadAlongRegion"
                    x: root.textX + (1 - root.pageT) * root.shift * (1 - root.wideT)
                    y: root.textTop
                    width: root.textW
                    height: Math.max(0, root.textBottom - root.textTop)
                    opacity: root.blend(root.pageT, 1)
                    visible: opacity > 0.01
                    enabled: root.wide || root.page === 1

                    PageSwitch {
                        id: sideTabs; objectName: "nowSideTabs"
                        x: 0; y: Theme.s16
                        labels: ["Chương", "Đọc theo"]
                        index: root.sidePage
                        onPicked: i => root.sidePage = i
                        opacity: root.wideT; visible: opacity > 0
                    }

                    ReadAlongView {
                        objectName: "nowReadAlong"
                        anchors.fill: parent
                        anchors.topMargin: root.wide ? sideTabs.height + 2 * Theme.s16 : 0
                        visible: root.displayedText
                        opacity: root.panelOpacity
                        enabled: root.showText
                    }
                    ChapterList {
                        objectName: "nowChapterList"
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: Math.min(parent.width, Theme.listMeasure)
                        anchors.topMargin: root.wide ? sideTabs.height + 2 * Theme.s16 : Theme.s24
                        visible: !root.displayedText
                        opacity: root.panelOpacity
                        enabled: !root.showText
                        model: Player.chapters
                        onChapterClicked: (chapterId) => Player.jumpTo(chapterId, 0)
                        onReadRequested: chapterId => reader.begin(Player.bookId, chapterId)
                        Component.onCompleted: positionViewAtIndex(Math.max(0, Player.chapters.rowOf(Player.chapterId)), ListView.Center)
                    }
                }
            }
        }
    }

    // ---- bảng nổi ----
    SpeedPopover { id: speed; anchorItem: speedChip }
    SleepPopover { id: sleep; anchorItem: sleepChip }
    ChaptersPopover { id: chapters; anchorItem: chaptersChip; onReadRequested: chapterId => reader.begin(Player.bookId, chapterId) }
    MusicPopover { id: music; anchorItem: moreButton }
    ChapterReader { id: reader }
    ReadingSuggestions { id: suggestions; objectName: "nowSuggestions"; bookId: Player.bookId }
    ShortcutsDialog { id: shortcuts; letters: Api.preferences.letterShortcuts !== false }
    Modal {
        id: recommendations; objectName: "nowRecommendations"; title: "Nghe cuốn khác"
        Column {
            width: parent.width; spacing: Theme.s8
            Repeater {
                model: root.otherBooks
                Button {
                    required property var modelData
                    width: parent.width; wrap: true; kind: "ghost"; icon: "play"; text: modelData.title
                    onClicked: { recommendations.close(); Player.playBook(modelData.bookId) }
                }
            }
            Button { text: "Về Thư viện"; kind: "ghost"; onClicked: { recommendations.close(); root.close(); if (Nav.stack) Nav.stack.show(0) } }
        }
    }
    Popover {
        id: more; objectName: "nowMoreMenu"; anchorItem: moreButton; panelWidth: 320; maxHeight: 600
        Column {
            width: parent.width; spacing: Theme.s8
            Text {
                width: parent.width; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption
                text: {
                    const p = LibraryLogic.progress(root.currentBook)
                    if (p.finished) return "Đã nghe hết cả cuốn"
                    const total = p.totalSeconds || root.currentBook.duration || 0, heard = Math.min(total, p.heardSeconds || 0)
                    if (!total) return `Chưa nghe · ${root.currentBook.chaptersTotal || 0} chương`
                    if (!heard) return `Chưa nghe · ${Player.lengthText(total)}`
                    const scope = root.currentBook.complete ? "cả cuốn" : "phần đã có"
                    const remaining = Player.rate === 1 ? "còn " + Player.lengthText(total - heard) : "còn khoảng " + Player.lengthText((total - heard) / Player.rate) + " ở tốc độ " + String(Player.rate).replace(".", ",") + "×"
                    return `Đã nghe ${Math.round(heard / total * 100) + "%"} ${scope} · ${remaining}`
                }
            }
            VolumeControl { width: parent.width }
            MenuRow { width: parent.width; text: "Nhạc nền"; icon: "eighth-note"; visible: Music.hasMusic; onClicked: { more.close(); music.show() } }
            MenuRow { objectName: "nowVoice"; width: parent.width; text: "Giọng đọc"; icon: "audio-lines"; visible: Player.speaking && Api.voiceList.length > 0; onClicked: { more.close(); voice.show() } }
            MenuRow { objectName: "nowOutput"; width: parent.width; text: "Thiết bị phát"; icon: "cast"; onClicked: { more.close(); output.show() } }
            MenuRow { objectName: "nowHistory"; width: parent.width; text: "Về chỗ vừa nghe"; icon: "undo-2"; visible: Player.canGoBack; onClicked: { more.close(); Player.goBack() } }
            MenuRow { objectName: "nowKeys"; width: parent.width; text: "Phím tắt"; icon: "keyboard"; onClicked: { more.close(); shortcuts.show() } }
            MenuRow { objectName: "nowAddVoice"; width: parent.width; text: "Thêm giọng…"; icon: "plus"; onClicked: { more.close(); root.settingsRequested("voice") } }
            MenuRow { objectName: "nowSuggestionsButton"; width: parent.width; text: "Gợi ý đọc"; icon: "lightbulb"; visible: suggestions.groups.length > 0; onClicked: { more.close(); suggestions.show() } }
            MenuRow { width: parent.width; text: "Cửa sổ mini"; icon: "picture-in-picture-2"; onClicked: { more.close(); if (Nav.windowMode) Nav.windowMode.enter() } }
        }
    }
    OutputPopover { id: output; anchorItem: moreButton }
    PlayerVoicePopover { id: voice; anchorItem: moreButton; onSettingsRequested: root.settingsRequested("voice") }
}
