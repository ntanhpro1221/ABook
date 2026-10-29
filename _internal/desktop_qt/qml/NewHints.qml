import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "StudioLogic.js" as Studio

// Lời nhắn dưới ô Tên sách của trình tạo (SourceStep): đang sửa thiết lập cuốn nào; truyện này đã có dự án; gợi ý tách một file cả truyện thành các chương;
// trang phụ của file sách chưa tích. Máy chỉ ĐỀ XUẤT, không tự sửa nguồn (chủ sách 29-09). Mỗi khối mở / khép tại chỗ.
Column {
    id: root
    property var form: null
    signal projectRequested(string id)
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property var replaces: draft.replaces
    readonly property var others: scan && scan.existing ? scan.existing.filter(project => !replaces || project.id !== replaces.id) : []
    readonly property var splits: scan ? scan.files.filter(file => file.split) : []
    readonly property var matter: form && form.rawScan ? Logic.matterFiles(form.rawScan.files) : []
    property string splitting: ""

    // Đang sửa thiết lập / làm lại
    Collapse {
        width: parent.width
        open: Boolean(root.replaces)
        NewNote {
            objectName: "newReplacesNote"
            width: parent.width
            icon: "info"
            Prose {
                textFormat: Text.StyledText
                tone: Theme.text
                text: root.replaces ? (root.replaces.restart ? "Đang làm lại phân tích của " : "Đang sửa thiết lập của ") + "<b>“" + Logic.esc(root.replaces.title) + "”</b>: đã điền thiết lập cũ; tạo xong sẽ đưa bản cũ vào Thùng rác." : " "
            }
        }
    }
    // Truyện này đã có dự án
    Collapse {
        width: parent.width
        open: root.others.length > 0
        NewNote {
            objectName: "newExistingNote"
            width: parent.width
            icon: "info"
            Prose { strong: true; tone: Theme.text; text: "Truyện này đã có dự án" }
            Repeater {
                model: root.others
                delegate: Flow {
                    required property var modelData
                    width: parent.width
                    spacing: 8
                    Text {
                        width: Math.min(implicitWidth, parent.width)
                        text: "“" + modelData.title + "” · " + (modelData.shared === modelData.chapters ? "cả " + modelData.chapters + " chương" : "trùng " + modelData.shared + "/" + modelData.chapters + " chương") + " · " + modelData.statusLabel
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    TextLink { objectName: "newExistingOpen"; text: "Mở dự án"; accent: true; onClicked: root.projectRequested(modelData.id) }
                }
            }
            Prose { text: "Vẫn tạo được dự án mới - ví dụ để thử một giọng kể khác." }
        }
    }
    // Gợi ý tách file cả truyện
    Collapse {
        width: parent.width
        open: root.splits.length > 0
        Column {
            width: parent.width
            Repeater {
                model: root.splits
                delegate: NewNote {
                    id: suggestion
                    required property var modelData
                    objectName: "newSplitNote"
                    width: parent.width
                    icon: "sparkles"
                    tone: Theme.accentText
                    readonly property var plan: modelData.split
                    readonly property var outcome: Logic.splitOutcome(plan, root.draft.title || "")
                    Prose {
                        strong: true
                        tone: Theme.text
                        text: "Gợi ý: “" + suggestion.modelData.name + "” có vẻ chứa cả " + Studio.formatNumber(suggestion.outcome.chapters) + " chương"
                    }
                    Prose {
                        text: "Tách theo " + suggestion.plan.titles.map(title => "“" + title + "”").join(", ") + (suggestion.plan.chapters > suggestion.plan.titles.length ? "…" : "") + ", giữ file gốc" + (suggestion.plan.preamble ? " và chữ mở đầu" : "") + "."
                    }
                    Item { width: 1; height: 6 }
                    Button {
                        objectName: "newSplitButton"
                        text: "Tách thành " + Studio.formatNumber(suggestion.outcome.chapters) + " chương"
                        icon: "scissors"
                        kind: "ghost"
                        size: "sm"
                        busy: root.splitting === suggestion.modelData.path
                        enabled: root.splitting === ""
                        onActivated: {
                            root.splitting = suggestion.modelData.path
                            root.form.splitSource(suggestion.modelData.path, function() { root.splitting = "" })
                        }
                    }
                }
            }
        }
    }
    // Trang phụ của file sách: có trong sách nhưng chưa tích
    Collapse {
        width: parent.width
        open: root.matter.length > 0
        Column {
            objectName: "newMatter"
            width: parent.width
            topPadding: 16
            Prose { strong: true; tone: Theme.text; topPadding: 16; text: Studio.formatNumber(root.matter.length) + " trang phụ chưa chọn" }
            Prose { topPadding: 4; text: "Bìa, bản quyền, mục lục hay trang tên sách nằm trong file sách. Máy chưa chọn chúng vì nghe lên không phải truyện - tích trang nào bạn muốn nghe." }
            Item { width: 1; height: 8 }
            Repeater {
                model: root.matter
                delegate: ImportCheck {
                    required property var modelData
                    objectName: "newMatterRow"
                    width: parent.width
                    label: modelData.matter
                    help: modelData.firstLine || modelData.name
                    checked: (root.draft.keepMatter || []).indexOf(modelData.path) >= 0
                    onToggled: value => root.form.keepMatter(modelData.path, value)
                }
            }
            Item { width: 1; height: 16 }
        }
    }
}
