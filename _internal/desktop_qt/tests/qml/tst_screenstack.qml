import QtQuick
import QtTest
import ABook
import "../../qml" as App

Item {
    id: host
    width: 900
    height: 600

    Component { id: page; Rectangle { color: "#f5f3ef" } }
    Component { id: libraryPage; Rectangle { property alias transitionCover: cover; CoverView { id: cover; x: 40; y: 80; width: 100; height: 150; title: "Sách" } } }
    Component { id: bookPage; Rectangle { property alias transitionCover: cover; CoverView { id: cover; x: 400; y: 100; width: 160; height: 240; title: "Sách" } } }
    Component { id: stackFactory; App.ScreenStack { width: 900; height: 600; roots: [libraryPage, page, page] } }
    Component {
        id: scrolledLibrary
        Flickable {
            property alias transitionCover: scrolledCover
            contentWidth: width; contentHeight: 1400; contentY: 510
            CoverView { id: scrolledCover; x: 40; y: 800; width: 100; height: 150; title: "Sách" }
        }
    }

    TestCase {
        name: "ScreenStackDirection"
        when: windowShown
        property var stack: null

        function init() {
            Theme.reduceMotion = false
            stack = createTemporaryObject(stackFactory, host)
            stack.show(0)
        }

        // Each transition runs on the test animation clock from its trigger until its transient was seen (mid-push dx,
        // 0 < coverT < 1): a loaded machine may give the test thread its turn only after a real-time animation ended.
        // The end state is still awaited in real time.
        function cleanup() { qtAnimationClock.end(); Theme.reduceMotion = false }

        function test_pushAndBackMoveInOppositeDirections() {
            const library = stack._top(0)
            qtAnimationClock.begin()
            stack.push(page)
            const book = stack._top(0)
            verify(qtAnimationClock.advanceUntil(() => library.dx < 0, 1000))
            compare(library.opacity, 1)
            compare(book.opacity, 1)
            verify(qtAnimationClock.advanceUntil(() => book.visible && book.dx > 0, 1000))
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(book.dx, 0)
            compare(book.zoom, 1)

            qtAnimationClock.begin()
            stack.pop()
            verify(qtAnimationClock.advanceUntil(() => book.dx > 0, 1000))
            compare(book.opacity, 1)
            compare(library.opacity, 1)
            verify(qtAnimationClock.advanceUntil(() => library.visible && library.dx < 0, 1000))
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(library.dx, 0)
            compare(library.zoom, 1)
            compare(stack.depth, 1)
        }

        function test_sidebarSectionsMoveInOppositeDirections() {
            const library = stack._top(0)
            qtAnimationClock.begin()
            stack.show(2)
            const settings = stack._top(2)
            verify(qtAnimationClock.advanceUntil(() => library.dy < 0, 1000))
            verify(qtAnimationClock.advanceUntil(() => settings.visible && settings.dy > 0, 1000))
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            qtAnimationClock.begin()
            stack.show(0)
            verify(qtAnimationClock.advanceUntil(() => settings.dy > 0, 1000))
            verify(qtAnimationClock.advanceUntil(() => library.visible && library.dy < 0, 1000))
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(library.dy, 0)
            compare(library.zoom, 1)
        }

        function test_popToRootKeepsBackDirection() {
            qtAnimationClock.begin()
            stack.push(page)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            qtAnimationClock.begin()
            stack.push(page)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            const outgoing = stack._top(0)
            const library = stack._stacks[0][0]
            qtAnimationClock.begin()
            stack.popToRoot()
            verify(qtAnimationClock.advanceUntil(() => outgoing.dx > 0, 1000))
            verify(qtAnimationClock.advanceUntil(() => library.visible && library.dx < 0, 1000))
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(stack.depth, 1)
        }

        function test_coverMovesFromSourceAndReturnsToIt() {
            const source = stack._top(0).content.transitionCover
            qtAnimationClock.begin()
            stack.push(bookPage, {}, source)
            const target = stack._top(0).content.transitionCover
            const cover = findChild(stack, "navigationCoverMorph")
            compare(stack._coverStart.x, 40)
            compare(stack._coverEnd.x, 400)
            compare(source.opacity, 1)
            compare(target.opacity, 0)
            verify(qtAnimationClock.advanceUntil(() => stack.coverT > 0 && stack.coverT < 1, 5000))
            fuzzyCompare(cover.x, 40 + 360 * stack.coverT, 0.01)
            fuzzyCompare(cover.width, 100 + 60 * stack.coverT, 0.01)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(source.opacity, 1)
            compare(target.opacity, 1)
            compare(cover.visible, false)
            qtAnimationClock.begin()
            stack.pop()
            compare(stack._coverStart.x, 400)
            compare(stack._coverEnd.x, 40)
            verify(qtAnimationClock.advanceUntil(() => stack.coverT > 0 && stack.coverT < 1, 5000))
            fuzzyCompare(cover.x, 400 - 360 * stack.coverT, 0.01)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(source.opacity, 1)
            compare(cover.visible, false)
        }

        function test_bookKeepsItsLibraryAndUsesOneClockBothWays() {
            const library = stack._top(0)
            const source = library.content.transitionCover
            qtAnimationClock.begin()
            stack.push(bookPage, {}, source)
            const book = stack._top(0)
            verify(stack._container)
            compare(library.dx, 0)
            compare(book.dx, 0)
            verify(qtAnimationClock.advanceUntil(() => stack.coverT > .1 && stack.coverT < .9, 5000))
            compare(library.opacity, 1)
            fuzzyCompare(book.opacity, stack.bookProgress, .001)
            fuzzyCompare(library.zoom, 1 - Theme.bookRecede * stack.bookProgress, .001)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            qtAnimationClock.begin()
            stack.pop()
            verify(stack._container)
            compare(library.dx, 0)
            compare(book.dx, 0)
            verify(qtAnimationClock.advanceUntil(() => stack.coverT > .1 && stack.coverT < .9, 5000))
            compare(library.opacity, 1)
            fuzzyCompare(book.opacity, stack.bookProgress, .001)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(library.zoom, 1)
            compare(source.opacity, 1)
        }

        function test_scrolledSourceReturnsToItsVisibleCell() {
            stack.destroy()
            stack = createTemporaryObject(stackFactory, host, { roots: [scrolledLibrary, page, page] })
            stack.show(0)
            const library = stack._top(0).content
            const source = library.transitionCover
            qtAnimationClock.begin()
            stack.push(bookPage, {}, source)
            compare(stack._coverStart.y, 290)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            qtAnimationClock.begin()
            stack.pop()
            compare(stack._coverEnd.y, 290)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1500)
            compare(library.contentY, 510)
            compare(stack._coverBox(source).y, 290)
        }

        function test_reducedMotionFadesWithoutMovingArtwork() {
            Theme.reduceMotion = true
            const library = stack._top(0)
            qtAnimationClock.begin()
            stack.push(bookPage, {}, library.content.transitionCover)
            const book = stack._top(0)
            verify(stack._container)
            compare(stack._coverFrom, null)
            compare(book.content.transitionCover.opacity, 1)
            compare(library.zoom, 1)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1000)
            qtAnimationClock.begin()
            stack.pop()
            compare(stack._coverFrom, null)
            qtAnimationClock.end()
            tryCompare(stack, "busy", false, 1000)
            compare(library.zoom, 1)
        }
    }
}
