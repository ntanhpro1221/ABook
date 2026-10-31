import QtQuick
import ABook
import "WorkLogic.js" as W
import "StudioLogic.js" as Studio

// Một thẻ của hộp "Việc cần duyệt" (Card của WorkInbox.tsx): viên loại việc + tiêu đề (đã quyết thì nói KẾT QUẢ) + lời máy nghi ngờ + "Ảnh hưởng N câu · Máy đang dùng …" + chỗ sửa theo
// loại thẻ (cách đọc tên, người nói, người kể, giọng / giới, yêu cầu chưa được) + vài câu ví dụ. Thẻ vai phụ cả cuốn cho bỏ chọn từng câu trước khi chọn người; nhóm lớn tải thêm theo trang.
Item {
    id: root
    objectName: "workCard"
    property var work: null
    property var item: ({})
    property bool active: false
    property bool scriptLinks: false
    property bool namesLink: false
    property bool voicePick: false
    property string scope: "alternate"
    property var dropped: ({})
    property bool all: false
    property var more: []
    property bool loadingMore: false
    property bool asked: false
    signal openReview(string key)
    signal openScript(int chapterId, string stableId, bool pick, string card)
    signal openNames(string name, string card)
    signal pickVoice(var person)

    readonly property string key: item.key || ""
    readonly property bool decided: Boolean(item.requested)
    readonly property string groupLines: item.pick && item.lines ? item.lines.map(function(line) { return line.stableId }).join(" ") : ""
    readonly property var picked: item.pick && item.lines ? W.pickedLines(item.lines, dropped) : null
    readonly property var page: W.examplesPage(work ? work.bookId : "", key, item.examples || [], more, item.examplesTotal, W.PICK_PAGE)
    readonly property var examples: page.loaded
    readonly property int headCount: item.pick ? Math.min(W.PICK_PREVIEW, examples.length) : examples.length
    readonly property real pad: 12
    // Gán một phần rồi thì thẻ còn đúng những câu đã bỏ chọn - chúng phải hiện là đang chọn, không phải vẫn bỏ
    onGroupLinesChanged: { dropped = ({}); more = [] }
    width: parent ? parent.width : 600
    height: body.height + 2 * 16

    // Các nút lựa chọn đang bấm được của thẻ (phím 1-9 của hộp việc): theo thứ tự trên màn hình
    function choices() {
        const out = []
        function walk(node) {
            for (const child of node.children) {
                if (child.choice === true && child.enabled && child.visible) out.push(child)
                walk(child)
            }
        }
        if (fix.item) walk(fix.item)
        return out
    }
    function loadMore() {
        if (!page.next || loadingMore) return
        loadingMore = true
        work.loadExamples(page.next, function(data) {
            root.loadingMore = false
            if (data) root.more = root.more.concat(data.examples || [])
        })
    }
    function undo() {
        if (asked) return
        asked = true
        work.undoDecision(item)
        // Không hoàn tác được (đã vào sách) thì thẻ còn đó - mở nút lại để thử khi đổi ý
        reopen.restart()
    }
    Timer { id: reopen; interval: 2500; onTriggered: root.asked = false }

    Rectangle {
        anchors.fill: parent
        color: Theme.hover
        opacity: root.active ? 0.5 : 0
        radius: Theme.radiusControl
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }

    Column {
        id: body
        x: root.pad
        y: 16
        width: root.width - 2 * root.pad
        spacing: 0

        Item {
            id: head
            width: parent.width
            height: Math.max(heading.height, undoButton.visible ? undoButton.height : 0)
            Flow {
                id: heading
                width: parent.width - (undoButton.visible ? undoButton.width + 8 : 0)
                spacing: 8
                Rectangle {
                    height: 22
                    width: kind.implicitWidth + 16
                    radius: height / 2
                    color: Theme.hover
                    Text {
                        id: kind
                        anchors.centerIn: parent
                        text: W.kindLabel(root.item.kind)
                        color: Theme.text2
                        font.pixelSize: 11
                        font.weight: Theme.weightMedium
                    }
                }
                Text {
                    objectName: "workTitle"
                    width: Math.min(implicitWidth, heading.width)
                    text: W.cardTitle(root.item)
                    color: root.active ? Theme.accentText : Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: 15
                    font.weight: Theme.weightBold
                    Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
                }
            }
            Button {
                id: undoButton
                objectName: "workUndo"
                visible: root.decided && Boolean(root.item.undo)
                anchors.right: parent.right
                size: "sm"
                kind: "ghost"
                icon: "rotate-ccw"
                text: "Hoàn tác"
                enabled: !root.asked
                Accessible.name: "Hoàn tác: " + W.cardTitle(root.item)
                onClicked: root.undo()
            }
        }
        Text {
            objectName: "workProblem"
            width: parent.width
            topPadding: 6
            text: root.item.problem || ""
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Flow {
            width: parent.width
            topPadding: 8
            spacing: 4
            Text {
                objectName: "workAffected"
                rightPadding: 12
                textFormat: Text.RichText
                text: "Ảnh hưởng <b><span style=\"color:" + W.cssColor(Theme.text) + "\">" + Studio.formatNumber(root.item.allLines && root.scope === "all" ? root.item.allLines.length : root.item.affected) + "</span></b> câu"
                color: Theme.text2
                font.pixelSize: Theme.sizeCaption
            }
            Text {
                objectName: "workCurrent"
                rightPadding: 12
                textFormat: Text.RichText
                text: (root.item.kind === "audio" ? "Trạng thái" : root.item.kind === "narrator" ? "Máy coi người kể là" : "Máy đang dùng") + ": <b><span style=\"color:" + W.cssColor(Theme.text) + "\">"
                    + W.esc(root.item.kind === "narrator" && !root.item.current ? "không ai - chương kể ở ngôi thứ ba" : root.item.current || "") + "</span></b>"
                color: Theme.text2
                wrapMode: Text.Wrap
                width: Math.min(implicitWidth, parent.width)
                font.pixelSize: Theme.sizeCaption
            }
        }

        // ---- chỗ sửa theo loại thẻ ----
        Loader {
            id: fix
            objectName: "workFix"
            width: parent.width
            sourceComponent: root.item.kind === "audio" ? audioFix
                : root.item.kind === "pronunciation" && root.item.surface ? pronunciationFix
                : root.item.kind === "narrator" && root.item.narratorSection ? narratorFix
                : root.item.kind === "refused" && root.item.refused ? refusedFix
                : root.item.kind === "voice-wish" ? wishFix
                : root.item.voiceChoices && root.item.voiceChoices.length > 0 ? voiceFix
                : root.item.lines && root.item.choices ? speakerFix : optionsFix
        }
        Component {
            id: audioFix
            Item {
                height: 12 + review.height
                Button { id: review; objectName: "workReview"; y: 12; size: "sm"; kind: "ghost"; icon: "audio-lines"; text: "Nghe lại"; onClicked: root.openReview(root.item.key) }
            }
        }
        Component {
            id: pronunciationFix
            WorkPronunciation {
                work: root.work
                item: root.item
                namesLink: root.namesLink
                onOpenNames: name => root.openNames(name, root.item.key)
            }
        }
        Component {
            id: narratorFix
            WorkNarrator { work: root.work; item: root.item }
        }
        Component {
            id: refusedFix
            Item {
                height: 12 + drop.height
                property bool busy: false
                Button {
                    id: drop
                    objectName: "workDrop"
                    y: 12
                    size: "sm"
                    kind: "ghost"
                    text: "Bỏ yêu cầu này"
                    busy: parent.busy
                    onActivated: { parent.busy = true; root.work.dropRefused(root.item, function() { parent.busy = false }) }
                }
            }
        }
        Component {
            id: wishFix
            Column {
                Item {
                    visible: root.voicePick && Boolean(root.item.pickVoice)
                    width: 1
                    height: visible ? 12 + pick.height : 0
                    Button {
                        id: pick
                        objectName: "workPickVoice"
                        y: 12
                        size: "sm"
                        kind: "ghost"
                        text: "Chọn giọng khác…"
                        onClicked: root.pickVoice(root.item.pickVoice)
                    }
                }
                WorkVoice { width: parent.width; work: root.work; item: root.item }
            }
        }
        Component {
            id: voiceFix
            WorkVoice { work: root.work; item: root.item }
        }
        Component {
            id: speakerFix
            WorkSpeaker {
                work: root.work
                item: root.item
                scope: root.scope
                scoped: Boolean(root.item.allLines) && Boolean(root.item.lines)
                picked: root.picked
                scriptLinks: root.scriptLinks
                onScopeChosen: value => root.scope = value
                onOpenScript: (chapterId, stableId, pick) => root.openScript(chapterId, stableId, pick, root.item.key)
            }
        }
        Component {
            id: optionsFix
            Item {
                height: 12 + flow.height
                Flow {
                    id: flow
                    y: 12
                    width: parent.width
                    spacing: 6
                    Accessible.role: Accessible.Grouping
                    Accessible.name: "Lựa chọn"
                    Repeater {
                        model: root.item.options || []
                        delegate: Rectangle {
                            required property string modelData
                            width: chip.implicitWidth + 20
                            height: chip.implicitHeight + 8
                            radius: Theme.radiusControl
                            color: "transparent"
                            border.width: 1
                            border.color: Theme.line
                            Text { id: chip; anchors.centerIn: parent; width: Math.min(implicitWidth, flow.width - 20); text: modelData; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                        }
                    }
                }
            }
        }

        // ---- câu ví dụ ----
        Item { width: 1; height: root.examples.length > 0 ? 12 : 0 }
        Rectangle { visible: root.examples.length > 0; width: parent.width; height: 1; color: Theme.line }
        Column {
            id: sentences
            objectName: "workExamples"
            visible: root.examples.length > 0
            width: parent.width
            topPadding: 12
            spacing: 8
            Text {
                objectName: "workPickNote"
                visible: root.picked !== null && Boolean(root.item.lines)
                width: parent.width
                text: root.picked !== null && root.item.lines ? W.pickNote(root.picked.length, root.item.lines.length) + " - bỏ chọn câu không phải của người ấy." : ""
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
            Repeater {
                model: root.examples.slice(0, root.headCount)
                delegate: WorkExample {
                    required property var modelData
                    work: root.work
                    example: modelData
                    changes: root.item.allLines && root.scope === "all" ? true : Boolean(modelData.changes)
                    picks: root.picked !== null && Boolean(modelData.stableId)
                    picked: !root.dropped[modelData.stableId || ""]
                    onPickToggled: root.dropped = W.toggleLine(root.dropped, modelData.stableId)
                }
            }
            Collapse {
                width: parent.width
                open: Boolean(root.item.pick) && root.all
                spacing: 8
                Repeater {
                    model: root.item.pick ? root.examples.slice(root.headCount) : []
                    delegate: WorkExample {
                        required property var modelData
                        work: root.work
                        example: modelData
                        picks: root.picked !== null && Boolean(modelData.stableId)
                        picked: !root.dropped[modelData.stableId || ""]
                        onPickToggled: root.dropped = W.toggleLine(root.dropped, modelData.stableId)
                    }
                }
            }
        }
        Flow {
            visible: Boolean(root.item.pick) && root.page.total > W.PICK_PREVIEW
            width: parent.width
            topPadding: 8
            spacing: 8
            Button {
                objectName: "workMore"
                size: "sm"
                kind: "ghost"
                text: root.all ? "Thu gọn" : "Xem cả " + Studio.formatNumber(root.page.total) + " câu"
                Accessible.description: root.all ? "Đang mở" : "Đang đóng"
                onClicked: {
                    if (!root.all && root.page.next && root.more.length === 0) root.loadMore()
                    root.all = !root.all
                }
            }
            Button {
                objectName: "workLoadMore"
                visible: root.all && Boolean(root.page.next)
                size: "sm"
                kind: "ghost"
                enabled: !root.loadingMore
                text: root.loadingMore ? "Đang tải…" : W.moreText(root.examples.length, root.page.total)
                onClicked: root.loadMore()
            }
        }
    }
}
