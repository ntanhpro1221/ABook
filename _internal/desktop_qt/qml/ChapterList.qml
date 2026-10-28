import QtQuick
import ABook

// Danh sách chương cuộn được (ChaptersModel): ngăn Chương và cột phải của Đang nghe khi sách chưa có chữ chạy theo giọng.
ListView {
    id: root
    signal chapterClicked(int chapterId)
    signal readRequested(int chapterId)
    property var menuChapter: null
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    delegate: ChapterRow {
        id: row
        required property var model
        width: Math.min(ListView.view.width, Theme.listMeasure)
        title: model.title
        subtitle: model.subtitle
        length: model.length
        status: model.status
        playable: model.playable
        done: model.done
        current: model.current
        progress: model.progress
        fullTitle: model.fullTitle
        hasMenu: true
        Accessible.name: model.playable ? model.current && Player.playing ? `Tạm dừng ${model.fullTitle}` : `Nghe ${model.fullTitle}` : `Đọc ${model.fullTitle} (chưa có audio)`
        menuOpen: menu.open && root.menuChapter && root.menuChapter.chapterId === model.chapterId
        onClicked: {
            if (row.onMenuButton) return
            if (!model.playable) root.readRequested(model.chapterId)
            else if (model.current) Player.toggle()
            else root.chapterClicked(model.chapterId)
        }
        onMenuRequested: anchor => {
            root.menuChapter = {chapterId: model.chapterId, playable: model.playable}
            menu.anchorItem = anchor; menu.show()
        }
    }
    Popover {
        id: menu
        panelWidth: 236; pad: Theme.s8
        Column {
            width: parent.width
            MenuRow { width: parent.width; text: "Nghe từ đầu chương"; icon: "play"; visible: !!root.menuChapter && root.menuChapter.playable; onClicked: { menu.close(); Player.jumpTo(root.menuChapter.chapterId, 0) } }
            MenuRow { objectName: "chapterRead"; width: parent.width; text: "Đọc chương này"; icon: "book-open"; onClicked: { menu.close(); root.readRequested(root.menuChapter.chapterId) } }
        }
    }
    SmoothWheel { flick: root }
    Scrollbar { target: root }
}
