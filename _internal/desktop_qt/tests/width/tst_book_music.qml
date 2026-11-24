import QtQuick
import QtTest
import ABook
import "../../qml" as Subject
import "ParityFixtures.js" as Fixture

Item {
    id: host
    width: 1000; height: 800
    Component { id: bookPage; Subject.BookPage {} }
    TestCase {
        name: "BookMusicPlacement"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Theme.reduceMotion = true
            WidthNet.setBook(Fixture.playerBook(true))
            DesktopApi.responses = {
                "/api/listen/books/width": {status: 200, data: Fixture.playerBook(true)},
                "/api/books/width/music/library": {status: 200, data: {tracks: [{link: "https://example.invalid/a.mp3", title: "Audit melody", scenes: 2, bytes: 1024}], missingBytes: 1024, unsaved: ["https://example.invalid/a.mp3"]}}
            }
        }
        function cleanup() { DesktopApi.delayed = false; Theme.reduceMotion = false; WidthNet.resetBooks() }
        function page() {
            const value = createTemporaryObject(bookPage, host, {book: {bookId: "width", title: "Audit book"}, width: host.width, height: host.height})
            verify(value !== null)
            tryVerify(function() { return value.loaded })
            return value
        }
        function musicCalls() { return DesktopApi.requests.filter(r => r.path.indexOf("music/library") >= 0) }
        function test_chaptersNeverLoadMusicEvenAtEnd() {
            const value = page()
            const list = findChild(value, "bookChapters")
            list.positionViewAtEnd()
            compare(list.footer, null)
            compare(musicCalls().length, 0)
            compare(findChild(value, "bookMusicPane").active, false)
        }
        function test_musicLoadsOnlyInItsOwnTabAndCanBeLeftWhilePending() {
            const value = page()
            DesktopApi.delayed = true
            value.tab = value.musicIndex
            tryVerify(function() { return findChild(value, "bookMusic") !== null })
            const music = findChild(value, "bookMusic")
            compare(music.loading, true)
            compare(findChild(music, "bookMusicStatus").text, "Đang tải")
            verify(musicCalls().length > 0)
            value.tab = 0
            tryCompare(findChild(value, "bookMusicPane"), "active", false)
            verify(findChild(value, "bookChapters").enabled)
            DesktopApi.finish()
        }
        function test_rowsAreVirtualizedAndEmptyAndErrorAreExplicit() {
            const value = page()
            value.tab = value.musicIndex
            tryVerify(function() { return findChild(value, "bookMusic") !== null })
            const music = findChild(value, "bookMusic")
            tryCompare(music, "loading", false)
            compare(music.count, 1)
            compare(music.tracks[0].title, "Audit melody")
            verify(findChild(music, "bookMusicSaveAll").visible)
            const tracks = []
            for (let n = 0; n < 200; n++) tracks.push({link: "https://example.invalid/" + n + ".mp3", title: "Audit melody " + n, scenes: 2})
            DesktopApi.responses = {"/api/books/width/music/library": {status: 200, data: {tracks: tracks, missingBytes: 0}}}
            music.refresh()
            tryCompare(music, "count", 200)
            tryVerify(function() {
                const count = music.contentItem.children.filter(child => child.objectName === "bookMusicRow").length
                return count > 0 && count < 40
            })
            tryVerify(function() {
                // Newly visited variable-height rows refine ListView's estimate of the end.
                music.positionViewAtIndex(music.count - 1, ListView.End)
                music.forceLayout()
                return music.itemAtIndex(music.count - 1) !== null
            })
            DesktopApi.responses = {"/api/books/width/music/library": {status: 200, data: {tracks: [], missingBytes: 0}}}
            music.refresh()
            tryCompare(findChild(music, "bookMusicStatus"), "text", "Chưa có nhạc")
            DesktopApi.responses = {"/api/books/width/music/library": {status: 503, data: {error: "fixture"}}}
            music.refresh()
            verify(findChild(music, "bookMusicRetry").visible)
        }
        function bundledRows(music) {
            return music.contentItem.children.filter(child => child.objectName === "bookMusicRow" && findChild(child, "bookMusicBundledRow").visible)
        }
        // bookmusic2: gói chỉ có nhạc `local:` của người làm sách từng ghi "Chưa có nhạc" trong khi sách vẫn phát nhạc.
        function test_packagedTracksAreListedInListeningOrderWithoutSave() {
            const float = "local:" + "a".repeat(40), phantom = "local:" + "b".repeat(40)
            DesktopApi.responses["/api/books/width/music/library"] = {status: 200, data: {tracks: [
                {link: float, title: "float flower (MONSTER)", creator: "Kuniaki Haishima", scenes: 4, scene: "1:0", bundled: true, saved: false, downloaded: false,
                 mood: [{id: "sadness", score: 0.8}, {id: "nostalgia", score: 0.6}]},
                {link: phantom, title: "Phantom", creator: "Yoshihisa Hirano", scenes: 2, scene: "1:136729", bundled: true, saved: false, downloaded: false, mood: []}],
                missingBytes: 0, unsaved: []}}
            const value = page()
            value.tab = value.musicIndex
            tryVerify(function() { return findChild(value, "bookMusic") !== null })
            const music = findChild(value, "bookMusic")
            tryCompare(music, "loading", false)
            compare(music.count, 2)
            compare(findChild(music, "bookMusicStatus").text, "")
            verify(!findChild(music, "bookMusicSaveAll").visible)
            tryVerify(function() { return bundledRows(music).length === 2 })
            const first = music.itemAtIndex(0)
            const row = findChild(first, "bookMusicBundledRow")
            compare(findChild(row, "musicBundledLabel").text, " · Đi kèm sách")
            verify(!findChild(first, "musicRowPreview").visible, "không có nút nghe thử")
            mouseClick(row)
            const sheet = findChild(music, "musicBundledDetail")
            tryCompare(sheet, "open", true)
            compare(sheet.title, "float flower (MONSTER)")
            compare(sheet.description, "Kuniaki Haishima")
            tryCompare(findChild(sheet, "musicBundledMood"), "text", "Đoạn này sadness.")
            sheet.open = false
            sheet.show(music.tracks[1])
            compare(sheet.mood.length, 0)
        }
        function test_mixedBookKeepsCatalogRowsAligned() {
            const float = "local:" + "a".repeat(40)
            DesktopApi.responses["/api/books/width/music/library"] = {status: 200, data: {tracks: [
                {link: float, title: "float flower (MONSTER)", creator: "Kuniaki Haishima", scenes: 4, scene: "1:0", bundled: true, saved: false, downloaded: false, mood: []},
                {link: "https://example.invalid/a.mp3", title: "Audit melody", creator: "Kevin MacLeod", scenes: 2, bytes: 1024, saved: false, downloaded: false}],
                missingBytes: 1024, unsaved: ["https://example.invalid/a.mp3"]}}
            const value = page()
            value.tab = value.musicIndex
            tryVerify(function() { return findChild(value, "bookMusic") !== null })
            const music = findChild(value, "bookMusic")
            tryCompare(music, "loading", false)
            compare(music.count, 2)
            verify(findChild(music, "bookMusicSaveAll").visible)
            tryVerify(function() { return music.itemAtIndex(1) !== null })
            const bundled = findChild(music.itemAtIndex(0), "musicBundledMark")
            const preview = findChild(music.itemAtIndex(1), "musicRowPreview")
            verify(findChild(music.itemAtIndex(1), "bookMusicBundledRow").visible === false)
            compare(bundled.mapToItem(music, 0, 0).x, preview.mapToItem(music, 0, 0).x)
            compare(bundled.width, preview.width)
        }
    }
}
