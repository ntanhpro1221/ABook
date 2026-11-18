import "UiStrings.js" as S
import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Thanh "Đang nghe thử · tên · ■" nổi ở đáy Kho nhạc (PreviewBar của ui/src/music/MusicScreen.tsx và của MusicScreen.kt). Bấm thân thanh mở chi
// tiết của chính bài đang nghe thử (`opened`, nối vào đúng hàm mà dòng bài gọi); nút ■ chỉ dừng nghe thử (`stopped`). Cả khung - thân thanh lẫn
// khe `gap` dưới nó - nuốt cú bấm (TapShield + nút giữ cú bấm riêng): không cú bấm nào lọt xuống dòng bài nằm dưới.
Item {
    id: root
    property var track: null
    property bool loading: false
    property bool paused: false
    property real gap: Theme.s8
    readonly property alias body: body
    readonly property alias stopButton: stop
    // Một câu cho cả chữ trên thanh lẫn tên đọc cho trình đọc màn hình: trạng thái (Đang đệm / Đã tạm dừng / Đang nghe thử) không được mất khỏi tên
    // (soát 17-11); việc của cú bấm ("Mở") nằm ở phần mô tả. Bài thiếu tên thì chỉ còn trạng thái, như web (soát 18-11: " · undefined").
    readonly property string line: (root.loading ? S.s_buffering : root.paused ? S.s_music_paused : S.s_dang_nghe_thu_f1fb4cba)
                                   + (root.track && root.track.title ? "\u00a0·\u00a0" + root.track.title : "")
    signal opened()
    signal stopped()
    implicitHeight: 48 + gap

    TapShield {}
    Interactive {
        id: body
        objectName: "musicPreviewOpen"
        width: parent.width
        height: 48
        Accessible.role: Accessible.Button
        Accessible.name: root.line
        Accessible.description: S.s_mo_741bd2c2
        onClicked: root.opened()
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusControl
            color: Theme.panel
            border.color: Theme.line
        }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusControl
            color: Theme.text
            opacity: body.pressed ? 0.08 : (body.hovered ? 0.04 : 0)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
        Text {
            x: Theme.s16; width: parent.width - stop.width - 2 * Theme.s16
            anchors.verticalCenter: parent.verticalCenter
            text: TextWrap.keepDots(root.line)
            color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap
        }
    }
    IconButton {
        id: stop
        objectName: "musicPreviewStop"
        x: body.width - width; y: (body.height - height) / 2
        icon: "square"; tip: S.s_dung_nghe_f20939be
        onActivated: root.stopped()
    }
}
