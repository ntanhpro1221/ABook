import QtQuick
import ABook
import "PrecastLogic.js" as P

// Dải mời trên trang dự án (PrecastBanner của PrecastReview.tsx): phân tích xong, chưa thu bao nhiêu - mở màn duyệt. Sách đang chờ duyệt thì nút "Thu âm" đã là nút chính ở đầu
// trang; dải này chỉ mời duyệt, không thêm nút thứ hai cùng làm một việc.
Item {
    id: root
    objectName: "precastBanner"
    property var book: null
    signal opened()
    readonly property bool held: !!book && !!book.precast && Boolean(book.precast.held)
    readonly property bool stacked: width < 520
    width: parent ? parent.width : 600
    height: 16 + Math.max(icon.height, stacked ? words.height : Math.max(words.height, open.height)) + (stacked ? 12 + open.height : 0) + 16

    Icon {
        id: icon
        x: 0
        y: 16
        name: "clipboard-check"
        size: 20
        color: root.held ? Theme.warning : Theme.accentText
    }
    Column {
        id: words
        x: 20 + 12
        y: 16
        width: root.width - x - (root.stacked ? 0 : open.width + 12)
        spacing: 2
        Text {
            objectName: "precastBannerTitle"
            width: parent.width
            text: P.bannerTitle(root.held)
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            font.weight: 600
        }
        Text {
            width: parent.width
            text: P.BANNER_TEXT
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    Button {
        id: open
        objectName: "precastBannerOpen"
        x: root.stacked ? 32 : root.width - width
        y: root.stacked ? 16 + words.height + 12 : 16 + (words.height - height) / 2
        kind: root.held ? "ghost" : "primary"
        text: "Duyệt ngay"
        onActivated: root.opened()
    }
}
