import QtQuick
import ABook
import "PrecastLogic.js" as Precast

Item {
    id: root
    property alias store: store
    signal projectRequested(string bookId)
    signal precastRequested(string bookId)
    signal allRequested()
    // Dự án đang mở ở Studio ("" = không): đang ở chính trang ấy thì dải mời trên trang đã nói, không mời thêm
    property string openProject: ""
    implicitHeight: column.implicitHeight
    readonly property var live: store.books.filter(b => b.running || b.starting || b.queuePosition != null)
        .sort((a, b) => (a.queuePosition || 0) - (b.queuePosition || 0))
    onLiveChanged: {
        const next = live.slice(0, 3)
        for (let i = rows.count - 1; i >= 0; --i) {
            const item = next.find(b => b.id === rows.get(i).book.id)
            rows.setProperty(i, "alive", !!item)
            if (item) rows.setProperty(i, "book", item)
        }
        for (let i = 0; i < next.length; ++i) {
            let at = -1
            for (let j = 0; j < rows.count; ++j) if (rows.get(j).book.id === next[i].id) at = j
            if (at < 0) rows.insert(i, {book: next[i], alive: true})
            else if (at !== i) rows.move(at, i, 1)
        }
        prune.restart()
    }
    ListModel { id: rows; dynamicRoles: true }
    Timer { id: prune; interval: Theme.reduceMotion ? Theme.motionFast : Theme.motionMediumOut; onTriggered: { for (let i = rows.count - 1; i >= 0; --i) if (!rows.get(i).alive) rows.remove(i) } }
    StudioStore { id: store; active: Nav.uiVisible && root.visible; libraryWanted: active; onBooksChanged: root.invite() }
    // Lời mời duyệt trước khi thu (usePrecastInvites): nhớ mốc đã mời của từng cuốn, mời bằng lời báo 30 giây có nút "Duyệt" mở thẳng tab ấy
    function invite() {
        if (store.peer) return
        for (const book of Precast.invites(store.books, id => Platform.setting("precast.invited." + id, "") || null)) {
            Platform.setSetting("precast.invited." + book.id, String(book.precast.announcedAt))
            if (book.id === openProject) continue
            const id = book.id
            Api.toast(Precast.inviteText(book), {duration: 30000, action: {label: "Duyệt", run: () => root.precastRequested(id)}})
        }
    }
    Connections { target: Nav; function onUiVisibleChanged() { if (Nav.uiVisible && root.visible) store.loadLibrary() } }
    Column {
        id: column; width: parent.width; spacing: Theme.s4
        Collapse {
            width: parent.width; open: store.libraryLoading
            Text { objectName: "sidebarLoading"; width: parent.width; text: "Đang tải tiến độ"; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        Collapse {
            width: parent.width; open: !!store.libraryError && !store.libraryData
            Button { width: parent.width; wrap: true; kind: "ghost"; text: "Bạn hãy thử tải lại tiến độ."; onClicked: store.loadLibrary() }
        }
        Repeater {
            model: rows
            Collapse {
                id: entry
                required property var book
                required property bool alive
                required property int index
                width: column.width; open: alive
                Interactive {
                id: row
                readonly property var modelData: entry.book
                objectName: "sidebarProject_" + entry.index
                width: column.width; height: Math.max(32, detail.implicitHeight) + 2 * Theme.s8
                Accessible.name: modelData.title
                onClicked: root.projectRequested(modelData.id)
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.sunken; opacity: row.hovered || row.pressed ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } } }
                CoverView { x: Theme.s8; y: Theme.s8; width: 32; height: 32; radius: Theme.radiusControl; title: row.modelData.title; coverKey: row.modelData.cover ? row.modelData.id + "/" + (row.modelData.cover.version || 0) : "" }
                Icon {
                    objectName: "sidebarStatus_" + entry.index
                    x: Theme.s8 + 40; y: Theme.s8 + 2; size: 12
                    name: row.modelData.queuePosition != null ? "clock" : row.modelData.paused || row.modelData.stopping ? "pause" : "audio-lines"
                    Accessible.name: row.modelData.queuePosition != null ? `Đang chờ ${row.modelData.queuePosition}` : row.modelData.stopping ? "Đang dừng" : row.modelData.paused ? "Đang tạm dừng" : ""
                    color: row.modelData.paused || row.modelData.stopping ? Theme.warning : Theme.accentText
                }
                Column {
                    id: detail; x: Theme.s8 + 60; y: Theme.s8; width: parent.width - x - Theme.s8; spacing: Theme.s4
                    Text { objectName: "sidebarTitle_" + entry.index; width: parent.width; text: row.modelData.title; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                    Row {
                        width: parent.width; spacing: Theme.s8
                        Rectangle {
                            objectName: "sidebarProgress_" + entry.index
                            width: parent.width - percent.width - Theme.s8; height: 3; anchors.verticalCenter: parent.verticalCenter
                            color: Theme.sunken; radius: Theme.radiusControl
                            Accessible.role: Accessible.ProgressBar
                            Accessible.name: `Tiến độ: ${row.modelData.title}`
                            Accessible.description: percent.text
                            Rectangle { width: parent.width * Math.max(0, Math.min(1, row.modelData.progress ? row.modelData.progress.overall : 0)); height: parent.height; radius: Theme.radiusControl; color: row.modelData.queuePosition != null ? Theme.text3 : Theme.accent; Behavior on width { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium } } }
                        }
                        Text { id: percent; text: row.modelData.queuePosition != null ? "Chờ" : row.modelData.starting ? "…" : Math.round((row.modelData.progress ? row.modelData.progress.overall : 0) * 100) + "%"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                    }
                }
                }
            }
        }
        Collapse { width: parent.width; open: root.live.length > 3; Button { objectName: "sidebarAll"; width: parent.width; wrap: true; kind: "ghost"; text: "Xem tất cả"; onClicked: root.allRequested() } }
    }
}
