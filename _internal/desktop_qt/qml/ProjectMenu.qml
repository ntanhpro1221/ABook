import QtQuick
import ABook

// Bảng "…" của Studio (DropdownMenu của ProjectScreen.tsx): một danh sách mục {key, icon, text, danger, disabled, hint} hay vạch {sep: true} do
// StudioLogic dựng; chọn một mục thì bảng khép lại rồi phát `picked(key)`. Là một lớp của ngăn xếp Back (Popover).
Popover {
    id: root
    property var items: []
    signal picked(string key)
    panelWidth: 248
    pad: Theme.s8
    Column {
        width: parent.width
        Repeater {
            model: root.items
            delegate: Loader {
                required property var modelData
                width: parent.width
                sourceComponent: modelData.sep ? line : row
                Component {
                    id: row
                    StudioMenuRow {
                        objectName: "menu_" + modelData.key
                        width: parent.width
                        text: modelData.text
                        icon: modelData.icon
                        hint: modelData.hint || ""
                        danger: Boolean(modelData.danger)
                        enabled: !modelData.disabled
                        onClicked: { root.close(); root.picked(modelData.key) }
                    }
                }
                Component {
                    id: line
                    Item { width: parent.width; height: 9; Rectangle { y: 4; width: parent.width; height: 1; color: Theme.line } }
                }
            }
        }
    }
}
