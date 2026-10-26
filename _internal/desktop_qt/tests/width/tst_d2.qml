import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 1440
    height: 900
    Component { id: settingsFactory; SettingsScreen {} }
    Component { id: importFactory; AddBook {} }
    Component { id: editFactory; EditBook {} }
    Component { id: coverFactory; CoverSearch {} }
    TestCase {
        name: "D2"
        when: windowShown
        function init() {
            Theme.reduceMotion = true
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system", autoRewind: true, sleepSchedule: null}
            Api.info = {version: "fixture"}
            Api.loaded = true
            Api.saving = false
            Nav.layers = []
        }
        function cleanup() { DesktopApi.delayed = false; Nav.layers = []; Theme.reduceMotion = false }
        function make(factory, props) {
            const item = createTemporaryObject(factory, host, Object.assign({width: host.width, height: host.height},props || {}))
            verify(item !== null)
            return item
        }
        function allText(item, out) {
            out = out || []
            if (item.text !== undefined) out.push(item.text)
            if (item.label !== undefined) out.push(item.label)
            if (item.title !== undefined) out.push(item.title)
            for (const child of item.children || []) allText(child,out)
            return out
        }
        function namedText(item, value) {
            if (item.text === value || item.label === value) return item
            for (const child of item.children || []) { const result = namedText(child,value); if (result) return result }
            return null
        }
        function test_settingsGroupsAndRows() {
            const page = make(settingsFactory)
            compare(page.groups.map(g => g.label).join("|"), "Giọng đọc|Nghe|Hẹn giờ ngủ|Giao diện|Thiết bị|Nâng cao")
            for (const group of ["listen","sleep","look","devices","advanced"]) {
                page.active = group; wait(30)
                const labels = allText(page)
                const expected = {listen: ["Tự lùi","Tự chọn nhạc nền","Nhạc của tôi"], sleep: ["Tự tắt","Lịch đêm","Mỗi lần nghe thêm","Nhỏ dần"], look: ["Màu","Nền đọc","Âm thanh chạm","Phím tắt chữ"], devices: ["Máy này","Kết nối Wi-Fi","Máy tính khác"], advanced: ["Bộ nhớ","Chẩn đoán","Giới thiệu","Gửi nhật ký"]}[group]
                for (const label of expected) verify(labels.includes(label), group + " missing " + label)
            }
        }
        function test_preferencesWriteThroughAndFailure() {
            const page = make(settingsFactory)
            page.active = "look"; wait(30)
            const choice = namedText(page,"Màu")
            verify(choice !== null)
            choice.picked("dark")
            compare(DesktopApi.requests[DesktopApi.requests.length - 1].method,"PUT")
            compare(DesktopApi.requests[DesktopApi.requests.length - 1].path,"/api/preferences")
            compare(DesktopApi.requests[DesktopApi.requests.length - 1].body.theme,"dark")
            compare(Theme.mode,"dark")
            DesktopApi.responses = {"/api/preferences": {status: 500,data: {error: "fixture failure"}}}
            choice.picked("light")
            compare(Theme.mode,"dark")
            compare(Api.notice,"fixture failure")
        }
        function test_settingsBackCompact() {
            const page = make(settingsFactory,{width: 700})
            page.active = "sleep"; wait(20)
            compare(Nav.layers.length,1)
            verify(Nav.back())
            compare(page.active,"")
            compare(Nav.layers.length,0)
        }
        function fixturePreview() {
            return {title: "Tên sách rất dài " .repeat(12),author: "Tác giả",sourceFingerprint: "fixture-fingerprint", chapters: [{index: 1,title: "Mở đầu",firstLine: "Nội dung",words: 70,included: false},{index: 2,title: "Chương một",firstLine: "Lời đầu",words: 500}],totals: {chapters:2,words:570},notes: [],hasCover: false}
        }
        function test_importReviewAndPayload() {
            DesktopApi.responses = {"/api/listen/import/preview": {status:200,data:fixturePreview()},"/api/listen/import": {status:200,data:{id:"new-book",how:"new"}}}
            const dialog = make(importFactory)
            dialog.begin(["D:/fixture/book.epub"])
            verify(dialog.preview !== null)
            compare(dialog.picked.length,1)
            compare(dialog.picked[0],2)
            const title = findChild(dialog,"importTitle")
            title.text = "Tên người dùng " .repeat(30)
            verify(title.height > 40)
            dialog.names = {2:"Tên chương đã sửa"}
            const typed = title.text.trim()
            dialog.add(false)
            const call = DesktopApi.requests.find(r => r.path === "/api/listen/import")
            verify(call !== undefined)
            compare(call.body.sourceFingerprint,"fixture-fingerprint")
            compare(call.body.title,typed)
            compare(call.body.chapters[0].index,2)
            compare(call.body.chapters[0].title,"Tên chương đã sửa")
            verify(!dialog.open)
        }
        function test_importCancelledResponseCannotReopen() {
            DesktopApi.delayed = true
            DesktopApi.responses = {"/api/listen/import/preview": {status:200,data:fixturePreview()}}
            const dialog = make(importFactory)
            dialog.begin(["D:/fixture/book.epub"])
            dialog.close()
            DesktopApi.finish()
            compare(dialog.preview,null)
            verify(!dialog.open)
        }
        function test_bookFileUsesOpenEndpoint() {
            DesktopApi.responses = {"/api/listen/open-book-file": {status:200,data:{id:"existing",how:"existing"}}}
            const dialog = make(importFactory)
            const opened = []
            dialog.openBook.connect(id => opened.push(id))
            dialog.begin(["D:/fixture/book.abook"])
            verify(DesktopApi.requests.some(r => r.path === "/api/listen/open-book-file" && r.body.path.endsWith(".abook")))
            verify(!DesktopApi.requests.some(r => r.path === "/api/listen/import/preview"))
            compare(opened.join(), "existing")
            compare(Api.notice, "Sách đã có")
            verify(!dialog.open)
        }
        function test_editIndependentDraftsAndBack() {
            DesktopApi.responses = {"/api/listen/books/edit": {status:200,data:{id:"edit",stage:"text",title:"Tên mới",author:"Tác giả cũ"}}}
            const dialog = make(editFactory)
            dialog.begin({id:"edit",stage:"text",title:"Tên cũ",author:"Tác giả cũ",capabilities:{editLayer:true}})
            const title = findChild(dialog,"editTitle"), author = findChild(dialog,"editAuthor")
            author.text = "Bản nháp tác giả " .repeat(15)
            title.text = "Tên mới " .repeat(40)
            dialog.mutate("PUT","/title",{title:title.text},"Đã đổi tên sách","title")
            compare(author.text,"Bản nháp tác giả " .repeat(15))
            const call = DesktopApi.requests.find(r => r.path === "/api/books/edit/title")
            compare(call.body.title,title.text)
            verify(title.height > 40)
            dialog.search()
            verify(dialog.searching)
            Nav.back()
            verify(!dialog.searching && dialog.open)
            Nav.back()
            verify(!dialog.open)
        }
        function test_coverQueryAndChoice() {
            const item = make(coverFactory,{width:500})
            DesktopApi.responses = {"/api/books/cover/cover/search?q=A%20B":{status:200,data:{results:[{title:"A B",provider:"itunes",url:"https://fixture/cover",thumb:""}],failed:[]}}}
            item.begin("cover","A B")
            compare(item.results.length,1)
            item.choose(item.results[0])
            const call = DesktopApi.requests.find(r => r.path === "/api/books/cover/cover")
            compare(call.method,"PUT")
            compare(call.body.url,"https://fixture/cover")
        }
    }
}
