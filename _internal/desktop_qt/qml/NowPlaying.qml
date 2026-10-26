import QtQuick
import ABook

// Đang nghe: phủ kín khung nội dung (thanh bên vẫn ở đó). Mở bằng cách biến thanh phát: bìa nhỏ lớn dần thành bìa lớn theo đường thẳng, phần còn lại trượt lên;
// đóng là đúng gương (Esc, Alt+Left, nút Back của chuột đều đóng). Chỉ một tiến độ p chạy 0..1, mọi thứ là hàm của p - không có mờ thuần.
//   Rộng (khung >= 1100 px): cột trái = bìa, tên, thanh tua, nút phát, rồi Tốc độ / Hẹn giờ / Chương / Nhạc nền; cột phải = văn bản chạy theo giọng
//   (sách chưa có mốc thì danh sách chương). Hẹp: một cột, công tắc "Bìa / Đọc theo" trượt theo thứ tự.
Item {
    id: root
    property Item bar: null
    property bool open: false
    property real p: 0
    property int page: 0                         // hẹp: 0 = Bìa, 1 = Chữ/Chương
    property real pageT: page
    property point thumbFrom: Qt.point(0, 0)
    property real thumbW: 44
    property real barTop: 0

    readonly property bool wide: width >= 1100
    // "Giảm hiệu ứng" của Windows: không bay / trượt, chỉ mờ <= 120 ms
    readonly property real g: Theme.reduceMotion ? (open ? 1 : 0) : p
    readonly property real fade: Math.max(0, Math.min(1, (g - 0.2) / 0.8))
    readonly property bool windowShown: Window.window !== null && Window.visibility !== Window.Minimized && Window.visibility !== Window.Hidden
    readonly property bool textWanted: open && windowShown && (wide || page === 1)
    readonly property bool showText: ReadAlong.status === "idle" || ReadAlong.status === "loading" || ReadAlong.timed
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
        open = true
        Nav.openLayer(root)
        speed.close(); sleep.close(); chapters.close()
    }
    function close() {
        if (!open) return
        capture()
        open = false
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
    readonly property real colW: wide ? Math.min(440, Math.floor((width - 2 * Theme.margin - gap) * 0.42)) : Math.min(width - 2 * Theme.margin, 520)
    readonly property real colX: wide ? Theme.margin : Math.round((width - colW) / 2)
    readonly property real titlesH: titles.implicitHeight
    readonly property real controlsH: controls.implicitHeight
    readonly property real coverAvail: wide ? height - topH - 24 - titlesH - 16 - controlsH - 24 - 24
                                            : height - 24 - controlsH - 16 - topH - titlesH - 16
    readonly property real coverW: Math.max(120, Math.min(colW, Math.floor(coverAvail / Theme.coverRatio)))
    readonly property real coverH: Math.round(coverW * Theme.coverRatio)
    readonly property real blockH: coverH + 16 + titlesH + (wide ? 24 + controlsH : 0)
    readonly property real regionBottom: wide ? height - 24 : height - 24 - controlsH - 16
    readonly property real blockY: topH + Math.max(0, (regionBottom - topH - blockH) / 2)
    readonly property real coverX: colX + (colW - coverW) / 2
    readonly property real coverY: blockY
    readonly property real titlesY: coverY + coverH + 16
    readonly property real controlsY: wide ? titlesY + titlesH + 24 : height - 24 - controlsH
    readonly property real shift: 64
    readonly property real coverPageX: wide ? 0 : -pageT * shift
    readonly property real coverPageOpacity: wide ? 1 : 1 - pageT
    readonly property real textX: wide ? colX + colW + gap : Math.round((width - Math.min(width - 2 * Theme.margin, 720)) / 2)
    readonly property real textW: wide ? width - Theme.margin - textX : Math.min(width - 2 * Theme.margin, 720)
    readonly property real textTop: wide ? topH - 24 : topH
    readonly property real textBottom: wide ? height : height - 24 - controlsH - 16

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
                    y: root.thumbFrom.y + (root.coverY - root.thumbFrom.y) * root.g
                    scale: (root.thumbW / width) + (1 - root.thumbW / width) * root.g
                    transformOrigin: Item.TopLeft
                    coverKey: Player.coverKey
                    title: Player.bookTitle
                    radius: Theme.radiusCover
                }
            }

            Item {
                id: inner
                width: parent.width
                height: parent.height
                y: (1 - root.g) * 28
                opacity: root.fade

                // ---- hàng trên ----
                IconButton {
                    x: (root.wide ? Theme.margin : root.colX) - 10
                    y: Theme.s16
                    icon: "chevron-down"
                    tip: "Thu nhỏ (Esc)"
                    onClicked: root.close()
                }
                PageSwitch {
                    visible: !root.wide
                    x: Math.round((root.width - width) / 2)
                    y: Theme.s16 + 2
                    labels: ["Bìa", ReadAlong.status === "ready" && !ReadAlong.timed ? "Chương" : "Đọc theo"]
                    index: root.page
                    onPicked: (i) => root.page = i
                }

                // ---- tên ----
                Column {
                    id: titles
                    x: root.colX + root.coverPageX
                    y: root.titlesY
                    width: root.colW
                    opacity: root.coverPageOpacity
                    spacing: 4
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: Player.bookTitle
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeSection
                        font.weight: Theme.weightBold
                    }
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: [Player.chapterTitle, Player.chapterSubtitle].filter(s => s !== "").join(" · ")
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Text {
                        visible: Player.narrator !== ""
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: Player.narrator.toLowerCase().startsWith("giọng") ? Player.narrator : "Giọng " + Player.narrator
                        color: Theme.text3
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                    }
                }

                // ---- điều khiển ----
                Column {
                    id: controls
                    x: root.colX
                    y: root.controlsY
                    width: root.colW
                    spacing: Theme.s12

                    Column {
                        id: status
                        visible: Player.error !== "" || Player.atEnd !== "none"
                        width: parent.width
                        spacing: Theme.s8
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: Player.error !== "" ? Player.error
                                : (Player.atEnd === "finished" ? "Đã nghe hết sách" : "Đã nghe hết phần đã có. Chương mới sẽ hiện ở đây khi làm xong.")
                            color: Player.error !== "" ? Theme.danger : Theme.text2
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Button {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: Player.error !== "" || Player.atEnd === "finished"
                            kind: "text"
                            text: Player.error !== "" ? "Thử lại" : "Nghe lại từ đầu"
                            onClicked: Player.error !== "" ? Player.retry() : Player.restart()
                        }
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
                            text: "-" + Player.clockText(Math.max(0, seek.total - seek.shownPosition))
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
                            tip: "Chương trước (Ctrl+←)"
                            onClicked: Player.previous()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        SkipButton { forward: false; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        PlayButton { size: 56; anchors.verticalCenter: parent.verticalCenter }
                        SkipButton { forward: true; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        IconButton {
                            icon: "skip-forward"
                            enabled: Player.canNext
                            opacity: enabled ? 1 : 0.4
                            tip: Player.canNext ? "Chương sau (Ctrl+→)" : "Chưa có chương sau để nghe"
                            onClicked: Player.next()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Row {
                        id: chips
                        width: parent.width
                        spacing: Theme.s8
                        readonly property real cellW: (width - (count - 1) * spacing) / count
                        readonly property int count: 3
                        ControlChip {
                            id: speedChip
                            width: chips.cellW
                            text: Player.rate === 1 ? "Tốc độ" : String(Player.rate).replace(".", ",") + "×"
                            active: Player.rate !== 1
                            tip: "Tốc độ đọc"
                            onClicked: speed.toggle()
                        }
                        ControlChip {
                            id: sleepChip
                            width: chips.cellW
                            icon: "moon"
                            // Nhãn trên nút có đơn vị ("14 phút", "40 giây") như web (sleepButtonLabel): "14:51" cạnh nút tốc độ trông như giờ đồng hồ
                            text: Player.sleepKind === "minutes"
                                ? (Player.clock.sleepLeft < 60 ? Math.max(1, Math.ceil(Player.clock.sleepLeft)) + " giây" : Math.ceil(Player.clock.sleepLeft / 60) + " phút")
                                : (Player.sleepKind === "chapter" ? "Hết chương" : "Hẹn giờ")
                            active: Player.sleepKind !== "off"
                            tip: "Hẹn giờ tắt"
                            onClicked: sleep.toggle()
                        }
                        ControlChip {
                            id: chaptersChip
                            width: chips.cellW
                            icon: "list-ordered"
                            text: "Chương"
                            tip: "Danh sách chương"
                            onClicked: chapters.toggle()
                        }
                    }
                }

                // ---- văn bản chạy theo giọng / danh sách chương ----
                Item {
                    id: textRegion
                    x: root.textX + (root.wide ? 0 : (1 - root.pageT) * root.shift)
                    y: root.textTop
                    width: root.textW
                    height: Math.max(0, root.textBottom - root.textTop)
                    opacity: root.wide ? 1 : root.pageT
                    visible: root.wide || root.pageT > 0.01
                    enabled: root.wide || root.page === 1

                    ReadAlongView {
                        anchors.fill: parent
                        visible: root.showText
                    }
                    ChapterList {
                        anchors.fill: parent
                        anchors.topMargin: Theme.s24
                        visible: !root.showText
                        model: Player.chapters
                        onChapterClicked: (chapterId) => Player.jumpTo(chapterId, 0)
                        Component.onCompleted: positionViewAtIndex(Math.max(0, Player.chapters.rowOf(Player.chapterId)), ListView.Center)
                    }
                }
            }
        }
    }

    // ---- bảng nổi ----
    SpeedPopover { id: speed; anchorItem: speedChip }
    SleepPopover { id: sleep; anchorItem: sleepChip }
    ChaptersPopover { id: chapters; anchorItem: chaptersChip }
}
