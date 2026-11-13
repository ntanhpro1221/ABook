import "UiStrings.js" as S
import QtQuick
import ABook
import "ScriptLogic.js" as Script
import "CastLogic.js" as Cast
import "StudioLogic.js" as Studio

// Chọn người nói của một câu (SpeakerMenu của ScriptTab.tsx): ô tìm mọi người trong truyện (bỏ dấu), "Máy gợi ý", người của chương (kèm số phím),
// rồi "Khác" (Người kể, Vai phụ không tên). Tìm không ra ai thì tạo người mới với giới - dây chuyền cấp giọng riêng như bước phân vai.
// `embedded`: nằm trong bảng cách đọc câu (lời kể thành lời thoại) - ô tìm không giành con trỏ và không mời "Người kể" (câu thoại phải có chủ).
Column {
    id: root
    property var line: ({})
    property var script: ({cast: [], others: []})
    property bool embedded: false
    signal picked(var person)

    readonly property string query: findField.text.trim()
    readonly property var found: query ? Script.findPeople(script, query) : []
    readonly property var suggested: Script.suggestedOf(script, line)
    readonly property var fixed: Script.FIXED.filter(person => !embedded || person.value !== Script.NARRATOR)
    function focusFind() { findField.forceActiveFocus() }
    spacing: 8

    WorkField {
        id: findField
        objectName: "speakerSearch"
        width: parent.width
        label: S.s_tim_nguoi_noi_70e3871e
        placeholderText: S.s_tim_nguoi_khac_trong_truyen_e6ee499c
        activeFocusOnTab: !root.embedded
        onAccepted: if (root.found.length) root.picked(root.found[0])
    }
    Column {
        width: parent.width
        // Tìm thấy: tối đa 8 người
        Repeater {
            model: root.query ? root.found : []
            delegate: Row_ { required property var modelData; person: modelData }
        }
        // Người chưa từng được máy gán câu nào (linh thể nói trong 『』...): tạo người ấy
        Item {
            objectName: "speakerNew"
            Reveal { shown: root.query !== "" && root.found.length === 0 }
            width: parent.width
            height: visible ? newBox.height + 20 : 0
            Column {
                id: newBox
                x: 8; y: 10
                width: parent.width - 16
                spacing: 8
                Text {
                    width: parent.width
                    text: S.s_chua_co_ai_ten_nhu_the_trong_truyen_tao_ng_897641ec + root.query + "”:"
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Row {
                    width: parent.width
                    spacing: 8
                    Repeater {
                        model: Script.GENDERS
                        delegate: Button {
                            required property var modelData
                            objectName: "speakerNew_" + modelData.value
                            width: (newBox.width - 12) / 3
                            size: "sm"
                            kind: "ghost"
                            text: modelData.label
                            onClicked: root.picked({value: root.query, label: root.query, lines: 0, newGender: modelData.value})
                        }
                    }
                }
            }
        }
        Section_ { shown: !root.query && !!root.suggested && root.suggested.value !== root.line.current; text: S.s_may_goi_y_1e7f4cfa; tone: Theme.warning }
        Row_ { Reveal { shown: !root.query && !!root.suggested && root.suggested.value !== root.line.current } person: root.suggested || ({value: "", label: "", lines: 0}) }
        Section_ { shown: !root.query && root.script.cast.length > 0; text: S.s_trong_chuong_nay_73a2b156 }
        Repeater {
            model: root.query ? [] : root.script.cast
            delegate: Row_ { required property var modelData; required property int index; person: modelData; hotkey: index < Script.HOTKEYS ? String(index + 1) : "" }
        }
        Section_ { shown: !root.query; text: S.s_khac_bda82bf0 }
        Repeater {
            model: root.query ? [] : root.fixed
            delegate: Row_ { required property var modelData; person: modelData }
        }
    }

    component Section_: Text { id: textItem;
        property bool shown: true
        property color tone: Theme.text2
        Reveal { shown: textItem.shown }
        width: parent.width
        height: shown ? implicitHeight + 10 : 0
        leftPadding: 8
        topPadding: 8
        bottomPadding: 4
        color: tone
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
        wrapMode: Text.Wrap
    }
    component Row_: Interactive {
        id: option
        property var person: ({})
        property string hotkey: ""
        readonly property bool current: person.value === root.line.current
        objectName: "speakerOption"
        width: parent ? parent.width : 0
        height: Math.max(36, label.implicitHeight + 12)
        Accessible.role: Accessible.Button
        Accessible.name: label.text
        onClicked: root.picked(person)
        Keys.onReturnPressed: root.picked(person)
        Keys.onSpacePressed: root.picked(person)
        Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: option.hovered || option.activeFocus ? 1 : 0 }
        Rectangle {
            id: badge
            x: 8
            anchors.verticalCenter: parent.verticalCenter
            width: 24; height: 24; radius: width / 2
            readonly property real hue: Cast.hueOf(option.person.label || "")
            color: Cast.avatarFill(hue, Theme.dark)
            Text {
                anchors.centerIn: parent
                text: option.hotkey || String(option.person.label || "").slice(0, 1).toUpperCase()
                color: Cast.avatarInk(badge.hue, Theme.dark)
                font.pixelSize: 12
                font.weight: Theme.weightBold
            }
        }
        Text {
            id: label
            objectName: "speakerOptionName"
            x: 40
            width: parent.width - x - tail.width - 16
            anchors.verticalCenter: parent.verticalCenter
            text: option.current ? S.s_dung_la_8cf18603 + option.person.label : option.person.label
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
        }
        Item {
            id: tail
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            width: option.current ? 16 : count.visible ? count.implicitWidth : 0
            height: 16
            Icon { Reveal { shown: option.current } name: "check"; size: 16; color: Theme.success }
            Text {
                id: count
                Reveal { shown: !option.current && option.person.lines > 0 }
                anchors.verticalCenter: parent.verticalCenter
                text: Studio.formatNumber(option.person.lines || 0)
                color: Theme.text3
                font.pixelSize: Theme.sizeCaption
            }
        }
    }
}
