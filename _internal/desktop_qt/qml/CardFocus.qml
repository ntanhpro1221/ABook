import QtQuick
import ABook
import "WorkLogic.js" as W

// Tiêu điểm của một danh sách thẻ việc (useCardFocus.ts + workFocus.ts): tìm thẻ theo khoá, chuyển tiêu điểm vào thẻ, và - khi thẻ đang giữ tiêu điểm rời danh sách
// (quyết xong, hoàn tác) - đưa tiêu điểm sang thẻ kế (hết thẻ thì về `endTarget()`) thay vì rơi về nền. Hộp "Việc cần duyệt" và màn "Duyệt trước khi thu" dùng chung.
// `scope`: phần tử chứa các thẻ; `lists()`: {open: [khoá], decided: [khoá]} lúc này.
Item {
    id: root
    property Item scope: null
    property var lists: function() { return ({open: [], decided: []}) }
    property var endTarget: function() { return null }
    property string lastCard: ""
    property var snapshot: null
    signal revealRequested(var card)

    function findCard(key) {
        let found = null
        function walk(node) {
            if (found || !node) return
            for (const child of node.children) {
                if (child.objectName === "workCard" && child.key === key) { found = child; return }
                walk(child)
            }
        }
        walk(scope)
        return found
    }
    function cardKey(node) {
        for (let n = node; n; n = n.parent) if (n.objectName === "workCard") return n.key
        return ""
    }
    function focusCard(key, take) {
        if (key === "end") { const target = endTarget(); if (target) target.forceActiveFocus(); return }
        const card = findCard(key)
        if (!card) return
        if (take !== false) {
            const buttons = card.choices()
            if (buttons.length > 0) buttons[0].forceActiveFocus(); else card.forceActiveFocus()
        }
        revealRequested(card)
    }
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            const now = root.Window.window.activeFocusItem
            const key = root.cardKey(now)
            if (key !== "") { root.lastCard = key; root.snapshot = root.lists(); return }
            if (root.lastCard === "" || !root.snapshot) return
            if (now && now !== root.Window.window.contentItem) { root.lastCard = ""; return }
            const target = W.focusAfterChange(root.snapshot, root.lists(), root.lastCard)
            root.lastCard = ""
            if (target !== null) Qt.callLater(function() { root.focusCard(target, true) })
        }
    }
}
