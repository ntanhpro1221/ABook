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
    Component { id: levelBar; LevelBar { width: 200; height: 8 } }
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
            // 0.4.173 soát tay: bìa ảnh của quyển 1 vuông, bìa vẽ của quyển 2 bo góc - cả hai phải bo Theme.radiusCover
            const frame = grabImage(VisualReady.grabTarget(host.Window.window, host))
            for (const id of [1, 2]) {
                const cover = findChild(findChild(made, "bookVolume_" + id), "bookVolumeCover")
                compare(cover.radius, Theme.radiusCover)
                const at = cover.mapToItem(host, 0, 0)
                const corner = frame.pixel(Math.round(at.x) + 1, Math.round(at.y) + 1)
                const inside = frame.pixel(Math.round(at.x + cover.width / 2), Math.round(at.y + cover.height - 3))
                verify(Qt.colorEqual(corner, Theme.bg), "góc bìa quyển " + id + " phải là nền (bo góc), không phải " + corner)
                verify(!Qt.colorEqual(inside, Theme.bg), "bìa quyển " + id + " có vẽ")
            }
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
        // Hàng quyển giống web (BookScreen.tsx ChapterGroups: p-3 items-center, BookCover sm + font-medium + Progress mt-2 h-2) và Android
        // (dọc 12, CenterVertically, volume_progress_<id> 8 dp): bìa bo Theme.radiusCover = 12 (DESIGN.md "12 bìa/ảnh"; leftfix đưa web BookCover
        // và Android BookCover nhỏ lên 12), bìa và chữ canh giữa hàng, đệm 12, cao tối thiểu 84 + 24; bìa vẽ chỉ ghi chữ cái đầu tên sách, tên đậm
        // vừa, thanh 8 px bo tròn cách 8 px, dưới 2 % không tô và chạy dần.
        // Thanh "Đã nghe" (LevelBar.progress): dưới Theme.progressFillMin (2 %) không tô như web progressFill / Android ProgressFill.of; đổi giá trị
        // thì chạy dần (web motion-progress); thang cảm xúc (progress false) tô đúng giá trị, không chuyển động.
        function test_heardBarThresholdAndMotion() {
            const bar = createTemporaryObject(levelBar, host, {progress: true, score: 0.01})
            const fill = findChild(bar, "levelBarFill")
            compare(fill.width, 0)
            bar.score = 0.5
            if (Theme.motionMedium > 0 && !Theme.reduceMotion) verify(fill.width < 100)
            tryCompare(fill, "width", 100)
            const emotion = createTemporaryObject(levelBar, host, {score: 0.01})
            compare(findChild(emotion, "levelBarFill").width, 2)
            emotion.score = 0.5
            compare(findChild(emotion, "levelBarFill").width, 100)
        }
        function test_volumeRowsMatchWebAndAndroid() {
            const made = createTemporaryObject(page, host, {width: host.width, height: host.height,
                book: {bookId: "width", title: "Đồng hồ bên cửa sổ"}})
            tryVerify(() => made.loaded && made.volumePicker)
            for (const id of [1, 2]) {
                const row = findChild(made, "bookVolume_" + id)
                const cover = findChild(row, "bookVolumeCover")
                compare(cover.radius, Theme.radiusCover)
                compare(Theme.radiusCover, 12)
                verify(row.height >= 84 + 24)
                compare(cover.x, 12)
                // Canh giữa hàng: bìa và cột chữ cùng tâm dọc với hàng
                verify(Math.abs(cover.y + cover.height / 2 - row.height / 2) <= 1)
                const info = findChild(row, "bookVolumeName").parent
                verify(Math.abs(info.y + info.height / 2 - row.height / 2) <= 1)
                compare(info.x, 12 + 56 + 16)
                compare(row.width - (info.x + info.width), 12)
                compare(cover.initials, true)
                compare([cover.width, cover.height], [56, 84])
                const name = findChild(row, "bookVolumeName")
                compare(name.font.weight, Theme.weightMedium)
                compare(name.text, id === 1 ? "Tập một" : "Tập hai")
                const bar = findChild(row, "bookVolumeProgress")
                compare(bar.height, 8)
                compare(bar.radius, 4)
                compare(bar.Accessible.name, "Đã nghe")
                compare(bar.width, name.width)
                // Cách dòng số chương ngay trên đúng 8 px
                const column = bar.parent
                const hint = column.children[1]
                compare(bar.mapToItem(row, 0, 0).y - hint.mapToItem(row, 0, hint.height).y, 8)
                verify(bar.mapToItem(row, 0, bar.height).y <= row.height)
                compare(bar.progress, true)
            }
            // Quyển 2 không có ảnh, sách không có ảnh: bìa vẽ nhỏ chỉ ghi chữ cái đầu tên sách (coverLabel của web: "Đồng hồ bên cửa sổ" -> "ĐB")
            const drawn = findChild(findChild(findChild(made, "bookVolume_2"), "bookVolumeCover"), "coverInitials")
            verify(drawn !== null && drawn.visible)
            compare(drawn.text, "ĐB")
            compare(drawn.font.pixelSize, Theme.sizeSection)
            compare(drawn.font.weight, Theme.weightBold)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            shot("qt_volumes_rows")
        }
    }
}
