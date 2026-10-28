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
    title: "Gộp nhân vật"
    description: "Mọi câu của " + shownName + " và các phần sau dùng người bạn chọn."

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
        Api.quiet("POST", "/api/books/" + bookId + "/characters/merge", {from: from.name, into: target.name}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail("Chưa gộp được", error); return }
            root.saved()
            Api.notice = "Đã ghi: " + (data ? data.lines : 0) + " câu của " + Logic.cleanName(from.displayName) + " là của " + Logic.cleanName(target.displayName)
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
            label: "Tìm người trong truyện…"
            placeholderText: "Tìm người trong truyện…"
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
                Accessible.name: "Gộp vào ai"
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
                                text: Logic.voiceToUse(choice.modelData) + (choice.modelData.pendingVoice && choice.modelData.pendingVoice.preset ? " (chờ áp dụng)" : "")
                                    + " · " + Logic.formatNumber(choice.modelData.lines) + " câu"
                                    + (root.twins[Logic.cleanName(choice.modelData.displayName).toLowerCase()] && choice.modelData.firstChapter ? " · " + choice.modelData.firstChapter : "")
                                color: Theme.text3
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                font.pixelSize: Theme.sizeCaption
                            }
                        }
                    }
                    Text {
                        objectName: "mergeNone"
                        visible: root.others.length === 0
                        width: parent.width
                        leftPadding: 12
                        topPadding: 12
                        bottomPadding: 12
                        text: "Không có ai khớp “" + root.query + "”."
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
            Button { objectName: "mergeCancel"; text: "Thôi"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "mergeDo"; text: "Gộp"; icon: "git-merge"; busy: root.saving; enabled: root.into !== null; onActivated: root.merge() }
        }
    ]
}
