import "UiStrings.js" as S
import QtQuick
import ABook

DevicesFold {
    id: root
    objectName: "castHistory"
    property string bookId: ""
    property var history: ({items: []})
    property var store: null
    property bool editable: false
    property bool busy: false
    property string problem: ""
    property var queued: ({})
    onBookIdChanged: { queued = ({}); busy = false; problem = "" }
    signal changed()
    title: S.s_lich_su_0a235708
    storageKey: "book." + bookId + ".cast-history"
    function undo(operationId) {
        if (busy) return
        busy = true
        problem = ""
        const requestedBook = bookId
        const answer = function(data, error) {
            if (requestedBook !== root.bookId) return
            root.busy = false
            if (error) { root.problem = String(error); return }
            const next = Object.assign({}, root.queued)
            next[operationId] = true
            root.queued = next
            if (root.store) root.store.editedCast(root.bookId); else Api.editedBook(root.bookId)
            root.changed()
        }
        const path = "/api/books/" + bookId + "/cast-history/undo"
        if (store) store.quiet("POST", path, {operationId: operationId}, answer)
        else Api.quiet("POST", path, {operationId: operationId}, answer)
    }
    Collapse {
        width: parent.width
        open: root.problem !== ""
        Text { width: parent.width; text: root.problem; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
    }
    Collapse {
        width: parent.width
        open: !root.history || !root.history.items || root.history.items.length === 0
        Text { width: parent.width; text: S.s_cast_history_manual; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
    }
    Repeater {
        model: root.history && root.history.items ? root.history.items : []
        Column {
            id: entry
            required property var modelData
            readonly property string state: modelData.state === "applied" && root.queued[modelData.operationId] ? "pending" : modelData.state
            width: root.width
            topPadding: Theme.s12
            bottomPadding: Theme.s12
            Row {
                width: parent.width
                spacing: Theme.s12
                Column {
                    width: parent.width - (action.visible ? action.width + parent.spacing : 0)
                    Text { width: parent.width; text: S.s_cast_history_row(entry.modelData.source || S.s_cast_history_group, entry.modelData.target, entry.modelData.lines); color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
                    Collapse {
                        width: parent.width
                        open: entry.state !== "applied"
                        Text { width: parent.width; text: entry.state === "undone" ? S.s_da_hoan_tac_2ef55fca : S.s_cho_ap_dung_77a52853; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                    Collapse {
                        width: parent.width
                        open: entry.modelData.conflicts > 0
                        Text { width: parent.width; text: S.s_cast_history_conflicts(entry.modelData.conflicts); color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                    Collapse {
                        width: parent.width
                        open: entry.state === "pending"
                        Text { width: parent.width; text: S.s_cast_history_audio; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                    Collapse {
                        width: parent.width
                        open: (entry.modelData.aliasConflicts || 0) > 0
                        Text { width: parent.width; text: S.s_cast_history_alias_conflicts(entry.modelData.aliasConflicts || 0); color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                }
                Button {
                    id: action
                    text: S.s_hoan_tac_e72ff675
                    kind: "ghost"
                    enabled: !root.busy
                    Reveal { shown: root.editable && entry.state === "applied" }
                    onActivated: root.undo(entry.modelData.operationId)
                }
            }
        }
    }
}
