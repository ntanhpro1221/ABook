import "UiStrings.js" as S
import QtQuick
import QtQuick.Shapes
import ABook
import "TextWrap.js" as TextWrap
import "BookLogic.js" as BookLogic
import "StudioLogic.js" as StudioLogic

// Ô sách trong lưới (DESIGN.md mục 6, "Lưới bìa"): bìa 2:3 bo 12, dưới bìa tên 2 dòng DÀNH SẴN + dòng phụ 1 dòng (OneLineFit) - mọi ô cao bằng
// nhau, hàng lưới phẳng (soát thiết kế 10-11 L5/L11, như điện thoại). Tên luôn hiện dưới bìa, bìa vẽ hay ảnh như nhau (chủ sách 15-11: hàng
// ô đồng nhất). Tên đầy đủ ở trang sách và Accessible.name. Tiến độ nghe = vạch mảnh ở đáy bìa; sách của máy khác: icon máy tính đầu
// dòng phụ, tên máy ở Accessible.name của icon (như web / điện thoại; chữ "Trên <máy>" không chiếm dòng).
Interactive {
    id: root
    property string title: ""
    property alias transitionCover: coverView
    property string subtitle: ""
    property string coverKey: ""
    property real progress: 0
    property string source: ""
    property bool remoteSeries: false
    property bool twin: false
    property var book: ({})
    property bool playVisible: false
    signal readRequested()
    property bool onPlayButton: false
    property real coverWidth: Theme.coverMin
    readonly property real coverHeight: Math.round(coverWidth * Theme.coverRatio)
    // Dòng tình trạng như web / điện thoại ("Còn 2 giờ", "Đã nghe xong", "12 chương"): tính từ chính cuốn, không kèm tác giả (tác giả có dòng
    // riêng ở trên). `subtitle` chỉ để ô một bộ nhiều tập ghi "N tập". Chỉ dòng thư viện thật (có chaptersTotal) mới có tình trạng.
    readonly property string statusText: root.subtitle !== "" ? root.subtitle
        : root.book && root.book.bookId && typeof root.book.chaptersTotal === "number" ? BookLogic.progressText(root.book, Api.voiceList.length > 0, false) : ""
    // Thư viện còn một cuốn CÙNG TÊN: nối "Dự án" / "Đã nhập" và "Thêm <ngày>" vào dòng tình trạng để biết cuốn nào là cuốn nào (như web twinKind).
    readonly property string twinKind: root.book && root.book.capabilities && root.book.capabilities.workshop ? S.s_du_an_4f139d43
        : root.book && root.book.imported ? S.s_da_nhap_47b970fc : ""
    readonly property string subLine: [root.statusText].concat(root.twin
            ? [root.twinKind, root.book && root.book.addedAt ? S.s_them_0_07ca4c38(StudioLogic.formatWhen(root.book.addedAt)) : ""] : [])
        .filter(part => part !== "").join("\u00a0·\u00a0")
    // Người nghe đã thả tim cho cuốn: dấu tim hổ phách đầu dòng phụ (như web / điện thoại).
    readonly property bool favorite: Boolean(root.book && root.book.state && root.book.state.favorite)
    readonly property real leadMarks: (root.favorite ? 18 : 0) + (root.source !== "" ? 18 : 0)
    readonly property real textBlock: 12 + root.titleHeight + authorText.height + 4 + subtitleText.height

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
            property Item transitionAnchor: root
            anchors.fill: parent
            coverKey: root.coverKey
            title: root.title
        }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: Theme.pressInk
            opacity: root.pressed ? Theme.pressShade : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFastOut } }
        }
        // Vạch tiến độ: một hình với web / Android - sát đáy, cao 4, rãnh Theme.coverOverlay, cắt theo đúng góc bo của bìa.
        Item {
            id: heard
            Reveal { shown: root.progress >= Theme.progressFillMin && root.progress < 0.995 }
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Theme.s4
            CoverBand { width: heard.width; height: heard.height; fill: Theme.coverOverlay }
            Item {
                width: heard.width * root.progress
                height: heard.height
                clip: true
                CoverBand { width: heard.width; height: heard.height; fill: Theme.accent }
            }
        }
        CoverButton {
            id: play
            objectName: "libraryTilePlay"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12
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
    // Hai dòng tên mẫu: chiều cao dành sẵn cho tên.
    FontMetrics { id: titleMetrics; font: titleText.font }
    readonly property real titleHeight: titleMetrics.height * 1.3 * 2
    Text {
        id: titleText
        objectName: "bookCellTitle"
        x: 0
        y: root.coverHeight + 12
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
    // Tác giả là chữ người dùng: một dòng qua OneLineFit (thu cỡ, không vừa thì xuống dòng), không bao giờ "…" - như web và điện thoại.
    OneLineFit {
        id: authorText
        objectName: "bookCellAuthor"
        x: 0
        y: titleText.y + titleText.height
        room: root.coverWidth
        height: text !== "" ? implicitHeight : 0
        text: root.book.author || ""
        color: Theme.text2
        baseSize: Theme.sizeCaption
    }
    // Dòng tình trạng là chữ của app, ĐÚNG một dòng (DESIGN.md mục 6): OneLineFit thu cỡ tới mức tối thiểu rồi mới cắt "…" (cutAtMin), để
    // mọi ô một hàng cao bằng nhau như web (truncate) và điện thoại (maxLines 1).
    OneLineFit {
        id: subtitleText
        objectName: "bookCellSubtitle"
        x: root.leadMarks
        y: authorText.y + authorText.height + 4
        room: root.coverWidth - x
        text: TextWrap.keepDots(root.subLine)
        color: Theme.text3
        baseSize: Theme.sizeCaption
        cutAtMin: true
        // Thu cỡ chữ không làm ô thấp đi: dòng giữ chiều cao một dòng ở cỡ gốc (mọi ô một hàng cao bằng nhau), chữ thu cỡ canh giữa.
        height: Math.max(implicitHeight, slot.implicitHeight)
        verticalAlignment: Text.AlignVCenter
        Text { id: slot; visible: false; text: subtitleText.text; font.family: subtitleText.font.family; font.pixelSize: Theme.sizeCaption }
    }
    Icon {
        objectName: "bookCellFavorite"
        x: 0; y: subtitleText.y + 2; size: 12; name: "heart-filled"; color: Theme.accentText
        Reveal { shown: root.favorite }
        Accessible.role: Accessible.Graphic
        Accessible.name: S.s_heart_favorite
    }
    // Same laptop mark as web, leading the one subtitle line.
    Icon {
        x: root.favorite ? 18 : 0; y: subtitleText.y + 2; size: 12; name: "laptop"; color: Theme.text3
        Reveal { shown: root.source !== "" }
        Accessible.name: root.remoteSeries ? S.s_co_sach_tren_may_khac_3b7cdd88 : S.s_tren_54f68805 + root.source
    }

    // Dải đáy của một hình chữ nhật bo Theme.radiusCover: hai đầu theo cung của góc bo (dải thấp hơn bán kính).
    component CoverBand: Shape {
        id: band
        property color fill: "transparent"
        readonly property real r: Theme.radiusCover
        readonly property real k: r - Math.sqrt(r * r - (r - height) * (r - height))
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillColor: band.fill
            startX: band.k; startY: 0
            PathLine { x: band.width - band.k; y: 0 }
            PathArc { x: band.width - band.r; y: band.height; radiusX: band.r; radiusY: band.r }
            PathLine { x: band.r; y: band.height }
            PathArc { x: band.k; y: 0; radiusX: band.r; radiusY: band.r }
        }
    }
}
