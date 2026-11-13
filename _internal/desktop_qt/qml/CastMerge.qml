import "UiStrings.js" as S
import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Gộp nhân vật" (MergeDialog của studio/MergePeople.tsx): máy tách một người thành hai tên (tên đầy đủ và tên gọi) - chọn người nhận, mọi câu của người
// này chuyển sang người kia và phần sau của cuốn tự hiểu (POST /api/books/<id>/characters/merge). Không áp ngay: như mọi sửa khác, chờ Studio / áp thay đổi.
CastModal {
    id: root
    panelWidth: 512
    property var person: null
    property var people: []
    property var into: null
    property string query: ""
    readonly property string shownName: person ? Logic.cleanName(person.displayName) : ""
    readonly property var others: Logic.mergeTargets(people, person, query)
    readonly property var twins: Logic.sameNames(people)
    title: S.s_gop_nhan_vat_37b51bd5
    description: S.s_moi_cau_cua_b04c7e8b + shownName + S.s_va_cac_phan_sau_dung_nguoi_ban_chon_7ed4d33d

    function begin(data) {
        generation++
        bookId = data.bookId; person = data.person; people = data.people || []
        into = null; query = ""; saving = false
        search.text = ""
        show()
        search.forceActiveFocus(Qt.TabFocusReason)
    }
    function merge() {
        if (saving || !person || !into) return
        saving = true
        const mine = generation
        const from = person, target = into
        root.ask("POST", "/api/books/" + bookId + "/characters/merge", {from: from.name, into: target.name}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail(S.s_chua_gop_duoc_3d63128a, error); return }
            root.saved()
            Api.notice = S.s_da_ghi_85094402 + (data ? data.lines : 0) + S.s_cau_cua_35c4143d + Logic.cleanName(from.displayName) + S.s_la_cua_315e2a12 + Logic.cleanName(target.displayName)
            root.dismiss()
        })
    }

    Column {
        width: parent.width
        spacing: 12
        FormField {
            id: search
            objectName: "mergeSearch"
            width: parent.width
            label: S.s_tim_nguoi_trong_truyen_a1507054
            placeholderText: S.s_tim_nguoi_trong_truyen_a1507054
            onTextChanged: root.query = text
        }
        // Danh sách người nhận; dài thì cuộn trong khung 256 như web (max-h-64)
        Item {
            width: parent.width
            height: Math.min(256, listColumn.height)
            Behavior on height { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Flickable {
                id: listFlick
                anchors.fill: parent
                contentWidth: width
                contentHeight: listColumn.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Accessible.role: Accessible.List
                Accessible.name: S.s_gop_vao_ai_640d3477
                Column {
                    id: listColumn
                    objectName: "mergeList"
                    width: listFlick.width
                    Repeater {
                        model: root.others
                        Interactive {
                            id: choice
                            required property var modelData
                            objectName: "mergeChoice"
                            readonly property bool selected: root.into !== null && root.into.name === modelData.name
                            width: listColumn.width
                            implicitHeight: Math.max(Theme.buttonHeight, Math.max(nameText.height, metaText.height) + 16)
                            height: implicitHeight
                            ringMargin: 0
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: Logic.cleanName(modelData.displayName)
                            Accessible.checked: selected
                            onClicked: root.into = modelData
                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.radiusControl
                                color: Theme.hover
                                opacity: choice.hovered && !choice.selected ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            }
                            Icon {
                                x: 8
                                anchors.verticalCenter: parent.verticalCenter
                                name: "check"
                                size: 16
                                color: Theme.accentText
                                opacity: choice.selected ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : Theme.motionFast } }
                            }
                            Text {
                                id: nameText
                                x: 32
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, (parent.width - 32 - 8) * 0.5)
                                text: Logic.cleanName(choice.modelData.displayName)
                                color: choice.selected ? Theme.accentText : Theme.text
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeBodySmall
                                font.weight: Theme.weightMedium
                            }
                            Text {
                                id: metaText
                                x: nameText.x + nameText.width + 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - x - 8
                                horizontalAlignment: Text.AlignRight
                                text: Logic.voiceToUse(choice.modelData) + (choice.modelData.pendingVoice && choice.modelData.pendingVoice.preset ? S.s_cho_ap_dung_31faa52d : "")
                                    + "\u00a0·\u00a0" + Logic.formatNumber(choice.modelData.lines) + S.s_cau_b07e1008
                                    + (root.twins[Logic.cleanName(choice.modelData.displayName).toLowerCase()] && choice.modelData.firstChapter ? "\u00a0·\u00a0" + choice.modelData.firstChapter : "")
                                color: Theme.text3
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                            }
                        }
                    }
                    Text {
                        objectName: "mergeNone"
                        Reveal { shown: root.others.length === 0 }
                        width: parent.width
                        leftPadding: 12
                        topPadding: 12
                        bottomPadding: 12
                        text: S.s_khong_co_ai_khop_2213386e + root.query + "”."
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
                SmoothWheel { flick: listFlick }
            }
        }
        Collapse {
            width: parent.width
            open: root.person !== null && root.into !== null
            Text {
                objectName: "mergeSummary"
                width: parent.width
                text: root.person && root.into ? Logic.mergeSummary(root.person, root.into) : ""
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
            }
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "mergeCancel"; text: S.s_thoi_e68f9e88; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "mergeDo"; text: S.s_gop_2380bed6; icon: "git-merge"; busy: root.saving; enabled: root.into !== null; onActivated: root.merge() }
        }
    ]
}
