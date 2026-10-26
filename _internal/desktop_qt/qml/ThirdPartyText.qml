import QtQuick
import ABook
import "MyMusicText.js" as Music

// Danh sách thành phần bên thứ ba (ThirdPartyList của shared/ThirdPartyList.tsx; docs/THIRD_PARTY.md gói lúc build): mỗi mục một tiêu đề 14 / 600 và các
// dòng 13 mực phụ (dòng gạch đầu có chấm, thụt 16); chữ đậm `**...**` và mã `...` của Markdown. Chọn và chép được chữ (select-text). Không có gì
// để hiện thì "Chưa mở được danh sách.".
Column {
    id: root
    property string text: DesktopApi.thirdParty
    readonly property var sections: Music.parseThirdParty(text)
    readonly property string strong: Qt.color(Theme.text).toString()
    readonly property string codeBack: Qt.color(Theme.sunken).toString()
    spacing: 16
    Text {
        visible: root.sections.length === 0
        width: parent.width
        topPadding: 16
        bottomPadding: 16
        text: "Chưa mở được danh sách."
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
    Repeater {
        model: root.sections
        Column {
            id: section
            required property var modelData
            width: root.width
            spacing: 4
            TextEdit {
                visible: section.modelData.title !== ""
                width: parent.width
                height: visible ? implicitHeight : 0
                bottomPadding: 0
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.RichText
                text: Music.inlineHtml(section.modelData.title, root.strong, root.codeBack)
                color: Theme.text
                wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                font.weight: 600
            }
            Repeater {
                model: section.modelData.items
                Item {
                    id: entry
                    required property var modelData
                    width: section.width
                    height: words.implicitHeight
                    Text { visible: entry.modelData.bullet; x: 4; text: "•"; color: Theme.text2; font.pixelSize: 13; lineHeight: 1.625 }
                    TextEdit {
                        id: words
                        x: entry.modelData.bullet ? 16 : 0
                        width: parent.width - x
                        readOnly: true
                        selectByMouse: true
                        textFormat: TextEdit.RichText
                        text: "<p style=\"margin:0; line-height:162%\">" + Music.inlineHtml(entry.modelData.text, root.strong, root.codeBack) + "</p>"
                        color: Theme.text2
                        wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: 13
                    }
                }
            }
        }
    }
}
