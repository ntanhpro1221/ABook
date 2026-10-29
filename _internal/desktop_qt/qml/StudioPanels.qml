import QtQuick
import ABook

// Nội dung các tab đã chuyển sang Qt nằm dưới hàng tab của dự án: Việc cần duyệt (Yêu cầu thiết bị + hộp việc), Cần nghe lại, Nhân vật (dàn người + công tắc tự kể + Cách đọc tên) và Duyệt trước khi thu. Chỉ dựng phần của tab đang mở -
// tab khác không tốn gì và không hỏi gì (WorkStore chỉ hỏi danh sách đầy đủ khi tab của nó mở). Nhảy sang tab khác từ một thẻ phát `jumped`; ProjectScreen đổi tab và nhớ nơi về.
Item {
    id: root
    objectName: "studioPanels"
    property var store: null
    property var book: null
    property var work: null
    property var caps: ({})                     // việc làm được với một người: rename / merge / gender / voice / unmerge / narrator
    property string precastStep: "cast"
    property string tab: "chapters"
    property string workKind: "all"
    property string workCard: ""
    property string nameParam: ""
    property bool focusNames: false
    signal kindChosen(string kind)
    signal jumped(string tab, string from, string card, string name, bool names)
    signal revealRequested(var target)
    signal personRequest(string kind, var person)
    signal personMenu(Item anchor, var person)
    signal precastStepChosen(string step)
    signal precastClosed()
    signal precastOpened()
    signal redoRequested()
    readonly property bool hosted: tab === "work" || tab === "review" || tab === "cast" || tab === "precast"
    height: loader.item ? loader.item.height : 0

    Loader {
        id: loader
        width: parent.width
        sourceComponent: root.tab === "work" ? workPanel : root.tab === "review" ? reviewPanel : root.tab === "cast" ? castPanel : root.tab === "precast" ? precastPanel : null
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
                voicePick: true
                inPrecast: root.work ? root.work.inPrecast : ({})
                onKindChosen: value => root.kindChosen(value)
                onOpenReview: card => root.jumped("review", "work", card, "", false)
                onOpenScript: (chapterId, stableId, pick, card) => root.jumped("script", "work", card, "", false)
                onOpenNames: (name, card) => root.jumped("cast", "work", card, name, true)
                onPickVoice: person => root.personRequest("voice", person)
                onOpenPrecast: root.precastOpened()
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
        Column {
            width: parent ? parent.width : 600
            CastList {
                objectName: "studioCastList"
                width: parent.width
                embedded: true
                active: true
                store: root.store
                bookId: root.book ? root.book.id : ""
                caps: root.caps
                narratorNote: castNote
                onRequest: (kind, person) => root.personRequest(kind, person)
                onMenuRequested: (anchor, person) => root.personMenu(anchor, person)
            }
            NameReadings {
                work: root.work
                jump: root.focusNames
                name: root.nameParam
                onRevealRequested: target => root.revealRequested(target)
            }
        }
    }
    Component {
        id: castNote
        CastNote {
            store: root.store
            book: root.book
            onRedoRequested: root.redoRequested()
        }
    }
    Component {
        id: precastPanel
        PrecastReview {
            store: root.store
            work: root.work
            book: root.book
            caps: root.caps
            step: root.precastStep
            onStepChosen: value => root.precastStepChosen(value)
            onPersonRequest: (kind, person) => root.personRequest(kind, person)
            onMenuRequested: (anchor, person) => root.personMenu(anchor, person)
            onPickVoice: person => root.personRequest("voice", person)
            onOpenReview: card => root.jumped("review", "precast", card, "", false)
            onOpenScript: (chapterId, stableId, pick, card) => root.jumped("script", "precast", card, "", false)
            onOpenNames: (name, card) => root.jumped("cast", "precast", card, name, true)
            onCloseRequested: root.precastClosed()
            onRevealRequested: target => root.revealRequested(target)
        }
    }
}
