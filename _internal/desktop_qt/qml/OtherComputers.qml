import QtQuick
import ABook
import "DevicesLogic.js" as Logic

// Khối "Máy tính khác" của Cài đặt › Thiết bị (desktop/OtherComputers.tsx, webui/remote_books.py): ghép bằng địa chỉ + mã 6 số đang hiện
// trên máy kia - đúng mã điện thoại dùng - rồi thư viện của máy ấy hiện trong Thư viện của máy này ("Trên <máy>"). Không chung Wi-Fi thì
// đi Bluetooth (địa chỉ Bluetooth của điện thoại, chọn từ thiết bị đã ghép ở Windows, hay đường Bluetooth dự phòng của máy đã ghép Wi-Fi).
// Máy chủ: GET/POST /api/computers, POST /api/computers/refresh, GET /api/computers/discover, GET /api/computers/bluetooth,
// POST /api/computers/<id>/bluetooth và /stop-waiting, GET /api/computers/<id>/unsent, DELETE /api/computers/<id>[?edits=send|discard].
// Hỏi lại 2 giây một lần khi có máy đang chờ dậy.
Column {
    id: root
    property var view: null                // {name, computers, broken}
    property bool loadFailed: false
    property var bluetoothDevices: []
    property string address: ""
    property string code: ""
    property string pairError: ""
    property bool pairBusy: false
    property bool discovering: false
    property var found: null               // kết quả "Tìm máy trong mạng": null = chưa tìm
    property bool refreshBusy: false
    property bool bluetoothBusy: false
    property real now: Date.now() / 1000
    property string wasWaking: ""
    // unpair (useUnpair): máy đang hỏi, lựa chọn đang chạy, lỗi lần gửi trước
    property var asking: null              // {computer, unsent}
    property string busyChoice: ""
    property string unpairError: ""
    readonly property Item overlay: Window.window ? Window.window.contentItem : root
    readonly property var computers: view ? view.computers || [] : []
    readonly property string waking: computers.filter(computer => computer.waking).map(computer => computer.id).join(",")
    readonly property string syncLabel: "Kết nối Wi-Fi"
    readonly property var pairedAddresses: computers.filter(computer => Logic.isBluetoothHost(computer.host)).map(computer => Logic.bluetoothAddress(computer))
    readonly property var unpairedDevices: bluetoothDevices.filter(device => pairedAddresses.indexOf(String(device.address).toUpperCase()) < 0)
    readonly property bool canPair: address.trim() !== "" && code.replace(/\D/g, "").length === 6
    signal openStudio(string id)

    function say(text) { Api.notice = text }
    function quiet(method, path, body, done) {
        const before = Api.notice
        Api.call(method, path, body, function(result, error) { if (error) Api.notice = before; done(result, error) })
    }
    function done(result) {
        root.view = result
        computerRows.update(result.computers || [])
        DesktopApi.refreshLibrary()
    }
    function load() {
        quiet("GET", "/api/computers", null, function(view, error) {
            if (error) { if (!root.view) root.loadFailed = true; return }
            root.loadFailed = false
            root.view = view
            computerRows.update(view.computers || [])
        })
    }
    function loadBluetooth() {
        // Thiết bị Bluetooth đã ghép ở Windows: chỉ đọc danh sách của hệ điều hành; lỗi hay rỗng thì thôi, không chặn gì.
        quiet("GET", "/api/computers/bluetooth", null, function(result, error) { if (!error) root.bluetoothDevices = result.devices || [] })
    }
    function pair() {
        pairBusy = true
        pairError = ""
        const known = computers.map(computer => computer.id)
        Api.call("POST", "/api/computers", {address: address, code: code}, function(view, error) {
            root.pairBusy = false
            if (error) { root.pairError = error; root.say("Chưa ghép được"); return }
            // Máy vừa ghép = máy có trong danh sách mới mà danh sách cũ chưa có: nói tên thật (soát UX a11).
            const added = (view.computers || []).find(computer => known.indexOf(computer.id) < 0)
            root.done(view)
            addressField.clear()
            codeField.clear()
            root.say(added && added.name ? "Đã ghép " + added.name : "Đã ghép")
        })
    }
    function refresh() {
        refreshBusy = true
        Api.call("POST", "/api/computers/refresh", null, function(view, error) { root.refreshBusy = false; if (!error) root.done(view) })
    }
    function stopWaiting(id) {
        refreshBusy = true
        Api.call("POST", "/api/computers/" + id + "/stop-waiting", null, function(view, error) { root.refreshBusy = false; if (!error) root.done(view) })
    }
    function setBluetooth(id, bluetoothAddress) {
        bluetoothBusy = true
        Api.call("POST", "/api/computers/" + id + "/bluetooth", {address: bluetoothAddress}, function(view, error) {
            root.bluetoothBusy = false
            if (error) { root.say("Chưa chọn được"); return }
            root.done(view)
            root.say(bluetoothAddress ? "Đã chọn Bluetooth dự phòng" : "Không dùng Bluetooth dự phòng nữa")
        })
    }
    function discover() {
        discovering = true
        Api.call("GET", "/api/computers/discover", null, function(result, error) {
            root.discovering = false
            if (error) { root.say("Không tìm được"); return }
            root.found = result.found || []
        })
    }
    function choose(target) {
        addressField.text = target
        codeField.forceActiveFocus()
    }
    // ---- Thôi ghép: có gì để mất thì hỏi trước, nói rõ mất gì và giữ gì (shared/useUnpair.tsx) ----
    function reachable(computer) {
        const current = computers.find(item => item.id === computer.id) || computer
        return !current.error && !current.waking
    }
    function runUnpair(computer, choice, finish) {
        const edits = choice === null ? "" : "?edits=" + choice
        const before = Api.notice
        Api.call("DELETE", "/api/computers/" + computer.id + edits, null, function(view, error) {
            if (!error) root.done(view)
            else Api.notice = before
            finish(error)
        })
    }
    function startUnpair(computer) {
        Api.call("GET", "/api/computers/" + computer.id + "/unsent", null, function(unsent, error) {
            if (error) { root.say("Chưa thôi ghép được"); return }
            if (Logic.unpairCopy(computer.name, "máy tính", unsent, root.reachable(computer)) === null) {
                root.runUnpair(computer, null, function(problem) { root.say(problem ? "Chưa thôi ghép được" : Logic.unpairDone(computer.name)) })
                return
            }
            root.unpairError = ""
            root.asking = {computer: computer, unsent: unsent}
            unpairDialog.show()
        })
    }
    function chooseUnpair(choice) {
        if (!asking) return
        const target = asking.computer
        busyChoice = choice
        unpairError = ""
        runUnpair(target, choice, function(problem) {
            root.busyChoice = ""
            if (problem) { root.unpairError = problem; return }
            root.say(Logic.unpairDone(target.name))
            unpairDialog.dismiss()
        })
    }

    Component.onCompleted: { load(); loadBluetooth() }
    onVisibleChanged: if (visible) { load(); loadBluetooth() }
    // Đang chờ một máy dậy: xem lại thường xuyên để thấy nó trả lời (hay hết hạn chờ).
    Timer { interval: 2000; running: root.visible && root.waking !== ""; repeat: true; onTriggered: { root.now = Date.now() / 1000; root.load() } }
    Timer { interval: 30000; running: root.visible; repeat: true; onTriggered: root.now = Date.now() / 1000 }
    // Một máy vừa thôi "đang ngủ" (đã trả lời, hay hết hạn): sách của nó có thể vừa hiện ra.
    onWakingChanged: { if (wasWaking !== "" && wasWaking !== waking) DesktopApi.refreshLibrary(); wasWaking = waking }

    DevicesRows { id: computerRows }

    // ---- Khung chờ / lỗi ----
    Collapse {
        width: parent.width
        open: root.view === null && !root.loadFailed
        DevicesSkeleton { width: parent.width; count: 2; label: "Đang tải thiết bị" }
    }
    DevicesError {
        width: parent.width
        open: root.view === null && root.loadFailed
        message: "Bạn hãy kiểm tra kết nối rồi tải lại thiết bị."
        onRetry: { root.loadFailed = false; root.load() }
    }
    Collapse {
        width: parent.width
        open: root.view !== null
        Column {
            width: parent.width
            // Danh sách máy đã ghép bị hỏng và đã làm lại: một dòng cho người dùng (máy chủ giữ bản hỏng).
            Collapse {
                width: parent.width
                open: Boolean(root.view && root.view.broken)
                Item {
                    width: parent.width
                    implicitHeight: brokenText.height + 16
                    height: implicitHeight
                    Text { id: brokenText; width: parent.width; text: root.view && root.view.broken ? root.view.broken : ""; color: Theme.warning; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall }
                }
            }
            // Ghép / thôi ghép: hàng mở / khép tại chỗ
            Collapse {
                width: parent.width
                open: computerRows.revision >= 0 && computerRows.presentCount() > 0
                Item {
                    width: parent.width
                    implicitHeight: list.height + 16
                    height: implicitHeight
                    Column {
                        id: list
                        objectName: "computerList"
                        width: Math.min(parent.width, Theme.listMeasure)
                        Repeater {
                            model: computerRows.model
                            OtherComputersRow {
                                id: computerRow
                                required property int index
                                required property var model
                                rowId: model.rowId
                                json: model.json
                                present: model.present
                                fresh: model.fresh
                                width: list.width
                                rows: computerRows
                                first: computerRows.revision >= 0 && computerRows.presentBefore(computerRow.index) === 0
                                devices: root.bluetoothDevices
                                busy: root.refreshBusy || root.bluetoothBusy
                                clock: root.now
                                overlay: root.overlay
                                onDiagnose: target => diagnostics.openFor(target)
                                onOpenStudio: id => { root.openStudio(id); Nav.openPeerStudio(id) }
                                onRefresh: root.refresh()
                                onStopWaiting: id => root.stopWaiting(id)
                                onUnpair: target => root.startUnpair(target)
                                onBluetooth: (id, address) => root.setBluetooth(id, address)
                            }
                        }
                    }
                }
            }
            DevicesFold {
                objectName: "pairFold"
                width: parent.width
                storageKey: "other-computers.pair"
                title: "Ghép máy"
                summary: "Nghe sách của máy tính khác"
                Column {
                    width: parent.width
                    spacing: 12
                    Column {
                        width: parent.width
                        spacing: 8
                        Button { objectName: "discover"; kind: "ghost"; icon: "radar"; text: "Tìm máy trong mạng"; busy: root.discovering; onActivated: root.discover() }
                        Collapse {
                            width: parent.width
                            open: root.found !== null && root.found.length > 0
                            Column {
                                width: Math.min(parent.width, Theme.listMeasure)
                                Repeater {
                                    model: root.found || []
                                    Item {
                                        id: foundRow
                                        required property var modelData
                                        required property int index
                                        width: parent.width
                                        implicitHeight: Math.max(foundWords.height, 40) + 16 + (index > 0 ? 1 : 0)
                                        height: implicitHeight
                                        Rectangle { width: parent.width; height: 1; color: Theme.line; visible: foundRow.index > 0 }
                                        Icon { x: 0; y: (foundRow.height - 20 + (foundRow.index > 0 ? 1 : 0)) / 2; name: modelData.kind === "phone" ? "smartphone" : "laptop"; size: 20; color: Theme.text2 }
                                        Column {
                                            id: foundWords
                                            x: 32
                                            y: (foundRow.height + (foundRow.index > 0 ? 1 : 0) - height) / 2
                                            width: parent.width - 32 - 12 - pick.width
                                            Text { width: parent.width; text: modelData.name; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                                            Text { width: parent.width; text: modelData.host + ":" + modelData.port; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeCaption }
                                        }
                                        Item {
                                            id: pick
                                            width: modelData.paired ? pairedText.implicitWidth : chooseButton.width
                                            height: parent.height
                                            x: parent.width - width
                                            Text { id: pairedText; visible: modelData.paired; anchors.verticalCenter: parent.verticalCenter; text: "Đã ghép"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                                            Button { id: chooseButton; visible: !modelData.paired; anchors.verticalCenter: parent.verticalCenter; size: "sm"; kind: "ghost"; text: "Chọn"; onClicked: root.choose(modelData.host + ":" + modelData.port) }
                                        }
                                    }
                                }
                            }
                        }
                        Collapse {
                            width: parent.width
                            open: root.found !== null && root.found.length === 0
                            HintText { width: parent.width; text: "Không thấy máy nào trong mạng này." }
                        }
                    }
                    Flow {
                        id: form
                        width: parent.width
                        spacing: 8
                        readonly property real codeWidth: 128
                        readonly property bool stacked: width < 420 + codeWidth + 8 + 90
                        Column {
                            width: form.stacked ? form.width : Math.max(160, form.width - form.codeWidth - 8 - connect.width - 8)
                            spacing: 4
                            Text { width: parent.width; text: "Địa chỉ máy kia"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                            FormField {
                                id: addressField
                                objectName: "addressField"
                                width: parent.width
                                label: "Địa chỉ máy kia"
                                placeholderText: "192.168.1.20 hoặc địa chỉ Bluetooth"
                                onTextChanged: root.address = text
                                onAccepted: if (root.canPair && !root.pairBusy) root.pair()
                            }
                        }
                        Column {
                            width: form.codeWidth
                            spacing: 4
                            Text { width: parent.width; text: "Mã 6 số"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                            FormField {
                                id: codeField
                                objectName: "codeField"
                                width: parent.width
                                label: "Mã 6 số"
                                placeholderText: "123456"
                                font.features: {"tnum": 1}
                                onTextChanged: {
                                    const digits = text.replace(/\D/g, "").slice(0, 6)
                                    if (text !== digits) { text = digits; return }
                                    root.code = digits
                                }
                                onAccepted: if (root.canPair && !root.pairBusy) root.pair()
                            }
                        }
                        Item {
                            width: connect.width
                            height: form.stacked ? connect.height : 4 + 16 + 40
                            Button {
                                id: connect
                                objectName: "connectComputer"
                                y: form.stacked ? 0 : parent.height - height
                                kind: "ghost"
                                text: "Kết nối"
                                busy: root.pairBusy
                                enabled: root.canPair
                                onActivated: root.pair()
                            }
                        }
                    }
                    // Toast biến mất sau vài giây; lý do không ghép được ở lại dưới ô địa chỉ cho tới lần thử kế (soát UX a17).
                    Collapse {
                        width: parent.width
                        open: root.pairError !== ""
                        Text {
                            objectName: "pairError"
                            width: parent.width
                            text: "Chưa ghép được: " + root.pairError
                            color: Theme.danger
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: 13
                        }
                    }
                    Collapse {
                        width: parent.width
                        open: root.unpairedDevices.length > 0
                        Column {
                            width: parent.width
                            spacing: 6
                            HintText { width: parent.width; text: "Khác Wi-Fi? Chọn máy đã ghép Bluetooth:" }
                            Flow {
                                width: parent.width
                                spacing: 8
                                Repeater {
                                    model: root.unpairedDevices
                                    Button {
                                        required property var modelData
                                        size: "sm"
                                        kind: "ghost"
                                        icon: "bluetooth"
                                        wrap: true
                                        text: modelData.name + " · " + Logic.deviceKindLabel(modelData.kind)
                                        onClicked: root.choose(modelData.address)
                                    }
                                }
                            }
                        }
                    }
                    HintText { width: parent.width; text: "Máy kia: Cài đặt › Thiết bị › bật “" + root.syncLabel + "” để lấy mã; ghép một chiều để nghe thư viện của máy ấy." }
                }
            }
        }
    }

    // ---- Hộp thoại ----
    DevicesUnpair {
        id: unpairDialog
        objectName: "unpairDialog"
        parent: root.overlay
        copy: root.asking ? Logic.unpairCopy(root.asking.computer.name, "máy tính", root.asking.unsent, root.reachable(root.asking.computer)) : null
        busyChoice: root.busyChoice
        error: root.unpairError
        onChoose: choice => root.chooseUnpair(choice)
        onClosed: root.asking = null
    }
    PhoneDiagnostics { id: diagnostics; objectName: "diagnostics"; parent: root.overlay }
}
