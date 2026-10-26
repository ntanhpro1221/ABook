import QtQuick
import ABook

// Trang sách (màn con của Thư viện): bìa lớn bên trái, thông tin bên phải - cửa sổ rộng nên hai cột, không một cột dài như điện thoại.
// D0: mới chỉ thông tin; nút chính "Nghe" và các hàng phụ (Đọc, Tìm, Từ đầu, Thêm) thuộc D1 khi có trình phát.
Item {
    id: root
    property var book: ({})

    ScreenHeader {
        id: header
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        showBack: true
        title: ""
        implicitHeight: Theme.s32 + Theme.headerRow
    }

    CoverView {
        id: cover
        x: Theme.margin
        y: header.height + Theme.s16
        width: 280
        height: Math.round(width * Theme.coverRatio)
        coverKey: root.book.coverKey || ""
        title: root.book.title || ""
        radius: Theme.radiusCover
    }

    Column {
        x: cover.x + cover.width + Theme.s48
        y: cover.y
        width: Math.min(parent.width - x - Theme.margin, 560)
        spacing: Theme.s8

        Text {
            width: parent.width
            text: root.book.title || ""
            color: Theme.text
            wrapMode: Text.Wrap
            maximumLineCount: 4
            elide: Text.ElideRight
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
    }
}
