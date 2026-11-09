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

    TestCase {
        name: "ScreenStackDirection"
        when: windowShown
        property var stack: null

        function init() {
            stack = createTemporaryObject(stackFactory, host)
            stack.show(0)
        }

        function test_pushAndBackMoveInOppositeDirections() {
            const library = stack._top(0)
            stack.push(page)
            const book = stack._top(0)
            tryVerify(() => library.dx < 0, 1000)
            compare(library.opacity, 1)
            compare(book.opacity, 1)
            tryVerify(() => book.visible && book.dx > 0, 1000)
            tryCompare(stack, "busy", false, 1500)
            compare(book.dx, 0)
            compare(book.zoom, 1)

            stack.pop()
            tryVerify(() => book.dx > 0, 1000)
            compare(book.opacity, 1)
            compare(library.opacity, 1)
            tryVerify(() => library.visible && library.dx < 0, 1000)
            tryCompare(stack, "busy", false, 1500)
            compare(library.dx, 0)
            compare(library.zoom, 1)
            compare(stack.depth, 1)
        }

        function test_sidebarSectionsMoveInOppositeDirections() {
            const library = stack._top(0)
            stack.show(2)
            const settings = stack._top(2)
            tryVerify(() => library.dy < 0, 1000)
            tryVerify(() => settings.visible && settings.dy > 0, 1000)
            tryCompare(stack, "busy", false, 1500)
            stack.show(0)
            tryVerify(() => settings.dy > 0, 1000)
            tryVerify(() => library.visible && library.dy < 0, 1000)
            tryCompare(stack, "busy", false, 1500)
            compare(library.dy, 0)
            compare(library.zoom, 1)
        }

        function test_popToRootKeepsBackDirection() {
            stack.push(page)
            tryCompare(stack, "busy", false, 1500)
            stack.push(page)
            tryCompare(stack, "busy", false, 1500)
            const outgoing = stack._top(0)
            const library = stack._stacks[0][0]
            stack.popToRoot()
            tryVerify(() => outgoing.dx > 0, 1000)
            tryVerify(() => library.visible && library.dx < 0, 1000)
            tryCompare(stack, "busy", false, 1500)
            compare(stack.depth, 1)
        }

        function test_coverMovesFromSourceAndReturnsToIt() {
            const source = stack._top(0).content.transitionCover
            stack.push(bookPage, {}, source)
            const target = stack._top(0).content.transitionCover
            const cover = findChild(stack, "navigationCoverMorph")
            compare(stack._coverStart.x, 40)
            compare(stack._coverEnd.x, 400)
            compare(source.opacity, 1)
            compare(target.opacity, 0)
            tryVerify(() => stack.coverT > 0 && stack.coverT < 1)
            fuzzyCompare(cover.x, 40 + 360 * stack.coverT, 0.01)
            fuzzyCompare(cover.width, 100 + 60 * stack.coverT, 0.01)
            tryCompare(stack, "busy", false, 1500)
            compare(source.opacity, 1)
            compare(target.opacity, 1)
            compare(cover.visible, false)
            stack.pop()
            compare(stack._coverStart.x, 400)
            compare(stack._coverEnd.x, 40)
            tryVerify(() => stack.coverT > 0 && stack.coverT < 1)
            fuzzyCompare(cover.x, 400 - 360 * stack.coverT, 0.01)
            tryCompare(stack, "busy", false, 1500)
            compare(source.opacity, 1)
            compare(cover.visible, false)
        }
    }
}
