import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 1920; height: 1080
    Component { id: barComponent; PlayerBar {} }
    Component { id: nowComponent; NowPlaying {} }
    Component { id: alertComponent; PlayerAlert {} }
    Component { id: subtitleComponent; PlayerSubtitle {} }
    Component { id: fadeComponent; PlayerFade {} }
    Component { id: sleepComponent; SleepPopover {} }
    Component { id: outputComponent; OutputPopover {} }
    Component { id: voiceComponent; PlayerVoicePopover {} }
    Component { id: progressComponent; SidebarProgress {} }
    Component { id: sidebarComponent; Sidebar { height: 900 } }
    SignalSpy { id: spy }
    TestCase {
        name: "PlayerStates"
        when: windowShown
        property string longText: "Giọng đọc tiếng Việt và tên chương rất dài cần hiển thị đầy đủ trên màn hình máy tính để người đang nghe biết chính xác nội dung. "
        function init() {
            Theme.reduceMotion = true; Nav.layers = []; Nav.uiVisible = true
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.info = {}; Api.voiceList = [{id: "local", name: "Giọng đọc trên máy", provider: "vieneu", gender: "female", online: false, default: true}, {id: "edge", name: "Hoài My", provider: "edge", gender: "female", online: true}]
            Api.preferences = {sleepFadeSeconds: 30, sleepExtendMinutes: 10}
            DesktopApi.responses["/api/readaloud/voices"] = {status: 200, data: Api.voiceList}
            Player.configure(Api.preferences); WidthNet.resetBooks(); Player.open("width", 1, 0, true); Player.pause(); Player.dismissError(); Player.setSleep("off")
            OutputDevices.selected = ""; OutputDevices.error = ""
        }
        function cleanup() {
            spy.target = null; Player.close(); Player.dismissError(); Player.setSleep("off")
            Nav.layers = []; Nav.uiVisible = true; WidthNet.resetBooks()
            Player.open("width", 1, 0, false); Theme.reduceMotion = false
        }
        function textBook() {
            WidthNet.setBook({id: "text-state", title: longText + longText, complete: true, chapters: [{id: 1, title: longText + longText, state: "text", available: false}], state: {voice: "local"}})
            Player.open("text-state", 1, 0, true)
        }
        function test_device_select_reject_revert_and_back() {
            const menu = createTemporaryObject(outputComponent, host, {width: 1024, height: 768})
            const before = OutputDevices.refreshes
            menu.show(); wait(180); compare(OutputDevices.refreshes, before + 1); compare(Nav.layers.length, 1)
            mouseClick(findChild(menu, "output_speaker")); compare(OutputDevices.selected, "speaker")
            mouseClick(findChild(menu, "output_gone")); compare(OutputDevices.selected, "speaker"); verify(findChild(menu, "outputError").visible)
            mouseClick(findChild(menu, "output_")); compare(OutputDevices.selected, ""); compare(OutputDevices.error, "")
            Nav.back(); wait(180); verify(!menu.open); compare(Nav.layers.length, 0)
            const count = OutputDevices.refreshes; wait(100); compare(OutputDevices.refreshes, count)
        }
        function test_closing_player_unwinds_voice_consent_and_output() {
            textBook(); Player.pause()
            const voice = createTemporaryObject(voiceComponent, host)
            voice.show(); wait(180)
            mouseClick(findChild(voice, "playerVoice_edge")); wait(180)
            compare(Nav.layers.length, 2)
            Nav.back(); wait(180); verify(voice.open); compare(Nav.layers.length, 1)
            mouseClick(findChild(voice, "playerVoice_edge")); wait(180)
            Player.close(); wait(180); verify(!voice.open); compare(Nav.layers.length, 0)
            Player.open("width", 1, 0, false)
            const output = createTemporaryObject(outputComponent, host)
            output.show(); wait(180); Player.close(); wait(180)
            verify(!output.open); compare(Nav.layers.length, 0)
        }
        function test_voice_error_close_and_resume_from_picker() {
            textBook(); Player.pause()
            const alert = createTemporaryObject(alertComponent, host, {width: 440})
            WidthNet.fail("Không có mạng - Hoài My đang không dùng được."); wait(180)
            verify(alert.open); verify(findChild(alert, "playerLocalVoice").visible); verify(findChild(alert, "playerOtherVoice").visible)
            mouseClick(findChild(alert, "playerErrorClose")); wait(180); compare(Player.error, ""); verify(!alert.open)
            const menu = createTemporaryObject(voiceComponent, host, {width: 1024, height: 768})
            menu.fromAlert(); wait(180); mouseClick(findChild(menu, "playerVoice_local")); wait(180)
            compare(Player.voiceId, "local"); verify(Player.playing); verify(!menu.open); compare(Nav.layers.length, 0)
        }
        function test_subtitle_prepare_delay_hidden_and_review() {
            textBook()
            const subtitle = createTemporaryObject(subtitleComponent, host, {width: 400})
            WidthNet.buffering(true); wait(400); verify(!subtitle.delayed)
            tryCompare(subtitle, "delayed", true, 2000)
            compare(findChild(subtitle, "playerSubtitleText").text, "Đang chuẩn bị giọng đọc…")
            Nav.uiVisible = false; compare(subtitle.delayed, false)
            WidthNet.buffering(false); Nav.uiVisible = true
            Player.review("width", 1); Player.pause(); compare(Player.purpose, "review")
        }
        function test_sleep_countdown_and_extend() {
            const fade = createTemporaryObject(fadeComponent, host, {width: 500})
            const sleep = createTemporaryObject(sleepComponent, host)
            sleep.show(); wait(180)
            Player.resume(); Player.setSleep("minutes", 1); WidthNet.advance(35); wait(180)
            verify(Player.fading); verify(fade.open); verify(findChild(fade, "playerFadeText").text.startsWith("Sắp tắt ·"))
            const countdown = findChild(sleep, "sleepCountdown")
            compare(countdown.text, "Tắt sau " + Player.clockText(Player.clock.sleepLeft))
            const before = countdown.text
            WidthNet.advance(2); verify(countdown.text !== before)
            Player.pause(); const paused = countdown.text; WidthNet.advance(2); compare(countdown.text, paused)
            Nav.back(); wait(180); verify(!sleep.open)
            mouseClick(findChild(fade, "playerFadeExtend")); verify(!Player.fading); verify(Player.clock.sleepLeft > 590)
        }
        function test_sidebar_loading_failure_states_and_no_hidden_polling() {
            DesktopApi.delayed = true
            const progress = createTemporaryObject(progressComponent, host, {width: 200})
            wait(180); verify(findChild(progress, "sidebarLoading").visible)
            DesktopApi.finish(); DesktopApi.delayed = false
            const books = [
                {id: "queue", title: longText, queuePosition: 2, progress: {overall: 0.2}},
                {id: "stop", title: longText, running: true, stopping: true, progress: {overall: 0.5}},
                {id: "pause", title: longText, running: true, paused: true, progress: {overall: 0.6}},
                {id: "start", title: longText, starting: true, progress: {overall: 0}}
            ]
            DesktopApi.responses["/api/library"] = {status: 200, data: {books: books}}
            progress.store.loadLibrary(); wait(180); compare(progress.live.length, 4); verify(findChild(progress, "sidebarAll").visible)
            spy.target = progress; spy.signalName = "projectRequested"; spy.clear()
            mouseClick(findChild(progress, "sidebarProject_0")); compare(spy.count, 1)
            compare(spy.signalArguments[0][0], "stop")
            compare(findChild(progress, "sidebarStatus_0").Accessible.name, "Đang dừng")
            compare(findChild(progress, "sidebarStatus_1").Accessible.name, "Đang tạm dừng")
            verify(findChild(progress, "sidebarTitle_0").implicitHeight > 40)
            progress.store.libraryData = {books: books.slice(0, 3)}; wait(180)
            compare(findChild(progress, "sidebarStatus_2").Accessible.name, "Đang chờ 2")
            compare(findChild(progress, "sidebarProgress_2").Accessible.name, "Tiến độ: " + longText)
            Nav.uiVisible = false; verify(!progress.store.libraryTimer.running)
            const count = DesktopApi.requests.length; wait(150); compare(DesktopApi.requests.length, count)
            Nav.uiVisible = true; verify(DesktopApi.requests.length > count)
            progress.store.libraryData = null; DesktopApi.responses["/api/library"] = {status: 503, data: {message: "Bạn hãy thử tải lại tiến độ."}}
            progress.store.loadLibrary(); wait(180); verify(progress.store.libraryError !== "")
        }
        function test_long_vietnamese_data() { return [{tag: "1024", pixels: 1024}, {tag: "1920", pixels: 1920}] }
        function test_long_vietnamese(data) {
            textBook()
            const bar = createTemporaryObject(barComponent, host, {width: data.pixels - 232})
            compare(findChild(bar, "chapterHeardProgress").Accessible.name, "Đã nghe chương này")
            const alert = createTemporaryObject(alertComponent, host, {width: data.pixels - 232})
            WidthNet.fail(longText + longText); wait(180)
            const message = findChild(alert, "playerErrorText")
            verify(message.implicitHeight > message.font.pixelSize * 2); verify(message.width <= alert.width); compare(message.truncated, false)
            const now = createTemporaryObject(nowComponent, host, {width: data.pixels - 232, height: 1000})
            now.show(); wait(180); verify(now.open)
            for (const text of [findChild(bar, "barChapterTitle"), findChild(now, "playerSubtitleText"), findChild(now, "nowChapterTitle")]) {
                verify(text.width > 0); verify(text.implicitHeight > text.font.pixelSize * 2); compare(text.truncated, false)
            }
            const scroll = findChild(now, "nowColumnScroll")
            verify(scroll.contentHeight >= scroll.height)
            scroll.contentY = scroll.contentHeight - scroll.height
            const chip = findChild(now, "nowSpeed")
            const chipBottom = chip.mapToItem(now, 0, chip.height).y
            verify(chipBottom > now.topH && chipBottom < now.height)
            const sidebar = createTemporaryObject(sidebarComponent, host)
            compare(sidebar.Accessible.name, "Điều hướng chính")
            now.close(); wait(180); bar.destroy(); alert.destroy(); now.destroy(); sidebar.destroy()
        }
    }
}
