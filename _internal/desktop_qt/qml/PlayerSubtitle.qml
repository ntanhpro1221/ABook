import "UiStrings.js" as S
import QtQuick
import ABook
import "TextWrap.js" as TextWrap

Column {
    id: root
    property alias bookLabel: bookLabel
    property int horizontalAlignment: Text.AlignLeft
    // Dấu › sau tên sách (màn Đang nghe); thanh phát hẹp không có.
    property bool chevron: false
    // Tên sách là nút tới trang sách (DESIGN.md L3c); dòng đang nói việc khác (đang chuẩn bị giọng, đã nghe hết phần đã có) thì chỉ là chữ.
    readonly property bool showsBook: !delayed && Player.atEnd !== "caughtUp"
    // Cú bấm vừa trúng tên sách: TapHandler của vùng mở Đang nghe nằm dưới cũng thấy cú bấm ấy và bỏ qua khi cờ này bật (như ChapterRow.onMenuButton).
    property bool tappedBook: false
    signal bookRequested()
    readonly property bool preparing: Player.speaking && Player.playing && Player.buffering
    property bool delayed: false
    onPreparingChanged: { delayed = false; if (preparing && Nav.uiVisible && visible) delay.restart(); else delay.stop() }
    onVisibleChanged: { if (visible && preparing && Nav.uiVisible) delay.restart(); else { delay.stop(); delayed = false } }
    Timer { id: delay; interval: 1500; onTriggered: root.delayed = root.preparing }
    Connections { target: Nav; function onUiVisibleChanged() { if (Nav.uiVisible && root.preparing && root.visible) delay.restart(); else { delay.stop(); root.delayed = false } } }
    Text { width: parent.width; horizontalAlignment: root.horizontalAlignment; wrapMode: Text.Wrap; Reveal { shown: Player.purpose === "review" } text: S.s_nghe_kiem_f9c474bb; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    Text {
        id: bookLabel
        objectName: "playerSubtitleText"; width: parent.width; wrapMode: Text.Wrap
        horizontalAlignment: root.horizontalAlignment
        text: TextWrap.keepDots(root.delayed ? S.s_dang_chuan_bi_giong_doc_25f86ccf : Player.atEnd === "caughtUp" ? S.s_da_nghe_het_phan_da_co_1aa0a8e0 : Player.bookTitle + (root.chevron ? "\u00a0›" : ""))
        color: bookLink.hovered ? Theme.text : Theme.text2; font.pixelSize: Theme.sizeCaption
        font.underline: bookLink.hovered
        Interactive {
            id: bookLink
            objectName: "playerBookLink"
            Reveal { shown: root.showsBook && bookLabel.text !== "" }
            // Vừa khít phần chữ: chỗ trống cạnh tên vẫn thuộc việc của nền (thanh phát: mở Đang nghe). Thấp hơn hộp chạm thì giãn đều lên dưới.
            width: Math.min(bookLabel.width, bookLabel.paintedWidth)
            height: Math.max(bookLabel.paintedHeight, 24)
            x: root.horizontalAlignment === Text.AlignHCenter ? (bookLabel.width - width) / 2 : 0
            y: (bookLabel.paintedHeight - height) / 2
            Accessible.role: Accessible.Button
            Accessible.name: S.s_mo_trang_sach_3f7bd955
            tip: S.s_mo_trang_sach_3f7bd955
            onClicked: {
                root.tappedBook = true
                Later.call(root, function() { root.tappedBook = false })
                root.bookRequested()
            }
        }
    }
}
