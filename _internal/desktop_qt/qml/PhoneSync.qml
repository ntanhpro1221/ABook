import "UiStrings.js" as S
import QtQuick
import ABook
import "DevicesLogic.js" as Logic
import "TextWrap.js" as TextWrap

// Hai khối "Máy này" và "Máy đã ghép" của Cài đặt › Thiết bị (desktop/PhoneSync.tsx): bật "Kết nối Wi-Fi", ghép thiết bị bằng mã 6 số
// (sống 5 phút, dùng một lần, sai 5 lần thì khoá), quyền điều khiển từ xa, địa chỉ + Bluetooth, danh sách máy đã ghép (đổi tên, bỏ ghép).
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
    readonly property bool wanted: pendingWanted !== null ? Boolean(pendingWanted) : Boolean(sync && sync.wanted)
    readonly property bool failing: Boolean(sync && sync.wanted && !sync.enabled)
    readonly property bool studioWanted: pendingStudio !== null ? Boolean(pendingStudio) : Boolean(sync && sync.remoteStudio)
    readonly property string syncLabel: S.s_ket_noi_wi_fi_7680d1aa
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
            if (added) say(S.s_da_ghep_7b3601f2 + added.name)
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
            if (enabled && !data.enabled) root.say(S.s_chua_bat_duoc_dong_bo_9927f58c)
            // Tắt xong không có gì đổi trên màn ngoài công tắc: nói một câu để biết đã tắt thật (soát UX a17).
            else if (!enabled && !data.enabled) root.say(S.s_da_tat_chia_se_qua_wi_fi_c818faf6)
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
            // Bỏ ghép xong nói một câu (soát a68 lỗi 15): dòng thiết bị biến mất không đủ để biết đã xong và hệ quả là gì.
            root.take(data)
            root.say(S.s_da_bo_ghep_0977f068 + name)
        })
    }
    function rename(id, name) {
        renameBusy = true
        Api.call("POST", "/api/sync/devices/" + id + "/name", {name: name}, function(data, error) {
            root.renameBusy = false
            if (error) return
            root.take(data)
            root.say(S.s_da_doi_ten_thanh_a5653594 + name + "”")
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
        title: S.s_may_nay_4668c138
        SettingsItem {
            width: parent.width
            spacing: 0
            // Khung chờ / lỗi và nội dung cùng một chỗ: tải xong thì khung chờ khép lại, nội dung mở ra
            Collapse {
                width: parent.width
                open: root.sync === null && !root.loadFailed
                DevicesSkeleton { width: parent.width; count: 2; label: S.s_dang_tai_ket_noi_e4acf571 }
            }
            InlineError {
                width: parent.width
                open: root.sync === null && root.loadFailed
                message: S.s_ban_hay_thu_tai_lai_cai_dat_ket_noi_db777637
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
                        hint: !root.sync ? "" : root.sync.enabled ? S.s_may_cung_mang_thay_may_nay_la_d52412f1 + root.sync.name + "”."
                            : root.failing ? (root.sync.error || S.s_chua_mo_duoc_cong_dong_bo_8f2a1744) : S.s_dang_tat_may_khac_khong_thay_may_nay_8924a002
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
                            Button { id: retry; y: 20; size: "sm"; text: S.s_thu_lai_c58d068c; busy: root.pendingWanted !== null; onActivated: root.toggle(true) }
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
                                title: S.s_ghep_thiet_bi_8de1f23c
                                summary: root.sync && root.sync.pairing ? S.s_dang_hien_ma_ghep_e97b43a2 : S.s_dien_thoai_may_tinh_bang_4ade8e1e
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
                                title: S.s_quyen_dieu_khien_e895c2b8
                                summary: root.studioWanted ? S.s_dang_bat_70767620 : S.s_dang_tat_53bfa8b7
                                DevicesToggle {
                                    objectName: "studioToggle"
                                    width: parent.width
                                    label: S.s_dieu_khien_tu_xa_1db316de
                                    labelSize: Theme.sizeBodySmall
                                    hintSize: 13
                                    hintRich: root.studioWanted
                                    hint: root.studioWanted ? S.s_mo_05587fd6 + Logic.whereHtml(root.sync || ({}), true, String(Theme.text)) + S.s_tren_thiet_bi_da_ghep_de_lam_sach_tu_xa_b780f10e
                                        : S.s_tat_thiet_bi_da_ghep_chi_tai_va_nghe_sach_284777c7
                                    checked: root.studioWanted
                                    switchItem.enabled: root.pendingStudio === null
                                    onToggled: value => { if (value) studioDialog.show(); else root.setStudio(false) }
                                }
                            }
                            DevicesFold {
                                objectName: "connectionFold"
                                width: parent.width
                                storageKey: "phone-sync.connection"
                                title: S.s_ket_noi_02ca3cba
                                summary: S.s_dia_chi_va_bluetooth_affb4f78
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
                                            text: !root.sync || !root.sync.bluetooth ? "" : TextWrap.pretty(root.sync.bluetooth.running
                                                ? S.s_bluetooth_dien_thoai_da_ghep_noi_duoc_ca_k_b6eea9f5 + (root.sync.bluetooth.connections ? " - " + root.sync.bluetooth.connections + S.s_dang_ket_noi_f8bc93c8 : "") + "."
                                                : root.sync.bluetooth.error)
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
                                            text: S.s_dien_thoai_khong_thay_may_nay_chon_nhap_di_55b69c24 + Logic.whereHtml(root.sync || ({}), false, String(Theme.text)) + "."
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
                                    text: S.s_ngoai_nha_nghe_sach_da_tai_hoac_noi_mang_r_43556c4f
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
            title: S.s_may_da_ghep_c2103758
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
                        font.pixelSize: 14
                        text: S.s_chua_co_thiet_bi_app_android_file_b9da7146 + "<span style='font-weight:500;color:" + Theme.text + S.s_apk_span_o_d607c209
                            + "<span style='font-weight:500;color:" + Theme.text + S.s_github_com_ntanhpro1221_abook_releases_spa_cbf121ce
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
        title: S.s_bat_studio_tu_xa_46f8566d
        description: S.s_bat_quyen_rieng_cho_tung_thiet_bi_de_mo_st_c9ba843b
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: S.s_de_sau_9be0a7ab; onClicked: studioDialog.dismiss() }
            Button { text: S.s_cho_phep_f1a437f5; busy: root.pendingStudio !== null; onActivated: { root.setStudio(true); studioDialog.dismiss() } }
        }
    }
    Modal {
        id: removeDialog
        objectName: "removeDialog"
        property string targetId: ""
        property string targetName: ""
        title: S.s_bo_ghep_9139fc92 + (targetName || S.s_thiet_bi_37816a2c) + "?"
        description: S.s_dung_tai_va_dong_bo_giu_sach_da_tai_b948aef5
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: S.s_de_nguyen_2f029b4a; onClicked: removeDialog.dismiss() }
            Button { kind: "danger"; text: S.s_bo_ghep_64f921f9; onClicked: { root.revoke(removeDialog.targetId, removeDialog.targetName); removeDialog.dismiss() } }
        }
    }
    Modal {
        id: renameDialog
        objectName: "renameDialog"
        property string targetId: ""
        property string draft: ""
        property bool focusPending: false
        onShownChanged: if (open && focusPending && shown > 0) { focusPending = false; field.forceActiveFocus() }
        title: S.s_doi_ten_thiet_bi_102b76be
        description: S.s_ten_hien_o_danh_sach_thiet_bi_da_ghep_cua_4261490a
        footer: Row {
            anchors.right: parent.right
            spacing: 8
            Button { kind: "ghost"; text: S.s_de_nguyen_2f029b4a; onClicked: renameDialog.dismiss() }
            Button { objectName: "renameSave"; text: S.s_luu_e91f26c0; enabled: renameDialog.draft.trim() !== ""; busy: root.renameBusy; onActivated: renameDialog.save() }
        }
        function save() { if (draft.trim() !== "" && !root.renameBusy) root.rename(targetId, draft.trim()) }
        FormField {
            id: field
            objectName: "renameField"
            width: parent.width
            label: S.s_ten_thiet_bi_525223a8
            onTextChanged: { if (text.length > 80) text = text.slice(0, 80); else renameDialog.draft = text }
            onAccepted: renameDialog.save()
        }
    }
}
