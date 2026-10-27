import QtQuick
import ABook

// Danh sách chương cuộn được (ChaptersModel): ngăn Chương và cột phải của Đang nghe khi sách chưa có chữ chạy theo giọng.
ListView {
    id: root
    signal chapterClicked(int chapterId)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    delegate: ChapterRow {
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
        onClicked: if (model.playable) root.chapterClicked(model.chapterId)
    }
    SmoothWheel { flick: root }
    Scrollbar { target: root }
}
