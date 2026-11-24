import "UiStrings.js" as S
import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// "Nhạc trong sách": bài kho nhạc không có (`local:` đóng gói kèm sách; BundledTrackRow của ui/src/music/BundledTrack.tsx). Cùng cột với
// MusicTrackRow để danh sách trộn thẳng hàng: ô nghe thử mang dấu sách mờ (không có gì để nghe thử hay lưu), dòng phụ "Đi kèm sách", cột tải để
// trống. Bấm dòng mở MusicBundledDetail.
Interactive {
    id: root
    property var track: ({})
    property bool first: false
    implicitHeight: Math.max(words.height, 40) + 2 * Theme.s12 + 1
    Accessible.name: (track.title || S.s_bai_nay_d9683a01) + (track.creator ? ", " + track.creator : "") + ", " + S.s_bundled_track

    Rectangle { width: parent.width; height: 1; color: Theme.line; Reveal { shown: !root.first }}
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.08 : (root.hovered ? 0.04 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    MusicArt {
        id: art
        x: 0; y: 1 + Theme.s12
        width: 40; height: 40
        track: root.track
    }
    // Same box as the preview IconButton of MusicTrackRow: the text column starts at the same x.
    Item {
        id: mark
        objectName: "musicBundledMark"
        x: art.width + Theme.s8; y: 1 + Theme.s12
        width: Theme.buttonHeight; height: 40
        Icon { anchors.centerIn: parent; name: "book-audio"; size: 20; color: Theme.text3 }
    }
    Column {
        id: words
        x: mark.x + mark.width + Theme.s12
        y: 1 + Theme.s12
        width: root.width - x - Theme.buttonHeight - Theme.s12
        spacing: 4
        Text {
            width: parent.width
            text: TextWrap.keepDots(root.track.title || S.s_bai_nay_d9683a01)
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere // book text is never cut in a new place: a packaged track's title wraps in full
            font.pixelSize: Theme.sizeBody
        }
        Row {
            width: parent.width
            Text {
                width: Math.min(implicitWidth, Math.max(0, parent.width - bundled.width))
                text: TextWrap.keepDots(root.track.creator || "")
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
                elide: Text.ElideRight // text-cut-ok: only the creator yields space to "Đi kèm sách", as to the duration in MusicTrackRow.
            }
            Text {
                id: bundled
                objectName: "musicBundledLabel"
                text: (root.track.creator ? "\u00a0·\u00a0" : "") + S.s_bundled_track
                color: Theme.text2; font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
}
