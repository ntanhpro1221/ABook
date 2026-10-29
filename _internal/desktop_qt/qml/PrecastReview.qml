import QtQuick
import ABook
import "PrecastLogic.js" as P
import "CastLogic.js" as Cast

// Tab "Duyệt trước khi thu" (PrecastReview của studio/PrecastReview.tsx, webui/precast.py, docs/STUDIO_REVIEW.md): ngay khi phân tích xong và trước khi thu tới những chương đầu, dẫn qua đúng
// thứ tự người duyệt cần - người nói nhiều nhất và giọng, cách đọc tên lạ, rồi "ai nói câu này" ở chương sắp thu. Mỗi bước là thẻ / dòng sẵn có của hộp việc (WorkCards) và tab Nhân vật
// (CastPeople, NameReadings); bước nào cũng bỏ qua được. Không bước nào chặn dây chuyền: chỉ khi bật "Duyệt trước khi thu" thì sách đứng lại (tạm dừng) và chờ nút "Thu âm".
// Dữ liệu: GET /precast (15 giây một lần), /work, /cast qua WorkStore; bước đang mở do trang dự án giữ (`step`) để Back từ Kịch bản trở lại đúng bước.
FocusScope {
    id: root
    objectName: "precastReview"
    property var store: null
    property var work: null
    property var book: null
    property var caps: ({})
    property string step: "cast"
    property bool introOpen: false
    property bool namesOpen: false
    signal stepChosen(string step)
    signal personRequest(string kind, var person)
    signal menuRequested(Item anchor, var person)
    signal openReview(string card)
    signal openScript(int chapterId, string stableId, bool pick, string card)
    signal openNames(string name, string card)
    signal pickVoice(var person)
    signal closeRequested()
    signal revealRequested(var target)

    readonly property var view: work ? work.precast.data : null
    readonly property var items: work && work.work.data ? work.work.data.items : null
    readonly property var cast: work ? work.cast.data : null
    readonly property bool failed: !!work && ((work.precast.error !== null && view === null) || (work.work.error !== null && items === null) || (work.cast.error !== null && cast === null))
    readonly property bool ready: view !== null && items !== null && cast !== null
    readonly property string current: P.stepOf(step)
    readonly property int index: P.STEPS.indexOf(current)
    readonly property bool narrow: width < 640
    readonly property var people: cast && cast.characters ? cast.characters.slice(0, P.TOP_PEOPLE) : []
    readonly property var twins: Cast.sameNames(cast && cast.characters ? cast.characters : [])
    readonly property var castCards: items ? P.castItems(items) : []
    readonly property var nameCards: items ? P.nameItems(items) : []
    readonly property var lineCards: items && view ? P.lineItems(items, P.upcomingIds(view)) : []
    readonly property string range: view ? P.chapterRange(view.upcoming) : ""
    readonly property var counts: P.stepCounts(castCards, nameCards, lineCards, people.length)
    width: parent ? parent.width : 600
    height: stack.height

    // Quyết xong một thẻ thì thẻ rời danh sách: tiêu điểm sang thẻ kế (hết thẻ thì về đầu vùng của bước), không rơi về nền (useCardFocus)
    function listsNow() {
        const list = current === "cast" ? castCards : current === "names" ? nameCards : current === "lines" ? lineCards : []
        return {open: list.map(function(item) { return item.key }), decided: []}
    }
    CardFocus {
        id: cardFocus
        scope: stack
        lists: root.listsNow
        endTarget: function() { return stepArea }
        onRevealRequested: card => root.revealRequested(card)
    }
    Binding { target: root.work; property: "precastWanted"; value: root.visible; when: !!root.work }
    Binding { target: root.work; property: "namesOpened"; value: root.namesOpen && root.current === "names"; when: !!root.work }
    function next() { stepChosen(P.STEPS[Math.min(index + 1, P.STEPS.length - 1)]) }
    function retry() { work.precast.load(); work.work.load(); work.cast.load() }

    // Bộ ba thẻ lên ba tín hiệu mở màn khác
    Component {
        id: cardsFor
        WorkCards {
            work: root.work
            voicePick: true
            onOpenReview: card => root.openReview(card)
            onOpenScript: (chapterId, stableId, pick, card) => root.openScript(chapterId, stableId, pick, card)
            onOpenNames: (name, card) => root.openNames(name, card)
            onPickVoice: person => root.pickVoice(person)
        }
    }

    Column {
        id: stack
        width: parent.width
        EditBookSkeleton {
            objectName: "precastSkeleton"
            visible: !root.ready && !root.failed
            y: 24
            width: parent.width
            shape: "rows"
            count: 4
            label: "Đang tải lượt duyệt"
        }
        EditBookError {
            objectName: "precastError"
            width: parent.width
            open: root.failed
            message: "Bạn hãy kiểm tra kết nối rồi tải lại lượt duyệt."
            onRetry: root.retry()
        }
        Column {
            id: content
            objectName: "precastContent"
            visible: root.ready
            width: parent.width
            Item { width: 1; height: 20 }
            Collapse {
                width: parent.width
                open: !!root.book && !!root.book.precast && Boolean(root.book.precast.held)
                Text {
                    objectName: "precastHeld"
                    width: Math.min(parent.width, 672)
                    bottomPadding: 4
                    text: P.HELD_NOTE
                    color: Theme.warning
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
            }
            // Điện thoại / cửa sổ hẹp: bốn bước phải nằm ở màn đầu - lời giới thiệu và công tắc gập lại
            DisclosureRow {
                objectName: "precastIntroToggle"
                visible: root.narrow
                width: parent.width
                title: "Chờ duyệt"
                expanded: root.introOpen
                onClicked: root.introOpen = !root.introOpen
            }
            Collapse {
                width: parent.width
                open: !root.narrow || root.introOpen
                Column {
                    width: parent.width
                    Text {
                        objectName: "precastIntro"
                        topPadding: 4
                        width: Math.min(parent.width, 672)
                        text: P.INTRO
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    MoreInfo {
                        width: parent.width
                        label: "Khi áp dụng"
                        Text {
                            objectName: "precastFree"
                            width: parent.width
                            text: P.freeNote(root.view)
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                        }
                    }
                    // Công tắc chỉ có nghĩa trước mốc (Studio mở màn này cả khi chưa kịp báo, vd app đóng lúc phân tích xong)
                    Collapse {
                        width: parent.width
                        open: !!root.book && !(root.book.precast && root.book.precast.announcedAt) && !(root.view && root.view.recordedChapters)
                        Item { width: 1; height: 8 }
                        PrecastWait { store: root.store; book: root.book }
                    }
                }
            }
            Item { width: 1; height: 20 }
            // Bốn bước: hàng chữ có số/dấu tích, bước đang mở có gạch chân hổ phách như tab - không bốn thẻ viền
            Item {
                id: stepBar
                objectName: "precastSteps"
                width: parent.width
                height: stepFlow.height
                Accessible.role: Accessible.List
                Accessible.name: "Các bước duyệt"
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
                Flow {
                    id: stepFlow
                    width: parent.width
                    spacing: root.narrow ? 16 : 24
                    Repeater {
                        model: P.STEPS
                        delegate: Interactive {
                            id: button
                            required property string modelData
                            required property int index
                            readonly property bool active: modelData === root.current
                            readonly property bool passed: index < root.index
                            objectName: "precastStep_" + modelData
                            width: root.narrow ? (stepFlow.width - 16) / 2 : Math.max(60, 26 + Math.max(titleText.implicitWidth, countText.implicitWidth))
                            height: Math.max(44, texts.height + 20)
                            pressScaling: false
                            Accessible.role: Accessible.Button
                            Accessible.name: P.TITLE[modelData]
                            Accessible.checked: active
                            onClicked: root.stepChosen(modelData)
                            Icon {
                                id: stepIcon
                                x: 0
                                y: (parent.height - 16) / 2
                                name: button.passed ? "check" : P.ICON[button.modelData]
                                size: 16
                                color: button.passed ? Theme.success : button.active ? Theme.accentText : Theme.text3
                                Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
                            }
                            Column {
                                id: texts
                                x: 26
                                y: (parent.height - height) / 2
                                width: parent.width - 26
                                Text {
                                    id: titleText
                                    width: parent.width
                                    text: P.TITLE[button.modelData]
                                    color: button.active ? Theme.text : Theme.text2
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeBodySmall
                                    font.weight: Theme.weightMedium
                                }
                                Text {
                                    id: countText
                                    visible: text !== ""
                                    width: parent.width
                                    text: root.counts[button.modelData] || ""
                                    color: Theme.text2
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeCaption
                                    font.features: { "tnum": 1 }
                                }
                            }
                            Rectangle {
                                anchors.bottom: parent.bottom
                                width: parent.width
                                height: 2
                                color: Theme.accent
                                opacity: button.active ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionFast } }
                            }
                        }
                    }
                }
            }
            Item { width: 1; height: 20 }
            Item {
                id: stepArea
                objectName: "precastStepArea"
                width: parent.width
                height: panes.height
                activeFocusOnTab: false
                Accessible.name: P.TITLE[root.current]
                Column {
                    id: panes
                    width: parent.width
                    // ---- Nhân vật và giọng ----
                    Collapse {
                        objectName: "precastCast"
                        width: parent.width
                        open: root.current === "cast"
                        Text {
                            width: Math.min(parent.width, 768)
                            text: P.castIntro(root.people.length)
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Item { width: 1; height: 12 }
                        CastPeople {
                            objectName: "precastPeople"
                            width: parent.width
                            bookId: root.book ? root.book.id : ""
                            peer: root.store ? root.store.peer : ""
                            people: root.people
                            caps: root.caps
                            below: twinNote
                            onRequest: (kind, person) => root.personRequest(kind, person)
                            onMenuRequested: (anchor, person) => root.menuRequested(anchor, person)
                        }
                        // Quyết xong thẻ cuối: cả nhóm khép lại, không mất cứng giữa lúc thẻ đang khép
                        Collapse {
                            width: parent.width
                            open: root.castCards.length > 0
                            Item { width: 1; height: 24 }
                            Flow {
                                width: parent.width
                                spacing: 6
                                Text {
                                    objectName: "precastDoubt"
                                    text: "Máy chưa chắc"
                                    color: Theme.text
                                    font.pixelSize: Theme.sizeBodySmall
                                    font.weight: 600
                                }
                                Text {
                                    width: Math.min(implicitWidth, parent.width)
                                    text: P.doubtLine(root.castCards.length)
                                    color: Theme.text2
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.sizeBodySmall
                                }
                            }
                            Loader { width: parent.width; sourceComponent: cardsFor; onLoaded: item.items = Qt.binding(function() { return root.castCards }) }
                        }
                    }
                    // ---- Cách đọc tên ----
                    Collapse {
                        objectName: "precastNames"
                        width: parent.width
                        open: root.current === "names"
                        Text {
                            objectName: "precastNamesIntro"
                            width: Math.min(parent.width, 768)
                            text: P.namesIntro(root.nameCards.length)
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Collapse {
                            width: parent.width
                            open: root.nameCards.length > 0
                            Item { width: 1; height: 12 }
                            Loader { width: parent.width; sourceComponent: cardsFor; onLoaded: item.items = Qt.binding(function() { return root.nameCards }) }
                        }
                        Item { width: 1; height: 24 }
                        Rectangle { width: parent.width; height: 1; color: Theme.line }
                        DisclosureRow {
                            objectName: "precastNamesToggle"
                            width: parent.width
                            title: "Cách đọc tên"
                            expanded: root.namesOpen
                            onClicked: root.namesOpen = !root.namesOpen
                        }
                        Collapse {
                            width: parent.width
                            open: root.namesOpen
                            Loader {
                                width: parent.width
                                active: root.namesOpen
                                sourceComponent: NameReadings {
                                    work: root.work
                                    onRevealRequested: target => root.revealRequested(target)
                                }
                            }
                        }
                    }
                    // ---- Ai nói câu này ----
                    Collapse {
                        objectName: "precastLines"
                        width: parent.width
                        open: root.current === "lines"
                        Text {
                            objectName: "precastLinesIntro"
                            width: Math.min(parent.width, 768)
                            text: root.view ? P.linesIntro(root.lineCards, root.view, root.range) : ""
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Collapse {
                            width: parent.width
                            open: root.lineCards.length > 0
                            Item { width: 1; height: 12 }
                            Loader { width: parent.width; sourceComponent: cardsFor; onLoaded: item.items = Qt.binding(function() { return root.lineCards }) }
                        }
                    }
                    // ---- Xong ----
                    Collapse {
                        objectName: "precastDone"
                        width: parent.width
                        open: root.current === "done"
                        EmptyState {
                            width: parent.width
                            topPadding: 40
                            bottomPadding: 40
                            icon: "clipboard-check"
                            title: "Xong lượt duyệt"
                            text: root.book ? P.doneText(root.book) : ""
                            Button {
                                objectName: "precastClose"
                                kind: "ghost"
                                size: "lg"
                                text: "Về danh sách chương"
                                onClicked: root.closeRequested()
                            }
                        }
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.current !== "done"
                Item { width: 1; height: 24 }
                Rectangle { width: parent.width; height: 1; color: Theme.line }
                Item { width: 1; height: 16 }
                Flow {
                    objectName: "precastFooter"
                    width: parent.width
                    layoutDirection: Qt.RightToLeft
                    spacing: 8
                    Button { objectName: "precastNext"; text: "Tiếp tục"; onClicked: root.next() }
                    Button { objectName: "precastSkip"; text: "Bỏ qua bước này"; kind: "ghost"; onClicked: root.next() }
                }
            }
        }
    }

    // "Cùng tên với người khác trong sách - một người?" dưới người trùng tên, kèm đường tắt tới chỗ gộp
    Component {
        id: twinNote
        Flow {
            id: twin
            property var person: ({})
            readonly property bool shown: Boolean(root.twins[Cast.cleanName(person.displayName).toLowerCase()]) && person.lines > 0
            visible: shown
            height: shown ? implicitHeight : 0
            spacing: 8
            leftPadding: 4
            Text {
                objectName: "precastTwin"
                width: Math.min(implicitWidth, twin.width - 8)
                text: P.TWIN_NOTE
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
            Button {
                objectName: "precastTwinMerge"
                size: "sm"
                kind: "ghost"
                text: "Gộp vào…"
                onClicked: root.personRequest("merge", twin.person)
            }
        }
    }
}
