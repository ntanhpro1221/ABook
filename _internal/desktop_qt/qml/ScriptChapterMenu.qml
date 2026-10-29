import QtQuick
import ABook
import "ScriptLogic.js" as S

// Chọn chương của tab Kịch bản (ChapterMenu của ScriptTab.tsx): bảng của app thay ô chọn gốc - dấu chọn ở chương đang xem, kèm điều KHÁC giữa các
// chương (chỉ lời kể, chỗ nghi, đã quyết). Mở ra thì cuộn tới chương đang xem (giữa khung), không bắt đầu ở chương đầu của danh sách dài.
Popover {
    id: root
    property var chapters: []
    property int chapterId: 0
    property bool narrow: false
    signal chosen(int id)
    panelWidth: 480
    pad: Theme.s8
    maxHeight: 384
    onOpenChanged: if (open) Later.call(root, centerChecked)
    function centerChecked() {
        const row = rows.itemAt(chapters.findIndex(chapter => chapter.chapterId === chapterId))
        if (!row) return
        for (let node = row.parent; node; node = node.parent) {
            if (node.contentY !== undefined && node.contentHeight !== undefined) {
                const y = row.mapToItem(node.contentItem, 0, 0).y
                node.contentY = Math.max(0, Math.min(node.contentHeight - node.height, y - node.height / 2 + row.height / 2))
                return
            }
        }
    }
    Column {
        width: parent.width
        Repeater {
            id: rows
            model: root.chapters
            delegate: Interactive {
                id: row
                required property var modelData
                readonly property bool selected: modelData.chapterId === root.chapterId
                objectName: "scriptChapterOption"
                width: parent.width
                height: Math.max(36, words.height + 12)
                pressScaling: false
                Accessible.role: Accessible.RadioButton
                Accessible.name: S.chapterLabel(modelData)
                Accessible.checked: selected
                function choose() { root.close(); if (!row.selected) root.chosen(row.modelData.chapterId) }
                onClicked: choose()
                Keys.onReturnPressed: choose()
                Keys.onSpacePressed: choose()
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: row.hovered || row.activeFocus ? 1 : 0 }
                Icon {
                    x: 8
                    anchors.verticalCenter: parent.verticalCenter
                    name: "check"
                    size: 16
                    color: Theme.accentText
                    opacity: row.selected ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Item {
                    id: words
                    x: 32
                    width: parent.width - x - 8
                    height: Math.max(title.height, extras.height)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        id: title
                        objectName: "scriptChapterTitle"
                        width: parent.width - (extras.visible ? extras.width + 8 : 0)
                        text: S.chapterLabel(row.modelData)
                        color: row.selected ? Theme.accentText : Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    Text {
                        id: extras
                        visible: !root.narrow && text !== ""
                        anchors.right: parent.right
                        width: Math.min(implicitWidth, parent.width / 2)
                        text: S.chapterExtras(row.modelData)
                        color: Theme.text2
                        horizontalAlignment: Text.AlignRight
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                    }
                }
            }
        }
    }
}
