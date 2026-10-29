import QtQuick
import ABook
import "WorkLogic.js" as W
import "StudioLogic.js" as Studio

// Hộp "Việc cần duyệt" (WorkInbox.tsx, docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự quyết và dây chuyền KHÔNG chờ ai - đây là nơi người sửa ít nhất
// mà được nhiều nhất. Lời mở đầu theo trạng thái sách, thanh lọc loại việc, thẻ (40 một trang), rồi ba nhóm phụ: Đã quyết (chờ áp dụng), Chờ phân tích lại, Đã ghi.
// Phím tắt chữ (tắt được ở Cài đặt): J / K chọn thẻ, 1-9 bấm lựa chọn thứ N của thẻ ấy, Esc bỏ chọn - duyệt cả trăm thẻ không cần chuột. Quyết xong thì thẻ rời danh sách và
// tiêu điểm sang thẻ kế (workFocus.ts) thay vì rơi về nền.
FocusScope {
    id: root
    objectName: "workInbox"
    property var work: null
    property var book: null
    property string kind: "all"
    property string focusKey: ""
    property int shown: W.PAGE
    property int cursor: -1
    property string lastCard: ""
    property var snapshot: null
    property bool focused: false
    property bool voicePick: false              // có chỗ chọn giọng để mở từ thẻ giọng (Studio chưa có thì thẻ không mời)
    signal kindChosen(string kind)
    signal openReview(string card)
    signal openScript(int chapterId, string stableId, bool pick, string card)
    signal openNames(string name, string card)
    signal pickVoice(var person)
    signal revealRequested(var item)

    readonly property var query: work ? work.work : null
    readonly property var all: query && query.data ? query.data.items : null
    readonly property var group: W.groups(all || [], ({}), kind)
    readonly property var cards: group.filtered.slice(0, shown)
    readonly property string activeKey: cursor < 0 || cards.length === 0 ? "" : cards[Math.min(cursor, cards.length - 1)].key
    readonly property bool keysOn: visible && Nav.uiVisible && !Nav.popupOpen && Api.preferences.letterShortcuts !== false
    readonly property bool wide: width >= 640
    readonly property bool numbersOn: keysOn && cursor >= 0 && !typing()
    width: parent ? parent.width : 600
    height: stack.height

    // Quyết xong việc cuối của loại đang lọc: loại ấy biến khỏi thanh lọc - về "Tất cả", đừng để danh sách trống không lời
    readonly property string active: group.active
    onActiveChanged: Later.call(root, function() { if (root.all !== null && root.kind !== root.active) { root.kind = root.active; root.kindChosen(root.active) } })   // sau khi group tính xong: đổi kind ngay trong lúc tính là vòng lặp
    onAllChanged: {
        if (all === null || focusKey === "" || focused) return
        focused = true
        const index = (group ? group.filtered : []).findIndex(function(item) { return item.key === focusKey })
        if (index >= shown) shown = Math.ceil((index + 1) / W.PAGE) * W.PAGE
        Later.call(root, function() { root.focusCard(root.focusKey, false) })
    }

    // ---- thẻ và tiêu điểm ----
    function findCard(key) {
        let found = null
        function walk(node) {
            if (found) return
            for (const child of node.children) {
                if (child.objectName === "workCard" && child.key === key) { found = child; return }
                walk(child)
            }
        }
        walk(stack)
        return found
    }
    function cardKey(node) {
        for (let n = node; n; n = n.parent) if (n.objectName === "workCard") return n.key
        return ""
    }
    function inside(node) {
        for (let n = node; n; n = n.parent) if (n === root) return true
        return false
    }
    function listsNow() {
        return {open: cards.map(function(item) { return item.key }), decided: group.decided.map(function(item) { return item.key })}
    }
    function focusCard(key, take) {
        if (key === "end") { (endLine.visible ? endLine : lead).forceActiveFocus(); return }
        const card = findCard(key)
        if (!card) return
        if (take !== false) {
            const buttons = card.choices()
            if (buttons.length > 0) buttons[0].forceActiveFocus(); else card.forceActiveFocus()
        }
        revealRequested(card)
    }
    function select(index) {
        if (cards.length === 0) return
        cursor = Math.min(Math.max(index, 0), cards.length - 1)
        focusCard(cards[cursor].key, true)
    }
    function moveCursor(step) { select(cursor < 0 ? 0 : cursor + step) }
    function chooseNumber(number) {
        if (cursor < 0 || cards.length === 0) return false
        const card = findCard(activeKey)
        const buttons = card ? card.choices() : []
        if (number > buttons.length) return false
        buttons[number - 1].clicked()
        return true
    }
    function typing() {
        const focus = Window.window ? Window.window.activeFocusItem : null
        return Boolean(focus) && typeof focus.cursorPosition === "number"
    }
    // Thẻ giữ tiêu điểm rời danh sách (quyết, hoàn tác): tiêu điểm sang thẻ kế thay vì rơi về nền
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            const now = root.Window.window.activeFocusItem
            const key = root.cardKey(now)
            if (key !== "") { root.lastCard = key; root.snapshot = root.listsNow(); return }
            if (root.lastCard === "" || !root.snapshot) return
            if (now && now !== root.Window.window.contentItem) { root.lastCard = ""; return }
            const target = W.focusAfterChange(root.snapshot, root.listsNow(), root.lastCard)
            root.lastCard = ""
            if (target !== null) Later.call(root, function() { root.focusCard(target, true) })
        }
    }
    Keys.onShortcutOverride: event => { if (event.key === Qt.Key_Escape && root.cursor >= 0) event.accepted = true }
    Keys.onEscapePressed: event => { if (root.cursor >= 0) { root.cursor = -1; event.accepted = true } }
    Shortcut { sequences: ["J"]; enabled: root.keysOn && root.cards.length > 0 && !root.typing(); onActivated: root.moveCursor(1) }
    Shortcut { sequences: ["K"]; enabled: root.keysOn && root.cards.length > 0 && !root.typing(); onActivated: root.moveCursor(-1) }
    Shortcut { sequences: ["1"]; enabled: root.numbersOn; onActivated: root.chooseNumber(1) }
    Shortcut { sequences: ["2"]; enabled: root.numbersOn; onActivated: root.chooseNumber(2) }
    Shortcut { sequences: ["3"]; enabled: root.numbersOn; onActivated: root.chooseNumber(3) }
    Shortcut { sequences: ["4"]; enabled: root.numbersOn; onActivated: root.chooseNumber(4) }
    Shortcut { sequences: ["5"]; enabled: root.numbersOn; onActivated: root.chooseNumber(5) }
    Shortcut { sequences: ["6"]; enabled: root.numbersOn; onActivated: root.chooseNumber(6) }
    Shortcut { sequences: ["7"]; enabled: root.numbersOn; onActivated: root.chooseNumber(7) }
    Shortcut { sequences: ["8"]; enabled: root.numbersOn; onActivated: root.chooseNumber(8) }
    Shortcut { sequences: ["9"]; enabled: root.numbersOn; onActivated: root.chooseNumber(9) }

    Column {
        id: stack
        width: parent.width
        EditBookSkeleton {
            objectName: "workSkeleton"
            visible: root.query !== null && root.query.loading
            width: parent.width
            y: 24
            shape: "rows"
            count: 4
            label: "Đang tải việc duyệt"
        }
        EditBookError {
            objectName: "workError"
            width: parent.width
            open: root.query !== null && root.query.error !== null && root.query.data === null
            message: "Bạn hãy kiểm tra kết nối rồi tải lại việc cần duyệt."
            onRetry: root.query.load()
        }
        EmptyState {
            objectName: "workEmpty"
            visible: root.all !== null && root.all.length === 0
            width: parent.width
            topPadding: 40
            bottomPadding: 40
            icon: "audio-lines"
            title: "Không còn việc duyệt"
            text: "Máy chắc chắn về mọi thứ đã làm tới giờ."
        }
        Column {
            id: content
            objectName: "workContent"
            visible: root.all !== null && root.all.length > 0
            width: parent.width
            Item { width: 1; height: 20 }
            // Lời mở đầu theo trạng thái sách: "đang chạy tiếp" không hiện cả khi sách đã xong hay đang dừng
            Text {
                id: lead
                objectName: "workLead"
                width: Math.min(parent.width, 768)
                text: root.book ? W.inboxLead(root.book) : ""
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Item { width: 1; height: 16 }
            ChoiceRow {
                objectName: "workFilter"
                width: parent.width
                label: "Loại việc"
                value: root.group.active
                options: W.filterOptions(root.group)
                onPicked: value => { root.kind = value; root.shown = W.PAGE; root.cursor = -1; root.kindChosen(value) }
            }
            WorkBulkKeep { work: root.work; kind: root.group.active; items: root.group.filtered }
            Flow {
                objectName: "workKeys"
                visible: root.wide && root.keysOn
                width: parent.width
                topPadding: 8
                spacing: 6
                LookKbd { text: "J" }
                LookKbd { text: "K" }
                Text { height: 20; verticalAlignment: Text.AlignVCenter; text: "chọn thẻ ·"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                LookKbd { text: "1–9" }
                Text { height: 20; verticalAlignment: Text.AlignVCenter; text: "chọn đáp án ·"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                LookKbd { text: "Esc" }
                Text { height: 20; verticalAlignment: Text.AlignVCenter; text: "bỏ chọn"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
            }
            Item { width: 1; height: 12 }
            StudioRows {
                objectName: "workCards"
                width: parent.width
                items: root.cards
                keyField: "key"
                delegate: cardDelegate
            }
            Collapse {
                width: parent.width
                open: root.group.filtered.length > root.shown
                Item {
                    width: parent.width
                    height: 16 + more.height
                    Button {
                        id: more
                        objectName: "workShowMore"
                        y: 16
                        size: "sm"
                        kind: "ghost"
                        text: "Xem thêm " + Math.min(W.PAGE, root.group.filtered.length - root.shown) + " việc"
                        onClicked: root.shown += W.PAGE
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.group.open.length === 0
                Text {
                    id: endLine
                    objectName: "workEnd"
                    topPadding: 16
                    width: parent.width
                    text: W.endLine(root.group, root.work ? root.work.pendingNote : "")
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
            WorkSection {
                objectName: "workDecided"
                present: root.group.decided.length > 0
                title: W.decidedSummary(root.group.decided, root.group.waiting)
                StudioRows { width: parent.width; items: root.group.decided; keyField: "key"; delegate: cardDelegate }
            }
            WorkSection {
                objectName: "workLater"
                present: root.group.later.length > 0
                gap: 16
                title: "Chờ phân tích lại"
                Text {
                    width: Math.min(parent.width, 768)
                    topPadding: 8
                    text: "Chỉ áp khi phân tích lại; không chặn sách chạy tiếp."
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                StudioRows { width: parent.width; items: root.group.later; keyField: "key"; delegate: cardDelegate }
            }
            WorkSection {
                objectName: "workRedo"
                present: root.group.redo.length > 0
                gap: 16
                title: "Đã ghi"
                StudioRows { width: parent.width; items: root.group.redo; keyField: "key"; delegate: cardDelegate }
            }
        }
    }

    Component {
        id: cardDelegate
        WorkCard {
            property var modelData: ({})
            work: root.work
            item: modelData || ({})
            active: Boolean(modelData) && modelData.key === root.activeKey
            scriptLinks: Boolean(modelData) && !modelData.requested
            namesLink: true
            voicePick: root.voicePick
            onOpenReview: card => root.openReview(card)
            onOpenScript: (chapterId, stableId, pick, card) => root.openScript(chapterId, stableId, pick, card)
            onOpenNames: (name, card) => root.openNames(name, card)
            onPickVoice: person => root.pickVoice(person)
        }
    }
}
