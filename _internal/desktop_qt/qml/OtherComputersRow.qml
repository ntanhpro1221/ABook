import "UiStrings.js" as S
import QtQuick
import ABook
import "DevicesLogic.js" as Logic

// Một máy tính / điện thoại đã ghép một chiều trong "Máy tính khác" (hàng của desktop/OtherComputers.tsx): khối gập (tên + "Đã ghép" /
// "Đang chờ" / "Cần kiểm tra"), thân có icon máy tính, dòng trạng thái (đường nối + "thấy ... trước", hay lời báo lỗi dài xuống dòng, hay
// "đang ngủ ... Thôi chờ"), vân tay, rồi các nút: Mở Studio (máy tính) / Chẩn đoán (điện thoại), Bluetooth dự phòng, Hỏi lại thư viện, Bỏ ghép.
// Hàng mới mở ra từ chiều cao 0, hàng đã bỏ ghép khép lại rồi mới gỡ (DevicesRows).
Collapse {
    id: root
    property var rows: null
    property string rowId: ""
    property string json: "{}"
    property bool present: true
    property bool fresh: false
    property bool first: true
    property var devices: []
    property bool busy: false
    property real clock: Date.now() / 1000
    readonly property var computer: JSON.parse(json)
    readonly property bool bluetoothHost: Logic.isBluetoothHost(computer.host)
    property bool entered: !fresh
    signal diagnose(var computer)
    signal openStudio(string id)
    signal refresh()
    signal stopWaiting(string id)
    signal unpair(var computer)
    signal bluetooth(string id, string address)

    open: present && entered
    Component.onCompleted: entered = true
    Timer {
        running: !root.present
        interval: (Theme.reduceMotion ? Theme.motionFast : Theme.motionMediumOut) + 80
        onTriggered: if (root.rows) root.rows.drop(root.rowId)
    }

    Item {
        width: parent.width
        implicitHeight: (root.first ? 0 : 1) + fold.height
        height: implicitHeight
        Rectangle { width: parent.width; height: 1; color: Theme.line; Reveal { shown: !root.first }}
        DevicesFold {
            id: fold
            y: root.first ? 0 : 1
            width: parent.width
            storageKey: "other-computers." + root.rowId
            title: root.computer.name || ""
            summary: root.computer.waking ? S.s_dang_cho_4257d45b : root.computer.error ? S.s_can_kiem_tra_d549619d : S.s_da_ghep_2bd0972f
            Item {
                id: body
                width: parent.width
                readonly property bool inline: 32 + 160 + 12 + group.width <= width
                readonly property real lineHeight: Math.max(40, infoColumn.height)
                height: inline ? lineHeight : lineHeight + 12 + group.height
                Icon { x: 0; y: body.lineHeight / 2 - 10; name: "laptop"; size: 20; color: Theme.text2 }
                Column {
                    id: infoColumn
                    x: 32
                    y: (body.lineHeight - height) / 2
                    width: body.inline ? body.width - 32 - 12 - group.width : body.width - 32
                    // Đang chờ máy ấy dậy
                    Flow {
                        width: parent.width
                        Reveal { shown: Boolean(root.computer.waking) }
                        spacing: 0
                        Item { width: 20; height: 16; Icon { x: 0; y: (parent.height - 14) / 2; name: "moon"; size: 14; color: Theme.text2 } }
                        Text { id: status; text: root.computer.waking ? Logic.wakingLine(root.computer, root.clock) : ""; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeCaption; width: Math.min(implicitWidth, parent.width - 20) }
                        Interactive {
                            id: stopLink
                            x: 8
                            implicitWidth: stopText.implicitWidth + 8
                            implicitHeight: stopText.implicitHeight
                            enabled: !root.busy
                            opacity: enabled ? 1 : 0.6
                            pressScaling: false
                            Accessible.role: Accessible.Button
                            Accessible.name: S.s_thoi_cho_6bf8a752
                            onClicked: root.stopWaiting(root.rowId)
                            Text { id: stopText; x: 8; text: S.s_thoi_cho_6bf8a752; color: Theme.accentText; font.pixelSize: Theme.sizeCaption; font.underline: stopLink.hovered }
                        }
                    }
                    // Lời báo lỗi dài (chứng chỉ máy kia đổi...) xuống dòng cho đọc hết, không cắt giữa chừng.
                    Text {
                        width: parent.width
                        Reveal { shown: !root.computer.waking }
                        text: root.computer.error ? root.computer.error
                            : Logic.connectionRoute(root.computer.connectedVia) + (root.computer.lastSeen ? S.s_u00a0_u00a0thay_f7bb91c5 + Logic.formatRelative(root.computer.lastSeen, root.clock) : "")
                        color: root.computer.error ? Theme.danger : Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                    // 8 ký tự đầu đủ để đối chiếu với máy kia
                    Text {
                        width: parent.width
                        topPadding: 4
                        Reveal { shown: Boolean(root.computer.fingerprint) }
                        text: S.s_van_tay_8abdcdf0 + Logic.formatFingerprint(root.computer.fingerprint).slice(0, 9) + "…"
                        Accessible.description: Logic.formatFingerprint(root.computer.fingerprint)
                        color: Theme.text3
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 12
                    }
                }
                Row {
                    id: group
                    spacing: 4
                    x: body.inline ? body.width - width : body.width - width
                    y: body.inline ? (body.lineHeight - height) / 2 : body.lineHeight + 12
                    // Studio của máy tính ấy ngay trong app này, bằng ghép sẵn có - không ghép lần hai (webui/peer_studio.py).
                    Button { objectName: "openStudio"; Reveal { shown: root.computer.kind === "computer" } size: "sm"; kind: "ghost"; icon: "clapperboard"; text: S.s_mo_studio_84ec0a81; Accessible.name: S.s_mo_studio_cua_57fcc890 + (root.computer.name || ""); onClicked: root.openStudio(root.rowId) }
                    Button { objectName: "diagnose"; Reveal { shown: root.computer.kind === "phone" } size: "sm"; kind: "ghost"; icon: "stethoscope"; text: S.s_chan_doan_906791d5; Accessible.name: S.s_chan_doan_738cc26b + (root.computer.name || ""); onClicked: root.diagnose(root.computer) }
                    OtherComputersBluetooth {
                        Reveal { shown: !root.bluetoothHost }
                        computer: root.computer
                        devices: root.devices
                        busy: root.busy
                        onChoose: address => root.bluetooth(root.rowId, address)
                    }
                    IconButton { objectName: "refreshBooks"; icon: "refresh-cw"; tip: S.s_hoi_lai_thu_vien_bfe2a0e8; enabled: !root.busy; Accessible.name: S.s_hoi_lai_thu_vien_bfe2a0e8; onClicked: root.refresh() }
                    IconButton { objectName: "unpairComputer"; icon: "unplug"; tip: S.s_bo_ghep_9139fc92 + (root.computer.name || ""); Accessible.name: S.s_bo_ghep_9139fc92 + (root.computer.name || ""); onClicked: root.unpair(root.computer) }
                }
            }
        }
    }
}
