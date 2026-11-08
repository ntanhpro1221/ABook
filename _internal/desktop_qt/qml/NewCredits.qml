import "UiStrings.js" as S
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
            Prose { strong: true; tone: Theme.text; text: S.s_so_chuong_co_cho_la_xem_lai_truoc_khi_tao_cbf84a1f }
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
            Prose { topPadding: 2; text: (root.suggestsSplit ? S.s_nhieu_tap_danh_so_lai_tu_1_chia_thanh_nhie_50bbb0ff : "") + S.s_van_tao_duoc_nhu_the_may_chi_nhac_khong_bo_08ad11a0 }
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
                text: root.dropped ? S.s_se_bo_976be2fb + Studio.formatNumber(root.dropped) + " " + Logic.droppedKind(root.credits, root.drop) + S.s_khoi_phan_doc_a9d1c125
                                   : S.s_goi_y_dddb8282 + Studio.formatNumber(root.credits.chapters) + S.s_chuong_co_51021419 + Logic.creditWhere(root.credits)
            }
            Prose {
                text: root.dropped ? S.s_chi_bo_khoi_phan_doc_giu_nguyen_file_truye_94c7dd67
                                   : root.credits.examples.join(", ") + (root.credits.lines > root.credits.examples.length ? "…" : "") + S.s_chon_bo_neu_khong_muon_doc_5abe810e
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
                        Accessible.role: Accessible.List
                        Accessible.name: S.s_moi_dong_goi_y_theo_chuong_af83ec00
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
                                return "<b>" + Logic.esc(modelData.chapter) + ":</b> " + parts.join("&nbsp;·&nbsp;")
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
                    text: root.drop.head ? S.s_giu_dong_dau_d250460c : S.s_bo_8d4fc41c + Studio.formatNumber(root.credits.head) + S.s_dong_7111afc1
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: !root.drop.head, tail: root.drop.tail})
                }
                Button {
                    visible: root.both
                    objectName: "newCreditTail"
                    text: root.drop.tail ? S.s_giu_dong_cuoi_d9387556 : S.s_bo_8d4fc41c + Studio.formatNumber(root.credits.tail) + S.s_dong_7111afc1
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: root.drop.head, tail: !root.drop.tail})
                }
                Button {
                    visible: !root.both && root.dropped > 0
                    objectName: "newCreditKeep"
                    text: S.s_giu_nguyen_chu_02c81916
                    kind: "ghost"; size: "sm"
                    onActivated: root.change(Logic.KEEP_CREDITS)
                }
                Button {
                    visible: !root.both && root.dropped === 0
                    objectName: "newCreditDrop"
                    text: S.s_bo_khoi_phan_doc_6726e734
                    kind: "ghost"; size: "sm"
                    onActivated: root.change({head: root.credits.head > 0, tail: root.credits.tail > 0})
                }
                Button {
                    objectName: "newCreditAll"
                    text: root.all ? S.s_thu_gon_1f6bf2c3 : S.s_xem_het_8cbaa769 + Studio.formatNumber(root.credits.lines) + S.s_dong_7111afc1
                    kind: "ghost"; size: "sm"
                    onActivated: root.all = !root.all
                }
            }
        }
    }
}
