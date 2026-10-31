import QtQuick
import ABook
import "SizeFormat.js" as Size
import "VoiceLogic.js" as VoiceLogic

// Thẻ một mô-đun giọng trên máy trong Cài đặt › Giọng đọc (VieneuModuleCard.tsx: "Giọng VieNeu", "Giọng Supertonic"): chọn giọng muốn tải (có "Khuyên dùng"
// theo máy), thấy đúng dung lượng còn thiếu, bấm mới tải; đang tải thì thanh tiến độ + "Huỷ" (phần đã tải giữ để làm tiếp); tải xong máy tự đo vài giây
// và nói giọng có kịp người nghe không - không kịp thì đề nghị đổi, người dùng bấm mới đổi. "Gỡ" một giọng đã tải hỏi trước (hộp thoại có lớp Back riêng).
// Hỏi lại trạng thái mỗi giây khi đang tải / đo; xong thì `changed()` để danh sách giọng và cỡ thẻ kia hỏi lại.
Item {
    id: root
    UiActivity { target: root; id: activity; onResumed: root.refresh() }
    property var copy: VoiceLogic.VIENEU
    property bool preselect: true
    property var status: ({})
    property var chosen: null                // null: theo lựa chọn đánh dấu sẵn
    property bool busy: false
    property var asking: null                // {id, label, use}: use undefined = đang hỏi máy chủ, null = không biết
    property string askLabel: ""
    property real peak: 0                    // % không bao giờ lùi trong lúc tải
    property var sizes: ({})                 // cỡ mỗi lựa chọn đứng yên ở cỡ lúc bấm tải
    property bool wasWorking: false
    readonly property string lowerName: VoiceLogic.lowerFirst(copy.name)
    readonly property bool ready: Array.isArray(status.choices)
    readonly property bool downloading: status.state === "downloading"
    readonly property bool working: VoiceLogic.working(status)
    readonly property bool failed: status.state === "error"
    readonly property bool canPick: !working && status.state !== "unsupported"
    readonly property var picked: chosen !== null ? chosen : (ready ? VoiceLogic.initialChoices(status, preselect) : [])
    readonly property var missing: ready ? picked.filter(id => { const found = status.choices.find(c => c.id === id); return !(found && found.installed) }) : []
    readonly property real bytes: ready ? VoiceLogic.selectionBytes(status, missing) : 0
    readonly property var shown: downloading ? Object.assign({}, status, {done: peak}) : status
    readonly property var suggestion: status.suggestion && !working ? VoiceLogic.suggestionText(status.suggestion) : null
    readonly property bool hasMeasure: Object.keys(status.benchmark || {}).length > 0 || Boolean(status.accelerated && status.accelerated.problem)
    readonly property bool hasActions: canPick && !status.restart && (status.state === "outdated" || missing.length > 0 || hasMeasure)
    property var keptSuggestion: ({message: "", action: ""})     // giữ chữ lúc khối đề nghị khép lại
    signal changed()
    signal switched(string voice)
    objectName: "voiceModule." + copy.key
    implicitHeight: card.height
    height: implicitHeight

    function refresh() {
        Api.quiet("GET", copy.path, null, function(data, error) { if (!error && data) root.status = data })
    }
    // Một việc ghi lên mô-đun; lỗi thì lời báo hai dòng (tiêu đề + nguyên nhân) như toast.error(failure, {description})
    function run(suffix, body, failure, after) {
        busy = true
        Api.quiet("POST", copy.path + suffix, body, function(data, error) {
            root.busy = false
            if (error) Api.notice = failure + "\n" + error
            else root.status = data
            if (after) after()
        })
    }
    function start(choices, failure) { run("", choices ? {choices: choices} : {}, failure || "Chưa tải được " + lowerName) }
    function remove(id) {
        run("/remove", {choice: id}, "Chưa gỡ được " + lowerName, function() { root.changed() })
    }
    function toggle(id, on) { chosen = VoiceLogic.toggleChoice(status, picked, id, on) }
    // "Gỡ" một giọng đã tải: hỏi trước. Bản tăng tốc chỉ là bản chạy nhanh hơn của cùng giọng: không hỏi cuốn nào.
    function ask(id, label) {
        const holdsVoices = id !== "fast" && id !== "supertonic_fast" && copy.key === "supertonic"
        askLabel = label
        asking = {id: id, label: label, use: holdsVoices ? undefined : null}
        confirm.show()
        if (holdsVoices) {
            Api.quiet("GET", "/api/studio/supertonic/use", null, function(data, error) {
                if (root.asking && root.asking.id === id) root.asking = {id: id, label: label, use: error ? null : data}
            })
        }
    }
    function switchTo() {
        const suggestion = status.suggestion
        if (!suggestion) return
        if (suggestion.switchTo === "nano" && !suggestion.installed) { run("", {choices: ["nano"]}, "Chưa tải được " + lowerName); return }
        function done(target) {
            root.switched(target)
            Api.notice = suggestion.switchTo === "nano" ? "Đã chuyển sang giọng VieNeu Nano" : "Đã chuyển sang giọng trực tuyến"
        }
        if (suggestion.switchTo !== "nano") { done(VoiceLogic.ONLINE_VOICE); return }
        Api.quiet("GET", "/api/readaloud/voices", null, function(voices, error) {
            const found = !error && Array.isArray(voices) ? voices.find(v => v.id.indexOf("vieneu:nano/") === 0) : undefined
            done(found ? found.id : VoiceLogic.ONLINE_VOICE)
        })
    }

    onStatusChanged: {
        if (status.state === "downloading") peak = Math.max(peak, status.done || 0)
        else {
            peak = 0
            const next = {}
            for (const choice of status.choices || []) next[choice.id] = choice.bytes
            sizes = next
        }
    }
    onSuggestionChanged: if (suggestion) keptSuggestion = suggestion
    onWorkingChanged: {
        if (wasWorking && !working) changed()
        wasWorking = working
    }
    // Tải <-> Huỷ thay chỗ nhau: tiêu điểm theo sang nút vừa hiện
    onDownloadingChanged: {
        if (downloading && startButton.activeFocus) Later.call(root, function() { cancelButton.forceActiveFocus(Qt.TabFocusReason) })
        else if (!downloading && cancelButton.activeFocus) Later.call(root, function() { startButton.forceActiveFocus(Qt.TabFocusReason) })
    }
    Component.onCompleted: refresh()
    Timer { interval: 1000; running: activity.running && root.working; repeat: true; onTriggered: root.refresh() }

    Collapse {
        id: card
        width: root.width
        open: root.ready
        Text {
            width: parent.width
            text: root.copy.title
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
            font.weight: 600
        }
        // Lỗi tải không ở đầu thẻ mà ngay trên nút Thử lại, nơi người dùng đang nhìn
        VoiceNote { width: parent.width; objectName: "moduleLabel"; tabular: true; text: root.ready && !root.failed ? VoiceLogic.moduleLabel(root.shown, root.copy) : ""; px: Theme.sizeBodySmall }
        VoiceBlock {
            width: parent.width
            show: root.downloading
            Item {
                width: parent.width
                height: Math.max(6, cancelButton.implicitHeight)
                Rectangle {
                    id: track
                    width: parent.width - cancelButton.width - 12
                    height: 6
                    radius: height / 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.line
                    Accessible.role: Accessible.ProgressBar
                    Accessible.name: "Đang tải " + root.lowerName
                    Rectangle {
                        objectName: "moduleBar"
                        width: track.width * VoiceLogic.percent(root.shown) / 100
                        height: parent.height
                        radius: height / 2
                        color: Theme.accent
                        // Phần tô theo giá trị tự đổi: vẽ thẳng, không Behavior (luật chủ sách 30-10; điện thoại native cũng vậy)
                    }
                }
                Button {
                    id: cancelButton
                    objectName: "moduleCancel"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    size: "sm"
                    kind: "text"
                    text: "Huỷ"
                    busy: root.busy
                    onActivated: root.run("/cancel", {}, "Chưa huỷ được việc tải " + root.lowerName)
                }
            }
        }
        Column {
            objectName: "voiceDownloadList"
            width: Math.min(parent.width, Theme.listMeasure)
            topPadding: 12
            Repeater {
                model: root.ready ? root.status.choices.length : 0
                Item {
                    id: choiceRow
                    required property int index
                    readonly property var choice: root.status.choices[index] || ({})
                    readonly property bool on: root.picked.indexOf(choice.id) >= 0
                    readonly property bool editable: root.canPick && !choice.installed
                    readonly property real size: choice.installed ? -1 : (root.downloading ? (root.sizes[choice.id] !== undefined ? root.sizes[choice.id] : choice.bytes) : choice.bytes)
                    readonly property bool removable: Boolean(choice.removable) && root.canPick
                    width: parent.width
                    height: rowColumn.height
                    Column {
                        id: rowColumn
                        width: parent.width
                        Rectangle { width: parent.width; height: choiceRow.index === 0 ? 0 : 1; color: Theme.line }
                        Item {
                            id: line
                            width: parent.width
                            height: Math.max(words.height, removeButton.visible ? removeButton.implicitHeight - 8 : 0) + 20
                            Interactive {
                                id: hit
                                objectName: "choice." + choiceRow.choice.id
                                width: removeButton.visible ? removeButton.x - 12 : line.width
                                height: line.height
                                enabled: choiceRow.editable
                                ringMargin: 0
                                pressScaling: false
                                Accessible.role: Accessible.CheckBox
                                Accessible.name: (choiceRow.choice.label || "") + ", " + sizeText.text
                                Accessible.checked: choiceRow.choice.installed || choiceRow.on
                                onClicked: root.toggle(choiceRow.choice.id, !choiceRow.on)
                            }
                            VoiceCheck {
                                checked: choiceRow.choice.installed || choiceRow.on
                                anchors.verticalCenter: parent.verticalCenter
                                opacity: choiceRow.editable ? 1 : 0.5
                            }
                            Column {
                                id: words
                                x: 28
                                width: line.width - 28 - sizeText.width - 12 - (removeButton.visible ? removeButton.width + 12 : 0)
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                Flow {
                                    width: parent.width
                                    spacing: 8
                                    Text {
                                        width: Math.min(implicitWidth, parent.width)
                                        text: choiceRow.choice.label || ""
                                        color: Theme.text
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeBodySmall
                                        font.weight: Theme.weightMedium
                                    }
                                    Rectangle {
                                        visible: Boolean(choiceRow.choice.recommended) && !choiceRow.choice.installed
                                        width: badge.implicitWidth + 16
                                        height: badge.implicitHeight + 4
                                        radius: height / 2
                                        color: Theme.accentSoft
                                        Text {
                                            id: badge
                                            anchors.centerIn: parent
                                            text: "Khuyên dùng"
                                            color: Theme.accentText
                                            font.pixelSize: 11
                                            font.weight: 600
                                        }
                                    }
                                }
                                Text {
                                    width: parent.width
                                    text: choiceRow.choice.detail || ""
                                    color: Theme.text2
                                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                    font.pixelSize: 13
                                }
                            }
                            Text {
                                id: sizeText
                                anchors.right: removeButton.visible ? removeButton.left : parent.right
                                anchors.rightMargin: removeButton.visible ? 12 : 0
                                anchors.verticalCenter: parent.verticalCenter
                                text: choiceRow.choice.installed ? "Đã có" : choiceRow.size > 0 ? Size.formatSize(choiceRow.size) : "Đã có sẵn"
                                color: Theme.text2
                                font.pixelSize: Theme.sizeCaption
                            }
                            Button {
                                id: removeButton
                                objectName: "choiceRemove." + choiceRow.choice.id
                                visible: choiceRow.removable
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                size: "sm"
                                kind: "text"
                                text: choiceRow.choice.installed ? "Gỡ" : "Xoá phần đã tải"
                                busy: root.busy
                                onActivated: { if (choiceRow.choice.installed) root.ask(choiceRow.choice.id, choiceRow.choice.label); else root.remove(choiceRow.choice.id) }
                            }
                        }
                    }
                }
            }
        }
        VoiceBlock {
            width: parent.width
            show: Boolean(root.status.accelerated)
            gap: 12
            Interactive {
                width: parent.width
                height: Math.max(accelText.height, 24)
                enabled: root.canPick && !root.busy
                ringMargin: 2
                pressScaling: false
                objectName: "moduleAccelerate"
                Accessible.role: Accessible.CheckBox
                Accessible.name: "Dùng bản tăng tốc"
                Accessible.checked: Boolean(root.status.accelerated && root.status.accelerated.on)
                onClicked: root.run("/accelerate", {on: !(root.status.accelerated && root.status.accelerated.on)}, "Chưa đổi được cách đọc")
                VoiceCheck { checked: Boolean(root.status.accelerated && root.status.accelerated.on); anchors.verticalCenter: parent.verticalCenter }
                Text {
                    id: accelText
                    x: 24
                    width: parent.width - 24
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Dùng bản tăng tốc"
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
            Text {
                width: parent.width
                topPadding: 4
                text: root.status.accelerated ? VoiceLogic.acceleratedNote(root.status.accelerated) : ""
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 13
            }
        }
        VoiceNote { width: parent.width; text: root.ready ? VoiceLogic.fastUnsupportedNote(root.status) : ""; ink: Theme.text3 }
        Repeater {
            model: root.copy.tiers
            VoiceNote {
                required property string modelData
                width: card.width
                text: root.status.benchmark && root.status.benchmark[modelData] ? VoiceLogic.benchmarkLabel(modelData, root.status.benchmark[modelData], root.status.slowRtf) : ""
            }
        }
        VoiceNote { width: parent.width; text: root.canPick && root.missing.length > 0 ? VoiceLogic.meteredNotice(root.status, root.bytes) : "" }
        VoiceBlock {
            width: parent.width
            show: root.suggestion !== null
            Item {
                width: parent.width
                height: suggestionColumn.height + 20
                Column {
                    id: suggestionColumn
                    y: 10
                    width: parent.width
                    Text {
                        width: parent.width
                        text: root.keptSuggestion.message
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                    }
                    Item { width: 1; height: 8 }
                    Button {
                        objectName: "moduleSwitch"
                        size: "sm"
                        kind: "text"
                        text: root.keptSuggestion.action
                        busy: root.busy
                        onActivated: root.switchTo()
                    }
                }
            }
        }
        VoiceBlock {
            width: parent.width
            show: root.failed
            ClockLabel {
                objectName: "moduleError"
                width: parent.width
                text: root.failed ? VoiceLogic.moduleLabel(root.shown, root.copy) : ""
                color: Theme.danger
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
            }
            VoiceDetails { width: parent.width; technical: root.failed ? (root.status.errorDetail || "") : "" }
        }
        VoiceBlock {
            width: parent.width
            show: root.hasActions
            VoiceFlex {
                width: parent.width
                Button {
                    objectName: "moduleUpdate"
                    visible: root.status.state === "outdated"
                    size: "sm"
                    kind: "text"
                    text: "Cập nhật (" + Size.formatSize(root.status.outdatedBytes || 0) + ")"
                    busy: root.busy
                    onActivated: root.start()
                }
                Button {
                    id: startButton
                    objectName: "moduleStart"
                    visible: root.missing.length > 0
                    size: "sm"
                    kind: root.status.state === "missing" ? "primary" : "text"
                    text: root.failed ? "Thử lại" : root.bytes > 0 ? "Tải (" + Size.formatSize(root.bytes) + ")" : "Dùng"
                    busy: root.busy
                    onActivated: root.start(root.missing)
                }
                Button {
                    objectName: "moduleMeasure"
                    visible: root.hasMeasure
                    size: "sm"
                    kind: "text"
                    text: "Thử lại tốc độ"
                    busy: root.busy
                    onActivated: root.run("/measure", {}, "Chưa tải được " + root.lowerName)
                }
            }
        }
    }

    // Hỏi trước khi gỡ: hộp thoại giữa màn ở lớp cửa sổ, có lớp Back riêng (Back đóng hộp rồi mới tới trang cha)
    Modal {
        id: confirm
        objectName: "removeConfirm." + root.copy.key
        parent: root.Window.window ? root.Window.window.contentItem : root
        title: "Gỡ “" + root.askLabel + "” khỏi máy này?"
        description: root.asking && root.asking.use === undefined ? "Đang xem cuốn nào còn dùng giọng này…" : VoiceLogic.removeAsk(root.asking ? root.asking.use : null)
        onClosed: root.asking = null
        footer: [
            Flow {
                anchors.right: parent.right
                width: parent.width
                spacing: 8
                layoutDirection: Qt.RightToLeft
                Button {
                    objectName: "removeConfirmYes." + root.copy.key
                    kind: "danger"
                    text: "Gỡ giọng"
                    enabled: root.asking !== null && root.asking.use !== undefined
                    onClicked: { const id = root.asking.id; confirm.dismiss(); root.remove(id) }
                }
                Button {
                    objectName: "removeConfirmNo." + root.copy.key
                    kind: "text"
                    text: "Giữ lại"
                    onClicked: confirm.dismiss()
                }
            }
        ]
    }
}
