import QtQuick
import ABook

// Cửa sổ chính: thanh bên trái + ngăn xếp màn bên phải. Khung cửa sổ là khung hệ điều hành (kéo, thu phóng, Snap Layouts như mọi app Windows).
// Back: Esc, Alt+Left, nút Back của chuột - đóng lớp nổi trên cùng trước, rồi lùi một màn; không bao giờ thoát app.
Window {
    id: win
    visible: true
    title: "ABook"
    width: 1280
    height: 800
    minimumWidth: 960
    minimumHeight: 600
    color: Theme.bg

    Binding { target: Theme; property: "reduceMotion"; value: Platform.reduceMotion }

    Component { id: libraryScreen; LibraryScreen { onOpenBook: (book) => stack.push(bookPage, { book: book }) } }
    Component { id: studioScreen; StudioScreen {} }
    Component { id: settingsScreen; SettingsScreen {} }
    Component { id: bookPage; BookPage {} }

    Item {
        id: shell
        anchors.fill: parent

        Sidebar {
            id: sidebar
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            currentSection: stack.current
            onSectionRequested: (index) => stack.show(index)
        }
        ScreenStack {
            id: stack
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            roots: [libraryScreen, studioScreen, settingsScreen]
        }

        // ---- phím tắt ----
        Shortcut { sequences: ["Escape"]; onActivated: Nav.back() }
        Shortcut { sequences: [StandardKey.Back]; onActivated: Nav.back() }          // Alt+Left
        Shortcut { sequences: ["Ctrl+1"]; onActivated: stack.show(0) }
        Shortcut { sequences: ["Ctrl+2"]; onActivated: stack.show(1) }
        Shortcut { sequences: ["Ctrl+3"]; onActivated: stack.show(2) }
        // Nút Back (nút bên) của chuột
        TapHandler {
            acceptedButtons: Qt.BackButton
            gesturePolicy: TapHandler.ReleaseWithinBounds
            onTapped: Nav.back()
        }
    }

    // ---- lớp phủ: bảng nổi và chú thích, vẽ trên cùng, không bị khung cuộn cắt ----
    ConnectionPopover {
        id: popover
        anchorItem: sidebar.chip
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
        radius: 6
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
        Theme.mode = Platform.setting("themeMode", "auto")
        Nav.stack = stack
        if (!Bench.enabled) restoreGeometry()
        stack.show(0)
        Bench.attach(win)
    }

    BenchScenario { stack: stack }
}
