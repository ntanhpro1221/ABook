import QtQuick
import ABook

// Danh sách chương của cuốn đang nghe: bấm một chương là nghe chương ấy. Mở ra thì chương đang nghe nằm giữa khung.
Popover {
    id: root
    panelWidth: 380
    maxHeight: 460
    pad: Theme.s8

    onOpenChanged: if (open) list.positionViewAtIndex(Math.max(0, Player.chapters.rowOf(Player.chapterId)), ListView.Center)

    ChapterList {
        id: list
        width: parent.width
        height: Math.min(contentHeight, root.maxHeight - 2 * root.pad)
        model: Player.chapters
        onChapterClicked: (chapterId) => {
            Player.jumpTo(chapterId, 0)
            root.close()
        }
    }
}
