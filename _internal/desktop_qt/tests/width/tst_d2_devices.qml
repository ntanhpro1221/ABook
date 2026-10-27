import QtQuick
import QtTest
import ABook

// Cài đặt › Thiết bị (SettingsDevices = PhoneSync + OtherComputers): hành vi (bật tắt kết nối, ghép bằng mã, đổi tên, thôi ghép, máy tính khác,
// tên dài xuống dòng, Back đối xứng) và ảnh sáng + tối ghi ra build/d2shots/settings_devices_*.png. Máy chủ giả đặt vào DesktopApi giả.
Item {
    id: host
    width: 1100
    height: 1700
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: devicesFactory; SettingsDevices {} }

    TestCase {
        id: test
        name: "D2Devices"
        when: windowShown

        property var server: ({})
        readonly property real nowSeconds: Date.now() / 1000

        function baseSync(over) {
            return Object.assign({
                enabled: true, wanted: true, error: "", name: "NGDtuanh-PC", port: 47630,
                addresses: ["192.168.1.20", "100.101.102.103"], awayAddresses: ["100.101.102.103"],
                pairing: null, pairingBlocked: false,
                fingerprint: "AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12",
                devices: [
                    {id: "aa11", name: "Google Pixel 8", pairedAt: nowSeconds - 86400 * 20, lastSeen: nowSeconds - 120, studio: false},
                    {id: "bb22", name: "Samsung Galaxy Tab S9 của phòng khách nhà bác Tuấn", pairedAt: nowSeconds - 86400 * 3, lastSeen: nowSeconds - 7200, studio: true}],
                remoteStudio: true,
                bluetooth: {running: true, channel: 4, error: "", connections: 1}
            }, over || {})
        }
        function computer(over) {
            return Object.assign({id: "c0ffee000001", name: "Máy bàn phòng làm việc", host: "192.168.1.40", port: 47630, connectedVia: "192.168.1.40:47630",
                lastSeen: nowSeconds - 30, fingerprint: "11AA22BB33CC44DD55EE66FF77889900", kind: "computer"}, over || {})
        }
        // Máy chủ giả: giữ trạng thái, đáp đúng hình dạng của webui/server.py
        function install(sync, computers) {
            server = {sync: sync, computers: computers || [], unsent: {books: [], changes: 0, sendable: true}, bluetooth: [{name: "Tai nghe của bạn", address: "AA:BB:CC:DD:EE:01", kind: "phone"}]}
            DesktopApi.responses = {
                "GET /api/sync": function() { return {status: 200, data: server.sync} },
                "POST /api/sync": function(body) { server.sync = Object.assign({}, server.sync, {enabled: body.enabled, wanted: body.enabled, devices: body.enabled ? server.sync.devices : []}); return {status: 200, data: server.sync} },
                "POST /api/sync/pairing": function() { server.sync = Object.assign({}, server.sync, {pairing: {code: "483920", expiresAt: nowSeconds + 300}}); return {status: 200, data: server.sync} },
                "DELETE /api/sync/pairing": function() { server.sync = Object.assign({}, server.sync, {pairing: null}); return {status: 200, data: server.sync} },
                "POST /api/sync/studio": function(body) { server.sync = Object.assign({}, server.sync, {remoteStudio: body.enabled}); return {status: 200, data: server.sync} },
                "DELETE /api/sync/devices/aa11": function() { server.sync = Object.assign({}, server.sync, {devices: server.sync.devices.filter(d => d.id !== "aa11")}); return {status: 200, data: server.sync} },
                "POST /api/sync/devices/aa11/name": function(body) { server.sync = Object.assign({}, server.sync, {devices: server.sync.devices.map(d => d.id === "aa11" ? Object.assign({}, d, {name: body.name}) : d)}); return {status: 200, data: server.sync} },
                "POST /api/sync/devices/bb22/studio": function(body) { server.sync = Object.assign({}, server.sync, {devices: server.sync.devices.map(d => d.id === "bb22" ? Object.assign({}, d, {studio: body.enabled}) : d)}); return {status: 200, data: server.sync} },
                "GET /api/computers": function() { return {status: 200, data: {name: "NGDtuanh-PC", computers: server.computers}} },
                "GET /api/computers/bluetooth": function() { return {status: 200, data: {devices: server.bluetooth}} },
                "POST /api/computers": function(body) { server.computers = server.computers.concat([computer({id: "c0ffee000002", name: "Laptop của bạn", host: body.address})]); return {status: 200, data: {name: "NGDtuanh-PC", computers: server.computers}} },
                "GET /api/computers/c0ffee000001/unsent": function() { return {status: 200, data: server.unsent} },
                "DELETE /api/computers/c0ffee000001": function() { server.computers = server.computers.filter(c => c.id !== "c0ffee000001"); return {status: 200, data: {name: "NGDtuanh-PC", computers: server.computers}} },
                "DELETE /api/computers/c0ffee000001?edits=discard": function() { server.computers = server.computers.filter(c => c.id !== "c0ffee000001"); return {status: 200, data: {name: "NGDtuanh-PC", computers: server.computers}} },
                "GET /api/computers/discover": function() { return {status: 200, data: {found: [{name: "Phòng ngủ", host: "192.168.1.55", port: 47630, paired: false, kind: "phone"}, {name: "Máy bàn phòng làm việc", host: "192.168.1.40", port: 47630, paired: true, kind: "computer"}]}} },
                "POST /api/computers/c0ffee000001/bluetooth": function(body) { server.computers = server.computers.map(c => Object.assign({}, c, {bt: body.address})); return {status: 200, data: {name: "NGDtuanh-PC", computers: server.computers}} },
                "GET /api/remote/c0ffee000003/diagnostics?lines=400": function() { return {status: 200, data: {app: {versionName: "0.4.147", versionCode: 4147}, device: {manufacturer: "Google", model: "Pixel 8", release: "15", sdk: 35}, battery: {percent: 64, charging: true}, network: {connected: true, wifi: true, validated: true}, storage: {freeBytes: 21474836480, totalBytes: 128849018880}, log: ["12:00:01 mở thư viện", "12:00:05 đồng bộ xong"], logcat: []}} }
            }
        }
        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "0.4.147"}
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
            Theme.reduceMotion = true
        }
        function cleanup() { Theme.mode = "auto"; Theme.reduceMotion = false; Nav.layers = []; DesktopApi.delayed = false }

        function make(over) {
            const item = createTemporaryObject(devicesFactory, host, Object.assign({x: 100, width: 888}, over || {}))
            verify(item !== null)
            wait(50)
            return item
        }
        function walk(item, visit) {
            if (visit(item) === true) return item
            for (const child of item.children || []) { const hit = walk(child, visit); if (hit) return hit }
            return null
        }
        function byName(root, name) { return walk(root, i => i.objectName === name) }
        function byText(root, value) { return walk(root, i => (i.text === value || i.label === value || i.title === value) && i.visible !== false) }
        function texts(root) {
            const out = []
            walk(root, i => { if (i.visible !== false && i.text !== undefined && String(i.text) !== "") out.push(String(i.text)); return false })
            return out
        }
        function shown(root, value) {
            let found = false
            walk(root, i => { if (i.text === value) { let ok = true; for (let n = i; n; n = n.parent) if (n.visible === false || (n.height === 0 && n !== i)) { ok = false; break } if (ok) found = true } return false })
            return found
        }
        function window() { return host.Window.window.contentItem }
        function request(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function shot(name, item) {
            const target = item || host
            target.Window.window.update()
            waitForRendering(target)
            wait(300)
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }

        // ---- hành vi ----
        function test_syncOffBody() {
            install(baseSync({enabled: false, wanted: false, devices: [], addresses: [], awayAddresses: [], bluetooth: null, fingerprint: ""}), [])
            const page = make()
            verify(shown(page, "Máy này"))
            verify(shown(page, "Kết nối Wi-Fi"))
            verify(shown(page, "Đang tắt - máy khác không thấy máy này."))
            verify(!shown(page, "Máy đã ghép"))
            verify(!shown(page, "Ghép thiết bị"))
            verify(shown(page, "Máy tính khác"))
            const toggle = byName(page, "syncToggle")
            toggle.toggled(true)
            const post = request("POST", "/api/sync")
            compare(post.length, 1)
            compare(post[0].body.enabled, true)
            wait(50)
            verify(shown(page, "Máy đã ghép"))
            verify(shown(page, "Ghép thiết bị"))
            verify(shown(page, "Máy cùng mạng thấy máy này là “NGDtuanh-PC”."))
        }
        function test_syncOnThenOffAnnounces() {
            install(baseSync(), [])
            const page = make()
            verify(shown(page, "Máy đã ghép"))
            compare(shown(page, "Điện thoại, máy tính bảng"), true)
            byName(page, "syncToggle").toggled(false)
            compare(request("POST", "/api/sync")[0].body.enabled, false)
            compare(Api.notice, "Đã tắt chia sẻ qua Wi-Fi")
            wait(250)
            verify(!shown(page, "Máy đã ghép"))
        }
        function test_syncFailingShowsRetry() {
            install(baseSync({enabled: false, wanted: true, error: "Cổng 47630 đang bận.", devices: []}), [])
            const page = make()
            verify(shown(page, "Cổng 47630 đang bận."))
            verify(shown(page, "Thử lại"))
        }
        function test_pairingStartAndCancel() {
            install(baseSync(), [])
            Platform.setSetting("fold.phone-sync.pair", "1")
            const page = make()
            verify(shown(page, "Ghép thiết bị mới"))
            const idle = byText(page, "Ghép thiết bị mới")
            idle.activated()
            compare(request("POST", "/api/sync/pairing").length, 1)
            wait(80)
            const code = byName(page, "pairingCode")
            verify(code.visible)
            verify(texts(code).join("").indexOf("483") >= 0)
            verify(shown(page, "Mã ghép thiết bị"))
            verify(shown(page, "Trên máy kia: Cài đặt › Thiết bị › chọn NGDtuanh-PC › nhập mã."))
            verify(shown(page, "Đang hiện mã ghép"))
            verify(shown(page, "Hết hạn sau 5:00") || shown(page, "Hết hạn sau 4:59"))
            verify(shown(page, "Vân tay: AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12"))
            byText(page, "Huỷ mã này").clicked()
            compare(request("DELETE", "/api/sync/pairing").length, 1)
            wait(250)
            verify(!byName(page, "pairingCode").visible)
            verify(shown(page, "Ghép thiết bị mới"))
        }
        function test_pairingBlocked() {
            install(baseSync({pairingBlocked: true}), [])
            Platform.setSetting("fold.phone-sync.pair", "1")
            const page = make()
            verify(shown(page, "Mã bị khoá"))
            verify(shown(page, "Sai 5 lần; chỉ tạo mã mới khi bạn đang ghép thiết bị."))
            byText(page, "Tạo mã mới").activated()
            compare(request("POST", "/api/sync/pairing").length, 1)
        }
        function test_newDeviceIsAnnounced() {
            install(baseSync(), [])
            const page = make()
            server.sync = Object.assign({}, server.sync, {devices: server.sync.devices.concat([{id: "cc33", name: "iPad của mẹ", pairedAt: nowSeconds, lastSeen: nowSeconds}])})
            page.children[0].load()
            compare(Api.notice, "Đã ghép iPad của mẹ")
        }
        function test_remoteStudioNeedsConfirm() {
            install(baseSync({remoteStudio: false}), [])
            const page = make()
            const dialog = byName(window(), "studioDialog")
            byName(page, "studioToggle").toggled(true)
            verify(dialog.open)
            compare(Nav.layers.length, 1)
            compare(request("POST", "/api/sync/studio").length, 0)
            verify(Nav.back())
            verify(!dialog.open)
            compare(request("POST", "/api/sync/studio").length, 0)
            byName(page, "studioToggle").toggled(true)
            wait(250)
            byText(window(), "Cho phép").activated()
            compare(request("POST", "/api/sync/studio")[0].body.enabled, true)
            verify(!dialog.open)
            byName(page, "studioToggle").toggled(false)
            compare(request("POST", "/api/sync/studio")[1].body.enabled, false)
        }
        function test_renameKeepsOtherDrafts() {
            install(baseSync(), [computer()])
            const page = make()
            const address = byName(page, "addressField")
            address.text = "10.0.0.5"
            const rows = byName(page, "deviceList").children
            verify(rows.length >= 2)
            const phone = rows[0]
            phone.rename("aa11", "Google Pixel 8")
            const dialog = byName(window(), "renameDialog")
            verify(dialog.open)
            compare(Nav.layers.length, 1)
            const field = byName(window(), "renameField")
            compare(field.text, "Google Pixel 8")
            field.text = "Điện thoại của bạn"
            verify(Nav.back())
            verify(!dialog.open)
            compare(request("POST", "/api/sync/devices/aa11/name").length, 0)
            compare(address.text, "10.0.0.5")
            // mở lại: bản nháp cũ không dính sang, máy khác không đổi
            rows[1].rename("bb22", "Samsung Galaxy Tab S9 của phòng khách nhà bác Tuấn")
            compare(field.text, "Samsung Galaxy Tab S9 của phòng khách nhà bác Tuấn")
            verify(Nav.back())
            phone.rename("aa11", "Google Pixel 8")
            field.text = "Điện thoại của bạn"
            byName(window(), "renameSave").activated()
            const call = request("POST", "/api/sync/devices/aa11/name")
            compare(call.length, 1)
            compare(call[0].body.name, "Điện thoại của bạn")
            compare(Api.notice, "Đã đổi tên thành “Điện thoại của bạn”")
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
            compare(address.text, "10.0.0.5")
            wait(30)
            verify(shown(page, "Điện thoại của bạn"))
        }
        function test_renameClampsAndNeedsText() {
            install(baseSync(), [])
            const page = make()
            byName(page, "deviceList").children[0].rename("aa11", "Google Pixel 8")
            const field = byName(window(), "renameField")
            field.text = "x".repeat(120)
            compare(field.text.length, 80)
            field.text = "   "
            compare(byName(window(), "renameSave").enabled, false)
            Nav.back()
        }
        function test_unpairPhoneConfirmAndBack() {
            install(baseSync(), [])
            const page = make()
            const list = byName(page, "deviceList")
            list.children[0].remove("aa11", "Google Pixel 8")
            const dialog = byName(window(), "removeDialog")
            verify(dialog.open)
            compare(dialog.title, "Thôi ghép Google Pixel 8?")
            compare(dialog.description, "Dừng tải và đồng bộ; giữ sách đã tải.")
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!dialog.open)
            compare(request("DELETE", "/api/sync/devices/aa11").length, 0)
            list.children[0].remove("aa11", "Google Pixel 8")
            wait(250)
            byText(window(), "Để nguyên").clicked()
            verify(!dialog.open)
            list.children[0].remove("aa11", "Google Pixel 8")
            const confirm = walk(dialog, i => i.text === "Thôi ghép" && i.kind === "danger")
            verify(confirm !== null)
            confirm.clicked()
            compare(request("DELETE", "/api/sync/devices/aa11").length, 1)
            compare(Api.notice, "Đã thôi ghép Google Pixel 8")
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
            wait(400)
            compare(byName(page, "deviceList").children.length - 1 /* Repeater */, 1)
        }
        function test_emptyDevicesHint() {
            install(baseSync({devices: []}), [])
            const page = make()
            const note = byName(page, "noDevices")
            verify(note.height > 0)
            const plain = note.getText(0, note.length)
            compare(plain, "Chưa có thiết bị. App Android: file .apk ở github.com/ntanhpro1221/ABook/releases. iPhone, iPad: nghe bằng trình duyệt.")
        }
        function test_longNamesWrapAndStayInside() {
            const longName = "Máy tính bảng Samsung Galaxy Tab S9 Ultra của phòng khách nhà bác Tuấn ở tầng ba khu tập thể số 12"
            install(baseSync({name: longName, devices: [{id: "aa11", name: longName, pairedAt: nowSeconds - 100, lastSeen: nowSeconds - 100}]}), [])
            Platform.setSetting("fold.phone-sync.device.aa11", "1")
            const page = make({width: 520})
            const hits = []
            walk(page, i => { if (i.visible !== false && i.text === longName) hits.push(i); return false })
            verify(hits.length >= 2)
            for (const item of hits) {
                verify(item.height > 20)
                verify(item.contentWidth <= item.width + 1)
                verify(item.mapToItem(page, item.width, 0).x <= page.width + 1)
            }
        }
        function test_otherComputersPairAndForget() {
            install(baseSync(), [computer()])
            Platform.setSetting("fold.other-computers.pair", "1")
            const page = make()
            verify(shown(page, "Máy bàn phòng làm việc"))
            verify(shown(page, "Đã ghép"))
            verify(shown(page, "Ghép máy"))
            verify(shown(page, "Nghe sách của máy tính khác"))
            const address = byName(page, "addressField"), code = byName(page, "codeField"), connect = byName(page, "connectComputer")
            verify(shown(page, "Máy kia: Cài đặt › Thiết bị › bật “Kết nối Wi-Fi” để lấy mã; ghép một chiều để nghe thư viện của máy ấy."))
            compare(connect.enabled, false)
            address.text = "192.168.1.77"
            code.text = "12a3-45678"
            compare(code.text, "123456")
            compare(connect.enabled, true)
            connect.activated()
            const post = request("POST", "/api/computers")
            compare(post.length, 1)
            compare(post[0].body.address, "192.168.1.77")
            compare(post[0].body.code, "123456")
            compare(Api.notice, "Đã ghép Laptop của bạn")
            compare(address.text, "")
            compare(code.text, "")
            wait(60)
            verify(shown(page, "Laptop của bạn"))
            // quên máy: không còn gì để mất -> thôi ghép luôn + một câu
            Platform.setSetting("fold.other-computers.c0ffee000001", "1")
            const unpair = byName(page, "unpairComputer")
            unpair.clicked()
            compare(request("GET", "/api/computers/c0ffee000001/unsent").length, 1)
            compare(request("DELETE", "/api/computers/c0ffee000001").length, 1)
            compare(Api.notice, "Đã thôi ghép Máy bàn phòng làm việc")
            compare(Nav.layers.length, 0)
        }
        function test_otherComputersUnpairAsksAndBackReturns() {
            install(baseSync(), [computer({fingerprint: ""})])
            server.unsent = {books: [{title: "Rokujouma", changes: 3}], changes: 3, sendable: true, reachable: true, cache: {books: 2, bytes: 52428800, places: 1}}
            Platform.setSetting("fold.other-computers.c0ffee000001", "1")
            const page = make()
            byName(page, "unpairComputer").clicked()
            const dialog = byName(window(), "unpairDialog")
            verify(dialog.open)
            compare(dialog.title, "Thôi ghép Máy bàn phòng làm việc?")
            compare(Nav.layers.length, 1)
            wait(250)
            verify(shown(window(), "2 cuốn của Máy bàn phòng làm việc sẽ rời Thư viện, và 50 MB đã tải về máy tính này sẽ bị xoá."))
            wait(250)
            verify(shown(window(), "Gửi trước rồi thôi ghép"))
            verify(shown(window(), "Vẫn thôi ghép, bỏ thay đổi"))
            verify(Nav.back())
            verify(!dialog.open)
            compare(request("DELETE", "/api/computers/c0ffee000001").length, 0)
            byName(page, "unpairComputer").clicked()
            byName(window(), "unpairDiscard").activated()
            compare(request("DELETE", "/api/computers/c0ffee000001?edits=discard").length, 1)
            compare(Api.notice, "Đã thôi ghép Máy bàn phòng làm việc")
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
        }
        function test_discoverListsAndChoose() {
            install(baseSync(), [])
            Platform.setSetting("fold.other-computers.pair", "1")
            const page = make()
            byName(page, "discover").activated()
            wait(50)
            verify(shown(page, "Phòng ngủ"))
            verify(shown(page, "192.168.1.55:47630"))
            verify(shown(page, "Đã ghép"))
            byText(page, "Chọn").clicked()
            compare(byName(page, "addressField").text, "192.168.1.55:47630")
        }
        function test_bluetoothFallbackMenu() {
            install(baseSync(), [computer()])
            Platform.setSetting("fold.other-computers.c0ffee000001", "1")
            const page = make()
            const button = byName(page, "bluetoothButton")
            verify(button !== null)
            button.clicked()
            const menu = byName(window(), "bluetoothMenu")
            verify(menu.open)
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!menu.open)
        }
        function test_diagnosticsDialog() {
            install(baseSync(), [computer({id: "c0ffee000003", name: "Pixel 8", kind: "phone", host: "192.168.1.60"})])
            Platform.setSetting("fold.other-computers.c0ffee000003", "1")
            const page = make()
            byName(page, "diagnose").clicked()
            const dialog = byName(window(), "diagnostics")
            verify(dialog.open)
            compare(dialog.title, "Chẩn đoán Pixel 8")
            wait(50)
            verify(shown(dialog, "0.4.147 (4147)"))
            verify(shown(dialog, "Google Pixel 8 · Android 15 (API 35)"))
            verify(shown(dialog, "20 GB / 120 GB"))
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!dialog.open)
        }

        // ---- ảnh ----
        function test_shots() {
            both(function() {
                install(baseSync({enabled: false, wanted: false, devices: [], addresses: [], awayAddresses: [], bluetooth: null, fingerprint: ""}), [])
                Platform.reset()
                let page = make()
                shot("settings_devices_off")
                page.destroy()

                install(baseSync(), [computer(), computer({id: "c0ffee000003", name: "Pixel 8 của bạn", kind: "phone", host: "bt:AA:BB:CC:DD:EE:02", connectedVia: "bluetooth"})])
                Platform.reset()
                for (const key of ["phone-sync.pair", "phone-sync.permissions", "phone-sync.connection", "phone-sync.device.aa11", "phone-sync.device.bb22", "other-computers.pair", "other-computers.c0ffee000001", "other-computers.c0ffee000003"])
                    Platform.setSetting("fold." + key, "1")
                page = make()
                shot("settings_devices_on")
                page.destroy()

                install(baseSync({pairing: {code: "483920", expiresAt: nowSeconds + 247}}), [])
                Platform.reset()
                Platform.setSetting("fold.phone-sync.pair", "1")
                page = make()
                shot("settings_devices_pairing")
                page.destroy()

                install(baseSync({pairingBlocked: true}), [])
                Platform.reset()
                Platform.setSetting("fold.phone-sync.pair", "1")
                page = make()
                shot("settings_devices_blocked")
                page.destroy()

                install(baseSync({enabled: false, wanted: true, error: "Cổng 47630 đang bận.", devices: []}), [])
                Platform.reset()
                page = make()
                shot("settings_devices_failing")
                page.destroy()

                install(baseSync(), [computer({waking: {since: nowSeconds - 30, until: nowSeconds + 200, via: "wifi"}, kind: "phone", name: "Pixel 8 của bạn"}), computer({id: "c0ffee000009", name: "Laptop cũ", error: "Chứng chỉ của máy kia đã đổi: bạn hãy ghép lại máy này bằng mã mới.", connectedVia: ""})])
                Platform.reset()
                Platform.setSetting("fold.other-computers.c0ffee000001", "1")
                Platform.setSetting("fold.other-computers.c0ffee000009", "1")
                page = make()
                shot("settings_devices_computers_states")
                page.destroy()
            })
        }
        function test_shotsDialogs() {
            both(function() {
                install(baseSync(), [computer()])
                Platform.reset()
                for (const key of ["phone-sync.device.aa11", "phone-sync.device.bb22", "other-computers.c0ffee000001"]) Platform.setSetting("fold." + key, "1")
                let page = make()
                byName(page, "deviceList").children[0].remove("aa11", "Google Pixel 8")
                shot("settings_devices_confirm_unpair", window())
                Nav.back()
                byName(page, "deviceList").children[1].rename("bb22", "Samsung Galaxy Tab S9 của phòng khách nhà bác Tuấn")
                shot("settings_devices_rename", window())
                Nav.back()
                install(baseSync({remoteStudio: false}), [computer()])
                byName(page, "studioToggle").toggled(true)
                shot("settings_devices_confirm_studio", window())
                Nav.back()
                server.unsent = {books: [{title: "Rokujouma", changes: 3}, {title: "Tên cuốn thứ hai", changes: 1}], changes: 4, sendable: true, reachable: false, cache: {books: 2, bytes: 52428800, places: 1}}
                byName(page, "unpairComputer").clicked()
                shot("settings_devices_confirm_unpair_computer", window())
                Nav.back()
                page.destroy()

                install(baseSync(), [computer({id: "c0ffee000003", name: "Pixel 8", kind: "phone", host: "192.168.1.60"})])
                Platform.reset()
                Platform.setSetting("fold.other-computers.c0ffee000003", "1")
                page = make()
                byName(page, "diagnose").clicked()
                wait(100)
                shot("settings_devices_diagnostics", window())
                Nav.back()
                byName(page, "bluetoothButton").clicked()
                shot("settings_devices_bluetooth_menu", window())
                Nav.back()
                page.destroy()
            })
        }
    }
}
