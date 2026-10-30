import QtQuick
import ABook
import "StudioMusicLogic.js" as Logic

// Một đoạn nhạc trong tab Nhạc nền (dòng <li> của MusicTab.tsx): giờ bắt đầu–kết thúc, không khí (+ nhãn "AI" khi AI đã đọc đoạn), bài đang dùng
// (hay "tiếp bài của đoạn trên" / im lặng), rồi MỘT nút chính "Đổi bài" + "…" - cột nút thẳng hàng ở mọi dòng. "Đổi bài" mở tại chỗ ngay dưới dòng.
// Hàng rộng: bốn cột trên một dòng; hàng hẹp: giờ + không khí, rồi bài, rồi nút (như flex-wrap của bản web dưới sm).
Column {
    id: root
    property var scene: ({})
    property var scenes: []
    property int position: 0
    property var plan: null
    property var taxonomy: ({})
    property bool open: false               // "Đổi bài" đang mở ở đoạn này
    property bool busy: false
    property string choosing: ""
    property string previewing: ""
    property var store: null
    property string bookId: ""
    property bool canPreviewMine: true
    property bool remote: false
    property int libraryVersion: 0
    signal swapRequested()
    signal menuRequested(Item anchor)
    signal choose(string link)
    signal preview(string link)
    signal stopPreview()

    readonly property bool wide: width >= 600
    readonly property bool follows: Logic.isContinuation(scene)
    readonly property var swap: Logic.swapButton(scene)
    readonly property var track: scene.link && plan ? (plan.tracks || {})[scene.link] : undefined
    readonly property string ai: Logic.aiNote(scene)
    readonly property real gap: 16
    readonly property real pad: follows ? 6 : 10

    Rectangle { width: parent.width; height: 1; color: Theme.line; visible: root.position > 0 }
    Item {
        id: line
        width: parent.width
        height: root.wide ? Math.max(32, cell.height) + 2 * root.pad
                          : root.pad + Math.max(timeText.height, mood.height) + 6 + cell.height + 6 + buttons.height + root.pad
        Text {
            id: timeText
            objectName: "sceneTime"
            y: root.wide ? root.pad + (Math.max(32, cell.height) - height) / 2 : root.pad
            width: 112
            text: Logic.sceneRange(root.scenes, root.position)
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.features: {"tnum": 1}
            wrapMode: Text.Wrap
        }
        Row {
            id: mood
            x: 112 + root.gap
            y: timeText.y
            width: 128
            spacing: 6
            Text {
                id: moodText
                objectName: "sceneMood"
                width: Math.min(implicitWidth, mood.width - (badge.visible ? badge.width + mood.spacing : 0))
                text: Logic.moodOf(root.scene, root.taxonomy.emotions)
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Rectangle {
                id: badge
                objectName: "sceneAi"
                visible: root.ai !== ""
                width: aiText.implicitWidth + 8
                height: aiText.implicitHeight + 4
                radius: Theme.radiusControl
                color: Theme.sunken
                Accessible.role: Accessible.StaticText
                Accessible.name: "AI"
                Accessible.description: root.ai
                Text { id: aiText; anchors.centerIn: parent; text: "AI"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
            }
        }
        Column {
            id: cell
            objectName: "sceneTrack"
            x: root.wide ? mood.x + mood.width + root.gap : 0
            y: root.wide ? root.pad + (Math.max(32, height) - height) / 2 : root.pad + Math.max(timeText.height, mood.height) + 6
            width: root.wide ? line.width - x - root.gap - buttons.width : line.width
            spacing: 2
            Row {
                width: parent.width
                visible: root.follows
                spacing: 4
                Icon { name: "corner-down-right"; size: 14; color: Theme.text2; y: 2 }
                Text {
                    width: parent.width - 18
                    text: Logic.CONTINUED_NOTE
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
            Text {
                width: parent.width
                visible: !root.follows && !root.scene.link
                text: root.scene.silenced ? "Im lặng (bạn chọn)" : "Im lặng - không bài nào đủ hợp"
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Flow {
                width: parent.width
                visible: !root.follows && !!root.scene.link
                spacing: 6
                Icon { name: "eighth-note"; size: 16; color: Theme.accentText; y: 2 }
                Text {
                    width: Math.min(implicitWidth, parent.width - 22)
                    text: {
                        const dim = Qt.color(Theme.text2).toString()
                        const title = (root.track && root.track.title) || "Bài nhạc"
                        const by = root.track && root.track.creator ? "<font color=\"" + dim + "\"> · " + root.esc(root.track.creator) + "</font>" : ""
                        return root.esc(title) + by
                    }
                    textFormat: Text.StyledText
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                }
                Rectangle {
                    visible: !!root.track && root.track.source === "local"
                    width: mineText.implicitWidth + 12
                    height: mineText.implicitHeight + 4
                    radius: Theme.radiusControl
                    color: Theme.sunken
                    Text { id: mineText; anchors.centerIn: parent; text: "Nhạc của tôi"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                }
                Icon {
                    objectName: "scenePinned"
                    visible: !!root.scene.pinned
                    name: "pin"; size: 14; color: Theme.text2; y: 3
                    Accessible.role: Accessible.Graphic
                    Accessible.name: "Đã ghim"
                }
            }
            Text {
                width: parent.width
                visible: !root.follows && !!root.scene.link && !!root.scene.pinUnavailable
                text: "Bài bạn ghim không còn trên máy này - đoạn dùng bài khác."
                color: Theme.warning
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
        Row {
            id: buttons
            x: root.wide ? line.width - width : -12
            y: root.wide ? root.pad + (Math.max(32, cell.height) - height) / 2 : cell.y + cell.height + 6
            spacing: 4
            Button {
                id: swapButton
                objectName: "sceneSwap"
                text: root.swap.text
                icon: "shuffle"; kind: "ghost"; size: "sm"
                anchors.verticalCenter: parent.verticalCenter
                Accessible.description: root.swap.title
                Accessible.checkable: true
                Accessible.checked: root.open
                onActivated: root.swapRequested()
            }
            Item { visible: root.follows && root.wide; width: 32; height: 32 }
            IconButton {
                id: more
                objectName: "sceneMore"
                visible: !root.follows
                width: 32
                height: 32
                anchors.verticalCenter: parent.verticalCenter
                icon: "ellipsis"
                iconSize: 16
                ink: Theme.text2
                hoverInk: Theme.text
                enabled: !root.busy
                Accessible.name: "Thêm tuỳ chọn cho đoạn này"
                onClicked: root.menuRequested(more)
            }
        }
    }
    function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
    // "Đổi bài" chỉ dựng khi mở lần đầu (sách dài có hàng trăm đoạn), rồi giữ để khép lại có chuyển động
    property bool swapMade: false
    onOpenChanged: if (open) swapMade = true
    Collapse {
        width: parent.width
        open: root.open
        Loader {
            width: parent.width
            active: root.swapMade
            sourceComponent: StudioMusicSwap {
                topPadding: 10
                bottomPadding: 10
                store: root.store
                bookId: root.bookId
                sceneKey: root.scene.key || ""
                active: root.open
                busy: root.busy
                choosing: root.choosing
                previewing: root.previewing
                canPreviewMine: root.canPreviewMine
                remote: root.remote
                libraryVersion: root.libraryVersion
                onPreview: link => root.preview(link)
                onStopPreview: root.stopPreview()
                onChoose: link => root.choose(link)
                Component.onCompleted: if (active && generation === 0) load()   // onActiveChanged có thể đã hỏi
            }
        }
    }
}
