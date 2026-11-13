import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "CastLogic.js" as CastLogic
import "TextWrap.js" as TextWrap

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

    Text { objectName: "newVoiceTitle"; width: parent.width; text: S.s_giong_ke_b209f686; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: S.s_giong_doc_loi_dan_nhan_vat_duoc_trao_giong_6dd30d7a }

    // Mở "Kể bằng “tôi”?"
    Item {
        width: parent.width
        height: !root.askOpen ? 12 + ask.height : 0
        visible: height > 0
        TextLink { id: ask; objectName: "newFirstPersonOpen"; y: 12; text: S.s_ke_bang_toi_521f80f7; accent: true; enabled: !(root.form && root.form.hintLoading); opacity: enabled ? 1 : 0.6; onClicked: root.opened = true }
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
            Text { width: parent.width; text: S.s_toi_la_ai_efbf5a65; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightBold }
            Prose { topPadding: 4; text: S.s_ten_nguoi_ke_giup_phan_vai_dung_loi_thoai_ded89111 }
            MoreInfo {
                width: parent.width
                label: S.s_may_doan_0f0472f0
                Prose { small: true; text: Logic.firstPersonGuess(root.hint) + S.s_ban_co_the_sua_goi_y_nay_ffd074da }
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
                    Accessible.name: S.s_goi_y_ten_nguoi_ke_7b50873d
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
            Prose { topPadding: 12; text: S.s_ten_nguoi_ke_d492ccfb }
            Item { width: 1; height: 6 }
            FormField {
                id: whoField
                objectName: "newFirstPersonName"
                width: parent.width
                label: S.s_ten_nguoi_ke_d492ccfb
                placeholderText: S.s_ten_nhan_vat_xung_toi_de_trong_neu_ke_ngoi_67659017
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
                    label: S.s_nguoi_ke_la_379f9c45
                    options: [{value: "unknown", label: S.s_chua_ro_be464a5a}, {value: "male", label: S.s_nam_22dd59c8}, {value: "female", label: S.s_nu_e15bc11c}]
                    value: root.draft.firstPersonGender || "unknown"
                    onPicked: value => root.setGender(value === "male" || value === "female" ? value : undefined)
                }
                Prose { topPadding: 8; small: true; text: S.s_chua_ro_thi_may_doan_loi_dan_dung_giong_cu_243f284d }
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
                    Prose { strong: true; tone: Theme.text; topPadding: 12; text: S.s_chuong_doi_nguoi_ke_88865076 }
                    Prose { topPadding: 4; text: S.s_ke_bang_toi_bo_chon_neu_may_doan_sai_306c44c1 }
                    Item { width: 1; height: 8 }
                    Repeater {
                        model: root.povList
                        delegate: ImportCheck {
                            required property var modelData
                            objectName: "newPovChapter"
                            width: parent.width
                            label: modelData.title + S.s_toi_la_90e4c35d + modelData.name
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
    Prose { objectName: "newNarratorAuto"; visible: root.auto; topPadding: visible ? 16 : 0; text: S.s_may_chon_cung_gioi_nguoi_ke_chon_giong_de_48aef3e1 }
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
            text: S.s_giong_ke_phan_truoc_b_font_color_6eeb7918 + Theme.text + "\">" + Logic.esc(root.previous) + "</font></b>" +
                (root.narrator && root.narrator !== root.previous ? S.s_dang_chon_giong_khac_hai_phan_se_doc_loi_d_ef58e52b : "")
        }
    }
    Item {
        width: parent.width
        visible: root.previous !== "" && root.narrator !== "" && root.narrator !== root.previous
        height: visible ? back.height : 0
        TextLink { id: back; objectName: "newPreviousBack"; text: S.s_dung_lai_267968d0 + root.previous; accent: true; onClicked: root.setNarrator(root.previous) }
    }
    Item { width: 1; height: 16 }
    // Đổi giọng
    ImportFold {
        width: parent.width
        storageKey: "voices"
        prefix: "fold.new-project."
        title: S.s_doi_giong_94b6b371
        summary: root.narrator || S.s_chon_mot_giong_749f92a2
        defaultOpen: root.narrator === ""
        Item { width: 1; height: 16 }
        Flow {
            width: parent.width
            spacing: 12
            ChoiceRow {
                objectName: "newVoiceGender"
                width: Math.min(implicitWidth, parent.width)
                label: S.s_gioi_tinh_46eb9a2c
                options: [{value: "all", label: S.s_moi_giong_b0243b7c}, {value: S.s_nam_22dd59c8, label: S.s_giong_nam_4ab78f43}, {value: S.s_nu_e15bc11c, label: S.s_giong_nu_cd860480}]
                value: root.gender
                onPicked: value => root.gender = value
            }
            ChoiceRow {
                objectName: "newVoiceRegion"
                width: Math.min(implicitWidth, parent.width)
                label: S.s_mien_498584a9
                options: [{value: "all", label: S.s_moi_mien_58ed42fb}, {value: S.s_bac_b8cc98f1, label: S.s_mien_bac_67b1bf3b}, {value: S.s_nam_22dd59c8, label: S.s_mien_nam_81505299}, {value: S.s_trung_83080cf9, label: S.s_mien_trung_f313e576}]
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
                    text: S.s_dang_chon_b_font_color_8e90bf67 + Theme.text + "\">" + Logic.esc(root.narrator) + S.s_font_b_bo_loc_dang_an_giong_nay_3e5b0821
                }
                TextLink { id: hiddenClear; objectName: "newVoiceClearFilter"; y: 12 + hiddenText.height; text: S.s_bo_loc_74de0064; accent: true; onClicked: { root.gender = "all"; root.region = "all" } }
            }
        }
        Item { width: 1; height: 16 }
        Flow {
            id: grid
            objectName: "newVoiceGrid"
            width: parent.width
            spacing: 12
            Accessible.role: Accessible.RadioButton
            Accessible.name: S.s_giong_ke_chuyen_4a4e32b1
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
                        label: S.s_nghe_thu_giong_d06e1a82 + card.modelData.name
                        stopLabel: S.s_dung_nghe_031d48f6 + card.modelData.name
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
                                text: TextWrap.keepDots(card.modelData.name)
                                color: card.selected ? Theme.accentText : Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBody
                                font.weight: Theme.weightBold
                                lineHeight: 1.25
                                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                            }
                            Text {
                                width: parent.width
                                topPadding: 4
                                text: card.modelData.gender + S.s_u00a0_u00a0mien_0b77fd18 + card.modelData.region + "\u00a0·\u00a0" + card.modelData.style
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
                                    text: S.s_de_xuat_c576f0da
                                    color: Theme.accentText
                                    font.pixelSize: 12
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
