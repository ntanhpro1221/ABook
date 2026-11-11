import "UiStrings.js" as S
import QtQuick
import ABook
import "MyMusicText.js" as Music

// Một dòng bài trong "Đổi bài" (TrackRow của MusicTab.tsx): nốt nhạc, "tên · tác giả · độ dài", một dòng ghi chú (tuỳ), "Nghe thử" và "Chọn"
// (= ghim bài ấy cho đoạn này). Hàng hẹp thì nút xuống dòng dưới chữ.
Item {
    id: root
    property var item: ({})
    property string note: ""
    property bool busy: false
    property string choosing: ""
    property string previewing: ""
    property bool canPreview: true
    signal preview(string link)
    signal choose(string link)
    readonly property bool narrow: width < 420
    readonly property string line: {
        const dim = Qt.color(Theme.text2).toString()
        let html = Music.escapeHtml(item.title || S.s_bai_nhac_5d07657e)
        if (item.creator) html += "<font color=\"" + dim + "\">&nbsp;·&nbsp;" + Music.escapeHtml(item.creator) + "</font>"
        if (item.duration) html += "<font color=\"" + dim + "\">&nbsp;·&nbsp;" + Music.formatClock(item.duration) + "</font>"
        return html
    }
    implicitHeight: narrow ? words.height + 4 + buttons.height : Math.max(words.height, buttons.height)
    height: implicitHeight

    Icon { id: noteIcon; y: words.y + 2; name: "eighth-note"; size: 16; color: Theme.text2 }
    Column {
        id: words
        x: noteIcon.width + 6
        width: root.width - x - (root.narrow ? 0 : buttons.width + 12)
        anchors.verticalCenter: root.narrow ? undefined : parent.verticalCenter
        Text {
            width: parent.width
            text: root.line
            textFormat: Text.StyledText
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
        }
        HintText { width: parent.width; visible: root.note !== ""; text: root.note }
    }
    Row {
        id: buttons
        x: root.narrow ? words.x - 12 : root.width - width
        y: root.narrow ? words.height + 4 : (root.height - height) / 2
        spacing: 4
        Button {
            objectName: "musicPreview"
            visible: root.canPreview
            text: root.previewing === root.item.link ? S.s_dung_nghe_f20939be : S.s_nghe_thu_fa024065
            icon: root.previewing === root.item.link ? "square" : "play"
            kind: "ghost"; size: "sm"
            Accessible.name: text + ": " + (root.item.title || S.s_bai_nhac_5d07657e)
            onActivated: root.preview(root.item.link)
        }
        Button {
            objectName: "musicChoose"
            text: root.choosing === root.item.link ? S.s_dang_doi_b4190199 : S.s_chon_1171ca97
            icon: "pin"; kind: "ghost"; size: "sm"
            enabled: !root.busy
            busy: root.choosing === root.item.link
            Accessible.name: S.s_chon_77279ce9 + (root.item.title || S.s_bai_nhac_5d07657e)
            onActivated: root.choose(root.item.link)
        }
    }
}
