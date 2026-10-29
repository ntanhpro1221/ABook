import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "StudioLogic.js" as Studio

// Hai lời nhắc về chữ của truyện, dưới phần chia tập: số chương có chỗ lạ (trùng, thiếu, xếp lùi, phần nối tiếp không bắt đầu đúng chương kế) và dòng ghi công người
// dịch / xin ủng hộ ở đầu - cuối chương mà máy ĐỀ XUẤT bỏ khỏi phần đọc. Máy chỉ NÓI ra, người dùng tự quyết (chủ sách 29-09: app không bao giờ tự sửa nội dung truyện);
// bỏ chỉ là bỏ khỏi phần đọc, file truyện giữ nguyên. Phải chọn lúc tạo sách: đổi cách tách câu sau khi đã làm là đổi cả quyển.
Column {
    id: root
    property var form: null
    property bool all: false
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property var files: scan ? scan.files : []
    readonly property var issues: scan ? Logic.numberIssues(files, form.splitting, form.volumeStarts, draft.seed ? draft.seed.lastChapter : undefined) : []
    readonly property bool suggestsSplit: form ? !form.splitting && Boolean(form.rawScan && form.rawScan.volumes) : false
    readonly property var credits: form ? form.credits : Logic.creditSummary([])
    readonly property var drop: draft.dropCredits || Logic.KEEP_CREDITS
    readonly property int dropped: Logic.droppedLines(credits, drop)
    readonly property bool both: credits.head > 0 && credits.tail > 0
    function change(value) { form.update({dropCredits: value}) }

    // Số chương có chỗ lạ
    Collapse {
        width: parent.width
        open: root.issues.length > 0
        NewNote {
            objectName: "newNumberWarning"
            width: parent.width
            icon: "triangle-alert"
            tone: Theme.warning
            Prose { strong: true; tone: Theme.text; text: "Số chương có chỗ lạ - xem lại trước khi tạo" }
            Repeater {
                model: root.issues
                delegate: Item {
                    required property string modelData
                    width: parent.width
                    height: issueText.height
                    Text { x: 4; text: "•"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                    Prose { id: issueText; x: 16; width: parent.width - 16; text: modelData }
                }
            }
            Prose { topPadding: 2; text: (root.suggestsSplit ? "Nhiều tập đánh số lại từ 1? Chia thành nhiều phần ở trên. " : "") + "Vẫn tạo được như thế - máy chỉ nhắc, không bỏ file nào." }
        }
    }
    // Gợi ý bỏ dòng ghi công / ủng hộ
    Collapse {
        width: parent.width
        open: root.credits.lines > 0
        NewNote {
            objectName: "newCreditNote"
            width: parent.width
            icon: "sparkles"
            tone: Theme.accentText
            Prose {
                strong: true
                tone: Theme.text
                text: root.dropped ? "Sẽ bỏ " + Studio.formatNumber(root.dropped) + " " + Logic.droppedKind(root.credits, root.drop) + " khỏi phần đọc"
                                   : "Gợi ý: " + Studio.formatNumber(root.credits.chapters) + " chương có " + Logic.creditWhere(root.credits)
            }
            Prose {
                text: root.dropped ? "Chỉ bỏ khỏi phần đọc, giữ nguyên file truyện."
                                   : root.credits.examples.join(", ") + (root.credits.lines > root.credits.examples.length ? "…" : "") + " — chọn bỏ nếu không muốn đọc."
            }
            // Xem hết mọi dòng theo chương trước khi bỏ
            Collapse {
                width: parent.width
                open: root.all
                Item {
                    width: parent.width
                    height: 8 + Math.min(creditList.contentHeight, 256)
                    ListView {
                        id: creditList
                        objectName: "newCreditList"
                        y: 8
                        width: parent.width
                        height: parent.height - 8
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.all ? Logic.creditRows(root.files, Logic.chapterLabel) : []
                        delegate: Text {
                            required property var modelData
                            width: creditList.width
                            textFormat: Text.RichText
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                            bottomPadding: 4
                            text: {
                                const lines = modelData.head.map(line => Logic.creditLine(line, "head", root.drop)).concat(modelData.tail.map(line => Logic.creditLine(line, "tail", root.drop)))
                                const parts = lines.map(line => line.dropped ? "<s>" + Logic.esc(line.text) + "</s>" : Logic.esc(line.text))
                                return "<b>" + Logic.esc(modelData.chapter) + ":</b> " + parts.join(" · ")
                            }
                        }
                        Scrollbar { target: creditList }
                    }
                }
            }
            Item { width: 1; height: 6 }
            Flow {
                width: parent.width
                spacing: 8
                Button {
                    visible: root.both
                    objectName: "newCreditHead"
                    text: root.drop.head ? "Giữ dòng đầu" : "Bỏ " + Studio.formatNumber(root.credits.head) + " dòng"
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: !root.drop.head, tail: root.drop.tail})
                }
                Button {
                    visible: root.both
                    objectName: "newCreditTail"
                    text: root.drop.tail ? "Giữ dòng cuối" : "Bỏ " + Studio.formatNumber(root.credits.tail) + " dòng"
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: root.drop.head, tail: !root.drop.tail})
                }
                Button {
                    visible: !root.both && root.dropped > 0
                    objectName: "newCreditKeep"
                    text: "Giữ nguyên chữ"
                    kind: "ghost"; size: "sm"
                    onActivated: root.change(Logic.KEEP_CREDITS)
                }
                Button {
                    visible: !root.both && root.dropped === 0
                    objectName: "newCreditDrop"
                    text: "Bỏ khỏi phần đọc"
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: root.credits.head > 0, tail: root.credits.tail > 0})
                }
                Button {
                    objectName: "newCreditAll"
                    text: root.all ? "Thu gọn" : "Xem hết " + Studio.formatNumber(root.credits.lines) + " dòng"
                    kind: "ghost"; size: "sm"
                    onActivated: root.all = !root.all
                }
            }
        }
    }
}
