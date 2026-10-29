import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

// Studio › Dự án mới / Sửa thiết lập / Làm tiếp (NewProjectScreen.tsx; DESIGN.md §2 L10: Studio -> "Dự án mới" -> chọn file -> "Bắt đầu", <= 3 chạm). MỘT trang, không bước:
// nguồn truyện (chọn / kéo thả, tên sách, chia phần, chương), rồi "Tuỳ chọn" gập (mẫu, giọng kể, chất lượng, khi tạo) với một dòng tóm tắt; lời nhắc phân tích ngay trên nút tạo, nút
// ghim ở đáy khung nhìn. Dữ liệu và việc nằm ở NewProjectStore (`form`, sống cùng StudioScreen nên rời trang rồi quay lại không mất nháp).
FocusScope {
    id: root
    property var form: null
    property bool pickOnOpen: false                 // tới từ nút "Dự án mới": mở luôn hộp chọn file
    signal peerRequested(string id)
    signal setupRequested()
    signal projectRequested(string id)
    readonly property var draft: form ? form.draft : ({})
    readonly property bool ready: form ? form.ready : false
    readonly property real contentW: Math.min(width - 2 * Theme.margin, 920)
    readonly property real contentX: (width - contentW) / 2
    readonly property var gate: form ? form.gate : ({disabled: true, label: ""})
    readonly property bool noStudio: form ? form.noStudio : false
    readonly property alias source: source
    property bool optionsOpen: Platform.setting("fold.new-project.options", "0") === "1"
    property real footerReveal: ready ? 1 : 0
    Behavior on footerReveal {
        NumberAnimation { duration: Theme.reduceMotion ? Theme.motionFast : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    readonly property real footerHeight: footer.implicitHeight

    function setOptions(open) {
        optionsOpen = open
        Platform.setSetting("fold.new-project.options", open ? "1" : "0")
    }
    // Một lần khi mở từ "Dự án mới": hộp chọn của máy này (thư mục, dán đường dẫn, kéo thả vẫn nằm ngay trang khi bạn huỷ)
    property bool pickedOnOpen: false
    function maybePick() {
        if (!pickOnOpen || pickedOnOpen || !form) return
        pickedOnOpen = true
        if (form.dialogs && !ready && !(form.draft.paths && form.draft.paths.length)) Qt.callLater(function() { source.chooseFiles(false) })
    }
    onPickOnOpenChanged: if (pickOnOpen) { pickedOnOpen = false; maybePick() }
    Component.onCompleted: maybePick()

    Flickable {
        id: page
        objectName: "newProjectPage"
        anchors.fill: parent
        contentWidth: width
        contentHeight: frame.height
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        SmoothWheel { flick: page }

        Column {
            id: frame
            x: root.contentX
            width: root.contentW
            ScreenHeader {
                id: header
                objectName: "newHeader"
                width: parent.width
                showBack: true
                backLabel: "Về Studio"
                title: root.draft.seed ? "Làm tiếp cuốn này" : "Tạo sách nói"
            }
            NewSeedBanner { id: seedBanner; width: parent.width; form: root.form }
            Item { width: 1; height: 32 }
            StudioSetupNotice {
                objectName: "newInstallNotice"
                width: parent.width
                form: root.form
                onSetupRequested: root.setupRequested()
                onPeerRequested: id => root.peerRequested(id)
            }
            Item { width: 1; height: 24 }
            NewSource {
                id: source
                width: parent.width
                form: root.form
                onProjectRequested: id => root.projectRequested(id)
            }
            // Tuỳ chọn: một dòng tóm tắt lựa chọn đang dùng; bấm thì mở mẫu, giọng kể, chất lượng và cách bắt đầu. Hiện khi đã có chương.
            Collapse {
                width: parent.width
                open: root.ready
                Item { width: 1; height: 32 }
                Rectangle { width: parent.width; height: 1; color: Theme.line }
                DisclosureRow {
                    objectName: "newOptions"
                    width: parent.width
                    section: true
                    icon: "sliders-horizontal"
                    title: "Tuỳ chọn"
                    summary: root.form ? Logic.optionsSummary(root.form.autoNarrator, root.draft.narrator, root.draft.profile, root.draft.startNow, root.noStudio) : ""
                    expanded: root.optionsOpen
                    onClicked: root.setOptions(!root.optionsOpen)
                }
                Collapse {
                    width: parent.width
                    open: root.optionsOpen
                    Column {
                        objectName: "newOptionsBody"
                        width: parent.width
                        topPadding: 16
                        bottomPadding: 16
                        spacing: 48
                        // Mẫu thiết lập chỉ cho sách mới: "Làm tiếp cuốn này" theo phần trước
                        Collapse {
                            width: parent.width
                            open: !root.draft.seed
                            NewTemplateBar { width: parent.width; form: root.form }
                        }
                        NewVoice { width: parent.width; form: root.form }
                        NewQuality { width: parent.width; form: root.form }
                        NewConfirm { width: parent.width; form: root.form }
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.ready
                Item { width: 1; height: 32 }
                NewStartNotes { width: parent.width; form: root.form; onPeerRequested: id => root.peerRequested(id) }
            }
            // Chỗ cho nút ghim + khoảng đệm cuối trang (pb-16)
            Item { id: tail; width: 1; height: root.footerHeight * root.footerReveal + 64 }
        }
    }

    Scrollbar { target: page }

    // Nút tạo ghim ở đáy vùng cuộn: "Tuỳ chọn" mở ra dài thì nút vẫn luôn thấy; trang ngắn thì nằm ngay dưới nội dung (sticky bottom-0 của bản web)
    Rectangle {
        id: footer
        objectName: "newFooter"
        readonly property real natural: frame.y + tail.y - page.contentY
        x: 0
        width: parent.width
        implicitHeight: 1 + 16 + actions.height + 16
        height: implicitHeight
        y: Math.min(root.height - height, natural)
        color: Theme.bg
        opacity: root.footerReveal
        visible: opacity > 0
        enabled: root.ready
        Rectangle { x: root.contentX; width: root.contentW; height: 1; color: Theme.line }
        Item {
            id: actions
            x: root.contentX
            y: 17
            width: root.contentW
            height: Math.max(startOver.height, create.height, hint.height)
            Button { id: startOver; objectName: "newStartOver"; text: "Bắt đầu lại"; kind: "ghost"; onActivated: root.form.reset() }
            Row {
                x: parent.width - width
                height: parent.height
                spacing: 12
                Text {
                    id: hint
                    objectName: "newUnfitHint"
                    visible: root.form ? Boolean(root.form.unfit) : false
                    anchors.verticalCenter: parent.verticalCenter
                    width: Math.min(implicitWidth, Math.max(80, actions.width - startOver.width - create.width - 36))
                    horizontalAlignment: Text.AlignRight
                    text: "Máy thiếu cấu hình"
                    color: Theme.text2
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: 13
                }
                Button {
                    id: create
                    objectName: "newCreate"
                    anchors.verticalCenter: parent.verticalCenter
                    kind: "primary"
                    size: "lg"
                    icon: root.draft.startNow && !root.noStudio ? "wand-sparkles" : "mic"
                    text: root.gate.label || (root.draft.startNow && !root.noStudio ? "Bắt đầu" : "Tạo sách")
                    busy: Boolean(root.form) && (root.form.submitting || root.gate.reading)
                    enabled: !root.gate.disabled
                    onActivated: root.form.submit()
                }
            }
        }
    }
}
