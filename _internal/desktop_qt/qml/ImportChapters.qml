import QtQuick
import ABook
import "ImportQueue.js" as Queue

// Danh sách chương của bước xem trước (ChapterPreview của shared/ChapterPreview.tsx, kiểu `choice`): mỗi hàng có ô tích, số thứ tự, tên chương đúng như sẽ lưu
// (bấm để đổi tên, bút nhỏ ngay sau chữ cuối), dòng đầu của chương ở dòng phụ, nhãn "rất ngắn…" / lý do máy thấy, số chữ ở cột phải. Tên dài xuống dòng đủ, không
// cắt. Danh sách dài (> 320) cuộn trong khung, mép còn nội dung thì mờ dần. Đổi tên là một bước con: mở lớp Back của riêng nó (Back / Esc huỷ, Enter hay rời ô
// thì lưu), xong thì tiêu điểm về đúng nút tên chương vừa sửa. Trạng thái (đã tích, tên đã đổi) do hộp giữ.
Item {
    id: root
    property var chapters: []
    property var picked: []
    property var names: ({})
    property bool locked: false
    property int editing: -1               // số thứ tự (index) của hàng đang đổi tên, -1 = không
    readonly property int digits: String(chapters.length).length
    readonly property bool wide: width >= 500
    readonly property real sideWidth: wide ? 90 : 64
    signal pick(int index, bool on)
    signal rename(var chapter, string value)
    objectName: "importChapters"
    implicitHeight: view.height
    height: implicitHeight

    // Lớp Back của bước đổi tên: Back huỷ việc gõ, về danh sách
    property bool cancelled: false
    property int returnTo: -1
    readonly property QtObject backLayer: QtObject { function close() { root.cancelEdit() } }
    function startEdit(index) {
        if (editing >= 0 || locked) return
        cancelled = false
        editing = index
        Nav.openLayer(backLayer)
    }
    function stopEdit() {
        const was = editing
        editing = -1
        Nav.closedLayer(backLayer)
        returnTo = was
        Qt.callLater(function() { const target = root.buttonFor(root.returnTo); if (target) target.forceActiveFocus(Qt.TabFocusReason) })
    }
    function cancelEdit() { if (editing < 0) return; cancelled = true; stopEdit() }
    function finishEdit(chapter, value) {
        if (editing !== chapter.index) return
        if (!cancelled) root.rename(chapter, value)
        stopEdit()
    }
    function buttonFor(index) {
        for (let i = 0; i < rows.count; ++i) {
            const row = rows.itemAt(i)
            if (row && row.chapter.index === index) return row.button
        }
        return null
    }
    Component.onDestruction: Nav.closedLayer(backLayer)

    // Hàng trôi ra ngoài khung cuộn thì không vẽ icon của nó (Shape của bộ vẽ phần mềm không theo khung cắt)
    function inside(top, size) { return top >= view.contentY && top + size <= view.contentY + view.height }
    Text { id: digitProbe; visible: false; text: "0".repeat(root.digits); font.pixelSize: Theme.sizeCaption; font.features: { "tnum": 1 } }

    Flickable {
        id: view
        width: root.width
        height: Math.min(320, column.height)
        contentWidth: width
        contentHeight: column.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }

        Column {
            id: column
            x: 6
            width: view.width - 12
            Repeater {
                id: rows
                model: root.chapters.length
                Item {
                    id: row
                    required property int index
                    readonly property var chapter: root.chapters[index]
                    readonly property bool on: root.picked.indexOf(chapter.index) >= 0
                    readonly property var renamed: root.names[chapter.index]
                    readonly property string title: renamed !== undefined ? renamed : chapter.title
                    readonly property string sub: chapter.firstLine && chapter.firstLine !== chapter.title ? chapter.firstLine : ""
                    readonly property bool isEditing: root.editing === chapter.index
                    property alias button: rename
                    readonly property real textX: 28 + digitProbe.implicitWidth + 8
                    width: column.width
                    height: Math.max(titleBlock.height, 20) + 16 + 1
                    Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }

                    ImportBox {
                        x: 0
                        y: 8 + 1
                        checked: row.on
                        inView: root.inside(row.y + 9, 20)
                        enabled: !root.locked
                        label: "Đưa vào sách: " + (row.renamed !== undefined ? row.renamed : row.chapter.title)
                        onToggled: value => root.pick(row.chapter.index, value)
                    }
                    Text {
                        x: 28
                        y: 8 + 2
                        width: digitProbe.implicitWidth
                        horizontalAlignment: Text.AlignRight
                        text: row.index + 1
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                        font.features: { "tnum": 1 }
                        lineHeight: 20
                        lineHeightMode: Text.FixedHeight
                        height: 20
                        verticalAlignment: Text.AlignTop
                        topPadding: -2
                    }
                    Column {
                        id: titleBlock
                        x: row.textX
                        y: 8
                        width: row.width - x - 8 - root.sideWidth
                        Item {
                            id: titleLine
                            width: parent.width
                            height: row.isEditing ? editor.height : rename.height
                            Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                            Interactive {
                                id: rename
                                objectName: "importRename"
                                width: parent.width
                                height: Math.max(20, titleText.contentHeight + 2)
                                visible: !row.isEditing
                                enabled: !root.locked
                                tip: "Bấm để đổi tên chương"
                                ringMargin: 2
                                Accessible.role: Accessible.Button
                                Accessible.name: row.title
                                onClicked: root.startEdit(row.chapter.index)
                                // Bút nằm ngay sau chữ cuối, kể cả khi tên xuống dòng
                                TextEdit {
                                    id: titleText
                                    width: parent.width - 18
                                    enabled: false
                                    readOnly: true
                                    text: row.title
                                    color: rename.hovered ? Theme.accentText : Theme.text
                                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                                    textFormat: TextEdit.PlainText
                                    font.family: Theme.family
                                    font.pixelSize: Theme.sizeBodySmall
                                    font.weight: Theme.weightMedium
                                    Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                                }
                                Icon {
                                    readonly property rect end: titleText.positionToRectangle(titleText.length)
                                    visible: root.inside(row.y + 8 + end.y, 14)
                                    x: end.x + 6
                                    y: end.y + (end.height - 12) / 2 + 1
                                    name: "pencil"
                                    size: 12
                                    color: rename.hovered ? Theme.accentText : Theme.text3
                                }
                            }
                            FormField {
                                id: editor
                                objectName: "importRenameField"
                                width: parent.width
                                visible: row.isEditing
                                enabled: row.isEditing
                                label: "Tên chương"
                                escapeLocal: true
                                topPadding: 6
                                bottomPadding: 6
                                implicitHeight: Math.max(32, contentHeight + 12)
                                font.weight: Theme.weightMedium
                                property bool seeded: false
                                onVisibleChanged: if (visible) {
                                    text = row.title
                                    forceActiveFocus(Qt.TabFocusReason)
                                    selectAll()
                                }
                                onAccepted: root.finishEdit(row.chapter, text)
                                onEscaped: root.cancelEdit()
                                onActiveFocusChanged: if (!activeFocus && row.isEditing) root.finishEdit(row.chapter, text)
                                onTextChanged: if (length > 160) remove(160, length)
                            }
                        }
                        Text {
                            width: parent.width
                            visible: row.sub !== ""
                            text: row.sub
                            color: Theme.text2
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeCaption
                            textFormat: Text.PlainText
                        }
                        Text {
                            width: parent.width
                            visible: text !== ""
                            text: row.chapter.matter ? row.chapter.matter + " - có vẻ không phải truyện, tích nếu muốn nghe" : (row.chapter.short ? "rất ngắn - có thể là bìa / trang bản quyền" : "")
                            color: Theme.text3
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeCaption
                            textFormat: Text.PlainText
                        }
                    }
                    Column {
                        x: row.width - root.sideWidth
                        y: 8
                        width: root.sideWidth
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignRight
                            text: Queue.formatNumber(row.chapter.words || 0) + " chữ"
                            color: Theme.text2
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeCaption
                            font.features: { "tnum": 1 }
                            topPadding: 2
                        }
                    }
                    Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.line; visible: row.index < root.chapters.length - 1 }
                }
            }
        }
    }
    ScrollEdges { target: view; color: Theme.panel; x: view.x; y: view.y; width: view.width; height: view.height }
    Scrollbar { target: view }
    SmoothWheel { flick: view }
}
