import QtQuick
import ABook

Popover {
    id: root
    objectName: "outputPicker"
    panelWidth: 320
    onOpenChanged: if (open) OutputDevices.refresh()
    Connections { target: Player; function onLoadedChanged() { if (!Player.loaded) root.close() } }
    Column {
        width: parent.width; spacing: Theme.s8
        Text { width: parent.width; text: "Thiết bị phát"; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        Repeater {
            model: OutputDevices.devices
            MenuRow {
                required property var modelData
                objectName: "output_" + modelData.id
                width: parent.width; text: modelData.name
                selected: OutputDevices.selected === modelData.id
                icon: selected ? "check" : ""
                enabled: !OutputDevices.busy
                onClicked: OutputDevices.select(modelData.id)
            }
        }
        Text { objectName: "outputError"; width: parent.width; visible: text !== ""; text: OutputDevices.error; wrapMode: Text.Wrap; color: Theme.danger; font.pixelSize: Theme.sizeCaption }
    }
}
