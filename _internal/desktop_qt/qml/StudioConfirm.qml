import QtQuick
import ABook

// Hộp hỏi lại / báo của Studio (Dialog + DialogActions của shared/ui.tsx): tên + mô tả của Modal, thân là các đoạn chữ (`lines`: {text, tone}
// với tone "bold" | "muted" | ""), có dấu cảnh báo đầu đoạn khi `warn`; chân hộp là các nút `actions` ({key, text, icon, kind, busy, enabled}) -
// nút cuối là nút chính. Bấm nút thì phát `chosen(key)`; đóng hộp (Back, ✕, bấm ra ngoài) phát `closed`. Chữ dài xuống dòng, không bao giờ cắt.
Modal {
    id: root
    property var lines: []
    property bool warn: false
    property var actions: []
    signal chosen(string key)

    Row {
        visible: root.lines.length > 0
        width: parent.width
        spacing: 12
        Icon { visible: root.warn; name: "triangle-alert"; size: 20; color: Theme.warning; y: 2 }
        Column {
            width: parent.width - (root.warn ? 20 + 12 : 0)
            spacing: 8
            Repeater {
                model: root.lines
                delegate: Text {
                    required property var modelData
                    objectName: "confirmLine"
                    width: parent.width
                    text: modelData.text
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    lineHeight: 1.4
                    color: modelData.tone === "muted" ? Theme.text2 : modelData.tone === "warning" ? Theme.warning : Theme.text
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: modelData.tone === "bold" ? Theme.weightBold : Theme.weightRegular
                }
            }
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Repeater {
                model: root.actions
                delegate: Button {
                    required property var modelData
                    objectName: "confirm_" + modelData.key
                    text: modelData.text
                    icon: modelData.icon || ""
                    kind: modelData.kind || "ghost"
                    busy: Boolean(modelData.busy)
                    enabled: modelData.enabled !== false
                    onActivated: root.chosen(modelData.key)
                }
            }
        }
    ]
}
