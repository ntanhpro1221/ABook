import QtQuick
import ABook

// Ô số chương của trình chia tập (NumberBox / AddCut của VolumeSplit.tsx): gõ thoải mái, chỉ nhận khi rời ô hay bấm Enter. "edit": số chương của một chỗ cắt
// (số lạ thì trả về số cũ, viền đỏ); "add": ô thêm chỗ cắt mới (nhận thì xoá ô). `commitWith(số)` trả true nếu nhận.
FormField {
    id: root
    property string mode: "edit"
    property int value: 0
    property bool bad: false
    property var commitWith: null
    implicitHeight: 32
    topPadding: 4
    bottomPadding: 4
    leftPadding: 8
    rightPadding: 8
    horizontalAlignment: TextEdit.AlignHCenter
    invalid: bad
    inputMethodHints: Qt.ImhDigitsOnly
    font.features: { "tnum": 1 }
    function commitNow() {
        const raw = text.trim()
        if (mode === "edit" && raw === String(value)) return
        const ok = /^\d+$/.test(raw) && commitWith !== null && commitWith(Number(raw))
        bad = !ok
        if (mode === "add") { if (ok) text = "" }
        else if (!ok) text = String(value)
    }
    onAccepted: commitNow()
    onActiveFocusChanged: if (!activeFocus && mode === "edit") commitNow()
    onValueChanged: if (mode === "edit") { text = String(value); bad = false }
    onTextChanged: if (mode === "add") bad = false
    Component.onCompleted: if (mode === "edit") text = String(value)
}
