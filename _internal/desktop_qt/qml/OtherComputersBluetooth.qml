import "UiStrings.js" as S
import QtQuick
import ABook
import "DevicesLogic.js" as Logic
import "TextWrap.js" as TextWrap

// Nút + bảng chọn đường Bluetooth dự phòng của một máy ghép qua Wi-Fi (BluetoothFallback của desktop/OtherComputers.tsx): Wi-Fi vẫn đi
// trước, Bluetooth chỉ khi Wi-Fi hỏng. Nút xanh nhấn khi đã chọn một thiết bị; bảng: nhãn S.s_qua_bluetooth_983cecc1, các thiết bị đã ghép ở Windows
// (dấu tích đầu dòng ở thiết bị đang chọn), "Không dùng". Bảng là một lớp của Back (Popover).
Item {
    id: root
    property var computer: ({})
    property var devices: []
    property bool busy: false
    readonly property string current: Logic.bluetoothAddress(computer)
    signal choose(string address)
    implicitWidth: button.width
    implicitHeight: button.height

    IconButton {
        id: button
        objectName: "bluetoothButton"
        icon: "bluetooth"
        ink: root.current !== "" ? Theme.accentText : Theme.text2
        hoverInk: root.current !== "" ? Theme.accentText : Theme.text
        tip: S.s_dung_bluetooth_a7d4c199
        enabled: !root.busy
        Accessible.name: S.s_dung_bluetooth_cho_1bd77035 + (root.computer.name || "")
        onClicked: menu.toggle()
    }
    Popover {
        id: menu
        objectName: "bluetoothMenu"
        anchorItem: button
        panelWidth: 288
        pad: 6
        Column {
            width: parent.width
            Text {
                x: 8
                width: parent.width - 16
                topPadding: 4
                bottomPadding: 4
                text: S.s_qua_bluetooth_983cecc1
                color: Theme.text3
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Text {
                x: 8
                width: parent.width - 16
                Reveal { shown: root.devices.length === 0 }
                topPadding: 8
                bottomPadding: 8
                text: S.s_ghep_thiet_bi_trong_cai_dat_windows_truoc_53fc93c2
                color: Theme.text3
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
            Repeater {
                model: root.devices
                Interactive {
                    id: row
                    required property var modelData
                    readonly property bool selected: String(modelData.address).toUpperCase() === root.current
                    width: parent.width
                    implicitHeight: label.height + 12
                    height: implicitHeight
                    pressScaling: false
                    Accessible.role: Accessible.MenuItem
                    Accessible.name: modelData.name + "\u00a0·\u00a0" + Logic.deviceKindLabel(modelData.kind) + (selected ? S.s_dang_chon_19938ba6 : "")
                    onClicked: { menu.close(); root.choose(modelData.address) }
                    Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: row.hovered ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                    Icon { x: 8; y: 6 + 2; name: "check"; size: 16; color: Theme.accentText; opacity: row.selected ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                    Text {
                        id: label
                        x: 8 + 16 + 8
                        y: 6
                        width: parent.width - x - 8
                        textFormat: Text.RichText
                        text: Logic.esc(TextWrap.keepDots(modelData.name)) + "&nbsp;<span style='color:" + Theme.text3 + "'>·&nbsp;" + Logic.esc(Logic.deviceKindLabel(modelData.kind)) + "</span>"
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
            }
            Interactive {
                id: none
                objectName: "bluetoothNone"
                width: parent.width
                implicitHeight: noneLabel.height + 12
                height: implicitHeight
                enabled: root.current !== ""
                opacity: enabled ? 1 : 0.6
                pressScaling: false
                Accessible.role: Accessible.MenuItem
                Accessible.name: S.s_khong_dung_30db3c31
                onClicked: { menu.close(); root.choose("") }
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: none.hovered && none.enabled ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                Text { id: noneLabel; x: 8 + 16 + 8; y: 6; width: parent.width - x - 8; text: S.s_khong_dung_30db3c31; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            }
        }
    }
}
