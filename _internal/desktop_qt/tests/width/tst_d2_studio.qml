import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Cài đặt › Studio (máy này): chọn giọng kể / chất lượng, công tắc pin, cài / gỡ (hỏi lại + Back), mẫu sách mới (đổi tên giữ nguyên phần còn
// lại, xoá + hoàn tác), cách đọc chung (thêm / bỏ), tên dài xuống dòng; ảnh settings_studio_*.png sáng + tối ở build/d2shots.
Item {
    id: host
    width: 900
    height: 1900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; SettingsStudio {} }
    SignalSpy { id: wantsStudio; signalName: "studioRequested" }

    TestCase {
        id: test
        name: "D2Studio"
        when: windowShown
        property var store: ({})

        function templates() {
            return [
                {name: "Đêm khuya", narrator: "Mai", profile: "high_quality", analysisModel: "", startNow: true, precastWait: false},
                {name: "Nhanh gọn", narrator: "", profile: "fast", analysisModel: "", startNow: false, precastWait: true},
                {name: "Cân bằng", narrator: "Nam", profile: "balanced", analysisModel: "", startNow: true, precastWait: false}
            ]
        }
        function installedStatus() {
            return {installed: true, outdated: [], running: false, step: null, steps: [], progress: null, detail: "", error: null,
                    gpu: {name: "NVIDIA GeForce RTX 3060", memory: 12 * 1073741824}, root: "C:\\Users\\Linh\\AppData\\Local\\ABook\\Studio"}
        }
        function freshStatus(extra) {
            return Object.assign({installed: false, outdated: [], running: false, step: null, steps: [], progress: null, detail: "", error: null,
                                  gpu: {name: "NVIDIA GeForce RTX 3060", memory: 12 * 1073741824}, root: ""}, extra || {})
        }
        function readings() {
            return [{surface: "Nasdell", spokenForm: "hên-cơ", addedAt: 1, from: "Rokujouma"}, {surface: "Aiya", spokenForm: "a-i-a", addedAt: 2, from: ""}]
        }
        function init() {
            Theme.reduceMotion = false
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.saving = false
            Api.loaded = true
            Api.notice = ""
            Api.preferences = {theme: "system", bookTemplates: templates()}
            Api.info = {version: "0.4.40", studio: {installed: true}}
            store = {status: installedStatus(), entries: readings(), prefs: {bookTemplates: templates()}}
            DesktopApi.responses = {
                "GET /api/studio/setup": function() { return {status: 200, data: store.status} },
                "POST /api/studio/setup": function() { store.status = freshStatus({running: true, step: "runtime"}); return {status: 200, data: store.status} },
                "DELETE /api/studio/setup": function() { store.status = freshStatus(); return {status: 200, data: store.status} },
                "GET /api/voices": {status: 200, data: [{name: "Mai", gender: "nữ", region: "Bắc"}, {name: "Nam", gender: "nam", region: "Nam"}]},
                "GET /api/readings": function() { return {status: 200, data: {entries: store.entries}} },
                "POST /api/readings": function(body) {
                    if (body.remove) store.entries = store.entries.filter(e => e.surface !== body.surface)
                    else store.entries = store.entries.concat([{surface: body.surface, spokenForm: body.spokenForm, addedAt: 3, from: ""}])
                    return {status: 200, data: {}}
                },
                "POST /api/book-templates": function(body) {
                    let list = store.prefs.bookTemplates.slice()
                    if (body.op === "rename") {
                        const i = list.findIndex(t => t.name === body.from)
                        if (i < 0) return {status: 404, data: {message: "Mẫu vừa bị xoá ở máy khác"}}
                        list[i] = Object.assign({}, list[i], {name: body.to})
                    } else if (body.op === "delete") list = list.filter(t => t.name !== body.name)
                    else if (body.op === "restore") list.splice(body.index, 0, body.template)
                    store.prefs = {bookTemplates: list}
                    return {status: 200, data: store.prefs}
                }
            }
            wantsStudio.target = null
            wantsStudio.clear()
            Nav.layers = []
        }
        function cleanup() { DesktopApi.delayed = false; Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto" }

        function make(props) {
            const page = createTemporaryObject(studioFactory, host, Object.assign({width: 760}, props || {}))
            verify(page !== null)
            wantsStudio.target = page
            host.Window.window.update(); waitForRendering(page)
            return page
        }
        function all(item, name, out) {
            out = out || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children || []) all(child, name, out)
            return out
        }
        // Các phần tử đang thấy (Collapse đã mở) - hàng mẫu nào cũng có ô đổi tên nhưng chỉ hàng đang sửa là thấy
        function live(page, name) { return all(page, name).filter(i => i.visible) }
        function theOne(page, name) { tryVerify(function() { return live(page, name).length === 1 }, 3000, name); return live(page, name)[0] }
        function one(page, name) { const found = all(page, name); verify(found.length > 0, "thiếu " + name); return found[0] }
        function texts(item, out) {
            out = out || []
            if (item.text !== undefined && item.visible !== false) out.push(String(item.text))
            for (const child of item.children || []) texts(child, out)
            return out
        }
        function has(page, value) { tryVerify(function() { return texts(page).some(t => t.includes(value)) }); return texts(page).some(t => t.includes(value)) }
        function last() { return DesktopApi.requests[DesktopApi.requests.length - 1] }
        function requestsOf(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }

        // ---------- ô chọn ----------
        function test_narratorAndProfileSelects() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const page = make()
            const narrator = one(page, "newBookNarrator")
            compare(narrator.options.length, 3)
            compare(narrator.options[0].label, "Máy đề xuất")
            compare(narrator.options[1].label, "Mai · nữ, miền Bắc")
            narrator.picked("Mai")
            compare(last().method, "PUT")
            compare(last().path, "/api/preferences")
            compare(last().body.newBookNarrator, "Mai")
            compare(narrator.currentLabel, "Mai · nữ, miền Bắc")
            const profile = one(page, "newBookProfile")
            compare(profile.options.map(o => o.label).join("|"), "Chất lượng cao|Cân bằng|Nhanh")
            compare(profile.currentLabel, "Chất lượng cao")
            profile.picked("fast")
            compare(last().body.newBookProfile, "fast")
            compare(profile.currentLabel, "Nhanh")
        }
        function test_batterySwitch() {
            const page = make()
            const sw = one(page, "pauseOnBattery")
            compare(sw.checked, true)
            sw.toggled(false)
            compare(last().body.pauseOnBattery, false)
            compare(sw.checked, false)
            verify(has(page, "Tạm dừng dùng pin"))
            verify(has(page, "Cắm sạc lại thì tự làm tiếp đúng chỗ."))
        }

        // ---------- Studio ----------
        function test_installedRowAndUninstallConfirm() {
            const page = make()
            verify(has(page, "Đã cài · NVIDIA GeForce RTX 3060"))
            verify(has(page, "C:\\Users\\Linh\\AppData\\Local\\ABook\\Studio"))
            const remove = one(page, "studioRemove")
            compare(remove.text, "Gỡ Studio")
            remove.clicked()
            compare(remove.text, "Xác nhận gỡ")
            compare(remove.kind, "danger")
            compare(Nav.layers.length, 1)
            tryVerify(function() { return texts(page).some(t => t.includes("Xoá runtime")) })
            verify(has(page, "Xoá runtime/model (15–20 GB), giữ sách và hồ sơ; cuốn đang làm phải làm lại sau khi cài."))
            compare(requestsOf("DELETE", "/api/studio/setup").length, 0)
            // Back huỷ lần hỏi lại, không gỡ
            verify(Nav.back())
            compare(remove.text, "Gỡ Studio")
            compare(Nav.layers.length, 0)
            compare(requestsOf("DELETE", "/api/studio/setup").length, 0)
            // Bấm hai lần mới gỡ
            remove.clicked()
            remove.clicked()
            compare(requestsOf("DELETE", "/api/studio/setup").length, 1)
            compare(Api.notice, "Đã gỡ Studio")
            compare(Nav.layers.length, 0)
            tryCompare(one(page, "studioState"), "text", "Chưa cài.")
        }
        function test_uninstallFailureAndBusy() {
            const page = make()
            DesktopApi.responses["DELETE /api/studio/setup"] = {status: 409, data: {message: "Đang làm cuốn \"A\" - dừng cuốn ấy trước khi gỡ Studio"}}
            const remove = one(page, "studioRemove")
            remove.clicked(); remove.clicked()
            compare(Api.notice, "Chưa gỡ được Studio\nĐang làm cuốn \"A\" - dừng cuốn ấy trước khi gỡ Studio")
            compare(remove.text, "Gỡ Studio")
        }
        function test_outdatedAndDamagedLine() {
            store.status = Object.assign(installedStatus(), {outdated: ["Ollama", "Giọng"], damaged: ["Ollama"]})
            const page = make()
            verify(has(page, "Mất Ollama (file đã bị xoá hay hỏng) - "))
            const link = one(page, "studioFixLink")
            compare(findText(link, "Sửa Studio").text, "Sửa Studio")
            link.clicked()
            compare(wantsStudio.count, 1)
            store.status = Object.assign(installedStatus(), {outdated: ["Giọng"]})
            const again = make()
            verify(has(again, "Cần cập nhật Giọng - "))
            verify(findText(one(again, "studioFixLink"), "Cập nhật Studio") !== null)
        }
        function test_notInstalledInstall() {
            Api.info = {version: "0.4.40", studio: {installed: false}}
            store.status = freshStatus()
            const page = make()
            compare(one(page, "studioState").text, "Chưa cài.")
            verify(has(page, "NVIDIA từ 8 GB · tải ~25 GB · trống 35 GB · ~7–10 phút/chương."))
            verify(has(page, "Card NVIDIA GeForce RTX 3060 (12 GB): đủ để làm sách nói (đã thử trên card 8 GB)."))
            verify(has(page, "Tuỳ chọn ở trang này dùng khi đã cài Studio."))
            const install = one(page, "studioInstall")
            compare(install.text, "Cài Studio")
            compare(install.kind, "primary")
            install.clicked()
            compare(requestsOf("POST", "/api/studio/setup").length, 1)
            compare(wantsStudio.count, 1)
            compare(one(page, "studioState").text, "Đang cài.")
            compare(install.text, "Xem tiến độ cài")
            install.clicked()
            compare(wantsStudio.count, 2)
        }
        function test_notInstalledWithoutGpuOffersStillInstall() {
            Api.info = {version: "0.4.40", studio: {installed: false}}
            store.status = freshStatus({gpu: null})
            const page = make()
            verify(has(page, "Máy này không làm sách nói được (không có card đồ hoạ NVIDIA, hay driver NVIDIA chưa cài). Bạn vẫn nghe ngay mọi sách."))
            const install = one(page, "studioInstall")
            compare(install.text, "Vẫn cài")
            compare(install.size, "sm")
            store.status = freshStatus({gpu: {name: "GTX 1060", memory: 6 * 1073741824}})
            const maybe = make()
            verify(has(maybe, "Card GTX 1060 (6 GB): có thể chạy được nhưng chưa thử trên card dưới 8 GB, có thể chậm."))
            compare(one(maybe, "studioInstall").text, "Cài Studio")
            store.status = freshStatus({gpu: {name: "GT 710", memory: 2 * 1073741824}})
            const low = make()
            verify(has(low, "Máy này không làm sách nói được (card GT 710 (2 GB) ít bộ nhớ hơn mức tối thiểu 6 GB). Bạn vẫn nghe ngay mọi sách."))
        }
        function test_installFailureKeepsButton() {
            Api.info = {version: "0.4.40", studio: {installed: false}}
            store.status = freshStatus()
            DesktopApi.responses["POST /api/studio/setup"] = {status: 500, data: {message: "Hết chỗ"}}
            const page = make()
            one(page, "studioInstall").clicked()
            compare(Api.notice, "Chưa cài được Studio\nHết chỗ")
            compare(wantsStudio.count, 0)
            compare(one(page, "studioInstall").text, "Cài Studio")
        }

        // ---------- mẫu sách mới ----------
        function test_templateRowsAndSummary() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const page = make()
            verify(has(page, "Mẫu sách mới"))
            verify(has(page, "Ở Tạo sách, chọn “Lưu thành mẫu…” để dùng lại."))
            verify(has(page, "Mai · Chất lượng cao · bắt đầu ngay"))
            verify(has(page, "Giọng máy đề xuất · Nhanh · chờ bấm bắt đầu · chờ bạn duyệt trước khi thu"))
            compare(all(page, "renameTemplate").length, 3)
        }
        function test_emptyTemplates() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            Api.preferences = {theme: "system", bookTemplates: []}
            const page = make()
            verify(has(page, "Chưa có mẫu nào."))
            compare(all(page, "renameTemplate").length, 0)
        }
        function test_renameKeepsOtherDrafts() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            Platform.setSetting("fold.settings.studio.shared-readings", "1")
            const page = make()
            const surface = one(page, "readingSurface")
            surface.text = "Dở dang"
            const rows = all(page, "renameTemplate")
            rows[1].clicked()
            compare(Nav.layers.length, 1)
            const field = theOne(page, "renameField")
            compare(field.text, "Nhanh gọn")
            compare(all(page, "renameTemplate").length, 3)
            field.text = "Đêm khuya"
            theOne(page, "saveRename").clicked()
            // Trùng tên: không gửi, nói lý do, giữ ô nhập
            compare(requestsOf("POST", "/api/book-templates").length, 0)
            tryCompare(theOne(page, "renameProblem"), "text", "Đã có mẫu tên “Đêm khuya”")
            field.text = "  Buổi   sáng  "
            compare(live(page, "renameProblem")[0].text, "")
            theOne(page, "saveRename").clicked()
            const call = last()
            compare(call.path, "/api/book-templates")
            compare(call.body.op, "rename")
            compare(call.body.from, "Nhanh gọn")
            compare(call.body.to, "  Buổi   sáng  ")
            compare(Nav.layers.length, 0)
            tryVerify(function() { return has(page, "Buổi   sáng") || has(page, "Buổi sáng") })
            // Các phần khác không bị dựng lại: ô nhập cách đọc còn nguyên chữ đang gõ, ba hàng mẫu vẫn còn
            compare(one(page, "readingSurface").text, "Dở dang")
            tryVerify(function() { return all(page, "renameTemplate").length === 3 })
            verify(has(page, "Đêm khuya"))
            verify(has(page, "Cân bằng · bắt đầu ngay") || has(page, "Nam · Cân bằng · bắt đầu ngay"))
        }
        function test_renameBackAndEscape() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const page = make()
            all(page, "renameTemplate")[0].clicked()
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            compare(Nav.layers.length, 0)
            compare(requestsOf("POST", "/api/book-templates").length, 0)
            all(page, "renameTemplate")[0].clicked()
            theOne(page, "cancelRename").clicked()
            compare(Nav.layers.length, 0)
            // Tên rỗng và tên "Mặc định"
            all(page, "renameTemplate")[0].clicked()
            const field = theOne(page, "renameField")
            field.text = "mặc định"
            theOne(page, "saveRename").clicked()
            compare(theOne(page, "renameProblem").text, "“Mặc định” là mẫu có sẵn của app - chọn tên khác")
            verify(Nav.back())
        }
        function test_renameStaleTemplateClosesBox() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const page = make()
            all(page, "renameTemplate")[0].clicked()
            store.prefs = {bookTemplates: store.prefs.bookTemplates.slice(1)}
            theOne(page, "renameField").text = "Tên khác"
            theOne(page, "saveRename").clicked()
            compare(Api.notice, "Mẫu vừa bị xoá ở máy khác")
            compare(Nav.layers.length, 0)
        }
        function test_deleteAndUndo() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const page = make()
            all(page, "deleteTemplate")[1].clicked()
            compare(last().body.op, "delete")
            compare(last().body.name, "Nhanh gọn")
            compare(Api.notice, "Đã xoá mẫu “Nhanh gọn”")
            tryVerify(function() { return all(page, "renameTemplate").length === 2 })
            // "Hoàn tác" là nút của lời báo (toast của web), sống 10 giây
            compare(Api.noticeAction.label, "Hoàn tác")
            compare(Api.noticeDuration, 10000)
            Api.runNoticeAction()
            compare(Api.notice, "")
            compare(last().body.op, "restore")
            compare(last().body.index, 1)
            compare(last().body.template.name, "Nhanh gọn")
            tryVerify(function() { return all(page, "renameTemplate").length === 3 })
        }
        function test_longTemplateNameWraps() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            const spaced = "Mẫu có cái tên dài dài dài dài dài dài dài dài dài dài dài dài dài dài dài dài rất dài"
            const unbroken = "Tênkhôngcóchỗngắtrấtrấtrấtrấtrấtrấtrấtrấtrấtdài"
            Api.preferences = {theme: "system", bookTemplates: [{name: spaced, narrator: "", profile: "balanced", analysisModel: "", startNow: true, precastWait: false},
                                                                {name: unbroken, narrator: "", profile: "fast", analysisModel: "", startNow: true, precastWait: false}]}
            const page = make({width: 420})
            for (const name of [spaced, unbroken]) {
                const label = findText(page, name)
                verify(label !== null, name)
                verify(label.contentWidth <= label.width + 1, "tràn ngang: " + name)
                verify(label.contentHeight > label.font.pixelSize * 1.5, "không xuống dòng: " + name)
                compare(label.text, name)
            }
        }
        function findText(item, value) {
            if (item.text === value && item.contentWidth !== undefined) return item
            for (const child of item.children || []) { const found = findText(child, value); if (found) return found }
            return null
        }

        // ---------- cách đọc chung ----------
        function test_sharedReadingsAddRemove() {
            Platform.setSetting("fold.settings.studio.shared-readings", "1")
            const page = make()
            verify(has(page, "Sửa cách đọc một tên một lần, sách mới tự dùng."))
            compare(all(page, "removeReading").length, 2)
            verify(has(page, "Hên-cơ"))
            verify(has(page, " · từ Rokujouma"))
            const add = one(page, "addReading")
            compare(add.enabled, false)
            one(page, "readingSurface").text = "  Eris "
            one(page, "readingSpoken").text = "ê-rít"
            compare(add.enabled, true)
            add.activated()
            const post = requestsOf("POST", "/api/readings")[0]
            compare(post.body.surface, "Eris")
            compare(post.body.spokenForm, "ê-rít")
            compare(Api.notice, "“Eris” đọc là “Ê-rít” cho mọi sách")
            compare(one(page, "readingSurface").text, "")
            tryVerify(function() { return all(page, "removeReading").length === 3 })
            const rows = all(page, "removeReading")
            compare(rows[0].tip, "Bỏ “Nasdell” khỏi cách đọc chung")
            rows[0].clicked()
            const removal = requestsOf("POST", "/api/readings")[1]
            compare(removal.body.surface, "Nasdell")
            compare(removal.body.remove, true)
            compare(Api.notice, "Đã bỏ “Nasdell” khỏi cách đọc chung")
            tryVerify(function() { return all(page, "removeReading").length === 2 })
        }
        function test_sharedReadingsErrorAndSearch() {
            Platform.setSetting("fold.settings.studio.shared-readings", "1")
            store.entries = []
            for (let i = 0; i < 10; ++i) store.entries.push({surface: "Tên" + i, spokenForm: "tên " + i, addedAt: i, from: ""})
            const page = make()
            verify(has(page, "Tìm tên…") || all(page, "readingsFilter").length === 1)
            one(page, "readingsFilter").text = "Tên7"
            tryVerify(function() { return all(page, "removeReading").length === 1 })
            DesktopApi.responses["POST /api/readings"] = {status: 400, data: {message: "Từ này đã có"}}
            one(page, "readingSurface").text = "A"
            one(page, "readingSpoken").text = "b"
            one(page, "addReading").activated()
            tryCompare(one(page, "readingsProblem"), "text", "Từ này đã có")
        }

        // ---------- ảnh ----------
        function shot(name, item) {
            const target = item || host
            target.Window.window.update()
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            qtGlyphAudit.scan()
            const img = grabImage(VisualReady.grabTarget(host.Window.window, target))
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }
        function openAll() {
            Platform.setSetting("fold.settings.studio.new-book", "1")
            Platform.setSetting("fold.settings.studio.shared-readings", "1")
        }
        function test_shots() {
            openAll()
            both(function() {
                let page = make({width: 820, height: 1400})
                shot("settings_studio_installed", page)
                one(page, "studioRemove").clicked()
                shot("settings_studio_confirm", page)
                Nav.back()
                all(page, "renameTemplate")[1].clicked()
                theOne(page, "renameField").text = "Đêm khuya"
                theOne(page, "saveRename").clicked()
                shot("settings_studio_rename", page)
                Nav.back()
                page.destroy()

                store.status = Object.assign(installedStatus(), {outdated: ["Ollama"], damaged: ["Ollama"]})
                page = make({width: 820, height: 1400})
                shot("settings_studio_damaged", page)
                page.destroy()

                Api.info = {version: "0.4.40", studio: {installed: false}}
                store.status = freshStatus()
                page = make({width: 820, height: 1400})
                shot("settings_studio_not_installed", page)
                page.destroy()

                store.status = freshStatus({gpu: null})
                page = make({width: 820, height: 1400})
                shot("settings_studio_no_gpu", page)
                page.destroy()

                store.status = freshStatus({running: true, step: "runtime"})
                page = make({width: 820, height: 1400})
                shot("settings_studio_installing", page)
                page.destroy()

                Api.info = {version: "0.4.40", studio: {installed: true}}
                store.status = installedStatus()
                const longName = "Mẫu có cái tên dài dài dài dài dài dài dài dài dài dài dài dài dài dài rất rất dài"
                Api.preferences = {theme: "system", bookTemplates: [{name: longName, narrator: "Mai", profile: "balanced", analysisModel: "", startNow: true, precastWait: true}]}
                page = make({width: 420, height: 1900})
                shot("settings_studio_narrow", page)
                page.destroy()
                Api.preferences = {theme: "system", bookTemplates: templates()}
            })
        }
    }
}
