import "UiStrings.js" as S
import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Ô sách trong lưới (DESIGN.md mục 6, "Lưới bìa"): bìa 2:3 bo 12, dưới bìa tên 2 dòng DÀNH SẴN + dòng phụ 1 dòng cắt "…" - mọi ô cao bằng
// nhau, hàng lưới phẳng (soát thiết kế 10-11 L5/L11, như điện thoại). Bìa vẽ (không ảnh) đã in tên: dưới bìa chỉ còn dòng phụ, chỗ của tên vẫn
// giữ - không in tên hai lần. Tên đầy đủ ở trang sách và Accessible.name. Tiến độ nghe = vạch mảnh ở đáy bìa; sách của máy khác: "Trên <máy>"
// đứng đầu dòng phụ, có icon máy tính.
Interactive {
    id: root
    property string title: ""
    property alias transitionCover: coverView
    property string subtitle: ""
    property string coverKey: ""
    property real progress: 0
    property string source: ""
    property bool remoteSeries: false
    property var book: ({})
    property bool playVisible: false
    signal readRequested()
    property bool onPlayButton: false
    property real coverWidth: Theme.coverMin
    readonly property real coverHeight: Math.round(coverWidth * Theme.coverRatio)
    // Bìa vẽ từ tên (không ảnh) đã in tên sách lên bìa.
    readonly property bool drawnTitle: coverKey === ""
    readonly property string subLine: [root.source !== "" ? (root.remoteSeries ? S.s_co_sach_tren_may_khac_3b7cdd88 : S.s_tren_54f68805 + root.source) : "", root.subtitle]
        .filter(part => part !== "").join(" · ")
    readonly property real textBlock: 12 + root.titleHeight + 4 + subtitleText.height

    activeFocusOnTab: false
    ringRadius: Theme.radiusCover
    ringHeight: coverHeight
    pressScaling: false
    implicitWidth: coverWidth
    implicitHeight: coverHeight + textBlock

    Item {
        id: cover
        width: root.coverWidth
        height: root.coverHeight
        // Rê chuột: bìa nhích lên 1,02; nhấn: thu 0,97 + tối 6 % (DESIGN.md 5.2). Chỉ transform / opacity.
        scale: root.pressed ? Theme.pressScale : (root.hovered && Nav.uiVisible && !Theme.reduceMotion ? 1.02 : 1)
        Behavior on scale {
            NumberAnimation {
                duration: root.pressed ? Theme.motionFastOut : Theme.motionFast
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
        CoverView {
            id: coverView
            anchors.fill: parent
            coverKey: root.coverKey
            title: root.title
        }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: "#000000"
            opacity: root.pressed ? Theme.pressShade : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFastOut } }
        }
        Rectangle {          // vạch tiến độ
            visible: root.progress > 0.005 && root.progress < 0.995
            x: 8
            y: parent.height - 11
            width: parent.width - 16
            height: 3
            radius: height / 2
            color: "#66000000"
            Rectangle {
                width: parent.width * root.progress
                height: parent.height
                radius: parent.radius
                color: Theme.accent
            }
        }
        CoverButton {
            id: play
            objectName: "libraryTilePlay"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10
            readonly property bool here: Player.loaded && Player.bookId === root.book.bookId
            // Sách chỉ có chữ vẫn nghe được bằng giọng đọc của máy; máy chưa có giọng nào thì nút mở trang đọc.
            readonly property bool textOnly: root.book.stage === "text" && Api.voiceList.length === 0
            icon: textOnly ? "book-open" : here && Player.playing ? "pause" : "play"
            tip: textOnly ? S.s_doc_0_2e6ee219(root.title) : here && Player.playing ? S.s_tam_dung_0_43ccbbf2(root.title)
                : root.book.stage === "text" ? S.s_nghe_ngay_0_95114fdc(root.title) : S.s_nghe_0_42d1e966(root.title)
            opacity: root.playVisible && (root.hovered || root.externalFocus || play.activeFocus || here) ? 1 : 0
            visible: opacity > 0
            enabled: root.playVisible
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            onClicked: {
                root.onPlayButton = true
                Later.call(root, function() { root.onPlayButton = false })
                if (textOnly) root.readRequested()
                else if (here) Player.toggle()
                else Player.playBook(root.book.bookId)
            }
        }
    }
    // Hai dòng tên mẫu: chiều cao dành sẵn cho tên, có hay không có tên dưới bìa.
    FontMetrics { id: titleMetrics; font: titleText.font }
    readonly property real titleHeight: titleMetrics.height * 1.3 * 2
    Text {
        id: titleText
        objectName: "bookCellTitle"
        visible: !root.drawnTitle
        x: 0
        y: root.subtitleFirst ? subtitleText.y + subtitleText.height + 4 : root.coverHeight + 12
        width: root.coverWidth
        height: root.titleHeight
        text: TextWrap.keepDots(root.title)
        color: Theme.text
        wrapMode: Text.Wrap
        maximumLineCount: 2   // text-cut-ok: tên dưới bìa giữ đúng 2 dòng để mọi ô cao bằng nhau (DESIGN.md mục 6); tên đầy đủ ở trang sách và Accessible.name
        elide: Text.ElideRight   // text-cut-ok: như trên
        lineHeight: 1.3
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
    readonly property bool subtitleFirst: root.drawnTitle
    Text {
        id: subtitleText
        objectName: "bookCellSubtitle"
        x: root.source !== "" ? 18 : 0
        y: root.subtitleFirst ? root.coverHeight + 12 : titleText.y + titleText.height + 4
        width: root.coverWidth - x
        text: TextWrap.keepDots(root.subLine)
        color: Theme.text3
        wrapMode: Text.NoWrap
        maximumLineCount: 1   // text-cut-ok: dòng phụ ô lưới một dòng (DESIGN.md mục 6), phần đầu là thứ quan trọng
        elide: Text.ElideRight   // text-cut-ok: như trên
        font.pixelSize: Theme.sizeCaption
    }
    // Same laptop mark as web, leading the one subtitle line.
    Icon {
        x: 0; y: subtitleText.y + 2; size: 12; name: "laptop"; color: Theme.text3
        visible: root.source !== ""
        Accessible.name: root.remoteSeries ? S.s_co_sach_tren_may_khac_3b7cdd88 : S.s_tren_54f68805 + root.source
    }
}
