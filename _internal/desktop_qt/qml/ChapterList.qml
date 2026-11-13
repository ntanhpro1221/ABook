import "UiStrings.js" as S
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
        width: Theme.listWidth(ListView.view, ListView.view.width)
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
        Accessible.name: model.playable ? model.current && Player.playing ? S.s_tam_dung_0_43ccbbf2(model.fullTitle) : S.s_nghe_0_42d1e966(model.fullTitle) : S.s_doc_0_2e6ee219(model.fullTitle)
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
            MenuRow { width: parent.width; text: S.s_nghe_tu_dau_chuong_06c66bfc; icon: "play"; Reveal { shown: !!root.menuChapter && root.menuChapter.playable } onClicked: { menu.close(); Player.jumpTo(root.menuChapter.chapterId, 0) } }
            MenuRow { objectName: "chapterRead"; width: parent.width; text: S.s_doc_chuong_nay_5d5272d3; icon: "book-open"; onClicked: { menu.close(); root.readRequested(root.menuChapter.chapterId) } }
        }
    }
    SmoothWheel { flick: root }
    Scrollbar { target: root }
}
