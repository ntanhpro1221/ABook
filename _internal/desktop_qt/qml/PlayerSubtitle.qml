import "UiStrings.js" as S
import QtQuick
import ABook
import "TextWrap.js" as TextWrap

Column {
    id: root
    property alias bookLabel: bookLabel
    property int horizontalAlignment: Text.AlignLeft
    readonly property bool preparing: Player.speaking && Player.playing && Player.buffering
    property bool delayed: false
    onPreparingChanged: { delayed = false; if (preparing && Nav.uiVisible && visible) delay.restart(); else delay.stop() }
    onVisibleChanged: { if (visible && preparing && Nav.uiVisible) delay.restart(); else { delay.stop(); delayed = false } }
    Timer { id: delay; interval: 1500; onTriggered: root.delayed = root.preparing }
    Connections { target: Nav; function onUiVisibleChanged() { if (Nav.uiVisible && root.preparing && root.visible) delay.restart(); else { delay.stop(); root.delayed = false } } }
    Text { width: parent.width; horizontalAlignment: root.horizontalAlignment; wrapMode: Text.Wrap; visible: Player.purpose === "review"; text: S.s_nghe_kiem_f9c474bb; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Text {
        id: bookLabel
        objectName: "playerSubtitleText"; width: parent.width; wrapMode: Text.Wrap
        horizontalAlignment: root.horizontalAlignment
        text: TextWrap.keepDots(root.delayed ? S.s_dang_chuan_bi_giong_doc_25f86ccf : Player.atEnd === "caughtUp" ? S.s_da_nghe_het_phan_da_co_1aa0a8e0 : Player.bookTitle)
        color: Theme.text2; font.pixelSize: Theme.sizeCaption
    }
}
