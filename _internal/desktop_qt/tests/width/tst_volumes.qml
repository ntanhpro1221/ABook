import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady
import "ParityFixtures.js" as Fixture

Item {
    id: host
    width: 1000; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: page; BookPage {} }
    Component { id: editor; VolumeEditor {} }
    TestCase {
        name: "BookVolumes"
        when: windowShown
        function book() {
            const data = Fixture.playerBook(false)
            data.title = "Đồng hồ bên cửa sổ"
            data.cover = null
            data.chapters = data.chapters.slice(0, 3).map((c, i) => Object.assign({}, c, {volumeId: i < 2 ? 1 : 2}))
            data.volumes = [
                {id: 1, number: 1, title: "Tập một", cover: {file: "covers/1.jpg", version: 1}, chapters: data.chapters.slice(0, 2)},
                {id: 2, number: 2, title: "Tập hai", cover: null, chapters: data.chapters.slice(2)}]
            return data
        }
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {}; Nav.layers = []; Theme.reduceMotion = true; Theme.mode = "light"
            WidthNet.setBook(book())
            DesktopApi.responses = {"/api/listen/books/width": {status: 200, data: book()}}
        }
        function cleanup() { Nav.layers = []; Theme.mode = "auto"; Theme.reduceMotion = false; WidthNet.resetBooks() }
        function shot(name) {
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            const target = VisualReady.grabTarget(host.Window.window, host)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(target).save(path)
            verify(qtUiTree.save(path, target))
        }
        function test_volumeRowsOpenTheirChaptersAndReturn() {
            const made = createTemporaryObject(page, host, {width: host.width, height: host.height,
                book: {bookId: "width", title: "Đồng hồ bên cửa sổ"}})
            verify(made !== null)
            tryVerify(() => made.loaded && made.volumePicker)
            const list = findChild(made, "bookVolumes")
            compare(list.count, 2)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            shot("qt_volumes")
            mouseClick(findChild(made, "bookVolume_2"))
            tryCompare(made, "volumePicker", false)
            compare(findChild(made, "bookVolumeTitle").text, "Tập hai")
            shot("qt_volume_chapters")
            mouseClick(findChild(made, "bookVolumeBack"))
            tryCompare(made, "volumePicker", true)
        }
        function test_singleVolumeSkipsThePicker() {
            const data = book(); data.volumes = [Object.assign({}, data.volumes[0], {chapters: data.chapters})]
            for (const chapter of data.chapters) chapter.volumeId = 1
            WidthNet.setBook(data)
            DesktopApi.responses = {"/api/listen/books/width": {status: 200, data: data}}
            const made = createTemporaryObject(page, host, {width: host.width, height: host.height, book: {bookId: "width", title: data.title}})
            tryVerify(() => made.loaded)
            compare(made.volumePicker, false)
        }
        function test_editorRefusesCrossedBoundariesBeforeSending() {
            const made = createTemporaryObject(editor, host, {width: 500, book: book()})
            compare(made.rows.length, 2)
            made.change(2, "start", 1)
            made.save()
            verify(made.problem.length > 0)
            compare(made.busy, false)
        }
    }
}
