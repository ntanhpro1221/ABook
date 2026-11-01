import QtQuick
import ABook
import "MyMusicText.js" as Music

// Dòng tự chọn của một bài nhạc (MyMusicTrack, EditBookMyMusic; bản web AutoPickNote): công tắc "Tự chọn" ĐẦU dòng rồi mới tới nhãn ngắn
// ("Có lời", "Chưa phân tích"). Nhãn dài ngắn khác nhau nên đứng sau: công tắc của các hàng anh em luôn cùng một cột. Nhãn nối sau "Tự chọn"
// bằng dấu ngăn dính hai bên ("Tự chọn · Có lời"), không đọc dính thành một cụm; máy không tự chọn (không công tắc) thì chỉ còn nhãn.
Flow {
    id: root
    objectName: "autoPickLine"
    property var track: ({})
    property bool canPick: true     // tự chọn là việc của máy chủ sách
    property bool busy: false       // đang gửi công tắc
    signal pick(var next)
    spacing: 8
    topPadding: 2
    readonly property string note: Music.trackNote(track)
    Row {
        visible: root.canPick
        spacing: 8
        Switch {
            id: autoSwitch
            objectName: "autoPick"
            label: Music.AUTO_PICK_LABEL + ": " + (root.track.title || "")
            checked: Music.autoOn(root.track)
            enabled: !root.busy
            onToggled: root.pick(Music.autoNext(root.track))
        }
        Text {
            objectName: "autoPickLabel"
            text: Music.AUTO_PICK_LABEL + (root.note !== "" ? "\u00a0·\u00a0" + root.note : "")
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            height: 24
            verticalAlignment: Text.AlignVCenter
            TapHandler { enabled: autoSwitch.enabled; onTapped: autoSwitch.clicked() }
        }
    }
    Text {
        objectName: "autoPickNote"
        visible: !root.canPick && text !== ""
        text: root.note
        color: Theme.text2
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        width: Math.min(implicitWidth, root.width)
        font.pixelSize: Theme.sizeCaption
        height: 24
        verticalAlignment: Text.AlignVCenter
    }
}
