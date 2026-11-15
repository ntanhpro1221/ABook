import "UiStrings.js" as S
import QtQuick
import ABook
import "MyMusicText.js" as Music

// Một bài trong "Nhạc của tôi" (hàng của MyMusicSection + AutoPickNote của bản web): nốt nhạc, "tên · nghệ sĩ · m:ss", dòng tự chọn (AutoPickLine: công tắc
// "Tự chọn" rồi nhãn ngắn), và
// "Xoá" -> "Xoá bài" / "Giữ lại" (hai bước). Hàng vào / ra bằng chiều cao (useListPresence): `leaving` khép hàng lại trước khi gỡ.
Collapse {
    id: root
    property var track: ({})
    property bool canImport: true
    property bool removing: false       // đang gửi lệnh xoá
    property bool leaving: false
    property bool entered: false
    property bool first: false
    property bool picking: false        // đang gửi công tắc tự chọn
    property bool canPreview: false     // tab Nhạc nền của Studio có "Nghe thử" ở mỗi bài; Cài đặt thì không
    property bool previewing: false
    signal preview()
    signal remove()
    signal pick(var next)
    open: entered && !leaving
    Component.onCompleted: Later.call(root, function() { root.entered = true })

    readonly property string line: {
        const dim = Qt.color(Theme.text2).toString()
        let html = Music.escapeHtml(track.title || "")
        if (track.creator) html += "<font color=\"" + dim + "\">&nbsp;·&nbsp;" + Music.escapeHtml(track.creator) + "</font>"
        if (track.duration) html += "<font color=\"" + dim + "\">&nbsp;·&nbsp;" + Music.formatClock(track.duration) + "</font>"
        return html
    }

    Item {
        width: parent.width
        height: Math.max(words.height, buttons.height, 40) + 16 + 1
        Rectangle { width: parent.width; height: 1; color: Theme.line; Reveal { shown: !root.first }}
        Item {
            id: row
            y: 1 + 8
            width: parent.width
            height: Math.max(words.height, buttons.height, 40)
            MusicArt { id: noteIcon; track: root.track; width: 40; height: 40 }
            Column {
                id: words
                x: noteIcon.width + 6
                width: row.width - x - (buttons.width > 0 ? buttons.width + 12 : 0)
                Text {
                    width: parent.width
                    text: root.line
                    textFormat: Text.StyledText
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                }
                AutoPickLine {
                    width: parent.width
                    track: root.track
                    canPick: root.canImport
                    busy: root.picking
                    onPick: next => root.pick(next)
                }
            }
            // Nút bên phải: "Xoá" co lại về 0 trong khi "Xoá bài" + "Giữ lại" mở ra (chiều ngang tween)
            Row {
                id: buttons
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Reveal { shown: root.canImport || root.canPreview }
                width: (root.canPreview ? listen.width + (root.canImport ? spacing : 0) : 0)
                       + (root.canImport ? ask.width : 0)
                Button {
                    id: listen
                    objectName: "musicPreview"
                    Reveal { shown: root.canPreview }
                    text: root.previewing ? (Clip.loading ? S.s_buffering : Clip.paused ? S.s_phat_343e7e48 : S.s_tam_dung_67635815) : S.s_nghe_thu_fa024065
                    icon: root.previewing && !Clip.paused ? "pause" : "play"
                    pending: root.previewing && Clip.loading
                    kind: "ghost"; size: "sm"
                    Accessible.name: text + ": " + (root.track.title || "")
                    onActivated: root.preview()
                }
                Item {
                    id: ask
                    Reveal { shown: root.canImport }
                    width: askButton.implicitWidth
                    height: askButton.implicitHeight
                    clip: true
                    Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                    Button {
                        id: askButton
                        objectName: "musicDelete"
                        text: S.s_xoa_777195ab; icon: "trash"; kind: "ghost"; size: "sm"
                        busy: root.removing
                        Accessible.name: S.s_xoa_81a43b8a + (root.track.title || "")
                        onActivated: removeConfirm.show()
                    }
                }
            }
        }
    }
    Collapse { width: parent.width; open: root.previewing; MusicListeningProgress { width: parent.width } }
    DestructiveConfirm { id: removeConfirm; objectName: "musicRemoveConfirm:" + root.track.link; title: S.s_xoa_bai_nay_412d7001
        description: S.s_0_se_bi_xoa_khoi_nhac_cua_toi_a41656b0(root.track.title || ""); onAccepted: root.remove()
    }

}
