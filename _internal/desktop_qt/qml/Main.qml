import QtQuick
import ABook

// Cửa sổ chính: dải tiêu đề tự vẽ ở trên, thanh bên trái + ngăn xếp màn bên phải. Không còn khung hệ thống; WindowChrome (QWindowKit) giữ hành vi gốc
// của Windows (kéo, thu phóng, Aero Snap, Snap Layouts, bóng, bo góc).
// Back: Esc, Alt+Left, nút Back của chuột - đóng lớp nổi trên cùng trước, rồi lùi một màn; không bao giờ thoát app.
Window {
    id: win
    visible: false          // hiện sau khi WindowChrome gắn xong (Component.onCompleted)
    title: "ABook"
    width: 1280
    height: 800
    minimumWidth: 960
    minimumHeight: 600
    color: Theme.bg

    WindowChrome { id: chrome }

    Binding { target: Theme; property: "reduceMotion"; value: Platform.reduceMotion }
    readonly property var nowPlaying: nowLoader.item          // Đang nghe (null cho tới lần mở đầu tiên)
    function openNowPlaying() {
        nowLoader.alive = true                               // dựng ngay (đồng bộ) rồi mở
        if (nowPlaying) nowPlaying.show()
    }
    function openBookId(id) {
        Api.call("GET", "/api/listen/books/" + id, null, function(data, error) {
            if (!error) { stack.show(0); stack.push(bookPage, {book: Object.assign({}, data, {bookId: data.id, coverKey: data.cover ? data.id + "/" + (data.cover.version || 0) : ""})}) }
        })
    }

    Component { id: libraryScreen; LibraryScreen { onOpenBook: (book) => stack.push(bookPage, { book: book }); onAddRequested: paths => addBook.begin(paths) } }
    Component { id: studioScreen; StudioScreen {} }
    Component { id: settingsScreen; SettingsScreen {} }
    Component { id: bookPage; BookPage { onEditRequested: data => editBook.begin(data) } }

    Item {
        id: shell
        anchors.fill: parent
        focus: true

        Sidebar {
            id: sidebar
            z: 20          // mở tạm đè lên khung nội dung (kể cả Đang nghe)
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            currentSection: stack.current
            onSectionRequested: (index) => stack.show(index)
        }
        // Khung nội dung: màn hiện tại, thanh phát ở đáy, Đang nghe phủ lên trên cả hai
        Item {
            id: content
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: titleBar.bottom
            anchors.bottom: parent.bottom

            ScreenStack {
                id: stack
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: playerBar.top
                roots: [libraryScreen, studioScreen, settingsScreen]
            }
            PlayerBar {
                id: playerBar
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                thumbShown: !nowPlaying || nowPlaying.p <= 0
                contentOpacity: nowPlaying ? 1 - Math.min(1, nowPlaying.g * 3) : 1
                contentShift: nowPlaying ? -nowPlaying.g * 12 : 0
                onOpenRequested: win.openNowPlaying()
            }
            // Đang nghe chỉ được dựng ở lần mở đầu tiên (thanh phát có sách nhưng chưa ai mở: không trả RAM / khung đầu của cả màn này).
            // Đã dựng thì giữ ít lâu sau khi đóng (mở lại liền không giật), rồi bỏ; cửa sổ thu nhỏ hay sách đóng thì bỏ ngay (RAM khi nghe nền).
            Loader {
                id: nowLoader
                anchors.fill: parent
                property bool alive: false
                active: alive
                sourceComponent: NowPlaying { bar: playerBar }
                Timer {
                    id: dropTimer
                    interval: 8000
                    onTriggered: if (nowLoader.item && nowLoader.item.p <= 0) nowLoader.alive = false
                }
                Connections {
                    target: nowLoader.item
                    function onPChanged() {
                        if (nowLoader.item.p > 0) dropTimer.stop()
                        else if (!Player.loaded) nowLoader.alive = false
                        else dropTimer.restart()
                    }
                }
                Connections {
                    target: win
                    function onVisibilityChanged() { if (win.visibility === Window.Minimized && nowLoader.item && nowLoader.item.p <= 0) nowLoader.alive = false }
                }
            }
            PlayerNotice {
                id: notice
                z: 60
                anchors.horizontalCenter: parent.horizontalCenter
                y: nowPlaying && nowPlaying.open ? 64 : playerBar.y - height - Theme.s16
            }
        }

        TitleBar {
            id: titleBar
            z: 50          // trên cả thanh bên mở tạm; trong suốt, chỉ ba nút cửa sổ có hình
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            window: win
            chrome: chrome
        }

        // ---- phím tắt ----
        Shortcut { sequences: ["Escape"]; onActivated: Nav.back() }
        Shortcut { sequences: [StandardKey.Back]; onActivated: Nav.back() }          // Alt+Left
        Shortcut { sequences: ["Ctrl+1"]; onActivated: stack.show(0) }
        Shortcut { sequences: ["Ctrl+2"]; onActivated: stack.show(1) }
        Shortcut { sequences: ["Ctrl+3"]; onActivated: stack.show(2) }
        Shortcut { sequences: ["Ctrl+Left"]; enabled: Player.loaded; onActivated: Player.previous() }
        Shortcut { sequences: ["Ctrl+Right"]; enabled: Player.loaded; onActivated: Player.next() }
        // Trình phát: Space, Left, Right khi không có ô nào đang nhận phím đó (danh sách Thư viện giữ mũi tên của nó)
        Keys.onPressed: (event) => {
            if (!Player.loaded || (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) return
            if (event.key === Qt.Key_Space && !event.isAutoRepeat) { Player.toggle(); event.accepted = true }
            else if (event.key === Qt.Key_Left) { Player.skip(-15); event.accepted = true }
            else if (event.key === Qt.Key_Right) { Player.skip(15); event.accepted = true }
        }
        // Nút Back (nút bên) của chuột
        TapHandler {
            acceptedButtons: Qt.BackButton
            gesturePolicy: TapHandler.ReleaseWithinBounds
            onTapped: Nav.back()
        }
    }
    // Bar bị ẩn / ô giữ tiêu điểm biến mất thì phím về lại shell
    onActiveFocusItemChanged: if (!activeFocusItem) shell.forceActiveFocus()

    // ---- lớp phủ: bảng nổi và chú thích, vẽ trên cùng, không bị khung cuộn cắt ----
    ConnectionPopover {
        id: popover
        anchorItem: sidebar.chip
    }
    AddBook { id: addBook; onOpenBook: id => win.openBookId(id) }
    EditBook { id: editBook }
    Connections {
        target: Backend
        function onStateChanged() { if (Backend.state === Backend.Ready) { Api.bind(DesktopApi, Theme); Api.load() } }
    }
    Connections { target: Api; function onPreferencesChanged() { Player.configure(Api.preferences) } }
    Rectangle {
        z: 90
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 32
        width: Math.min(parent.width - 80, apiNotice.implicitWidth + 32)
        height: apiNotice.height + 24
        visible: Api.notice !== ""
        color: Theme.panel; radius: Theme.radiusControl; border.color: Theme.line
        FormLabel { id: apiNotice; x: 16; y: 12; width: parent.width - 32; text: Api.notice }
        Timer { running: Api.notice !== ""; interval: 6000; onTriggered: Api.notice = "" }
    }
    Connections {
        target: sidebar.chip
        function onClicked() { popover.open ? popover.close() : popover.show() }
    }

    Rectangle {
        id: tip
        z: 100
        readonly property rect a: Nav.tipAnchor
        visible: opacity > 0
        opacity: Nav.tipShown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Nav.tipShown ? Theme.motionFast : Theme.motionFastOut } }
        height: tipLabel.implicitHeight + 12
        width: tipLabel.implicitWidth + 20
        radius: Theme.radiusControl
        color: Theme.dark ? Theme.text : "#2a2723"
        x: Math.max(8, Math.min(win.width - width - 8, a.x + a.width / 2 - width / 2))
        y: a.y + a.height + 8 + height > win.height ? a.y - height - 8 : a.y + a.height + 8
        Text {
            id: tipLabel
            anchors.centerIn: parent
            text: Nav.tipText
            color: Theme.dark ? Theme.bg : "#f5f3ef"
            font.pixelSize: Theme.sizeCaption
        }
    }

    // ---- cài đặt cửa sổ và chủ đề ----
    function restoreGeometry() {
        const saved = Platform.setting("window", "").split(",").map(Number)
        if (saved.length !== 5 || saved.some(isNaN)) return
        const cx = saved[0] + saved[2] / 2, cy = saved[1] + saved[3] / 2
        // Chỉ khôi phục vị trí khi màn hình cũ còn (rút màn phụ thì cửa sổ không nằm ngoài màn)
        const onScreen = Qt.application.screens.some(s => cx >= s.virtualX && cx < s.virtualX + s.width && cy >= s.virtualY && cy < s.virtualY + s.height)
        if (!onScreen) return
        x = saved[0]; y = saved[1]; width = Math.max(minimumWidth, saved[2]); height = Math.max(minimumHeight, saved[3])
        if (saved[4] === 1) visibility = Window.Maximized
    }
    onClosing: {
        if (Bench.enabled) return
        const maximized = visibility === Window.Maximized
        // Cỡ khi thu nhỏ lại (restore) không lấy được lúc đang phóng to: lưu cỡ hiện có, lần sau mở phóng to
        if (!maximized)
            Platform.setSetting("window", [x, y, width, height, 0].join(","))
        else
            Platform.setSetting("window", Platform.setting("window", "").split(",").slice(0, 4).concat(["1"]).join(","))
    }
    Connections {
        target: Qt.application
        function onStateChanged() { if (Qt.application.state === Qt.ApplicationActive) Platform.refresh() }
    }

    Component.onCompleted: {
        if (!chrome.attach(win, titleBar, titleBar.minimizeButton, titleBar.maximizeButton, titleBar.closeButton))
            console.warn("WindowChrome: không gắn được khung cửa sổ")
        chrome.keepClickable(sidebar.toggleButton)       // nút thu / mở thanh bên nằm trong dải kéo được
        Theme.mode = Platform.setting("themeMode", "auto")
        Nav.stack = stack
        if (!Bench.enabled) restoreGeometry()
        stack.show(0)
        Bench.attach(win)
        win.visible = true
    }

    BenchScenario { stack: stack; win: win; nowPlaying: win.nowPlaying }
}
