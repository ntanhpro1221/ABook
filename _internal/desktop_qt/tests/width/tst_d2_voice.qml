import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Cài đặt › Giọng đọc (SettingsVoice + VoiceModule + ProviderKey): việc làm thật (yêu cầu gửi đi, giọng mặc định, nghe thử, khoá, tải / huỷ / gỡ có hỏi, Back từ hộp hỏi,
// tên giọng dài xuống dòng) + ảnh offscreen sáng / tối ghi ra build/d2shots/settings_voice_*.png. Máy chủ giả: DesktopApi giả (tests/qml/stub/ABook/DesktopApi.qml).
Item {
    id: host
    width: 1000
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: voiceFactory; SettingsVoice {} }
    Component { id: screenFactory; SettingsScreen {} }

    property var voices: []
    property var providers: []
    property var vieneu: ({})
    property var supertonic: ({})
    property var speed: ({})
    property var use: ({})
    property var checked: ({ok: true, voices: 3, provider: {voices: 3}})

    function fixtureVoices() {
        return [
            {id: "edge:vi-VN-HoaiMyNeural", name: "Hoài My (Edge)", provider: "edge", gender: "female", online: true, default: true},
            {id: "edge:vi-VN-NamMinhNeural", name: "Nam Minh (Edge)", provider: "edge", gender: "male", online: true},
            {id: "azure:vi-VN-HoaiMyNeural", name: "Hoài My (Azure Speech)", provider: "azure", gender: "female", online: true},
            {id: "vieneu:turbo/Phạm Tuyên", name: "Phạm Tuyên (VieNeu Turbo)", provider: "vieneu", gender: "male", online: false},
            {id: "vieneu:turbo/Ngọc Linh", name: "Ngọc Linh (VieNeu Turbo)", provider: "vieneu", gender: "female", online: false},
            {id: "vieneu:nano/Ái Hân", name: "Ái Hân (VieNeu Nano)", provider: "vieneu", gender: "female", online: false},
            {id: "vieneu:nano/Đức Trí", name: "Đức Trí (VieNeu Nano)", provider: "vieneu", gender: "male", online: false},
            {id: "device:An", name: "Microsoft An (vi-VN)", provider: "device", gender: "male", online: false}
        ]
    }
    function fixtureProviders() {
        return [
            {id: "azure", name: "Azure Speech", limits: {max_chars: 5000, free: "Miễn phí 500.000 ký tự mỗi tháng", timings: "exact", region: true}, hasKey: true, masked: "••••abcd", region: "southeastasia", valid: true, voices: 3},
            {id: "google", name: "Google Cloud", limits: {max_chars: 5000, free: "Miễn phí 1 triệu ký tự mỗi tháng", timings: "estimated", region: false}, hasKey: false, masked: "", region: "", valid: false, voices: 0},
            {id: "fpt", name: "FPT.AI", limits: {max_chars: 1000, free: "Miễn phí 100.000 ký tự mỗi tháng", timings: "estimated", region: false}, hasKey: true, masked: "••••9f2e", region: "", valid: false, voices: 0},
            {id: "viettel", name: "Viettel AI", limits: {max_chars: 1000, free: "Có gói miễn phí", timings: "estimated", region: false}, hasKey: false, masked: "", region: "", valid: false, voices: 0}
        ]
    }
    function fixtureVieneu() {
        return {
            state: "ready", done: 0, total: 0, error: "", supported: true, reason: "", outdatedParts: [], outdatedBytes: 0, benchmarking: false, suggestion: null, restart: false,
            recommended: "turbo", slowRtf: 0.8, device: {cores: 8, ramGb: 16, gpu: "", runs: "cpu"},
            choices: [
                {id: "turbo", label: "Giọng VieNeu Turbo", detail: "Giọng hay, đọc ngay trên máy.", needs: ["lib", "turbo"], bytes: 0, installed: true, recommended: true, default: true, removable: true},
                {id: "nano", label: "Giọng VieNeu Nano", detail: "Nhẹ hơn, hợp máy yếu.", needs: ["lib", "nano"], bytes: 296000000, installed: false, recommended: false, default: false, removable: false},
                {id: "aligner", label: "Tô đúng từng chữ", detail: "Tô sáng từng chữ đang đọc, đúng với tiếng.", needs: ["aligner"], bytes: 0, installed: true, recommended: false, default: true, removable: false},
                {id: "fast", label: "Bản tăng tốc", detail: "Đọc nhanh hơn trên máy có AVX2.", needs: ["fast"], bytes: 0, installed: true, recommended: false, default: false, removable: true, requires: ["turbo"]}
            ],
            parts: [{id: "lib", label: "Thư viện", bytes: 120000000, state: "current"}, {id: "turbo", label: "Turbo", bytes: 300000000, state: "current"}, {id: "nano", label: "Nano", bytes: 176000000, state: "missing"}, {id: "aligner", label: "Căn chữ", bytes: 30000000, state: "current"}, {id: "fast", label: "Tăng tốc", bytes: 20000000, state: "current"}],
            benchmark: {turbo: {rtf: 0.35, firstAudioMs: 900}},
            accelerated: {on: true, active: true, problem: ""}
        }
    }
    function fixtureSupertonic() {
        return {
            state: "downloading", done: 120000000, total: 228000000, error: "", supported: true, reason: "", outdatedParts: [], outdatedBytes: 0, benchmarking: false, suggestion: null, restart: false,
            recommended: "supertonic", device: {cores: 8, ramGb: 16, gpu: "", runs: "cpu"},
            choices: [{id: "supertonic", label: "Giọng Supertonic", detail: "Mười giọng nam nữ, nhẹ máy.", needs: ["st"], bytes: 228000000, installed: false, recommended: true, default: true, removable: true}],
            parts: [{id: "st", label: "Supertonic", bytes: 228000000, state: "missing"}],
            benchmark: {}
        }
    }
    function fixtureSpeed() {
        return {choice: "auto", voices: [{id: "supertonic", name: "Giọng Supertonic", module: "supertonic", fastChoice: "supertonic_fast", rtf: 0.9, tier: "fast", using: "quality", fastBytes: 65000000}]}
    }
    function install() {
        DesktopApi.reset()
        Platform.reset()
        voices = fixtureVoices(); providers = fixtureProviders(); vieneu = fixtureVieneu(); supertonic = fixtureSupertonic(); speed = fixtureSpeed()
        use = {bookCount: 2, peopleCount: 5, left: 40, books: [{title: "Rokujouma", people: [], left: 40}, {title: "Sách thứ hai", people: [], left: 0}]}
        DesktopApi.responses = {
            "GET /api/readaloud/voices": function() { return {status: 200, data: host.voices} },
            "GET /api/readaloud/online": function() { return {status: 200, data: host.providers} },
            "GET /api/readaloud/vieneu": function() { return {status: 200, data: host.vieneu} },
            "GET /api/readaloud/supertonic": function() { return {status: 200, data: host.supertonic} },
            "GET /api/readaloud/voice-speed": function() { return {status: 200, data: host.speed} },
            "GET /api/studio/supertonic/use": function() { return {status: 200, data: host.use} },
            "POST /api/readaloud/online/azure/check": function() { return {status: 200, data: host.checked} },
            "POST /api/readaloud/clip": {status: 200, data: {url: "/media/readaloud/x.mp3", duration_ms: 4000, words: []}},
            "POST /api/readaloud/voice-speed": function(body) { host.speed = Object.assign({}, host.speed, {choice: body.choice}); return {status: 200, data: host.speed} }
        }
    }

    TestCase {
        id: test
        name: "D2Voice"
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        when: windowShown

        function init() {
            install()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system", autoRewind: true}
            Api.info = {version: "0.4.40"}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Api.defaultVoice = ""
            Api.voiceList = []
            Api.voiceName = ""
            Nav.layers = []
            Theme.reduceMotion = false
        }
        function cleanup() { current = null; DesktopApi.delayed = false; Theme.mode = "auto"; Theme.reduceMotion = false; Nav.layers = [] }

        function openAll() {
            for (const key of ["voice.provider.edge", "voice.provider.azure", "voice.provider.vieneu", "voice.provider.device", "voice.modules", "voice.performance", "voice.keys"]) Platform.setSetting("fold." + key, "1")
        }
        function make(width) {
            const page = createTemporaryObject(voiceFactory, host, {width: width || 760})
            verify(page !== null)
            current = page
            ready()
            return page
        }
        function find(item, name) {
            if (item.objectName === name) return item
            for (const child of item.children || []) { const found = find(child, name); if (found) return found }
            return null
        }
        function findAll(item, match, out) {
            out = out || []
            if (match(item)) out.push(item)
            for (const child of item.children || []) findAll(child, match, out)
            return out
        }
        function textItem(item, value) {
            const all = findAll(item, node => node.text === value && node.visible)
            return all.length ? all[0] : null
        }
        // chữ đang THẤY được (Collapse khép / khối ẩn thì không tính)
        function hasText(item, value) { return findAll(item, node => typeof node.text === "string" && node.text === value && node.visible).length > 0 }
        function overlay(name) { return find(host.Window.window.contentItem, name) }
        function row(page, id) { const found = findAll(page, node => node.voiceId === id); verify(found.length > 0, "no row " + id); return found[0] }
        function last(method, path) {
            for (let i = DesktopApi.requests.length - 1; i >= 0; --i) if (DesktopApi.requests[i].method === method && DesktopApi.requests[i].path === path) return DesktopApi.requests[i]
            return null
        }
        // Trang cao hơn cửa sổ: kéo trang lên cho phần tử vào khung nhìn rồi mới bấm (chuột thật chỉ chạm được thứ đang thấy)
        property var current: null
        function click(item) {
            ready()
            if (current) {
                current.y = 0
                const y = item.mapToItem(host, 0, 0).y
                if (y + item.height > host.height - 60) current.y = -(y - 300)
            }
            // Hit testing must see the new page position after scrolling it into view.
            ready()
            mouseClick(item, item.width / 2, item.height / 2)
        }
        function lacksOverflow(page) {
            // không Text nào rộng hơn khung chứa nó (chữ xuống dòng, không tràn)
            const bad = findAll(page, node => node.paintedWidth !== undefined && node.visible && node.width > 0 && node.paintedWidth > node.width + 1)
            return bad.length === 0
        }

        function test_loadsEverythingTheWebLoads() {
            openAll()
            const page = make()
            verify(last("GET", "/api/readaloud/voices") !== null)
            verify(last("GET", "/api/readaloud/online") !== null)
            verify(last("GET", "/api/readaloud/vieneu") !== null)
            verify(last("GET", "/api/readaloud/supertonic") !== null)
            verify(last("GET", "/api/readaloud/voice-speed") !== null)
            // chưa chọn mà máy có giọng VieNeu: giọng kể chuyện trung tính của VieNeu, không phải Edge
            compare(find(page, "voiceCurrent").text, "Đang dùng: Phạm Tuyên (VieNeu Turbo)")
            for (const text of ["Edge", "Azure Speech", "VieNeu", "Giọng của máy", "Bộ giọng", "Hiệu năng", "Khoá trực tuyến"]) verify(textItem(page, text) !== null, "thiếu " + text)
            verify(hasText(page, "trực tuyến, miễn phí · 2 giọng"))
            verify(hasText(page, "dùng khoá của bạn · 1 giọng"))
            verify(hasText(page, "trên máy này, không cần mạng · 4 giọng · đang dùng"))
            verify(hasText(page, "không cần mạng · 1 giọng"))
            verify(hasText(page, "Giọng Edge gửi chữ của sách tới máy chủ Microsoft để đọc."))
            verify(hasText(page, "Giọng Azure Speech gửi chữ của sách tới Azure Speech bằng khoá của bạn - có thể bị tính tiền vào tài khoản của bạn."))
            verify(!hasText(page, "Cài giọng tiếng Việt tại Cài đặt Windows › Thời gian và ngôn ngữ › Giọng nói."))
            compare(Api.voiceName, "Phạm Tuyên")
            verify(lacksOverflow(page))
        }

        function test_noDeviceVoiceShowsHint() {
            voices = fixtureVoices().filter(v => v.provider !== "device")
            openAll()
            const page = make()
            verify(hasText(page, "Cài giọng tiếng Việt tại Cài đặt Windows › Thời gian và ngôn ngữ › Giọng nói."))
            verify(hasText(page, "không cần mạng · 0 giọng"))
        }

        function test_choosingDefaultVoice() {
            openAll()
            const page = make()
            const target = row(page, "edge:vi-VN-NamMinhNeural")
            verify(!target.selected)
            click(target.radio)
            tryCompare(Api, "defaultVoice", "edge:vi-VN-NamMinhNeural")
            tryVerify(function() { return (Platform.setting("abook-readaloud-voice", "")) === ("edge:vi-VN-NamMinhNeural") })
            tryVerify(function() { return (last("PUT", "/api/preferences").body.readAloudVoice) === ("edge:vi-VN-NamMinhNeural") })
            tryVerify(function() { return target.selected })
            tryVerify(function() { return (find(page, "voiceCurrent").text) === ("Đang dùng: Nam Minh (Edge)") })
            tryVerify(function() { return hasText(page, "trực tuyến, miễn phí · 2 giọng · đang dùng") })
            tryCompare(Api, "voiceName", "Nam Minh")
            // chỉ giọng được chọn có "Mặc định"
            compare(findAll(page, node => node.text === "Mặc định" && node.visible).length, 1)
            // lưu hỏng: lời báo cách thử lại, như web
            DesktopApi.responses["PUT /api/preferences"] = {status: 500, data: {error: "đĩa đầy"}}
            click(row(page, "edge:vi-VN-HoaiMyNeural").radio)
            tryCompare(Api, "notice", "Chưa lưu được giọng mặc định. Bạn hãy chọn lại để thử lại.")
        }

        function test_arrowKeysMoveTheChoice() {
            openAll()
            const page = make()
            Platform.setSetting("abook-readaloud-voice", "")
            click(row(page, "edge:vi-VN-HoaiMyNeural").radio)
            row(page, "edge:vi-VN-HoaiMyNeural").radio.forceActiveFocus()
            keyClick(Qt.Key_Down)
            tryCompare(Api, "defaultVoice", "edge:vi-VN-NamMinhNeural")
            keyClick(Qt.Key_Down)               // vòng lại đầu nhóm
            tryCompare(Api, "defaultVoice", "edge:vi-VN-HoaiMyNeural")
            keyClick(Qt.Key_End)
            tryCompare(Api, "defaultVoice", "edge:vi-VN-NamMinhNeural")
        }

        function test_sampleStartsStopsAndDropsStaleReply() {
            openAll()
            const page = make()
            const target = row(page, "edge:vi-VN-HoaiMyNeural")
            const sample = textItem(target, "Thử giọng")
            verify(sample !== null)
            DesktopApi.delayed = true
            click(sample)
            compare(last("POST", "/api/readaloud/clip").body.voice, "edge:vi-VN-HoaiMyNeural")
            compare(last("POST", "/api/readaloud/clip").body.text, "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?")
            compare(target.loading, true)
            DesktopApi.finish()
            tryCompare(target, "loading", false)
            tryCompare(target, "playing", true)
            tryVerify(function() { return textItem(target, "Dừng") !== null })
            click(textItem(target, "Dừng"))
            tryCompare(target, "playing", false)
            tryVerify(function() { return textItem(target, "Thử giọng") !== null })
            // bấm giọng khác khi mẫu cũ còn đang về: mẫu cũ bị bỏ
            const other = row(page, "edge:vi-VN-NamMinhNeural")
            DesktopApi.delayed = true
            DesktopApi.pending = []
            click(textItem(target, "Thử giọng"))
            click(textItem(other, "Thử giọng"))
            DesktopApi.finish()
            tryCompare(target, "playing", false)
            tryCompare(other, "playing", true)
            // hết thời lượng mẫu thì nút về "Thử giọng"
            DesktopApi.delayed = false
            tryCompare(other, "playing", false)
        }

        function test_sampleErrorShowsUnderTheRow() {
            openAll()
            const page = make()
            DesktopApi.responses["POST /api/readaloud/clip"] = {status: 503, data: {message: "Không có mạng - giọng Hoài My cần mạng."}}
            const target = row(page, "edge:vi-VN-HoaiMyNeural")
            click(textItem(target, "Thử giọng"))
            tryVerify(function() { return hasText(target, "Không có mạng - giọng Hoài My cần mạng.") })
            tryCompare(Api, "notice", "")                      // lỗi nghe thử hiện tại chỗ, không toast
            tryVerify(function() { return textItem(target, "Thử giọng") !== null })
        }

        function test_keyFlow() {
            openAll()
            const page = make()
            const azure = find(page, "providerKey.azure")
            const google = find(page, "providerKey.google")
            verify(azure !== null && google !== null)
            // đã có khoá: gập mở sẵn; chưa có: gập
            compare(azure.open, true)
            compare(google.open, false)
            verify(hasText(azure, "Dùng được · 3 giọng"))
            verify(hasText(azure, "Miễn phí 500.000 ký tự mỗi tháng. Tô đúng từng chữ đang đọc."))
            // Lưu bị khoá khi chưa gõ gì
            const save = find(azure, "keySave")
            compare(save.enabled, false)
            const input = find(azure, "keyInput")
            compare(input.placeholderText, "Đã lưu ••••abcd - dán khoá mới để thay")
            input.forceActiveFocus()
            input.text = "  secret-key-123  "
            compare(save.enabled, true)
            save.activated()
            tryVerify(function() { return last("PUT", "/api/readaloud/online/azure") !== null })
            const put = last("PUT", "/api/readaloud/online/azure")
            compare(put.body.key, "secret-key-123")
            compare(put.body.region, "southeastasia")
            compare(input.text, "")
            compare(find(azure, "keyResult").text, "Đã lưu khoá. Bấm “Kiểm tra” để thử.")
            // Kiểm tra không có gì mới gõ thì không PUT lại, chỉ POST check
            DesktopApi.requests = []
            find(azure, "keyCheck").activated()
            tryVerify(function() { return (DesktopApi.requests.filter(r => r.method === "PUT").length) === (0) })
            tryVerify(function() { return last("POST", "/api/readaloud/online/azure/check") !== null })
            tryVerify(function() { return (find(azure, "keyResult").text) === ("Dùng được · 3 giọng tiếng Việt") })
            // khoá bị từ chối: lời của dịch vụ
            DesktopApi.responses["POST /api/readaloud/online/azure/check"] = {status: 200, data: {ok: false, message: "Khoá bị từ chối.", provider: {voices: 0}}}
            find(azure, "keyCheck").activated()
            tryVerify(function() { return (find(azure, "keyResult").text) === ("Khoá bị từ chối.") })
            // chưa gõ khoá và chưa có: báo dán khoá, không gọi mạng
            google.open = true
            tryCompare(find(google, "keyInput"), "text", "")
            DesktopApi.requests = []
            compare(find(google, "keyCheck").enabled, false)
            find(google, "keyInput").text = "k"
            find(google, "keySave").activated()
            tryVerify(function() { return (last("PUT", "/api/readaloud/online/google").body.key) === ("k") })
            // gỡ khoá
            DesktopApi.requests = []
            find(azure, "keyRemove").activated()
            tryVerify(function() { return last("DELETE", "/api/readaloud/online/azure") !== null })
            // sau mỗi việc, danh sách giọng + khoá hỏi lại
            verify(last("GET", "/api/readaloud/voices") !== null)
            verify(last("GET", "/api/readaloud/online") !== null)
        }

        function test_keyErrorsAreInline() {
            openAll()
            const page = make()
            const google = find(page, "providerKey.google")
            google.open = true
            DesktopApi.responses["PUT /api/readaloud/online/google"] = {status: 400, data: {message: "Khoá không hợp lệ"}}
            find(google, "keyInput").text = "bad"
            find(google, "keySave").activated()
            tryVerify(function() { return (find(google, "keyResult").text) === ("Khoá không hợp lệ") })
            tryCompare(Api, "notice", "")
        }

        function test_azureRegionOnlyChangeEnablesSave() {
            openAll()
            const page = make()
            const azure = find(page, "providerKey.azure")
            const region = find(azure, "regionInput")
            compare(region.text, "southeastasia")
            compare(find(azure, "keySave").enabled, false)
            region.text = "eastus"
            compare(find(azure, "keySave").enabled, true)
            verify(find(page, "providerKey.google") !== null)
            compare(find(find(page, "providerKey.google"), "regionInput").visible, false)
        }

        function test_downloadAndCancel() {
            openAll()
            const page = make()
            const card = find(page, "voiceModule.supertonic")
            verify(card.downloading)
            verify(hasText(card, "Đang tải giọng Supertonic (217 MB) 52%"))
            verify(find(card, "moduleBar").width > 0)
            // tóm tắt ở đầu "Bộ giọng"
            verify(hasText(page, "Supertonic · 52%"))
            // cỡ mỗi lựa chọn đứng yên, % không lùi
            const bar = find(card, "moduleBar").width
            supertonic = Object.assign({}, supertonic, {done: 60000000})
            card.refresh()
            tryVerify(function() { return (find(card, "moduleBar").width) === (bar) })
            // Huỷ
            DesktopApi.responses["POST /api/readaloud/supertonic/cancel"] = function() {
                host.supertonic = Object.assign({}, host.supertonic, {state: "missing", cancelled: true, done: 0})
                return {status: 200, data: host.supertonic}
            }
            click(find(card, "moduleCancel"))
            tryVerify(function() { return JSON.stringify(last("POST", "/api/readaloud/supertonic/cancel").body) === JSON.stringify({}) })
            tryVerify(function() { return !card.downloading })
            tryVerify(function() { return hasText(card, "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng. Mười giọng nam nữ, nhẹ máy, không cần mạng. Chữ của sách không rời máy.") || card.status.cancelled })
            // Tải (cỡ còn thiếu) -> POST kèm lựa chọn
            click(find(card, "choice.supertonic"))          // VieNeu đã có nên Supertonic không đánh dấu sẵn
            tryVerify(function() { return find(card, "moduleStart").text === "Tải (217 MB)" })
            const start = find(card, "moduleStart")
            compare(start.text, "Tải (217 MB)")
            DesktopApi.responses["POST /api/readaloud/supertonic"] = function(body) {
                host.supertonic = Object.assign({}, host.supertonic, {state: "downloading", done: 1000000})
                return {status: 200, data: host.supertonic}
            }
            click(start)
            tryVerify(function() { return JSON.stringify(last("POST", "/api/readaloud/supertonic").body.choices) === JSON.stringify(["supertonic"]) })
            tryVerify(function() { return card.downloading })
        }

        function test_downloadFailureToast() {
            openAll()
            const page = make()
            const card = find(page, "voiceModule.vieneu")
            const nano = find(card, "choice.nano")
            click(nano)
            tryVerify(function() { return (find(card, "moduleStart").text) === ("Tải (168 MB)") })
            DesktopApi.responses["POST /api/readaloud/vieneu"] = {status: 400, data: {message: "Hết chỗ trên đĩa"}}
            click(find(card, "moduleStart"))
            tryVerify(function() { return JSON.stringify(last("POST", "/api/readaloud/vieneu").body.choices) === JSON.stringify(["nano"]) })
            tryCompare(Api, "notice", "Chưa tải được giọng VieNeu\nHết chỗ trên đĩa")
        }

        function test_removeAsksFirstAndBackClosesTheAsk() {
            openAll()
            const page = make()
            const card = find(page, "voiceModule.vieneu")
            click(find(card, "choiceRemove.turbo"))
            tryVerify(function() { return overlay("removeConfirm.vieneu") !== null })
            const confirm = overlay("removeConfirm.vieneu")
            verify(confirm !== null)
            compare(confirm.open, true)
            compare(Nav.layers.length, 1)
            compare(confirm.title, "Gỡ “Giọng VieNeu Turbo” khỏi máy này?")
            // VieNeu không hỏi cuốn nào: câu ngắn
            compare(confirm.description, "Giọng sẽ không còn trên máy này cho tới khi bạn tải lại.")
            // Back đóng hộp hỏi, không gỡ gì
            verify(Nav.back())
            tryCompare(confirm, "open", false)
            tryVerify(function() { return (Nav.layers.length) === (0) })
            tryVerify(function() { return (DesktopApi.requests.filter(r => r.path === "/api/readaloud/vieneu/remove").length) === (0) })
            // mở lại, "Giữ lại" cũng không gỡ
            click(find(card, "choiceRemove.turbo"))
            tryVerify(function() { return overlay("removeConfirmNo.vieneu") !== null })
            click(overlay("removeConfirmNo.vieneu"))
            tryCompare(confirm, "open", false)
            tryVerify(function() { return (DesktopApi.requests.filter(r => r.path === "/api/readaloud/vieneu/remove").length) === (0) })
            // "Gỡ giọng" mới gỡ
            DesktopApi.responses["POST /api/readaloud/vieneu/remove"] = function(body) {
                host.vieneu.choices[0] = Object.assign({}, host.vieneu.choices[0], {installed: false, bytes: 300000000})
                return {status: 200, data: host.vieneu}
            }
            click(find(card, "choiceRemove.turbo"))
            tryVerify(function() { return overlay("removeConfirmYes.vieneu") !== null })
            click(overlay("removeConfirmYes.vieneu"))
            tryVerify(function() { return (last("POST", "/api/readaloud/vieneu/remove").body.choice) === ("turbo") })
            tryCompare(confirm, "open", false)
            tryVerify(function() { return (Nav.layers.length) === (0) })
            tryVerify(function() { return last("GET", "/api/readaloud/voices") !== null })
        }

        function test_supertonicRemoveNamesTheBooksStillUsingIt() {
            host.supertonic = Object.assign({}, fixtureSupertonic(), {state: "ready", choices: [Object.assign({}, fixtureSupertonic().choices[0], {installed: true, bytes: 0})]})
            openAll()
            const page = make()
            const card = find(page, "voiceModule.supertonic")
            DesktopApi.delayed = true
            click(find(card, "choiceRemove.supertonic"))
            tryVerify(function() { return overlay("removeConfirm.supertonic") !== null })
            const confirm = overlay("removeConfirm.supertonic")
            verify(confirm !== null)
            // chưa biết cuốn nào dùng: đang xem, nút Gỡ giọng chưa bấm được
            const supertonicConfirm = findAll(host.Window.window.contentItem, node => node.objectName === "removeConfirm.supertonic")
            verify(supertonicConfirm.length >= 1)
            DesktopApi.delayed = false
            DesktopApi.finish()
            tryVerify(function() { return findAll(host.Window.window.contentItem, node => node.objectName === "removeConfirm.supertonic" && node.open).length > 0 })
            const dialog = findAll(host.Window.window.contentItem, node => node.objectName === "removeConfirm.supertonic" && node.open)[0]
            verify(dialog !== undefined)
            compare(dialog.description, "2 cuốn đang dùng giọng này (“Rokujouma”, “Sách thứ hai”), 5 nhân vật. 40 câu chưa thu sẽ im tới khi bạn tải lại giọng hay đổi giọng khác; câu đã thu vẫn nghe được.")
            verify(Nav.back())
        }

        function test_speedChoice() {
            openAll()
            const page = make()
            const choice = find(page, "voiceSpeedChoice")
            compare(choice.value, "auto")
            verify(hasText(page, "Máy kịp thì đọc bản hay nhất. Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất."))
            verify(hasText(page, "Giọng Supertonic - Đang dùng: Chất lượng cao nhất. Bản nhanh hơn cần tải thêm 62 MB."))
            choice.picked("fast")
            tryVerify(function() { return (last("POST", "/api/readaloud/voice-speed").body.choice) === ("fast") })
            tryVerify(function() { return hasText(page, "Nhanh hơn, tiếng kém hơn chút - hợp máy yếu. Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất.") })
            tryVerify(function() { return hasText(page, "Nhanh hơn") })
        }

        function test_loadErrorHasRetry() {
            DesktopApi.responses["GET /api/readaloud/voices"] = {status: 500, data: {message: "x"}}
            openAll()
            const page = make()
            verify(find(page, "voiceLoadError") !== null)
            compare(find(page, "voiceLoadError").text, "Bạn hãy kiểm tra kết nối rồi tải lại giọng đọc.")
            DesktopApi.responses["GET /api/readaloud/voices"] = function() { return {status: 200, data: host.voices} }
            click(textItem(page, "Thử lại"))
            tryCompare(page, "loadError", "")
            tryVerify(function() { return row(page, "edge:vi-VN-HoaiMyNeural") !== null })
        }

        function test_longVoiceNamesWrap() {
            const longName = "Giọng có một cái tên rất rất dài để thử xem nó xuống dòng thay vì bị cắt mất chữ ở cuối dòng (Edge)"
            voices = fixtureVoices().concat([{id: "edge:long", name: longName, provider: "edge", gender: "female", online: true}])
            openAll()
            const page = make(520)
            const longRow = row(page, "edge:long")
            const name = findAll(longRow, node => node.text === longName.replace(" (Edge)", ""))[0]
            verify(name !== undefined)
            verify(name.height > 2 * 14, "tên dài phải xuống dòng, cao " + name.height)
            verify(name.paintedWidth <= name.width + 1)
            verify(longRow.radio.height >= name.height)
            // nút thử vẫn nằm trong hàng, không bị đẩy ra ngoài
            const sample = textItem(longRow, "Thử giọng")
            const edge = longRow.mapFromItem(sample, sample.width, 0).x
            verify(edge <= longRow.width + 1, "nút ra ngoài hàng: " + edge + " > " + longRow.width)
            verify(lacksOverflow(page))
            // bề ngang hẹp nhất của cửa sổ cũng không tràn
            const narrow = make(360)
            verify(lacksOverflow(narrow))
        }

        function test_foldsAreRememberedAndAnimated() {
            const page = make()
            const edge = findAll(page, node => node.storageKey === "voice.provider.edge")[0]
            compare(edge.expanded, false)
            const head = findAll(edge, node => node !== edge && node.title === "Edge")[0]
            click(head)
            compare(edge.expanded, true)
            compare(Platform.setting("fold.voice.provider.edge", "0"), "1")
            click(head)
            compare(edge.expanded, false)
            compare(Platform.setting("fold.voice.provider.edge", "0"), "0")
        }

        function test_reducedMotionCollapseDoesNotTweenHeight() {
            openAll()
            Theme.reduceMotion = true
            const page = make()
            const edge = findAll(page, node => node.storageKey === "voice.provider.edge")[0]
            verify(edge.height > 100)
        }

        function test_settingsListShowsSpokenName() {
            const screen = createTemporaryObject(screenFactory, host, {width: 1000, height: 900})
            Api.defaultVoice = "edge:vi-VN-HoaiMyNeural"
            Api.loadVoiceName()
            tryCompare(Api, "voiceName", "Hoài My")
            tryVerify(function() { return (screen.summary("voice")) === ("Hoài My") })
        }

        // ---- ảnh ----
        function shot(name, item) {
            const target = item || host
            ready()
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }

        // Khung chụp: trang đặt trong khung cắt, kéo lên bằng page.y để thấy từng đoạn của trang dài
        function framed(width, x) {
            const frame = createTemporaryObject(frameFactory, host, {width: host.width, height: host.height})
            const page = createTemporaryObject(voiceFactory, frame.holder, {width: width, x: x === undefined ? (host.width - width) / 2 : x, y: 0})
            current = page
            ready()
            return {frame: frame, page: page}
        }
        function scrollTo(page, item, margin) { page.y = 0; page.y = -Math.max(0, item.mapToItem(page, 0, 0).y - (margin === undefined ? 40 : margin)) }
        function release(shown) { shown.page.destroy(); shown.frame.destroy(); ready() }

        function test_screenshotsPage() {
            openAll()
            both(function() {
                const shown = framed(800)
                const page = shown.page
                shot("settings_voice_top")
                scrollTo(page, find(page, "voiceModule.vieneu"), 100)
                shot("settings_voice_modules")
                scrollTo(page, find(page, "voiceModule.supertonic"), 40)
                shot("settings_voice_download")
                scrollTo(page, find(page, "voiceKeysHeader"), 40)
                shot("settings_voice_keys")
                release(shown)
            })
        }

        function test_screenshotsSampleAndKeyResult() {
            openAll()
            DesktopApi.responses["POST /api/readaloud/clip"] = function(body) {
                if (body.voice === "edge:vi-VN-NamMinhNeural") return {status: 503, data: {message: "Không có mạng - giọng Nam Minh cần mạng."}}
                return {status: 200, data: {url: "/media/readaloud/x.mp3", duration_ms: 60000, words: []}}
            }
            both(function() {
                const shown = framed(800)
                const page = shown.page
                click(textItem(row(page, "edge:vi-VN-HoaiMyNeural"), "Thử giọng"))
                ready()
                page.y = 0
                shot("settings_voice_sample")
                click(textItem(row(page, "edge:vi-VN-NamMinhNeural"), "Thử giọng"))
                ready()
                page.y = 0
                shot("settings_voice_sample_error")
                find(page, "providerKey.google").open = true
                find(page, "providerKey.azure").open = true
                const azure = find(page, "providerKey.azure")
                find(azure, "keyCheck").activated()
                tryVerify(function() { return find(find(page, "providerKey.azure"), "keyResult").text.length > 0 })
                find(find(page, "providerKey.fpt"), "keyInput").text = "dán-khoá-ở-đây"
                findAll(azure, node => node.label === "Nhận khoá")[0].open = true
                ready()
                scrollTo(page, find(page, "voiceKeysHeader"), 40)
                shot("settings_voice_keyresult")
                release(shown)
            })
        }

        function test_screenshotsConfirmAndLong() {
            const longName = "Giọng có một cái tên rất rất dài để thử xem nó xuống dòng thay vì bị cắt mất chữ ở cuối dòng (Edge)"
            voices = fixtureVoices().concat([{id: "edge:long", name: longName, provider: "edge", gender: "female", online: true}])
            openAll()
            both(function() {
                const shown = framed(520)
                const page = shown.page
                scrollTo(page, row(page, "edge:long"), 200)
                shot("settings_voice_narrow_long")
                click(find(find(page, "voiceModule.vieneu"), "choiceRemove.turbo"))
                ready()
                shot("settings_voice_confirm_narrow")
                Nav.back()
                ready()
                release(shown)
            })
            host.supertonic = Object.assign({}, fixtureSupertonic(), {state: "ready", choices: [Object.assign({}, fixtureSupertonic().choices[0], {installed: true, bytes: 0})]})
            both(function() {
                const shown = framed(800)
                const page = shown.page
                click(find(find(page, "voiceModule.supertonic"), "choiceRemove.supertonic"))
                ready()
                shot("settings_voice_confirm")
                Nav.back()
                ready()
                release(shown)
            })
        }

        function test_screenshotsNarrowKeys() {
            openAll()
            both(function() {
                const shown = framed(400)
                const page = shown.page
                find(page, "providerKey.google").open = true
                ready()
                scrollTo(page, find(page, "voiceKeysHeader"), 20)
                shot("settings_voice_narrow_keys")
                scrollTo(page, find(page, "voiceModule.supertonic"), 20)
                shot("settings_voice_narrow_download")
                release(shown)
            })
        }

        function test_screenshotsLoadingAndError() {
            openAll()
            both(function() {
                DesktopApi.delayed = true
                let shown = framed(800)
                shot("settings_voice_loading")
                release(shown)
                DesktopApi.delayed = false
                DesktopApi.responses["GET /api/readaloud/voices"] = {status: 500, data: {message: "x"}}
                shown = framed(800)
                shot("settings_voice_error")
                release(shown)
                DesktopApi.responses["GET /api/readaloud/voices"] = function() { return {status: 200, data: host.voices} }
            })
        }

        function test_screenshotsSettingsScreen() {
            Platform.setSetting("fold.voice.provider.edge", "1")
            Platform.setSetting("fold.voice.modules", "1")
            both(function() {
                const screen = createTemporaryObject(screenFactory, host, {width: host.width, height: host.height, active: "voice"})
                ready()
                shot("settings_voice_screen")
                screen.destroy()
                ready()
            })
        }
        Component {
            id: frameFactory
            Item {
                property alias holder: clip
                Rectangle { anchors.fill: parent; color: Theme.bg }
                Item { id: clip; anchors.fill: parent; clip: true; property real contentY: 0 }
            }
        }
    }
}
