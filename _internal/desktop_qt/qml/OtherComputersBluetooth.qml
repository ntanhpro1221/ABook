import QtQuick
import ABook
import "DevicesLogic.js" as Logic

// Nút + bảng chọn đường Bluetooth dự phòng của một máy ghép qua Wi-Fi (BluetoothFallback của desktop/OtherComputers.tsx): Wi-Fi vẫn đi
// trước, Bluetooth chỉ khi Wi-Fi hỏng. Nút xanh nhấn khi đã chọn một thiết bị; bảng: nhãn "Đường Bluetooth", các thiết bị đã ghép ở Windows
// (dấu tích đầu dòng ở thiết bị đang chọn), "Không dùng". Bảng là một lớp của Back (Popover).
Item {
    id: root
    property var computer: ({})
    property var devices: []
    property bool busy: false
    property Item overlay: null
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
        tip: "Dự phòng qua Bluetooth…"
        enabled: !root.busy
        Accessible.name: "Dự phòng qua Bluetooth cho " + (root.computer.name || "")
        onClicked: menu.toggle()
    }
    Popover {
        id: menu
        objectName: "bluetoothMenu"
        parent: root.overlay
        anchorItem: button
        panelWidth: 288
        pad: 6
        Column {
            width: parent.width
            Text {
                x: 8
                width: parent.width - 16
                topPadding: 2
                bottomPadding: 4
                text: "Đường Bluetooth"
                color: Theme.text3
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Text {
                x: 8
                width: parent.width - 16
                visible: root.devices.length === 0
                topPadding: 6
                bottomPadding: 6
                text: "Ghép thiết bị trong Cài đặt Windows trước."
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
                    Accessible.name: modelData.name + " · " + Logic.deviceKindLabel(modelData.kind) + (selected ? ", đang chọn" : "")
                    onClicked: { menu.close(); root.choose(modelData.address) }
                    Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: row.hovered ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                    Icon { x: 8; y: 6 + 2; name: "check"; size: 16; color: Theme.accentText; opacity: row.selected ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                    Text {
                        id: label
                        x: 8 + 16 + 8
                        y: 6
                        width: parent.width - x - 8
                        textFormat: Text.RichText
                        text: Logic.esc(modelData.name) + " <span style='color:" + Theme.text3 + "'>· " + Logic.esc(Logic.deviceKindLabel(modelData.kind)) + "</span>"
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
                Accessible.name: "Không dùng"
                onClicked: { menu.close(); root.choose("") }
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: none.hovered && none.enabled ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                Text { id: noneLabel; x: 8 + 16 + 8; y: 6; width: parent.width - x - 8; text: "Không dùng"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            }
        }
    }
}
