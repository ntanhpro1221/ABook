import QtQuick
import ABook
import "DevicesLogic.js" as Logic

// Hai khối "Máy này" và "Máy đã ghép" của Cài đặt › Thiết bị (desktop/PhoneSync.tsx): bật "Kết nối Wi-Fi", ghép thiết bị bằng mã 6 số
// (sống 5 phút, dùng một lần, sai 5 lần thì khoá), quyền điều khiển từ xa, địa chỉ + Bluetooth, danh sách máy đã ghép (đổi tên, thôi ghép).
// Hợp đồng với máy chủ: GET/POST /api/sync, POST/DELETE /api/sync/pairing, POST /api/sync/studio, DELETE /api/sync/devices/<id>,
// POST /api/sync/devices/<id>/name và /studio. Hỏi lại 10 giây một lần, 1,5 giây khi đang hiện mã (báo "đã ghép" ngay).
Item {
    id: root
    UiActivity { target: root; id: activity; onResumed: { root.now = Date.now() / 1000; root.load() } }
    readonly property bool expanded: Theme.widthClass(width) >= 2
    property real wideT: expanded ? 1 : 0
    Behavior on wideT {
        NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    implicitHeight: Math.max(thisDevice.height, pairedDevices.y + pairedDevices.height)
    height: implicitHeight
    property var sync: null
    property bool loadFailed: false
    property var pendingWanted: null      // công tắc đang chờ máy chủ: hiện giá trị người dùng vừa chọn (wanted = toggle.variables)
    property var pendingStudio: null
    property bool pairBusy: false
    property bool studioDeviceBusy: false
    property bool renameBusy: false
    property real now: Date.now() / 1000
    property var known: null
    // Hộp thoại / bảng nổi vẽ ở lớp ngoài cùng của cửa sổ (không bị khung cuộn cắt)
    readonly property Item overlay: Window.window ? Window.window.contentItem : root
    readonly property bool wanted: pendingWanted !== null ? Boolean(pendingWanted) : Boolean(sync && sync.wanted)
    readonly property bool failing: Boolean(sync && sync.wanted && !sync.enabled)
    readonly property bool studioWanted: pendingStudio !== null ? Boolean(pendingStudio) : Boolean(sync && sync.remoteStudio)
    readonly property string syncLabel: "Kết nối Wi-Fi"
    readonly property alias deviceRows: deviceRows

    // Toast của web = Api.notice (cùng chữ). Lỗi của máy chủ đã được Api.call đặt vào notice.
    function say(text) { Api.notice = text }
    function quiet(method, path, body, done) {
        const before = Api.notice
        Api.call(method, path, body, function(data, error) { if (error) Api.notice = before; done(data, error) })
    }
    function take(data) {
        // Điện thoại vừa nhập đúng mã: nó xuất hiện trong danh sách - báo ngay, người dùng đang nhìn vào máy tính.
        const previous = known
        known = (data.devices || []).map(device => device.id)
        if (previous) {
            const added = (data.devices || []).find(device => previous.indexOf(device.id) < 0)
            if (added) say("Đã ghép " + added.name)
        }
        sync = data
        loadFailed = false
        deviceRows.update(data.devices || [])
    }
    function load() {
        quiet("GET", "/api/sync", null, function(data, error) {
            if (error) { if (!root.sync) root.loadFailed = true; return }
            root.take(data)
        })
    }
    function toggle(enabled) {
        pendingWanted = enabled
        Api.call("POST", "/api/sync", {enabled: enabled}, function(data, error) {
            root.pendingWanted = null
            if (error) return
            root.take(data)
            if (enabled && !data.enabled) root.say("Chưa bật được đồng bộ")
            // Tắt xong không có gì đổi trên màn ngoài công tắc: nói một câu để biết đã tắt thật (soát UX a17).
            else if (!enabled && !data.enabled) root.say("Đã tắt chia sẻ qua Wi-Fi")
        })
    }
    function startPairing() {
        pairBusy = true
        Api.call("POST", "/api/sync/pairing", null, function(data, error) { root.pairBusy = false; if (!error) root.take(data) })
    }
    function cancelPairing() {
        pairBusy = true
        Api.call("DELETE", "/api/sync/pairing", null, function(data, error) { root.pairBusy = false; if (!error) root.take(data) })
    }
    function setStudio(enabled) {
        pendingStudio = enabled
        Api.call("POST", "/api/sync/studio", {enabled: enabled}, function(data, error) { root.pendingStudio = null; if (!error) root.take(data) })
    }
    function setDeviceStudio(id, enabled) {
        studioDeviceBusy = true
        Api.call("POST", "/api/sync/devices/" + id + "/studio", {enabled: enabled}, function(data, error) { root.studioDeviceBusy = false; if (!error) root.take(data) })
    }
    function revoke(id, name) {
        Api.call("DELETE", "/api/sync/devices/" + id, null, function(data, error) {
            if (error) return
            // Thôi ghép xong nói một câu (soát a68 lỗi 15): dòng thiết bị biến mất không đủ để biết đã xong và hệ quả là gì.
            root.take(data)
            root.say("Đã thôi ghép " + name)
        })
    }
    function rename(id, name) {
        renameBusy = true
        Api.call("POST", "/api/sync/devices/" + id + "/name", {name: name}, function(data, error) {
            root.renameBusy = false
            if (error) return
            root.take(data)
            root.say("Đã đổi tên thành “" + name + "”")
            renameDialog.dismiss()
        })
    }

    Component.onCompleted: load()
    Timer { interval: root.sync && root.sync.pairing ? 1500 : 10000; running: activity.running && root.visible; repeat: true; onTriggered: root.load() }
    Timer { interval: 1000; running: activity.running && root.visible && Boolean(root.sync && root.sync.pairing); repeat: true; triggeredOnStart: true; onTriggered: root.now = Date.now() / 1000 }
    Timer { interval: 30000; running: activity.running && root.visible; repeat: true; onTriggered: root.now = Date.now() / 1000 }

    DevicesRows { id: deviceRows }

    // ---- Máy này ----
    SectionBlock {
        id: thisDevice
        objectName: "thisDeviceColumn"
        width: Math.min(Theme.listMeasure, parent.width + ((parent.width - Theme.s32) / 2 - parent.width) * Math.min(1, root.wideT * 2))
        title: "Máy này"
        SettingsItem {
            width: parent.width
            spacing: 0
            // Khung chờ / lỗi và nội dung cùng một chỗ: tải xong thì khung chờ khép lại, nội dung mở ra
            Collapse {
                width: parent.width
                open: root.sync === null && !root.loadFailed
                DevicesSkeleton { width: parent.width; count: 2; label: "Đang tải kết nối" }
            }
            DevicesError {
                width: parent.width
                open: root.sync === null && root.loadFailed
                message: "Bạn hãy thử tải lại cài đặt kết nối."
                onRetry: { root.loadFailed = false; root.load() }
            }
            Collapse {
                width: parent.width
                open: root.sync !== null
                Column {
                    width: parent.width
                    DevicesToggle {
                        objectName: "syncToggle"
                        width: parent.width
                        label: root.syncLabel
                        hint: !root.sync ? "" : root.sync.enabled ? "Máy cùng mạng thấy máy này là “" + root.sync.name + "”."
                            : root.failing ? (root.sync.error || "Chưa mở được cổng đồng bộ.") : "Đang tắt - máy khác không thấy máy này."
                        hintColor: root.failing ? Theme.danger : Theme.text2
                        checked: root.wanted
                        switchItem.enabled: root.pendingWanted === null
                        onToggled: value => root.toggle(value)
                    }
                    Collapse {
                        width: parent.width
                        open: root.failing
                        Item {
                            width: parent.width
                            implicitHeight: retry.height + 20
                            height: implicitHeight
                            Button { id: retry; y: 20; size: "sm"; text: "Thử lại"; busy: root.pendingWanted !== null; onActivated: root.toggle(true) }
                        }
                    }
                    Collapse {
                        width: parent.width
                        open: Boolean(root.sync && root.sync.enabled)
                        Column {
                            width: parent.width
                            topPadding: 20
                            spacing: 20
                            DevicesFold {
                                objectName: "pairFold"
                                width: parent.width
                                storageKey: "phone-sync.pair"
                                title: "Ghép thiết bị"
                                summary: root.sync && root.sync.pairing ? "Đang hiện mã ghép" : "Điện thoại, máy tính bảng"
                                defaultOpen: Boolean(root.sync && root.sync.pairing)
                                bottomGap: 12
                                PhoneSyncPairing {
                                    width: parent.width
                                    sync: root.sync || ({})
                                    busy: root.pairBusy
                                    now: root.now
                                    onPair: root.startPairing()
                                    onCancel: root.cancelPairing()
                                }
                            }
                            DevicesFold {
                                objectName: "permissionsFold"
                                width: parent.width
                                storageKey: "phone-sync.permissions"
                                title: "Quyền điều khiển"
                                summary: root.studioWanted ? "Đang bật" : "Đang tắt"
                                DevicesToggle {
                                    objectName: "studioToggle"
                                    width: parent.width
                                    label: "Điều khiển từ xa"
                                    labelSize: Theme.sizeBodySmall
                                    hintSize: 13
                                    hintRich: root.studioWanted
                                    hint: root.studioWanted ? "Mở " + Logic.whereHtml(root.sync || ({}), true, String(Theme.text)) + " trên thiết bị đã ghép để làm sách từ xa."
                                        : "Tắt: thiết bị đã ghép chỉ tải và nghe sách."
                                    checked: root.studioWanted
                                    switchItem.enabled: root.pendingStudio === null
                                    onToggled: value => { if (value) studioDialog.show(); else root.setStudio(false) }
                                }
                            }
                            DevicesFold {
                                objectName: "connectionFold"
                                width: parent.width
                                storageKey: "phone-sync.connection"
                                title: "Kết nối"
                                summary: "Địa chỉ và Bluetooth"
                                Collapse {
                                    width: parent.width
                                    open: Boolean(root.sync && root.sync.bluetooth)
                                    Item {
                                        width: parent.width
                                        implicitHeight: bluetoothNote.height + 8
                                        height: implicitHeight
                                        Text {
                                            id: bluetoothNote
                                            width: parent.width
                                            text: !root.sync || !root.sync.bluetooth ? "" : root.sync.bluetooth.running
                                                ? "Bluetooth: điện thoại đã ghép nối được cả khi khác Wi-Fi" + (root.sync.bluetooth.connections ? " - " + root.sync.bluetooth.connections + " đang kết nối" : "") + "."
                                                : root.sync.bluetooth.error
                                            color: Theme.text3
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeCaption
                                            lineHeight: 1.3
                                        }
                                    }
                                }
                                Collapse {
                                    width: parent.width
                                    open: Boolean(root.sync && (root.sync.addresses || []).length > 0)
                                    Item {
                                        width: parent.width
                                        implicitHeight: addressNote.height + 8
                                        height: implicitHeight
                                        Text {
                                            id: addressNote
                                            width: parent.width
                                            textFormat: Text.RichText
                                            text: "Điện thoại không thấy máy này? Chọn “Nhập địa chỉ” rồi gõ " + Logic.whereHtml(root.sync || ({}), false, String(Theme.text)) + "."
                                            color: Theme.text3
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeCaption
                                            lineHeight: 1.3
                                        }
                                    }
                                }
                                // Chủ sách 29-09 hỏi khác mạng có dùng được không: app không cần gì riêng - mạng riêng ảo người dùng tự cài cho
                                // máy này một địa chỉ điện thoại tới được, và điện thoại học địa chỉ ấy mỗi lần mở Thư viện.
                                Text {
                                    width: parent.width
                                    text: "Ngoài nhà: nghe sách đã tải, hoặc nối mạng riêng ảo để nghe thẳng."
                                    color: Theme.text3
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeCaption
                                    lineHeight: 1.3
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ---- Máy đã ghép ----
    Collapse {
        id: pairedDevices
        objectName: "pairedDeviceColumn"
        x: (thisDevice.width + Theme.s32) * Math.min(1, root.wideT * 2)
        y: thisDevice.height * (1 - Math.max(0, root.wideT * 2 - 1))
        width: Math.min(Theme.listMeasure, parent.width - x)
        open: Boolean(root.sync && root.sync.enabled)
        SectionBlock {
            width: parent.width
            title: "Máy đã ghép"
            SettingsItem {
                width: parent.width
                spacing: 0
                // Người mới chưa có app trên điện thoại: nói chỗ lấy (chữ chọn được, không phải liên kết - trong cửa sổ app một liên kết có thể điều hướng chính cửa sổ).
                Collapse {
                    width: parent.width
                    open: deviceRows.revision >= 0 && deviceRows.presentCount() === 0
                    TextEdit {
                        objectName: "noDevices"
                        width: parent.width
                        readOnly: true
                        selectByMouse: true
                        textFormat: TextEdit.RichText
                        wrapMode: TextEdit.Wrap
                        color: Theme.text2
                        selectionColor: Theme.accent
                        selectedTextColor: Theme.accentInk
                        font.family: Theme.family
                        font.pixelSize: 13
                        text: "Chưa có thiết bị. App Android: file " + "<span style='font-weight:500;color:" + Theme.text + "'>.apk</span> ở "
                            + "<span style='font-weight:500;color:" + Theme.text + "'>github.com/ntanhpro1221/ABook/releases</span>. iPhone, iPad: nghe bằng trình duyệt."
                    }
                }
                Column {
                    id: deviceList
                    objectName: "deviceList"
                    width: parent.width
                    Repeater {
                        model: deviceRows.model
                        PhoneSyncDevice {
                            id: deviceRow
                            required property int index
                            required property var model
                            rowId: model.rowId
                            json: model.json
                            present: model.present
                            fresh: model.fresh
                            width: deviceList.width
                            rows: deviceRows
                            first: deviceRows.revision >= 0 && deviceRows.presentBefore(deviceRow.index) === 0
                            remoteStudio: Boolean(root.sync && root.sync.remoteStudio)
                            studioBusy: root.studioDeviceBusy
                            clock: root.now
                            onRename: (id, name) => { renameDialog.targetId = id; renameDialog.draft = name; field.text = name; renameDialog.focusPending = true; renameDialog.show() }
                            onRemove: (id, name) => { removeDialog.targetId = id; removeDialog.targetName = name; removeDialog.show() }
                            onStudioToggled: (id, enabled) => root.setDeviceStudio(id, enabled)
                        }
                    }
                }
            }
        }
    }

    // ---- Hộp thoại ----
    // Bật điều khiển sản xuất từ xa phải hỏi lại (soát UX 29-09): thiết bị đã ghép bắt đầu / dừng sản xuất qua http trong mạng.
    Modal {
        id: studioDialog
        objectName: "studioDialog"
        parent: root.overlay
        title: "Bật Studio từ xa?"
        description: "Bật quyền riêng cho từng thiết bị để mở Studio trong trình duyệt."
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: "Để sau"; onClicked: studioDialog.dismiss() }
            Button { text: "Cho phép"; busy: root.pendingStudio !== null; onActivated: { root.setStudio(true); studioDialog.dismiss() } }
        }
    }
    Modal {
        id: removeDialog
        objectName: "removeDialog"
        parent: root.overlay
        property string targetId: ""
        property string targetName: ""
        title: "Thôi ghép " + (targetName || "thiết bị") + "?"
        description: "Dừng tải và đồng bộ; giữ sách đã tải."
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: "Để nguyên"; onClicked: removeDialog.dismiss() }
            Button { kind: "danger"; text: "Thôi ghép"; onClicked: { root.revoke(removeDialog.targetId, removeDialog.targetName); removeDialog.dismiss() } }
        }
    }
    Modal {
        id: renameDialog
        objectName: "renameDialog"
        parent: root.overlay
        property string targetId: ""
        property string draft: ""
        property bool focusPending: false
        onShownChanged: if (open && focusPending && shown > 0) { focusPending = false; field.forceActiveFocus() }
        title: "Đổi tên thiết bị"
        description: "Tên hiện ở danh sách thiết bị đã ghép của máy này."
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: "Để nguyên"; onClicked: renameDialog.dismiss() }
            Button { objectName: "renameSave"; text: "Lưu"; enabled: renameDialog.draft.trim() !== ""; busy: root.renameBusy; onActivated: renameDialog.save() }
        }
        function save() { if (draft.trim() !== "" && !root.renameBusy) root.rename(targetId, draft.trim()) }
        FormField {
            id: field
            objectName: "renameField"
            width: parent.width
            label: "Tên thiết bị"
            onTextChanged: { if (text.length > 80) text = text.slice(0, 80); else renameDialog.draft = text }
            onAccepted: renameDialog.save()
        }
    }
}
