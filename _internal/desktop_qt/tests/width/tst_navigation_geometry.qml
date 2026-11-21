import QtQuick
import QtTest
import ABook
import "../../qml" as App

Item {
    id: host
    width: 1280; height: 900
    Component { id: sourcePage; Item { property alias transitionCover: cover; CoverView { id: cover; x: 40; y: 280; width: 180; height: 270; title: "Sách" } } }
    Component { id: bookPage; BookPage { book: ({bookId: "width", title: "Hành trình qua miền đất mới"}) } }
    Component { id: stackFactory; App.ScreenStack { width: 1280; height: 900; roots: [sourcePage] } }
    Component { id: settingsFactory; SettingsScreen { width: 760; height: 900 } }
    Component { id: studioFactory; StudioScreen { width: 1200; height: 900 } }
    TestCase {
        name: "NavigationGeometry"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme); Theme.reduceMotion = false; Nav.uiVisible = true
            DesktopApi.responses["/api/listen/books/width"] = {status: 200, data: {id: "width", title: "Hành trình qua miền đất mới", stage: "audio", chapters: []}}
        }
        function cleanup() { qtAnimationClock.end() }
        function test_coverTracksResponsiveDestinationUntilLastFrame() {
            const stack = createTemporaryObject(stackFactory, host)
            stack.show(0)
            const source = stack._top(0).content.transitionCover
            stack.push(bookPage, {}, source)
            const destination = stack._top(0).content.transitionCover
            tryCompare(stack, "busy", false, 1500)
            verify(destination.width > 100, "The actual expanded destination must differ from its compact construction size")
            const point = destination.mapToItem(stack, 0, 0)
            fuzzyCompare(stack._coverEnd.width, destination.width, 0.1)
            fuzzyCompare(stack._coverEnd.height, destination.height, 0.1)
            fuzzyCompare(stack._coverEnd.x, point.x, 0.1)
            fuzzyCompare(stack._coverEnd.y, point.y, 0.1)
            compare(destination.opacity, 1)
            stack.pop(); tryCompare(stack, "busy", false, 1500)
            compare(source.opacity, 1)
            fuzzyCompare(stack._coverEnd.width, source.width, 0.1)
        }
        function test_narrowSettingsBackReversesEntry() {
            const settings = createTemporaryObject(settingsFactory, host)
            const frame = findChild(settings, "settingsFrame")
            const origin = frame.mapToItem(host, 0, 0).x
            qtAnimationClock.begin()
            settings.active = "listen"
            verify(qtAnimationClock.advanceUntil(() => settings.navigationPhase > 0 && settings.navigationPhase < 1, 5000))
            verify(frame.mapToItem(host, 0, 0).x > origin)
            verify(findChild(settings, "settingsContentSlide").image !== null)
            qtAnimationClock.end()
            tryCompare(settings, "navigationPhase", 1)
            qtAnimationClock.begin()
            settings.active = ""
            verify(qtAnimationClock.advanceUntil(() => settings.navigationPhase > 0 && settings.navigationPhase < 1, 5000))
            verify(frame.mapToItem(host, 0, 0).x < origin)
            verify(findChild(settings, "settingsContentSlide").image !== null)
            qtAnimationClock.end()
            tryCompare(settings, "navigationPhase", 1)
            compare(settings.shown, "")
        }
        function test_studioBackReversesEntry() {
            const studio = createTemporaryObject(studioFactory, host)
            const content = findChild(studio, "studioContent")
            qtAnimationClock.begin()
            studio.openProject("width")
            verify(qtAnimationClock.advanceUntil(() => studio.phase > 0 && studio.phase < 1, 5000))
            verify(content.mapToItem(host, 0, 0).x > 0)
            verify(findChild(studio, "studioContentSlide").image !== null)
            qtAnimationClock.end()
            tryCompare(studio, "phase", 1)
            qtAnimationClock.begin()
            studio.goList()
            verify(qtAnimationClock.advanceUntil(() => studio.phase > 0 && studio.phase < 1, 5000))
            verify(content.mapToItem(host, 0, 0).x < 0)
            verify(findChild(studio, "studioContentSlide").image !== null)
            qtAnimationClock.end()
            tryCompare(studio, "phase", 1)
        }
        function test_bookTabsMoveAndReverseInsteadOfOnlyFading() {
            const page = createTemporaryObject(bookPage, host, {width: 1280, height: 900})
            tryCompare(page, "loaded", true)
            const chapters = findChild(page, "bookChapters"), history = findChild(page, "historyList")
            const origin = chapters.mapToItem(host, 0, 0).x
            qtAnimationClock.begin()
            page.tab = 1
            verify(qtAnimationClock.advanceUntil(() => history.opacity > 0 && history.opacity < 1 && history.mapToItem(host, 0, 0).x > origin, 5000))
            verify(chapters.mapToItem(host, 0, 0).x < origin)
            qtAnimationClock.end()
            tryCompare(history, "opacity", 1)
            qtAnimationClock.begin()
            page.tab = 0
            verify(qtAnimationClock.advanceUntil(() => chapters.opacity > 0 && chapters.opacity < 1 && chapters.mapToItem(host, 0, 0).x < origin, 5000))
            verify(history.mapToItem(host, 0, 0).x > origin)
            qtAnimationClock.end()
            tryCompare(chapters, "opacity", 1)
            fuzzyCompare(chapters.mapToItem(host, 0, 0).x, origin, 0.01)
        }
    }
}
