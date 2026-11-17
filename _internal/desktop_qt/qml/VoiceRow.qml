import "UiStrings.js" as S
import QtQuick
import ABook
import "VoiceLogic.js" as VoiceLogic

// Settings and player share one radio row: one-line name, explicit selection
// semantics and a separate preview action at least 12 logical pixels away.
// Gender is shown only when supplied by the engine; failures stay below the row.
// Each group keeps one radio in the Tab order; its preview is a separate action.
Item {
    id: root
    property var voice: ({})
    property string shown: ""
    property bool selected: false
    property bool saving: Api.savingVoice === voiceId
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
        objectName: "voiceListRow"
        width: Theme.listWidth(root, root.width)
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
                onClicked: if (Api.savingVoice === null) root.choose()
                Keys.onDownPressed: root.step(1)
                Keys.onRightPressed: root.step(1)
                Keys.onUpPressed: root.step(-1)
                Keys.onLeftPressed: root.step(-1)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Home) { root.jump(false); event.accepted = true }
                    else if (event.key === Qt.Key_End) { root.jump(true); event.accepted = true }
                }
                SelectionMark {
                    id: mark
                    selected: root.selected
                    circled: true
                    y: name.y + (name.firstLineHeight - height) / 2      // dấu chọn đứng giữa DÒNG ĐẦU của tên (tên xuống dòng vẫn thẳng dòng đầu)
                }
                // Dấu chọn mờ ra khi vòng chờ lưu hiện, mờ vào khi xong (không bật / tắt cứng)
                Reveal { target: mark; shown: !saveWait.shown }
                PendingIndicator { id: saveWait; y: name.y + (name.firstLineHeight - height) / 2; pending: root.saving }
                // Tên dài: thu cỡ cho vừa một dòng, không vừa nữa thì xuống dòng ở cỡ gốc - không "…" (OneLineFit, cùng luật điện thoại và web)
                OneLineFit {
                    id: name
                    x: 30
                    objectName: "voiceName"
                    room: Math.max(0, radio.width - 30 - (gender.visible ? gender.implicitWidth + 10 : 0))
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.shown
                    color: Theme.text
                    baseSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
                Text {
                    id: gender
                    Reveal { shown: gender.text !== "" }
                    x: name.x + name.width + 10
                    y: name.y + (name.firstLineHeight - height) / 2
                    text: VoiceLogic.genderLabel(root.voice.gender)
                    color: Theme.text2
                    font.pixelSize: Theme.sizeCaption
                }
            }
            Button {
                id: sampleButton
                objectName: "voiceTry"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                size: "sm"
                kind: "text"
                text: root.playing ? S.s_dung_11554138 : S.s_nghe_thu_fa024065
                icon: root.playing ? "square" : "play"
                busy: root.loading
                activeFocusOnTab: root.tabbable || activeFocus
                Accessible.name: root.playing ? S.s_dung_nghe_thu_0_c63198da(root.voice.name || "") : S.s_nghe_thu_0_65a85c4d(root.voice.name || "")
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
                font.pixelSize: 14
            }
        }
        Item { width: parent.width; height: 8 }
    }
}
