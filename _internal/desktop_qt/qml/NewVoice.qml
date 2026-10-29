import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "CastLogic.js" as CastLogic

// "Giọng kể" của trình tạo sách (VoiceStep + FirstPersonQuestion + PovChapters + VoiceCard của NewProjectScreen.tsx): "“Tôi” là ai?" (tên người kể, giới, nhân vật tự kể, chương đổi
// người kể), giọng kể phần trước, và lưới giọng (lọc theo giới / miền, nghe thử, mũi tên đổi giọng như radiogroup). Mọi lựa chọn ghi vào nháp của `form`.
Column {
    id: root
    property var form: null
    readonly property var draft: form ? form.draft : ({})
    readonly property var hint: form ? form.hint : undefined
    readonly property var voices: form ? form.voices : []
    readonly property string narrator: draft.narrator || ""
    readonly property string previous: draft.seed ? (draft.seed.narrator || "") : ""
    readonly property string firstPerson: draft.firstPerson || ""
    readonly property bool auto: form ? form.autoNarrator : false
    readonly property var povList: Logic.povChaptersOf(hint, firstPerson)
    property bool opened: false
    property string gender: "all"
    property string region: "all"
    readonly property var shown: voices.filter(voice => (gender === "all" || voice.gender === gender) && (region === "all" || voice.region === region))
        .sort((a, b) => Number(b.name === previous) - Number(a.name === previous))
    readonly property bool hiddenSelection: narrator !== "" && !shown.some(voice => voice.name === narrator)
    readonly property string focusName: shown.some(voice => voice.name === narrator) ? narrator : (shown.length ? shown[0].name : "")
    readonly property bool askOpen: Boolean((hint && hint.firstPerson) || firstPerson !== "" || opened || (hint && hint.chapters && hint.chapters.length))
    readonly property int columns: width >= 1100 ? 3 : width >= 640 ? 2 : 1

    function setNarrator(name) { form.update({narrator: name, narratorPicked: true}) }
    function setFirstPerson(name) { form.update(Object.assign({firstPerson: name}, name.trim() ? {} : {firstPersonGender: undefined, tellerMode: false})) }
    function setGender(next) {
        // Máy chọn giọng dẫn thì giọng hiện trong lưới theo giới vừa chọn (máy chủ đặt đúng giọng ấy lúc tạo)
        const suggested = auto ? Logic.recommendedFor(voices, next) : ""
        form.update(Object.assign({firstPersonGender: next}, suggested ? {narrator: suggested} : {}))
    }
    function focusVoice(name) {
        for (let i = 0; i < cards.count; ++i) {
            const card = cards.itemAt(i)
            if (card && card.voiceName === name) { card.pick.forceActiveFocus(Qt.TabFocusReason); return }
        }
    }
    function step(direction) {
        if (!shown.length) return
        let index = 0
        for (let i = 0; i < shown.length; ++i) if (shown[i].name === focusName) index = i
        const next = shown[(index + direction + shown.length) % shown.length]
        setNarrator(next.name)
        Later.call(root, function() { root.focusVoice(next.name) })
    }

    Text { objectName: "newVoiceTitle"; width: parent.width; text: "Giọng kể"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: "Giọng đọc lời dẫn. Nhân vật được trao giọng riêng sau." }

    // Mở "Kể bằng “tôi”?"
    Item {
        width: parent.width
        height: !root.askOpen ? 12 + ask.height : 0
        visible: height > 0
        TextLink { id: ask; objectName: "newFirstPersonOpen"; y: 12; text: "Kể bằng “tôi”?"; accent: true; enabled: !(root.form && root.form.hintLoading); opacity: enabled ? 1 : 0.6; onClicked: root.opened = true }
    }
    // “Tôi” là ai?
    Collapse {
        width: parent.width
        open: root.askOpen
        Column {
            id: whoBox
            objectName: "newFirstPerson"
            width: parent.width
            topPadding: 20
            Text { width: parent.width; text: "“Tôi” là ai?"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightBold }
            Prose { topPadding: 4; text: "Tên người kể giúp phân vai đúng lời thoại." }
            MoreInfo {
                width: parent.width
                label: "Máy đoán"
                Prose { small: true; text: Logic.firstPersonGuess(root.hint) + " Bạn có thể sửa gợi ý này." }
            }
            // Gợi ý tên người kể
            Item {
                width: parent.width
                visible: Boolean(root.hint) && root.hint.suggestions.length > 0
                height: visible ? 12 + chips.height : 0
                Flow {
                    id: chips
                    objectName: "newPersonChips"
                    y: 12
                    width: parent.width
                    spacing: 8
                    Accessible.role: Accessible.Grouping
                    Accessible.name: "Gợi ý tên người kể"
                    Repeater {
                        model: root.hint ? root.hint.suggestions : []
                        delegate: Interactive {
                            id: chip
                            required property string modelData
                            readonly property bool on: root.firstPerson === modelData
                            width: Math.min(chipText.implicitWidth + 24, chips.width)
                            height: Math.max(36, chipText.height + 12)
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: modelData
                            Accessible.checked: on
                            onClicked: root.setFirstPerson(on ? "" : modelData)
                            Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: chip.hovered && !chip.on ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                            Text {
                                id: chipText
                                width: parent.width - 24
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: chip.modelData
                                color: chip.on ? Theme.accentText : Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBodySmall
                                font.weight: Theme.weightMedium
                                font.underline: chip.on
                                Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
                            }
                        }
                    }
                }
            }
            Prose { topPadding: 12; text: "Tên người kể" }
            Item { width: 1; height: 6 }
            FormField {
                id: whoField
                objectName: "newFirstPersonName"
                width: parent.width
                label: "Tên người kể"
                placeholderText: "Tên nhân vật xưng “tôi” (để trống nếu kể ngôi thứ ba)"
                text: root.firstPerson
                onTextChanged: if (text !== root.firstPerson) root.setFirstPerson(text)
            }
            Collapse {
                width: parent.width
                open: root.firstPerson.trim() !== ""
                Item { width: 1; height: 12 }
                ChoiceRow {
                    objectName: "newPersonGender"
                    width: Math.min(implicitWidth, parent.width)
                    label: "Người kể là"
                    options: [{value: "unknown", label: "Chưa rõ"}, {value: "male", label: "Nam"}, {value: "female", label: "Nữ"}]
                    value: root.draft.firstPersonGender || "unknown"
                    onPicked: value => root.setGender(value === "male" || value === "female" ? value : undefined)
                }
                Prose { topPadding: 6; small: true; text: "Chưa rõ thì máy đoán. Lời dẫn dùng giọng cùng giới người kể." }
                NewSwitchRow {
                    objectName: "newTellerMode"
                    width: parent.width
                    pad: 16
                    name: Logic.TELLER_TITLE
                    hint: Logic.tellerHint(Boolean(root.draft.tellerMode))
                    checked: Boolean(root.draft.tellerMode)
                    onToggled: value => root.form.update({tellerMode: value})
                }
            }
            // Chương đổi người kể
            Collapse {
                width: parent.width
                open: root.povList.length > 0
                Column {
                    objectName: "newPovChapters"
                    width: parent.width
                    topPadding: 16
                    Rectangle { width: parent.width; height: 1; color: Theme.line }
                    Prose { strong: true; tone: Theme.text; topPadding: 12; text: "Chương đổi người kể" }
                    Prose { topPadding: 2; text: "Kể bằng “tôi”; bỏ chọn nếu máy đoán sai." }
                    Item { width: 1; height: 8 }
                    Repeater {
                        model: root.povList
                        delegate: ImportCheck {
                            required property var modelData
                            objectName: "newPovChapter"
                            width: parent.width
                            label: modelData.title + " - “tôi” là " + modelData.name
                            checked: (root.draft.povOff || []).indexOf(modelData.chapter) < 0
                            onToggled: value => {
                                const off = root.draft.povOff || []
                                root.form.update({povOff: value ? off.filter(item => item !== modelData.chapter) : off.concat([modelData.chapter])})
                            }
                        }
                    }
                }
            }
            Item { width: 1; height: 4 }
        }
    }
    Prose { objectName: "newNarratorAuto"; visible: root.auto; topPadding: visible ? 16 : 0; text: "Máy chọn cùng giới người kể; chọn giọng để đổi." }
    // Giọng kể phần trước
    Item {
        width: parent.width
        visible: root.previous !== ""
        height: visible ? 16 + previousText.height : 0
        Text {
            id: previousText
            objectName: "newPreviousNarrator"
            y: 16
            width: parent.width
            textFormat: Text.StyledText
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            lineHeight: 1.4
            text: "Giọng kể phần trước: <b><font color=\"" + Theme.text + "\">" + Logic.esc(root.previous) + "</font></b>" +
                (root.narrator && root.narrator !== root.previous ? " - đang chọn giọng khác, hai phần sẽ đọc lời dẫn khác nhau." : "")
        }
    }
    Item {
        width: parent.width
        visible: root.previous !== "" && root.narrator !== "" && root.narrator !== root.previous
        height: visible ? back.height : 0
        TextLink { id: back; objectName: "newPreviousBack"; text: "Dùng lại " + root.previous; accent: true; onClicked: root.setNarrator(root.previous) }
    }
    Item { width: 1; height: 16 }
    // Đổi giọng
    ImportFold {
        width: parent.width
        storageKey: "voices"
        prefix: "fold.new-project."
        title: "Đổi giọng"
        summary: root.narrator || "Chọn một giọng"
        defaultOpen: root.narrator === ""
        Item { width: 1; height: 16 }
        Flow {
            width: parent.width
            spacing: 12
            ChoiceRow {
                objectName: "newVoiceGender"
                width: Math.min(implicitWidth, parent.width)
                label: "Giới tính"
                options: [{value: "all", label: "Mọi giọng"}, {value: "Nam", label: "Giọng nam"}, {value: "Nữ", label: "Giọng nữ"}]
                value: root.gender
                onPicked: value => root.gender = value
            }
            ChoiceRow {
                objectName: "newVoiceRegion"
                width: Math.min(implicitWidth, parent.width)
                label: "Miền"
                options: [{value: "all", label: "Mọi miền"}, {value: "Bắc", label: "Miền Bắc"}, {value: "Nam", label: "Miền Nam"}, {value: "Trung", label: "Miền Trung"}]
                value: root.region
                onPicked: value => root.region = value
            }
        }
        Collapse {
            width: parent.width
            open: root.hiddenSelection
            Item {
                width: parent.width
                height: 12 + hiddenText.height + hiddenClear.height
                Text {
                    id: hiddenText
                    objectName: "newVoiceHidden"
                    y: 12
                    width: parent.width
                    textFormat: Text.StyledText
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    color: Theme.text2
                    font.pixelSize: Theme.sizeBodySmall
                    lineHeight: 1.4
                    text: "Đang chọn: <b><font color=\"" + Theme.text + "\">" + Logic.esc(root.narrator) + "</font></b> (bộ lọc đang ẩn giọng này)."
                }
                TextLink { id: hiddenClear; objectName: "newVoiceClearFilter"; y: 12 + hiddenText.height; text: "Bỏ lọc"; accent: true; onClicked: { root.gender = "all"; root.region = "all" } }
            }
        }
        Item { width: 1; height: 16 }
        Flow {
            id: grid
            objectName: "newVoiceGrid"
            width: parent.width
            spacing: 12
            Accessible.role: Accessible.RadioButton
            Accessible.name: "Giọng kể chuyện"
            Repeater {
                id: cards
                model: root.shown
                delegate: Item {
                    id: card
                    required property var modelData
                    readonly property string voiceName: modelData.name
                    readonly property bool selected: modelData.name === root.narrator
                    readonly property alias pick: select
                    width: (grid.width - (root.columns - 1) * grid.spacing) / root.columns
                    height: 14 + Math.max(words.height, 40) + 14 + 1
                    CastSample {
                        x: 0
                        y: (card.height - 1 - height) / 2
                        clipId: "voice-" + card.modelData.name
                        url: CastLogic.voiceUrl(card.modelData.name)
                        label: "Nghe thử giọng " + card.modelData.name
                    }
                    Interactive {
                        id: select
                        objectName: "newVoiceCard"
                        x: 48
                        width: parent.width - 48
                        height: parent.height - 1
                        activeFocusOnTab: card.modelData.name === root.focusName
                        pressScaling: false
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: card.modelData.name
                        Accessible.checked: card.selected
                        onClicked: root.setNarrator(card.modelData.name)
                        Keys.onRightPressed: root.step(1)
                        Keys.onDownPressed: root.step(1)
                        Keys.onLeftPressed: root.step(-1)
                        Keys.onUpPressed: root.step(-1)
                        Column {
                            id: words
                            y: 14
                            width: parent.width - 32
                            Text {
                                width: parent.width
                                text: card.modelData.name
                                color: card.selected ? Theme.accentText : Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBody
                                font.weight: Theme.weightBold
                                lineHeight: 1.25
                                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                            }
                            Text {
                                width: parent.width
                                topPadding: 2
                                text: card.modelData.gender + " · Miền " + card.modelData.region + " · " + card.modelData.style
                                color: Theme.text2
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                            }
                            Rectangle {
                                visible: Boolean(card.modelData.recommended)
                                width: badge.width + 12
                                height: visible ? badge.height + 2 : 0
                                radius: Theme.radiusControl
                                color: Theme.accentSoft
                                Text {
                                    id: badge
                                    x: 6
                                    y: 1
                                    text: "ĐỀ XUẤT"
                                    color: Theme.accentText
                                    font.pixelSize: 11
                                    font.weight: Theme.weightBold
                                    font.letterSpacing: 0.5
                                }
                            }
                        }
                        Icon {
                            x: parent.width - 24
                            y: (parent.height - 16) / 2
                            name: "check"
                            size: 16
                            color: Theme.accentText
                            opacity: card.selected ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                        }
                    }
                    Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.line }
                }
            }
        }
    }
}
