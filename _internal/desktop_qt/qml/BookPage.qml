import QtQuick
import ABook

// Trang sách (màn con của Thư viện): bìa lớn bên trái, thông tin + nút nghe bên phải, dưới là danh sách chương (mỗi hàng nghe chương ấy).
// Nút chính nói đúng chỗ nghe tiếp: "Nghe" cuốn mới, "Nghe tiếp" + tên chương, "Tạm dừng" khi đang phát cuốn này. Sách chưa có audio nói thẳng còn thiếu gì.
// Hàng phụ (Đọc, Tìm, Từ đầu, Thêm) thuộc các bước sau.
Item {
    id: root
    property var book: ({})

    BookDetail {
        id: detail
        bookId: root.book.bookId || ""
    }

    ScreenHeader {
        id: header
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        showBack: true
        title: ""
        implicitHeight: Theme.s32 + Theme.headerRow
    }

    ListView {
        id: list
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        model: detail.chapters
        boundsBehavior: Flickable.StopAtBounds
        bottomMargin: Theme.s32
        readonly property real rowW: Math.min(width - 2 * Theme.margin, 760)

        header: Item {
            width: list.width
            height: Math.max(cover.y + cover.height, info.y + info.height) + Theme.s32 + chaptersTitle.height + Theme.s8

            CoverView {
                id: cover
                x: Theme.margin
                y: Theme.s16
                width: 280
                height: Math.round(width * Theme.coverRatio)
                coverKey: root.book.coverKey || ""
                title: root.book.title || ""
                radius: Theme.radiusCover
            }

            Column {
                id: info
                x: cover.x + cover.width + Theme.s48
                y: cover.y
                width: Math.min(list.width - x - Theme.margin, 560)
                spacing: Theme.s8

                Text {
                    width: parent.width
                    text: root.book.title || ""
                    color: Theme.text
                    wrapMode: Text.Wrap
                    lineHeight: 1.15
                    font.pixelSize: Theme.sizeTitleDesktop
                    font.weight: Theme.weightBold
                }
                Text {
                    visible: !!root.book.author
                    width: parent.width
                    text: root.book.author || ""
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBody
                }
                Text {
                    visible: text !== ""
                    width: parent.width
                    text: [root.book.detail, root.book.chapters > 0 ? root.book.chapters + " chương" : ""].filter(s => !!s).join(" · ")
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Item { width: 1; height: Theme.s8 }
                Rectangle {          // tiến độ mảnh
                    visible: root.book.progress > 0.005
                    width: parent.width
                    height: 4
                    radius: 2
                    color: Theme.sunken
                    Rectangle {
                        width: parent.width * Math.min(1, root.book.progress || 0)
                        height: parent.height
                        radius: parent.radius
                        color: Theme.accent
                    }
                }
                Text {
                    visible: root.book.progress > 0.005
                    width: parent.width
                    text: root.book.progress >= 0.995 ? "Bạn đã nghe xong"
                        : "Bạn đã nghe " + Math.round((root.book.progress || 0) * 100) + " %"
                          + (root.book.lastChapter ? " · " + root.book.lastChapter : "")
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Item { width: 1; height: Theme.s8 }
                Row {
                    visible: detail.canListen
                    spacing: Theme.s16
                    Button {
                        id: primary
                        text: detail.primaryText
                        icon: detail.primaryIcon
                        onClicked: detail.activate()
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: detail.primaryCaption !== ""
                        text: detail.primaryCaption
                        color: Theme.text2
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
                Text {
                    visible: detail.message !== ""
                    width: parent.width
                    text: detail.message
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Text {
                    visible: detail.status === "failed"
                    width: parent.width
                    text: "Chưa lấy được danh sách chương."
                    color: Theme.danger
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
            }

            Text {
                id: chaptersTitle
                visible: detail.chapters.count > 0
                x: Theme.margin
                y: Math.max(cover.y + cover.height, info.y + info.height) + Theme.s32
                text: "Chương"
                color: Theme.text
                font.pixelSize: Theme.sizeSection
                font.weight: Theme.weightMedium
            }
        }

        delegate: Item {
            id: row
            required property var model
            width: list.width
            height: chapter.height
            ChapterRow {
                id: chapter
                x: Theme.margin
                width: list.rowW
                title: row.model.title
                subtitle: row.model.subtitle
                length: row.model.length
                status: row.model.status
                playable: row.model.playable
                done: row.model.done
                current: row.model.current
                progress: row.model.progress
                onClicked: if (row.model.playable) detail.playChapter(row.model.chapterId)
            }
        }
        SmoothWheel { flick: list }
        Scrollbar { target: list }
    }
}
