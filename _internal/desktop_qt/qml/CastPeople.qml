import QtQuick
import ABook

// Lưới người của một nhóm (grid gap-x-8 của CastList): một cột ở khổ hẹp, hai cột khi đủ rộng. Mỗi người nằm trong một Collapse nên người của các chương
// sau mở / khép tại chỗ ("Hiện / Ẩn chương sau"), không nhảy cả danh sách. `shown(person)` quyết người nào đang hiện.
Flow {
    id: root
    property string bookId: ""
    property string peer: ""
    property var people: []
    property var caps: ({})
    property var shown: person => true
    property Component below: null
    readonly property int columns: width >= 560 ? 2 : 1
    readonly property real cellWidth: (width - (columns - 1) * spacing) / columns
    signal request(string kind, var person)
    signal menuRequested(Item anchor, var person)
    spacing: Theme.s32

    Repeater {
        model: root.people
        Collapse {
            id: cell
            required property var modelData
            objectName: "castCell"
            width: root.cellWidth
            open: root.shown(modelData)
            CastPerson {
                width: cell.width
                bookId: root.bookId
                peer: root.peer
                person: cell.modelData
                caps: root.caps
                onRequest: (kind, person) => root.request(kind, person)
                onMenuRequested: (anchor, person) => root.menuRequested(anchor, person)
            }
            // Dòng dưới người (màn "Duyệt trước khi thu": người trùng tên): Component có `property var person`
            Loader {
                width: cell.width
                active: root.below !== null
                sourceComponent: root.below
                onLoaded: item.person = Qt.binding(function() { return cell.modelData })
            }
        }
    }
}
