import "UiStrings.js" as S
import QtQuick
import ABook

// Ghi công bài nhạc đang phát, dưới tên chương (như MusicCreditLine của bản web): "Nhạc nền: tên · tác giả". Bài của danh mục: bấm mở hộp
// "Bài đang phát" (MusicTrackDetail: cảm xúc, Vì sao bài này, Lưu / Bỏ lưu, Xem trong kho, Đổi bài). Bài tự nhập (local:): bấm mở dần lời ghi
// công đầy đủ, giấy phép (liên kết), lời "Đã chỉnh sửa" khi giấy phép đòi, trang của bài. Đổi bài thì gập lại. Hiện / ẩn dần khi nhạc phát / im.
Item {
    id: root
    readonly property bool shown: Player.playing && (Music.credit.label || "") !== ""
    property var credit: ({})
    property bool open: false
    readonly property bool catalog: (credit.link || "") !== "" && String(credit.link).indexOf("local:") !== 0

    // Giữ lời ghi công cuối trong lúc mờ đi, không để chữ biến mất trước khung.
    function refresh() {
        if ((Music.credit.label || "") !== "") credit = Music.credit
        open = false
    }
    function esc(value) { return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;").split('"').join("&quot;") }
    Component.onCompleted: refresh()
    Connections {
        target: Music
        function onCreditChanged() { root.refresh() }
    }

    // Cuốn có nhạc: giữ chỗ một dòng kể cả khi nhạc im (dừng nghe, đoạn không nhạc) - bìa lớn không đổi cỡ mỗi lần bấm phát / dừng.
    implicitHeight: shown ? body.implicitHeight : (Music.hasMusic ? body.topPadding + caption.implicitHeight : 0)
    height: implicitHeight
    opacity: shown ? 1 : 0
    clip: height < body.implicitHeight
    Behavior on implicitHeight { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }

    Column {
        id: body
        width: parent.width
        topPadding: 4
        spacing: 0

        Interactive {
            id: toggle
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, caption.implicitWidth)
            height: caption.implicitHeight
            pressScaling: false
            tip: root.credit.text || root.credit.label || ""
            onClicked: root.catalog ? playingSheet.show(root.credit.link, root.credit.book && root.credit.scene ? {book: root.credit.book, scene: root.credit.scene} : null) : root.open = !root.open
            Text {
                id: caption
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                textFormat: Text.PlainText
                text: S.s_nhac_nen_198fce26 + (root.credit.label || "")
                color: toggle.hovered ? Theme.text : Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
            }
        }

        // Phần mở: cao và mờ cùng đi (Collapse của bản web).
        Item {
            id: collapse
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(parent.width, 384)
            height: root.open ? details.implicitHeight : 0
            opacity: root.open ? 1 : 0
            clip: height < details.implicitHeight
            visible: height > 0
            Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }

            Column {
                id: details
                width: parent.width
                topPadding: Theme.s4
                Line { text: root.credit.text || "" }
                Line {
                    Reveal { shown: (root.credit.license || "") !== "" }
                    rich: true
                    text: S.s_giay_phep_14b585a0 + (root.credit.licenseUrl
                        ? "<a href=\"" + root.esc(root.credit.licenseUrl) + "\">" + root.esc(root.credit.license) + "</a>" : root.esc(root.credit.license))
                }
                Line { Reveal { shown: root.credit.modified === true } text: root.credit.modifiedNote || "" }
                Line {
                    Reveal { shown: (root.credit.landing || "") !== "" }
                    rich: true
                    text: "<a href=\"" + root.esc(root.credit.landing) + S.s_trang_cua_bai_nhac_a_dcd03b62
                }
            }
        }
    }

    component Line: Text {
        property bool rich: false
        width: parent.width
        textFormat: rich ? Text.StyledText : Text.PlainText
        linkColor: Theme.text2
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
        onLinkActivated: (link) => Qt.openUrlExternally(link)
        HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
    }

    MusicTrackDetail {
        id: playingSheet
        playing: true
        onSave: playingSheet.change("/api/music/library/save")
        onUnsave: playingSheet.change("/api/music/library/unsave")
        onOpenLibrary: title => { playingSheet.open = false; Nav.musicRequested(title) }
        onSwap: { playingSheet.open = false; Nav.musicPickRequested(playingSheet.context.book, playingSheet.context.scene) }
        function change(path) { Api.quiet("POST", path, {links: [playingSheet.link]}, function(data, problem) { if (problem) Api.notice = problem; else playingSheet.reload() }) }
    }
}
