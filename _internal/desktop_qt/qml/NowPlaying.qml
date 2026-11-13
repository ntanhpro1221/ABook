import "UiStrings.js" as S
import "UiNumber.js" as UiNumber
import QtQuick
import ABook
import "LibraryLogic.js" as LibraryLogic
import "TextWrap.js" as TextWrap

// Đang nghe: phủ kín khung nội dung (thanh bên vẫn ở đó). Mở bằng cách biến thanh phát: bìa nhỏ lớn dần thành bìa lớn theo đường thẳng, phần còn lại trượt lên;
// đóng là đúng gương (Esc, Alt+Left, nút Back của chuột đều đóng). Chỉ một tiến độ p chạy 0..1, mọi thứ là hàm của p - không có mờ thuần.
//   Khổ large trở lên: cột trái = bìa, tên, thanh tua, nút phát, rồi Tốc độ / Hẹn giờ / Chương / Nhạc nền; cột phải = văn bản chạy theo giọng
//   (sách chưa có mốc thì danh sách chương). Hẹp: một cột, công tắc S.s_copy_1e37d64a785f trượt (cùng chữ với Android và web) theo thứ tự.
Item {
    id: root
    property Item bar: null
    property bool open: false
    property real p: 0
    property int page: 0                         // hẹp: 0 = Nghe (bìa), 1 = Chữ/Chương
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
    property var sharedFrames: []
    property rect playFrom: Qt.rect(0, 0, 44, 44)
    property rect playTo: Qt.rect(0, 0, 56, 56)
    Binding { target: root.bar; property: "sharedShown"; value: root.p <= 0; when: root.bar !== null }
    function itemFrame(item) {
        const point = item.mapToItem(root, 0, 0)
        return Qt.rect(point.x, point.y, item.width, item.height)
    }
    function barFrame(item) {
        const box = itemFrame(item)
        return Qt.rect(box.x, box.y - bar.contentShift, box.width, box.height)
    }
    function textFrame(from, to) {
        return {from: barFrame(from), to: itemFrame(to),
            fromSize: from.font.pixelSize, toSize: to.font.pixelSize,
            fromWeight: from.font.weight, toWeight: to.font.weight,
            fromColor: from.color, toColor: to.color,
            fromAlign: from.horizontalAlignment, toAlign: to.horizontalAlignment,
            fromInk: from.paintedWidth,
            text: to.text}
    }

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
    // S.s_copy_4cc215f21497 của Windows: không bay / trượt, chỉ mờ <= 120 ms
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
            duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionMedium
            easing.type: Easing.BezierSpline
            easing.bezierCurve: Theme.easeStandard
        }
    }
    Binding { target: ReadAlong; property: "active"; value: root.textWanted }

    function capture() {
        if (!bar) return
        const t = bar.thumb.mapToItem(root, 0, 0)
        thumbFrom = Qt.point(t.x, t.y - bar.contentShift)
        thumbW = bar.thumb.width
        barTop = bar.mapToItem(root, 0, 0).y
        sharedFrames = [textFrame(bar.chapterLabel, chapterTitle), textFrame(bar.bookLabel, bookSubtitle.bookLabel)]
        playFrom = barFrame(bar.playButton)
        playTo = itemFrame(fullPlay)
    }
    signal bookRequested()
    function show() {
        if (open || !Player.loaded) return
        columnScroll.contentY = 0
        capture()
        page = 0
        sidePage = ReadAlong.status === "ready" && !ReadAlong.timed ? 0 : 1
        open = true
        Nav.openLayer(root)
        speed.close(); sleep.close(); chapters.close()
    }
    function close() {
        if (!open) return
        capture()
        open = false
        speed.close(); sleep.close(); chapters.close(); music.close(); more.close(); audioFx.close(); shortcuts.close(); reader.close(); recommendations.close(); suggestions.close(); output.close(); voice.close()
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
    readonly property real displayedTitlesY: titlesY + (topH + Theme.s8 - titlesY) * pageT * (1 - wideT)
    readonly property real controlsY: blend(Math.max(height - 24 - controlsH, page === 0 ? titlesY + titlesH + 24 : 0), titlesY + titlesH + 24)
    readonly property real shift: 64
    readonly property real coverPageX: -pageT * shift * (1 - wideT)
    readonly property real coverPageOpacity: blend(1 - pageT, 1)
    readonly property real textX: blend((width - Math.min(width - 2 * Theme.margin, 720)) / 2, colX + colW + gap)
    readonly property real textW: blend(Math.min(width - 2 * Theme.margin, 720), width - Theme.margin - textX)
    readonly property real textTop: blend(topH + (titlesH + Theme.s24) * pageT, topH - 24)
    readonly property real textBottom: blend(height - 24 - controlsH - 16, height)

    // ---- khung vẽ: mép trên đi từ mép trên thanh phát lên tới đỉnh ----
    Item {
        id: panel; objectName: "nowMorphPanel"
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
                    id: bigCover; objectName: "nowCover"
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
                    icon: "ellipsis"; tip: S.s_them_tuy_chon_a0b4bb6e
                    onClicked: more.toggle()
                }
                Text {
                    x: root.colX + 44; y: Theme.s16 + 12
                    width: Math.max(0, root.colW - 88)
                    horizontalAlignment: Text.AlignHCenter
                    text: S.s_dang_nghe_9310d8cf; color: Theme.text2; font.pixelSize: Theme.sizeCaption
                    opacity: root.wideT
                }
                IconButton {
                    x: root.blend(root.colX, Theme.margin) - 10
                    y: Theme.s16
                    icon: "chevron-down"
                    tip: S.s_thu_nho_esc_884a3a3e
                    onClicked: root.close()
                }
                PageSwitch {
                    visible: opacity > 0
                    opacity: 1 - root.wideT
                    enabled: !root.wide
                    x: Math.round((root.width - width) / 2)
                    y: Theme.s16 + 2
                    labels: [S.s_nghe_a43aafef, ReadAlong.status === "ready" && !ReadAlong.timed ? S.s_chuong_2d157977 : S.s_doc_theo_df342819]
                    index: root.page
                    onPicked: (i) => root.page = i
                }

                // ---- tên ----
                Column {
                    id: titles
                    parent: columnScroll.contentItem
                    x: root.colX
                    y: root.displayedTitlesY - root.topH
                    width: root.colW
                    spacing: 4
                    Text {
                        id: chapterTitle
                        objectName: "nowChapterTitle"
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: TextWrap.keepDots([Player.chapterTitle, Player.chapterSubtitle].filter(s => s !== "").join("\u00a0·\u00a0"))
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeSection
                        font.weight: Theme.weightBold
                        opacity: root.g >= 1 ? 1 : 0
                    }
                    PlayerSubtitle { id: bookSubtitle; width: parent.width; horizontalAlignment: Text.AlignHCenter; chevron: true; opacity: root.g >= 1 ? 1 : 0; onBookRequested: root.bookRequested() }
                    Text {
                        id: narratorLabel
                        Reveal { shown: Player.narrator !== "" }
                        opacity: Math.max(0, Math.min(1, (root.g - 0.9) * 10))
                        transform: Translate { y: Theme.reduceMotion ? 0 : (1 - narratorLabel.opacity) * 8 }
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: Player.narrator.toLowerCase().startsWith(S.s_giong_35c0fe3c) ? Player.narrator : S.s_giong_7e6f9338 + Player.narrator
                        color: Theme.text3
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                    }
                    MusicCredit { width: parent.width; transform: Translate { y: Theme.reduceMotion ? 0 : (1 - root.fade) * 8 } }
                }

                // ---- điều khiển ----
                Column {
                    id: controls; objectName: "nowControls"
                    parent: columnScroll.contentItem
                    x: root.colX
                    y: root.controlsY - root.topH
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
                                : (Player.atEnd === "finished" ? (root.nextVolume ? S.s_da_nghe_het_cuon_nay_05edcdd9 : S.s_da_nghe_het_sach_2fefde33) : S.s_da_nghe_het_phan_da_co_56906a54)
                            color: Player.error !== "" ? Theme.danger : Theme.text2
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Text {
                            width: parent.width; horizontalAlignment: Text.AlignHCenter
                            opacity: Player.atEnd === "caughtUp" ? 1 : 0; visible: opacity > 0
                            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
                            text: root.currentBook.producing ? S.s_chuong_tiep_theo_se_nghe_duoc_khi_may_lam_2d887378 : S.s_cac_chuong_sau_chua_co_audio_44723dd5
                            color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption
                        }
                        Collapse {
                            width: parent.width; open: Player.atEnd === "finished"
                            Button {
                                anchors.horizontalCenter: parent.horizontalCenter
                                kind: "text"
                                text: Player.error !== "" ? S.s_thu_lai_c58d068c : S.s_nghe_lai_tu_dau_e251d632
                                onClicked: Player.error !== "" ? Player.retry() : Player.restart()
                            }
                        }
                        Collapse {
                            width: parent.width; open: Player.atEnd === "finished" && !!root.nextVolume
                            Button {
                                objectName: "nowNextVolume"
                                anchors.horizontalCenter: parent.horizontalCenter
                                kind: "ghost"; text: S.s_nghe_tiep_403b90a5
                                tip: root.nextVolume ? root.nextVolume.title : ""
                                onClicked: Player.playBook(root.nextVolume.bookId)
                            }
                        }
                        Collapse {
                            width: parent.width; open: Player.atEnd === "finished"
                            Button {
                                objectName: "nowOtherBooks"
                                anchors.horizontalCenter: parent.horizontalCenter
                                kind: "ghost"; text: S.s_nghe_cuon_khac_cc5cf8a7
                                onClicked: recommendations.show()
                            }
                        }
                    }
                    PlayerFade { width: parent.width }
                    PlayerAlert { width: parent.width; onVoiceRequested: voice.fromAlert(); onSettingsRequested: root.settingsRequested("voice") }
                    Collapse {
                        width: parent.width; open: Player.sleepKind === "chapter" && !Player.fading
                        Text { width: parent.width; text: S.s_se_dung_khi_het_chuong_nay_9c1f8c30; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                    }
                    SeekBar {
                        id: seek
                        width: parent.width
                    }
                    Item {
                        width: parent.width
                        height: elapsed.implicitHeight
                        ClockLabel {
                            id: elapsed
                            objectName: "nowElapsed"
                            text: Player.clockText(seek.shownPosition)
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                        }
                        ClockLabel {
                            objectName: "nowRemaining"
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
                            tip: S.s_chuong_truoc_shift_9994756d
                            onClicked: Player.previous()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        SkipButton { forward: false; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        PlayButton { id: fullPlay; objectName: "nowPlay"; size: 56; anchors.verticalCenter: parent.verticalCenter; opacity: root.g >= 1 ? 1 : 0 }
                        SkipButton { forward: true; iconSize: 28; anchors.verticalCenter: parent.verticalCenter }
                        IconButton {
                            icon: "skip-forward"
                            enabled: Player.loaded && Player.chapters.rowOf(Player.chapterId) < Player.chapters.count - 1
                            opacity: enabled ? 1 : 0.4
                            tip: Player.canNext ? S.s_chuong_sau_shift_20da5bb5 : Player.chapters.rowOf(Player.chapterId) >= Player.chapters.count - 1 ? S.s_day_la_chuong_cuoi_e4e693d4 : S.s_chuong_sau_chua_co_audio_e17e3d72
                            onClicked: Player.next()
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    Flow {
                        id: chips
                        width: parent.width
                        spacing: Theme.s8
                        Accessible.role: Accessible.Grouping
                        Accessible.name: S.s_dieu_khien_phu_bf325663
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
                            text: Player.rate === 1 ? S.s_toc_do_16ee0914 : UiNumber.decimal(Player.rate) + "×"
                            active: Player.rate !== 1
                            tip: S.s_toc_do_doc_3657e59d
                            onClicked: speed.toggle()
                        }
                        ControlChip {
                            id: sleepChip
                            objectName: "nowSleep"
                            icon: "moon"
                            // Nhãn trên nút có đơn vị (S.s_copy_521d621b4996, S.s_copy_7bb79ab52e37) như web (sleepButtonLabel): "14:51" cạnh nút tốc độ trông như giờ đồng hồ
                            text: Player.sleepKind === "minutes"
                                ? (Player.clock.sleepLeft < 60 ? Math.max(1, Math.ceil(Player.clock.sleepLeft)) + S.s_giay_9f6b3e22 : Math.ceil(Player.clock.sleepLeft / 60) + S.s_phut_cf728a6a)
                                : (Player.sleepKind === "chapter" ? S.s_het_chuong_f1d590bb : S.s_hen_gio_39d9ca26)
                            // Đếm ngược đổi tại chỗ: giữ chỗ cho hai chữ số, Flow không đẩy các nút bên cạnh mỗi phút / giây
                            reserve: Player.sleepKind === "minutes" ? [S.s_00_phut_347ed245, S.s_00_giay_27015af3] : []
                            active: Player.sleepKind !== "off"
                            tip: S.s_hen_gio_39d9ca26
                            Accessible.name: Player.sleepKind === "minutes"
                                ? Player.clock.sleepLeft < 60 ? S.s_hen_gio_tat_con_0_giay_ae60de9d(Math.ceil(Player.clock.sleepLeft)) : S.s_hen_gio_tat_con_0_phut_e53bab94(Math.ceil(Player.clock.sleepLeft / 60))
                                : S.s_hen_gio_39d9ca26
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
                            text: S.s_chuong_2d157977
                            tip: S.s_danh_sach_chuong_7fa755f9
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
                            tip: S.s_nhac_nen_271fb292
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
                        labels: [S.s_chuong_2d157977, S.s_doc_theo_df342819]
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
                        transform: Translate { x: Theme.reduceMotion ? 0 : (1 - root.panelOpacity) * 24 }
                        enabled: root.showText
                    }
                    ChapterList {
                        objectName: "nowChapterList"
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: Theme.listWidth(parent, parent.width)
                        anchors.topMargin: root.wide ? sideTabs.height + 2 * Theme.s16 : Theme.s24
                        visible: !root.displayedText
                        opacity: root.panelOpacity
                        transform: Translate { x: Theme.reduceMotion ? 0 : (1 - root.panelOpacity) * 24 }
                        enabled: !root.showText
                        model: Player.chapters
                        onChapterClicked: (chapterId) => Player.jumpTo(chapterId, 0)
                        onReadRequested: chapterId => reader.begin(Player.bookId, chapterId)
                        Component.onCompleted: positionViewAtIndex(Math.max(0, Player.chapters.rowOf(Player.chapterId)), ListView.Center)
                    }
                }
            }

            // Shared parts keep their own path from the mini player. The final
            // controls retain their layout slots, so the underlay never reflows.
            Item {
                objectName: "nowSharedMorph"
                anchors.fill: parent
                Reveal { shown: root.p > 0 && root.p < 1 }
                Repeater {
                    model: root.sharedFrames
                    Item {
                        required property var modelData
                        required property int index
                        objectName: index === 0 ? "nowChapterMorph" : "nowBookMorph"
                        x: modelData.from.x + (modelData.to.x - modelData.from.x) * root.g
                        y: modelData.from.y + (modelData.to.y - modelData.from.y) * root.g
                        width: modelData.from.width + (modelData.to.width - modelData.from.width) * root.g
                        height: modelData.from.height + (modelData.to.height - modelData.from.height) * root.g
                        Text {
                            width: parent.width; height: parent.height
                            x: (1 - root.g) * (parent.modelData.fromAlign === Text.AlignLeft ? -1 : parent.modelData.fromAlign === Text.AlignRight ? 1 : 0)
                                * Math.max(0, parent.modelData.from.width - parent.modelData.fromInk) / 2
                            text: parent.modelData.text; wrapMode: Text.Wrap
                            font.pixelSize: parent.modelData.fromSize + (parent.modelData.toSize - parent.modelData.fromSize) * root.g
                            font.weight: parent.modelData.fromWeight + (parent.modelData.toWeight - parent.modelData.fromWeight) * root.g
                            horizontalAlignment: parent.modelData.toAlign
                            color: Qt.rgba(parent.modelData.fromColor.r + (parent.modelData.toColor.r - parent.modelData.fromColor.r) * root.g,
                                           parent.modelData.fromColor.g + (parent.modelData.toColor.g - parent.modelData.fromColor.g) * root.g,
                                           parent.modelData.fromColor.b + (parent.modelData.toColor.b - parent.modelData.fromColor.b) * root.g, 1)
                        }
                    }
                }
                Item {
                    objectName: "nowPlayMorph"
                    x: root.playFrom.x + (root.playTo.x - root.playFrom.x) * root.g
                    y: root.playFrom.y + (root.playTo.y - root.playFrom.y) * root.g
                    width: 56; height: 56
                    scale: root.playFrom.width / 56 + (root.playTo.width - root.playFrom.width) / 56 * root.g
                    transformOrigin: Item.TopLeft
                    PlayButton { size: 56; activeFocusOnTab: false }
                }
            }
        }
    }

    // ---- bảng nổi ----
    SpeedPopover { id: speed; objectName: "nowSpeedSheet"; anchorItem: speedChip }
    SleepPopover { id: sleep; objectName: "nowSleepSheet"; anchorItem: sleepChip }
    ChaptersPopover { id: chapters; anchorItem: chaptersChip; onReadRequested: chapterId => reader.begin(Player.bookId, chapterId) }
    MusicPopover { id: music; anchorItem: moreButton }
    ChapterReader { id: reader }
    ReadingSuggestions { id: suggestions; objectName: "nowSuggestions"; bookId: Player.bookId }
    ShortcutsDialog { id: shortcuts; letters: Api.preferences.letterShortcuts !== false }
    Modal {
        id: recommendations; objectName: "nowRecommendations"; title: S.s_nghe_cuon_khac_cc5cf8a7
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
            Button { text: S.s_ve_thu_vien_992fad7b; kind: "ghost"; onClicked: { recommendations.close(); root.close(); if (Nav.stack) Nav.stack.show(0) } }
        }
    }
    Popover {
        id: more; objectName: "nowMoreMenu"; anchorItem: moreButton; panelWidth: 320; maxHeight: 600
        Column {
            width: parent.width; spacing: Theme.s8
            ClockLabel {
                width: parent.width; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption
                text: {
                    const p = LibraryLogic.progress(root.currentBook)
                    if (p.finished) return S.s_da_nghe_het_ca_cuon_11fdce7b
                    const total = p.totalSeconds || root.currentBook.duration || 0, heard = Math.min(total, p.heardSeconds || 0)
                    if (!total) return S.s_chua_nghe_u00a0_u00a0_0_chuong_af6b9134(root.currentBook.chaptersTotal || 0)
                    if (!heard) return S.s_chua_nghe_u00a0_u00a0_0_2ada9121(Player.lengthText(total))
                    const scope = root.currentBook.complete ? S.s_ca_cuon_b841210a : S.s_phan_da_co_69a9b13c
                    const remaining = Player.rate === 1 ? S.s_con_c697bae9 + Player.lengthText(total - heard) : S.s_con_khoang_f88c6a5c + Player.lengthText((total - heard) / Player.rate) + S.s_o_toc_do_46172629 + UiNumber.decimal(Player.rate) + "×"
                    return S.s_da_nghe_0_1_u00a0_u00a0_2_12a8bc8c(Math.round(heard / total * 100) + "%", scope, remaining)
                }
            }
            MenuRow { objectName: "nowAudioFxButton"; width: parent.width; text: S.s_copy_c1303271503d; value: S.s_copy_cc27613e0895; icon: "sliders-horizontal"; onClicked: { more.close(); audioFx.show() } }
            MenuRow { objectName: "nowVoice"; width: parent.width; text: S.s_giong_doc_11f2548d; icon: "audio-lines"; Reveal { shown: Player.speaking && Api.voiceList.length > 0 } onClicked: { more.close(); voice.show() } }
            MenuRow { objectName: "nowOutput"; width: parent.width; text: S.s_phat_tren_681e16e1; icon: "cast"; onClicked: { more.close(); output.show() } }
            MenuRow { objectName: "nowHistory"; width: parent.width; text: S.s_ve_cho_vua_nghe_8da3c710; icon: "undo-2"; Reveal { shown: Player.canGoBack } onClicked: { more.close(); Player.goBack() } }
            MenuRow { objectName: "nowKeys"; width: parent.width; text: S.s_phim_tat_7baaed2f; icon: "keyboard"; onClicked: { more.close(); shortcuts.show() } }
            MenuRow { objectName: "nowAddVoice"; width: parent.width; text: S.s_them_giong_15d3a618; icon: "plus"; onClicked: { more.close(); root.settingsRequested("voice") } }
            MenuRow { objectName: "nowSuggestionsButton"; width: parent.width; text: S.s_goi_y_doc_346ac8be; icon: "lightbulb"; Reveal { shown: suggestions.groups.length > 0 } onClicked: { more.close(); suggestions.show() } }
            // Như Android / web: trang của cuốn đang nghe, ngay trước Cửa sổ mini.
            MenuRow { objectName: "nowBookPage"; width: parent.width; text: S.s_trang_sach_2b6c8e51; icon: "book-open"; Reveal { shown: Player.bookId !== "" } onClicked: { more.close(); root.bookRequested() } }
            MenuRow { width: parent.width; text: S.s_cua_so_mini_65edeb9b; icon: "picture-in-picture-2"; onClicked: { more.close(); if (Nav.windowMode) Nav.windowMode.enter() } }
        }
    }
    OutputPopover { id: output; anchorItem: moreButton }
    Popover { id: audioFx; closeGuard: action => audioSettings.requestClose(action); objectName: "nowAudioFx"; anchorItem: moreButton; panelWidth: 360; maxHeight: 760; AudioFxPanel { id:audioSettings; openMusic: () => { audioFx.close(); music.show() } } }
    PlayerVoicePopover { id: voice; anchorItem: moreButton; onSettingsRequested: root.settingsRequested("voice") }
}
