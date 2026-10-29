import QtQuick
import ABook
import "CastLogic.js" as Logic

// Một người ở tab Nhân vật (PersonRow của listen/BookScreen.tsx): ô tròn chữ cái, tên + giới (xuống dòng, không cắt), giọng, dòng "Chờ áp dụng" /
// "gộp vào …" (+ "Bỏ gộp"), số câu; bên phải nghe thử, "Đổi giọng", "…" (Gộp vào người khác…, Đổi tên, Đổi giới tính). Nút nào có tuỳ khả năng
// của cuốn (`caps`): rename / merge / gender (cuốn sửa được), voice / unmerge (cuốn có xưởng), waiting (cuốn chờ Studio: chữ "Đang chờ máy làm sách").
Item {
    id: root
    property string bookId: ""
    property string peer: ""                    // Studio của máy tính ghép: mã máy (tệp nghe thử đi qua máy ấy)
    property var person: ({})
    property var caps: ({})
    signal request(string kind, var person)
    signal menuRequested(Item anchor, var person)
    readonly property string shownName: Logic.cleanName(person.displayName)
    readonly property bool canVoiceHere: Boolean(caps.voice) && Boolean(person.voice) && person.lines > 0
    readonly property bool canMergeHere: Boolean(caps.merge) && person.lines > 0
    readonly property bool canGenderHere: Boolean(caps.gender) && Boolean(person.voice) && person.lines > 0
    readonly property bool hasMenu: Boolean(caps.rename) || canGenderHere || canMergeHere
    readonly property bool showsPending: Boolean(caps.voice) || Boolean(caps.waiting)
    implicitHeight: Math.max(avatar.height, texts.height) + 24
    height: implicitHeight

    Rectangle {
        id: avatar
        objectName: "castAvatar"
        x: 0
        y: 12
        width: 40
        height: 40
        radius: width / 2
        readonly property real hue: Logic.hueOf(root.person.voice && root.person.voice.preset ? root.person.voice.preset : root.person.name)
        color: Logic.avatarFill(hue, Theme.dark)
        Text {
            anchors.centerIn: parent
            text: Logic.initials(root.person.displayName)
            color: Logic.avatarInk(avatar.hue, Theme.dark)
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightBold
        }
    }
    Column {
        id: texts
        x: avatar.width + 12
        y: 12
        width: Math.max(0, root.width - x - 12 - buttons.width)
        spacing: 2
        Flow {
            width: parent.width
            spacing: 8
            Text {
                objectName: "castName"
                width: Math.min(implicitWidth, parent.width)
                text: root.shownName
                color: Theme.text
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBody
                font.weight: 600
            }
            Text {
                visible: !!root.person.gender
                text: root.person.gender || ""
                color: Theme.text2
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            visible: !!root.person.originalName
            width: parent.width
            text: "(tên gốc: " + Logic.cleanName(root.person.originalName) + ")"
            color: Theme.text3
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
        }
        Item {
            width: parent.width
            height: voiceText.height + 2
            Icon { x: 0; y: 3; name: "audio-lines"; size: 14; color: Theme.text3 }
            Text {
                id: voiceText
                objectName: "castVoice"
                x: 18
                y: 2
                width: parent.width - 18
                text: Logic.voiceLine(root.person)
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            objectName: "castPending"
            visible: !!root.person.pendingVoice && root.showsPending
            width: parent.width
            text: Logic.pendingVoiceLine(root.person, Boolean(root.caps.waiting))
            color: Theme.accentText
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
            font.weight: Theme.weightMedium
        }
        Flow {
            objectName: "castMerged"
            visible: !!root.person.mergedInto && root.showsPending
            width: parent.width
            spacing: 8
            Text {
                width: Math.min(implicitWidth, parent.width)
                text: Logic.mergedLine(root.person, Boolean(root.caps.waiting))
                color: Theme.accentText
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Interactive {
                objectName: "castUnmerge"
                visible: Boolean(root.caps.unmerge) && typeof root.person.mergedAt === "number"
                implicitWidth: unmergeText.implicitWidth
                implicitHeight: unmergeText.implicitHeight
                width: implicitWidth
                height: implicitHeight
                Accessible.role: Accessible.Button
                Accessible.name: "Bỏ gộp " + root.shownName + " vào " + Logic.cleanName(root.person.mergedInto)
                onClicked: root.request("unmerge", root.person)
                Text {
                    id: unmergeText
                    text: "Bỏ gộp"
                    color: Theme.accentText
                    font.pixelSize: Theme.sizeCaption
                    font.weight: Theme.weightMedium
                    font.underline: true
                }
            }
        }
        Item { width: 1; height: 2 }
        Text {
            objectName: "castCounts"
            width: parent.width
            text: Logic.countLine(root.person)
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
            font.features: { "tnum": 1 }
        }
    }
    Row {
        id: buttons
        x: root.width - width
        y: 12 + (40 - 36) / 2
        spacing: 4
        CastSample {
            objectName: "castSample"
            visible: !!root.person.sampleId
            clipId: Logic.sampleId(root.bookId, root.person)
            url: Logic.routed(Logic.sampleUrl(root.bookId, root.person), root.peer)
            label: "Nghe " + root.shownName + " nói"
        }
        IconButton {
            objectName: "castVoiceButton"
            visible: root.canVoiceHere
            implicitWidth: 36
            implicitHeight: 36
            icon: "sliders-horizontal"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            tip: "Đổi giọng " + root.shownName
            Accessible.name: "Đổi giọng " + root.shownName
            onClicked: root.request("voice", root.person)
        }
        IconButton {
            id: more
            objectName: "castMore"
            visible: root.hasMenu
            implicitWidth: 36
            implicitHeight: 36
            icon: "ellipsis"
            iconSize: 16
            ink: Theme.text2
            hoverInk: Theme.text
            tip: "Thêm tuỳ chọn cho " + root.shownName
            Accessible.name: "Thêm tuỳ chọn cho " + root.shownName
            onClicked: root.menuRequested(more, root.person)
        }
    }
}
