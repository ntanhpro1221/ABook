import QtQuick
import ABook
import "ExportLogic.js" as Logic
import "SizeFormat.js" as Size
import "EditBookLogic.js" as Notes

// Máy chưa có (hay có bản cũ của) công cụ ghép âm thanh (FfmpegNeeded của desktop/AudiobookDialog.tsx): tải một lần ngay trong hộp. Đang tải: thanh + % + "Dừng".
// Studio từ xa chỉ nói việc này làm ở máy tính; máy không tải được thì nói lý do; tải hỏng thì lời lỗi + nút "Thử lại" + nguyên văn trong "Chi tiết".
// `status`: trả lời của GET /api/ffmpeg. Chữ xuống dòng, không bao giờ cắt.
Column {
    id: root
    objectName: "ffmpegNeeded"
    property var status: null
    property bool remote: false
    property string computer: "máy tính"
    property bool detailOpen: false
    signal download()
    signal stop()
    readonly property bool outdated: Boolean(status && status.outdated)
    topPadding: 12
    bottomPadding: 12
    spacing: 2
    Accessible.role: Accessible.Grouping
    Accessible.name: "Công cụ ghép âm thanh"

    Text {
        objectName: "ffmpegTitle"
        width: parent.width
        text: root.outdated ? "Cập nhật công cụ" : "Thiếu công cụ ghép"
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightMedium
    }
    Text {
        objectName: "ffmpegLine"
        width: parent.width
        text: (root.outdated ? "Có bản mới để ghép lời đọc thành file MP3 / M4B" : "Tải một lần để ghép MP3 / M4B")
              + " (khoảng " + Size.formatSize(root.status ? root.status.bytes : 0).replace(" ", " ") + ")."
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
    Item { width: 1; height: 6 }
    Item {
        visible: root.status !== null && root.status.downloading
        width: parent.width
        height: Math.max(40, percent.implicitHeight)
        Button { id: halt; objectName: "ffmpegStop"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; size: "sm"; kind: "ghost"; text: "Dừng"; onClicked: root.stop() }
        Text {
            id: percent
            objectName: "ffmpegPercent"
            anchors.right: halt.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, parent.width * 0.5)
            text: root.status ? (root.status.retrying ? Notes.RETRYING_NOTE + " " : "") + Logic.ffmpegPercent(root.status) + "%" : ""
            color: Theme.text2
            horizontalAlignment: Text.AlignRight
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
        StudioBar {
            objectName: "ffmpegBar"
            anchors.left: parent.left
            anchors.right: percent.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            value: root.status ? Logic.ffmpegPercent(root.status) / 100 : 0
            label: "Đang tải công cụ ghép âm thanh"
        }
    }
    OnComputerPill {
        visible: root.status !== null && !root.status.downloading && root.remote
        verb: root.outdated ? "Cập nhật công cụ ghép âm thanh" : "Tải công cụ ghép âm thanh"
        computer: root.computer
        maxWidth: root.width
    }
    Text {
        objectName: "ffmpegBlocked"
        visible: root.status !== null && !root.status.downloading && !root.remote && Boolean(root.status.blocked)
        width: parent.width
        text: root.status ? root.status.blocked : ""
        color: Theme.warning
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
    Flow {
        visible: root.status !== null && !root.status.downloading && !root.remote && !root.status.blocked
        width: parent.width
        spacing: 12
        // Lời lỗi nói "bấm Thử lại" (studio_setup.download_failure): nút mang đúng tên ấy
        Button {
            objectName: "ffmpegDownload"
            size: "sm"
            text: root.status && root.status.error ? "Thử lại" : root.outdated ? "Cập nhật công cụ" : "Tải công cụ"
            onClicked: root.download()
        }
        Column {
            visible: root.status !== null && Boolean(root.status.error)
            width: Math.min(root.width, 360)
            Text { objectName: "ffmpegError"; width: parent.width; text: root.status ? root.status.error : ""; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
            TextLink {
                visible: root.status !== null && Boolean(root.status.errorDetail)
                small: true
                text: "Chi tiết"
                onClicked: root.detailOpen = !root.detailOpen
            }
            Collapse {
                width: parent.width
                open: root.detailOpen && root.status !== null && Boolean(root.status.errorDetail)
                TextEdit {
                    objectName: "ffmpegDetail"
                    width: parent.width
                    readOnly: true
                    selectByMouse: true
                    text: root.status && root.status.errorDetail ? root.status.errorDetail : ""
                    color: Theme.text2
                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                    font.family: "monospace"
                    font.pixelSize: 11
                }
            }
        }
    }
}
