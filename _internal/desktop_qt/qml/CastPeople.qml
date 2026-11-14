import QtQuick
import ABook

// Lưới người của một nhóm (grid gap-x-8 của CastList): một cột ở khổ hẹp, hai cột khi đủ rộng. Mỗi người nằm trong một Collapse nên người của các chương
// sau mở / khép tại chỗ ("Hiện / Ẩn chương sau"), không nhảy cả danh sách. `shown(person)` quyết người nào đang hiện.
WindowedRows {
    id: root
    property string bookId: ""
    property string peer: ""
    property var people: []
    property var caps: ({})
    property var shown: person => true
    property Component below: null
    readonly property int columns: width >= 560 ? 2 : 1
    signal request(string kind, var person)
    signal menuRequested(Item anchor, var person)
    rows: {
        const result = []
        const visiblePeople = people.filter(person => root.shown(person))
        for (let i = 0; i < visiblePeople.length; i += columns) result.push(visiblePeople.slice(i, i + columns))
        return result
    }
    estimate: 160
    spacing: Theme.s32
    delegate: Component {
        Row {
            id: line
            readonly property var rowData: parent.rowData
            readonly property int rowIndex: parent.rowIndex
            width: root.width
            spacing: Theme.s32
            Repeater {
                model: line.rowData
                Collapse {
                    id: cell
                    required property var modelData
                    objectName: "castCell"
                    width: (root.width - (root.columns - 1) * Theme.s32) / root.columns
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
                    // A caller may supply a note under a person, with a `person` property.
                    Loader {
                        width: cell.width
                        active: root.below !== null
                        sourceComponent: root.below
                        onLoaded: item.person = Qt.binding(function() { return cell.modelData })
                    }
                }
            }
        }
    }
}
