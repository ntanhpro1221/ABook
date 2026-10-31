import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Một hàng của bảng chương (ChapterRow của ProjectScreen.tsx): số chương (rê chuột thành nút nghe) · tên + tên phụ / lỗi · trạng thái (dấu nhỏ hay vạch
// "đang thu") · độ dài · xong lúc nào · "…". Khổ rộng đủ cột như web; hẹp thì trạng thái và độ dài xuống dưới tên. Tên dài xuống dòng, hàng cao theo chữ.
Item {
    id: root
    property var chapter: ({})
    property bool running: false                // sách đang chạy (vạch thu âm chạy / "dừng ở")
    property bool studio: false                 // máy này có Studio: chữ lỗi nói theo bộ Studio
    property bool canPlay: true                 // Studio từ xa: nghe ở Thư viện của máy kia, không phát ở đây
    property bool current: false
    property bool menuOpen: false
    property real numberW: 48
    signal playRequested()
    signal menuRequested(Item anchor)
    signal errorRequested(Item anchor)

    readonly property bool wide: width >= 720
    readonly property real pad: 8
    readonly property real gap: 12
    readonly property real titleX: pad + numberW + gap
    readonly property real moreX: width - pad - 32 + 4
    readonly property real doneX: wide ? moreX - gap - 96 : moreX
    readonly property real lengthX: wide ? doneX - gap - 110 : moreX
    readonly property real statusX: wide ? lengthX - gap - 150 : moreX
    readonly property var mark: Logic.chapterMark(chapter)
    readonly property bool working: Logic.chapterWorking(chapter)
    readonly property bool playable: Boolean(chapter.playable) && canPlay
    readonly property bool hot: rowButton.hovered || more.hovered || more.activeFocus || menuOpen
    readonly property string errorLine: chapter.lastError ? Logic.friendlyError(chapter.lastError, studio, false, false).summary : ""
    readonly property bool hasStatus: working || mark !== null
    readonly property real narrowExtra: !wide && (hasStatus || lengthText.text !== "") ? 30 : 0
    implicitHeight: Math.max(56, titleBlock.height + narrowExtra + 2 * 12)
    height: implicitHeight
    Accessible.role: Accessible.ListItem
    Accessible.name: chapter.displayTitle || ""

    Interactive {
        id: rowButton
        objectName: "chapterRowButton"
        anchors.fill: parent
        pressScaling: false
        enabled: root.playable
        ringRadius: Theme.radiusControl
        Accessible.name: (root.current && Player.playing ? "Tạm dừng " : "Nghe ") + (root.chapter.displayTitle || "")
        onClicked: root.playRequested()
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusControl
            color: root.current ? Theme.accentSoft : Theme.hover
            opacity: root.current || (root.playable && (rowButton.hovered || more.hovered)) ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        }
    }
    Item {
        x: root.pad
        y: 12
        width: root.numberW
        height: 20
        Text {
            objectName: "chapterNumber"
            visible: !(root.playable && root.hot) && !(root.current && Player.playing)
            text: root.chapter.index
            color: root.current ? Theme.accentText : Theme.text3
            font.pixelSize: Theme.sizeCaption
            font.features: { "tnum": 1 }
            anchors.verticalCenter: parent.verticalCenter
        }
        Icon { visible: root.current && Player.playing && !(root.playable && root.hot); name: "audio-lines"; size: 16; color: Theme.accentText; anchors.verticalCenter: parent.verticalCenter }
        Icon { visible: root.playable && root.hot; name: root.current && Player.playing ? "pause" : "play"; size: 16; color: Theme.text; anchors.verticalCenter: parent.verticalCenter }
    }
    Column {
        id: titleBlock
        x: root.titleX
        y: 12
        width: Math.max(80, (root.wide ? root.statusX - root.gap : root.moreX - 4) - root.titleX)
        spacing: 2
        Text {
            objectName: "chapterTitle"
            width: parent.width
            text: root.chapter.displayTitle || ""
            color: root.current ? Theme.accentText : Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
        }
        Text {
            objectName: "chapterSubtitle"
            visible: text !== ""
            width: parent.width
            text: root.errorLine !== "" ? "" : (root.chapter.subtitle || "")
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        // Lỗi của chương: một câu cho người nghe + "Chi tiết" mở khung nổi có việc nên làm và nguyên văn (ChapterError.tsx)
        Flow {
            objectName: "chapterErrorLine"
            visible: root.errorLine !== ""
            width: parent.width
            spacing: 4
            Text {
                objectName: "chapterErrorText"
                width: Math.min(implicitWidth, parent.width)
                text: root.errorLine
                color: Theme.danger
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
            Interactive {
                id: errorMore
                objectName: "chapterErrorMore"
                width: moreLabel.implicitWidth
                height: Math.max(20, moreLabel.implicitHeight)
                ringMargin: 2
                Accessible.role: Accessible.Button
                Accessible.name: "Chi tiết lỗi " + (root.chapter.displayTitle || "")
                onClicked: root.errorRequested(errorMore)
                Text { id: moreLabel; text: "Chi tiết"; color: Theme.danger; font.pixelSize: Theme.sizeCaption; font.underline: true }
            }
        }
    }
    // Trạng thái: dấu nhỏ khi chương cần chú ý, vạch + "12/30" khi đang thu
    Item {
        id: statusCell
        objectName: "chapterStatus"
        x: root.wide ? root.statusX : root.titleX
        y: root.wide ? 12 : 12 + titleBlock.height + 6
        width: root.wide ? 150 : 200
        height: 24
        visible: root.hasStatus
        // Rê chuột lên vạch đang thu: đang thu hay đứng giữa chương (title của ô trạng thái bên web)
        HoverHandler {
            id: statusHover
            enabled: root.working
            onHoveredChanged: if (hovered) statusTip.restart(); else { statusTip.stop(); Nav.hideTip(statusCell) }
        }
        Timer { id: statusTip; interval: 600; onTriggered: Nav.showTip(statusCell, root.running ? "Đang thu âm" : "Tạm dừng giữa chương") }
        Accessible.description: root.working ? (root.running ? "Đang thu âm" : "Tạm dừng giữa chương") : ""
        Row {
            visible: root.working
            spacing: 8
            anchors.verticalCenter: parent.verticalCenter
            StudioBar {
                objectName: "chapterBar"
                width: 72
                size: "xs"
                anchors.verticalCenter: parent.verticalCenter
                value: Logic.chapterRecorded(root.chapter)
                tone: root.running ? "accent" : "muted"
                label: "Đã thu âm"
            }
            Text { text: Logic.chapterWorkingText(root.chapter, root.running); color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
        }
        StatusPill { visible: !root.working && root.mark !== null; label: root.mark ? root.mark.label : ""; tone: root.mark ? root.mark.tone : "muted"; anchors.verticalCenter: parent.verticalCenter }
    }
    Text {
        id: lengthText
        objectName: "chapterLength"
        x: root.wide ? root.lengthX : root.hasStatus ? statusCell.x + (root.working ? 72 + 8 + 60 : (root.mark ? 100 : 0)) + 12 : root.titleX
        y: root.wide ? 12 + (24 - height) / 2 : 12 + titleBlock.height + 6 + (24 - height) / 2
        width: root.wide ? 110 : implicitWidth
        horizontalAlignment: root.wide ? Text.AlignRight : Text.AlignLeft
        text: Logic.chapterLength(root.chapter)
        color: Theme.text2
        font.pixelSize: Theme.sizeCaption
        font.features: { "tnum": 1 }
    }
    Text {
        objectName: "chapterDone"
        visible: root.wide
        x: root.doneX
        y: 12 + (24 - height) / 2
        width: 96
        horizontalAlignment: Text.AlignRight
        text: Logic.chapterDone(root.chapter)
        color: Theme.text3
        font.pixelSize: Theme.sizeCaption
        font.features: { "tnum": 1 }
    }
    IconButton {
        id: more
        objectName: "chapterMore"
        x: root.moreX
        y: 12 - 6
        width: 32
        height: 32
        icon: "ellipsis"
        iconSize: 16
        ink: Theme.text2
        hoverInk: Theme.text
        Accessible.name: "Tuỳ chọn " + (root.chapter.displayTitle || "")
        opacity: root.hot || !root.wide ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        onClicked: root.menuRequested(more)
    }
}
