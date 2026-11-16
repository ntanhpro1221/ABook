import QtQuick
import ABook
import "UiStrings.js" as S

// Uses the existing Modal frame and shadow. Closing any way cancels the action.
Modal {
    id: root
    property string actionText: S.s_xoa_777195ab
    property int ownedRequest: 0
    property bool sending: false
    property bool accepting: false
    property bool requestSeen: false
    property string problem: ""
    dismissable: !sending
    keepOpen: function() { return root.sending }
    signal accepted()
    function settled(status) {
        ownedRequest = 0; sending = false
        if (status >= 200 && status < 300) close()
        else problem = S.s_action_failed_retry
    }
    function accept() {
        if (sending) return
        problem = ""; sending = true
        accepting = true; requestSeen = false
        accepted()
        accepting = false
        if (!requestSeen) { sending = false; close() }
    }
    Listen { target: Api;
        function onRequestBegan(id) { if (root.accepting && !root.requestSeen) { root.requestSeen = true; root.ownedRequest = id } }
        function onRequestDone(id, status) { if (root.ownedRequest === id) root.settled(status) }
    }
    InlineError { width: parent.width; message: root.problem; onRetry: root.accept() }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { id: cancel; text: S.s_huy_96732485; kind: "ghost"; enabled: !root.sending; onActivated: root.close() }
            Button { text: root.problem ? S.s_thu_lai_c58d068c : root.actionText; kind: "danger"; busy: root.sending; onActivated: root.accept() }
        }
    ]
    onOpenChanged: if (open) { problem = ""; Later.call(root, function() { cancel.forceActiveFocus(Qt.TabFocusReason) }) }
}
