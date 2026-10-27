import QtQuick
import ABook
import "ReaderLogic.js" as Logic

// Màn ĐỌC "Đọc chương này" (listen/ReaderScreen.tsx): văn bản chương như một cuốn ebook, đi cùng chỗ đang nghe. Mở từ menu "…" của dòng chương
// (hay bấm dòng chương chưa có audio) ở trang sách; Back (nút ←, Esc) trượt ngược về trang sách.
//   - thanh đầu: nút ← "Về trang sách" + tên chương (xuống dòng, không cắt), nền đặc, đứng ngoài khung cuộn
//   - chữ: cùng ReadAlongView với "Đọc theo" (mặt đọc giấy / ngà / đêm, cỡ chữ, tô câu đang nghe, bấm chữ để nghe từ đó, tự cuộn theo giọng)
//   - lời nhắc đầu trang (readerHint), thẻ "Chương tiếp theo" cuối trang
//   - thanh nổi dưới đáy: Chương trước · Nghe từ đây · Cỡ chữ và giãn dòng · Chương sau; người tự cuộn thì mờ đi, bấm vào trang / Tab là hiện lại
//   - chỗ đọc = câu đầu tiên còn thấy, lưu bản dự phòng trên máy ngay và gửi hồ sơ 2 giây sau lần cuộn cuối (POST .../reading); mở lại tới câu đang
//     nghe, hay chỗ đọc dở
//   - giọng tự sang chương kế khi màn đang mở đúng chương đang nghe: màn đọc đi theo
// Chưa có ở bản Qt (PROGRESS.md D4 Open): "Tìm trong sách", chọn câu (Chép / Sửa câu này), giọng đọc to cho chương chỉ có chữ.
Item {
    id: root
    objectName: "readerScreen"
    property var book: ({})
    property int chapterId: 0
    readonly property var chapters: book.chapters || []
    readonly property int index: {
        for (let i = 0; i < chapters.length; ++i) if (chapters[i].id === chapterId) return i
        return -1
    }
    readonly property var chapter: index >= 0 ? chapters[index] : null
    readonly property string name: chapter ? (chapter.subtitle || chapter.title || "") : ""
    readonly property bool textOnly: Boolean(chapter && chapter.state === "text")
    readonly property bool canListen: text.timed
    readonly property bool tapped: Boolean(Api.reader.tapped)
    readonly property var hint: text.status === "ready" ? Logic.readerHint({textOnly: textOnly, canSpeak: false, timed: text.timed, tapped: tapped,
        coarse: false, wish: false, readings: false}) : null
    readonly property string record: Logic.readingRecord(book)
    property bool controls: true
    property var pending: null
    property bool saving: false

    ChapterText {
        id: text
        bookId: root.book.id || ""
        chapterId: root.chapterId
        textOnly: root.textOnly
        title: root.chapter ? root.chapter.title || "" : ""
        skip: root.chapter && root.chapter.skip ? root.chapter.skip : []
        active: root.visible
        onStatusChanged: if (status === "ready") root.restore()
        onListened: root.markTapped()
    }

    // ---- chỗ đọc ----
    function localPlace() { return Logic.parseLocal(Api.store(Logic.readingKey(book.id, record))) }
    function saveLocal(place) { Api.store(Logic.readingKey(book.id, record), JSON.stringify(place)) }
    // Mở chương: tới câu đang nghe, hay chỗ đọc dở của đúng chương này, không thì đầu chương
    function restore() {
        if (text.listeningHere && text.currentSegment >= 0) return       // ReadAlongView tự đưa câu đang nghe vào khung
        const saved = Logic.latestReading(book, localPlace())
        const target = saved && saved.chapterId === chapterId ? text.restoreIndex(saved) : 0
        Qt.callLater(function() { reading.showSegment(target) })
    }
    function placeNow() {
        if (text.status !== "ready" || !book.id) return
        const found = reading.firstVisibleSegment()
        const place = {chapterId: chapterId, index: found, at: Date.now() / 1000, rev: Logic.nextReadingRevision(book, pending || localPlace()),
            anchor: text.anchorOf(found), quote: text.quoteOf(found), pending: true}
        pending = place
        saveLocal(place)
        saveTimer.restart()
    }
    function flush() {
        const place = pending
        if (!place || saving || !book.id) return
        if (!Logic.validRevision(place.rev)) { place.rev = Logic.nextReadingRevision(book, place); saveLocal(place) }
        saving = true
        const bookId = book.id, record = root.record
        const body = Object.assign({}, place, {chapterId: place.chapterId, index: place.index})
        delete body.pending
        if (record !== "default") body.record = record
        Api.quiet("POST", "/api/listen/books/" + bookId + "/reading", body, function(data, error) {
            saving = false
            if (error) {
                const backup = Boolean(localPlace())
                Api.toast("Chưa lưu được chỗ đọc vào hồ sơ\n" + (backup ? "Bạn vẫn có bản lưu trên máy này." : "App sẽ thử lưu lại chỗ đọc của bạn.") + " " + error,
                    {id: "reading-save"})
                return
            }
            if (pending === place) pending = null
            const local = localPlace()
            if (Logic.sameVersion(local, place)) saveLocal(Object.assign({}, place, {pending: false}))
        })
    }
    Timer { id: scrollCoalesce; interval: 120; onTriggered: root.placeNow() }
    Timer { id: saveTimer; interval: 2000; onTriggered: root.flush() }
    Timer { interval: 5000; repeat: true; running: root.pending !== null; onTriggered: root.flush() }
    Component.onCompleted: {
        const saved = localPlace()
        if (saved && saved.pending) pending = saved
        lastPlaying = Player.loaded && Player.bookId === book.id ? Player.chapterId : null
        placeToasts()
    }
    Component.onDestruction: { flush(); if (Nav.toastTop === toastTop) Nav.toastTop = 0 }

    function markTapped() { if (!tapped) Api.setReader({tapped: true}) }
    function go(step) {
        const next = chapters[index + step]
        if (next) chapterId = next.id
    }
    // "Nghe từ đây": câu đang nghe dở còn trong màn thì nghe tiếp đúng chỗ ấy, không thì nghe từ câu đầu tiên còn thấy
    function listenHere() {
        if (text.listeningHere && text.currentSegment >= 0 && reading.playingInView()) {
            reading.goBackToReading()
            if (!Player.playing) Player.resume()
            markTapped()
            return
        }
        text.listenSegment(reading.firstVisibleSegment())
    }

    // Giọng sang chương kế khi màn đang mở đúng chương đang nghe: đi theo (chapterToFollow)
    property var lastPlaying: null
    Connections {
        target: Player
        function onChapterChanged() { root.followVoice() }
        function onBookChanged() { root.followVoice() }
    }
    function followVoice() {
        const now = Player.loaded && Player.bookId === book.id ? Player.chapterId : null
        const next = Logic.chapterToFollow(lastPlaying, now, chapterId)
        lastPlaying = now
        if (next !== null) chapterId = next
    }

    // Đổi chương tại chỗ (Chương trước / sau, đi theo giọng): chữ cũ khuất, chữ mới trôi lên 8 px vào chỗ
    property real swapT: 1
    onChapterIdChanged: {
        pending = null
        swapIn.stop()
        swapT = 0
        swapIn.start()
    }
    NumberAnimation {
        id: swapIn
        target: root
        property: "swapT"
        to: 1
        duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionMedium
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDecelerate
    }

    // Thông báo nằm dưới thanh đầu, không che nút ở góc trên (--toast-top của web); màn khuất / đóng thì trả chỗ thường
    property real toastTop: 0
    function placeToasts() {
        toastTop = visible ? header.mapToItem(null, 0, header.height).y + 8 : 0
        Nav.toastTop = toastTop
    }
    onVisibleChanged: placeToasts()

    Keys.onTabPressed: (event) => { root.controls = true; event.accepted = false }

    // ---- thanh đầu ----
    Rectangle {
        id: header
        objectName: "readerHeader"
        z: 2
        width: parent.width
        height: Math.max(56, titleText.implicitHeight + Theme.s16)
        onHeightChanged: root.placeToasts()
        color: Theme.bg
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
        IconButton {
            id: back
            objectName: "readerBack"
            x: Theme.margin - 10
            anchors.verticalCenter: parent.verticalCenter
            icon: "arrow-left"
            tip: "Về trang sách (Esc)"
            Accessible.name: "Về trang sách"
            onClicked: Nav.back()
        }
        Text {
            id: titleText
            objectName: "readerTitle"
            x: back.x + back.width + Theme.s4
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - x - Theme.margin
            text: root.name
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBody
            font.weight: 600
            opacity: root.swapT
            transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.swapT) }
        }
    }

    // ---- chữ ----
    Item {
        id: body
        y: header.height
        width: parent.width
        height: parent.height - y
        clip: true

        ReadAlongView {
            id: reading
            objectName: "readerText"
            anchors.fill: parent
            source: text
            untimed: true
            headingScale: 1.5
            textMax: fontPx * 31
            topPad: 32
            bottomPad: 160
            chipBottom: root.controls ? Theme.s24 + bar.height + Theme.s8 : Theme.s24
            opacity: (text.status === "ready" ? 1 : 0) * root.swapT
            transform: Translate { y: Theme.reduceMotion ? 0 : 8 * (1 - root.swapT) }
            Behavior on opacity { enabled: root.swapT === 1; NumberAnimation { duration: Theme.motionMedium } }
            // Bấm trên thanh nổi / hộp cỡ chữ không phải bấm vào chữ bên dưới
            overlays: [bar, typePanel]
            onUserScrolled: root.controls = false
            onPageTapped: root.controls = true
            onScrolled: scrollCoalesce.restart()
            header: Item {
                width: reading.width
                height: hintBox.height
                Collapse {
                    id: hintBox
                    objectName: "readerHint"
                    x: Math.round((parent.width - reading.textW) / 2)
                    width: reading.textW
                    open: root.hint !== null
                    Text {
                        width: parent.width
                        text: root.hint || ""
                        color: reading.surface.fg2
                        wrapMode: Text.Wrap
                        lineHeight: 1.625
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Item { width: 1; height: Theme.s24 }
                }
            }
            footer: Item {
                width: reading.width
                height: nextCard.visible ? nextCard.height + Theme.s48 : 0
                Interactive {
                    id: nextCard
                    objectName: "readerNext"
                    visible: root.index >= 0 && root.index < root.chapters.length - 1
                    readonly property var next: visible ? root.chapters[root.index + 1] : null
                    x: Math.round((parent.width - reading.textW) / 2)
                    y: Theme.s48
                    width: reading.textW
                    height: nextColumn.height + 2 * 20
                    pressScaling: false
                    Accessible.name: "Chương tiếp theo"
                    onClicked: root.go(1)
                    Rectangle { width: parent.width; height: 1; color: Theme.line }
                    Column {
                        id: nextColumn
                        y: 20
                        width: parent.width - 17.5 - Theme.s16
                        Text { width: parent.width; text: "Chương tiếp theo"; wrapMode: Text.Wrap; color: reading.surface.fg2; font.pixelSize: Theme.sizeCaption }
                        Text {
                            width: parent.width
                            text: nextCard.next ? (nextCard.next.subtitle || nextCard.next.title || "") : ""
                            wrapMode: Text.Wrap
                            color: nextCard.hovered ? reading.surface.accentText : reading.surface.fg
                            font.pixelSize: Theme.sizeBody
                            font.weight: 600
                            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                        }
                    }
                    Icon {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        name: "arrow-right"
                        size: 20
                        color: reading.surface.fg2
                    }
                }
            }
        }

        // Chưa có chữ: khung giữ chỗ (Skeleton của web) mờ chéo sang chữ
        Column {
            objectName: "readerSkeleton"
            x: Math.round((parent.width - reading.textW) / 2)
            y: 40
            width: reading.textW
            spacing: Theme.s16
            opacity: text.status === "loading" || text.status === "idle" ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
            Rectangle { width: parent.width * 2 / 3; height: 32; radius: Theme.radiusControl; color: Theme.sunken }
            Rectangle { width: parent.width; height: 16; radius: Theme.radiusControl; color: Theme.sunken }
            Rectangle { width: parent.width * 11 / 12; height: 16; radius: Theme.radiusControl; color: Theme.sunken }
        }

        EmptyState {
            objectName: "readerProblem"
            x: Theme.margin
            y: 80 - 56
            width: parent.width - 2 * Theme.margin
            icon: "book-open-text"
            title: "Không mở được chương này"
            text: Logic.chapterOpenProblem(text.errorStatus, text.errorMessage)
            opacity: text.status === "failed" ? 1 : 0
            visible: opacity > 0
            transform: Translate { y: text.status === "failed" || Theme.reduceMotion ? 0 : 8 }
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
            Button { text: "Về trang sách"; onClicked: Nav.back() }
        }

        // Chữ mờ dần dưới thanh nổi thay vì lộ nửa dòng giữa thanh và đáy (phần đặc 66 %); ẩn thanh thì cũng tắt dần
        Rectangle {
            objectName: "readerFade"
            anchors.bottom: parent.bottom
            width: parent.width
            height: 144
            visible: text.status === "ready"
            opacity: root.controls ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionSlow } }
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(reading.surfaceBg.r, reading.surfaceBg.g, reading.surfaceBg.b, 0) }
                GradientStop { position: 0.34; color: reading.surfaceBg }
                GradientStop { position: 1; color: reading.surfaceBg }
            }
        }

        // ---- thanh nổi ----
        Item {
            id: bar
            objectName: "readerControls"
            readonly property bool shown: root.controls && text.status === "ready"
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - height - Theme.s24 + (shown ? 0 : 16)
            width: barRow.width + 2 * Theme.s8
            height: barRow.height + 2 * 6
            opacity: shown ? 1 : 0
            visible: opacity > 0
            enabled: shown
            Behavior on opacity { NumberAnimation { duration: bar.shown ? Theme.motionMedium : Theme.motionFastOut } }
            Behavior on y {
                NumberAnimation {
                    duration: Theme.reduceMotion ? 0 : (bar.shown ? Theme.motionMedium : Theme.motionFastOut)
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: bar.shown ? Theme.easeDecelerate : Theme.easeAccelerate
                }
            }
            Accessible.role: Accessible.ToolBar
            Accessible.name: "Điều khiển đọc"
            Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
            Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
            Rectangle { anchors.fill: parent; radius: Theme.radiusCover; color: Theme.panel; border.width: Theme.dark ? 1 : 0; border.color: Theme.line }
            // Cú bấm trên thanh dừng ở thanh, không rơi xuống chữ bên dưới (bấm chữ là nghe từ đó)
            MouseArea { anchors.fill: parent; onClicked: root.controls = true }
            Row {
                id: barRow
                x: Theme.s8
                y: 6
                spacing: Theme.s4
                IconButton {
                    objectName: "readerPrevious"
                    implicitWidth: 36; implicitHeight: 36
                    icon: "skip-back"
                    tip: "Chương trước"
                    Accessible.name: "Chương trước"
                    enabled: root.index > 0
                    opacity: enabled ? 1 : 0.4
                    onClicked: root.go(-1)
                }
                Item {
                    // "Nghe từ đây" tới / đi (chương có audio hay chưa) mở / khép theo bề ngang, không bật vào đẩy các nút khác
                    readonly property bool shown: root.canListen
                    width: (listenButton.width + 2 * Theme.s4) * listenT
                    height: 36
                    property real listenT: shown ? 1 : 0
                    clip: listenT < 1
                    Behavior on listenT { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                    visible: listenT > 0
                    Button {
                        id: listenButton
                        objectName: "readerListen"
                        x: Theme.s4
                        anchors.verticalCenter: parent.verticalCenter
                        size: "sm"
                        icon: "headphones"
                        text: "Nghe từ đây"
                        opacity: parent.listenT
                        onClicked: root.listenHere()
                    }
                }
                IconButton {
                    id: typeButton
                    objectName: "readerType"
                    implicitWidth: 36; implicitHeight: 36
                    icon: "type"
                    ink: Theme.text2
                    hoverInk: Theme.text
                    tip: "Cỡ chữ và giãn dòng"
                    Accessible.name: "Cỡ chữ và giãn dòng"
                    onClicked: typePanel.toggle()
                }
                IconButton {
                    objectName: "readerNextChapter"
                    implicitWidth: 36; implicitHeight: 36
                    icon: "skip-forward"
                    tip: "Chương sau"
                    Accessible.name: "Chương sau"
                    enabled: root.index >= 0 && root.index < root.chapters.length - 1
                    opacity: enabled ? 1 : 0.4
                    onClicked: root.go(1)
                }
            }
        }
    }

    Popover {
        id: typePanel
        objectName: "readerTypePanel"
        anchorItem: typeButton
        panelWidth: 288
        pad: Theme.s12
        Column {
            width: parent.width
            ReaderChoices {
                objectName: "readerSizes"
                width: parent.width
                label: "Cỡ chữ"
                options: Logic.SIZES.map(size => ({value: size, label: String(size), name: "Cỡ chữ " + size}))
                value: Number(Api.reader.size || Theme.sizeReading)
                onPicked: value => Api.setReader({size: value})
            }
            Item { width: 1; height: Theme.s12 }
            ReaderChoices {
                objectName: "readerLeadings"
                width: parent.width
                label: "Giãn dòng"
                boldSelected: true
                options: Logic.LEADINGS.map(leading => ({value: leading, label: Logic.leadingLabel(leading), name: Logic.leadingLabel(leading)}))
                value: Number(Api.reader.leading || Theme.lineHeightReading)
                onPicked: value => Api.setReader({leading: value})
            }
        }
    }
}
