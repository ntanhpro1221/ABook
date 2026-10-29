import QtQuick
import ABook

// Nội dung các tab đã chuyển sang Qt nằm dưới hàng tab của dự án: Việc cần duyệt (Yêu cầu thiết bị + hộp việc), Cần nghe lại, và mục Cách đọc tên của tab Nhân vật. Chỉ dựng phần của tab đang mở -
// tab khác không tốn gì và không hỏi gì (WorkStore chỉ hỏi danh sách đầy đủ khi tab của nó mở). Nhảy sang tab khác từ một thẻ phát `jumped`; ProjectScreen đổi tab và nhớ nơi về.
Item {
    id: root
    objectName: "studioPanels"
    property var work: null
    property string tab: "chapters"
    property string workKind: "all"
    property string workCard: ""
    property string nameParam: ""
    property bool focusNames: false
    signal kindChosen(string kind)
    signal jumped(string tab, string from, string card, string name, bool names)
    signal revealRequested(var target)
    readonly property bool hosted: tab === "work" || tab === "review" || tab === "cast"
    height: loader.item ? loader.item.height : 0

    Loader {
        id: loader
        width: parent.width
        sourceComponent: root.tab === "work" ? workPanel : root.tab === "review" ? reviewPanel : root.tab === "cast" ? castPanel : null
    }

    Component {
        id: workPanel
        Column {
            width: parent ? parent.width : 600
            PhoneEdits { work: root.work }
            WorkInbox {
                work: root.work
                book: root.work ? root.work.book : null
                kind: root.workKind
                focusKey: root.workCard
                onKindChosen: value => root.kindChosen(value)
                onOpenReview: card => root.jumped("review", "work", card, "", false)
                onOpenScript: (chapterId, stableId, pick, card) => root.jumped("script", "work", card, "", false)
                onOpenNames: (name, card) => root.jumped("cast", "work", card, name, true)
                onRevealRequested: target => root.revealRequested(target)
            }
        }
    }
    Component {
        id: reviewPanel
        ReviewQueue {
            work: root.work
            active: root.tab === "review"
            onOpenScript: (chapterId, stableId) => root.jumped("script", "review", "", "", false)
            onRevealRequested: target => root.revealRequested(target)
        }
    }
    Component {
        id: castPanel
        NameReadings {
            work: root.work
            jump: root.focusNames
            name: root.nameParam
            onRevealRequested: target => root.revealRequested(target)
        }
    }
}
