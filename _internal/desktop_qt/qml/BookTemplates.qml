import QtQuick
import ABook

// Mẫu sách mới đã lưu (desktop/BookTemplates.tsx + studio/bookTemplates.ts): đổi tên, xoá (có "Hoàn tác" 10 giây). Lưu mẫu mới làm ở trình
// tạo sách. Mỗi việc là một thao tác riêng gửi POST /api/book-templates nên hai thiết bị cùng sửa không đè mất nhau. Đổi tên là một lớp Back:
// Back / Esc huỷ ô nhập trước khi làm gì khác.
Column {
    id: root
    readonly property int nameMax: 40
    readonly property string defaultLabel: "Mặc định"
    // Nhãn mức chất lượng (PROFILE_LABEL của studio/bookTemplates.ts)
    readonly property var profileLabel: ({high_quality: "Chất lượng cao", balanced: "Cân bằng", fast: "Nhanh"})
    readonly property var templates: templatesOf(Api.preferences ? Api.preferences.bookTemplates : null)
    property string renaming: ""
    property bool renamingNow: false
    property string typed: ""
    property string problem: ""
    property bool busy: false
    objectName: "bookTemplates"
    bottomPadding: 16

    function same(a, b) { return a.toLocaleLowerCase("vi") === b.toLocaleLowerCase("vi") }
    function cleanName(value) { return value.split(/\s+/).filter(Boolean).join(" ") }
    function templatesOf(value) {
        if (!Array.isArray(value)) return []
        const found = []
        for (const item of value) {
            if (!item || typeof item !== "object") continue
            if (typeof item.name !== "string" || !item.name || !profileLabel[item.profile]) continue
            found.push({
                name: item.name,
                narrator: typeof item.narrator === "string" ? item.narrator : "",
                profile: item.profile,
                analysisModel: typeof item.analysisModel === "string" ? item.analysisModel : "",
                startNow: item.startNow !== false,
                precastWait: item.precastWait === true
            })
        }
        return found
    }
    function templateIndex(name) {
        for (let i = 0; i < templates.length; ++i) if (same(templates[i].name, name)) return i
        return -1
    }
    // Lời báo cho một cái tên không dùng được, "" nếu được. `except`: tên đang được đổi.
    function nameProblem(raw, except) {
        const name = cleanName(raw)
        if (!name) return "Đặt cho mẫu một cái tên"
        if (name.length > nameMax) return "Tên mẫu tối đa " + nameMax + " chữ"
        if (same(name, defaultLabel)) return "“" + defaultLabel + "” là mẫu có sẵn của app - chọn tên khác"
        for (const item of templates) if (same(item.name, name) && !(except !== undefined && same(item.name, except))) return "Đã có mẫu tên “" + name + "”"
        return ""
    }
    function summaryOf(t) {
        return [t.narrator || "Giọng máy đề xuất", profileLabel[t.profile], t.startNow ? "bắt đầu ngay" : "chờ bấm bắt đầu"]
            .concat(t.precastWait ? ["chờ bạn duyệt trước khi thu"] : []).join(" · ")
    }

    // Một thao tác lên danh sách mẫu; `done(ok, status)`. Lỗi: mẫu bị thiết bị khác xoá / đặt trùng tên (404 / 409) thì nói đúng lời máy tính
    // báo và tải lại tuỳ chọn; việc khác hỏng thì "Không lưu được mẫu" + lời máy tính.
    function run(op, done) {
        if (!Api.transport || busy) return
        busy = true
        Api.transport.request("POST", "/api/book-templates", op, function(status, data) {
            busy = false
            const ok = status >= 200 && status < 300
            if (ok) {
                Api.preferences = Object.assign({}, Api.preferences, data)
            } else {
                const message = data && (data.message || data.error) || "Không làm được lúc này."
                if (status === 404 || status === 409) { Api.notice = message; Api.load() }
                else Api.notice = "Không lưu được mẫu\n" + message
            }
            if (done) done(ok, status)
        })
    }

    // Lớp Back của ô đổi tên
    property QtObject renameLayer: QtObject { function close() { root.cancelRename() } }
    function startRename(name) {
        if (renamingNow) Nav.closedLayer(renameLayer)
        typed = name
        problem = ""
        renaming = name
        renamingNow = true
        Nav.openLayer(renameLayer)
    }
    function cancelRename() {
        Nav.closedLayer(renameLayer)
        renamingNow = false
        renaming = ""
        problem = ""
    }
    Component.onDestruction: Nav.closedLayer(renameLayer)

    function finishRename(from) {
        const wrong = nameProblem(typed, from)
        if (wrong) { problem = wrong; return }
        run({op: "rename", from: from, to: typed}, function(ok, status) {
            if (ok || status === 404) cancelRename()
        })
    }
    function removeTemplate(template) {
        const index = templateIndex(template.name)
        run({op: "delete", name: template.name}, function(ok) {
            if (!ok) return
            Api.toast("Đã xoá mẫu “" + template.name + "”", {duration: 10000, action: {label: "Hoàn tác", run: function() { root.run({op: "restore", template: template, index: index}) }}})
        })
    }

    Text { width: parent.width; text: "Mẫu sách mới"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
    Text {
        width: parent.width
        topPadding: 2
        text: "Ở Tạo sách, chọn “Lưu thành mẫu…” để dùng lại."
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: 13
    }
    Collapse {
        width: parent.width
        open: root.templates.length === 0
        Text { width: parent.width; topPadding: 8; text: "Chưa có mẫu nào."; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: 13 }
    }
    Item {
        width: parent.width
        height: list.height > 0 ? list.height + 8 : 0
        StudioRows {
            id: list
            y: 8
            width: parent.width
            items: root.templates
            keyField: "name"
            delegate: Component {
                Item {
                    id: row
                    property var modelData: ({name: "", narrator: "", profile: "high_quality", startNow: true, precastWait: false})
                    readonly property bool editing: root.renamingNow && root.renaming === modelData.name
                    width: parent ? parent.width : 0
                    implicitHeight: shown.height + edit.height + 16
                    height: implicitHeight
                    // Hàng thường: tên + dòng tóm tắt + hai nút; hẹp thì nút xuống dưới chữ
                    Collapse {
                        id: shown
                        y: 8
                        width: parent.width
                        open: !row.editing
                        Item {
                            id: normal
                            width: parent.width
                            readonly property real buttons: renameButton.implicitWidth + removeButton.implicitWidth + 12
                            readonly property bool stacked: width - buttons - 12 < 160
                            implicitHeight: stacked ? words.height + 6 + buttonRow.height : Math.max(words.height, buttonRow.height)
                            height: implicitHeight
                            Column {
                                id: words
                                width: normal.stacked ? parent.width : parent.width - normal.buttons - 12
                                anchors.verticalCenter: normal.stacked ? undefined : parent.verticalCenter
                                Text { width: parent.width; text: row.modelData.name; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                                Text { width: parent.width; text: root.summaryOf(row.modelData); color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: 13 }
                            }
                            Row {
                                id: buttonRow
                                spacing: 12
                                x: normal.stacked ? 0 : parent.width - normal.buttons
                                y: normal.stacked ? words.height + 6 : (normal.height - height) / 2
                                Button { id: renameButton; objectName: "renameTemplate"; text: "Đổi tên"; kind: "ghost"; size: "sm"; onClicked: root.startRename(row.modelData.name) }
                                Button { id: removeButton; objectName: "deleteTemplate"; text: "Xoá"; kind: "ghost"; size: "sm"; onClicked: root.removeTemplate(row.modelData) }
                            }
                        }
                    }
                    // Hàng đang đổi tên: ô nhập + Lưu + Huỷ, lời báo lỗi bên dưới
                    Collapse {
                        id: edit
                        y: 8 + shown.height
                        width: parent.width
                        open: row.editing
                        Column {
                            width: parent.width
                            spacing: 8
                            // Ô nhập chiếm phần còn lại của hàng cạnh Lưu / Huỷ (flex-1); hẹp thì hai nút xuống dưới
                            Item {
                                id: editLine
                                width: parent.width
                                readonly property real buttons: saveButton.implicitWidth + cancelButton.implicitWidth + 8
                                readonly property bool stacked: width - buttons - 8 < 160
                                implicitHeight: nameField.height + (stacked ? buttonLine.height + 8 : 0)
                                height: implicitHeight
                                FormField {
                                    id: nameField
                                    objectName: "renameField"
                                    width: editLine.stacked ? parent.width : parent.width - editLine.buttons - 8
                                    label: "Tên mới của mẫu “" + row.modelData.name + "”"
                                    invalid: root.problem !== ""
                                    escapeLocal: true
                                    // Tối đa 40 chữ (maxLength của ô nhập bên web)
                                    onTextChanged: {
                                        if (text.length > root.nameMax) { text = text.substring(0, root.nameMax); return }
                                        if (row.editing && text !== root.typed) { root.typed = text; root.problem = "" }
                                    }
                                    onAccepted: root.finishRename(row.modelData.name)
                                    onEscaped: root.cancelRename()
                                    Connections { target: row; function onEditingChanged() { if (row.editing) { nameField.text = root.typed; nameField.forceActiveFocus(); nameField.selectAll() } } }
                                }
                                Row {
                                    id: buttonLine
                                    spacing: 8
                                    x: editLine.stacked ? 0 : parent.width - editLine.buttons
                                    y: editLine.stacked ? nameField.height + 8 : (nameField.height - height) / 2
                                    Button { id: saveButton; objectName: "saveRename"; text: "Lưu"; size: "sm"; enabled: root.typed.trim() !== "" && !root.busy; onClicked: root.finishRename(row.modelData.name) }
                                    Button { id: cancelButton; objectName: "cancelRename"; text: "Huỷ"; kind: "ghost"; size: "sm"; onClicked: root.cancelRename() }
                                }
                            }
                            Collapse {
                                width: parent.width
                                open: root.problem !== ""
                                Text { objectName: "renameProblem"; width: parent.width; text: root.problem; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: 13 }
                            }
                        }
                    }
                }
            }
        }
    }
}
