import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "UploadLogic.js" as Upload
import "StudioLogic.js" as Studio

// Phần cuối bước Nguồn khi đã có chương (SourceStep): dòng tổng (số chương, chữ, audio) với "Thêm file" / "Huỷ gửi" / "Chọn lại", chọn nhanh "Đợt này làm…" cho truyện dài,
// danh sách chương (cuộn trong khung tối đa 340, bỏ từng chương, vạch "Phần N bắt đầu" khi chia tập), file bị bỏ qua và lời cảnh báo của lần quét.
// Danh sách ảo (ListView) vì truyện có thể hàng nghìn chương; hàng bỏ / hoàn tác khép / mở tại chỗ như AnimatedRows của bản web.
Column {
    id: root
    property var form: null
    signal filesRequested()
    readonly property var scan: form ? form.scan : null
    readonly property var files: scan ? scan.files : []
    readonly property bool dialogs: form ? form.dialogs : false
    readonly property bool browser: form ? form.browser : false
    readonly property var uploading: form ? form.uploading : null
    readonly property bool starts: form ? form.splitting && form.volumeStarts.length > 1 : false
    readonly property bool narrow: width < 480
    property var byKey: ({})
    property var position: ({})
    property bool populated: false

    // Đồng bộ ListModel với danh sách chương: hàng mất đi thì khép rồi gỡ, hàng mới đến sau lần đầu thì mở ra (tối đa vài hàng một lần; nhiều hơn là đổi cả nguồn - hiện thẳng)
    function sync() {
        const map = Object.assign({}, byKey)
        const where = {}
        const keys = []
        files.forEach(function(file, index) { map[file.path] = file; where[file.path] = index; keys.push(file.path) })
        byKey = map
        position = where
        const known = {}
        for (let i = 0; i < rows.count; ++i) known[rows.get(i).key] = true
        let added = 0
        for (const key of keys) if (!known[key]) ++added
        for (let i = rows.count - 1; i >= 0; --i) {
            const gone = where[rows.get(i).key] === undefined
            if (gone && (rows.count > 200 || added > 3 || !populated)) rows.remove(i)
            else rows.setProperty(i, "gone", gone)
        }
        let at = 0
        for (const key of keys) {
            let found = -1
            for (let i = 0; i < rows.count; ++i) if (rows.get(i).key === key) { found = i; break }
            if (found < 0) { rows.insert(at, {key: key, gone: false, appear: populated && added <= 3}); ++at }
            else at = Math.max(at, found + 1)
        }
        populated = true
    }
    function drop(key) {
        for (let i = 0; i < rows.count; ++i) {
            const row = rows.get(i)
            if (row.key === key) { if (row.gone) rows.remove(i); return }
        }
    }
    onFilesChanged: sync()
    Component.onCompleted: sync()
    ListModel { id: rows }

    // Dòng tổng + nút
    Item {
        width: parent.width
        height: 20 + Math.max(total.height, buttons.height)
        Text {
            id: total
            objectName: "newTotals"
            y: 20
            width: root.narrow ? parent.width : parent.width - buttons.width - 12
            textFormat: Text.StyledText
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.features: { "tnum": 1 }
            text: root.scan ? "<font color=\"" + Theme.text + "\"><b>" + Studio.formatNumber(root.files.length) + " chương</b></font> · " +
                              Logic.approx(root.scan.totals.words, root.scan.totals.estimated) + " chữ · khoảng " + Studio.formatLength(root.scan.totals.audioSeconds) : " "
        }
        Flow {
            id: buttons
            y: root.narrow ? 20 + total.height + 8 : 20 + (total.height - height) / 2
            x: root.narrow ? 0 : parent.width - width
            width: root.narrow ? parent.width : fit
            spacing: 4
            readonly property real fit: {
                let sum = 0
                for (let i = 0; i < children.length; ++i) if (children[i].visible) sum += children[i].width + spacing
                return Math.max(0, sum - spacing)
            }
            Button { objectName: "newAddFiles"; visible: root.dialogs; text: "Thêm file"; icon: "file-text"; kind: "ghost"; size: "sm"; onActivated: root.filesRequested() }
            Button {
                objectName: "newAddUpload"
                visible: root.browser
                text: root.uploading ? Upload.progressLabel(root.uploading) : "Thêm file"
                icon: "upload"
                kind: "ghost"
                size: "sm"
                busy: Boolean(root.uploading)
                enabled: !root.uploading
                onActivated: root.filesRequested()
            }
            Button {
                objectName: "newAddCancel"
                visible: root.browser && Boolean(root.uploading)
                text: root.form && root.form.stopping ? "Đang dừng…" : "Huỷ gửi"
                kind: "ghost"
                size: "sm"
                enabled: !(root.form && root.form.stopping)
                onActivated: root.form.cancelUpload()
            }
            Button { objectName: "newReselect"; text: "Chọn lại"; kind: "ghost"; size: "sm"; onActivated: root.form.setPaths([]) }
        }
    }
    // Truyện dài: chọn nhanh làm N chương đầu, phần còn lại để đợt sau
    Collapse {
        width: parent.width
        open: Boolean(root.form) && root.form.totalFound > Logic.CHAPTER_LIMITS[0] && !root.form.splitting
        Item {
            width: parent.width
            height: 12 + limitRow.height
            Flow {
                id: limitRow
                objectName: "newLimitRow"
                y: 12
                width: parent.width
                spacing: 8
                Text { height: 36; verticalAlignment: Text.AlignVCenter; text: "Đợt này làm"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                ChoiceRow {
                    objectName: "newLimit"
                    width: Math.min(implicitWidth, limitRow.width)
                    label: "Đợt này làm bao nhiêu chương"
                    options: {
                        const total = root.form ? root.form.totalFound : 0
                        return Logic.CHAPTER_LIMITS.filter(count => count < total).map(count => ({value: String(count), label: count + " chương đầu"}))
                            .concat([{value: "all", label: "Cả " + Studio.formatNumber(total) + " chương"}])
                    }
                    value: root.form && root.form.draft.limit ? String(root.form.draft.limit) : "all"
                    onPicked: value => root.form.update({limit: value === "all" ? null : Number(value)})
                }
                Text {
                    objectName: "newLimitLater"
                    visible: Boolean(root.form) && Boolean(root.form.draft.limit) && root.form.later > 0
                    height: 36
                    verticalAlignment: Text.AlignVCenter
                    text: "· còn " + Studio.formatNumber(root.form ? root.form.later : 0) + " chương cho đợt sau"
                    color: Theme.text2
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
        }
    }
    // Danh sách chương
    ImportFold {
        width: parent.width
        storageKey: "chapters"
        prefix: "fold.new-project."
        title: "Danh sách chương"
        summary: Studio.formatNumber(root.files.length) + " chương"
        defaultOpen: root.files.length <= 4
        Item { width: parent.width; height: 8 }
        Item {
            width: parent.width
            height: Math.min(list.contentHeight, 340)
            Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            ListView {
                id: list
                objectName: "newChapterList"
                anchors.fill: parent
                clip: true
                model: rows
                boundsBehavior: Flickable.StopAtBounds
                reuseItems: false
                cacheBuffer: 240
                Accessible.role: Accessible.List
                Accessible.name: "Các chương sẽ làm"
                delegate: Collapse {
                    id: cell
                    objectName: "newChapterRow"
                    required property int index
                    required property string key
                    required property bool gone
                    required property bool appear
                    property bool entered: !appear
                    readonly property var file: root.byKey[key]
                    readonly property int at: root.position[key] === undefined ? -1 : root.position[key]
                    // Vạch "Phần N bắt đầu" trước chương đầu mỗi phần (khỏi đối số chương với ô "từ chương")
                    readonly property int part: root.starts && at >= 0 && root.form ? root.form.volumeStarts.indexOf(at + 1) : -1
                    width: list.width
                    open: entered && !gone
                    onSettledChanged: if (settled && gone) Qt.callLater(function() { root.drop(cell.key) })
                    Component.onCompleted: {
                        if (gone) Qt.callLater(function() { root.drop(cell.key) })
                        else if (appear) Qt.callLater(function() { cell.entered = true })
                    }
                    Collapse {
                        width: parent.width
                        open: cell.part >= 0
                        Item {
                            width: parent.width
                            height: bar.height + 13
                            Row {
                                id: bar
                                x: 12
                                y: 6
                                spacing: 8
                                Icon { y: 1; name: "layers"; size: 14; color: Theme.accentText }
                                Text {
                                    width: cell.width - 48
                                    text: "Phần " + (cell.part + 1) + " bắt đầu"
                                    color: Theme.accentText
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: Theme.sizeCaption
                                    font.weight: Theme.weightBold
                                }
                            }
                            Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.accent; opacity: 0.3 }
                        }
                    }
                    Item {
                        id: line
                        width: parent.width
                        height: 16 + Math.max(names.height, figures.height, 32)
                        HoverHandler { id: over }
                        Rectangle { visible: cell.index > 0 && cell.part < 0; width: parent.width; height: 1; color: Theme.line }
                        Text {
                            x: 12
                            y: 8
                            width: Math.max(16, String(root.files.length).length * 8)
                            horizontalAlignment: Text.AlignRight
                            text: cell.at >= 0 ? cell.at + 1 : ""
                            color: Theme.text2
                            font.pixelSize: Theme.sizeCaption
                            font.features: { "tnum": 1 }
                            lineHeight: 1.4
                        }
                        Column {
                            id: names
                            readonly property real lead: 12 + Math.max(16, String(root.files.length).length * 8) + 8
                            x: lead
                            y: 8
                            width: parent.width - lead - 90 - 36 - 12 - 16
                            Text {
                                width: parent.width
                                text: cell.file ? (cell.file.firstLine || cell.file.title) : " "
                                color: Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBodySmall
                                font.weight: Theme.weightMedium
                            }
                            Text {
                                width: parent.width
                                text: cell.file ? cell.file.name : " "
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                            }
                        }
                        Column {
                            id: figures
                            x: parent.width - 90 - 36 - 12 - 8
                            y: 8
                            width: 90
                            Text {
                                width: parent.width
                                horizontalAlignment: Text.AlignRight
                                text: cell.file ? Logic.approx(cell.file.words, cell.file.estimated) + " chữ" : " "
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.features: { "tnum": 1 }
                            }
                            Text {
                                visible: Boolean(cell.file) && cell.file.chars > 0
                                width: parent.width
                                horizontalAlignment: Text.AlignRight
                                text: cell.file && cell.file.chars > 0 ? Logic.approx(cell.file.chars, cell.file.estimated) + " ký tự" : ""
                                color: Theme.text3
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                                font.features: { "tnum": 1 }
                            }
                        }
                        IconButton {
                            id: remove
                            objectName: "newChapterRemove"
                            x: parent.width - 36 - 8
                            y: 4
                            width: 32
                            height: 32
                            icon: "trash-2"
                            iconSize: 16
                            tip: "Bỏ chương này"
                            ink: Theme.text2
                            hoverInk: Theme.danger
                            opacity: root.narrow || over.hovered || activeFocus ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            Accessible.name: cell.file ? "Bỏ chương " + cell.file.name : "Bỏ chương"
                            onClicked: if (cell.file) root.form.removeChapter(cell.file.path)
                        }
                    }
                }
                ScrollEdges { target: list; color: Theme.bg; x: list.x; y: list.y; width: list.width; height: list.height }
                Scrollbar { target: list }
                SmoothWheel { flick: list }
            }
        }
    }
    Prose {
        objectName: "newSkipped"
        visible: root.scan && root.scan.skipped.length > 0
        topPadding: visible ? 8 : 0
        small: true
        text: root.scan && root.scan.skipped.length ? "Bỏ qua " + root.scan.skipped.length + " file không phải .txt." : ""
    }
    // File sách hỏng / PDF scan nằm cạnh file tốt, thư mục có cả TXT lẫn EPUB, trang chỉ có ảnh bị bỏ: không chặn, nhưng nói ra
    Repeater {
        model: root.scan ? (root.scan.errors || []).map(error => "Bỏ qua " + error).concat(root.scan.notes || []) : []
        delegate: Prose {
            required property string modelData
            objectName: "newScanNote"
            topPadding: 8
            small: true
            tone: Theme.warning
            text: modelData
        }
    }
}
