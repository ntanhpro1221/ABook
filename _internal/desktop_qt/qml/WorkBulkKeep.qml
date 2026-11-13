import "UiStrings.js" as S
import QtQuick
import ABook
import "WorkLogic.js" as W

// "Giữ như máy đang làm" cho cả loại thẻ đang lọc (BulkKeep): sau khi soát vài thẻ thấy máy đúng gần hết, người làm sách không phải bấm "giữ" từng thẻ một trong cả trăm thẻ. Một lần
// bấm (có hỏi lại) ghi đúng quyết định "giữ" mà từng thẻ ghi - không câu nào phải thu lại, máy thôi hỏi - và hoàn tác được cả nhóm.
Item {
    id: root
    property var work: null
    property string kind: "all"
    property var items: []
    property bool busy: false
    readonly property var keepable: W.bulkKeepable(kind, items)
    readonly property bool available: W.BULK_KINDS.indexOf(kind) >= 0 && keepable.length >= 2
    width: parent ? parent.width : 400
    height: available ? 12 + ask.height : 0
    Reveal { shown: root.available }

    Button {
        id: ask
        objectName: "bulkKeep"
        y: 12
        size: "sm"
        kind: "ghost"
        icon: "check"
        text: S.s_giu_d3777f80 + root.keepable.length + S.s_the_539c2ef4
        onClicked: root.open()
    }
    function open() {
        confirm.title = W.bulkTitle(kind, keepable.length)
        confirm.description = W.bulkDescription(kind)
        confirm.actions = actions()
        confirm.show()
    }
    function actions() { return [{key: "later", text: S.s_thoi_e68f9e88, enabled: !busy}, {key: "go", text: S.s_giu_ca_4b7c5467 + keepable.length + S.s_the_5d800d1c, icon: "check", kind: "primary", busy: busy}] }
    function run() {
        if (busy) return
        busy = true
        confirm.actions = actions()
        work.bulkKeep(kind, keepable, function() { root.busy = false; confirm.dismiss() })
    }
    StudioConfirm {
        id: confirm
        objectName: "bulkConfirm"
        panelWidth: 480
        dismissable: !root.busy
        keepOpen: function() { return root.busy }
        onChosen: key => { if (key === "go") root.run(); else confirm.dismiss() }
    }
}
