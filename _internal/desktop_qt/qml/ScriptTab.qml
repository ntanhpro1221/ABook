import QtQuick
import ABook
import "ScriptLogic.js" as S
import "CastLogic.js" as Cast
import "StudioLogic.js" as Studio

// Tab "Kịch bản" của dự án (ScriptTab.tsx, docs/STUDIO_REVIEW.md mục 3): đọc cả chương như kịch bản - câu nào của ai - và đổi người nói của bất kỳ câu
// thoại hay nội tâm nào. Hộp "Việc cần duyệt" chỉ đưa ra chỗ máy nghi; ở đây người nghe duyệt cả chương. Sửa đi đúng đường của thẻ "Ai nói câu này"
// (POST /speaker -> overrides.json -> dây chuyền áp ở ranh giới chương, câu đã thu thì thu lại); mỗi lần sửa hay xác nhận là một nhãn cho vòng học.
// Thanh chương + chú giải người nói DÍNH ở đầu khung khi cuộn (`flick` = danh sách của trang dự án). Bàn phím như web: ↑ ↓ / j k chọn câu (Shift chọn
// nhiều), phím số gán người theo số rồi sang câu kế, Enter danh sách người, P nghe, R thu lại, E cách đọc, / tìm chữ, Ctrl+Z hoàn tác, Esc bỏ chọn.
Item {
    id: root
    property var store: null
    property var work: null
    property string bookId: ""
    property Flickable flick: null
    property Item overlay: null
    property string pendingNote: work ? work.pendingNote : ""
    // Mở từ nơi khác (thẻ việc, menu chương): chương, câu cần tới, có mở sẵn ô chọn người không
    property var target: null
    property var remembered: null
    signal positionChanged(int chapter, string line)
    property string restoreLine: ""
    property bool restorePick: false
    property bool restoring: true
    property bool initialized: false

    property string filter: "all"
    property string who: ""
    property string findText: ""
    property int findAt: 0
    property int asked: 0
    property var added: []
    property string active: ""
    property var selected: []
    property string anchorLine: ""
    property string menuLine: ""
    property string deliveryLine: ""
    property string openedLine: ""
    property real stick: 0
    property var rowById: ({})
    readonly property bool narrow: width < 600
    readonly property alias scriptStore: scripts

    ScriptStore {
        id: scripts
        store: root.store
        work: root.work
        bookId: root.bookId
        wanted: root.visible
        chapterId: S.startChapter(scripts.chapters, root.asked)
    }
    readonly property var chapters: scripts.chapters
    readonly property var script: scripts.data
    readonly property var entry: chapters.find(chapter => chapter.chapterId === scripts.chapterId) || null
    readonly property var shown: script ? S.visibleLines(script.lines, filter, who || null) : []
    readonly property var speechRows: shown.filter(item => S.isSpeech(item.line)).map(item => item.line)
    readonly property var activeLine: speechRows.find(line => line.stableId === active) || null
    readonly property var people: S.people(script, added)
    readonly property int unnamed: script ? S.said(script.lines, S.UNNAMED) : 0
    readonly property int doubts: script ? script.lines.filter(line => line.hint).length : entry ? entry.hints : 0
    // Chỗ ô tìm chữ khớp (trong câu đang hiện, theo thứ tự đọc): {stableId: [[đầu, cuối]...]}
    readonly property var matches: {
        const out = {}
        if (!findText.trim()) return out
        for (const item of shown) {
            if (item.context) continue
            const ranges = S.findRanges(item.line.text, findText)
            if (ranges.length) out[item.line.stableId] = ranges
        }
        return out
    }
    readonly property var matchIds: Object.keys(matches)
    readonly property string nowMatch: matchIds.length ? matchIds[S.wrapIndex(findAt, matchIds.length)] : ""
    readonly property var openLines: script ? script.lines.filter(line => line.editable && !line.wish && !line.hint) : []
    readonly property int doubtful: script ? script.lines.filter(line => line.editable && !line.wish && line.hint).length : 0
    readonly property var group: speechRows.filter(line => selected.indexOf(line.stableId) >= 0)
    readonly property int recordedInGroup: group.filter(line => line.hasAudio && line.retake !== "pending").length

    implicitHeight: page.height
    height: implicitHeight

    function restorePosition(place) {
        restoring = true
        restoreLine = place && typeof place.line === "string" ? place.line : ""
        restorePick = !!(place && place.pick)
        asked = place && Number(place.chapter) || 0
        openedLine = ""
        Later.call(root, root.openWanted)
    }
    onTargetChanged: if (initialized && target) restorePosition(target)
    Component.onCompleted: { initialized = true; restorePosition(target || remembered) }
    onActiveChanged: if (!restoring && script) positionChanged(script.chapterId, active)
    // Đổi chương thì bỏ chọn, bỏ menu (useEffect theo chapterId)
    Connections {
        target: scripts
        function onChapterIdChanged() {
            root.restoring = true
            root.active = ""; root.menuLine = ""; root.deliveryLine = ""; root.selected = []; root.anchorLine = ""
            speakerPop.close(); deliveryPop.close()
        }
    }
    onNowMatchChanged: if (nowMatch) Later.call(root, function() { root.center(root.rowItem(root.nowMatch)) })
    onFindAtChanged: if (nowMatch) Later.call(root, function() { root.center(root.rowItem(root.nowMatch)) })
    onShownChanged: Later.call(root, root.syncRows)

    // Giữ delegate theo stableId, kể cả câu đang bị lọc. Đổi bộ lọc không tạo lại
    // hàng/chữ; mỗi hàng chỉ mờ + Translate. Column dàn lại tại hai đầu hiệu ứng,
    // không hoạt họa height/y của bố cục qua từng khung.
    ListModel { id: lineModel }
    function syncRows() {
        const next = {}, visible = {}
        for (let i = 0; i < shown.length; ++i) visible[shown[i].line.stableId] = {context: shown[i].context, gap: S.gapBefore(shown, i, filter)}
        const keys = script ? script.lines.map(line => line.stableId) : []
        for (const line of script ? script.lines : []) {
            const found = visible[line.stableId]
            next[line.stableId] = {line: line, context: found ? found.context : false, gap: found ? found.gap : false, present: !!found}
        }
        for (let i = lineModel.count - 1; i >= 0; --i) if (!next[lineModel.get(i).key]) lineModel.remove(i)
        rowById = next
        for (let i = 0; i < keys.length; ++i) {
            if (i < lineModel.count && lineModel.get(i).key === keys[i]) continue
            let at = i + 1
            while (at < lineModel.count && lineModel.get(at).key !== keys[i]) ++at
            if (at < lineModel.count) lineModel.move(at, i, 1)
            else lineModel.insert(i, {key: keys[i]})
        }
        lines.forceLayout()
        Later.call(root, root.openWanted)
    }

    function go(id) {
        if (!id) return
        who = ""
        findAt = 0
        restoreLine = ""; restorePick = false
        asked = id
    }
    function setWho(value) { who = who === value ? "" : value }
    function setFilter(value) { filter = value }

    // ---- hàng và cuộn ----
    function rowItem(stableId) {
        for (let i = 0; i < rows.count; ++i) {
            const holder = rows.itemAt(i)
            if (holder && holder.row.line.stableId === stableId) return holder.row
        }
        return null
    }
    function topOf(item) { return item.mapToItem(flick.contentItem, 0, 0).y }
    // "vừa đủ thấy" (↑ ↓): tính cả thanh dính ở đầu khung
    function nearest(item) {
        if (!item || !flick) return
        const top = topOf(item), bottom = top + item.height
        const ceiling = flick.contentY + header.height + 8
        if (top < ceiling) flick.contentY = Math.max(flick.originY, top - header.height - 8)
        else if (bottom > flick.contentY + flick.height - 16) flick.contentY = bottom - flick.height + 16
    }
    // Giữa khung (chỗ khớp của ô tìm, câu mở từ thẻ việc): thấy cả câu trước lẫn câu sau
    function center(item) {
        if (!item || !flick) return
        const y = topOf(item) - (flick.height + header.height) / 2 + item.height / 2
        flick.contentY = Math.max(flick.originY, Math.min(flick.contentHeight + flick.originY - flick.height, y))
    }
    function updateStick() {
        if (!flick || !visible) { stick = 0; return }
        const top = root.mapToItem(flick.contentItem, 0, 0).y + headerSlot.y
        stick = Math.max(0, Math.min(flick.contentY - top, page.height - headerSlot.y - header.height))
    }
    Connections {
        target: root.flick
        function onContentYChanged() { root.updateStick() }
        function onHeightChanged() { root.updateStick() }
        function onContentHeightChanged() { if (root.restoring) Later.call(root, root.openWanted) }
    }
    onHeightChanged: { updateStick(); if (restoring) Later.call(root, root.openWanted) }

    function range(from, to) {
        const start = speechRows.findIndex(line => line.stableId === from)
        const end = speechRows.indexOf(to)
        if (start < 0 || end < 0) return [to.stableId]
        const low = Math.min(start, end), high = Math.max(start, end)
        return speechRows.slice(low, high + 1).map(line => line.stableId)
    }
    function focusRow(line, extend) {
        if (!line) return
        if (extend) {
            if (!anchorLine) anchorLine = active || line.stableId
            selected = range(anchorLine, line)
        } else {
            anchorLine = ""
            selected = []
        }
        active = line.stableId
        const item = rowItem(line.stableId)
        if (item) { item.forceActiveFocus(Qt.OtherFocusReason); nearest(item) }
    }
    function activate(line) {
        if (line.stableId !== active) { anchorLine = ""; selected = [] }
        active = line.stableId
    }
    function extend(line) {
        if (!anchorLine) anchorLine = active || line.stableId
        selected = range(anchorLine, line)
        active = line.stableId
    }
    // Menu đóng (chọn xong hay Esc) thì tiêu điểm về lại câu, để ↑ ↓ và phím số làm tiếp từ đó
    function backTo(stableId) {
        menuLine = ""; deliveryLine = ""
        Later.call(root, function() { const item = root.rowItem(stableId); if (item) item.forceActiveFocus(Qt.OtherFocusReason) })
    }
    // Câu đang đứng nằm trong nhóm đã chọn thì gán cả nhóm; không thì chỉ câu ấy
    function targets(line) {
        return selected.length > 1 && selected.indexOf(line.stableId) >= 0 ? speechRows.filter(item => selected.indexOf(item.stableId) >= 0) : [line]
    }
    // Câu nói kế sau nhóm (theo mã câu: gán xong thì danh sách là bản mới, đối tượng câu cũ không còn trong đó)
    function nextAfter(many) {
        const last = many[many.length - 1].stableId
        const at = speechRows.findIndex(item => item.stableId === last)
        return at >= 0 && at + 1 < speechRows.length ? speechRows[at + 1].stableId : ""
    }
    function focusId(stableId) {
        const line = speechRows.find(item => item.stableId === stableId)
        if (line) focusRow(line, false)
    }
    function pick(line, person, refocus) {
        if (refocus) { speakerPop.close(); backTo(line.stableId) }
        if (!script || !script.castReady || !line.editable) return
        const many = targets(line)
        const lines = many.filter(item => item.editable && !(item.wish && item.wish.value === person.value))
        if (!lines.length) return
        if (person.value !== S.UNNAMED && !added.some(item => item.value === person.value)) added = added.concat([person])
        // Chọn trong danh sách (Enter, bấm tên) cũng sang câu kế như phím số
        const after = nextAfter(many)
        scripts.assign(lines, person)
        if (refocus && after) Later.call(root, function() { root.focusId(after) })
    }
    // Thu lại câu đang đứng (hay cả nhóm Shift-chọn): chỉ câu đã thu và chưa xin; không câu nào thì nói vì sao
    function askRetake(line) {
        const many = targets(line)
        const lines = many.filter(item => item.hasAudio && item.retake !== "pending")
        if (!lines.length) { Api.toast(S.retakeNone(many)); return }
        scripts.retake(lines)
    }
    function openSpeaker(line, anchor) {
        if (!script || !script.castReady || !line.editable) return
        menuLine = line.stableId
        speakerPop.anchorItem = anchor
        speakerPop.show()
    }
    function openDelivery(line, anchor) {
        if (!script || !script.castReady || line.emotion === null) return
        deliveryLine = line.stableId
        deliveryPop.anchorItem = anchor
        deliveryPop.saved = false
        deliveryPop.show()
    }
    // Câu được mở từ thẻ việc: tới đó một lần (giữa khung) và mở ô chọn người nói (tìm được mọi người trong truyện)
    function openWanted() {
        if (!script) return
        if (restoreLine) {
            const line = script.lines.find(item => item.stableId === restoreLine)
            if (line) {
                const item = rowItem(line.stableId)
                if (!item) return
                // Column và footer ListView polish ở lượt khác. Đợi chiều cao
                // thật trước khi cuộn, nếu không Flickable kẹp về đầu khung cũ.
                if (flick && (height < lines.height || flick.originY + flick.contentHeight < mapToItem(flick.contentItem, 0, height).y - 1)) return
                openedLine = restoreLine
                focusRow(line, false)
                center(item)
                if (restorePick && script.castReady && line.editable) openSpeaker(line, item.speakerChip)
            }
            // Như web: câu đã mất thì giữ chương, không tự chọn câu khác.
            restoreLine = ""; restorePick = false
        }
        restoring = false
        positionChanged(script.chapterId, active)
    }

    function onKey(event) {
        if (menuLine || deliveryLine || (event.modifiers & (Qt.AltModifier | Qt.ControlModifier | Qt.MetaModifier))) return
        const index = activeLine ? speechRows.indexOf(activeLine) : -1
        const shift = Boolean(event.modifiers & Qt.ShiftModifier)
        const key = event.key
        if (key === Qt.Key_Down || key === Qt.Key_J) {
            focusRow(speechRows[Math.min(index + 1, speechRows.length - 1)], shift)
        } else if (key === Qt.Key_Up || key === Qt.Key_K) {
            focusRow(speechRows[Math.max(index - 1, 0)], shift)
        } else if (key === Qt.Key_Escape && selected.length) {
            anchorLine = ""; selected = []
        } else if (key === Qt.Key_P && !shift && activeLine && activeLine.hasAudio) {
            Clip.toggle("script-" + activeLine.segmentId, store.path("/media/books/" + bookId + "/samples/" + activeLine.segmentId))
        } else if ((key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Space) && activeLine) {
            const item = rowItem(activeLine.stableId)
            if (item) openSpeaker(activeLine, item.speakerChip)
        } else if (key === Qt.Key_Slash) {
            findField.forceActiveFocus()
        } else if (key === Qt.Key_R && activeLine) {
            askRetake(activeLine)
        } else if (key === Qt.Key_E && !shift && activeLine && script.castReady && activeLine.emotion !== null) {
            const item = rowItem(activeLine.stableId)
            if (item) openDelivery(activeLine, item.deliveryAnchor)
        } else if (key >= Qt.Key_1 && key <= Qt.Key_9 && activeLine) {
            const person = people[key - Qt.Key_1]
            if (!person) return
            const line = activeLine
            const after = nextAfter(targets(line)) || line.stableId
            pick(line, person, false)
            focusId(after)
        } else return
        event.accepted = true
    }
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: root.visible && !root.menuLine && !root.deliveryLine
        onActivated: scripts.undoLast()
    }

    Column {
        id: page
        width: parent.width
        spacing: 0
        Item { width: 1; height: 20 }
        EditBookError {
            objectName: "scriptContentsError"
            width: parent.width
            open: scripts.contents.error !== null && scripts.contents.data === null
            message: "Bạn hãy kiểm tra kết nối rồi tải lại kịch bản."
            onRetry: scripts.contents.load()
        }
        EditBookSkeleton {
            visible: scripts.contents.loading
            width: parent.width * 2 / 3
            shape: "rows"
            count: 4
            label: "Đang tải kịch bản"
        }
        EmptyState {
            objectName: "scriptEmpty"
            visible: scripts.contents.data !== null && root.chapters.length === 0
            width: parent.width
            height: visible ? implicitHeight + 40 : 0
            icon: "book-open-text"
            title: "Chưa có kịch bản"
            text: "Kịch bản hiện ra khi máy đã phân tích xong chương đầu tiên: câu nào là lời kể, câu nào của ai."
        }
        Column {
            id: main
            visible: root.chapters.length > 0
            width: parent.width
            spacing: 0
            Text {
                objectName: "scriptIntro"
                width: Math.min(parent.width, 768)
                text: "Bấm tên để đổi người nói; dấu vàng là câu cần xem."
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
            Collapse {
                objectName: "scriptNoAudio"
                width: Math.min(parent.width, 768)
                open: !!root.script && root.script.lines.length > 0 && !root.script.lines.some(line => line.hasAudio)
                Text {
                    width: parent.width
                    topPadding: 4
                    text: "Thu xong chương sẽ nghe lại được từng câu."
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
            // Chỗ của thanh dính (thanh thật nằm trên cùng, trượt theo khung khi cuộn)
            Item { id: headerSlot; width: parent.width; height: header.height }
            EditBookError {
                objectName: "scriptChapterError"
                width: parent.width
                open: scripts.script.error !== null && !root.script
                message: "Bạn hãy kiểm tra kết nối rồi tải lại chương này."
                onRetry: scripts.script.load()
            }
            Column {
                objectName: "scriptSkeleton"
                visible: !root.script && scripts.script.error === null
                width: parent.width
                topPadding: 16
                spacing: 8
                Repeater {
                    model: 8
                    delegate: Rectangle { width: parent.width; height: 36; radius: Theme.radiusControl; color: Theme.hover }
                }
            }
            Column {
                id: chapterBody
                visible: !!root.script
                width: parent.width
                spacing: 0
                Item {
                    objectName: "scriptNotReady"
                    visible: !!root.script && !root.script.castReady
                    width: parent.width
                    height: visible ? notReady.height + 24 : 0
                    Icon { y: 14; name: "clock"; size: 16; color: Theme.text2 }
                    Text {
                        id: notReady
                        x: 24; y: 12
                        width: parent.width - x
                        text: "Sửa người nói được sau bước phân vai."
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
                // Chương kể ngôi thứ nhất: máy gán nhầm câu của người khác cho "tôi" nhiều nhất - mời soát riêng câu của người kể trước
                Item {
                    objectName: "scriptFirstPerson"
                    readonly property var first: root.script ? root.script.firstPerson : null
                    visible: !!root.script && root.script.castReady && !!first && !!first.chip && root.who !== first.chip
                    width: parent.width
                    height: visible ? firstFlow.height + 12 : 0
                    Flow {
                        id: firstFlow
                        y: 12
                        width: parent.width
                        spacing: 8
                        Text {
                            width: Math.min(implicitWidth, firstFlow.width)
                            height: Math.max(32, implicitHeight)
                            verticalAlignment: Text.AlignVCenter
                            text: "Chương kể ngôi thứ nhất: máy hay nhầm câu của người khác thành của “tôi”."
                            color: Theme.text2
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                        }
                        Button {
                            objectName: "scriptFirstPersonCheck"
                            size: "sm"
                            kind: "ghost"
                            readonly property var first: parent.parent.first
                            readonly property var person: first && root.script ? root.script.cast.find(item => item.value === first.chip) : null
                            text: first ? "Soát câu của " + (person ? person.label : first.label) : ""
                            onClicked: root.setWho(first.chip)
                        }
                    }
                }
                // Đang chọn nhiều câu (Shift): một phím số gán cả nhóm; thu lại cả nhóm (chỉ câu đã thu)
                Collapse {
                    objectName: "scriptSelection"
                    width: parent.width
                    open: root.selected.length > 1
                    Item {
                        width: parent.width
                        height: selectionFlow.height + 12
                        Flow {
                            id: selectionFlow
                            x: 12; y: 12
                            width: parent.width - 24
                            spacing: 8
                            Text {
                                height: 32
                                verticalAlignment: Text.AlignVCenter
                                text: "Đang chọn " + root.selected.length + " câu"
                                color: Theme.text
                                font.pixelSize: 13
                                font.weight: Theme.weightBold
                            }
                            Text {
                                width: Math.min(implicitWidth, selectionFlow.width)
                                height: Math.max(32, implicitHeight)
                                verticalAlignment: Text.AlignVCenter
                                text: "- phím số hay chọn người ở một câu trong nhóm gán cả " + root.selected.length + " câu · Esc bỏ chọn"
                                color: Theme.text2
                                wrapMode: Text.Wrap
                                font.pixelSize: 13
                            }
                            Button {
                                objectName: "scriptGroupRetake"
                                size: "sm"
                                kind: "ghost"
                                icon: "refresh-cw"
                                enabled: root.recordedInGroup > 0 && !scripts.retaking
                                tip: root.recordedInGroup ? "" : "Các câu đang chọn chưa thu hay đã xin thu lại"
                                text: root.recordedInGroup ? "Thu lại " + root.recordedInGroup + " câu" : "Chưa có bản thu"
                                onClicked: root.askRetake(root.group[0])
                            }
                        }
                    }
                }
                EmptyState {
                    objectName: "scriptNoLines"
                    visible: !!root.script && root.shown.length === 0
                    width: parent.width
                    height: visible ? implicitHeight + 40 : 0
                    icon: "book-open-text"
                    title: S.emptyTitle(root.who, S.whoLabel(root.people, root.who), root.filter)
                    text: S.emptyText(root.who, root.filter)
                }
                Column {
                    id: lines
                    objectName: "scriptLines"
                    visible: height > topPadding
                    width: parent.width
                    topPadding: 12
                    Keys.onPressed: event => root.onKey(event)
                    Accessible.role: Accessible.List
                    Accessible.name: root.script ? "Kịch bản " + root.script.title : ""
                    Repeater {
                        id: rows
                        model: lineModel
                        delegate: Item {
                            id: holder
                            required property string key
                            readonly property var item: root.rowById[key] || ({line: {}, context: false, gap: false, present: false})
                            readonly property bool gap: item.gap
                            readonly property bool present: item.present
                            property real reveal: present ? 1 : 0
                            property bool motionReady: false
                            readonly property bool settled: reveal === (present ? 1 : 0)
                            visible: present || reveal > 0
                            enabled: present
                            opacity: reveal
                            transform: Translate { y: Theme.reduceMotion ? 0 : (holder.present ? 6 : -4) * (1 - holder.reveal) }
                            Behavior on reveal {
                                enabled: holder.motionReady
                                NumberAnimation {
                                    duration: Theme.reduceMotion ? Theme.motionFast : (holder.present ? Theme.motionMedium : Theme.motionMediumOut)
                                    easing.type: Easing.BezierSpline
                                    easing.bezierCurve: holder.present ? Theme.easeDecelerate : Theme.easeAccelerate
                                }
                            }
                            Component.onCompleted: motionReady = true
                            property alias row: scriptRow
                            width: lines.width
                            height: scriptRow.height + (gap ? 8 : 0)
                            ScriptRow {
                                id: scriptRow
                                y: holder.gap ? 8 : 0
                                width: parent.width
                                line: holder.item.line
                                context: holder.item.context
                                script: root.script || ({cast: [], others: [], castReady: false})
                                bookId: root.bookId
                                store: root.store
                                active: line.stableId === root.active
                                selected: root.selected.length > 1 && root.selected.indexOf(line.stableId) >= 0
                                marks: root.matches[line.stableId] || []
                                markNow: line.stableId === root.nowMatch
                                pendingNote: root.pendingNote
                                onActivate: root.activate(line)
                                onExtend: root.extend(line)
                                onOpenSpeaker: anchor => root.openSpeaker(line, anchor)
                                onOpenDelivery: anchor => root.openDelivery(line, anchor)
                                onPick: person => root.pick(line, person, true)
                                onRetake: root.askRetake(line)
                                onCancelRetake: scripts.cancelRetake([line])
                                onActiveFocusChanged: if (activeFocus && S.isSpeech(line) && root.active !== line.stableId) root.activate(line)
                            }
                        }
                    }
                }
                // Chân chương: "Duyệt N câu" (coi người nói của các câu chưa ai quyết là đúng) bên trái, "Chương sau" sát phải (justify-between);
                // không đủ chỗ trên một dòng thì "Chương sau" xuống dòng dưới (flex-wrap)
                Item {
                    id: footer
                    objectName: "scriptFooter"
                    readonly property real natural: Math.max(confirmButton.visible ? confirmButton.width : 0, footerNote.implicitWidth)
                    readonly property bool sameLine: !nextChapter.visible || natural + 12 + nextChapter.width <= width
                    width: parent.width
                    height: 41 + (sameLine ? Math.max(footerLeft.height, nextChapter.visible ? nextChapter.height : 0) : footerLeft.height + 12 + nextChapter.height)
                    Rectangle { y: 24; width: parent.width; height: 1; color: Theme.line }
                    Column {
                        id: footerLeft
                        y: 41 + (footer.sameLine && nextChapter.visible ? Math.max(0, (nextChapter.height - height) / 2) : 0)
                        width: Math.min(footer.natural, footer.width)
                        spacing: 4
                        Button {
                            id: confirmButton
                            objectName: "scriptConfirm"
                            visible: !!root.script && root.script.castReady && root.openLines.length > 0
                            size: "sm"
                            kind: "ghost"
                            icon: "check"
                            busy: scripts.confirming
                            text: "Duyệt " + root.openLines.length + " câu"
                            onClicked: scripts.confirm(root.openLines)
                        }
                        Text {
                            id: footerNote
                            objectName: "scriptFooterNote"
                            width: parent.width
                            text: root.script ? S.footerNote(root.script, root.openLines.length, root.doubtful) : ""
                            color: Theme.text3
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                        }
                    }
                    Interactive {
                        id: nextChapter
                        objectName: "scriptNextChapter"
                        visible: !!root.script && root.script.next !== null
                        x: footer.sameLine ? footer.width - width : -4
                        y: footer.sameLine ? 41 + Math.max(0, (footerLeft.height - height) / 2) : 41 + footerLeft.height + 12
                        width: nextRow.width + 8
                        height: 40
                        Accessible.role: Accessible.Button
                        Accessible.name: "Chương sau"
                        onClicked: root.go(root.script.next)
                        Row {
                            id: nextRow
                            x: 4
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Text { text: "Chương sau"; color: nextChapter.hovered ? Theme.text : Theme.text2; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                            Icon { anchors.verticalCenter: parent.verticalCenter; name: "skip-forward"; size: 16; color: nextChapter.hovered ? Theme.text : Theme.text2 }
                        }
                    }
                }
            }
        }
    }

    // ---- thanh dính: chương, tìm chữ, bộ lọc, chú giải người nói, phím tắt ----
    Rectangle {
        id: header
        objectName: "scriptHeader"
        visible: main.visible
        x: -8
        y: main.y + headerSlot.y + root.stick
        z: 2
        width: root.width + 16
        height: headerBox.height + 16
        color: Theme.bg
        Column {
            id: headerBox
            x: 8; y: 8
            width: root.width
            spacing: 8
            Flow {
                id: toolbar
                width: parent.width
                spacing: 16
                Row {
                    id: chapterNav
                    width: root.narrow ? toolbar.width : implicitWidth
                    spacing: 0
                    Interactive {
                        id: chapterButton
                        objectName: "scriptChapter"
                        x: -10
                        width: Math.min(chapterTitle.implicitWidth + 40, (root.narrow ? toolbar.width : 416) - 80)
                        height: Math.max(36, chapterTitle.height + 12)
                        pressScaling: false
                        Accessible.role: Accessible.ComboBox
                        Accessible.name: "Chương"
                        onClicked: chapterMenu.toggle()
                        Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: chapterButton.hovered || chapterMenu.open ? 1 : 0 }
                        Text {
                            id: chapterTitle
                            x: 10
                            width: Math.min(implicitWidth, chapterButton.width - 36)
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.entry ? S.chapterLabel(root.entry) : ""
                            color: Theme.text
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            font.weight: Theme.weightMedium
                        }
                        Icon {
                            x: chapterTitle.x + chapterTitle.width + 6
                            anchors.verticalCenter: parent.verticalCenter
                            name: "chevron-down"
                            size: 16
                            color: Theme.text3
                            rotation: chapterMenu.open ? 180 : 0
                            Behavior on rotation { NumberAnimation { duration: Theme.motionFast } }
                        }
                    }
                    IconButton {
                        objectName: "scriptPrevious"
                        icon: "skip-back"
                        tip: "Chương trước"
                        Accessible.name: "Chương trước"
                        enabled: !!root.script && !!root.script.previous
                        opacity: enabled ? 1 : 0.4
                        onClicked: root.go(root.script.previous)
                    }
                    IconButton {
                        objectName: "scriptNext"
                        icon: "skip-forward"
                        tip: "Chương sau"
                        Accessible.name: "Chương sau"
                        enabled: !!root.script && !!root.script.next
                        opacity: enabled ? 1 : 0.4
                        onClicked: root.go(root.script.next)
                    }
                }
                Text {
                    visible: root.narrow && !!root.entry && text !== ""
                    width: toolbar.width
                    text: root.entry ? S.chapterExtras(root.entry) : ""
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                Item {
                    width: root.narrow ? toolbar.width : 240
                    height: 36
                    WorkField {
                        id: findField
                        objectName: "scriptFind"
                        width: parent.width
                        y: 2
                        leftPadding: 34
                        rightPadding: findCount.width + 16
                        label: "Tìm chữ trong chương này"
                        placeholderText: "Tìm chữ trong chương…"
                        escapeLocal: text !== ""
                        onTextChanged: { root.findText = text; root.findAt = 0 }
                        onEscaped: text = ""
                        Keys.onPressed: event => {
                            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                root.findAt += (event.modifiers & Qt.ShiftModifier) ? -1 : 1
                                event.accepted = true
                            }
                        }
                    }
                    Icon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 16; color: Theme.text3 }
                    Text {
                        id: findCount
                        objectName: "scriptFindCount"
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        text: S.findCount(root.findText, root.findAt, root.matchIds.length)
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                        font.features: {"tnum": 1}
                        Accessible.role: Accessible.StaticText
                    }
                }
                ChoiceRow {
                    objectName: "scriptFilter"
                    label: "Hiện câu nào"
                    value: root.filter
                    options: [{value: "all", label: "Cả chương"}, {value: "speech", label: "Chỉ lời nói"}, {value: "doubt", label: "Máy nghi · " + root.doubts}]
                    onPicked: value => root.setFilter(value)
                }
            }
            // Chú giải người nói: bấm để chỉ xem câu của họ, bấm lại để xem tất cả
            Flow {
                objectName: "scriptLegend"
                visible: !!root.script && (root.people.length > 0 || root.unnamed > 0)
                x: -4
                width: parent.width + 4
                spacing: 4
                Accessible.role: Accessible.Grouping
                Accessible.name: "Người nói trong chương - bấm để chỉ xem câu của họ, bấm lại để xem tất cả"
                Repeater {
                    model: S.legend(root.people, root.unnamed)
                    delegate: Interactive {
                        id: chip
                        required property var modelData
                        readonly property bool on: root.who === modelData.person.value
                        objectName: "legendChip"
                        width: chipRow.width + 12
                        height: 28
                        opacity: root.who && !on ? 0.5 : 1
                        tip: modelData.person.value === S.UNNAMED ? "Câu máy chưa biết ai nói, và vai phụ không tên" : ""
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.person.label
                        Accessible.checked: on
                        onClicked: root.setWho(modelData.person.value)
                        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                        Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.hover; opacity: chip.on || chip.hovered ? 1 : 0 }
                        Row {
                            id: chipRow
                            x: 2
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            Rectangle {
                                id: badge
                                width: 24; height: 24; radius: width / 2
                                readonly property real hue: Cast.hueOf(chip.modelData.person.label)
                                color: Cast.avatarFill(hue, Theme.dark)
                                Text { anchors.centerIn: parent; text: chip.modelData.badge; color: Cast.avatarInk(badge.hue, Theme.dark); font.pixelSize: 11; font.weight: Theme.weightBold }
                            }
                            Text { objectName: "legendName"; anchors.verticalCenter: parent.verticalCenter; text: chip.modelData.person.label; color: Theme.text; font.pixelSize: 13; font.weight: Theme.weightMedium }
                            Text { anchors.verticalCenter: parent.verticalCenter; text: Studio.formatNumber(chip.modelData.person.lines); color: Theme.text3; font.pixelSize: 13; font.features: {"tnum": 1} }
                        }
                    }
                }
                Interactive {
                    id: showAll
                    objectName: "legendAll"
                    visible: root.who !== ""
                    width: showAllRow.width + 16
                    height: 28
                    Accessible.role: Accessible.Button
                    Accessible.name: "Xem tất cả"
                    onClicked: root.setWho(root.who)
                    Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.hover; opacity: showAll.hovered ? 1 : 0 }
                    Row {
                        id: showAllRow
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "x"; size: 12; color: Theme.accentText }
                        Text { text: "Xem tất cả"; color: Theme.accentText; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
                    }
                }
            }
            MoreInfo {
                objectName: "scriptKeys"
                visible: !!root.script && root.script.castReady && root.people.length > 0 && root.width >= 720
                width: parent.width
                label: "Phím tắt"
                Flow {
                    width: parent.width
                    spacing: 4
                    Kbd_ { text: "Bàn phím:" ; plain: true }
                    LookKbd { text: "↑" }
                    LookKbd { text: "↓" }
                    Kbd_ { text: "chọn câu ("; plain: true }
                    LookKbd { text: "Shift" }
                    Kbd_ { text: "chọn nhiều) ·"; plain: true }
                    LookKbd { text: "1" }
                    Kbd_ { text: "–"; plain: true }
                    LookKbd { text: String(Math.min(S.HOTKEYS, root.people.length)) }
                    Kbd_ { text: "gán người theo số rồi sang câu kế ·"; plain: true }
                    LookKbd { text: "Enter" }
                    Kbd_ { text: "danh sách ·"; plain: true }
                    LookKbd { text: "P" }
                    Kbd_ { text: "nghe câu ·"; plain: true }
                    LookKbd { text: "R" }
                    Kbd_ { text: "thu lại câu ·"; plain: true }
                    LookKbd { text: "/" }
                    Kbd_ { text: "tìm chữ ·"; plain: true }
                    LookKbd { text: "Ctrl" }
                    Kbd_ { text: "+"; plain: true }
                    LookKbd { text: "Z" }
                    Kbd_ { text: "hoàn tác"; plain: true }
                }
            }
        }
    }

    // ---- bảng nổi: chọn chương, chọn người nói, cách đọc câu ----
    ScriptChapterMenu {
        id: chapterMenu
        objectName: "scriptChapterMenu"
        parent: root.overlay || root
        anchorItem: chapterButton
        chapters: root.chapters
        chapterId: scripts.chapterId
        narrow: root.narrow
        onChosen: id => root.go(id)
    }
    Popover {
        id: speakerPop
        objectName: "scriptSpeakerPop"
        parent: root.overlay || root
        panelWidth: 288
        pad: Theme.s8
        readonly property var line: root.script ? root.script.lines.find(item => item.stableId === root.menuLine) || null : null
        onOpenChanged: if (!open && root.menuLine) root.backTo(root.menuLine)
        Loader {
            width: parent.width
            active: speakerPop.open && !!speakerPop.line
            sourceComponent: ScriptSpeakerMenu {
                objectName: "scriptSpeakerMenu"
                width: parent ? parent.width : 0
                line: speakerPop.line
                script: root.script
                onPicked: person => root.pick(speakerPop.line, person, true)
            }
        }
    }
    Popover {
        id: deliveryPop
        objectName: "scriptDeliveryPop"
        parent: root.overlay || root
        panelWidth: 340
        pad: Theme.s8
        maxHeight: 640
        property bool saved: false
        property bool dirty: false
        readonly property var line: root.script ? root.script.lines.find(item => item.stableId === root.deliveryLine) || null : null
        // Esc / bấm ra ngoài khi còn lựa chọn chưa lưu: bảng đóng và lựa chọn mất - nói ra thay vì lặng lẽ
        onOpenChanged: if (!open && root.deliveryLine) {
            if (dirty && !saved) Api.toast("Chưa lưu cách đọc của câu này\nLựa chọn vừa rồi đã bỏ. Mở lại và bấm “Lưu cho câu này” để giữ.")
            dirty = false
            root.backTo(root.deliveryLine)
        }
        Loader {
            width: parent.width
            active: deliveryPop.open && !!deliveryPop.line
            sourceComponent: ScriptDelivery {
                objectName: "scriptDelivery"
                width: parent ? parent.width : 0
                line: deliveryPop.line
                script: root.script
                work: root.work
                onUnsavedChanged: deliveryPop.dirty = unsaved
                onSave: change => {
                    const line = deliveryPop.line
                    deliveryPop.saved = true
                    deliveryPop.close()
                    scripts.fixLine(line, change)
                }
            }
        }
    }

    component Kbd_: Text {
        property bool plain: false
        height: 24
        verticalAlignment: Text.AlignVCenter
        color: Theme.text2
        font.pixelSize: Theme.sizeCaption
    }
}
