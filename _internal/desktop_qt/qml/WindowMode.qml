import QtQuick
import ABook

// Chỉ đổi hình học của cửa sổ đang sống; bộ phát không bị dựng lại hay dừng.
Item {
    id: root
    property var window: null
    property bool loaded: Player.loaded
    property bool mini: false
    property bool pinned: true
    property bool closeToTray: Platform.setting("closeToTray", "true") !== "false"
    property bool autoMini: Platform.setting("autoMini", "true") !== "false"
    property bool quitting: false
    property bool notified: Platform.setting("trayNotified", "false") === "true"
    property real miniHeight: 112
    property rect fullRect: Qt.rect(0, 0, 1280, 800)
    property bool fullMaximized: false
    property point miniPosition: Qt.point(NaN, NaN)
    readonly property bool transitioning: geometry.running
    signal expanded()
    signal notifyTray()
    signal exitRequested()

    Component.onCompleted: {
        const saved = Platform.setting("window", "").split(",").map(Number)
        fullRect = saved.length === 5 && saved.every(Number.isFinite) && saved[2] >= 960 && saved[3] >= 600
            ? Qt.rect(saved[0], saved[1], saved[2], saved[3]) : Qt.rect(window.x, window.y, window.width, window.height)
    }
    // Ghi nhớ cỡ thường sau sự kiện hình học, tránh lấy cỡ phóng to làm cỡ khôi phục.
    Timer {
        id: rememberFull
        interval: 0
        onTriggered: if (!root.mini && !root.transitioning && root.window.visibility === Window.Windowed)
            root.fullRect = Qt.rect(root.window.x, root.window.y, root.window.width, root.window.height)
    }
    Connections {
        target: root.window
        function onXChanged() { rememberFull.restart() }
        function onYChanged() { rememberFull.restart() }
        function onWidthChanged() { rememberFull.restart() }
        function onHeightChanged() { rememberFull.restart() }
    }

    onPinnedChanged: if (mini) applyPin()
    function applyPin() {
        const shown = window.visible
        window.flags = pinned && mini ? window.flags | Qt.WindowStaysOnTopHint : window.flags & ~Qt.WindowStaysOnTopHint
        if (shown) window.show()
    }
    function saveMini() {
        miniPosition = Qt.point(window.x, window.y)
        Platform.setSetting("miniPosition", [window.x, window.y].join(","))
    }
    function saveFull() {
        if (mini) return
        if (window.visibility !== Window.Maximized && window.visibility !== Window.Minimized && window.visible)
            Platform.setSetting("window", [window.x, window.y, window.width, window.height, 0].join(","))
        else if (window.visibility === Window.Maximized)
            Platform.setSetting("window", [fullRect.x, fullRect.y, fullRect.width, fullRect.height, 1].join(","))
    }
    function reveal() {
        if (window.visibility === Window.Minimized || !window.visible) {
            if (!mini && fullMaximized) window.showMaximized()
            else window.showNormal()
        }
        window.raise(); window.requestActivate()
    }
    function moveTo(rect) {
        geometry.stop()
        ax.to = rect.x; ay.to = rect.y; aw.to = rect.width; ah.to = rect.height
        geometry.start()
    }
    function enter() {
        if (!loaded) return
        if (mini) { reveal(); return }
        if (transitioning) geometry.complete()
        saveFull()
        fullMaximized = window.visibility === Window.Maximized || ((!window.visible || window.visibility === Window.Minimized) && fullMaximized)
        const saved = Platform.setting("window", "").split(",").map(Number)
        fullRect = fullMaximized && saved.length === 5 && saved.every(Number.isFinite)
            ? Qt.rect(saved[0], saved[1], saved[2], saved[3]) : Qt.rect(window.x, window.y, window.width, window.height)
        // Một hộp có thể giữ Back để hỏi lại; đóng từng lớp một lần, không quay vô hạn.
        for (const layer of Nav.layers.slice().reverse()) {
            if (layer.dismiss) layer.dismiss()
            else if (layer.close) layer.close()
        }
        Nav.hideTip()
        window.minimumWidth = 0; window.minimumHeight = 0
        window.showNormal()
        mini = true
        applyPin()
        const stored = Platform.setting("miniPosition", "").split(",").map(Number)
        const validStored = stored.length === 2 && stored.every(Number.isFinite)
        const position = Number.isFinite(miniPosition.x) && Number.isFinite(miniPosition.y) ? miniPosition
            : validStored ? Qt.point(stored[0], stored[1]) : Qt.point(NaN, NaN)
        const area = Platform.workArea(window, position)
        const px = Number.isFinite(position.x) ? position.x : area.x + area.width - 360 - 24
        const py = Number.isFinite(position.y) ? position.y : area.y + area.height - miniHeight - 24
        moveTo(Qt.rect(Math.max(area.x, Math.min(px, area.x + area.width - 360)), Math.max(area.y, Math.min(py, area.y + area.height - miniHeight)), 360, miniHeight))
    }
    function expand() {
        if (mini) {
            if (transitioning) geometry.complete()
            saveMini()
            geometry.stop()
            window.maximumWidth = 16777215; window.maximumHeight = 16777215
            mini = false
            applyPin()
            moveTo(fullRect)
        }
        reveal()
        if (loaded) expanded()
    }
    function minimize() {
        if (loaded && autoMini) enter()
        else { fullMaximized = window.visibility === Window.Maximized; window.showMinimized() }
    }
    function hideToTray() {
        if (transitioning) geometry.complete()
        if (mini) saveMini(); else { fullMaximized = window.visibility === Window.Maximized; saveFull() }
        Nav.hideTip()
        window.hide()
        if (!notified) {
            notified = true
            Platform.setSetting("trayNotified", "true")
            notifyTray()
        }
    }
    function closeRequested(close, trayAvailable) {
        if (!quitting && closeToTray && trayAvailable) {
            close.accepted = false
            hideToTray()
        } else quit()
    }
    function quit() {
        if (transitioning) geometry.complete()
        if (mini) saveMini(); else saveFull()
        quitting = true
        exitRequested()
    }
    onCloseToTrayChanged: Platform.setSetting("closeToTray", String(closeToTray))
    onAutoMiniChanged: Platform.setSetting("autoMini", String(autoMini))
    onLoadedChanged: if (!loaded && mini) expand()
    onMiniHeightChanged: if (mini && !transitioning) {
        window.minimumHeight = miniHeight
        window.height = miniHeight
    }
    ParallelAnimation {
        id: geometry
        NumberAnimation { id: ax; target: root.window; property: "x"; duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { id: ay; target: root.window; property: "y"; duration: ax.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { id: aw; target: root.window; property: "width"; duration: ax.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        NumberAnimation { id: ah; target: root.window; property: "height"; duration: ax.duration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        onFinished: {
            if (root.mini) { root.window.minimumWidth = 360; root.window.maximumWidth = 360; root.window.minimumHeight = root.miniHeight; root.window.height = root.miniHeight }
            else { root.window.minimumWidth = 960; root.window.minimumHeight = 600; if (root.fullMaximized) root.window.showMaximized() }
        }
    }
}
