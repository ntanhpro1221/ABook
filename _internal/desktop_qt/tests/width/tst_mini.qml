import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 900; height: 900
    Component { id: miniFactory; MiniPlayer { width: 360; height: naturalHeight } }
    Component { id: modeFactory; WindowMode {} }
    Component { id: exitModeFactory; WindowMode { onExitRequested: {} } }
    Component { id: trayFactory; TrayMenuModel {} }
    Component {
        id: fakeModeFactory
        QtObject {
            property string action: ""
            function reveal() { action = "reveal" }
            function expand() { action = "open" }
            function enter() { action = "mini" }
            function quit() { action = "quit" }
        }
    }
    Component {
        id: fakePlayerFactory
        QtObject {
            property bool loaded: true
            property bool playing: false
            property bool canNext: true
            property bool canPrevious: true
            property int skipSeconds: Player.skipSeconds
            property string bookTitle: "Một tên sách rất dài ".repeat(20)
            property string chapterTitle: "Một tên chương rất dài ".repeat(20)
            property string action: ""
            function toggle() { playing = !playing; action = "play" }
            function skip(seconds) { action = String(seconds) }
            function previous() { action = "previous" }
            function next() { action = "next" }
        }
    }
    Component {
        id: windowFactory
        Window { x: 120; y: 90; width: 1100; height: 720; minimumWidth: 960; minimumHeight: 600 }
    }
    TestCase {
        name: "Mini"
        when: windowShown
        function init() { Platform.reset(); Theme.reduceMotion = false; Nav.layers = []; Nav.windowMode = null; Player.open("width", 1, 0, false); Player.seek(0) }
        function cleanup() { Player.pause(); Theme.reduceMotion = false; Theme.mode = "auto"; Nav.windowMode = null; Nav.layers = [] }
        function test_menu() {
            const player = createTemporaryObject(fakePlayerFactory, host)
            const tray = createTemporaryObject(trayFactory, host, {player: player, loaded: false})
            verify(tray)
            compare(tray.actions.map(a => a.separator ? "|" : a.label), ["Mở ABook", "|", "Phát", "Lùi 15 giây", "Tới 15 giây", "Chương trước", "Chương sau", "|", "Cửa sổ mini", "|", "Thoát ABook"])
            for (let i of [2, 3, 4, 5, 6, 8]) compare(tray.actions[i].enabled, false)
            tray.loaded = true; tray.playing = true
            compare(tray.actions[2].label, "Tạm dừng")
            for (let i of [2, 3, 4, 5, 6, 8]) compare(tray.actions[i].enabled, true)
        }
        function test_menuDispatchAndTooltip() {
            const mode = createTemporaryObject(fakeModeFactory, host)
            const player = createTemporaryObject(fakePlayerFactory, host)
            const tray = createTemporaryObject(trayFactory, host, {windowMode: mode, player: player})
            compare(tray.tooltip, player.bookTitle + " · " + player.chapterTitle)
            tray.activate(); compare(mode.action, "reveal")
            for (const action of ["open", "mini", "quit"]) {
                tray.dispatch(action); compare(mode.action, action)
            }
            tray.dispatch("play"); compare(player.playing, true); compare(tray.actions[2].label, "Tạm dừng")
            tray.dispatch("back"); compare(player.action, String(-Player.skipSeconds))
            tray.dispatch("forward"); compare(player.action, String(Player.skipSeconds))
            for (const action of ["previous", "next"]) { tray.dispatch(action); compare(player.action, action) }
            player.loaded = false; player.action = ""; mode.action = ""
            compare(tray.tooltip, "ABook")
            for (const action of ["play", "back", "forward", "previous", "next", "mini"]) tray.dispatch(action)
            compare(player.action, ""); compare(mode.action, "")
            tray.dispatch("open"); compare(mode.action, "open")
            tray.dispatch("quit"); compare(mode.action, "quit")
        }
        function test_miniTrayAndSmtcSharePlayback() {
            const mode = createTemporaryObject(fakeModeFactory, host)
            const mini = createTemporaryObject(miniFactory, host, {windowMode: mode})
            const tray = createTemporaryObject(trayFactory, host, {windowMode: mode})
            const play = findChild(mini, "miniPlay")
            verify(waitForRendering(mini))
            compare(WidthMedia.playing, false)
            mouseClick(play)
            compare(Player.playing, true); compare(WidthMedia.playing, true)
            compare(tray.playing, true); compare(tray.actions[2].label, "Tạm dừng")
            mouseClick(play)
            compare(Player.playing, false); compare(WidthMedia.playing, false)
            compare(tray.playing, false); compare(tray.actions[2].label, "Phát")
            WidthMedia.play()
            tryCompare(Player, "playing", true)
            compare(play.tip, "Tạm dừng"); compare(tray.playing, true)
            tray.dispatch("play")
            compare(WidthMedia.playing, false); compare(play.tip, "Phát")
            tray.dispatch("play")
            compare(WidthMedia.playing, true)
            WidthMedia.pause()
            tryCompare(Player, "playing", false)
            compare(tray.playing, false); compare(play.tip, "Phát")
            for (const chapter of [1, 2, 32]) {
                Player.jumpTo(chapter)
                compare(tray.actions[5].enabled, WidthMedia.canPrevious)
                compare(tray.actions[6].enabled, WidthMedia.canNext)
            }
            Player.close()
            compare(WidthMedia.loaded, false); compare(play.enabled, false)
            compare(tray.actions[2].enabled, false)
            compare(tray.actions[5].enabled, false); compare(tray.actions[6].enabled, false)
        }
        function test_windowFillingSheetIsSquare() {
            // Tấm lấp cả cửa sổ: bo góc hay viền riêng sẽ lộ nền cửa sổ ở bốn góc (hệ thống tự bo góc cửa sổ).
            const filling = createTemporaryObject(miniFactory, host, {framed: false})
            compare(filling.radius, 0)
            compare(filling.border.width, 0)
            const card = createTemporaryObject(miniFactory, host)
            compare(card.radius, Theme.radiusSheet)
        }

        function test_geometryAndPlayback() {
            const win = createTemporaryObject(windowFactory, host)
            win.show()
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: true})
            Player.resume()
            const playing = Player.playing
            mode.enter()
            tryCompare(win, "width", 360)
            compare(mode.mini, true)
            verify(win.flags & Qt.WindowStaysOnTopHint)
            compare(Player.playing, playing)
            for (const wide of [1024, 1366, 1630, 1920]) {
                win.width = wide
                compare(win.width, wide, "mini width must be resizable")
                compare(mode.mini, true)
                compare(Player.playing, playing)
            }
            mode.pinned = false
            verify(!(win.flags & Qt.WindowStaysOnTopHint))
            win.x = 450; win.y = 300
            mode.expand()
            tryCompare(win, "width", 1100)
            compare(win.height, 720); compare(win.x, 120); compare(win.y, 90)
            compare(win.minimumWidth, 960)
            compare(Player.playing, playing)
            mode.enter()
            tryCompare(win, "x", 450); compare(win.y, 300)
            mode.expand(); Player.pause(); win.hide()
        }
        function test_minimizeSetting() {
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: false})
            compare(mode.closeToTray, true); compare(mode.autoMini, true)
            mode.minimize(); compare(mode.mini, false)
            mode.loaded = true; mode.autoMini = false
            mode.minimize(); compare(mode.mini, false)
            mode.autoMini = true; mode.minimize(); compare(mode.mini, true)
            mode.expand(); win.hide()
        }
        function test_maximizedRestore() {
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: true})
            win.show(); tryCompare(win, "visible", true)
            win.width = 1180; win.height = 740
            tryVerify(function() { return mode.fullRect.width === 1180 && mode.fullRect.height === 740 })
            win.showMaximized(); tryCompare(win, "visibility", Window.Maximized)
            mode.enter(); tryCompare(win, "width", 360)
            compare(mode.fullRect.width, 1180); compare(mode.fullRect.height, 740)
            mode.expand(); tryCompare(win, "visibility", Window.Maximized)
            win.showNormal(); win.hide()
        }
        function test_invalidPositionAndDefaultCorner() {
            Platform.setSetting("miniPosition", "broken,position")
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: true})
            win.show(); mode.enter()
            tryCompare(win, "x", 1920 - 360 - 24)
            compare(win.y, 1080 - 112 - 24)
            mode.expand(); win.hide()
        }
        function test_hideAndNotifyOnce() {
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(modeFactory, host, {window: win})
            const spy = Qt.createQmlObject('import QtTest; SignalSpy { signalName: "notifyTray" }', host)
            spy.target = mode
            Player.resume()
            win.show()
            const close = {accepted: true}
            mode.closeRequested(close, true)
            compare(close.accepted, false)
            compare(win.visible, false); compare(spy.count, 1)
            compare(Player.playing, true)
            mode.reveal(); compare(win.visible, true)
            mode.hideToTray(); compare(spy.count, 1)
            compare(Player.playing, true)
            const nextMode = createTemporaryObject(modeFactory, host, {window: win})
            nextMode.hideToTray(); compare(spy.count, 1); compare(nextMode.notified, true)
            spy.destroy()
        }
        function test_closeExitsWhenDisabledOrUnavailable() {
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(exitModeFactory, host, {window: win})
            const spy = Qt.createQmlObject('import QtTest; SignalSpy { signalName: "exitRequested" }', host)
            spy.target = mode
            mode.closeToTray = false
            const close = {accepted: true}
            mode.closeRequested(close, true); compare(close.accepted, true); compare(spy.count, 1)
            mode.quitting = false
            mode.closeToTray = true
            mode.closeRequested(close, false); compare(spy.count, 2)
            spy.destroy()
        }
        function test_motionAndInterruptedTransition() {
            Theme.reduceMotion = false
            const win = createTemporaryObject(windowFactory, host)
            win.show()
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: true})
            mode.enter(); compare(mode.transitioning, true)
            tryVerify(function() { return win.width < 1100 && win.width > 360 })
            mode.expand(); mode.enter()
            tryCompare(mode, "transitioning", false)
            compare(win.width, 360)
            mode.expand(); tryCompare(mode, "transitioning", false)
            compare(win.width, 1100); compare(win.height, 720)
            win.hide()
        }
        function test_persistedPositionAndSettings() {
            Platform.setSetting("miniPosition", "400,250")
            Platform.setSetting("autoMini", "false")
            Platform.setSetting("closeToTray", "false")
            const win = createTemporaryObject(windowFactory, host)
            win.show()
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: true})
            compare(mode.autoMini, false); compare(mode.closeToTray, false)
            mode.enter(); tryCompare(win, "x", 400); compare(win.y, 250)
            mode.miniHeight = 280; compare(win.height, 280)
            compare(win.minimumHeight, 280)    // Kéo mép cửa sổ cũng không thể ép tên sách bị cắt.
            mode.expand(); win.hide()
        }
        function test_coverControlsAndSeek() {
            const mode = createTemporaryObject(fakeModeFactory, host)
            const mini = createTemporaryObject(miniFactory, host, {windowMode: mode})
            mouseClick(findChild(mini, "miniCover")); compare(mode.action, "open")
            mode.action = ""; mouseDoubleClickSequence(findChild(mini, "miniCover")); compare(mode.action, "open")
            mouseClick(findChild(mini, "miniExpand")); compare(mode.action, "open")
            mouseClick(findChild(mini, "miniPlay")); compare(Player.playing, true)
            mouseClick(findChild(mini, "miniPlay")); compare(Player.playing, false)
            const seek = findChild(mini, "miniSeek")
            mouseClick(seek, seek.width / 2, seek.height / 2)
            verify(Math.abs(Player.clock.position - Player.clock.duration / 2) < 1)
            mousePress(seek, 5, seek.height / 2)
            mouseMove(seek, seek.width * 0.75, seek.height / 2)
            mouseRelease(seek, seek.width * 0.75, seek.height / 2)
            verify(Math.abs(Player.clock.position - Player.clock.duration * 0.75) < 1)
        }
        function test_disabledWithoutBook() {
            const win = createTemporaryObject(windowFactory, host)
            const mode = createTemporaryObject(modeFactory, host, {window: win, loaded: false})
            mode.enter(); compare(mode.mini, false); win.hide()
        }
        function test_titleWrapAndShots() {
            mouseMove(host, host.width - 1, host.height - 1)
            Nav.hideTip()
            for (const theme of ["light", "dark"]) {
                Theme.mode = theme
                const mini = createTemporaryObject(miniFactory, host, {bookTitle: "Bên bờ sông", chapterTitle: "Chương 1"})
                mini.Window.window.update()
                verify(waitForRendering(mini))
                const shortHeight = mini.naturalHeight
                for (const length of ["short", "long"]) {
                    if (length === "long") {
                        mini.bookTitle = "Tôi đã đi qua những ngày rất dài để tìm lại câu chuyện còn dang dở bên bờ sông trong buổi sáng đầu mùa của chúng ta"
                        mini.chapterTitle = "Chương một trăm hai mươi ba · Những cuộc gặp gỡ trên con đường trở về nhà vào một ngày trời đầy nắng"
                        tryVerify(() => mini.naturalHeight > shortHeight)
                        const title = findChild(mini, "miniBookTitle")
                        verify(title.lineCount > 1)
                        verify(title.paintedWidth <= title.width + 1)
                    }
                    waitForRendering(mini)
                    const path = Qt.resolvedUrl("../../build/d2shots/mini_" + length + "_" + theme + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
                    qtGlyphAudit.scan()
                    grabImage(mini).save(path)
                }
                mini.destroy()
            }
        }
    }
}
