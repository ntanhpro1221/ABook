import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

// Một giọng trong danh sách Cài đặt › Giọng đọc (li của VoiceSettings.tsx): radio "chọn làm mặc định" (dấu tích 20, tên 14/500 xuống dòng ở bất kỳ
// đâu, giới 12 mực phụ, "Mặc định" 12 màu nhấn) + nút "Thử giọng" / "Dừng" cỡ nhỏ bên phải; vạch chia với giọng trên; lỗi nghe thử nằm ngay dưới
// hàng vừa bấm. Cả nhóm chỉ một điểm Tab (`tabbable`): mũi tên đổi chọn như radiogroup, nút thử chỉ vào vòng Tab ở đúng giọng ấy.
Item {
    id: root
    property var voice: ({})
    property string shown: ""
    property bool selected: false
    property bool playing: false
    property bool loading: false
    property string failure: ""
    property bool tabbable: false
    property bool first: false
    readonly property string voiceId: voice.id || ""
    readonly property alias radio: radio
    signal choose()
    signal sample()
    signal step(int direction)
    signal jump(bool end)
    // Giữ chữ lỗi lúc Collapse khép lại
    property string lastFailure: ""
    onFailureChanged: if (failure !== "") lastFailure = failure
    implicitHeight: col.height
    height: implicitHeight

    Column {
        id: col
        width: root.width
        Rectangle { width: parent.width; height: root.first ? 0 : 1; color: Theme.line }
        Item { width: parent.width; height: 8 }
        Item {
            width: parent.width
            height: Math.max(sampleButton.implicitHeight, radio.implicitHeight)
            Interactive {
                id: radio
                x: 0
                width: parent.width - sampleButton.width - 12
                implicitHeight: Math.max(20, name.height)
                height: implicitHeight
                anchors.verticalCenter: parent.verticalCenter
                activeFocusOnTab: root.tabbable || activeFocus      // đang giữ tiêu điểm thì không tắt giữa chừng (Qt cấm)
                Accessible.role: Accessible.RadioButton
                Accessible.name: root.voice.name || ""
                Accessible.checked: root.selected
                onClicked: root.choose()
                Keys.onDownPressed: root.step(1)
                Keys.onRightPressed: root.step(1)
                Keys.onUpPressed: root.step(-1)
                Keys.onLeftPressed: root.step(-1)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Home) { root.jump(false); event.accepted = true }
                    else if (event.key === Qt.Key_End) { root.jump(true); event.accepted = true }
                }
                Icon {
                    id: mark
                    name: "check"
                    size: 20
                    color: Theme.accentText
                    opacity: root.selected ? 1 : 0
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Text {
                    id: name
                    x: 30
                    width: Math.min(implicitWidth, Math.max(0, radio.width - 30 - (gender.visible ? gender.implicitWidth + 10 : 0) - (marker.visible ? marker.implicitWidth + 10 : 0)))
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.shown
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
                Text {
                    id: gender
                    visible: text !== ""
                    x: name.x + name.width + 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: VoiceLogic.genderLabel(root.voice.gender)
                    color: Theme.text2
                    font.pixelSize: Theme.sizeCaption
                }
                Text {
                    id: marker
                    visible: root.selected
                    x: (gender.visible ? gender.x + gender.implicitWidth : name.x + name.width) + 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Mặc định"
                    color: Theme.accentText
                    font.pixelSize: Theme.sizeCaption
                }
            }
            Button {
                id: sampleButton
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                size: "sm"
                kind: "text"
                text: root.playing ? "Dừng" : "Thử giọng"
                icon: root.playing ? "square" : "play"
                busy: root.loading
                activeFocusOnTab: root.tabbable || activeFocus
                Accessible.name: (root.playing ? "Dừng" : "Thử") + " giọng " + (root.voice.name || "")
                onActivated: root.sample()
            }
        }
        Collapse {
            width: parent.width
            open: root.failure !== ""
            Text {
                width: parent.width
                topPadding: 4
                text: root.lastFailure
                color: Theme.danger
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 13
            }
        }
        Item { width: parent.width; height: 8 }
    }
}
