import QtQuick
import ABook
import "UiStrings.js" as S
import "ScriptScope.js" as Scope
import "ScriptLogic.js" as Script

Modal {
    id: root
    property var script: null
    property var snapshot: null
    property var line: null
    property var store: null
    property string bookId: ""
    property string mode: "line"
    property var toggled: []
    property var person: null
    property string revision: ""
    property string error: ""
    property bool busy: false
    dismissable: !busy
    keepOpen: () => root.busy
    signal apply(var lines, var person)
    signal refreshed(var data)
    title: S.s_scope_title
    readonly property var candidates: snapshot && line ? Scope.lines(snapshot.lines, line.stableId, mode, Number(start.text) - 1, Number(end.text) - 1) : []
    readonly property var chosen: Scope.selected(candidates, toggled)
    readonly property var people: {
        if (!snapshot) return []
        const all = snapshot.cast.concat(snapshot.others).concat([{value: "UNNAMED", label: S.s_vai_phu_khong_ten_6395f0d2, lines: 0}])
        return all.filter((person, index) => person.value !== "NARRATOR" && all.findIndex(other => other.value === person.value) === index)
    }
    readonly property var found: people.filter(person => Script.fold(person.label).indexOf(Script.fold(search.text.trim())) >= 0).slice(0, 8)
    function begin(value) {
        snapshot = script
        line = value; mode = value.scene === null || value.scene === undefined ? "line" : "scene"
        const range = value.scene === null || value.scene === undefined ? [value] : script.lines.filter(item => item.scene === value.scene)
        start.text = String(range[0].seq + 1); end.text = String(range[range.length - 1].seq + 1)
        toggled = []; person = null; error = ""; busy = false; search.text = ""
        revision = script.scopeRevision || ""
        show()
    }
    function submit() {
        if (!person || !chosen.length || busy) return
        busy = true
        store.request("GET", "/api/books/" + bookId + "/casting/" + snapshot.chapterId, null, function(status, data) {
            root.busy = false
            if (!root.store.ok(status) || !root.revision || data.scopeRevision !== root.revision) {
                root.error = S.s_scope_changed
                if (root.store.ok(status)) root.refreshed(data)
                return
            }
            root.apply(root.chosen, root.person)
            root.close()
        })
    }
    Column {
        width: root.bodyWidth
        spacing: 12
        Text {
            width: parent.width; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            text: root.line && root.line.scene !== null && root.line.scene !== undefined ? S.s_scope_marker_note : S.s_scope_no_markers
        }
        Flow {
            width: parent.width; spacing: 8
            Repeater {
                model: [{value: "line", label: S.s_cau_nay_ee66e104}, {value: "scene", label: S.s_scope_scene}, {value: "chapter", label: S.s_scope_chapter}, {value: "manual", label: S.s_scope_manual}]
                delegate: Button {
                    required property var modelData
                    objectName: "scopeMode_" + modelData.value
                    text: modelData.label; size: "sm"; kind: root.mode === modelData.value ? "outline" : "ghost"
                    enabled: !root.busy && (modelData.value !== "scene" || !!root.line && root.line.scene !== null && root.line.scene !== undefined)
                    onClicked: { root.mode = modelData.value; root.toggled = [] }
                }
            }
        }
        Collapse {
            width: parent.width; open: root.mode === "manual"
            Row {
                width: parent.width; spacing: 12
                Column {
                    width: (parent.width - 12) / 2; spacing: 4
                    Text { text: S.s_scope_start; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                    WorkField { id: start; objectName: "scopeStart"; width: parent.width; label: S.s_scope_start; inputMethodHints: Qt.ImhDigitsOnly }
                }
                Column {
                    width: (parent.width - 12) / 2; spacing: 4
                    Text { text: S.s_scope_end; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                    WorkField { id: end; objectName: "scopeEnd"; width: parent.width; label: S.s_scope_end; inputMethodHints: Qt.ImhDigitsOnly }
                }
            }
        }
        Collapse {
            width: parent.width; open: !root.person
            WorkField {
                id: search; objectName: "scopeSearch"; width: parent.width
                label: S.s_tim_nguoi_noi_70e3871e; placeholderText: S.s_tim_nguoi_noi_70e3871e
            }
            Repeater {
                model: root.found
                delegate: Interactive {
                    id: personOption
                    required property var modelData
                    objectName: "scopePerson_" + modelData.value
                    width: parent.width; height: Math.max(40, personLabel.implicitHeight + 16)
                    Accessible.role: Accessible.Button; Accessible.name: modelData.label
                    onClicked: root.person = modelData
                    Icon { x: 8; y: 12; name: "check"; size: 16; color: Theme.accentText; opacity: root.line && root.line.current === personOption.modelData.value ? 1 : 0 }
                    Text { id: personLabel; x: 36; y: 8; width: parent.width - 44; text: personOption.modelData.label; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
                }
            }
            Collapse {
                width: parent.width; open: search.text.trim() !== "" && root.found.length === 0
                Flow {
                    width: parent.width; spacing: 8
                    Repeater {
                        model: Script.GENDERS
                        delegate: Button {
                            required property var modelData
                            objectName: "scopeNew_" + modelData.value
                            text: modelData.label; kind: "ghost"
                            onClicked: root.person = {value: search.text.trim(), label: search.text.trim(), lines: 0, newGender: modelData.value}
                        }
                    }
                }
            }
        }
        Button {
            Reveal { shown: !!root.person }
            text: S.s_scope_target(root.person ? root.person.label : ""); kind: "ghost"
            onClicked: root.person = null
        }
        Text {
            objectName: "scopeCount"
            width: parent.width; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall
            text: S.s_scope_count(root.chosen.length, root.candidates.filter(Scope.conflict).length)
        }
        Text {
            width: parent.width; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            text: S.s_scope_before_after(root.line ? root.line.label : "", root.person ? root.person.label : S.s_scope_pick)
        }
        Repeater {
            model: root.snapshot && root.line ? Scope.lines(root.snapshot.lines, root.line.stableId, "chapter", 0, 0) : []
            delegate: Collapse {
                id: previewRow
                required property var modelData
                width: parent.width
                open: root.candidates.some(line => line.stableId === modelData.stableId)
                Interactive {
                id: option
                property var modelData: previewRow.modelData
                readonly property bool picked: root.chosen.some(line => line.stableId === modelData.stableId)
                objectName: "scopeLine_" + modelData.stableId
                width: parent.width; height: Math.max(40, words.implicitHeight + 16)
                Accessible.role: Accessible.CheckBox; Accessible.name: words.text; Accessible.checked: picked
                onClicked: root.toggled = root.toggled.indexOf(modelData.stableId) >= 0 ? root.toggled.filter(id => id !== modelData.stableId) : root.toggled.concat([modelData.stableId])
                Icon { x: 8; y: 10; name: "check"; size: 16; color: Theme.accentText; opacity: option.picked ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                Text {
                    id: words; x: 40; y: 8; width: parent.width - 48; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall
                    text: (option.modelData.seq + 1) + ". " + option.modelData.text + (Scope.conflict(option.modelData) ? "\n" + S.s_scope_conflict : "") + "\n" + S.s_scope_before_after(option.modelData.wish && option.modelData.wish.state === "pending" ? option.modelData.wish.label : option.modelData.label, root.person ? root.person.label : S.s_scope_pick)
                }
                }
            }
        }
        Collapse {
            width: parent.width; open: !!root.error
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.danger; font.pixelSize: Theme.sizeBodySmall; text: root.error }
        }
    }
    footer: Button { objectName: "scopeApply"; text: S.s_scope_apply; enabled: !root.busy && !!root.person && root.chosen.length > 0; onClicked: root.submit() }
}
