import QtQuick
import ABook
import "SizeFormat.js" as Size
import "StudioSetupLogic.js" as Setup

// Thẻ "Cài Studio" / "Sửa Studio" / "Cập nhật Studio" ở đầu màn Dự án (StudioSetupCard của studio/StudioSetup.tsx): app đóng gói chưa cài Studio (hay Studio cài từ
// bản app cũ) thì nói cần gì, từng bước, tiến độ, lỗi đọc được, bấm lại là làm tiếp. Dùng StudioSetupState chung với Cài đặt › Studio. Hiện / ẩn bằng
// Collapse (mở khép tại chỗ), chỉ hỏi máy khi cửa sổ đang thấy. Màn hẹp: chữ chiếm cả hàng, nút xuống dưới.
Item {
    id: root
    property var store: null
    property bool active: true
    readonly property alias setup: setup
    readonly property var status: setup.status
    readonly property bool needed: Setup.cardNeeded(setup.info)
    readonly property bool shown: needed && status !== null
    readonly property bool wide: width >= 640
    implicitHeight: reveal.height
    height: implicitHeight
    visible: reveal.visible
    objectName: "studioSetupCard"

    StudioSetupState {
        id: setup
        store: root.store
        wanted: root.active && root.needed
        onFinished: data => {
            if (data.installed && (data.outdated || []).length === 0) {
                Api.notice = "Studio đã sẵn sàng"
                setup.refreshInfo()
            } else if (data.error) {
                Api.notice = "Studio chưa xong\n" + Setup.friendlySetupError(data.error).summary
            }
        }
    }
    property bool details: false
    property var fit: root.status && !root.status.installed ? Setup.studioFit(root.status.gpu) : null
    readonly property var button: root.status ? Setup.cardButton(root.status, root.fit) : ({kind: "go", text: "Cài Studio"})
    readonly property var friendly: root.status && root.status.error ? Setup.friendlySetupError(root.status.error) : ({summary: "", detail: ""})

    function press() {
        const kind = button.kind
        if (kind === "cancel" || kind === "cancelOld") setup.cancel(function(ok, data) { if (!ok) setup.failure("Chưa cài được Studio", data) })
        else if (kind === "go" || kind === "unfit") setup.install(function(ok, data) { if (!ok) setup.failure("Chưa cài được Studio", data) })
    }

    Collapse {
        id: reveal
        width: parent.width
        open: root.shown
        Column {
            width: parent.width
            topPadding: 32
            bottomPadding: 8
            Flow {
                width: parent.width
                spacing: 16
                Rectangle {
                    width: 44; height: 44
                    radius: Theme.radiusCover
                    color: Theme.accentSoft
                    Icon { anchors.centerIn: parent; name: "cpu"; size: 20; color: Theme.accentText }
                }
                Column {
                    objectName: "studioSetupText"
                    width: root.wide ? parent.width - 44 - 16 - actions.width - 16 : parent.width
                    spacing: 4
                    Text {
                        objectName: "studioSetupTitle"
                        width: parent.width
                        text: root.status ? Setup.cardTitle(root.status) : ""
                        color: Theme.text
                        wrapMode: Text.Wrap
                        font.pixelSize: 16
                        font.weight: Theme.weightBold
                    }
                    Text {
                        objectName: "studioSetupLine"
                        width: Math.min(parent.width, 672)
                        text: root.status ? Setup.cardLine(root.status) : ""
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        lineHeight: 1.45
                        font.pixelSize: 13
                    }
                    Text {
                        objectName: "studioSetupFit"
                        visible: root.fit !== null
                        topPadding: 4
                        width: Math.min(parent.width, 672)
                        text: root.fit ? (root.fit.level === "no" ? Setup.noStudioLine(root.fit.reason || "") : root.fit.line) : ""
                        color: root.fit && root.fit.level === "no" ? Theme.text : Theme.text2
                        font.weight: root.fit && root.fit.level === "no" ? Theme.weightMedium : Theme.weightRegular
                        wrapMode: Text.Wrap
                        lineHeight: 1.45
                        font.pixelSize: 13
                    }
                }
                Row {
                    id: actions
                    spacing: 8
                    Button {
                        objectName: "studioSetupButton"
                        text: root.button.text
                        kind: root.button.kind === "unfit" || root.button.kind === "wait" ? "ghost" : (root.button.kind === "cancel" || root.button.kind === "cancelOld") ? "ghost" : "primary"
                        size: root.button.kind === "unfit" ? "sm" : "md"
                        icon: root.button.kind === "cancel" || root.button.kind === "cancelOld" ? "square" : "download"
                        enabled: root.button.kind !== "wait" && !setup.busy
                        onActivated: root.press()
                    }
                }
            }
            Text {
                objectName: "studioSetupLeftover"
                visible: !!root.status && !!root.status.leftover && !root.status.running
                width: parent.width
                topPadding: 16
                text: root.status && root.status.leftover ? Setup.leftoverLine(root.status.leftover) : ""
                color: Theme.text
                wrapMode: Text.Wrap
                lineHeight: 1.45
                font.pixelSize: 13
            }
            Column {
                objectName: "studioSetupError"
                visible: !!root.status && !!root.status.error && !root.status.running && !root.status.leftover
                width: parent.width
                topPadding: 16
                spacing: 4
                Text { width: parent.width; text: root.friendly.summary; color: Theme.danger; wrapMode: Text.Wrap; lineHeight: 1.45; font.pixelSize: 13 }
                Interactive {
                    visible: root.friendly.detail !== ""
                    objectName: "studioSetupDetailsToggle"
                    implicitWidth: toggleText.implicitWidth
                    implicitHeight: 24
                    Accessible.role: Accessible.Button
                    Accessible.name: toggleText.text
                    onClicked: root.details = !root.details
                    Text { id: toggleText; anchors.verticalCenter: parent.verticalCenter; text: "Chi tiết"; color: Theme.danger; font.pixelSize: Theme.sizeCaption }
                }
                Text {
                    visible: root.details && root.friendly.detail !== ""
                    width: parent.width
                    text: root.friendly.detail
                    color: Theme.danger
                    textFormat: Text.PlainText
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.family: "Consolas"
                    font.pixelSize: Theme.sizeCaption
                }
            }
            // Từng bước (khi đang cài hay đã cài dở)
            Grid {
                objectName: "studioSetupSteps"
                visible: !!root.status && (root.status.running || Setup.started(root.status))
                width: parent.width
                topPadding: 20
                columns: root.wide ? 2 : 1
                columnSpacing: 32
                rowSpacing: 6
                Repeater {
                    model: root.status ? root.status.steps || [] : []
                    delegate: Row {
                        required property var modelData
                        readonly property bool activeStep: !!root.status && root.status.running && modelData.id === root.status.step
                        width: (parent.width - (root.wide ? 32 : 0)) / (root.wide ? 2 : 1)
                        spacing: 10
                        Item {
                            width: 16; height: 20
                            Icon { anchors.centerIn: parent; visible: modelData.done; name: "check"; size: 16; color: Theme.accentText }
                            Icon {
                                id: spinner
                                anchors.centerIn: parent
                                visible: !modelData.done && parent.parent.activeStep
                                name: "loader-circle"; size: 16; color: Theme.accentText
                                RotationAnimator on rotation { running: spinner.visible && Nav.uiVisible && !Theme.reduceMotion; from: 0; to: 360; duration: 1000; loops: Animation.Infinite }
                            }
                            Rectangle {
                                anchors.centerIn: parent
                                visible: !modelData.done && !parent.parent.activeStep
                                width: 16; height: 16; radius: width / 2
                                color: "transparent"; border.width: 1; border.color: Theme.controlLine
                            }
                        }
                        Text {
                            width: parent.width - 26
                            text: modelData.label + (modelData.hint ? " · " + modelData.hint : "")
                            color: parent.activeStep ? Theme.text : Theme.text2
                            font.weight: parent.activeStep ? Theme.weightBold : Theme.weightRegular
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                        }
                    }
                }
            }
            Column {
                objectName: "studioSetupProgress"
                visible: !!root.status && root.status.running && Setup.currentStep(root.status) !== null
                width: parent.width
                topPadding: 16
                spacing: 6
                StudioBar {
                    width: parent.width
                    size: "sm"
                    value: root.status ? Math.max(0, Setup.progressOf(root.status)) : 0
                    label: "Tiến độ: " + (root.status && Setup.currentStep(root.status) ? Setup.currentStep(root.status).label : "")
                }
                Item {
                    width: parent.width
                    height: Math.max(detail.height, sizes.height)
                    Text {
                        id: detail
                        width: parent.width - (sizes.visible ? sizes.width + 16 : 0)
                        text: root.status ? (root.status.detail || (Setup.currentStep(root.status) ? Setup.currentStep(root.status).label : "")) : ""
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeCaption
                    }
                    Text {
                        id: sizes
                        objectName: "studioSetupSizes"
                        visible: !!root.status && !!root.status.progress && root.status.progress.total > 0
                        anchors.right: parent.right
                        text: root.status && root.status.progress ? Size.formatSize(root.status.progress.done) + " / " + Size.formatSize(root.status.progress.total) : ""
                        color: Theme.text2
                        font.pixelSize: Theme.sizeCaption
                        font.features: { "tnum": 1 }
                    }
                }
            }
        }
    }
}
